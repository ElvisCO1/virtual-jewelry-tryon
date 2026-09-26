"""Lossless preprocessing must preserve transparency and avoid accidental clipping."""

import unittest

import numpy as np
from PIL import Image

from virtual_jewelry_tryon.normalize_assets import align_canvas, estimate_anchor


class AssetNormalizationTests(unittest.TestCase):
    def test_rgba_values_are_preserved_including_partial_alpha(self):
        pixels = np.array([[[200, 100, 50, 128], [20, 30, 40, 0]],
                           [[255, 255, 255, 255], [0, 0, 0, 64]]], dtype=np.uint8)
        source = Image.fromarray(pixels)
        result, offset = align_canvas(source, (1, 1), 8)
        self.assertEqual(offset, (3, 3))
        np.testing.assert_array_equal(np.asarray(result)[3:5, 3:5], pixels)
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0, 0))

    def test_small_disconnected_noise_does_not_set_anchor(self):
        pixels = np.zeros((20, 20, 4), dtype=np.uint8)
        pixels[10:15, 8:13, 3] = 255
        pixels[0, 0, 3] = 255
        anchor, bounds = estimate_anchor(Image.fromarray(pixels))
        self.assertEqual(anchor, (10, 12))
        self.assertEqual(bounds, [8, 10, 5, 5])

    def test_clipping_is_rejected(self):
        with self.assertRaises(ValueError):
            align_canvas(Image.new('RGBA', (10, 10)), (0, 0), 10)


if __name__ == '__main__':
    unittest.main()
