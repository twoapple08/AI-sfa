"""Kaggle A/B version2 실패(T4 fp16 초기 배율 넘침을 치명 오류로 처리) 회귀 시험."""
import sys
import unittest
from pathlib import Path

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
INF_GRAD = 1e37**.5  # 손실 16·f²≈1.6e38은 유한, 기울기≈8e38은 float32 범위 밖


@unittest.skipIf(torch is None, 'torch 필요')
class TestScaledUpdate(unittest.TestCase):
    def setUp(self):
        from seq_refine import scaled_update
        self.update = scaled_update
        torch.manual_seed(0)
        self.net = torch.nn.Linear(4, 1)
        with torch.no_grad():
            self.net.weight.fill_(.1)
            self.net.bias.zero_()
        self.optimizer = torch.optim.AdamW(self.net.parameters(), lr=1e-3)
        self.x = torch.full((2, 4), 10.)
        self.calls = 0

    def run_batch(self, factor=1.):
        def run():
            self.calls += 1
            loss = (self.net(self.x)*factor).pow(2).mean()
            return loss, dict(token=loss.detach())
        return run

    def test_scale_overflow_retries_same_batch_and_counts_one_update(self):
        # 큰 배율에서는 기울기가 inf가 된다. 배율이 줄어든 뒤 같은 묶음으로 정확히 한 번 업데이트한다.
        scaler = torch.amp.GradScaler('cpu', init_scale=2.**127)
        before = [p.detach().clone() for p in self.net.parameters()]
        loss, parts, overflows = self.update(self.net, self.optimizer, scaler, self.run_batch())
        self.assertGreaterEqual(overflows, 1)
        self.assertEqual(self.calls, overflows+1)
        self.assertLess(scaler.get_scale(), 2.**127)
        self.assertTrue(torch.isfinite(loss))
        self.assertEqual(self.optimizer.state[next(self.net.parameters())]['step'].item(), 1)
        self.assertTrue(any(not torch.equal(a, b.detach()) for a, b in zip(before, self.net.parameters())))
        self.assertTrue(all(torch.isfinite(p).all() for p in self.net.parameters()))

    def test_no_overflow_updates_once_without_retry(self):
        scaler = torch.amp.GradScaler('cpu', init_scale=2.**8)
        _, _, overflows = self.update(self.net, self.optimizer, scaler, self.run_batch())
        self.assertEqual((overflows, self.calls), (0, 1))

    def test_non_finite_gradient_without_scaler_still_stops(self):
        scaler = torch.amp.GradScaler('cpu', enabled=False)
        with self.assertRaisesRegex(RuntimeError, '배율 없는 경로'):
            self.update(self.net, self.optimizer, scaler, self.run_batch(INF_GRAD))
        self.assertEqual(self.optimizer.state, {})

    def test_non_finite_loss_still_stops(self):
        scaler = torch.amp.GradScaler('cpu', init_scale=2.**8)
        with self.assertRaisesRegex(RuntimeError, '비유한 손실'):
            self.update(self.net, self.optimizer, scaler, self.run_batch(float('inf')))

    def test_persistent_overflow_is_bounded(self):
        scaler = torch.amp.GradScaler('cpu', init_scale=2.**8)
        with self.assertRaisesRegex(RuntimeError, '넘었다'):
            self.update(self.net, self.optimizer, scaler, self.run_batch(INF_GRAD), max_retries=3)
        self.assertEqual(self.calls, 4)
        self.assertEqual(self.optimizer.state, {})


if __name__ == '__main__':
    unittest.main()
