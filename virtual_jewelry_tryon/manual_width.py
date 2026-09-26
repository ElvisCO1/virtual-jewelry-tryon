"""User-adjusted width guide; no image measurement or jewelry resizing."""

from math import cos, sin, radians

import cv2


def width_reference(pose, segment_length, ratio):
    if pose is None:
        return None
    width = segment_length * ratio
    angle = radians(pose.angle)
    # A perpendicular unit vector to (cos(angle), sin(angle)).
    normal = (-sin(angle), cos(angle))
    endpoints = [tuple(c + sign * width / 2 * n for c, n in zip(pose.center, normal))
                 for sign in (-1, 1)]
    return {'width_px': width, 'ratio': ratio, 'endpoints': endpoints,
            'method': 'manual_segment_ratio_v1'}


def draw_width_reference(frame, reference):
    if reference is None:
        return
    endpoints = [tuple(round(v) for v in point) for point in reference['endpoints']]
    cv2.line(frame, *endpoints, (255, 255, 0), 2, cv2.LINE_AA)
    for point in endpoints:
        cv2.circle(frame, point, 4, (255, 255, 0), -1, cv2.LINE_AA)
