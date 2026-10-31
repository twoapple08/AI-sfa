"""조합 문제·쉬운 것부터(사용자 11-01): 묶음 떼어 오기·ID 새로 매기기·정답 왕복, 단계 안 길이 분위."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

import sfa_compose as C  # noqa: E402
import sfa_objscore as OS  # noqa: E402
import sfa_tokens as K  # noqa: E402
import seq_train as ST  # noqa: E402
import vec_data as V  # noqa: E402


class ComposeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = random.Random(5)
        cls.pool, cls.bgp, cls.hwrs = C.build_pool(rng.sample(V.file_list(), 40), V.ROOT, rng, 3)

    def test_ids_and_references_valid(self):
        rng = random.Random(1)
        for n in (1, 4, 30, 120):
            seq, fr = C.compose(self.pool, rng, n, 0.5625, self.bgp)
            aos = fr.findall('AO')
            ao_ids = [a.get('ID') for a in aos]
            ap_ids = [p.get('ID') for a in aos for p in a.findall('AP')]
            self.assertEqual(len(ao_ids), len(set(ao_ids)))
            self.assertEqual(len(ap_ids), len(set(ap_ids)))
            layers = {d.get('ID') for d in fr.findall('LayerDef')}
            self.assertTrue(all(a.get('LayerId') in layers for a in aos))
            for a in aos:
                for p in a.findall('AP'):
                    for ac in p.findall('AC'):
                        self.assertIn(ac.get('ConnPtId'), ap_ids)
            for r in fr.findall('FR'):
                for s in r.findall('FS'):
                    self.assertIn(s.get('ObjId'), ao_ids)

    def test_small_target_gives_small_frame(self):
        rng = random.Random(2)
        ns = [len(C.compose(self.pool, rng, 1, 0.5625, self.bgp)[1].findall('AO')) for _ in range(20)]
        self.assertLessEqual(max(ns), 2)

    def test_answer_roundtrip_and_onscreen(self):
        rng = random.Random(3)
        for _ in range(20):
            seq, fr = C.compose(self.pool, rng, C.n_target(rng, 1, 120), 0.5625, self.bgp)
            t, st = K.encode(seq, fr)
            K.fields(t)
            if not st['drop_far'] and not st['clamp']:
                self.assertTrue(OS.score(K.decode(t), fr, hwr=0.5625)['perfect'])

    def test_real_frames_differ_per_frame(self):
        rng = random.Random(4)
        rel = V.file_list()[3]
        root = C.load(rel, V.ROOT)
        fr = root.findall('Frame')[0]
        a = C.real_frame(root, fr, rng, 0.5625)[1]
        b = C.real_frame(root, fr, rng, 0.5625)[1]
        pa = [p.get('X') for p in a.iter('AP')]
        pb = [p.get('X') for p in b.iter('AP')]
        self.assertNotEqual(pa, pb)
        self.assertEqual(fr.find('.//AP').get('X'), C.load(rel, V.ROOT).findall('Frame')[0].find('.//AP').get('X'))   # 원본은 그대로


class RealCropTest(unittest.TestCase):
    def test_long_real_frame_is_cropped_in_place(self):
        """2,048을 넘는 실제 장(사용자 11-01): 버리지 않고 일부 구역을 원래 자리·모양 그대로 잘라 한도 안에."""
        rel = '묶음1_Sfa__zip/hownty.sfa'
        root = C.load(rel, V.ROOT)
        hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
        fr = next(f for f in root.findall('Frame') if len(K.encode(root, f)[0]) > 2048)
        seq, f2 = C.real_crop(fr, random.Random(0), hwr, 1984)
        t = K.encode(seq, f2)[0]
        self.assertLessEqual(len(t), 1984)
        self.assertGreater(len(t), 1000)   # 한도 가까이 채운다
        orig = {tuple((round(float(p.get('X')), 6), round(float(p.get('Y')), 6)) for p in a.findall('AP')) for a in fr.findall('AO')}
        for a in f2.findall('AO'):
            self.assertIn(tuple((round(float(p.get('X')), 6), round(float(p.get('Y')), 6)) for p in a.findall('AP')), orig)


class CurriculumTest(unittest.TestCase):
    def test_quantile_schedule(self):
        self.assertAlmostEqual(ST.cur_quantile(0.0), 0.2)
        self.assertAlmostEqual(ST.cur_quantile(0.4), 0.6)
        self.assertAlmostEqual(ST.cur_quantile(0.8), 1.0)
        self.assertAlmostEqual(ST.cur_quantile(1.0), 1.0)
        qs = [ST.cur_quantile(x / 100) for x in range(101)]
        self.assertEqual(qs, sorted(qs))

    def test_stage_progress(self):
        frac = [0.2, 0.25, 0.25, 0.3]
        self.assertAlmostEqual(ST.stage_progress(0.1, frac, 0), 0.5)
        self.assertAlmostEqual(ST.stage_progress(0.45, frac, 1), 1.0)
        self.assertAlmostEqual(ST.stage_progress(0.85, frac, 3), 0.5)

    def test_cap_limits_batches(self):
        class D:
            tok = [[0] * n for n in (5, 10, 50, 100, 400)]

            def __len__(self):
                return 5
        b = ST.make_batches(D(), 4, 10000, cap=50)
        self.assertEqual(sorted(k for x in b for k in x), [0, 1, 2])


if __name__ == '__main__':
    unittest.main()
