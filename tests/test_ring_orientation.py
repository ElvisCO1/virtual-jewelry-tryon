"""Synthetic checks for angle continuity, hand histories, rotation and blending."""

import unittest

import numpy as np

from virtual_jewelry_tryon.ring_overlay import overlay_ring, transform_ring
from virtual_jewelry_tryon.smoothing import HandPoseSmoother, PoseSmoother, RingPose


class SmoothingTests(unittest.TestCase):
    def test_wraparound_uses_short_path(self):
        smoother = PoseSmoother()
        smoother.update(RingPose((0, 0), 20, 179), 0)
        result = smoother.update(RingPose((10, 10), 30, -179), 0.03)
        self.assertGreater(abs(result.angle), 179)
        self.assertTrue(0 < result.center[0] < 10)
        self.assertTrue(20 < result.width < 30)

    def test_equivalent_elapsed_time_at_different_frame_rates(self):
        results = []
        for fps in (30, 60):
            smoother = PoseSmoother()
            smoother.update(RingPose((0, 0), 20, 0), 0)
            for frame in range(1, fps + 1):
                result = smoother.update(RingPose((10, 10), 30, 40), frame / fps)
            results.append(result)
        self.assertAlmostEqual(results[0].center[0], results[1].center[0])
        self.assertAlmostEqual(results[0].angle, results[1].angle)

    def test_reset_after_gap_or_jump(self):
        for timestamp, target in [(1, RingPose((10, 10), 20, 20)),
                                  (0.03, RingPose((500, 500), 20, 20))]:
            smoother = PoseSmoother()
            smoother.update(RingPose((0, 0), 20, 0), 0)
            self.assertEqual(smoother.update(target, timestamp), target)

    def test_zero_smoothing(self):
        smoother = PoseSmoother(0)
        smoother.update(RingPose((0, 0), 20, 0), 0)
        target = RingPose((10, 10), 30, 30)
        self.assertEqual(smoother.update(target, 0.01), target)

    def test_hands_can_reorder_and_missing_hand_resets(self):
        smoother = HandPoseSmoother()
        left = RingPose((20, 20), 20, 0)
        right = RingPose((200, 200), 40, 90)
        smoother.update(['Left', 'Right'], [left, right], 0)
        self.assertEqual(smoother.update(['Right', 'Left'], [right, left], 0.03), [right, left])
        smoother.update([], [], 0.06)
        moved = RingPose((40, 40), 30, 20)
        self.assertEqual(smoother.update(['Left'], [moved], 0.09), [moved])

    def test_duplicate_labels_and_invalid_poses_do_not_share_history(self):
        smoother = HandPoseSmoother()
        pose = RingPose((0, 0), 20, 0)
        moved = RingPose((10, 10), 30, 20)
        smoother.update(['Left'], [pose], 0)
        self.assertEqual(smoother.update(['Left', 'Left'], [pose, moved], 0.03), [pose, moved])
        smoother.update(['Left'], [None], 0.06)
        self.assertEqual(smoother.update(['Left'], [moved], 0.09), [moved])


class RotationTests(unittest.TestCase):
    def test_upright_asset_rotation_direction(self):
        asset = np.zeros((9, 9, 4), dtype=np.uint8)
        asset[1, 4] = (0, 0, 255, 255)  # Red point above center.
        upright = transform_ring(asset, 9, -90)
        np.testing.assert_allclose(upright[1, 4], (0, 0, 1, 1))
        right = transform_ring(asset, 9, 0)
        y, x = np.unravel_index(right[:, :, 3].argmax(), right.shape[:2])
        self.assertGreater(x, (right.shape[1] - 1) / 2)
        self.assertAlmostEqual(y, (right.shape[0] - 1) / 2, delta=0.5)

    def test_scaling_preserves_proportions(self):
        asset = np.full((10, 20, 4), 255, dtype=np.uint8)
        self.assertEqual(transform_ring(asset, 40, -90).shape, (20, 40, 4))

    def test_rotation_canvas_expands(self):
        asset = np.full((20, 40, 4), 255, dtype=np.uint8)
        rotated = transform_ring(asset, 40, -45)
        self.assertGreater(rotated.shape[0], 20)
        self.assertGreater(rotated.shape[1], 40)

    def test_transparency_and_edge_clipping(self):
        frame = np.full((20, 20, 3), 100, dtype=np.uint8)
        asset = np.zeros((5, 5, 4), dtype=np.uint8)
        asset[:] = (0, 0, 255, 128)
        overlay_ring(frame, asset, RingPose((0, 0), 5, -90))
        np.testing.assert_array_equal(frame[0, 0], (50, 50, 178))
        np.testing.assert_array_equal(frame[-1, -1], (100, 100, 100))
        before = frame.copy()
        overlay_ring(frame, asset, RingPose((-100, -100), 5, -90))
        np.testing.assert_array_equal(frame, before)

    def test_transparent_colors_do_not_create_fringes(self):
        asset = np.zeros((9, 9, 4), dtype=np.uint8)
        asset[:, :, 0] = 255  # Invisible blue must not leak into interpolated edges.
        asset[2:7, 2:7] = (0, 0, 255, 255)
        rotated = transform_ring(asset, 15, -30)
        self.assertEqual(float(rotated[:, :, 0].max()), 0)


if __name__ == '__main__':
    unittest.main()
