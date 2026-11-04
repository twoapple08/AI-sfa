"""생성 수 선택 보정(mass_pick) 시험: 기본은 기존 argmax와 같고, 켜면 흩어진 확률 합을 반영한다."""
import sys
import unittest
from pathlib import Path

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


@unittest.skipIf(torch is None, 'torch 필요')
class TestMassPick(unittest.TestCase):
    def setUp(self):
        import seq_train as T
        import sfa_tokens as K
        self.T, self.K = T, K
        self.big = K.TOK['BIG']
        self.al = (frozenset([self.big]), 1000, 5000, 'coord')

    def spread(self, centre=3000, width=40, big=0.14):
        """정답 근처 이웃 칸에 확률이 흩어지고 BIG 한 칸에 몰린 분포(진단에서 본 모양)."""
        K = self.K
        p = torch.full((K.VOCAB,), 1e-9)
        p[K.OFF + centre - width:K.OFF + centre + width + 1] = (1 - big) / (2 * width + 1)
        p[self.big] = big
        lg = p.log() + self.T.allowed_mask(self.al, 'cpu')
        return lg

    def test_default_is_plain_argmax(self):
        lg = self.spread()
        self.assertEqual(self.T.mass_pick(lg, self.al), int(lg.argmax()))
        self.assertEqual(int(lg.argmax()), self.big)

    def test_big_mass_rejects_big_when_in_range_mass_is_larger(self):
        t = self.T.mass_pick(self.spread(), self.al, big_mass=True)
        self.assertNotEqual(t, self.big)
        self.assertTrue(abs(t - self.K.OFF - 3000) <= 40)

    def test_big_kept_when_it_really_dominates(self):
        lg = self.spread(big=0.9)
        self.assertEqual(self.T.mass_pick(lg, self.al, big_mass=True), self.big)

    def test_window_prefers_dense_region_over_single_spike(self):
        K = self.K
        al = (frozenset(), 1000, 5000, 'coord')
        p = torch.full((K.VOCAB,), 1e-9)
        p[K.OFF + 2000:K.OFF + 2061] = 0.012     # 넓게 모인 덩어리(합 약 0.73)
        p[K.OFF + 4000] = 0.05                    # 한 칸 튀는 값
        lg = p.log() + self.T.allowed_mask(al, 'cpu')
        self.assertEqual(self.T.mass_pick(lg, al), K.OFF + 4000)
        t = self.T.mass_pick(lg, al, coord_window=30)
        self.assertTrue(2000 <= t - K.OFF <= 2060)

    def test_window_ignored_outside_coordinates(self):
        al = (frozenset(), 0, 255, 'color')
        lg = torch.randn(self.K.VOCAB) + self.T.allowed_mask(al, 'cpu')
        self.assertEqual(self.T.mass_pick(lg, al, coord_window=30), int(lg.argmax()))


if __name__ == '__main__':
    unittest.main()
