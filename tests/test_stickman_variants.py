import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import stickman_variants as sv  # noqa: E402
from pose_to_stickman import frame_xml  # noqa: E402


def fake(T=6, seed=0):
    rng = np.random.default_rng(seed)
    S = np.linspace(150, 100, T)
    pel = np.stack([500 + 5 * np.arange(T), 400 + 0 * np.arange(T)], 1).astype(float)
    J = {'pel': pel, 'neck': pel + [0, -1] * S[:, None]}
    for s, sg in (('l', 1), ('r', -1)):
        J[f'sho_{s}'] = J['neck'] + [sg * 0.3, 0] * S[:, None]
        J[f'hip_{s}'] = pel + [sg * 0.18, 0] * S[:, None]
        J[f'elb_{s}'] = J[f'sho_{s}'] + rng.normal(0, 0.1, (T, 2)) * S[:, None] + [0, 0.6] * S[:, None]
        J[f'wri_{s}'] = J[f'elb_{s}'] + [0, 0.5] * S[:, None]
        J[f'kne_{s}'] = J[f'hip_{s}'] + [0, 0.75] * S[:, None]
        J[f'ank_{s}'] = J[f'kne_{s}'] + [0, 0.75] * S[:, None]
    return J, S


class TestBasic(unittest.TestCase):
    def test_fixed_ratio_and_attachment(self):
        J, S = fake()
        B, info = sv.basic_joints(J, S)
        for s in ('l', 'r'):
            r = np.linalg.norm(B[f'elb_{s}'] - B['neck'], axis=1) / S
            np.testing.assert_allclose(r, info['ratios_torso_units']['elb'], rtol=1e-9)
            r = np.linalg.norm(B[f'kne_{s}'] - B['pelvis'], axis=1) / S
            np.testing.assert_allclose(r, info['ratios_torso_units']['kne'], rtol=1e-9)
            np.testing.assert_allclose(B[f'wri_{s}'] - B[f'elb_{s}'], J[f'wri_{s}'] - J[f'elb_{s}'])
        np.testing.assert_allclose(np.linalg.norm(B['head_t'] - B['neck'], axis=1) / S, sv.HEAD_TEMPLATE, rtol=1e-9)

    def test_ten_pieces_one_root(self):
        J, S = fake()
        B, _ = sv.basic_joints(J, S)
        to_pct = lambda p: (100 * p[0] / 1152, 100 * (p[1] - 63) / 648)  # noqa: E731
        ids = set()
        for n in range(len(S)):
            fr = ET.fromstring(frame_xml(n, {k: v[n] for k, v in B.items()}, to_pct))
            self.assertEqual(len(fr.findall('AO')), 10)
            pts = [ap.get('ID') for ap in fr.iter('AP')]
            self.assertFalse(ids & set(pts))
            ids |= set(pts)
            self.assertEqual(sum(ap.get('Flags') == '3' for ap in fr.iter('AP')), 1)


class TestCurve(unittest.TestCase):
    def test_torso_offset_measures_shift(self):
        # 세로 몸통(P 아래 → N 위), 영역 가운데가 오른쪽(+x)으로 10px 밀린 띠 → 오프셋 = ±10/100
        m = np.zeros((300, 300), np.uint8)
        m[100:200, 120:180] = 1
        off, w = sv.torso_offset(m, np.array([140.0, 200.0]), np.array([140.0, 100.0]))
        self.assertTrue(np.allclose(np.abs(off), 0.10, atol=0.011))
        self.assertTrue(np.allclose(w, 0.59, atol=0.02))

    def test_curve_frame(self):
        J, S = fake(T=1)
        B, _ = sv.basic_joints(J, S)
        to_pct = lambda p: (100 * p[0] / 1152, 100 * (p[1] - 63) / 648)  # noqa: E731
        fr = ET.fromstring(sv.curve_frame_xml(0, {k: v[0] for k, v in B.items()}, 0.1, to_pct))
        curves = [ao for ao in fr.findall('AO') if ao.get('TypeId') == '3']
        self.assertEqual(len(curves), 1)
        pts = curves[0].findall('AP')
        self.assertEqual([p.get('Flags') for p in pts], ['4', '5', '3'])
        self.assertEqual(pts[1].findall('AC'), [])
        # 조절점은 몸통 가운데에서 수직으로 2 × 0.1 × 몸통 길이
        P, N = B['pelvis'][0], B['neck'][0]
        c = np.array([float(pts[1].get('X')) * 1152 / 100, float(pts[1].get('Y')) * 648 / 100 + 63])
        self.assertAlmostEqual(np.linalg.norm(c - (P + N) / 2) / np.linalg.norm(N - P), 0.2, places=3)


if __name__ == '__main__':
    unittest.main()
