import sys
import tempfile
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_key_motion import keyed_medians, axis_from_keys, reject_duplicate_chains, rebase_arm
from stickman_fit_cache import cached_fit


class TestKeyMotion(unittest.TestCase):
    def test_single_drawing_has_one_scale_despite_input_scale_wobble(self):
        np.testing.assert_array_equal(keyed_medians([60, 90, 50, 100, 60], [(0,4)]), np.full(5,60.))

    def test_one_censored_key_does_not_disable_observed_coordinates_elsewhere(self):
        observed=np.array([10.,10.,40.,40.,90.,90.]);w=np.ones(6);w[2:4]=0
        fallback=np.array([200.,100.,1100.,1200.,400.,800.]);side=np.array([0,0,1,1,0,0])
        result,_=axis_from_keys(observed,w,fallback,[(0,1),(2,3),(4,5)],side,(-100,100,-100,1000),1)
        self.assertEqual(result[0],10);self.assertEqual(result[-1],90)
        self.assertGreater(result[2],900)

    def test_fully_unobserved_axis_preserves_existing_inference(self):
        fallback=np.arange(6.)
        result,_=axis_from_keys(np.zeros(6),np.zeros(6),fallback,[(0,1),(2,3),(4,5)])
        np.testing.assert_array_equal(result,fallback)

    def pairs(self):
        k=np.zeros((3,23,3));k[:,:,2]=5
        k[:,[5,11],:2]=[-5,0];k[:,[6,12],:2]=[5,0]
        k[:,[7,13],:2]=[-20,20];k[:,[9,15],:2]=[-30,40]
        k[:,[8,14],:2]=[20,20];k[:,[10,16],:2]=[30,40]
        return k,np.ones((3,23,2)),[(0,0),(1,1),(2,2)],np.full(3,100.)

    def test_duplicate_branch_is_unobserved_not_reinjected_from_bad_fallback(self):
        k,w,spans,scale=self.pairs();k[1,[14,16]]=k[1,[13,15]]
        clean,rejected,events=reject_duplicate_chains(k,w,spans,scale)
        self.assertTrue(rejected[1,14]);self.assertTrue(rejected[1,16])
        values,_=axis_from_keys(k[:,16,0],clean[:,16,0],k[:,16,0],spans,rejected=rejected[:,16])
        np.testing.assert_array_equal(values,[30.,30.,30.]);self.assertTrue(events)

    def test_real_crossing_and_wrist_contact_are_preserved(self):
        k,w,spans,scale=self.pairs();k[1,[13,14],:2]=[0,20];k[1,[15,16],:2]=[0,40]
        k[2,[13,14]]=k[0,[14,13]];k[2,[15,16]]=k[0,[16,15]]
        clean,rejected,_=reject_duplicate_chains(k,w,spans,scale)
        self.assertFalse(rejected.any());np.testing.assert_array_equal(clean,w)
        k,w,spans,scale=self.pairs();k[1,[9,10],:2]=[0,40]
        _,rejected,_=reject_duplicate_chains(k,w,spans,scale);self.assertFalse(rejected.any())

    def test_fast_observed_kick_is_not_clipped_or_shortened(self):
        values,_=axis_from_keys(np.array([0.,1400.,-300.]),np.ones(3),np.zeros(3),[(0,0),(1,1),(2,2)])
        np.testing.assert_array_equal(values,[0.,1400.,-300.])

    def test_center_hub_does_not_add_shoulder_width_to_bent_arm_length(self):
        hub, elbow, wrist = np.array([[0., 0.]]), np.array([[-70., 40.]]), np.array([[-40., 80.]])
        out, feasible = rebase_arm(hub, elbow, wrist, [50.], [50.])
        self.assertTrue(feasible[0])
        np.testing.assert_allclose(np.linalg.norm(out-hub,axis=1),50.)
        np.testing.assert_allclose(np.linalg.norm(wrist-out,axis=1),50.)
        np.testing.assert_array_equal(wrist,[[-40.,80.]])

    def test_projected_arm_lengths_can_change_with_view_scale(self):
        hub=np.zeros((2,2));elbow=np.array([[-70.,40.],[-28.,16.]]);wrist=np.array([[-40.,80.],[-16.,32.]])
        out,feasible=rebase_arm(hub,elbow,wrist,[50.,20.],[50.,20.])
        self.assertTrue(feasible.all())
        np.testing.assert_allclose(np.linalg.norm(out-hub,axis=1),[50.,20.])
        np.testing.assert_allclose(np.linalg.norm(wrist-out,axis=1),[50.,20.])

    def test_infeasible_rebase_does_not_pull_a_fast_wrist_back(self):
        hub=np.array([[0.,0.]]);elbow=np.array([[-80.,0.]]);wrist=np.array([[-120.,0.]])
        out,feasible=rebase_arm(hub,elbow,wrist,[40.],[40.])
        self.assertFalse(feasible[0]);np.testing.assert_array_equal(out,elbow)
        np.testing.assert_array_equal(wrist,[[-120.,0.]])

    def test_cache_is_input_pinned_and_does_not_share_mutable_arrays(self):
        calls=[]
        def compute():
            calls.append(1);return {'neck':np.ones((2,2))},np.ones(2),{'count':2},None,None
        with tempfile.TemporaryDirectory() as d:
            a,_,_,first=cached_fit(d,{'K':np.ones((2,2))},{'q':50},compute);a['neck'][0,0]=999
            b,_,_,second=cached_fit(d,{'K':np.ones((2,2))},{'q':50},compute)
            self.assertFalse(first['hit']);self.assertTrue(second['hit']);self.assertEqual(b['neck'][0,0],1)
            cached_fit(d,{'K':np.zeros((2,2))},{'q':50},compute)
            self.assertEqual(len(calls),2)


if __name__=='__main__': unittest.main()
