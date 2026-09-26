"""Time-based smoothing of 2D ring poses, independent of camera and rendering."""

from dataclasses import dataclass
from math import exp, hypot, isfinite


@dataclass(frozen=True)
class RingPose:
    center: tuple[float, float]
    width: float
    angle: float  # MCP -> PIP angle in screen coordinates (clockwise positive).


class PoseSmoother:
    """Exponential smoothing with shortest-path angles; one instance per hand."""

    def __init__(self, time_constant=0.12):
        if not isfinite(time_constant) or time_constant < 0:
            raise ValueError("Smoothing time constant must be finite and nonnegative.")
        self.time_constant = time_constant
        self.reset()

    def reset(self):
        self._pose = None
        self._timestamp = None

    def update(self, pose, timestamp):
        previous = self._pose
        dt = timestamp - self._timestamp if self._timestamp is not None else 0
        # Reinitialize after a gap or large jump instead of dragging a stale ring.
        jump = previous is not None and hypot(
            pose.center[0] - previous.center[0], pose.center[1] - previous.center[1]
        ) > max(100, previous.width * 3)
        if previous is None or dt <= 0 or dt > 0.5 or jump or self.time_constant == 0:
            smoothed = pose
        else:
            # Continuous-time EMA: consistent response at different frame rates.
            alpha = 1 - exp(-dt / self.time_constant)
            center = tuple(a + alpha * (b - a) for a, b in zip(previous.center, pose.center))
            width = previous.width + alpha * (pose.width - previous.width)
            # 179 -> -179 is a +2 degree move, not a -358 degree spin.
            delta = (pose.angle - previous.angle + 180) % 360 - 180
            angle = (previous.angle + alpha * delta + 180) % 360 - 180
            smoothed = RingPose(center, width, angle)
        self._pose, self._timestamp = smoothed, timestamp
        return smoothed


class HandPoseSmoother:
    """Keep separate histories by handedness, never by unstable result-list index."""

    def __init__(self, time_constant=0.12):
        self.time_constant = time_constant
        self._hands = {}

    def update(self, labels, poses, timestamp):
        # Missing, invalid, or duplicate labels discard history. For ambiguous
        # handedness, use the current pose without mixing two people's hands.
        unique = {label for label in labels if labels.count(label) == 1}
        active = {label for label, pose in zip(labels, poses) if label in unique and pose is not None}
        self._hands = {label: smoother for label, smoother in self._hands.items() if label in active}
        output = []
        for label, pose in zip(labels, poses):
            if pose is None or label not in unique:
                output.append(pose)
                continue
            if label not in self._hands:
                self._hands[label] = PoseSmoother(self.time_constant)
            output.append(self._hands[label].update(pose, timestamp))
        return output
