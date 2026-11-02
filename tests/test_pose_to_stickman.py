"""포즈 → 스틱맨 SFA(2단계 인물 갈래): 관절점·파란점·ID 불변 조건."""
import collections
import os
import sys
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))


class PoseToStickman(unittest.TestCase):
    def test_structure(self):
        import pose_to_stickman as P
        import sfa_tokens as K
        rng = np.random.default_rng(0)
        base = np.array([[50, 20], [48, 18], [52, 18], [46, 19], [54, 19], [44, 30], [56, 30], [40, 40], [60, 40], [38, 50], [62, 50],
                         [46, 55], [54, 55], [45, 70], [55, 70], [44, 85], [56, 85]], float) * [8.54, 4.8]
        res = [dict(kp=np.c_[base + rng.normal(0, 2, base.shape), np.full(17, 0.9)].tolist()) for _ in range(10)]
        res[3]['kp'][9][2] = 0.05   # 낮은 신뢰 점은 보간
        xml, _ = P.build(dict(W=854, H=480, res=res), 0, 9)
        root = ET.fromstring(xml.split('\n', 1)[1])
        frs = root.findall('Frame')
        self.assertEqual(len(frs), 10)
        own, acs = collections.defaultdict(set), collections.defaultdict(set)
        for fr in frs:
            aos = fr.findall('AO')
            find = K.link_groups(aos, True)
            self.assertEqual(len({find(a.get('ID')) for a in aos}), 1)          # 스틱맨 하나 = 무리 하나
            flags = [int(p.get('Flags')) for p in fr.iter('AP')]
            self.assertEqual(flags.count(3), 1)                                    # 파란점 하나
            self.assertEqual(flags.count(33), 5)                                   # 관절점: 목·팔꿈치 2·무릎 2
            for a in aos:
                for p in a.findall('AP'):
                    own[p.get('ID')].add(a.get('ID'))
                    acs[p.get('ID')].add(frozenset(c.get('ConnPtId') for c in p.findall('AC')))
        self.assertTrue(all(len(v) == 1 for v in own.values()))
        self.assertTrue(all(len(v) == 1 for v in acs.values()))


if __name__ == '__main__':
    unittest.main()
