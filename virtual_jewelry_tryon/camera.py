"""OpenCV camera ownership and guaranteed resource cleanup."""

from contextlib import contextmanager

import cv2


@contextmanager
def open_camera(index=0):
    """Open the default webcam and release it on success, failure, or Ctrl+C."""
    camera = cv2.VideoCapture(index)
    try:
        if not camera.isOpened():
            raise RuntimeError(
                "Could not open the default webcam. Check its connection, camera "
                "permissions, and whether another app is using it."
            )
        yield camera
    finally:
        camera.release()
        cv2.destroyAllWindows()
