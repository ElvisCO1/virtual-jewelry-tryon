"""Coordinate detection, geometry, orientation, and rendering for each frame."""

from contextlib import ExitStack, closing
import time

import cv2

from .camera import open_camera
from .config import AppConfig
from .hand_detection import HandDetector, draw_landmarks, print_landmarks
from .geometry import ring_finger_geometry
from .geometry_view import draw_geometry
from .ring_overlay import load_ring, overlay_ring
from .smoothing import HandPoseSmoother, RingPose
from .hand_orientation import estimate_orientation, select_ring_view, SurfaceTracker


class FrameProcessor:
    """Shared frame pipeline for the desktop interface and OpenCV preview."""

    def __init__(self, config, detector):
        self.config = config
        self.detector = detector
        self.ring = load_ring(config.ring) if config.ring else None
        self.ring_views = ({"front": load_ring(config.ring_front), "back": load_ring(config.ring_back)}
                           if config.ring_front else {})
        self.smoother = HandPoseSmoother(config.smoothing)
        self.surface_tracker = SurfaceTracker()
        self._debug = None

    def process(self, frame, show_references=True):
        """Return the annotated frame without opening a display window."""
        result = self.detector.detect(frame)
        height, width = frame.shape[:2]
        geometries = [
            ring_finger_geometry(landmarks, width, height)
            for landmarks in result.hand_landmarks
        ]
        orientations = [
            estimate_orientation(landmarks, hand[0].category_name, hand[0].score,
                                 width, height, self.config.input_mirrored)
            for landmarks, hand in zip(result.hand_landmarks, result.handedness)
        ]
        labels = [orientation.handedness for orientation in orientations]
        surfaces = self.surface_tracker.update(orientations)
        views = [select_ring_view(surface, self.config.swap_ring_views) for surface in surfaces]
        poses = [
            RingPose(g.midpoint, g.distance_px * self.config.width_ratio, g.angle_deg)
            if g.angle_deg is not None and g.distance_px >= 2 else None
            for g in geometries
        ]
        poses = self.smoother.update(labels, poses, time.monotonic())
        # Visibility affects drawing only; detection and ring geometry always run.
        if show_references:
            draw_landmarks(frame, result)
        orientation_lines = []
        for orientation, surface, view in zip(orientations, surfaces, views):
            asset_status = (f"ring_{view}.png" if view else "hidden (uncertain)")
            if not self.ring_views:
                asset_status = "single PNG" if self.ring is not None else f"{view or 'none'} (no PNG loaded)"
            orientation_lines.append([
                f"Side: {surface} | estimate: {orientation.surface}",
                f"L/R confidence: {orientation.confidence:.2f}",
                f"Ring view: {asset_status}",
            ])
        display_frame = draw_geometry(
            frame, geometries, labels, orientation_lines, show_references=show_references
        )
        for pose, view in zip(poses, views):
            selected_ring = self.ring_views.get(view) if self.ring_views else self.ring
            if selected_ring is not None:
                overlay_ring(display_frame[:height, :width], selected_ring, pose, self.config.asset_angle)
        self._debug = result, frame.shape, orientations, surfaces, views
        return display_frame

    def print_debug(self):
        if self._debug is None:
            return
        result, shape, orientations, surfaces, views = self._debug
        print_landmarks(result, shape)
        for index, (orientation, surface, view) in enumerate(zip(orientations, surfaces, views)):
            print(f"H{index}: {orientation}; stable={surface}; selected_view={view}")


class PreviewSession:
    """Own a camera and detector between explicit start/stop operations."""

    def __init__(self, config):
        self.config = config
        self._resources = None
        self.camera = None
        self.processor = None
        # Session-level preference survives camera stop/start and processor recreation.
        self.show_references = True

    @property
    def active(self):
        return self._resources is not None

    def start(self):
        if self.active:
            return
        # Roll back partial startup if the camera, model, or PNG cannot load.
        with ExitStack() as resources:
            camera = resources.enter_context(open_camera())
            detector = resources.enter_context(closing(HandDetector()))
            processor = FrameProcessor(self.config, detector)
            self.camera, self.processor = camera, processor
            self._resources = resources.pop_all()

    def read(self):
        if not self.active:
            raise RuntimeError("La cámara está desactivada.")
        success, frame = self.camera.read()
        if not success:
            raise RuntimeError("No se pudo leer la cámara. Comprueba su conexión.")
        return self.processor.process(frame, show_references=self.show_references)

    def stop(self):
        resources, self._resources = self._resources, None
        self.camera = self.processor = None
        if resources is not None:
            resources.close()


def run(config: AppConfig) -> int:
    """Optional original OpenCV preview for troubleshooting."""
    session = PreviewSession(config)
    try:
        session.start()
        print("Focus the video window: q quits, d prints landmark coordinates.")
        while True:
            cv2.imshow("Hand Orientation", session.read())
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                return 0
            if key == ord("d"):
                session.processor.print_debug()
    finally:
        session.stop()
