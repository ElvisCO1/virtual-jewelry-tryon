"""Ring-finger geometry in image pixels; independent of OpenCV and MediaPipe."""

from dataclasses import dataclass
from math import atan2, degrees, hypot


RING_FINGER_INDICES = (13, 14, 15, 16)  # MCP, PIP, DIP, fingertip


@dataclass(frozen=True)
class RingFingerGeometry:
    points: tuple[tuple[float, float], ...]
    midpoint: tuple[float, float]
    distance_px: float
    angle_deg: float | None


def ring_finger_geometry(landmarks, width, height):
    """Measure MCP -> PIP from landmarks with normalized .x and .y attributes.

    The midpoint of this base segment is a candidate placement reference, not a
    fitted ring position. Length is the projected segment length, not finger width.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive.")

    # Scale each axis separately BEFORE measuring: normalized coordinates would
    # distort lengths and angles when the image width and height differ.
    points = tuple(
        (landmarks[index].x * width, landmarks[index].y * height)
        for index in RING_FINGER_INDICES
    )
    (x1, y1), (x2, y2) = points[:2]
    dx, dy = x2 - x1, y2 - y1

    # The midpoint averages the endpoints; Euclidean distance is sqrt(dx² + dy²).
    midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
    distance = hypot(dx, dy)

    # atan2 handles all quadrants and vertical fingers without dividing by dx.
    # Image y increases DOWN, so +90° points down and -90° points up.
    # Coincident endpoints have no meaningful orientation.
    angle = degrees(atan2(dy, dx)) if distance > 1e-6 else None
    return RingFingerGeometry(points, midpoint, distance, angle)
