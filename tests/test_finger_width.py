"""Known synthetic contours verify pixel measurements, not physical accuracy."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from virtual_jewelry_tryon.finger_width import estimate_width
from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args


class WidthTests(unittest.TestCase):
    def test_known_width_and_rotated_scan(self):
        frame = np.zeros((140, 140, 3), dtype=np.uint8)
        frame[:, 50:90] = 200
        measurement = estimate_width(frame, (70, 70), -90, 60)
        self.assertIsNotNone(measurement)
        self.assertAlmostEqual(measurement['width_px'], 40, delta=2)
        rotated = estimate_width(frame.transpose(1, 0, 2).copy(), (70, 70), 0, 60)
        self.assertAlmostEqual(rotated['width_px'], 40, delta=2)

    def test_flat_missing_edges_and_outside_frame_rejected(self):
        frame = np.zeros((140, 140, 3), dtype=np.uint8)
        self.assertIsNone(estimate_width(frame, (70, 70), -90, 60))
        frame[:, 50:] = 200
        self.assertIsNone(estimate_width(frame, (70, 70), -90, 60))
        self.assertIsNone(estimate_width(frame, (0, 0), -90, 60))
        self.assertIsNone(estimate_width(frame, (70, 70), None, 60))

    def test_mm_requires_matching_calibration_and_clean_camera_input(self):
        points = [SimpleNamespace(x=.5, y=.5, z=0) for _ in range(21)]
        points[13].y = .7
        points[14].y = .3
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(hand_landmarks=[points],
            handedness=[[SimpleNamespace(category_name='Left', score=.99)]])
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        frame = np.zeros((140, 140, 3), dtype=np.uint8)
        frame[:, 50:90] = 200
        with patch('virtual_jewelry_tryon.app.estimate_width', wraps=estimate_width) as measure:
            processor.process(frame.copy())
            measure.assert_not_called()
            self.assertEqual(processor.last_widths, [])
            processor.process(frame.copy(), measure_width=True)
            np.testing.assert_array_equal(measure.call_args.args[0][:, :50], frame[:, :50])
        self.assertIsNone(processor.last_widths[0]['measurement']['width_mm'])
        context = processor.last_widths[0]['context']
        reference = processor.last_widths[0]['measurement']['width_px']
        calibration = {'context': context, 'mm_per_pixel': 20 / reference}
        processor.process(frame.copy(), calibration=calibration, measure_width=True)
        self.assertAlmostEqual(processor.last_widths[0]['measurement']['width_mm'], 20)
        processor.process(frame.copy(), position=.6, calibration=calibration, measure_width=True)
        self.assertIsNone(processor.last_widths[0]['measurement']['width_mm'])
