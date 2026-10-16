"""Shot split / hold / camera-only classification on synthetic frames (needs numpy + opencv)."""
import tempfile
import unittest
from pathlib import Path

try:
    import cv2
    import numpy as np
    from pipeline import shots
except ImportError:          # system Python without the .venv packages
    shots = None


def moving_square(n, hold):
    frames = []
    for i in range(n):
        f = np.full((180, 320, 3), 128, np.uint8)
        x = 20 + 8 * (i // hold)
        cv2.rectangle(f, (x, 60), (x + 40, 100), (255, 255, 255), -1)
        frames.append(f)
    return frames


def panned_picture(n, step=3):
    rng = np.random.default_rng(7)
    big = cv2.GaussianBlur(rng.integers(0, 255, (260, 480, 3), dtype=np.uint8), (5, 5), 0)
    big[..., 0] = np.clip(big[..., 0].astype(int) + 80, 0, 255)          # blue-ish, unlike the other shots
    return [big[20:200, 10 + step * i:330 + step * i].copy() for i in range(n)]


@unittest.skipIf(shots is None, 'numpy/opencv not installed (use .venv)')
class Shots(unittest.TestCase):
    def test_cuts_holds_and_kinds(self):
        still = [np.full((180, 320, 3), (30, 30, 200), np.uint8)] * 10
        frames = moving_square(24, hold=2) + panned_picture(16) + still
        result = shots.analyse_frames(frames, 24.0)
        self.assertEqual([(s['start'], s['end']) for s in result['shots']], [(0, 24), (24, 40), (40, 50)])
        a, b, c = result['shots']
        self.assertEqual((a['kind'], a['hold_mode'], a['drawings']), ('animated', 2, 12))
        self.assertEqual(b['kind'], 'camera_only')
        self.assertEqual(b['drawing_hold_mode'], 16)                    # pan = one drawing, not on 1s
        self.assertEqual((c['kind'], c['drawings']), ('still', 1))

    def test_cross_dissolve_is_split(self):
        a = moving_square(16, hold=2)
        b = [np.full((180, 320, 3), (40, 90, 160), np.uint8) for _ in range(16)]
        for f in b:
            cv2.circle(f, (220, 90), 50, (230, 230, 230), -1)
        fade = [cv2.addWeighted(a[-1], 1 - k / 11, b[0], k / 11, 0) for k in range(1, 11)]
        result = shots.analyse_frames(a + fade + b, 24.0)
        self.assertEqual(len(result['shots']), 2)
        self.assertTrue(16 <= result['shots'][1]['start'] <= 26)

    def test_flash_frame_is_an_event_not_a_shot(self):
        frames = moving_square(24, hold=2)
        frames[11] = np.full_like(frames[11], 255)
        frames[11][..., 0] = 0                                         # one yellow impact frame
        result = shots.analyse_frames(frames, 24.0)
        self.assertEqual(len(result['shots']), 1)
        self.assertEqual(result['shots'][0]['flashes'], [[11, 12]])

    def test_lineart_and_clip_file(self):
        page = []
        for i in range(12):
            f = np.full((180, 320, 3), 245, np.uint8)
            cv2.line(f, (40 + 10 * (i // 3), 30), (200, 150), (20, 20, 20), 2)
            page.append(f)
        shot = shots.analyse_frames(page, 24.0)['shots'][0]
        self.assertTrue(shot['lineart_like'])
        self.assertEqual(shot['hold_mode'], 3)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, '1.avi')
            w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 24, (320, 180))
            for f in moving_square(12, hold=3):
                w.write(f)
            w.release()
            clip = shots.analyse_clip(path)
            self.assertEqual(clip['size'], [320, 180])
            self.assertEqual(clip['shots'][0]['hold_mode'], 3)


if __name__ == '__main__':
    unittest.main()
