import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_tapered_parts import apply_tapered_parts,strip_tapered,joined_contour
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

    def test_joined_boundary_has_no_cap_or_tangent_break_at_the_knee(self):
        c=joined_contour([[0,0],[50,30],[90,110]],[9,7,5])
        self.assertEqual(len(c),12)
        np.testing.assert_allclose(c[0,2],c[1,0])
        np.testing.assert_allclose(c[0,2]-c[0,1],c[1,1]-c[1,0],atol=1e-9)
        np.testing.assert_allclose(c[6,2]-c[6,1],c[7,1]-c[7,0],atol=1e-9)
        for a,b in zip(c,np.roll(c,-1,axis=0)):np.testing.assert_array_equal(a[2],b[0])

    def test_a_whole_bent_leg_uses_one_fill_and_retains_the_control_network(self):
        pose={n:np.array([100.,100.]) for n in JOINTS};pose.update(head_t=np.array([100.,70.]),
            pelvis=np.array([30.,40.]),kne_r=np.array([100.,100.]),ank_r=np.array([160.,180.]))
        fr=ET.fromstring('<Frame>'+person_aos(0,0,pose,lambda p:p/2,'blue')+'</Frame>');before=ET.tostring(fr)
        specs=[dict(object_id=4560007,index=6,radii_px=[12,10]),dict(object_id=4560008,index=7,radii_px=[10,7])]
        out,record=apply_tapered_parts(fr,specs,'blue',0,0,200,200,0,joined_chains=True)
        self.assertEqual(len(record['added_fills']),1)
        self.assertEqual(record['curves'],12)
        self.assertEqual(len(record['added_objects']),15)
        reversed_out,reversed_record=apply_tapered_parts(fr,list(reversed(specs)),'blue',0,0,200,200,0,joined_chains=True)
        self.assertEqual(ET.tostring(reversed_out),ET.tostring(out))
        self.assertEqual(reversed_record,record)
        root=ET.Element('Sequence',HeightWidthRatio='1');root.append(out)
        self.assertEqual(ET.tostring(strip_tapered(root,[record]).find('Frame')),before)
        # 이전 각마디 면과 한줄기 면이 이웃 장에 있어도 객체 형식/점ID가 충돌하지 않는다.
        fr2=ET.fromstring('<Frame>'+person_aos(1,0,pose,lambda p:p/2,'blue')+'</Frame>')
        old_style,old_record=apply_tapered_parts(fr2,specs,'blue',0,1,200,200,0)
        root.append(old_style)
        restored=strip_tapered(root,[record,old_record])
        self.assertEqual(len(restored.findall('Frame')),2)
