"""Selected anatomy, placement and displayed evidence must agree."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.geometry import FINGER_INDICES, placement_point, ring_finger_geometry


class PlacementTests(unittest.TestCase):
    def test_size_factor_changes_width_only_and_is_recorded(self):
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(
            hand_landmarks=[self.landmarks],
            handedness=[[SimpleNamespace(category_name='Left', score=.99)]])
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        view = SimpleNamespace(filename='test.png', azimuth=0, elevation=0, width_scale=1.4,
                               image=np.zeros((10, 10, 4), dtype=np.uint8))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay:
            for factor in (1, .5, 2, 1):
                processor.process(frame.copy(), manual_view=view, size_factor=factor, occlusion=True)
                pose = overlay.call_args.args[2]
                snapshot = processor.last_snapshot
                base = snapshot['hands'][0]['smoothed_pose']
                self.assertAlmostEqual(pose.width, base['width'] * factor * view.width_scale)
                self.assertEqual(pose.center, base['center'])
                self.assertEqual(pose.angle, base['angle'])
                self.assertEqual(snapshot['settings']['size_factor'], factor)
                self.assertEqual(snapshot['hands'][0]['requested_overlay_width_px'], pose.width)
                self.assertTrue(overlay.call_args.kwargs['occlusion'])
            for invalid in (0, 2.1, float('nan')):
                with self.assertRaises(ValueError):
                    processor.process(frame.copy(), size_factor=invalid)

    def setUp(self):
        self.landmarks = [SimpleNamespace(x=.1 + i * .02, y=.2 + i * .01, z=0) for i in range(21)]

    def test_all_fingers_interpolate_base_midpoint_and_joint(self):
        for finger, indices in FINGER_INDICES.items():
            with self.subTest(finger=finger):
                geometry = ring_finger_geometry(self.landmarks, 640, 480, finger)
                first = self.landmarks[indices[0]]
                self.assertEqual(geometry.points[0], (first.x * 640, first.y * 480))
                self.assertEqual(placement_point(geometry, 0), geometry.points[0])
                self.assertEqual(placement_point(geometry, 1), geometry.points[1])
                np.testing.assert_allclose(placement_point(geometry), geometry.midpoint)
                for invalid in (-.1, 1.1, float('nan')):
                    with self.assertRaises(ValueError):
                        placement_point(geometry, invalid)

    def test_switch_resets_smoothing_and_marker_matches_overlay_and_snapshot(self):
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(
            hand_landmarks=[self.landmarks],
            handedness=[[SimpleNamespace(category_name='Left', score=.99)]])
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        view = SimpleNamespace(filename='test.png', azimuth=0, elevation=0, width_scale=1,
                               image=np.zeros((10, 10, 4), dtype=np.uint8))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        from virtual_jewelry_tryon.geometry_view import draw_geometry
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay, patch(
                'virtual_jewelry_tryon.app.draw_geometry', wraps=draw_geometry) as drawing:
            for finger in FINGER_INDICES:
                for fraction in (0, .5, 1):
                    processor.process(frame.copy(), manual_view=view, finger=finger, position=fraction)
                    expected = placement_point(ring_finger_geometry(self.landmarks, 640, 480, finger), fraction)
                    self.assertEqual(overlay.call_args.args[2].center, expected)
                    self.assertEqual(drawing.call_args.kwargs['placement_centers'][0], expected)
                    snapshot = processor.last_snapshot
                    self.assertEqual(snapshot['settings']['finger'], finger)
                    self.assertEqual(snapshot['settings']['position_fraction'], fraction)
                    self.assertEqual(snapshot['hands'][0]['smoothed_pose']['center'], expected)
