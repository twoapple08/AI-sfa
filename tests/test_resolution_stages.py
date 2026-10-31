"""해상도 단계 학습(10-31 복원, 사용자 10-29 '1080 → 720 → 480 → 360'): 그림 칸 고정, 단계 경계, 영상 저장 왕복, 작업자 설정."""
import shutil
import sys
import unittest
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))

import kaggle_seq_worker as KW  # noqa: E402

try:
    import torch  # noqa: F401
    import seq_train as S
except ImportError:   # torch 없는 환경
    S = None


@unittest.skipIf(S is None, 'torch 없음')
class TestStagesModel(unittest.TestCase):
    def test_feat_grid(self):
        self.assertEqual(S.feat_grid(640, 8), [45, 80])
        self.assertEqual(S.feat_grid(640, 16), [23, 40])

    def test_grid_pooling(self):
        # 1080 입력도 기본(360)과 같은 45×80칸 → 글자 쪽 메모리와 칸 뜻이 해상도와 무관
        net = S.Net(32, 1, 2, 64, 'resnet34', pretrained=False, stride=8, grid=S.feat_grid(640, 8)).eval()
        hwr = torch.tensor([0.5625])
        with torch.no_grad():
            for w in (640, 854, 1920):
                m = net.memory(torch.rand(1, 3, w * 9 // 16, w), hwr)
                self.assertEqual(tuple(m.shape), (1, 45 * 80, 32), w)
        old = S.Net(32, 1, 2, 64, 'resnet34', pretrained=False, stride=8).eval()   # 예전 저장본(grid 없음)은 입력 크기 그대로
        with torch.no_grad():
            self.assertEqual(old.memory(torch.rand(1, 3, 360, 640), hwr).shape[1], 45 * 80)

    def test_stage_of(self):
        frac = [0.2, 0.25, 0.25, 0.3]
        self.assertEqual([S.stage_of(p, frac) for p in (0, 0.19, 0.2, 0.44, 0.45, 0.69, 0.7, 0.99, 1.0, 1.5)], [0, 0, 1, 1, 2, 2, 3, 3, 3, 3])


@unittest.skipIf(S is None, 'torch 없음')
class TestFieldScores(unittest.TestCase):
    def test_field_hits_report(self):
        # 사용자 10-31: 분야마다 100점 만점 + 좌표는 '몇 개마다 지적'
        K = S.K
        fl = [K.FID[f] for f in ('spec', 'coord', 'coord', 'coord', 'coord', 'color')]
        tgt = torch.tensor([[K.TOK['LINE'], K.OFF + 1, K.OFF + 2, K.OFF + 3, K.OFF + 4, K.OFF + 9, K.TOK['PAD']]])
        fld = torch.tensor([fl + [0]])
        pred = tgt.clone()
        pred[0, 4] = K.OFF + 7   # 좌표 4개 중 1개 틀림
        logits = torch.nn.functional.one_hot(pred, K.VOCAB).float()
        hn = S.field_hits(logits, tgt, fld)
        rec, txt = S.field_report(hn, 'v_')
        self.assertEqual(rec['v_struct'], 100.0)
        self.assertEqual(rec['v_coord'], 75.0)
        self.assertEqual(rec['v_coord_every'], 4.0)
        self.assertEqual(rec['v_color'], 100.0)
        self.assertNotIn('v_glow', rec)   # 없는 분야는 안 적음
        self.assertIn('좌표 75(4.0개마다 지적)', txt)


@unittest.skipIf(shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None, 'ffmpeg 없음')
class TestVideoStore(unittest.TestCase):
    def test_encode_decode_count(self):
        try:
            import vec_data as V
        except ImportError as e:   # skia 등 렌더 의존성 없음
            self.skipTest(str(e))
        rng = np.random.default_rng(0)
        frames = [np.full((36, 64, 3), v, np.uint8) for v in (0, 120, 255)]
        frames[1][10:20, 10:40] = rng.integers(0, 255, (10, 30, 3))
        vid = V.encode_video(iter(frames), 23, size=(64, 36))   # 하나씩 흘려 넣기(1080 수백 장을 모으지 않게)
        self.assertEqual(V.count_frames(vid), 3)
        dec = V.decode_video(vid, 64, 36)
        self.assertEqual(dec.shape, (3, 36, 64, 3))
        self.assertLess(np.abs(dec.astype(int) - np.stack(frames)).mean(), 12)
        self.assertTrue(np.array_equal(V.encode_decode(frames, 23), dec))   # 예전 함수와 같은 결과


class TestAugThickness(unittest.TestCase):
    def test_thickness_scaled_with_answer(self):
        # 늘린 사본: 모든 오브젝트 굵기에 같은 배율(0.5–2배) → 정답의 굵기 칸도 같이 바뀐다(사용자 10-31)
        try:
            import seq_data as D
        except ImportError as e:
            self.skipTest(str(e))
        import xml.etree.ElementTree as ET
        xml = ('<Sequence><Frame Position="1"><AO ID="1" TypeId="1" Color="-16777216" ThicknessScale="1.0">'
               '<AP X="10" Y="10"/><AP X="20" Y="20"/></AO><AO ID="2" TypeId="1" Color="-16777216" ThicknessScale="3.0">'
               '<AP X="30" Y="30"/><AP X="40" Y="40"/></AO></Frame></Sequence>')
        seen = []
        for seed in range(20):
            root = ET.fromstring(xml)
            info = D.augment(root, np.random.default_rng(seed))
            t1, t2 = (float(o.get('ThicknessScale')) for o in root.iter('AO'))
            self.assertAlmostEqual(t1, info['thick'])
            self.assertAlmostEqual(t2, 3.0 * info['thick'])
            self.assertTrue(D.THICK_RANGE[0] <= info['thick'] <= D.THICK_RANGE[1])
            self.assertEqual(D.K.style_of(next(root.iter('AO')))[1], D.K.q_th(t1))
            seen.append(info['thick'])
        self.assertLess(min(seen), 0.8)
        self.assertGreater(max(seen), 1.3)


class TestWorkerStages(unittest.TestCase):
    def test_data_args(self):
        for smoke in (False, True):
            a = KW.data_args(dict(smoke=smoke), 4)
            self.assertEqual(set(a), {'sd1920', 'sd1280', 'sd854', 'sd', 'sv', 'ss'})
            for r in KW.HIRES:   # 고해상도 자료 = 기본 학습 자료와 같은 고르기 + 폭·영상 저장만 다름
                self.assertEqual(a[f'sd{r}'], a['sd'] + f' --W {r} --video')
            self.assertNotIn('--video', a['sd'])
            self.assertIn('--synth 0.3', a['sd'])   # 페인트 합성(사용자 10-29) — 학습 자료에만
            self.assertNotIn('--synth', a['sv'] + a['ss'])
            b = KW.data_args(dict(smoke=smoke, stages=False), 4)
            self.assertEqual(set(b), {'sd', 'sv', 'ss'})
            self.assertEqual(b['sd'], a['sd'])


if __name__ == '__main__':
    unittest.main()
