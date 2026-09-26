"""Explainable left/right and palm/back estimation; no additional model."""

from dataclasses import dataclass
from math import hypot, isfinite


@dataclass(frozen=True)
class HandOrientation:
    handedness: str
    confidence: float  # MediaPipe handedness confidence, NOT palm/back probability.
    surface: str       # Palm, Back, or Unknown.
    signed_area: float # Normalized signed cross product, after mirror correction.


def estimate_orientation(landmarks, handedness, confidence, width, height,
                         input_mirrored=False):
    """Use the projected wrist/index-MCP/pinky-MCP triangle and handedness.

    Assumes MediaPipe Tasks labels on ordinary unmirrored camera frames. If the
    camera driver already mirrors the input, correct BOTH handedness and winding.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive.")
    if handedness not in ("Left", "Right"):
        return HandOrientation("Unknown", confidence, "Unknown", 0.0)
    if input_mirrored:
        handedness = "Left" if handedness == "Right" else "Right"

    wrist, index, pinky = (landmarks[i] for i in (0, 5, 17))
    ux, uy = (index.x - wrist.x) * width, (index.y - wrist.y) * height
    vx, vy = (pinky.x - wrist.x) * width, (pinky.y - wrist.y) * height
    lengths = hypot(ux, uy), hypot(vx, vy)
    if not all(isfinite(value) for value in (*lengths, confidence)) or min(lengths) < 2:
        return HandOrientation(handedness, confidence, "Unknown", 0.0)

    # cross = twice the signed projected triangle area. Dividing by |u||v|
    # makes it scale-independent (sin of the angle between the palm vectors).
    signed_area = (ux * vy - uy * vx) / (lengths[0] * lengths[1])
    if input_mirrored:
        signed_area = -signed_area
    # Near-collinear palm vectors indicate an edge-on/degenerate projection.
    # These are heuristic cutoffs, not calibrated palm/back probabilities.
    if confidence < 0.6 or abs(signed_area) < 0.15:
        surface = "Unknown"
    else:
        # Unmirrored right palm has negative winding; left palm has positive.
        palm_sign = -1 if handedness == "Right" else 1
        surface = "Palm" if signed_area * palm_sign > 0 else "Back"
    return HandOrientation(handedness, confidence, surface, signed_area)


def select_ring_view(surface, swap=False):
    """Decorative front faces the back of the hand; band/back faces the palm."""
    view = {"Back": "front", "Palm": "back"}.get(surface)
    if swap and view is not None:
        view = "back" if view == "front" else "front"
    return view


class SurfaceTracker:
    """Require three consecutive estimates before changing a hand's ring view."""

    def __init__(self, confirm_frames=3):
        if confirm_frames < 1:
            raise ValueError("confirm_frames must be positive.")
        self.confirm_frames = confirm_frames
        self._states = {}

    def update(self, orientations):
        labels = [orientation.handedness for orientation in orientations]
        active = {o.handedness for o in orientations
                  if o.surface != "Unknown" and labels.count(o.handedness) == 1}
        # Loss, uncertainty, or duplicate handedness clears state rather than
        # transferring an old view to another hand. Ambiguous views hide the ring.
        self._states = {key: state for key, state in self._states.items() if key in active}
        surfaces = []
        for orientation in orientations:
            key, candidate = orientation.handedness, orientation.surface
            if key not in active:
                surfaces.append("Unknown")
                continue
            stable, pending, count = self._states.get(key, ("Unknown", "Unknown", 0))
            count = count + 1 if candidate == pending else 1
            if count >= self.confirm_frames:
                stable = candidate
            self._states[key] = stable, candidate, min(count, self.confirm_frames)
            surfaces.append(stable)
        return surfaces
