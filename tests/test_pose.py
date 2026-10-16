"""Drawing timing from joint tracks (pure numpy; no model needed)."""
import unittest

try:
    import numpy as np
    from pipeline import pose
except ImportError:
    pose = None


@unittest.skipIf(pose is None, 'numpy not installed (use .venv)')
class PoseTiming(unittest.TestCase):
    def test_runs_follow_joint_motion_not_noise(self):
        t, hold = 12, 2
        kpts = np.zeros((t, 17, 3), np.float32)
        kpts[..., 2] = 0.9
        for i in range(t):
            kpts[i, :, 0] = 100 + 10 * (i // hold)                 # character on 2s
            kpts[i, :, 1] = 200 + 0.3 * ((-1) ** i)               # sub-pixel detector jitter
        boxes = np.tile(np.array([50, 50, 250, 450], np.float32), (t, 1))
        self.assertEqual(pose.pose_runs(kpts, boxes), [2] * 6)

    def test_segments_need_consecutive_frames_of_one_track(self):
        data = {'shot': np.array([0, 0, 0, 0, 1, 1]), 'track': np.array([1, 1, 1, 2, 1, 1]),
                'frame': np.array([0, 1, 2, 2, 5, 7])}
        segs = [(tr, list(rows)) for tr, rows in pose.track_segments(data, min_len=2)]
        self.assertEqual(segs, [(1, [0, 1, 2])])                  # shot 1 has a gap


if __name__ == '__main__':
    unittest.main()
