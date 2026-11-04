import sys
import unittest
from pathlib import Path

try:
    import torch  # noqa: F401
    import cv2  # noqa: F401
except ImportError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))


@unittest.skipIf(torch is None, 'torch/cv2 필요')
class TestCoordReprProbe(unittest.TestCase):
    def setUp(self):
        import coord_repr_probe as P
        self.P = P

    def test_both_representations_round_trip_to_same_quantized_lines(self):
        P = self.P
        lines = [(10.0, 20.0, 80.0, 70.0, 1), (33.3, 5.5, 90.1, 94.9, 2)]
        for mode in ('flat', 'two'):
            got = P.decode(P.encode(lines, mode), mode)
            self.assertEqual(len(got), 2)
            for g, t in zip(got, lines):
                for a, b in zip(g, t[:4]):
                    self.assertAlmostEqual(a, b, delta=100 / (P.Q - 1))

    def test_two_level_uses_same_total_resolution(self):
        self.assertEqual(self.P.COARSE * self.P.FINE, self.P.Q)

    def test_grammar_alternates_coarse_and_fine(self):
        P = self.P
        import math
        open_c = [i for i, v in enumerate(P.grammar_masks('two', 0)) if not math.isinf(v)]
        open_f = [i for i, v in enumerate(P.grammar_masks('two', 1)) if not math.isinf(v)]
        self.assertEqual((open_c[0], open_c[-1]), (P.SPECIAL, P.SPECIAL + P.COARSE - 1))
        self.assertEqual((open_f[0], open_f[-1]), (P.SPECIAL + P.COARSE, P.SPECIAL + P.COARSE + P.FINE - 1))
        ends = [i for i, v in enumerate(P.grammar_masks('flat', None)) if not math.isinf(v)]
        self.assertEqual(ends, [P.EOS, P.LINE])

    def test_endpoint_error_ignores_endpoint_order(self):
        e = self.P.endpoint_error_px((10, 10, 50, 50), (50, 50, 10, 10))
        self.assertEqual(e, 0.0)


if __name__ == '__main__':
    unittest.main()
