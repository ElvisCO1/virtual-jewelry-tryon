"""Experimental 2D mask, not a depth or finger segmentation model."""

from math import cos, sin, radians

import numpy as np


METHOD = "palm_half_strip_v1"


def apply_occlusion(source, left, top, center, angle, ring_width):
    """Suppress the central palm-side band; retain the fingertip-side decoration.

    Project pixels onto the finger axis (u) and its perpendicular (v). Assume
    the hidden band lies on the palm side (u < -0.05 * width), inside a strip
    with half-width 0.32 * ring_width. This is an adjustable-in-code visual
    hypothesis, not a determination of which pixels are actually behind skin.
    Apply the same soft mask to premultiplied RGB and alpha to avoid fringes.
    """
    y, x = np.ogrid[:source.shape[0], :source.shape[1]]
    dx, dy = x + left - center[0], y + top - center[1]
    theta = radians(angle)
    u = dx * cos(theta) + dy * sin(theta)
    v = -dx * sin(theta) + dy * cos(theta)
    feather = max(1.0, ring_width * .03)
    palm = np.clip((-u - ring_width * .05) / feather, 0, 1)
    strip = np.clip((ring_width * .32 - np.abs(v)) / feather, 0, 1)
    visibility = (1 - palm * strip).astype(np.float32)
    return source * visibility[:, :, None]
