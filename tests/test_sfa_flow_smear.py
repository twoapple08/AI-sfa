import sys,unittest,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sfa_flow_smear as F
import smear_density as D
import test_sfa_swept_smear as fixtures

class FlowSmearTests(unittest.TestCase):
    def motion(self,angle=.8):return fixtures.SweptSmearTests().motion(angle)

    def test_rotation_front_turns_face_local_tangent(self):
        m=self.motion();family,p,arcs=F.geometry(m)
        self.assertEqual(family,'flow_rotation');self.assertEqual(arcs,[])
        b=p[1::2]-(p[:-1:2]+p[2::2])/2;vel=F.local_motion(m,F.RADII)
        cosine=np.sum(b*vel,axis=1)/(np.linalg.norm(b,axis=1)*np.linalg.norm(vel,axis=1))
        self.assertTrue((cosine>.98).all())
        self.assertGreater(np.linalg.norm(b[-1]),np.linalg.norm(b[0]))

    def test_four_translation_directions(self):
        for direction in [[0,1],[0,-1],[1,0],[-1,0]]:
            m=self.motion(0);travel=np.array(direction,float)*12;m['hub']=-travel;m['tip']=m['now']['tip']-travel
            family,p,arcs=F.geometry(m);self.assertEqual(arcs,[])
            b=p[1::2]-(p[:-1:2]+p[2::2])/2
            self.assertTrue((b@travel>0).all())
            self.assertEqual(family,'flow_translation' if travel[0]==0 else 'flow_axial_candidate')

    def test_front_peaks_dominate_return_depth(self):
        m=self.motion();_,p,_=F.geometry(m);self.assertGreater(np.mean(p[1::2,1]),abs(np.mean(p[::2,1]))*2)

    def test_no_outline_arcs_even_for_large_rotation(self):
        for angle in [-1.4,-.8,.8,1.4]:self.assertEqual(F.geometry(self.motion(angle))[2],[])

    def test_mirrored_flow(self):
        a=F.geometry(self.motion(.8))[1];b=F.geometry(self.motion(-.8))[1]
        np.testing.assert_allclose(a*[1,-1],b)

    def test_density_keeps_major_vertices_and_all_front_directions(self):
        m=self.motion();_,p,_=F.geometry(m);d=D.process(p,(1152,648),json.loads(F.S.PROFILE.read_text()))
        np.testing.assert_array_equal(np.array(d['points_px'])[d['fixed_mask']],p)
        check=F.check_turns(m,d);self.assertTrue(check['passed']);self.assertEqual(check['backward_turns'],0)
        reversed_density=dict(d);reversed_density['points_px']=(np.array(d['points_px'])*[1,-1]).tolist()
        self.assertFalse(F.check_turns(m,reversed_density)['passed'])

    def test_export_has_no_curves_and_preserves_body(self):
        source=fixtures.SweptSmearTests().source();out,report=F.build(source,canvas=(100,100))
        self.assertEqual(report['changed_effects'],2);self.assertTrue(report['body_identical'])
        for e in report['effects']:
            if e['family']=='keep':continue
            self.assertTrue(e['direction_check']['passed']);self.assertEqual(e['curved_accents'],0)
        for a in out.findall('.//AO'):
            if 1420000000<=int(a.get('ID'))<1500000000:self.assertEqual(a.get('TypeId'),'1')

if __name__=='__main__':unittest.main()
