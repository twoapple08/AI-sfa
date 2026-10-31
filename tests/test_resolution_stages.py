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


class TestWorkerStages(unittest.TestCase):
    def test_data_args(self):
        for smoke in (False, True):
            a = KW.data_args(dict(smoke=smoke), 4)
            self.assertEqual(set(a), {'sd1920', 'sd1280', 'sd854', 'sd', 'sv', 'ss'})
            for r in KW.HIRES:   # 고해상도 자료 = 기본 학습 자료와 같은 고르기 + 폭·영상 저장만 다름
                self.assertEqual(a[f'sd{r}'], a['sd'] + f' --W {r} --video')
            self.assertNotIn('--video', a['sd'])
            b = KW.data_args(dict(smoke=smoke, stages=False), 4)
            self.assertEqual(set(b), {'sd', 'sv', 'ss'})
            self.assertEqual(b['sd'], a['sd'])


if __name__ == '__main__':
    unittest.main()
