"""Coordinate detection, geometry, orientation, and rendering for each frame."""

from contextlib import ExitStack, closing
from dataclasses import asdict, replace
from datetime import datetime, timezone
from uuid import uuid4
import time
from math import isfinite

import cv2

from .camera import open_camera
from .config import AppConfig
from .hand_detection import HandDetector, draw_landmarks, print_landmarks
from .geometry import ring_finger_geometry, placement_point, FINGER_INDICES
from .geometry_view import draw_geometry
from .ring_overlay import load_ring, overlay_ring
from .occlusion import METHOD as OCCLUSION_METHOD
from .finger_width import estimate_width
from .manual_width import width_reference, draw_width_reference
from .features import FINGER_WIDTH_ENABLED
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
        self.last_snapshot = None
        self._placement_settings = None
        self.last_widths = []

    def process(self, frame, show_references=True, manual_view=None, show_ring=True,
                finger="ring", position=0.5, occlusion=False, size_factor=1.0, calibration=None,
                measure_width=FINGER_WIDTH_ENABLED, show_manual_width=False, manual_width_ratio=0.6):
        """Return the annotated frame without opening a display window."""
        if not isfinite(size_factor) or not 0.5 <= size_factor <= 2.0:
            raise ValueError("Ring size factor must be between 0.5 and 2.0.")
        if not isfinite(manual_width_ratio) or not .1 <= manual_width_ratio <= 2:
            raise ValueError("Manual width ratio must be between 0.1 and 2.0.")
        frame_time = datetime.now(timezone.utc).isoformat()
        result = self.detector.detect(frame)
        height, width = frame.shape[:2]
        geometries = [
            ring_finger_geometry(landmarks, width, height, finger)
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
            RingPose(placement_point(g, position), g.distance_px * self.config.width_ratio, g.angle_deg)
            if g.angle_deg is not None and g.distance_px >= 2 else None
            for g in geometries
        ]
        raw_poses = poses
        if self._placement_settings != (finger, position):
            # Do not drag the ring across fingers or lag behind manual adjustment.
            self.smoother = HandPoseSmoother(self.config.smoothing)
            self._placement_settings = (finger, position)
        poses = self.smoother.update(labels, poses, time.monotonic())
        manual_widths = [width_reference(p, g.distance_px, manual_width_ratio)
                         for p, g in zip(poses, geometries)] if show_manual_width else None
        # Measure the original camera image BEFORE landmarks or jewelry are drawn.
        widths = [estimate_width(frame, p.center, p.angle, g.distance_px) if p else None
                  for p, g in zip(poses, geometries)] if measure_width else [None] * len(poses)
        self.last_widths = []
        for label, measurement in zip(labels, widths):
            context = {'hand': label, 'finger': finger, 'position': position,
                       'frame_size': [width, height]}
            if measurement is not None:
                measurement['width_mm'] = None
                if calibration and len(labels) == 1 and calibration['context'] == context:
                    measurement['width_mm'] = measurement['width_px'] * calibration['mm_per_pixel']
                self.last_widths.append({'context': context, 'measurement': measurement})
        # Visibility affects drawing only; detection and ring geometry always run.
        if show_references:
            draw_landmarks(frame, result)
        orientation_lines = []
        for orientation, surface, view in zip(orientations, surfaces, views):
            asset_status = (f"ring_{view}.png" if view else "hidden (uncertain)")
            if not self.ring_views:
                asset_status = "single PNG" if self.ring is not None else f"{view or 'none'} (no PNG loaded)"
            if manual_view is not None:
                asset_status = manual_view.filename
            orientation_lines.append([
                f"Side: {surface} | estimate: {orientation.surface}",
                f"L/R confidence: {orientation.confidence:.2f}",
                f"Ring view: {asset_status}",
            ])
        display_frame = draw_geometry(
            frame, geometries, labels, orientation_lines, show_references=show_references,
            finger=finger, placement_centers=[p.center if p else None for p in poses],
            widths=widths if measure_width else None, manual_widths=manual_widths
        )
        for pose, view in zip(poses, views):
            # Apply user sizing after tracking so it responds immediately without
            # changing the smoothed position, angle or base width history.
            if pose is not None:
                pose = replace(pose, width=pose.width * size_factor)
            selected_ring = self.ring_views.get(view) if self.ring_views else self.ring
            if manual_view is not None:
                selected_ring = manual_view.image
                if pose is not None:
                    # Compensate only for transparent padding, after pose smoothing.
                    pose = replace(pose, width=pose.width * manual_view.width_scale)
            if show_ring and selected_ring is not None:
                options = {"occlusion": True} if occlusion else {}
                overlay_ring(display_frame[:height, :width], selected_ring, pose, self.config.asset_angle, **options)
        self._debug = result, frame.shape, orientations, surfaces, views
        # Independent of landmarks and ring visibility; draw last for comparison.
        for reference in manual_widths or []:
            draw_width_reference(display_frame[:height, :width], reference)
        self.last_snapshot = None
        if manual_view is not None:
            # Copy numerical values from THIS frame, never store image arrays.
            def points(values):
                return [{"x": float(p.x), "y": float(p.y), "z": float(p.z)} for p in values]

            world = getattr(result, "hand_world_landmarks", [])
            self.last_snapshot = {
                "frame_id": str(uuid4()), "frame_time_utc": frame_time,
                "frame_size": [width, height],
                "image": {"filename": manual_view.filename, "azimuth_category": manual_view.azimuth,
                          "elevation_category": manual_view.elevation, "width_scale": manual_view.width_scale},
                "settings": {"input_mirrored": self.config.input_mirrored,
                             "width_ratio": self.config.width_ratio, "asset_angle": self.config.asset_angle,
                             "smoothing": self.config.smoothing, "show_references": show_references,
                             "show_ring": show_ring, "finger": finger, "size_factor": size_factor,
                             "width_measurement_enabled": measure_width,
                             "show_manual_width": show_manual_width,
                             "manual_width_ratio": manual_width_ratio,
                             "width_calibration": calibration if measure_width else None,
                             "occlusion": occlusion, "occlusion_method": OCCLUSION_METHOD if occlusion else None,
                             "position_fraction": position, "landmark_indices": list(FINGER_INDICES[finger])},
                "hands": [{
                    "frame_hand_index": i, "handedness": o.handedness,
                    "confidence": float(o.confidence), "surface": o.surface,
                    "landmarks_normalized": points(result.hand_landmarks[i]),
                    "world_landmarks_m": points(world[i]) if i < len(world) else None,
                    "geometry_px": asdict(geometries[i]),
                    "finger_width": widths[i],
                    "manual_width_reference": manual_widths[i] if manual_widths is not None else None,
                    "raw_pose": asdict(raw_poses[i]) if raw_poses[i] else None,
                    "smoothed_pose": asdict(poses[i]) if poses[i] else None,
                    "requested_overlay_width_px": poses[i].width * size_factor * manual_view.width_scale if poses[i] else None,
                    "eligible": show_ring and poses[i] is not None and labels.count(o.handedness) == 1
                                and o.handedness in ("Left", "Right") and o.confidence >= 0.6,
                } for i, o in enumerate(orientations)],
            }
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
        self.show_ring = True
        self.finger = "ring"
        self.position = 0.5
        self.occlusion = False
        self.size_factor = 1.0
        self.show_manual_width = False
        self.manual_width_ratio = 0.6
        self.calibration = None
        self.manual_view = None

    @property
    def active(self):
        return self._resources is not None

    @property
    def last_snapshot(self):
        return self.processor.last_snapshot if self.processor else None

    @property
    def last_widths(self):
        return self.processor.last_widths if self.processor else []

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
        return self.processor.process(
            frame, show_references=self.show_references, manual_view=self.manual_view,
            show_ring=self.show_ring, finger=self.finger, position=self.position,
            occlusion=self.occlusion, size_factor=self.size_factor, calibration=self.calibration,
            show_manual_width=self.show_manual_width, manual_width_ratio=self.manual_width_ratio
        )

    def stop(self):
        self.calibration = None
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
