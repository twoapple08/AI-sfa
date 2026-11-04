"""격자 포인터 좌표(coord3) 변환층·학습 연결 시험."""
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
         '<AP ID="4" Flags="8" Index="1" X="{x}" Y="{y}" /></AO>'
         '<AO ID="5" TypeId="3" LayerId="0" DrawOrder="1" ObjectScale="1.0" Color="-65536" ThicknessScale="1.0" GlowRadius="0" '
         'GlowThickness="0" GlowAlpha="0" GlowColor="0"><AP ID="6" Flags="3" Index="0" X="10" Y="90" />'
         '<AP ID="7" Flags="5" Index="1" X="-20" Y="50" /><AP ID="8" Flags="9" Index="2" X="99.97" Y="0" /></AO></Frame>')


@unittest.skipIf(torch is None, 'torch/cv2 필요')
class TestCoord3(unittest.TestCase):
    def setUp(self):
        import seq_train as T
        import seq_coord3 as C3
        import sfa_tokens as K
        self.T, self.C3, self.K = T, C3, K

    def encoded(self, x='70.0', y='60.0'):
        seq = self.T.seq_xml(0.5625)
        tok, _ = self.K.encode(seq, ET.fromstring(FRAME.format(x=x, y=y)))
        return np.array(tok), np.array(self.K.fields(tok))

    def accept(self, t3):
        g = self.C3.grammar3(strict=True)
        al = next(g)
        for i, t in enumerate(t3):
            m = self.T.allowed_mask(al, 'cpu', self.C3.VOCAB3)
            self.assertFalse(math.isinf(float(m[t])), f'{i}번째 토큰 {t} 불허 {al[1:]}')
            try:
                al = g.send(int(t))
            except StopIteration:
                self.assertEqual(i, len(t3) - 1)
                return
        self.fail('문법이 끝나지 않았다')

    def test_round_trip_grammar_and_cells(self):
        C3, K = self.C3, self.K
        for x, y in (('70.0', '60.0'), ('400.0', '60.0'), ('70.0', '-300.0'), ('120.0', '50.0')):
            tok, fld = self.encoded(x, y)
            t3, f3 = C3.to_three(tok, fld)
            self.assertEqual(C3.merge(t3.tolist()), tok.tolist())
            self.accept(t3.tolist())
            self.assertEqual(len(t3), len(f3))
        tok, fld = self.encoded()
        t3, _ = C3.to_three(tok, fld)
        n_cell = int(((t3 >= C3.CELL0) & (t3 < C3.FX0)).sum())
        self.assertEqual(n_cell, 4)          # 화면 안 점 (30,40)(70,60)(10,90)(99.97,0). (-20,50)은 화면 밖 → coord2 C·F
        import seq_coord2 as C2
        self.assertEqual(int(((t3 >= C2.C0) & (t3 < C2.F0)).sum()), 2)

    def test_cell_boundaries_are_exact(self):
        C3 = self.C3
        self.assertEqual((C3.NCELL, C3.NFX), (3600, 50))
        for vx, vy in ((2000, 2000), (5999, 5999), (2049, 2088), (4321, 3456)):
            c = C3.cell_of(vx, vy)
            self.assertEqual(C3.value_of(*c), (vx, vy))
        self.assertIsNone(C3.cell_of(1999, 3000))
        self.assertIsNone(C3.cell_of(3000, 6000))

    def test_cache_matches_full_forward_with_pointer(self):
        T, C3 = self.T, self.C3
        torch.manual_seed(0)
        net = T.Net(64, 1, 2, 300, 'resnet18', pretrained=False, stride=8, grid=(45, 80), coord3=True).eval()
        tok, fld = self.encoded()
        t3, f3 = C3.to_three(tok, fld)
        img = torch.rand(1, 3, 36, 64)
        hwr = torch.tensor([0.5625])
        with torch.no_grad():
            full = net(img, torch.from_numpy(t3)[None], torch.from_numpy(f3)[None], hwr)[0]
            cache = T.Cache(net, net.memory(img, hwr))
            for i, (t, f) in enumerate(zip(t3.tolist(), f3.tolist())):
                lc = cache.step(t, f)
                self.assertLess(float((lc - full[i]).abs().max()), 1e-3, i)

    def test_generate_and_objective(self):
        T, C3, K = self.T, self.C3, self.K
        import seq_objective as O
        torch.manual_seed(0)
        net = T.Net(64, 1, 2, 300, 'resnet18', pretrained=False, stride=8, grid=(45, 80), coord3=True).eval()
        toks, done = T.generate(net, torch.rand(3, 36, 64), 0.5625, maxlen=150)
        self.assertTrue(all(t < K.VOCAB for t in toks))
        tok, fld = self.encoded()
        t3, f3 = C3.to_three(tok, fld)
        tt = torch.from_numpy(t3)[None]
        ff = torch.from_numpy(f3)[None]
        lg = torch.randn(1, len(t3) - 1, C3.VOCAB3, requires_grad=True)
        loss, parts = O.objective(lg, tt[:, 1:], ff[:, 1:], [t3], 'balanced-v1')
        self.assertTrue(torch.isfinite(loss) and float(parts['stop']) > 0)
        stop = O.metadata(tuple(int(v) for v in t3), True, True)[0]
        self.assertEqual(sum(s[-1] for s in stop), 1)

    def test_data_loader_coord3(self):
        T = self.T
        tok, fld = self.encoded()
        with tempfile.TemporaryDirectory() as d:
            np.savez(Path(d) / 'a.npz', tok=tok, fld=fld, off=np.array([0, len(tok)]), pos=np.array([0]),
                     img=np.full((1, 36, 64, 3), 255, np.uint8), meta=json.dumps({'file': 'a', 'hwr': 0.5625}))
            ds = T.Data(d, 2048, 64, workers=1, coord3=True)
        self.assertEqual(T.answer_tokens(ds.tok[0]), tok.tolist())


if __name__ == '__main__':
    unittest.main()
