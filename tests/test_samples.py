"""Numerical evidence must remain independent of later tracking updates."""

import unittest

from virtual_jewelry_tryon.samples import SampleBuffer


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.buffer = SampleBuffer()
        self.snapshot = {
            'frame_id': 'frame-1', 'image': {'filename': 'ring.png'},
            'hands': [{'handedness': 'Right', 'eligible': True,
                       'landmarks_normalized': [{'x': .5, 'y': .6, 'z': 0}]}],
        }

    def test_capture_copies_data_and_prevents_duplicate(self):
        sample = self.buffer.capture(self.snapshot, 'Right')
        self.snapshot['hands'][0]['landmarks_normalized'][0]['x'] = .9
        self.assertEqual(sample['hand']['landmarks_normalized'][0]['x'], .5)
        self.assertEqual(sample['assessment'], 'adequate')
        with self.assertRaises(ValueError):
            self.buffer.capture(self.snapshot, 'Right')

    def test_missing_ambiguous_or_ineligible_hand_is_rejected(self):
        with self.assertRaises(ValueError):
            self.buffer.capture(None, 'Right')
        with self.assertRaises(ValueError):
            self.buffer.capture(self.snapshot, 'Left')
        self.snapshot['hands'][0]['eligible'] = False
        with self.assertRaises(ValueError):
            self.buffer.capture(self.snapshot, 'Right')
        self.snapshot['hands'][0]['eligible'] = True
        self.snapshot['hands'] *= 2
        with self.assertRaises(ValueError):
            self.buffer.capture(self.snapshot, 'Right')

    def test_discard_preserves_record_and_updates_count(self):
        sample = self.buffer.capture(self.snapshot, 'Right')
        self.assertIs(self.buffer.discard_last(), sample)
        self.assertTrue(sample['discarded'])
        self.assertEqual(self.buffer.valid_count, 0)
        self.assertEqual(len(self.buffer.samples), 1)
        with self.assertRaises(ValueError):
            self.buffer.discard_last()
