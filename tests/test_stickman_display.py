import sys,copy,unittest,xml.etree.ElementTree as E
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_display import normalize_taper_widths,crop_upper_pose,apply_actor_order,restore_actor_order,shared_node_widths
from stickman_clip import person_aos,AO0


class TestDisplay(unittest.TestCase):
    def test_surface_and_line_use_same_scale_but_keep_depth_ratios_and_shared_nodes(self):
        specs=[dict(radii_px=[48.,32.]),dict(radii_px=[32.,24.])]
        small=normalize_taper_widths(specs,2.);large=normalize_taper_widths(specs,4.)
        np.testing.assert_allclose(np.median([x for s in small for x in s['radii_px']]),5.472)
        self.assertEqual(small[0]['radii_px'][1],small[1]['radii_px'][0])
        np.testing.assert_allclose(np.array([s['radii_px'] for s in large]),np.array([s['radii_px'] for s in small])*2)
        self.assertEqual(specs[0]['radii_px'],[48.,32.])
        self.assertAlmostEqual(small[0]['radii_px'][0]/small[1]['radii_px'][1],2.)

    def test_invalid_width_is_not_filled_by_a_constant(self):
        with self.assertRaises(ValueError):normalize_taper_widths([dict(radii_px=[0,50])],2.)
        with self.assertRaises(ValueError):normalize_taper_widths([],float('nan'))

    def test_shared_arm_width_uses_actual_ap_endpoint_order(self):
        out=shared_node_widths([dict(object_id=AO0+3,radii_px=[10,5]),dict(object_id=AO0+4,radii_px=[2,8])],0)
        self.assertEqual(out[0]['radii_px'],[9,5]);self.assertEqual(out[1]['radii_px'],[2,9])
        with self.assertRaises(ValueError):shared_node_widths([dict(object_id=AO0+3,radii_px=[0,5])],0)

    def test_explicit_upper_view_hides_false_legs_preserving_arms_head_and_direction(self):
        p=dict(neck=np.array([10.,10.]),pelvis=np.array([30.,80.]),head_t=np.array([10.,0.]),wri_l=np.array([20.,30.]))
        q=crop_upper_pose(p,100)
        self.assertEqual(q['_visible_segments'],[1,2,3,4,5,6])
        self.assertGreater(q['pelvis'][1],100)
        np.testing.assert_array_equal(q['wri_l'],p['wri_l'])
        np.testing.assert_array_equal(q['head_t'],p['head_t'])
        self.assertEqual(p['pelvis'][1],80)

    def example(self):
        root=E.Element('Sequence',HeightWidthRatio='1',FrameCount='1')
        p={n:np.array([50.,50.]) for n in ['neck','pelvis','head_t','head_b','elb_l','elb_r','wri_l','wri_r','kne_l','kne_r','ank_l','ank_r']}
        p.update(head_t=np.array([10.,-50.]),head_b=np.array([10.,-30.]),neck=np.array([10.,-30.]),pelvis=np.array([50.,90.]))
        fr=E.SubElement(root,'Frame',Position='0')
        for slot,c in enumerate(['blue','red']):fr.extend(E.fromstring('<Frame>'+person_aos(0,slot,p,lambda v:v,c)+'</Frame>'))
        return root

    def test_actor_foreground_changes_both_stored_order_and_physical_order_and_restores_exactly(self):
        original=self.example();out,records=apply_actor_order(original,[dict(start=0,end=0,back_to_front=['red','blue'])],0)
        a={int(n.get('ID')):n for n in out.iter('AO')}
        self.assertGreater(int(a[AO0+1].get('DrawOrder')),int(a[AO0+101].get('DrawOrder')))
        self.assertEqual(out.find('Frame').findall('AO')[-1].get('ID'),str(AO0+1))
        self.assertEqual(E.tostring(restore_actor_order(out,records)),E.tostring(original))
        bad=copy.deepcopy(out);bad.find('Frame/AO').set('DrawOrder','1')
        with self.assertRaises(ValueError):restore_actor_order(bad,records)
        bad=copy.deepcopy(out);fr=bad.find('Frame');first=fr[0];fr.remove(first);fr.append(first)
        with self.assertRaises(ValueError):restore_actor_order(bad,records)

    def test_actor_order_rejects_duplicate_events(self):
        event=dict(start=0,end=0,back_to_front=['red','blue'])
        with self.assertRaises(ValueError):apply_actor_order(self.example(),[event,event],0)

    def test_actual_renderer_places_blue_in_front_after_plan(self):
        import sfa_render as R
        root=self.example();out,_=apply_actor_order(root,[dict(start=0,end=0,back_to_front=['red','blue'])],0)
        old=R.render_frame(root,root.find('Frame'),100,100)[60,40]
        new=R.render_frame(out,out.find('Frame'),100,100)[60,40]
        self.assertGreater(int(old[0]),int(old[2]))
        self.assertGreater(int(new[2]),int(new[0]))

if __name__=='__main__':unittest.main()
