import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_smear_axis import measure_straight_limb


class TestSmearAxis(unittest.TestCase):
    def test_fragmented_smear_keeps_a_long_straight_axis(self):
        mask=np.zeros((100,240),bool);mask[40:60,20:200]=True
        mask[:,80:85]=False;mask[5,0]=True
        end,report=measure_straight_limb(mask,[210,50],[-1,0],20,80)
        self.assertLess(end[0],30);self.assertLess(abs(end[1]-50),2)
        self.assertLess(report['centerline_rms_px'],1)

    def test_no_visible_limb_is_rejected_instead_of_invented(self):
        with self.assertRaises(ValueError):
            measure_straight_limb(np.zeros((100,100),bool),[50,50],[-1,0],20,30)
