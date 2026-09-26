"""Proportional ring scaling, bounded rotation, and alpha compositing."""

from math import ceil

import cv2
import numpy as np


def load_ring(path):
    """Load one tightly cropped BGRA PNG; its center is the placement anchor."""
    ring = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if ring is None:
        raise ValueError(f"Could not read ring PNG: {path}")
    if ring.ndim != 3 or ring.shape[2] != 4 or ring.dtype != np.uint8:
        raise ValueError("Use an 8-bit PNG with an alpha channel containing one ring.")
    if not np.any(ring[:, :, 3]):
        raise ValueError("The ring PNG is completely transparent.")
    return ring


def transform_ring(ring, width, finger_angle, asset_angle=-90):
    """Return rotated, premultiplied BGRA floats; preserve the PNG's aspect ratio.

    asset_angle is the direction a finger would point in the unrotated PNG.
    Default -90 means the asset is designed for an upright finger.
    """
    height, original_width = ring.shape[:2]
    scale = width / original_width  # One scale factor preserves proportions.
    # OpenCV's positive rotation is counterclockwise; screen angles are clockwise.
    rotation = asset_angle - finger_angle
    matrix = cv2.getRotationMatrix2D(((original_width - 1) / 2, (height - 1) / 2), rotation, scale)
    cos_scale, sin_scale = abs(matrix[0, 0]), abs(matrix[0, 1])
    # Expand the canvas so the rotated PNG's corners are not clipped.
    out_width = max(1, ceil(original_width * cos_scale + height * sin_scale))
    out_height = max(1, ceil(height * cos_scale + original_width * sin_scale))
    matrix[0, 2] += (out_width - original_width) / 2
    matrix[1, 2] += (out_height - height) / 2

    # Interpolate premultiplied colors and alpha together to avoid dark fringes.
    premultiplied = ring.astype(np.float32) / 255
    premultiplied[:, :, :3] *= premultiplied[:, :, 3:4]
    return cv2.warpAffine(premultiplied, matrix, (out_width, out_height),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(0, 0, 0, 0))


def overlay_ring(frame, ring, pose, asset_angle=-90):
    """Blend a transformed ring in place, clipping safely at the frame edges."""
    if pose is None:
        return
    # Bound output allocation for very large/partially offscreen landmark estimates.
    max_side = 2 * max(frame.shape[:2])
    max_width = max_side / (1 + ring.shape[0] / ring.shape[1])
    width = min(max(1, pose.width), max_width)
    transformed = transform_ring(ring, width, pose.angle, asset_angle)
    height, width = transformed.shape[:2]
    left = round(pose.center[0] - (width - 1) / 2)
    top = round(pose.center[1] - (height - 1) / 2)
    x1, y1 = max(0, left), max(0, top)
    x2, y2 = min(frame.shape[1], left + width), min(frame.shape[0], top + height)
    if x1 >= x2 or y1 >= y2:
        return
    source = transformed[y1 - top:y2 - top, x1 - left:x2 - left]
    target = frame[y1:y2, x1:x2]
    # Premultiplied source-over: C = C_ring * alpha + C_video * (1-alpha).
    blended = source[:, :, :3] * 255 + target * (1 - source[:, :, 3:4])
    target[:] = np.clip(np.rint(blended), 0, 255).astype(np.uint8)
