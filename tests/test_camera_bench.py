"""Camera estimation on synthetic frames and the ground-truth clean-up benchmark (numpy + opencv)."""
import sys
import unittest
import warnings
from pathlib import Path

try:
    import cv2
    import numpy as np
    from pipeline import camera
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
    import motion_bench
except ImportError:
    camera = None


@unittest.skipIf(camera is None, 'numpy/opencv not installed (use .venv)')
class Camera(unittest.TestCase):
    def test_zoom_and_pan_recovered_with_a_moving_person_masked(self):
        rng = np.random.default_rng(3)
        world = cv2.GaussianBlur(rng.integers(0, 255, (720, 1280), dtype=np.uint8), (5, 5), 0)
        frames, boxes, truth = [], [], []
        for t in range(12):
            s, tx = 1.0 + 0.02 * t, -4.0 * t
            m = np.array([[s, 0, tx - (s - 1) * 640], [0, s, -(s - 1) * 360]])
            f = cv2.warpAffine(world, m, (1280, 720))
            x = 300 + 25 * t                                          # a "person" moving on its own
            cv2.rectangle(f, (x, 200), (x + 120, 600), 255, -1)
            frames.append(cv2.resize(f, (320, 180), interpolation=cv2.INTER_AREA))
            boxes.append([(x, 200, x + 120, 600)])
            truth.append(m)
        cams = camera.estimate(frames, boxes, 1280)
        self.assertAlmostEqual(camera.scale_of(cams[-1]), camera.scale_of(truth[-1]), delta=0.02)
        p = camera.to_screen(cams[-1], [[640, 360]])[0]
        q = camera.to_screen(truth[-1], [[640, 360]])[0]
        self.assertLess(np.hypot(*(p - q)), 6.0)                       # px at 1280 wide
        back = camera.to_world(cams[-1], camera.to_screen(cams[-1], [[100, 50]]))[0]
        np.testing.assert_allclose(back, [100, 50], atol=1e-6)


@unittest.skipIf(camera is None, 'numpy/opencv not installed (use .venv)')
class Benchmark(unittest.TestCase):
    def test_clean_up_targets(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r = {row['scenario']: row['new'] for row in motion_bench.bench()}
        self.assertLess(r['zoom_reveal']['error_%body'], 5)          # legs hidden by a close-up (was 13.8)
        self.assertEqual(r['track_break']['missing_frames'], 0)       # no blinking (was 33 frames)
        self.assertLess(r['jitter']['jitter_ratio'], 1.7)            # detector shake (was 2.29)
        self.assertLess(r['jitter']['error_%body'], 1.5)
        self.assertLess(r['occlusion']['error_%body'], 15)


if __name__ == '__main__':
    unittest.main()
