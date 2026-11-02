import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import rtmw_to_stickman_2d as m  # noqa: E402


def fake_kp(J):
    k = np.zeros((17, 3))
    k[:, 2] = 5.0
    for n, j in m.OBS.items():
        k[j, :2] = J[n]
    return k


class TestFit(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.L = np.array([0.2, 0.2, 1.0, 0.3, 0.3, 0.7, 0.6, 0.7, 0.6, 0.85, 0.8, 0.85, 0.8])
        self.th = rng.uniform(-np.pi, np.pi, 13)
        self.th[2] = -np.pi / 2

    def test_recovers_pose_when_rig_matches(self):
        # 관측이 리그로 정확히 만들어졌으면 관절을 되찾는다. 단 골반·목은 '엉덩이·어깨 중점' 관측이라
        # 좌우 엉덩이(어깨) 각도가 중점과 맞아야 한다 → 중점이 골반·목에 오도록 대칭 각도로 만든다.
        th = self.th.copy()
        th[1] = th[0] + np.pi
        th[4] = th[3] + np.pi
        J = m.forward(th, [400.0, 300.0], 150.0, self.L)
        k = fake_kp(J)
        _, prior = m.raw_angles([k], [np.ones(17)])
        _, _, s, Jf, rms = m.fit_frame(k, np.ones(17), self.L, prior[0], s0=120.0)
        self.assertAlmostEqual(s, 150.0, places=3)
        self.assertLess(rms, 1e-6)
        for n in m.OBS:
            np.testing.assert_allclose(Jf[n], J[n], atol=1e-3)

    def test_unobserved_bone_follows_prior(self):
        th = self.th.copy()
        th[1] = th[0] + np.pi
        th[4] = th[3] + np.pi
        J = m.forward(th, [400.0, 300.0], 150.0, self.L)
        k = fake_kp(J)
        w = np.ones(17)
        w[m.RWRI] = 0
        prior = th.copy()
        prior[m.BONES.index(('elb_r', 'wri_r'))] = 0.3
        out = m.fit_frame(k, w, self.L, prior, s_fixed=150.0)
        self.assertAlmostEqual(float(np.angle(np.exp(1j * (out[0][8] - 0.3)))), 0.0, places=6)

    def test_symmetric_lengths(self):
        J = m.forward(self.th, [400.0, 300.0], 150.0, self.L * np.r_[1, 1, 1, 1, 1, 0.5, 0.5, 1, 1, 1, 1, 0.7, 0.7])
        K = [fake_kp(J)]
        L, _ = m.calib_lengths(K, [np.ones(17)], q=90, symmetric=True)
        for (a, b), i in zip(m.BONES, range(13)):
            if b.endswith('_l'):
                j = m.BONES.index((a[:-2] + '_r' if a.endswith('_l') else a, b[:-2] + '_r'))
                self.assertEqual(L[i], L[j])


class TestSfa(unittest.TestCase):
    def test_ids_connections_root(self):
        L = np.array([0.2, 0.2, 1.0, 0.3, 0.3, 0.7, 0.6, 0.7, 0.6, 0.85, 0.8, 0.85, 0.8])
        Js = [m.with_head(m.forward(np.linspace(0, 3, 13) + t, [500, 400], 100, L), L) for t in range(3)]
        root = ET.fromstring(m.sfa_xml(Js, 1152, 648, 63, 'x').split('?>', 1)[1])
        frames = root.findall('Frame')
        self.assertEqual(len(frames), 3)
        seen_pts = set()
        ao_sets = []
        for fr in frames:
            pts = {ap.get('ID'): ap for ap in fr.iter('AP')}
            self.assertFalse(seen_pts & set(pts), '점 ID는 장마다 새로')
            seen_pts |= set(pts)
            ao_sets.append(sorted(ao.get('ID') for ao in fr.iter('AO')))
            self.assertEqual(sum(ap.get('Flags') == '3' for ap in pts.values()), 1, '파란점(뿌리) 하나')
            adj = {}
            for pid, ap in pts.items():
                for ac in ap.findall('AC'):
                    q = ac.get('ConnPtId')
                    self.assertIn(q, pts)
                    self.assertIn(pid, [c.get('ConnPtId') for c in pts[q].findall('AC')], '연결은 양방향')
                    self.assertAlmostEqual(float(ap.get('X')), float(pts[q].get('X')), places=3)
                    self.assertAlmostEqual(float(ap.get('Y')), float(pts[q].get('Y')), places=3)
                    adj.setdefault(pid, set()).add(q)
            # 조각 안 두 점 + 연결로 한 무리인지
            owner = {}
            for ao in fr.iter('AO'):
                ids = [ap.get('ID') for ap in ao.findall('AP')]
                for a in ids:
                    adj.setdefault(a, set()).update(i for i in ids if i != a)
                    owner[a] = ao.get('ID')
            start = next(iter(pts))
            stack, comp = [start], {start}
            while stack:
                for q in adj.get(stack.pop(), ()):
                    if q not in comp:
                        comp.add(q)
                        stack.append(q)
            self.assertEqual(comp, set(pts), '모든 조각이 한 무리')
        self.assertTrue(all(s == ao_sets[0] for s in ao_sets), '오브젝트 ID는 장끼리 유지')


if __name__ == '__main__':
    unittest.main()
