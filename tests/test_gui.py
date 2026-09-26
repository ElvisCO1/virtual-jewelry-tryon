"""Exercise real Tk buttons with a synthetic camera, without opening the webcam."""

import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from virtual_jewelry_tryon.app import PreviewSession
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.gui import TryOnWindow


class FakeSession:
    def __init__(self):
        self.active = False
        self.read_error = False
        self.starts = 0
        self.show_references = True

    def start(self):
        self.active = True
        self.starts += 1

    def read(self):
        if self.read_error:
            raise RuntimeError('Camera disconnected')
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def stop(self):
        self.active = False


class WindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()  # Tests must not pop up interactive windows.
        self.session = FakeSession()
        with patch('virtual_jewelry_tryon.gui.PreviewSession', return_value=self.session):
            self.window = TryOnWindow(self.root, parse_args([]))

    def tearDown(self):
        if hasattr(self, 'window') and self.root.winfo_exists():
            self.window.close()

    def test_camera_starts_off_and_can_restart(self):
        self.assertFalse(self.session.active)
        for _ in range(2):
            self.window.start_button.invoke()
            self.assertTrue(self.session.active)
            self.assertIsNotNone(self.window._photo)
            self.assertIsNotNone(self.window._scheduled_frame)
            self.window.stop_button.invoke()
            self.assertFalse(self.session.active)
            self.assertIsNone(self.window._scheduled_frame)
            self.assertIsNone(self.window._photo)
            self.assertEqual(str(self.window.start_button['state']), 'normal')
        self.assertEqual(self.session.starts, 2)

    def test_disconnected_camera_stops_and_can_retry(self):
        self.session.read_error = True
        self.window.start()
        self.assertFalse(self.session.active)
        self.assertIn('Camera disconnected', self.window.status.get())
        self.assertIsNone(self.window._scheduled_frame)
        self.session.read_error = False
        self.window.start()
        self.assertTrue(self.session.active)

    def test_references_toggle_without_restarting_camera_and_survive_stop(self):
        self.window.references_button.invoke()
        self.assertFalse(self.session.show_references)
        self.window.start()
        scheduled_frame = self.window._scheduled_frame
        self.window.references_button.invoke()
        self.assertTrue(self.session.show_references)
        self.assertEqual(self.session.starts, 1)
        self.assertEqual(self.window._scheduled_frame, scheduled_frame)
        self.window.references_button.invoke()
        self.window.stop()
        self.window.start()
        self.assertFalse(self.session.show_references)
        self.assertEqual(self.window.references_button['text'], 'Mostrar referencias')

    def test_failed_start_restores_start_button(self):
        with patch.object(self.session, 'start', side_effect=RuntimeError('Camera busy')):
            self.window.start()
        self.assertFalse(self.session.active)
        self.assertIn('Camera busy', self.window.status.get())
        self.assertEqual(str(self.window.start_button['state']), 'normal')

    def test_close_releases_session_and_cancels_callback(self):
        self.window.start()
        self.window.close()
        self.assertFalse(self.session.active)
        self.assertIsNone(self.window._scheduled_frame)
        del self.window  # Root has already been destroyed; skip tearDown cleanup.


class SessionTests(unittest.TestCase):
    @patch('virtual_jewelry_tryon.camera.cv2.destroyAllWindows')
    @patch('virtual_jewelry_tryon.camera.cv2.VideoCapture')
    @patch('virtual_jewelry_tryon.app.HandDetector')
    def test_repeated_start_stop_owns_resources_once_per_activation(self, detector, capture, windows):
        session = PreviewSession(parse_args(['--geometry-only']))
        session.show_references = False
        self.assertFalse(session.active)
        for _ in range(2):
            session.start()
            session.start()  # Duplicate activation must not reopen hardware.
            self.assertTrue(session.active)
            self.assertFalse(session.show_references)
            session.stop()
            session.stop()
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(capture.return_value.release.call_count, 2)
        self.assertEqual(detector.return_value.close.call_count, 2)
        self.assertIsNone(session.processor)


if __name__ == '__main__':
    unittest.main()
