"""Persistence tests use temporary folders, never the user's evidence folder."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from virtual_jewelry_tryon.samples import SampleBuffer
from virtual_jewelry_tryon.session_store import save_session


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.buffer = SampleBuffer()
        self.buffer.capture({'frame_id': 'one', 'image': {'filename': 'ring.png'},
                             'hands': [{'handedness': 'Right', 'eligible': True}]}, 'Right')

    def test_roundtrip_revisions_preserve_previous_evidence(self):
        first = save_session(self.buffer, 'prueba ñ', self.directory)
        original = first.read_bytes()
        self.assertFalse(self.buffer.dirty)
        self.buffer.discard_last()
        second = save_session(self.buffer, 'prueba ñ', self.directory)
        self.assertEqual(first.read_bytes(), original)
        data = json.loads(second.read_text(encoding='utf-8'))
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['session_id'], self.buffer.session_id)
        self.assertEqual(data['revision'], 2)
        self.assertEqual(data['valid_count'], 0)
        self.assertTrue(data['samples'][0]['discarded'])
        self.assertEqual(data['name'], 'prueba ñ')
        self.assertNotEqual(first, second)

    def test_failure_keeps_pending_data_and_removes_partial_file(self):
        with patch('virtual_jewelry_tryon.session_store.os.fsync', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                save_session(self.buffer, 'prueba', self.directory)
        self.assertTrue(self.buffer.dirty)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_names_cannot_escape_directory_and_repeated_saves_are_unique(self):
        first = save_session(self.buffer, '../../prueba', self.directory)
        second = save_session(self.buffer, '../../prueba', self.directory)
        self.assertEqual(first.parent, self.directory)
        self.assertNotEqual(first, second)

    def test_invalid_name_empty_buffer_and_nan_rejected(self):
        with self.assertRaises(ValueError):
            save_session(self.buffer, ' ', self.directory)
        with self.assertRaises(ValueError):
            save_session(SampleBuffer(), 'prueba', self.directory)
        self.buffer.samples[0]['bad_value'] = float('nan')
        with self.assertRaises(ValueError):
            save_session(self.buffer, 'prueba', self.directory)
        self.assertEqual(list(self.directory.iterdir()), [])
