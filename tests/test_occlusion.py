"""Experimental masking must preserve the unmasked pipeline and input assets."""

import unittest
import numpy as np

from virtual_jewelry_tryon.occlusion import apply_occlusion
from virtual_jewelry_tryon.ring_overlay import overlay_ring
from virtual_jewelry_tryon.smoothing import RingPose


class OcclusionTests(unittest.TestCase):
    def test_mask_rotates_and_preserves_tip_and_edges(self):
        source = np.ones((41, 41, 4), dtype=np.float32)
        masked = apply_occlusion(source, 0, 0, (20, 20), -90, 40)
        self.assertEqual(masked[30, 20, 3], 0)
        self.assertEqual(masked[10, 20, 3], 1)
        self.assertEqual(masked[30, 0, 3], 1)
        rotated = apply_occlusion(source, 0, 0, (20, 20), 0, 40)
        self.assertEqual(rotated[20, 10, 3], 0)
        self.assertEqual(rotated[20, 30, 3], 1)
        np.testing.assert_array_equal(source, np.ones_like(source))
        np.testing.assert_array_equal(masked[:, :, 0], masked[:, :, 3])

    def test_toggle_clipped_overlay_and_asset_immutability(self):
        asset = np.full((30, 40, 4), 255, dtype=np.uint8)
        original = asset.copy()
        for center in ((30, 30), (0, 0), (59, 59), (-100, -100)):
            pose = RingPose(center, 40, -90)
            baseline = np.zeros((60, 60, 3), dtype=np.uint8)
            disabled = baseline.copy()
            enabled = baseline.copy()
            overlay_ring(baseline, asset, pose)
            overlay_ring(disabled, asset, pose, occlusion=False)
            overlay_ring(enabled, asset, pose, occlusion=True)
            np.testing.assert_array_equal(baseline, disabled)
            self.assertTrue(np.all(enabled <= baseline))
            if center == (30, 30):
                self.assertTrue(np.any(enabled != baseline))
        np.testing.assert_array_equal(asset, original)
