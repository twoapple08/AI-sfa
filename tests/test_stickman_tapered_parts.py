import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_tapered_parts import apply_tapered_parts,strip_tapered
from stickman_simple_parts import apply_parts
from stickman_clip import person_aos
from stickman_scene import JOINTS


class TestTaperedParts(unittest.TestCase):
    def frame(self):
        pose={n:np.array([100.,100.]) for n in JOINTS};pose['head_t']=np.array([100.,70.])
        fr=ET.fromstring('<Frame>'+person_aos(0,0,pose,lambda p:p/2,'blue')+'</Frame>')
        return apply_parts(fr,{'a':[20,100],'b':[100,100],'c':[180,100]},
            [['a','b'],['b','c']],'blue',0,0,200,200,0,hide_base=True)[0]

    def test_near_width_is_a_filled_continuous_surface_and_can_be_removed(self):
        import sfa_render as R
        frame=self.frame();before=ET.tostring(frame)
        out,record=apply_tapered_parts(frame,[dict(object_id=95_000_000,index=0,radii_px=[30,20]),
            dict(object_id=95_000_001,index=1,radii_px=[20,10])],'blue',0,0,200,200,0)
        self.assertEqual(len(record['added_fills']),2)
        root=ET.Element('Sequence',HeightWidthRatio='1',Thickness='100');root.append(out)
        self.assertEqual(ET.tostring(strip_tapered(root,[record]).find('Frame')),before)
        saved=dict(R.PARAMS)
        try:
            R.PARAMS.update(pad=0.,thick_mul=.6);im=R.render_frame(root,out,200,200)
        finally:R.PARAMS.clear();R.PARAMS.update(saved)
        blue=(im[:,:,2]>200)&(im[:,:,0]<80)
        self.assertTrue(blue[90:111,95:106].all())
        self.assertGreater(blue[:,40].sum(),blue[:,160].sum())

    def test_invalid_width_does_not_create_a_surface(self):
        with self.assertRaises(ValueError):
            apply_tapered_parts(self.frame(),[dict(object_id=95_000_000,index=0,radii_px=[30,-1])],
                'blue',0,0,200,200,0)
