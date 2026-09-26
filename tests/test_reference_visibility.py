"""Visibility must leave tracking, ring poses and the data panel intact."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.config import DEFAULT_RING_FRONT
from virtual_jewelry_tryon.ring_overlay import overlay_ring


def detection(hand_count=1):
    hands = []
    for i in range(hand_count):
        x = .25 + i * .4
        landmarks = [SimpleNamespace(x=x, y=.7, z=0) for _ in range(21)]
        landmarks[5] = SimpleNamespace(x=x-.08, y=.45, z=0)
        landmarks[17] = SimpleNamespace(x=x+.08, y=.45, z=0)
        for index, y in zip((13, 14, 15, 16), (.55, .4, .3, .2)):
            landmarks[index] = SimpleNamespace(x=x, y=y, z=0)
        hands.append(landmarks)
    return SimpleNamespace(
        hand_landmarks=hands,
        handedness=[[SimpleNamespace(category_name=label, score=.95)]
                    for label in ('Right', 'Left')[:hand_count]],
    )


class ReferenceVisibilityTests(unittest.TestCase):
    def test_hidden_marks_leave_camera_clean_and_keep_data_for_all_hands(self):
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        for count in (0, 1, 2):
            with self.subTest(hands=count):
                detector = Mock()
                detector.detect.return_value = detection(count)
                processor = FrameProcessor(parse_args(['--geometry-only']), detector)
                visible = processor.process(frame.copy())
                hidden = processor.process(frame.copy(), show_references=False)
                np.testing.assert_array_equal(hidden[:480, :640], frame)
                np.testing.assert_array_equal(visible[:, 640:], hidden[:, 640:])
                self.assertEqual(detector.detect.call_count, 2)
                if count:
                    self.assertTrue(np.any(visible[:480, :640] != frame))
                    # Hidden references must not freeze coordinate updates.
                    detector.detect.return_value.hand_landmarks[0][13].x += .01
                    updated = processor.process(frame.copy(), show_references=False)
                    # Compare the first coordinate row, not the orientation status.
                    self.assertTrue(np.any(updated[85:105, 640:] != hidden[85:105, 640:]))

    def test_ring_pose_and_overlay_remain_active_when_references_are_hidden(self):
        detector = Mock()
        detector.detect.return_value = detection()
        processor = FrameProcessor(parse_args(['--ring', str(DEFAULT_RING_FRONT), '--smoothing', '0']), detector)
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        with patch('virtual_jewelry_tryon.app.overlay_ring', wraps=overlay_ring) as overlay:
            visible = processor.process(frame.copy())
            hidden = processor.process(frame.copy(), show_references=False)
        self.assertEqual(overlay.call_count, 2)
        self.assertEqual(overlay.call_args_list[0].args[2], overlay.call_args_list[1].args[2])
        np.testing.assert_array_equal(visible[:, 640:], hidden[:, 640:])
        expected = frame.copy()
        overlay_ring(expected, processor.ring, overlay.call_args.args[2], processor.config.asset_angle)
        np.testing.assert_array_equal(hidden[:480, :640], expected)
        self.assertTrue(np.any(expected != frame))


if __name__ == '__main__':
    unittest.main()
