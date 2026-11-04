import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_simple_parts import apply_parts
from stickman_body_detail import strip_and_check
from stickman_clip import person_aos
from stickman_scene import JOINTS


class TestSimpleParts(unittest.TestCase):
    def frame(self):
        p={n:np.array([100.,100.]) for n in JOINTS};p['head_t']=np.array([100.,70.])
        return ET.fromstring('<Frame>'+person_aos(0,0,p,lambda p:p/2,'blue')+'</Frame>')

    def test_fingers_and_sole_are_connected_lines_without_fills(self):
        before=self.frame()
        nodes={'wrist':[100,100],'palm':[110,100],'finger':[130,80],
               'ankle':[100,100],'toe':[125,100]}
        out,record=apply_parts(before,nodes,[['wrist','palm'],['palm','finger'],['ankle','toe']],
            'blue',0,0,200,200,0,visible_edges=[0,1])
        self.assertEqual(record['visible_lines'],2);self.assertEqual(record['added_fills'],[])
        added=[a for a in out.findall('AO') if int(a.get('ID')) in record['added_objects']]
        self.assertTrue(all(a.get('TypeId')=='1' for a in added))
        root=ET.Element('Sequence');root.append(out)
        restored=strip_and_check(root,[record]).find('Frame')
        self.assertEqual(ET.tostring(before),ET.tostring(restored))

    def test_invalid_observation_is_not_serialized(self):
        with self.assertRaises(ValueError):
            apply_parts(self.frame(),{'a':[float('nan'),0],'b':[1,1]},[['a','b']],
                'blue',0,0,200,200,0)

    def test_extension_does_not_mutate_the_input_rig(self):
        before=self.frame();original=ET.tostring(before)
        apply_parts(before,{'a':[100,100],'b':[120,100]},[['a','b']],
            'blue',0,0,200,200,0,hide_base=True)
        self.assertEqual(ET.tostring(before),original)

    def test_simple_line_does_not_turn_into_a_wide_silhouette(self):
        import sfa_render as R
        before=self.frame()
        out,_=apply_parts(before,{'a':[40,100],'b':[160,100]},[['a','b']],
            'blue',0,0,200,200,0,thickness=10,hide_base=True)
        root=ET.Element('Sequence',HeightWidthRatio='1',Thickness='100');root.append(out)
        saved=dict(R.PARAMS)
        try:
            R.PARAMS.update(pad=0.,thick_mul=.6)
            image=R.render_frame(root,out,200,200)
        finally:
            R.PARAMS.clear();R.PARAMS.update(saved)
        ys,xs=np.nonzero((image[:,:,2]>200)&(image[:,:,0]<80))
        self.assertGreater(len(ys),0)
        self.assertLessEqual(ys.max()-ys.min()+1,12)
        self.assertGreaterEqual(ys.max()-ys.min()+1,8)
