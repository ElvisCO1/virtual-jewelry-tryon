"""MediaPipe hand detection, drawing, and debugging independent of the webcam."""

from pathlib import Path
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from .config import MODEL_PATH

# MediaPipe's 21 landmark indices, from the wrist through each finger.
LANDMARK_NAMES = (
    "WRIST",
    "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
    "INDEX_MCP", "INDEX_PIP", "INDEX_DIP", "INDEX_TIP",
    "MIDDLE_MCP", "MIDDLE_PIP", "MIDDLE_DIP", "MIDDLE_TIP",
    "RING_MCP", "RING_PIP", "RING_DIP", "RING_TIP",
    "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP",
)
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


class HandDetector:
    """Process consecutive BGR frames and return MediaPipe landmark results."""

    def __init__(self, model_path=MODEL_PATH, max_hands=2):
        if not Path(model_path).is_file():
            raise FileNotFoundError(
                f"Hand model not found: {model_path}. Follow the model setup in README.md."
            )

        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            # Synchronous video mode keeps each result paired with its input frame.
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def detect(self, frame):
        """Return a result; result.hand_landmarks is empty when no hand is found."""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        # MediaPipe requires strictly increasing timestamps in video mode.
        timestamp_ms = max(time.monotonic_ns() // 1_000_000, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        return self._landmarker.detect_for_video(image, timestamp_ms)

    def close(self):
        """Release MediaPipe resources when the camera loop ends."""
        self._landmarker.close()


def draw_landmarks(frame, result):
    """Draw joints and connections directly on the supplied BGR frame."""
    height, width = frame.shape[:2]
    for landmarks in result.hand_landmarks:
        points = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
        for start, end in HAND_CONNECTIONS:
            cv2.line(frame, points[start], points[end], (0, 255, 0), 2)
        for point in points:
            cv2.circle(frame, point, 4, (0, 0, 255), -1)


def print_landmarks(result, frame_shape):
    """Print all normalized coordinates and pixel positions for one frame."""
    height, width = frame_shape[:2]
    if not result.hand_landmarks:
        print("No hands detected in this frame.")
        return

    for hand_index, landmarks in enumerate(result.hand_landmarks):
        handedness = result.handedness[hand_index][0]
        print(f"\nHand {hand_index}: {handedness.category_name} ({handedness.score:.2f})")
        print(" ID  Landmark        x        y        z       pixel_x pixel_y")
        for index, lm in enumerate(landmarks):
            print(
                f" {index:2d}  {LANDMARK_NAMES[index]:12s} "
                f"{lm.x:8.4f} {lm.y:8.4f} {lm.z:8.4f} "
                f"{int(lm.x * width):7d} {int(lm.y * height):7d}"
            )
