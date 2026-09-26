"""Synthetic orientation checks with explicit anatomical and mirror conventions."""

import math
from types import SimpleNamespace
import unittest

from virtual_jewelry_tryon.hand_orientation import (
    HandOrientation, SurfaceTracker, estimate_orientation, select_ring_view,
)


def palm_points(right=True, rotate=0, mirrored=False, scale=1):
    # Right palm in an unmirrored image: index on image right, pinky on left.
    points = [(0, 0)] * 21
    points[5], points[17] = (80, -120), (-80, -120)
    result = []
    angle = math.radians(rotate)
    for x, y in points:
        x = x if right else -x
        x, y = scale * (x * math.cos(angle) - y * math.sin(angle)), scale * (
            x * math.sin(angle) + y * math.cos(angle))
        x = 320 + x
        result.append(SimpleNamespace(x=(640 - x if mirrored else x) / 640,
                                      y=(240 + y) / 480))
    return result


class OrientationTests(unittest.TestCase):
    def test_left_right_palms_and_backs(self):
        for right, label in ((True, "Right"), (False, "Left")):
            self.assertEqual(estimate_orientation(palm_points(right), label, .9, 640, 480).surface, "Palm")
            self.assertEqual(estimate_orientation(palm_points(not right), label, .9, 640, 480).surface, "Back")

    def test_in_plane_rotation_and_scaling(self):
        for angle in (0, 45, 90, 180, -90):
            for scale in (.25, 1, 2):
                with self.subTest(angle=angle, scale=scale):
                    result = estimate_orientation(palm_points(rotate=angle, scale=scale), "Right", .9, 640, 480)
                    self.assertEqual(result.surface, "Palm")

    def test_mirrored_input_corrects_label_and_winding(self):
        for right, raw_label, actual in ((True, "Left", "Right"), (False, "Right", "Left")):
            result = estimate_orientation(palm_points(right, mirrored=True), raw_label, .9,
                                          640, 480, input_mirrored=True)
            self.assertEqual(result.handedness, actual)
            self.assertEqual(result.surface, "Palm")

    def test_uncertain_or_degenerate_views(self):
        points = palm_points()
        self.assertEqual(estimate_orientation(points, "Right", .55, 640, 480).surface, "Unknown")
        self.assertEqual(estimate_orientation(points, "Other", .9, 640, 480).surface, "Unknown")
        points[17] = points[5]  # Collinear projected vectors.
        self.assertEqual(estimate_orientation(points, "Right", .9, 640, 480).surface, "Unknown")
        points[5] = points[0]
        self.assertEqual(estimate_orientation(points, "Right", .9, 640, 480).surface, "Unknown")

    def test_view_mapping(self):
        self.assertEqual(select_ring_view("Back"), "front")
        self.assertEqual(select_ring_view("Palm"), "back")
        self.assertEqual(select_ring_view("Back", swap=True), "back")
        self.assertEqual(select_ring_view("Palm", swap=True), "front")
        self.assertIsNone(select_ring_view("Unknown"))
        self.assertIsNone(select_ring_view("Unknown", swap=True))


class SurfaceTrackerTests(unittest.TestCase):
    def orientation(self, surface, label="Right"):
        return HandOrientation(label, .9, surface, .5)

    def test_debounce_and_switch(self):
        tracker = SurfaceTracker()
        palm, back = self.orientation("Palm"), self.orientation("Back")
        self.assertEqual(tracker.update([palm]), ["Unknown"])
        self.assertEqual(tracker.update([palm]), ["Unknown"])
        self.assertEqual(tracker.update([palm]), ["Palm"])
        self.assertEqual(tracker.update([back]), ["Palm"])
        self.assertEqual(tracker.update([palm]), ["Palm"])
        self.assertEqual(tracker.update([back]), ["Palm"])
        self.assertEqual(tracker.update([back]), ["Palm"])
        self.assertEqual(tracker.update([back]), ["Back"])

    def test_two_hands_reorder(self):
        tracker = SurfaceTracker(confirm_frames=1)
        left, right = self.orientation("Palm", "Left"), self.orientation("Back")
        self.assertEqual(tracker.update([left, right]), ["Palm", "Back"])
        self.assertEqual(tracker.update([right, left]), ["Back", "Palm"])

    def test_loss_uncertainty_and_duplicate_labels_clear_state(self):
        for interruption in ([], [self.orientation("Unknown")],
                             [self.orientation("Palm"), self.orientation("Back")]):
            tracker = SurfaceTracker()
            for _ in range(3):
                tracker.update([self.orientation("Palm")])
            self.assertEqual(tracker.update(interruption), ["Unknown"] * len(interruption))
            self.assertEqual(tracker.update([self.orientation("Palm")]), ["Unknown"])


if __name__ == "__main__":
    unittest.main()
