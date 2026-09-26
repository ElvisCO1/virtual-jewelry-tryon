"""Manual guide follows the finger without altering the jewelry pose."""
import unittest
from math import hypot
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from virtual_jewelry_tryon.manual_width import width_reference
from virtual_jewelry_tryon.smoothing import RingPose
from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args


class ManualWidthTests(unittest.TestCase):
    def test_perpendicular_center_and_length(self):
        for angle in (0, 45, 90, -90):
            pose = RingPose((100, 100), 90, angle)
            a, b = width_reference(pose, 50, .6)['endpoints']
            self.assertAlmostEqual(hypot(b[0]-a[0], b[1]-a[1]), 30)
            np.testing.assert_allclose(np.mean([a, b], axis=0), pose.center)
            from math import cos, sin, radians
            self.assertAlmostEqual((b[0]-a[0])*cos(radians(angle)) + (b[1]-a[1])*sin(radians(angle)), 0)
        self.assertIsNone(width_reference(None, 50, .6))

    def test_guide_changes_pixels_but_not_ring_pose(self):
        points = [SimpleNamespace(x=.5, y=.5, z=0) for _ in range(21)]
        points[13].y, points[14].y = .7, .3
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(hand_landmarks=[points],
            handedness=[[SimpleNamespace(category_name='Left', score=.99)]])
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        view = SimpleNamespace(filename='test.png', azimuth=0, elevation=0, width_scale=1,
                               image=np.zeros((10, 10, 4), dtype=np.uint8))
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay:
            baseline = processor.process(frame.copy(), show_references=False, manual_view=view)
            pose = overlay.call_args.args[2]
            for ratio in (.1, .6, 2):
                visible = processor.process(frame.copy(), show_references=False, manual_view=view,
                                            show_manual_width=True, manual_width_ratio=ratio)
                self.assertEqual(overlay.call_args.args[2], pose)
                self.assertTrue(np.any(visible[:240, :320] != baseline[:240, :320]))
                reference = processor.last_snapshot['hands'][0]['manual_width_reference']
                self.assertAlmostEqual(reference['width_px'], 96 * ratio)
