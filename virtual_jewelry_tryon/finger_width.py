"""Local image-edge width estimate; landmarks locate the scan, not skin borders."""
from math import cos, sin, radians

import cv2
import numpy as np


def estimate_width(frame, center, angle, segment_length):
    """Median of five perpendicular scans; reject missing/inconsistent edges.

    Contrast edges are only candidates: shadows and neighboring fingers can fool
    this heuristic. No physical units or stale measurements are inferred here.
    """
    if center is None or angle is None or segment_length < 8:
        return None
    radius = min(160, int(segment_length * .8))
    if radius < 5:
        return None
    theta = radians(angle)
    axis = np.array([cos(theta), sin(theta)])
    normal = np.array([-sin(theta), cos(theta)])
    offsets = np.arange(-radius, radius + 1, dtype=np.float32)
    profiles = []
    for shift in np.linspace(-.12, .12, 5) * segment_length:
        coords = np.asarray(center) + shift * axis + offsets[:, None] * normal
        if (coords[:, 0].min() < 0 or coords[:, 1].min() < 0 or
                coords[:, 0].max() >= frame.shape[1]-1 or coords[:, 1].max() >= frame.shape[0]-1):
            continue
        samples = cv2.remap(frame, coords[:, 0].astype(np.float32)[None, :],
                            coords[:, 1].astype(np.float32)[None, :], cv2.INTER_LINEAR)
        smooth = cv2.GaussianBlur(samples.astype(np.float32), (5, 1), 0)[0]
        gradient = np.linalg.norm(smooth[2:] - smooth[:-2], axis=1) / 2
        positions = offsets[1:-1]
        threshold = max(12., float(np.median(gradient) * 3))
        peaks = (gradient > threshold)
        peaks[1:-1] &= (gradient[1:-1] >= gradient[:-2]) & (gradient[1:-1] >= gradient[2:])
        left = positions[peaks & (positions < -3)]
        right = positions[peaks & (positions > 3)]
        if left.size and right.size:
            a, b = float(left[-1]), float(right[0])
            if .15 * segment_length <= b-a <= 1.4 * segment_length:
                profiles.append((a, b))
    if len(profiles) < 3:
        return None
    values = np.array(profiles)
    if np.max(np.ptp(values, axis=0)) > max(3, segment_length * .12):
        return None
    a, b = np.median(values, axis=0)
    return {'width_px': float(b-a),
            'endpoints': [(np.asarray(center) + t * normal).tolist() for t in (a, b)],
            'scan_count': len(profiles), 'method': 'local_edges_v1'}
