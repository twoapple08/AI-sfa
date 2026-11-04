import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_occlusion import bridge_occlusions, PARENTS


class TestOcclusion(unittest.TestCase):
    def pose(self, sign=1, size=100):
        p = {'pelvis': np.array([0., 0.])}
        for node, parent in PARENTS.items():
            p[node] = p[parent]+np.array([sign*size, 0.])
        return p

    def test_folded_detection_does_not_shrink_bones_during_occlusion(self):
        original = [{'red': self.pose()}, {'red': self.pose(size=.01)}, {'red': self.pose(-1, 200)}]
        out, report = bridge_occlusions(original, [10,11,12],
            [dict(actor='red', start=11, end=11, evidence='전경 기둥 가림')])
        for node, parent in PARENTS.items():
            self.assertAlmostEqual(np.linalg.norm(out[1]['red'][node]-out[1]['red'][parent]),150.)
        self.assertAlmostEqual(np.linalg.norm(original[1]['red']['neck']),.01)
        self.assertEqual(len(report),1)
        for i in [0,2]:
            for node in original[i]['red']:
                np.testing.assert_array_equal(original[i]['red'][node],out[i]['red'][node])

    def test_cut_crossing_and_missing_anchor_are_rejected(self):
        rows=[{'red': self.pose()} for _ in range(3)]
        event=dict(actor='red', start=11, end=11, evidence='가림')
        with self.assertRaises(ValueError):bridge_occlusions(rows,[10,11,12],[event],[12])
        rows[0]['red']=None
        with self.assertRaises(ValueError):bridge_occlusions(rows,[10,11,12],[event])

    def test_untagged_fast_motion_is_preserved(self):
        rows=[{'red': self.pose(size=s)} for s in [100,1,900]]
        out,_=bridge_occlusions(rows,[10,11,12],[])
        for a,b in zip(rows,out):
            for node in a['red']:np.testing.assert_array_equal(a['red'][node],b['red'][node])
