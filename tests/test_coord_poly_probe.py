import math
import sys
import unittest
from pathlib import Path

import numpy as np

try:
    import torch
    import cv2  # noqa: F401
except ImportError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


@unittest.skipIf(torch is None, 'torch/cv2 필요')
class TestCoordPolyProbe(unittest.TestCase):
    def setUp(self):
        import coord_poly_probe as Q
        import coord_repr_probe as P
        self.Q, self.P = Q, P

    def test_round_trip_and_grammar_accepts_answer(self):
        Q, P = self.Q, self.P
        rng = np.random.default_rng(3)
        for mode in ('two', 'two_w', 'ptr', 'flat1k'):
            for _ in range(5):
                objs = Q.sample(rng)
                toks = Q.encode(objs, mode)
                self.assertLessEqual(len(toks), Q.MAXLEN)
                got = Q.decode(toks, mode)
                self.assertEqual([len(o) for o in got], [len(o[0]) for o in objs])
                tol = 100 / P.GH / P.PF + 1e-6 if mode == 'ptr' else 100 / (P.SINGLE.get(mode, P.Q) - 1) + 1e-6
                for g, (pts, _) in zip(got, objs):
                    for a, b in zip(g, pts):
                        self.assertLessEqual(max(abs(a[0] - b[0]), abs(a[1] - b[1])), tol)
                gr = Q.Grammar(mode)
                for t in toks[1:]:
                    self.assertFalse(math.isinf(float(gr.mask()[t])), (mode, t))
                    gr.push(t)

    def test_sample_has_shared_axis_neighbours(self):
        rng = np.random.default_rng(0)
        same = total = 0
        for _ in range(300):
            for pts, _ in self.Q.sample(rng):
                for a, b in zip(pts, pts[1:]):
                    total += 1
                    same += a[0] == b[0] or a[1] == b[1]
        self.assertGreater(same / total, 0.3)

    def test_metrics_run_on_untrained_model(self):
        Q, P = self.Q, self.P
        net = P.Net('two', maxlen=Q.MAXLEN)
        r = Q.copy_rate(net, 3, 1)
        self.assertTrue(0 <= r['copy'] <= 1 and r['n'] > 0)
        e = Q.evaluate(net, 2, 1)
        self.assertIn('median_px', e)


if __name__ == '__main__':
    unittest.main()
