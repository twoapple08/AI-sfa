import sys,unittest,json
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sfa_swept_smear as S
import smear_density as D

class SweptSmearTests(unittest.TestCase):
    def motion(self,angle=.8):
        tip=np.array([50.,0.]);old=S.rotation(tip,-angle)
        return dict(now=dict(hub=np.zeros(2),tip=tip),hub=np.zeros(2),tip=old,angle=angle,length=50.,old_length=50.,displacement=float(np.linalg.norm(tip-old)))

    def source(self):
        root=E.Element('Sequence',Name='synthetic',HeightWidthRatio='1')
        for i in range(4):
            frame=E.SubElement(root,'Frame');E.SubElement(frame,'LayerDef',ID='0');E.SubElement(frame,'LayerDef',ID='1')
            def obj(oid,xy,layer='0'):
                a=E.SubElement(frame,'AO',ID=str(oid),TypeId='1',Color='-16777216',LayerId=layer,ThicknessScale='.3',GlowAlpha='0')
                for j,p in enumerate(xy):E.SubElement(a,'AP',ID=str(i*1000+len(frame.findall('.//AP'))),Index=str(j),X=str(p[0]),Y=str(p[1]),Flags='9')
                return a
            obj(4560002,[(40,30),(40,50)])
            tip=np.array([40.,40.])+S.rotation(np.array([20.,0.]),i*.6)
            obj(4560004,[tip,(40,40)])
            if i>=2:
                a=obj(1300000000,[tip,tip+[2,1]],'1');b=obj(1300000001,[tip+[2,1],tip+[0,2]],'1')
                E.SubElement(a.findall('AP')[1],'AC',ConnPtId=b.findall('AP')[0].get('ID'))
                E.SubElement(b.findall('AP')[0],'AC',ConnPtId=a.findall('AP')[1].get('ID'))
        return root

    def test_rotation_uses_real_swept_sector(self):
        m=self.motion();family,base,arcs=S.sweep_geometry(m)
        self.assertEqual(family,'radial_sweep');self.assertEqual(len(arcs),3)
        np.testing.assert_allclose(base[-2],m['now']['tip'])
        self.assertTrue((base[:-1,1]<0).any())
        # 고정된 팔꿈치 회전은 안쪽 경계보다 바깥 경계의 이동이 크다.
        self.assertGreater(np.linalg.norm(base[-2]-base[1]),np.linalg.norm(base[-3]-base[0]))

    def test_straight_motion_has_no_decorative_curves(self):
        m=self.motion(0);m['tip']=m['tip']+np.array([0.,-15.]);m['hub']=np.array([0.,-15.]);m['displacement']=15.
        family,base,arcs=S.sweep_geometry(m)
        self.assertEqual(family,'translation_blade');self.assertEqual(arcs,[])
        self.assertGreater(np.ptp(base[:,1]),5)

    def test_mirrored_rotation_mirrors_geometry(self):
        a=S.sweep_geometry(self.motion(.8));b=S.sweep_geometry(self.motion(-.8))
        np.testing.assert_allclose(a[1]*[1,-1],b[1]);np.testing.assert_allclose(np.array(a[2])*[1,-1],b[2])

    def test_detached_effect_stays_at_source_region(self):
        m=self.motion();family,base,arcs=S.sweep_geometry(m,True,np.array([300.,300.]),30.)
        self.assertEqual(family,'detached_ribbon');self.assertLess(np.linalg.norm(base.mean(0)-[300,300]),15);self.assertEqual(arcs,[])

    def test_density_uses_original_gaps_and_preserves_base(self):
        _,base,_=S.sweep_geometry(self.motion(1.))
        p=json.loads(S.PROFILE.read_text());r=D.process(base,(1152,648),p)
        np.testing.assert_array_equal(np.array(r['points_px'])[r['fixed_mask']],base)
        self.assertGreater(r['added_pairs'],0)
        for interval in r['intervals']:
            scale=min(1.,min(interval['turn_distances_px'])/(4.8*1152/852))
            for bounds in interval['effective_depth_bounds']:np.testing.assert_allclose(bounds,np.array([.12,.26])*scale)

    def test_export_preserves_body_and_valid_topology(self):
        source=self.source();out,report=S.build(source,canvas=(100,100));self.assertEqual(report['changed_effects'],2);kinds={}
        for a,b in zip(source.findall('Frame'),out.findall('Frame')):
            self.assertEqual([E.tostring(x) for x in a if x.get('LayerId')!='1'],[E.tostring(x) for x in b if x.get('LayerId')!='1'])
            points={p.get('ID'):p for p in b.findall('.//AP')};self.assertEqual(len(points),len(b.findall('.//AP')))
            for obj in b.findall('AO'):
                if not 1420000000<=int(obj.get('ID'))<1500000000:continue
                self.assertEqual(kinds.setdefault(obj.get('ID'),obj.get('TypeId')),obj.get('TypeId'))
                for p in obj.findall('AP'):
                    for ac in p.findall('AC'):
                        q=points[ac.get('ConnPtId')];self.assertEqual((p.get('X'),p.get('Y')),(q.get('X'),q.get('Y')))
                        self.assertIn(p.get('ID'),[c.get('ConnPtId') for c in q.findall('AC')])

    def test_no_previous_motion_keeps_source(self):
        source=self.source()
        for f in source.findall('Frame'):
            a=next(a for a in f.findall('AO') if a.get('ID')=='4560004')
            for p,xy in zip(a.findall('AP'),[(60,40),(40,40)]):p.set('X',str(xy[0]));p.set('Y',str(xy[1]))
        out,report=S.build(source,canvas=(100,100));self.assertEqual(report['changed_effects'],0)
        self.assertEqual([E.tostring(f) for f in source.findall('Frame')],[E.tostring(f) for f in out.findall('Frame')])

if __name__=='__main__':unittest.main()
