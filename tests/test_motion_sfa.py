"""Pose clean-up and stickman SFA conversion on synthetic tracks (numpy needed)."""
import sys
import unittest
from pathlib import Path

try:
    import numpy as np
    from pipeline import motion, to_sfa
except ImportError:
    motion = None

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def coco_pose(dx=0.0):
    """Standing person around (960, 540) in a 1920x1080 frame, shifted by dx."""
    xy = {0: (960, 330), 1: (950, 320), 2: (970, 320), 3: (940, 325), 4: (980, 325),
          5: (920, 400), 6: (1000, 400), 7: (900, 480), 8: (1020, 480), 9: (890, 560), 10: (1030, 560),
          11: (930, 560), 12: (990, 560), 13: (925, 660), 14: (995, 660), 15: (920, 760), 16: (1000, 760)}
    return [[xy[j][0] + dx, xy[j][1], 0.9] for j in range(17)]


@unittest.skipIf(motion is None, 'numpy not installed (use .venv)')
class Cleanup(unittest.TestCase):
    def test_swapped_labels_are_mirrored_back(self):
        k = np.array([coco_pose(), coco_pose(2)], float)
        k[1] = k[1, motion.MIRROR]                                   # detector flipped L/R
        fixed = motion.fix_swaps(k)
        np.testing.assert_allclose(fixed[1, 5, :2], [922, 400])

    def test_short_gaps_filled_long_gaps_kept(self):
        k = np.array([coco_pose(i) for i in range(12)], float)
        k[2:4, 9, :2] = np.nan
        k[5:11, 10, :2] = np.nan
        out = motion.fill_gaps(k)
        self.assertAlmostEqual(out[2, 9, 0], 892.0)
        self.assertTrue(np.isnan(out[7, 10, 0]))


@unittest.skipIf(motion is None, 'numpy not installed (use .venv)')
class StickmanSfa(unittest.TestCase):
    def setUp(self):
        joints = [coco_pose(10 * (i // 2)) for i in range(8)]
        joints[3][9] = [None, None, 0.0]                             # a wrist lost in one frame
        self.motion = {'clip': '1', 'fps': 24.0, 'size': [1920, 1080],
                       'characters': [{'shot': 0, 'track': 1, 'start': 0, 'joints': joints,
                                       'runs': [2] * 4, 'uncertain': []}]}

    def test_valid_sfa_with_stable_object_ids(self):
        import sfa
        root, info = to_sfa.build(self.motion)
        self.assertEqual(sfa.validate(root), [])
        self.assertEqual(info['frames'], 8)
        frames = root.findall('Frame')
        ids = [[a.get('ID') for a in f.findall('AO')] for f in frames]
        self.assertTrue(all(i == ids[0] for i in ids))                # app pairs objects by ID
        torso = frames[0].findall('AO')[1].findall('AP')
        self.assertAlmostEqual(float(torso[0].get('X')), 50.0)        # neck x = 960 px -> 50 %
        self.assertAlmostEqual(float(torso[0].get('Y')), 400 / 1080 * 100, places=3)

    def test_letterbox_fit_and_render(self):
        to_pct = to_sfa.fit((1440, 1080))                            # 4:3 clip in the 16:9 canvas
        self.assertAlmostEqual(to_pct((0, 0))[0], 12.5)
        try:
            import sfa_render
        except ImportError:
            self.skipTest('renderer dependencies missing')
        root, _ = to_sfa.build(self.motion)
        img = sfa_render.render_frame(root.find('Frame'), 320, 180)
        self.assertGreater(int((img.sum(axis=2) < 200).sum()), 50)   # dark stick lines drawn


if __name__ == '__main__':
    unittest.main()
