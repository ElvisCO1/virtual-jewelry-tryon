"""Display compositing must not change the numerical tracking pipeline."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
import numpy as np

from virtual_jewelry_tryon.virtual_background import VirtualBackground
from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args


class BackgroundTests(unittest.TestCase):
    def test_disabled_is_noop_and_masks_preserve_foreground(self):
        bg = VirtualBackground()
        frame = np.full((40, 60, 3), 150, dtype=np.uint8)
        self.assertIs(bg.apply(frame), frame)
        bg.image = np.full((20, 20, 3), 30, dtype=np.uint8)
        bg.enabled = True
        bg._segmenter = Mock()
        for value in (0, 1):
            mask = Mock()
            mask.numpy_view.return_value = np.full((256, 256), value, dtype=np.float32)
            bg._segmenter.segment.return_value = SimpleNamespace(confidence_masks=[mask])
            result = bg.apply(frame)
            np.testing.assert_array_equal(result, np.full_like(frame, 150 if value else 30))
        np.testing.assert_array_equal(frame, np.full_like(frame, 150))
        bg.close()
        self.assertIsNone(bg._segmenter)

    def test_failure_disables_background_and_keeps_frame(self):
        bg = VirtualBackground()
        bg.enabled = True
        frame = np.zeros((20, 20, 3), dtype=np.uint8)
        self.assertIs(bg.apply(frame), frame)
        self.assertFalse(bg.enabled)
        self.assertIsNotNone(bg.error)

    def test_tracking_uses_original_and_pose_is_unchanged(self):
        landmarks = [SimpleNamespace(x=.5, y=.5, z=0) for _ in range(21)]
        landmarks[13].y, landmarks[14].y = .7, .3
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(hand_landmarks=[landmarks],
            handedness=[[SimpleNamespace(category_name='Left', score=.99)]])
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        frame = np.full((240, 320, 3), 70, dtype=np.uint8)
        view = SimpleNamespace(filename='test.png', azimuth=0, elevation=0, width_scale=1,
            image=np.zeros((10, 10, 4), dtype=np.uint8))
        bg = Mock(enabled=True)
        bg.apply.side_effect = lambda original: np.zeros_like(original)
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay:
            processor.process(frame.copy(), show_references=False, manual_view=view)
            expected_pose = overlay.call_args.args[2]
            expected_hand = processor.last_snapshot['hands'][0]
            processor.process(frame.copy(), show_references=False, manual_view=view, background=bg)
            np.testing.assert_array_equal(detector.detect.call_args.args[0], frame)
            self.assertEqual(overlay.call_args.args[2], expected_pose)
            self.assertEqual(processor.last_snapshot['hands'][0], expected_hand)
