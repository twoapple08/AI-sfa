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
        k = np.array([coco_pose(i) for i in range(16)], float)
        k[2:4, 9, :2] = np.nan
        k[4:14, 10, :2] = np.nan                                     # 10 frames > MAX_GAP
        out = motion.fill_gaps(k)
        self.assertAlmostEqual(out[2, 9, 0], 892.0)
        self.assertTrue(np.isnan(out[8, 10, 0]))


@unittest.skipIf(motion is None, 'numpy not installed (use .venv)')
class OffScreen(unittest.TestCase):
    def frames(self):
        out = []
        for i in range(8):
            f = coco_pose()
            if i >= 4:                                               # walks down: feet leave the picture
                f = [[x, y + 400, c] for x, y, c in f]
                for j in (15, 16):
                    f[j][1] = 1079.0                                 # detector clamps them to the edge
            out.append(f)
        return np.array(out, float)

    def test_clamped_joints_are_off_screen_not_real(self):
        k = self.frames()
        boxes = np.tile(np.array([800, 300, 1100, 1079], float), (8, 1))
        cleaned, _, _, bits = motion.clean_track(k, boxes, (1920, 1080))
        self.assertGreater(cleaned[5, 15, 1], 1080)                  # not the clamped edge value: below the frame
        self.assertEqual(cleaned[5, 15, 2], 0.02)                    # borrowed from a frame where it was seen
        self.assertEqual(bits[5], (1 << 15) | (1 << 16))
        self.assertEqual(bits[0], 0)

    def test_off_screen_leg_continues_past_the_canvas(self):
        k = self.frames()
        boxes = np.tile(np.array([800, 300, 1100, 1079], float), (8, 1))
        cleaned, runs, unsure, bits = motion.clean_track(k, boxes, (1920, 1080))
        joints = [[[None, None, 0.0] if np.isnan(x) else [x, y, c] for x, y, c in f] for f in cleaned]
        mo = {'clip': '1', 'fps': 24.0, 'size': [1920, 1080], 'characters': [
            {'shot': 0, 'track': 1, 'start': 0, 'joints': joints, 'runs': runs, 'uncertain': unsure,
             'offscreen': bits}]}
        root, _ = to_sfa.build(mo)
        shin = root.findall('Frame')[6].findall('AO')[7].findall('AP')
        knee_y, ankle_y = float(shin[0].get('Y')), float(shin[1].get('Y'))
        self.assertGreater(ankle_y, 100.0)                           # below the canvas, not squashed at the edge
        self.assertAlmostEqual((ankle_y - knee_y) * 1080 / 100, 100, delta=3)    # shin as last seen, not squashed


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

    def test_head_is_a_fixed_circle_that_only_turns(self):
        joints = [coco_pose() for _ in range(3)]
        for j in range(5):                                           # frame 1: head bowed (face near neck)
            joints[1][j] = [joints[1][j][0] + 30, joints[1][j][1] + 50, 0.9]
        for j in range(5):                                           # frame 2: big hairy head (face far up)
            joints[2][j] = [joints[2][j][0], joints[2][j][1] - 60, 0.9]
        mo = dict(self.motion, characters=[dict(self.motion['characters'][0], joints=joints, runs=[1, 1, 1])])
        root, _ = to_sfa.build(mo)
        sizes, dirs = [], []
        for f in root.findall('Frame'):
            top, neck = [(float(p.get('X')) * 19.2, float(p.get('Y')) * 10.8) for p in f.findall('AO')[0].findall('AP')]
            sizes.append(np.hypot(top[0] - neck[0], top[1] - neck[1]))
            dirs.append(np.degrees(np.arctan2(top[0] - neck[0], neck[1] - top[1])))
        self.assertAlmostEqual(max(sizes) - min(sizes), 0, delta=0.05)  # same size bowed, upright, big hair
        self.assertAlmostEqual(sizes[0], 0.75 * 160, delta=1)           # template ratio x torso (400 -> 560 px)
        self.assertGreater(dirs[1], dirs[0] + 20)                       # bowing turns the circle

    def test_world_mode_removes_the_camera(self):
        import sfa
        c = dict(self.motion['characters'][0])
        zoom = [1.0 + 0.2 * i for i in range(8)]                      # filmed with a zoom-in
        c['joints'] = [[[None, None, 0.0] if x is None else [960 + (x - 960) * z, 540 + (y - 540) * z, q]
                        for x, y, q in f] for f, z in zip(c['joints'], zoom)]
        c['camera'] = [[z, 0, 960 * (1 - z), 0, z, 540 * (1 - z)] for z in zoom]
        mo = dict(self.motion, characters=[c])
        root, _ = to_sfa.build(mo, world=True)
        self.assertEqual(sfa.validate(root), [])
        torso = [abs(float(f.findall('AO')[1].findall('AP')[1].get('Y')) - float(f.findall('AO')[1].findall('AP')[0].get('Y')))
                 for f in root.findall('Frame')]
        self.assertAlmostEqual(max(torso) - min(torso), 0, delta=0.01)   # no zoom left in world mode
        filmed, _ = to_sfa.build(mo)
        t2 = [abs(float(f.findall('AO')[1].findall('AP')[1].get('Y')) - float(f.findall('AO')[1].findall('AP')[0].get('Y')))
              for f in filmed.findall('Frame')]
        self.assertGreater(t2[-1], 2 * t2[0])                          # as filmed: the zoom is baked in

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


