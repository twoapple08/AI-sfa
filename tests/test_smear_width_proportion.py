import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from smear_width_proportion import scale_width

class SmearWidthProportionTests(unittest.TestCase):
    def test_thicker_body_changes_width_only_and_preserves_irregularity(self):
        points=np.array([[0,-4],[1,4],[3,-2],[6,3],[10,-4]],float);axis=[[0,0],[10,0]]
        a,ra=scale_width(points,axis,1.,1152)
        b,rb=scale_width(points,axis,2.,1152)
        np.testing.assert_array_equal(a[:,0],points[:,0])
        np.testing.assert_allclose(b[:,1],2*a[:,1])
        np.testing.assert_allclose(a[:,1]/np.ptp(a[:,1]),points[:,1]/np.ptp(points[:,1]))
        self.assertAlmostEqual(np.ptp(a[:,1])/ra['body_stroke_width_px'],8.)

    def test_uniform_canvas_resize_and_rotation_keep_relative_result(self):
        points=np.array([[0,-4],[1,4],[3,-2],[6,3],[10,-4]],float);axis=np.array([[0,0],[10,0]],float)
        a,_=scale_width(points,axis,2.,1152)
        b,_=scale_width(points*2,axis*2,2.,2304);np.testing.assert_allclose(b,2*a)
        angle=.71;q=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        c,_=scale_width(points@q.T,axis@q.T,2.,1152);np.testing.assert_allclose(c,a@q.T,atol=1e-10)

    def test_degenerate_width_and_invalid_thickness_fail(self):
        with self.assertRaises(ValueError):scale_width([[0,0],[10,0]],[[0,0],[10,0]],1.,1152)
        with self.assertRaises(ValueError):scale_width([[0,1],[10,0]],[[0,0],[10,0]],0.,1152)
