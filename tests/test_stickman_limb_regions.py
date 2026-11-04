import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_limb_regions import regional_arm_tracks


class TestLimbRegions(unittest.TestCase):
    def test_duplicate_and_label_swap_do_not_erase_opposing_arm(self):
        k=np.zeros((3,23,3));k[:,:,2]=4
        k[:,[7,9],:2]=[[20,40],[10,20]];k[:,[8,10],:2]=[[80,40],[90,20]]
        k[1,[7,9]]=k[1,[8,10]]
        k[2,[7,9,8,10]]=k[2,[8,10,7,9]]
        tracks,report=regional_arm_tracks(k,np.ones((3,23)),np.ones(3,bool),[10,11,12],
            [(0,0),(1,1),(2,2)],'blue',100,[dict(side='r',x_range=[0,.5]),dict(side='l',x_range=[.5,1])])
        self.assertEqual(tracks[0]['keys']['11']['wri_r'],[10.,20.])
        self.assertEqual(report[0]['source_frames'],[10,12])
        self.assertEqual(tracks[1]['keys']['11']['wri_l'],[90.,20.])

    def test_unobserved_or_unsupported_points_cannot_seed_a_track(self):
        k=np.ones((2,23,3))*10
        for observed,support in [(np.zeros(2,bool),np.ones((2,23))),(np.ones(2,bool),np.zeros((2,23)))]:
            with self.assertRaises(ValueError):
                regional_arm_tracks(k,support,observed,[10,11],[(0,1)],'blue',100,[dict(side='l',x_range=[0,1])])
