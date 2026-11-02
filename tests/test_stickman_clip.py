import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import stickman_clip as sc  # noqa: E402
from pose_to_stickman import BODY  # noqa: E402


class TestClipFrame(unittest.TestCase):
    def test_two_people_distinct_ids_and_roots(self):
        names = {nm for _, _, pts in BODY for _, nm, _, _ in pts}
        J = {nm: np.array([500.0, 300.0]) + np.random.default_rng(0).normal(0, 50, 2) for nm in names}
        to_pct = lambda p: (100 * p[0] / 1152, 100 * (p[1] - 63) / 648)  # noqa: E731
        ids_by_frame = []
        for n in range(2):
            xml = '<Frame>' + sc.person_aos(n, 0, J, to_pct, 'blue') + sc.person_aos(n, 1, J, to_pct, 'red') + '</Frame>'
            fr = ET.fromstring(xml)
            aos = fr.findall('AO')
            self.assertEqual(len(aos), 20)
            self.assertEqual(len({ao.get('ID') for ao in aos}), 20)
            self.assertEqual({ao.get('Color') for ao in aos[:10]}, {str(sc.LINE_COLOR['blue'])})
            self.assertEqual({ao.get('Color') for ao in aos[10:]}, {str(sc.LINE_COLOR['red'])})
            pts = [ap.get('ID') for ap in fr.iter('AP')]
            self.assertEqual(len(set(pts)), len(pts))
            self.assertEqual(sum(ap.get('Flags') == '3' for ap in fr.iter('AP')), 2)   # 인물마다 파란점 하나
            ids_by_frame.append(set(pts))
        self.assertFalse(ids_by_frame[0] & ids_by_frame[1])   # 점 ID는 장마다 새로


class TestBorder(unittest.TestCase):
    def test_border_and_chain(self):
        # 가까운 화면: 무릎이 화면 아래 끝(719)에 몰림 → 무릎·발목 모두 빠진다. 손목만 끝이면 손목만
        K = np.zeros((1, 23, 3))
        K[0, :, :2] = [500, 400]
        K[0, 5, :2], K[0, 6, :2] = [450, 330], [550, 330]
        K[0, 11, :2], K[0, 12, :2] = [470, 620], [530, 620]
        K[0, 13, :2], K[0, 15, :2] = [470, 718], [460, 690]     # 왼무릎 끝, 왼발목은 안쪽이지만 사슬로 빠짐
        K[0, 9, :2] = [3, 400]                                   # 왼손목만 왼쪽 끝
        bm = sc.border_mask(K, 1152, 720, 63)[0]
        self.assertTrue(bm[13] and bm[15])
        self.assertFalse(bm[14] or bm[16] or bm[11])
        self.assertTrue(bm[9])
        self.assertFalse(bm[7])


if __name__ == '__main__':
    unittest.main()
