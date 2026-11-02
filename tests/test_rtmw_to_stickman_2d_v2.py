import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import rtmw_to_stickman_2d_v2 as m  # noqa: E402

L = {'torso': 1.0, 'hip_span': 0.35, 'sho_span': 0.64, 'uarm_l': 0.67, 'farm_l': 0.57, 'uarm_r': 0.67, 'farm_r': 0.57,
     'thigh_l': 0.74, 'shin_l': 0.75, 'thigh_r': 0.74, 'shin_r': 0.75}


def kp_from(J, T):
    K = np.zeros((T, 17, 3))
    K[:, :, 2] = 5.0
    for n, j in m.OBS.items():
        K[:, j, :2] = J[n]
    return K


class TestV2(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.T = 12
        base = rng.uniform(-np.pi, np.pi, 11)
        base[1] = -np.pi / 2
        self.th = base + 0.05 * np.arange(self.T)[:, None]
        self.t = np.stack([400 + 3 * np.arange(self.T), 300 + 0 * np.arange(self.T)], 1).astype(float)
        self.S = np.full(self.T, 150.0)

    def test_midpoints_exact(self):
        J = m.forward(self.th, self.t, self.S, L)
        np.testing.assert_allclose((J['hip_l'] + J['hip_r']) / 2, J['pel'], atol=1e-9)
        np.testing.assert_allclose((J['sho_l'] + J['sho_r']) / 2, J['neck'], atol=1e-9)

    def test_recovers_clean_motion(self):
        J = m.forward(self.th, self.t, self.S, L)
        K = kp_from(J, self.T)
        Jf, X, rms, _, _ = m.fit_all(K, np.ones((self.T, 17)), L, self.S, lam=0.0)
        self.assertLess(max(rms), 1e-4)

    def test_lambda_reduces_jitter(self):
        J = m.forward(self.th, self.t, self.S, L)
        K = kp_from(J, self.T)
        K[:, 5:17, :2] += np.random.default_rng(2).normal(0, 6.0, (self.T, 12, 2))
        a0 = np.median(m.accel(m.fit_all(K, np.ones((self.T, 17)), L, self.S, lam=0.0)[0], self.S))
        a2 = np.median(m.accel(m.fit_all(K, np.ones((self.T, 17)), L, self.S, lam=2.0)[0], self.S))
        self.assertLess(a2, a0)

    def test_keypose_on_threes(self):
        # 3컷 작화 흉내: 3장마다 새 포즈, 그 사이 정지 → 그림 구간 3장씩 찾고, 출력은 장마다 움직인다(계단 없음)
        T = 15
        th = np.repeat(self.th[:5], 3, 0)
        t = np.repeat(self.t[:5], 3, 0)
        S = np.full(T, 150.0)
        J = m.forward(th, t, S, L)
        K = kp_from(J, T)
        W = np.ones((T, 17))
        tor = np.full(T, 150.0)
        self.assertEqual(m.drawing_segments(K, W, tor), [(0, 2), (3, 5), (6, 8), (9, 11), (12, 14)])
        Jk, rms, segs, _, _, _ = m.keypose_fit(K, W, L, S, tor, lam_key=0.0)
        # 키 시각(구간 가운데)에서는 원래 포즈와 같다
        for c in (4, 7, 10):
            self.assertLess(np.abs(Jk['wri_l'][c] - J['wri_l'][c]).max(), 1e-3)
        # 가운데 구간에서 장마다 움직인다
        step = np.linalg.norm(np.diff(Jk['wri_l'][1:14], axis=0), axis=1)
        self.assertTrue((step > 1e-6).all())

    def test_sfa_structure(self):
        J = m.with_head(m.forward(self.th, self.t, self.S, L), self.S, 0.17, 0.5)
        root = ET.fromstring(m.sfa_xml(J, 1152, 648, 63, 'x', np.full(self.T, 3.0)).split('?>', 1)[1])
        seen, ao_sets = set(), []
        for fr in root.findall('Frame'):
            pts = {ap.get('ID'): ap for ap in fr.iter('AP')}
            self.assertFalse(seen & set(pts))
            seen |= set(pts)
            aos = list(fr.iter('AO'))
            self.assertEqual(len(aos), 15)
            ao_sets.append([ao.get('ID') for ao in aos])
            self.assertEqual(sum(ap.get('Flags') == '3' for ap in pts.values()), 1)
            heads = [ao for ao in aos if ao.get('TypeId') == '2']
            self.assertEqual(heads[0].get('ThicknessScale'), '1.000')
            self.assertTrue(all(ao.get('ThicknessScale') == '3.000' for ao in aos if ao.get('TypeId') == '1'))
            adj = {}
            for pid, ap in pts.items():
                for ac in ap.findall('AC'):
                    q = ac.get('ConnPtId')
                    self.assertIn(pid, [c.get('ConnPtId') for c in pts[q].findall('AC')])
                    self.assertAlmostEqual(float(ap.get('X')), float(pts[q].get('X')), places=3)
                    self.assertAlmostEqual(float(ap.get('Y')), float(pts[q].get('Y')), places=3)
                    adj.setdefault(pid, set()).add(q)
            for ao in aos:
                ids = [ap.get('ID') for ap in ao.findall('AP')]
                for x in ids:
                    adj.setdefault(x, set()).update(i for i in ids if i != x)
            start = next(iter(pts))
            stack, comp = [start], {start}
            while stack:
                for q in adj.get(stack.pop(), ()):
                    if q not in comp:
                        comp.add(q)
                        stack.append(q)
            self.assertEqual(comp, set(pts))
        self.assertTrue(all(s == ao_sets[0] for s in ao_sets))


if __name__ == '__main__':
    unittest.main()
