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


def _scene():
    import xml.etree.ElementTree as ET
    seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
    return seq, ET.SubElement(seq, 'Frame', ID='1', Position='0')


def _layer(fr, key, visible=True):
    import xml.etree.ElementTree as ET
    ET.SubElement(fr, 'LayerDef', ID=key, Visible='true' if visible else 'false')


def _obj(fr, key, lid, col, xy, order, typ='1'):
    import xml.etree.ElementTree as ET
    ao = ET.SubElement(fr, 'AO', ID=str(key), TypeId=typ, LayerId=lid, Color=str(col), ThicknessScale=repr(C.snap_th(4)), DrawOrder=str(order))
    for i, (x, y) in enumerate(xy):
        ET.SubElement(ao, 'AP', ID=str(key * 10 + i), X=str(x), Y=str(y))
    return ao


def _fs(fill, key, t=None, contour=0):
    import xml.etree.ElementTree as ET
    if t is None:
        ET.SubElement(fill, 'FS', ObjId=str(key), Kind='1', Contour=str(contour))
    else:
        ET.SubElement(fill, 'FS', ObjId=str(key), Kind='0', StartPtId=str(key * 10), EndPtId=str(key * 10 + 1),
                      StartT=repr(t[0]), EndT=repr(t[1]), Contour=str(contour))


class GptRound1Regression(unittest.TestCase):
    """GPT 1라운드 검토(11-01) 재현 반례 → 회귀 방지. 그림·정답 정합성은 seq_check(σ=1.5 흐림 비교)로."""

    def test_all_hidden_layers_give_no_units(self):   # ②
        seq, fr = _scene()
        _layer(fr, '0', False)
        _obj(fr, 1, '0', -16777216, [(20, 50), (80, 50)], 0)
        self.assertEqual(C.units_of(fr, 0.5625), [])
        seq2, fr2 = _scene()
        _obj(fr2, 1, '0', -16777216, [(20, 50), (80, 50)], 0)   # 레이어 정의가 없으면 보이는 것으로
        self.assertEqual(len(C.units_of(fr2, 0.5625)), 1)

    def test_hidden_fill_owner_consistent(self):   # ①
        import seq_check as SC
        import xml.etree.ElementTree as ET
        seq, fr = _scene()
        _layer(fr, 'hidden', False)
        _layer(fr, 'visible')
        _obj(fr, 1, 'hidden', 0, [(20, 20), (80, 20)], 0)
        _obj(fr, 2, 'visible', 0, [(80, 20), (50, 80)], 1)
        _obj(fr, 3, 'visible', 0, [(50, 80), (20, 20)], 2)
        fill = ET.SubElement(fr, 'FR', Color='-65536')
        for k in (1, 2, 3):
            _fs(fill, k, (0, 1))
        self.assertGreater(SC.mismatch(seq, fr)[0], 1000)   # 원본 그대로는 그림·정답이 다르다(검사기가 잡는지)
        for sd in range(5):
            seq2, fr2 = C.real_frame(seq, fr, random.Random(sd), 0.5625)
            self.assertEqual(SC.mismatch(seq2, fr2)[0], 0)
            self.assertEqual(fr2.findall('FR'), [])

    def test_crop_keeps_original_order(self):   # ③
        import xml.etree.ElementTree as ET
        seq, fr = _scene()
        _layer(fr, '0')
        for k, col in ((1, -65536), (2, -16776961), (3, -16711936)):
            _obj(fr, k, '0', col, [(20, 50), (80, 50)], k - 1)
        fill = ET.SubElement(fr, 'FR', Color='0')
        for k in (1, 3):
            _fs(fill, k)
        seq2, fr2 = C.real_crop(fr, random.Random(0), 0.5625, 2048)
        self.assertEqual([a.get('Color') for _, a in K.order_objects(seq2, fr2)], [a.get('Color') for _, a in K.order_objects(seq, fr)])
        seq.set('BackgroundColor', '-16776961')   # 시퀀스 배경 상속
        seq3, fr3 = C.real_crop(fr, random.Random(0), 0.5625, 2048, seq.get('BackgroundColor'))
        self.assertEqual(seq3.get('BackgroundColor'), '-16776961')

    def test_partial_crop_order_is_subsequence(self):
        rel = '묶음1_Sfa__zip/hownty.sfa'
        root = C.load(rel, V.ROOT)
        hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
        fr = next(f for f in root.findall('Frame') if len(K.encode(root, f)[0]) > 2048)
        seq, f2 = C.real_crop(fr, random.Random(1), hwr, 1500)
        orig = [a.get('ID') for _, a in K.order_objects(root, fr)]
        got = [a.get('ID') for _, a in K.order_objects(seq, f2)]
        it = iter(orig)
        self.assertTrue(all(g in it for g in got))   # 원래 그리기 순서의 부분열

    def test_per_frame_cap(self):   # ⑦
        import seq_data as D
        from collections import Counter
        for sd in range(200):
            p = D.pick_frames(2, 30, random.Random(sd))
            self.assertLessEqual(max(Counter(p).values()), 3)
            self.assertEqual(len(p), 6)
        self.assertEqual(sorted(D.pick_frames(40, 30, random.Random(0))), sorted(set(D.pick_frames(40, 30, random.Random(0)))))

    def test_flip_mirrors_circle_fills(self):   # ④ 좌우 반전 = 원래 그림의 거울상
        import numpy as np
        import copy
        import xml.etree.ElementTree as ET
        import sfa_render as R
        import seq_check as SC
        seq, fr = _scene()
        _layer(fr, '0')
        _obj(fr, 1, '0', -16777216, [(30, 40), (45, 55)], 0, '2')            # 비스듬한 지름 원 — 부분 면
        _obj(fr, 2, '0', -16777216, [(60, 30), (75, 30)], 1, '2')            # 복합 윤곽 안 WHOLE 원
        _obj(fr, 3, '0', -16777216, [(75, 30), (80, 70)], 2)
        _obj(fr, 4, '0', -16777216, [(80, 70), (60, 30)], 3)
        f1 = ET.SubElement(fr, 'FR', Color='-65536')
        _fs(f1, 1, (0.1, 0.45))
        f2 = ET.SubElement(fr, 'FR', Color='-16776961')
        _fs(f2, 2)
        _fs(f2, 3, (0, 1))
        _fs(f2, 4, (0, 1))
        R.PARAMS.update(pad=0.0, thick_mul=640 / 1920)
        a = R.render_frame(seq, fr, 640, 360)[..., :3]
        g = copy.deepcopy(fr)
        for p in g.iter('AP'):
            p.set('X', repr(100 - float(p.get('X'))))
        circ = {'1', '2'}
        for r in g.findall('FR'):
            C.mirror_fs(r, circ)
        b = R.render_frame(seq, g, 640, 360)[..., :3]
        self.assertEqual(SC.tolerant_diff(np.ascontiguousarray(a[:, ::-1]), b), 0)
        g2 = copy.deepcopy(fr)   # 면 T를 그대로 두면(예전 코드) 거울상이 아니다
        for p in g2.iter('AP'):
            p.set('X', repr(100 - float(p.get('X'))))
        self.assertGreater(SC.tolerant_diff(np.ascontiguousarray(a[:, ::-1]), R.render_frame(seq, g2, 640, 360)[..., :3]), 100)


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
