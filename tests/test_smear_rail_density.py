import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from smear_rail_fit import densify_chain

class DensityTests(unittest.TestCase):
    def test_only_wide_interval_gets_new_round_trips(self):
        p=np.array([[0,0],[0,20],[1,0],[1,20],[9,0],[9,20],[10,0]],float)
        q,records=densify_chain(p,3,.2,1)
        self.assertEqual([r['divisions'] for r in records],[1,3])
        np.testing.assert_array_equal(q[:4],p[:4])
        self.assertEqual(len(q)-1,10)
        # 기존 모든 꼭짓점과 순서가 보존된다.
        cursor=0
        for vertex in p:
            while cursor<len(q) and not np.array_equal(q[cursor],vertex):cursor+=1
            self.assertLess(cursor,len(q));cursor+=1
        self.assertTrue(np.all((q[:,0]>=0)&(q[:,0]<=10)))
        self.assertTrue(np.all(np.isin(q[:,1],[0,20])))

    def test_already_dense_chain_is_identical(self):
        p=np.array([[0,0],[0,20],[1,0],[1,20],[2,0]],float)
        q,_=densify_chain(p,3,.2,1)
        np.testing.assert_array_equal(q,p)

    def test_invalid_threshold_is_rejected(self):
        p=[[0,0],[0,10],[1,0],[1,10],[2,0]]
        with self.assertRaises(ValueError):densify_chain(p,1,.1,2)

class InsetTests(unittest.TestCase):
    def test_only_inserted_pairs_move_and_keep_their_midpoints(self):
        from smear_rail_fit import inset_added_turns
        p=np.array([[0,0],[0,20],[1,0],[1,20],[9,0],[9,20],[10,0]],float)
        dense,_=densify_chain(p,3,.2,1)
        inset,fixed=inset_added_turns(p,dense,.25)
        np.testing.assert_array_equal(inset[fixed],p)
        self.assertEqual(inset.shape,dense.shape)
        added=np.flatnonzero(~fixed).reshape(-1,2)
        for i,j in added:
            np.testing.assert_allclose((inset[i]+inset[j])/2,(dense[i]+dense[j])/2)
            self.assertAlmostEqual(np.linalg.norm(inset[j]-inset[i]),np.linalg.norm(dense[j]-dense[i])*.5)

    def test_zero_depth_and_bad_depth(self):
        from smear_rail_fit import inset_added_turns
        p=np.array([[0,0],[0,20],[1,0],[1,20],[2,0]],float)
        q,_=inset_added_turns(p,p,0)
        np.testing.assert_array_equal(q,p)
        with self.assertRaises(ValueError):inset_added_turns(p,p,.5)

class VaryTurnsTests(unittest.TestCase):
    def test_variable_spacing_and_depth_keep_all_fixed_vertices(self):
        from smear_rail_fit import vary_added_turns
        p=np.array([[0,0],[0,20],[1,0],[1,20],[13,0],[13,20],[14,0]],float)
        dense,_=densify_chain(p,3,.2,1)
        q,fixed=vary_added_turns(p,dense,[.5,1.4,.8,1.3],[.15,.35,.3,.4,.2,.1])
        np.testing.assert_array_equal(q[fixed],p)
        self.assertEqual(q.shape,dense.shape)
        pairs=q[~fixed].reshape(-1,2,2)
        self.assertGreater(np.ptp(np.linalg.norm(pairs[:,1]-pairs[:,0],axis=1)),1)
        self.assertGreater(np.ptp(np.diff(pairs[:,0,0])),.1)
        self.assertTrue(np.all((q[:,0]>=0)&(q[:,0]<=14)&(q[:,1]>=0)&(q[:,1]<=20)))

    def test_bad_distribution_rejected(self):
        from smear_rail_fit import vary_added_turns
        p=np.array([[0,0],[0,20],[1,0],[1,20],[2,0]],float)
        with self.assertRaises(ValueError):vary_added_turns(p,p,[0],[.2])
        with self.assertRaises(ValueError):vary_added_turns(p,p,[1],[.5])
