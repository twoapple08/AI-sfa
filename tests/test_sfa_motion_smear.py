import sys,unittest,copy
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sfa_motion_smear as M

class MotionSmearTests(unittest.TestCase):
    def sequence(self,mode='straight',camera=False):
        r=E.Element('Sequence',Name='probe')
        for i in range(5):
            f=E.SubElement(r,'Frame');scale=1+i*.1 if camera else 1;shift=np.array([i*4.,i*2.]) if camera else np.zeros(2)
            def obj(oid,pts,layer='0'):
                a=E.SubElement(f,'AO',ID=str(oid),TypeId='1',LayerId=layer,Color='-16777216',ThicknessScale='.3')
                for j,p in enumerate(pts):
                    q=np.array(p)*scale+shift
                    E.SubElement(a,'AP',ID=str(i*1000+len(f.findall('.//AP'))),Index=str(j),Flags='9',X=str(q[0]),Y=str(q[1]))
                return a
            obj(M.BASE+2,[(40,30),(40,50)])
            if mode=='arc':tip=np.array([40.,40.])+20*np.array([np.cos(-.6+i*.3),np.sin(-.6+i*.3)])
            elif mode=='length':tip=np.array([45.+i*4,40.])
            else:tip=np.array([50.+i*3,40.])
            obj(M.BASE+4,[tip,(40,40)])
            if i==2:
                a=obj(1300000000,[(43,40),(50,42)],'1');b=obj(1300000001,[(50,42),(44,41)],'1')
                E.SubElement(a.findall('AP')[1],'AC',ConnPtId=b.findall('AP')[0].get('ID'))
                E.SubElement(b.findall('AP')[0],'AC',ConnPtId=a.findall('AP')[1].get('ID'))
        return r

    def test_straight_is_not_curved(self):
        r=self.sequence();f=M.motion_features(r.findall('Frame'),2,0,4,(100,100))
        self.assertNotEqual(M.choose_family(f),'arc_fan')
        p=np.array([[0,0],[0,5],[3,-4],[4,6],[8,-7],[10,8.]])
        q,controls,gaps=M.deform(p,'straight_taper',f)
        self.assertTrue(all(c is None for c in controls));self.assertEqual(len(q),len(p))

    def test_real_rotation_uses_arc(self):
        r=self.sequence('arc');f=M.motion_features(r.findall('Frame'),2,0,4,(100,100))
        self.assertEqual(M.choose_family(f),'arc_fan')
        p=np.array([[0,0],[0,5],[3,-4],[4,6],[8,-7],[10,8.]])
        q,c,g=M.deform(p,'arc_fan',f);self.assertFalse(np.allclose(q,p));self.assertTrue(any(x is not None for x in c))

    def test_common_translation_and_scale_do_not_change_features(self):
        a=self.sequence('arc');b=self.sequence('arc',camera=True)
        x=M.motion_features(a.findall('Frame'),2,0,4,(100,100));y=M.motion_features(b.findall('Frame'),2,0,4,(100,100))
        for k in x:self.assertAlmostEqual(x[k],y[k],places=8)

    def test_projected_length_change_is_only_a_candidate(self):
        r=self.sequence('length');f=M.motion_features(r.findall('Frame'),2,0,4,(100,100))
        self.assertEqual(M.choose_family(f),'compact_burst')
        self.assertEqual(M.choose_family(None),'keep')

    def test_cut_like_discontinuity_is_rejected(self):
        r=self.sequence('arc')
        for i,frame in enumerate(r.findall('Frame')):
            if i==2:continue
            for p in frame.findall('.//AP'):p.set('X',str(float(p.get('X'))+1000))
        self.assertIsNone(M.motion_features(r.findall('Frame'),2,0,4,(100,100)))

    def test_missing_limb_keeps_source(self):
        r=self.sequence()
        for f in r.findall('Frame'):
            a=next(a for a in f.findall('AO') if a.get('ID')==str(M.BASE+4));a.set('Color','0')
        out,report=M.build(r,(100,100));self.assertEqual(report['changed_effect_frames'],0)
        for a,b in zip(r.findall('Frame'),out.findall('Frame')):self.assertEqual(E.tostring(a),E.tostring(b))

    def test_export_preserves_body_and_connections(self):
        r=self.sequence('arc');out,report=M.build(r,(100,100));self.assertTrue(report['body_and_fills_identical'])
        for old,new in zip(r.findall('Frame'),out.findall('Frame')):
            self.assertEqual([E.tostring(a) for a in old.findall('AO') if a.get('LayerId')=='0'],[E.tostring(a) for a in new.findall('AO') if a.get('LayerId')=='0'])
            pts={p.get('ID'):p for p in new.findall('.//AP')}
            self.assertEqual(len(pts),len(new.findall('.//AP')))
            for a in new.findall('AO'):
                if int(a.get('ID'))<1400000000:continue
                for p in a.findall('AP'):
                    for c in p.findall('AC'):
                        q=pts[c.get('ConnPtId')];self.assertEqual(p.get('X'),q.get('X'));self.assertEqual(p.get('Y'),q.get('Y'))
                        self.assertIn(p.get('ID'),[x.get('ConnPtId') for x in q.findall('AC')])

if __name__=='__main__':unittest.main()
