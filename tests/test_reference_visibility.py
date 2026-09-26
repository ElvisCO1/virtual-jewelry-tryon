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
    def test_hidden_ring_keeps_tracking_and_blocks_manual_validation(self):
        detector = Mock()
        detector.detect.return_value = detection()
        processor = FrameProcessor(parse_args(['--ring', str(DEFAULT_RING_FRONT)]), detector)
        view = SimpleNamespace(filename='ring.png', azimuth=0, elevation=0,
                               width_scale=1.0, image=processor.ring)
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay:
            hidden = processor.process(frame.copy(), show_references=False, manual_view=view, show_ring=False)
            overlay.assert_not_called()
            np.testing.assert_array_equal(hidden[:480, :640], frame)
            self.assertFalse(processor.last_snapshot['settings']['show_ring'])
            self.assertFalse(processor.last_snapshot['hands'][0]['eligible'])
            self.assertEqual(len(processor.last_snapshot['hands'][0]['landmarks_normalized']), 21)
            processor.process(frame.copy(), manual_view=view)
            overlay.assert_called_once()
            self.assertTrue(processor.last_snapshot['hands'][0]['eligible'])
        self.assertEqual(detector.detect.call_count, 2)

    def test_manual_snapshot_tracks_frame_and_copies_coordinates(self):
        detector = Mock()
        detector.detect.return_value = detection()
        processor = FrameProcessor(parse_args(['--geometry-only']), detector)
        view = SimpleNamespace(filename='ring.png', azimuth=30, elevation=-30,
                               width_scale=1.0, image=np.zeros((10, 10, 4), dtype=np.uint8))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        processor.process(frame.copy(), show_references=False, manual_view=view)
        snapshot = processor.last_snapshot
        self.assertEqual(snapshot['frame_size'], [640, 480])
        self.assertEqual(snapshot['image']['azimuth_category'], 30)
        self.assertFalse(snapshot['settings']['show_references'])
        hand = snapshot['hands'][0]
        self.assertTrue(hand['eligible'])
        self.assertEqual(len(hand['landmarks_normalized']), 21)
        self.assertIsNone(hand['world_landmarks_m'])
        detector.detect.return_value.hand_landmarks[0][0].x = .9
        self.assertEqual(hand['landmarks_normalized'][0]['x'], .25)
        processor.process(frame.copy(), manual_view=view)
        self.assertNotEqual(snapshot['frame_id'], processor.last_snapshot['frame_id'])
        processor.process(frame.copy())
        self.assertIsNone(processor.last_snapshot)

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
