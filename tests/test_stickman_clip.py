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


if __name__ == '__main__':
    unittest.main()
