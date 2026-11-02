"""포즈 → 앱 기본 스틱맨 SFA(2단계 인물 갈래): 앱 틀과 같은 구조·길이 비율·ID 불변 조건."""
import collections
import math
import os
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def topo(frame):
    """오브젝트 순서대로 (TypeId, [(Flags, 연결 상대의 (오브젝트 순번, Index))])."""
    aos = frame.findall('AO')
    where = {p.get('ID'): (k, p.get('Index')) for k, a in enumerate(aos) for p in a.findall('AP')}
    return [(a.get('TypeId'), [(p.get('Flags'), sorted(where[c.get('ConnPtId')] for c in p.findall('AC'))) for p in a.findall('AP')])
            for a in aos]


def seg_len(frame, r):
    return [math.hypot(float(p1.get('X')) - float(p0.get('X')), (float(p1.get('Y')) - float(p0.get('Y'))) * r)
            for p0, p1 in (a.findall('AP') for a in frame.findall('AO'))]


class PoseToStickman(unittest.TestCase):
    def test_structure(self):
        import pose_to_stickman as P
        import sfa_tokens as K
        z = zipfile.ZipFile(os.path.join(ROOT, 'data', 'app_templates', 'stickman_default.sfa'))
        app = ET.fromstring(z.read(z.namelist()[0])).find('Frame')
        rng = np.random.default_rng(0)
        base = np.array([[50, 20], [48, 18], [52, 18], [46, 19], [54, 19], [44, 30], [56, 30], [40, 40], [60, 40], [38, 50], [62, 50],
                         [46, 55], [54, 55], [45, 70], [55, 70], [44, 85], [56, 85]], float) * [8.54, 4.8]
        res = [dict(kp=np.c_[base + rng.normal(0, 2, base.shape), np.full(17, 0.9)].tolist()) for _ in range(10)]
        res[3]['kp'][9][2] = 0.05   # 낮은 신뢰 점은 보간
        xml, _ = P.build(dict(W=854, H=480, res=res), 0, 9)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8" ?><Sequence') and '\n' not in xml)  # 앱 형식
        root = ET.fromstring(xml.encode())
        r = float(root.get('HeightWidthRatio'))
        frs = root.findall('Frame')
        self.assertEqual(len(frs), 10)
        app_len = np.array(seg_len(app, 0.5625))
        own, acs = collections.defaultdict(set), collections.defaultdict(set)
        for fr in frs:
            self.assertEqual(topo(fr), topo(app))                                  # 앱 기본 스틱맨과 같은 구조
            L = np.array(seg_len(fr, r))
            np.testing.assert_allclose(L / L.sum(), app_len / app_len.sum(), atol=1e-3)  # 길이 비율 고정
            aos = fr.findall('AO')
            find = K.link_groups(aos, True)
            self.assertEqual(len({find(a.get('ID')) for a in aos}), 1)          # 스틱맨 하나 = 무리 하나
            for a in aos:
                for p in a.findall('AP'):
                    own[p.get('ID')].add(a.get('ID'))
                    acs[p.get('ID')].add(frozenset(c.get('ConnPtId') for c in p.findall('AC')))
        self.assertTrue(all(len(v) == 1 for v in own.values()))
        self.assertTrue(all(len(v) == 1 for v in acs.values()))
        lens = np.array([seg_len(f, r) for f in frs])
        np.testing.assert_allclose(lens, lens[:1].repeat(len(frs), 0), atol=2e-3)       # 기본: 조각 길이가 모든 장에서 같음(앱 파일처럼)
        fr0 = {f.get('ID') for f in frs}
        self.assertFalse(set(own) & {i for v in own.values() for i in v} or fr0 & set(own))  # 장·오브젝트·점 ID 범위가 겹치지 않음
        # 원근 단축: 짧게 보이는 팔(화면 쪽)은 짧게 그린다
        res2 = [dict(kp=[list(k) for k in r['kp']]) for r in res]
        for q in res2:
            q['kp'][7][:2] = [(a + b) / 2 for a, b in zip(q['kp'][5][:2], q['kp'][7][:2])]   # 왼 위팔을 절반으로
        xml2, _ = P.build(dict(W=854, H=480, res=res2), 0, 9, fore=True, const=False)
        f2 = ET.fromstring(xml2.encode()).findall('Frame')
        full = np.array(seg_len(frs[5], r))
        short = np.array(seg_len(f2[5], r))
        k = [i for i, (oid, _, pts) in enumerate(P.BODY) if pts[0][1] == 'elb_l'][0]
        self.assertLess(short[k] / short[1], 0.75 * full[k] / full[1])                       # 위팔/몸통 비가 줄어듦


if __name__ == '__main__':
    unittest.main()
