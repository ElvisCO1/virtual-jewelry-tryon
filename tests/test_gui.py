"""Exercise real Tk buttons with a synthetic camera, without opening the webcam."""

import tkinter as tk
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from virtual_jewelry_tryon.app import PreviewSession
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.gui import TryOnWindow
from virtual_jewelry_tryon.session_store import save_session


class FakeSession:
    def __init__(self):
        self.active = False
        self.read_error = False
        self.starts = 0
        self.show_references = True
        self.show_ring = True
        self.manual_view = None
        self.last_snapshot = None

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
    def test_manual_width_controls_preserve_ring_size_and_invalidate_capture(self):
        self.window.start()
        self.window.manual_width_toggle.invoke()
        self.window.manual_width_slider.set(80)
        self.assertTrue(self.session.show_manual_width)
        self.assertEqual(self.session.manual_width_ratio, .8)
        self.assertEqual(self.window.size_value.get(), 100)
        self.assertIsNone(self.window._displayed_snapshot)
        self.window.stop()
        self.window.start()
        self.assertTrue(self.session.show_manual_width)
        self.assertEqual(self.session.manual_width_ratio, .8)
        self.window.manual_width_toggle.invoke()
        self.assertFalse(self.session.show_manual_width)

    def test_size_control_invalidates_capture_and_survives_restart(self):
        self.assertEqual(self.window.size_value.get(), 100)
        self.window.start()
        self.window.size_slider.set(150)
        self.assertEqual(self.session.size_factor, 1.5)
        self.assertIsNone(self.window._displayed_snapshot)
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.stop()
        self.window.start()
        self.assertEqual(self.session.size_factor, 1.5)
        self.window.reset_size_button.invoke()
        self.assertEqual(self.session.size_factor, 1)
        self.assertEqual(self.window.size_value.get(), 100)

    def test_occlusion_toggle_invalidates_capture_and_survives_restart(self):
        self.assertFalse(self.window.occlusion_enabled.get())
        self.window.start()
        self.window.occlusion_toggle.invoke()
        self.assertTrue(self.session.occlusion)
        self.assertTrue(self.session.show_ring)
        self.assertIsNone(self.window._displayed_snapshot)
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.stop()
        self.window.start()
        self.assertTrue(self.session.occlusion)
        self.window.occlusion_toggle.invoke()
        self.assertFalse(self.session.occlusion)

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()  # Tests must not pop up interactive windows.
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        saver = patch('virtual_jewelry_tryon.gui.save_session',
                      side_effect=lambda buffer, name: save_session(buffer, name, temporary.name))
        saver.start()
        self.addCleanup(saver.stop)
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

    def test_new_session_saves_and_failed_save_preserves_evidence(self):
        snapshot = {'frame_id': 'a', 'image': {'filename': 'ring.png'},
                    'hands': [{'handedness': 'Right', 'eligible': True}]}
        self.window.samples.capture(snapshot, 'Right')
        original = self.window.samples
        with patch('virtual_jewelry_tryon.gui.save_session', side_effect=OSError('disk full')):
            self.window.new_session_button.invoke()
            self.assertIs(self.window.samples, original)
            self.window.close()
            self.assertTrue(self.root.winfo_exists())
            self.assertTrue(original.dirty)
        self.window.new_session_button.invoke()
        self.assertFalse(original.dirty)
        self.assertNotEqual(self.window.samples.session_id, original.session_id)
        self.assertEqual(self.window.samples.valid_count, 0)

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

    def test_ring_visibility_is_independent_and_blocks_stale_capture(self):
        self.window.start()
        self.window.ring_toggle.invoke()
        self.assertFalse(self.session.show_ring)
        self.assertTrue(self.session.show_references)
        self.assertEqual(self.session.starts, 1)
        self.window.capture_sample()
        self.assertEqual(self.window.samples.valid_count, 0)
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.stop()
        self.window.start()
        self.assertFalse(self.session.show_ring)
        self.window.ring_toggle.invoke()
        self.assertTrue(self.session.show_ring)
        self.assertIsNone(self.window._displayed_snapshot)
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')

    def test_placement_controls_invalidate_capture_and_survive_restart(self):
        self.window.start()
        self.window.finger_name.set('Índice')
        self.window.position_value.set(20)
        self.window.change_placement()
        self.assertEqual(self.session.finger, 'index')
        self.assertEqual(self.session.position, .2)
        self.assertIsNone(self.window._displayed_snapshot)
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.stop()
        self.window.start()
        self.assertEqual(self.session.finger, 'index')
        self.assertEqual(self.session.position, .2)
        self.window.reset_position_button.invoke()
        self.assertEqual(self.session.position, .5)

    def test_failed_start_restores_start_button(self):
        with patch.object(self.session, 'start', side_effect=RuntimeError('Camera busy')):
            self.window.start()
        self.assertFalse(self.session.active)
        self.assertIn('Camera busy', self.window.status.get())
        self.assertEqual(str(self.window.start_button['state']), 'normal')

    def test_manual_views_cycle_and_switch_without_camera_restart(self):
        self.assertEqual(self.window.mode.get(), 'Automático front/back')
        self.window.start()
        callback = self.window._scheduled_frame
        self.window.mode.set('Manual — 36 vistas')
        self.window.change_mode()
        first = self.session.manual_view
        seen = set()
        for _ in range(36):
            seen.add(self.session.manual_view.filename)
            self.window.next_button.invoke()
        self.assertEqual(len(seen), 36)
        self.assertIs(self.session.manual_view, first)
        self.window.previous_button.invoke()
        selected = self.session.manual_view
        self.assertIn('36 de 36', self.window.view_description.get())
        self.assertEqual(self.session.starts, 1)
        self.assertEqual(self.window._scheduled_frame, callback)
        self.window.stop()
        self.window.start()
        self.assertIs(self.session.manual_view, selected)
        self.window.mode.set('Automático front/back')
        self.window.change_mode()
        self.assertIsNone(self.session.manual_view)
        self.assertEqual(str(self.window.next_button['state']), 'disabled')
        with patch('virtual_jewelry_tryon.gui.load_catalog', side_effect=AssertionError('reloaded')):
            self.window.mode.set('Manual — 36 vistas')
            self.window.change_mode()
        self.assertIs(self.session.manual_view, selected)

    def test_catalog_failure_leaves_camera_and_automatic_mode_available(self):
        self.window.start()
        with patch('virtual_jewelry_tryon.gui.load_catalog', side_effect=ValueError('Missing PNG')):
            self.window.mode.set('Manual — 36 vistas')
            self.window.change_mode()
        self.assertTrue(self.session.active)
        self.assertIsNone(self.session.manual_view)
        self.assertEqual(self.window.mode.get(), 'Automático front/back')
        self.assertIn('Missing PNG', self.window.status.get())

    def test_close_releases_session_and_cancels_callback(self):
        self.window.start()
        self.window.close()
        self.assertFalse(self.session.active)
        self.assertIsNone(self.window._scheduled_frame)
        del self.window  # Root has already been destroyed; skip tearDown cleanup.

    def test_capture_uses_displayed_frame_and_invalidates_on_view_change(self):
        self.window.mode.set('Manual — 36 vistas')
        self.window.change_mode()
        self.session.last_snapshot = {
            'frame_id': 'first', 'image': {'filename': self.session.manual_view.filename},
            'hands': [{'handedness': 'Right', 'eligible': True}],
        }
        self.window.start()
        self.session.last_snapshot = None  # Not yet displayed: must not affect capture.
        self.window.capture_button.invoke()
        self.assertEqual(self.window.samples.samples[0]['frame_id'], 'first')
        self.assertEqual(self.window.samples.valid_count, 1)
        self.window.next_button.invoke()
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.capture_sample()
        self.assertEqual(self.window.samples.valid_count, 1)
        self.window.stop()
        self.assertEqual(self.window.samples.valid_count, 1)
        self.window.discard_button.invoke()
        self.assertEqual(self.window.samples.valid_count, 0)

    def test_two_hands_require_initial_choice(self):
        self.session.last_snapshot = {
            'frame_id': 'two', 'image': {'filename': 'test.png'},
            'hands': [{'handedness': side, 'eligible': True} for side in ('Right', 'Left')],
        }
        self.window.start()
        self.assertEqual(str(self.window.capture_button['state']), 'disabled')
        self.window.capture_hand.set('Izquierda')
        self.window._refresh_capture()
        self.window.capture_button.invoke()
        self.assertEqual(self.window.samples.samples[0]['hand']['handedness'], 'Left')


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