@unittest.skipIf(motion is None, 'numpy not installed (use .venv)')
class Slots(unittest.TestCase):
    """Test clip 317969 5-10s: a fighter whose track broke into pieces vanished, because only
    the two longest pieces of the shot were drawn."""
    @staticmethod
    def piece(track, start, n, dx):
        return {'shot': 0, 'track': track, 'start': start, 'joints': [coco_pose(dx) for _ in range(n)],
                'runs': [1] * n, 'uncertain': []}

    def mo(self, *pieces):
        return {'clip': '1', 'fps': 24.0, 'size': [1920, 1080], 'characters': list(pieces)}

    def necks(self, root):
        """Per frame: {slot AO ID base: neck x %}."""
        return [{int(f.findall('AO')[k].get('ID')) // 100: float(f.findall('AO')[k + 1].findall('AP')[0].get('X'))
                 for k in range(0, len(f.findall('AO')), 10)} for f in root.findall('Frame')]

    def test_broken_track_keeps_one_slot(self):
        import sfa
        left = self.piece(1, 0, 20, -400)                            # whole shot
        right_a = self.piece(2, 0, 8, 400)                           # the other fighter, track broke
        right_b = self.piece(3, 9, 11, 410)
        root, info = to_sfa.build(self.mo(left, right_a, right_b))
        self.assertEqual(sfa.validate(root), [])
        self.assertEqual((info['characters'], info['pieces']), (2, 3))
        necks = self.necks(root)
        self.assertEqual(len(necks[15]), 2)                          # both fighters drawn after the break
        self.assertEqual(set(necks[3]), set(necks[15]))              # same AO IDs -> the app tweens them
        self.assertEqual(len(necks[8]), 1)                           # the one-frame gap stays empty

    def test_far_piece_is_another_person(self):
        a = self.piece(1, 0, 10, -400)
        b = self.piece(2, 10, 10, 400)                               # starts where a ends, far away
        root, info = to_sfa.build(self.mo(a, b))
        self.assertEqual(info['characters'], 2)
        necks = self.necks(root)
        self.assertNotEqual(set(necks[0]), set(necks[15]))           # no jump across the screen

    def test_far_piece_joins_when_slots_are_full(self):
        a = self.piece(1, 0, 20, -400)
        b = self.piece(2, 0, 10, 400)
        c = self.piece(3, 10, 10, 0)                                 # third pose, only time-free slot is b
        _, info = to_sfa.build(self.mo(a, b, c))
        self.assertEqual((info['characters'], info['pieces']), (2, 3))

    def test_overlapping_extra_piece_is_dropped(self):
        a, b = self.piece(1, 0, 20, -400), self.piece(2, 0, 20, 400)
        extra = self.piece(3, 5, 5, 0)                               # a third person / duplicate
        _, info = to_sfa.build(self.mo(a, b, extra))
        self.assertEqual((info['characters'], info['pieces']), (2, 2))


@unittest.skipIf(motion is None, 'numpy not installed (use .venv)')
class ClipSfa(unittest.TestCase):
    def piece(self, shot, start, n, dx):
        return {'shot': shot, 'track': shot, 'start': start, 'joints': [coco_pose(dx) for _ in range(n)],
                'runs': [1] * n, 'uncertain': []}

    def test_every_shot_aligned_with_the_video(self):
        import sfa
        mo = {'clip': '7', 'fps': 24.0, 'size': [1920, 1080],
              'characters': [self.piece(0, 2, 6, -300), self.piece(1, 12, 8, 300)]}   # frames 8-11: nobody
        root, info = to_sfa.build_clip(mo, n_frames=24)
        self.assertEqual(sfa.validate(root), [])
        frames = root.findall('Frame')
        self.assertEqual((len(frames), info['frames']), (24, 24))     # same length as the clip
        drawn = [len(f.findall('AO')) // 10 for f in frames]
        self.assertEqual(drawn, [0, 0] + [1] * 6 + [0] * 4 + [1] * 8 + [0] * 4)
        x = lambda f: float(f.findall('AO')[1].findall('AP')[0].get('X'))
        self.assertLess(x(frames[2]), 50)                             # shot 0 person on the left
        self.assertGreater(x(frames[12]), 50)                         # shot 1 person on the right

    def test_batch_converts_each_clip_once(self):
        import json
        import tempfile
        mo = {'clip': '7', 'fps': 24.0, 'size': [1920, 1080], 'characters': [self.piece(0, 0, 4, 0)]}
        with tempfile.TemporaryDirectory() as d:
            media = Path(d, 'media')
            media.mkdir()
            (media / '7.motion.json').write_text(json.dumps(mo), encoding='utf-8')
            (media / '7.shots.json').write_text(json.dumps({'fps': 24.0, 'frames': 10, 'shots': []}), encoding='utf-8')
            (media / '8.motion.json').write_text(json.dumps(dict(mo, clip='8', characters=[])), encoding='utf-8')
            to_sfa.convert_all(d)
            out = Path(d, 'sfa', '7.sfa')
            self.assertTrue(out.exists())
            self.assertFalse(Path(d, 'sfa', '8.sfa').exists())       # nobody tracked: no file
            stamp = out.stat().st_mtime_ns
            to_sfa.convert_all(d)                                     # re-run skips finished clips
            self.assertEqual(out.stat().st_mtime_ns, stamp)


if __name__ == '__main__':
    unittest.main()
