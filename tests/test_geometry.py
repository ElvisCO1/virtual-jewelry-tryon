"""Check pixel scaling, orientation conventions, and degenerate geometry."""

import unittest
from types import SimpleNamespace

from virtual_jewelry_tryon.geometry import ring_finger_geometry


class GeometryTests(unittest.TestCase):
    def measure(self, start, end, width=800, height=400):
        landmarks = [SimpleNamespace(x=0.0, y=0.0) for _ in range(21)]
        for index, point in zip((13, 14, 15, 16), (start, end, (0.6, 0.7), (0.8, 0.9))):
            landmarks[index] = SimpleNamespace(x=point[0], y=point[1])
        return ring_finger_geometry(landmarks, width, height)

    def test_pixel_scaling_on_non_square_frame(self):
        geometry = self.measure((0.1, 0.2), (0.4, 0.6))
        self.assertEqual(geometry.points, ((80, 80), (320, 240), (480, 280), (640, 360)))
        self.assertEqual(geometry.midpoint, (200, 160))
        self.assertAlmostEqual(geometry.distance_px, 288.44410203711914)
        self.assertAlmostEqual(geometry.angle_deg, 33.690067525979785)

    def test_screen_angle_directions(self):
        for end, expected in [((0.8, 0.5), 0), ((0.5, 0.8), 90),
                              ((0.5, 0.2), -90), ((0.2, 0.5), 180),
                              ((0.4, 0.3), -135), ((0.4, 0.7), 135)]:
            with self.subTest(end=end):
                self.assertAlmostEqual(self.measure((0.5, 0.5), end).angle_deg, expected)

    def test_coincident_points_have_no_angle(self):
        geometry = self.measure((0.5, 0.5), (0.5, 0.5))
        self.assertEqual(geometry.distance_px, 0)
        self.assertIsNone(geometry.angle_deg)

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            self.measure((0, 0), (1, 1), width=0)


if __name__ == "__main__":
    unittest.main()
