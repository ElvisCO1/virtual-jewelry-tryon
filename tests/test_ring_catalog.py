"""Catalog loading and manual selection must preserve the automatic baseline."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from virtual_jewelry_tryon.app import FrameProcessor
from virtual_jewelry_tryon.cli import parse_args
from virtual_jewelry_tryon.ring_catalog import load_catalog


class CatalogTests(unittest.TestCase):
    def test_complete_order_and_padding_compensation(self):
        views = load_catalog()
        self.assertEqual(len({v.filename for v in views}), 36)
        self.assertEqual((views[0].azimuth, views[0].elevation), (0, 0))
        self.assertEqual((views[12].azimuth, views[12].elevation), (0, -30))
        self.assertEqual((views[-1].azimuth, views[-1].elevation), (330, 30))
        for view in views:
            self.assertEqual(view.image.shape, (288, 288, 4))
            self.assertAlmostEqual(view.width_scale, 288 / 209)
            self.assertFalse(view.image.flags.writeable)

    def test_incomplete_catalog_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'manifest.json').write_text(json.dumps({'images': []}))
            with self.assertRaisesRegex(ValueError, 'Missing catalog metadata'):
                load_catalog(folder)

    def test_manual_switch_preserves_pose_and_return_to_automatic(self):
        points = [SimpleNamespace(x=.5, y=.7, z=0) for _ in range(21)]
        points[5] = SimpleNamespace(x=.4, y=.4, z=0)
        points[17] = SimpleNamespace(x=.6, y=.4, z=0)
        for index, y in zip((13, 14, 15, 16), (.55, .4, .3, .2)):
            points[index] = SimpleNamespace(x=.5, y=y, z=0)
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(
            hand_landmarks=[points],
            handedness=[[SimpleNamespace(category_name='Right', score=.95)]],
        )
        processor = FrameProcessor(parse_args(['--smoothing', '0']), detector)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        with patch('virtual_jewelry_tryon.app.overlay_ring') as overlay:
            for _ in range(3):
                processor.process(frame.copy(), False)
            auto_pose = overlay.call_args.args[2]
            auto_image = overlay.call_args.args[1]
            for view in load_catalog():
                processor.process(frame.copy(), False, manual_view=view)
                self.assertIs(overlay.call_args.args[1], view.image)
                pose = overlay.call_args.args[2]
                self.assertEqual(pose.center, auto_pose.center)
                self.assertEqual(pose.angle, auto_pose.angle)
                self.assertAlmostEqual(pose.width, auto_pose.width * view.width_scale)
            processor.process(frame.copy(), False)
            self.assertIs(overlay.call_args.args[1], auto_image)
            self.assertEqual(overlay.call_args.args[2], auto_pose)
        self.assertEqual(detector.detect.call_count, 40)


if __name__ == '__main__':
    unittest.main()
