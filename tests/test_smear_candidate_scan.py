import sys,unittest
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from smear_candidate_scan import scan

class CandidateScanTests(unittest.TestCase):
    def setUp(self):self.empty=np.full((200,1152,3),220,np.uint8)
    def test_repeated_teeth_are_found_even_on_a_held_drawing(self):
        image=self.empty.copy();pts=[]
        for x in range(100,400,6):pts.append((x,45 if (x//6)%2 else 75))
        pts.extend([(400,110),(100,110)]);cv2.fillPoly(image,[np.array(pts,np.int32)],(170,50,60))
        found=scan(image,image,image)
        self.assertTrue(any(r['actor']=='red' and r['support_pixels']>=4 for r in found))
        self.assertTrue(all(r['status']=='needs_review' for r in found))
        self.assertTrue(all(r['temporal_change']==0 for r in found))
    def test_moving_flat_background_is_not_a_smear(self):
        other=np.full_like(self.empty,20);self.assertEqual(scan(self.empty,other,other),[])
    def test_rejects_neighbor_shape_mismatch(self):
        with self.assertRaises(ValueError):scan(self.empty,self.empty[:50])
