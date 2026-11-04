"""두 단계 좌표(coord2) 변환층·학습 연결 시험."""
import json
import math
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

try:
    import torch
    import cv2  # noqa: F401
except ImportError:  # pragma: no cover
    torch = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

FRAME = ('<Frame ID="1" Position="0" BackgroundColor="-1"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />'
         '<AO ID="2" TypeId="1" LayerId="0" DrawOrder="0" ObjectScale="1.0" Color="-16777216" ThicknessScale="2.0" GlowRadius="0" '
         'GlowThickness="0" GlowAlpha="0" GlowColor="0"><AP ID="3" Flags="9" Index="0" X="30.0" Y="40.0" />'
         '<AP ID="4" Flags="8" Index="1" X="{x}" Y="60.0" /></AO>'
         '<AO ID="5" TypeId="2" LayerId="0" DrawOrder="1" ObjectScale="1.0" Color="-65536" ThicknessScale="1.0" GlowRadius="0" '
         'GlowThickness="0" GlowAlpha="0" GlowColor="0"><AP ID="6" Flags="5" Index="0" X="50" Y="50" />'
         '<AP ID="7" Flags="5" Index="1" X="50" Y="30" /></AO></Frame>')


@unittest.skipIf(torch is None, 'torch/cv2 필요')
class TestCoord2(unittest.TestCase):
    def setUp(self):
        import seq_train as T
        import seq_coord2 as C2
        import sfa_tokens as K
        self.T, self.C2, self.K = T, C2, K

    def encoded(self, x='70.0'):
        K, T = self.K, self.T
        seq = T.seq_xml(0.5625)
        tok, _ = K.encode(seq, ET.fromstring(FRAME.format(x=x)))
        return np.array(tok), np.array(K.fields(tok))

    def test_round_trip_and_length(self):
        tok, fld = self.encoded()
        t2, f2 = self.C2.to_two(tok, fld)
        n_coord = int(((fld == self.K.FID['coord']) & (tok >= self.K.OFF)).sum())
        self.assertEqual(len(t2), len(tok) + n_coord)
        self.assertEqual(self.C2.merge(t2.tolist()), tok.tolist())
        self.assertTrue(((t2 >= self.C2.C0) & (t2 < self.C2.F0)).sum() == n_coord)

    def test_big_coordinates_are_left_alone(self):
        tok, fld = self.encoded(x='400.0')          # 화면 밖 좌표 → BIG + 세 자리
        self.assertIn(self.K.TOK['BIG'], tok.tolist())
        t2, f2 = self.C2.to_two(tok, fld)
        self.assertEqual(self.C2.merge(t2.tolist()), tok.tolist())

    def test_grammar2_accepts_converted_answer_exactly(self):
        T = self.T
        for x in ('70.0', '400.0'):
            tok, fld = self.encoded(x)
            t2, _ = self.C2.to_two(tok, fld)
            g = self.C2.grammar2()
            al = next(g)
            for i, t in enumerate(t2.tolist()):
                m = T.allowed_mask(al, 'cpu', self.C2.VOCAB2)
                self.assertFalse(math.isinf(float(m[t])), f'{i}번째 토큰 {t} 불허 {al[1:]}')
                try:
                    al = g.send(t)
                except StopIteration:
                    self.assertEqual(i, len(t2) - 1)
                    break
            else:
                self.fail('문법이 끝나지 않았다')

    def test_fine_range_respects_coarse_boundary(self):
        C2 = self.C2
        K = self.K
        lo, hi = 70, 200                               # 거친 칸 1..3, 경계 칸에서 세부 범위 제한

        def inner():
            yield (frozenset(), lo, hi, 'coord')

        orig = K.grammar
        K.grammar = inner
        try:
            g = C2.grammar2()
            al = next(g)
            self.assertEqual((al[1], al[2]), (C2._NC + 1, C2._NC + 3))
            al = g.send(C2.C0 + 1)
            self.assertEqual((al[1], al[2]), (C2._NF + 70 % 64, C2._NF + 63))
        finally:
            K.grammar = orig

    def test_loss_uses_exact_only_for_new_tokens(self):
        T, C2 = self.T, self.C2
        tok, fld = self.encoded()
        t2, f2 = C2.to_two(tok, fld)
        tgt = torch.from_numpy(t2)[None]
        f = torch.from_numpy(f2)[None]
        lg = torch.randn(1, len(t2), C2.VOCAB2)
        per, mask = T.token_loss(lg, tgt, f)
        exact = -torch.log_softmax(lg, -1).gather(-1, tgt[..., None])[..., 0]
        new = tgt >= self.K.VOCAB
        self.assertTrue(torch.allclose(per[new], exact[new]))

    def test_data_loader_converts_and_drops_too_long(self):
        T, K = self.T, self.K
        tok, fld = self.encoded()
        with tempfile.TemporaryDirectory() as d:
            img = np.full((2, 36, 64, 3), 255, np.uint8)
            np.savez(Path(d) / 'a.npz', tok=np.concatenate([tok, tok]), fld=np.concatenate([fld, fld]),
                     off=np.array([0, len(tok), 2 * len(tok)]), pos=np.array([0, 1]), img=img,
                     meta=json.dumps({'file': 'a', 'hwr': 0.5625}))
            plain = T.Data(d, 2048, 64, workers=1)
            two = T.Data(d, 2048, 64, workers=1, coord2=True)
            tight = T.Data(d, len(tok), 64, workers=1, coord2=True)
        self.assertEqual(len(plain), 2)
        self.assertEqual(len(two), 2)
        self.assertEqual(T.answer_tokens(two.tok[0]), plain.tok[0].tolist())
        self.assertEqual((len(tight), tight.coord2_dropped), (0, 2))

    def test_generate_returns_merged_tokens_that_decode(self):
        T, K = self.T, self.K
        torch.manual_seed(0)
        net = T.Net(64, 1, 2, 200, 'resnet18', pretrained=False, coord2=True).eval()
        img = torch.rand(3, 36, 64)
        toks, done = T.generate(net, img, 0.5625, maxlen=120)
        self.assertTrue(all(t < K.VOCAB for t in toks))
        K.decode(toks) if done else None
        self.assertLessEqual(len(toks), 120)


if __name__ == '__main__':
    unittest.main()
