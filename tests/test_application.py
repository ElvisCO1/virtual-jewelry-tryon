"""Regression checks for entry point, relocated assets and camera lifecycle."""

from contextlib import redirect_stderr
import io
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from virtual_jewelry_tryon import app
from virtual_jewelry_tryon.camera import open_camera
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.config import PROJECT_ROOT, MODEL_PATH


class EntryPointTests(unittest.TestCase):
    def test_bundled_resources_and_modes(self):
        config = parse_args([])
        self.assertTrue(config.ring_front.is_file())
        self.assertTrue(config.ring_back.is_file())
        self.assertEqual(MODEL_PATH.parent, PROJECT_ROOT / 'models')
        self.assertIsNone(parse_args(['--geometry-only']).ring_front)
        self.assertIsNone(parse_args(['--ring', 'custom.png']).ring_front)

    def test_invalid_modes_are_rejected(self):
        for args in (['--ring-front', 'front.png'],
                     ['--ring', 'ring.png', '--geometry-only'],
                     ['--width-ratio', '-1']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    parse_args(args)
                self.assertEqual(error.exception.code, 2)

    def test_main_help_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / 'main.py'), '--help'],
                cwd=directory, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--geometry-only', result.stdout)


class ResourceTests(unittest.TestCase):
    @patch('virtual_jewelry_tryon.camera.cv2.destroyAllWindows')
    @patch('virtual_jewelry_tryon.camera.cv2.VideoCapture')
    def test_unavailable_camera_is_released(self, capture, close_windows):
        capture.return_value.isOpened.return_value = False
        with self.assertRaises(RuntimeError):
            with open_camera():
                self.fail('Unavailable camera should not be yielded')
        capture.return_value.release.assert_called_once()
        close_windows.assert_called_once()

    @patch('virtual_jewelry_tryon.camera.cv2.destroyAllWindows')
    @patch('virtual_jewelry_tryon.camera.cv2.VideoCapture')
    @patch('virtual_jewelry_tryon.app.HandDetector')
    def test_detector_failure_releases_camera(self, detector, capture, close_windows):
        detector.side_effect = RuntimeError('Model unavailable')
        with self.assertRaisesRegex(RuntimeError, 'Model unavailable'):
            app.run(parse_args(['--geometry-only']))
        capture.return_value.release.assert_called_once()
        close_windows.assert_called_once()

    @patch('virtual_jewelry_tryon.camera.cv2.destroyAllWindows')
    @patch('virtual_jewelry_tryon.camera.cv2.VideoCapture')
    @patch('virtual_jewelry_tryon.app.HandDetector')
    @patch('virtual_jewelry_tryon.app.cv2.imshow')
    @patch('virtual_jewelry_tryon.app.cv2.waitKey', return_value=ord('q'))
    def test_default_run_loads_assets_and_quits_cleanly(
        self, wait_key, show, detector, capture, close_windows
    ):
        capture.return_value.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        detector.return_value.detect.return_value = SimpleNamespace(hand_landmarks=[], handedness=[])
        self.assertEqual(app.run(parse_args([])), 0)
        show.assert_called_once()
        detector.return_value.close.assert_called_once()
        capture.return_value.release.assert_called_once()
        close_windows.assert_called_once()


if __name__ == '__main__':
    unittest.main()
