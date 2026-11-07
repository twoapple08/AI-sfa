import copy,json,sys,unittest
from pathlib import Path
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import smear_density as S
import smear_thickness_variants as T

class SmearThicknessTests(unittest.TestCase):
    def setUp(self):
        p=json.loads(S.DEFAULT_PROFILE.read_text());points=[[10,10],[10,30],[12,10],[12,30],[14,10]]
        self.base=S.export_sfa(S.process(points,[852,480],p),[852,480],p)
        self.base.set('FrameCount','2');self.base.append(copy.deepcopy(self.base.find('Frame')))
        self.source=copy.deepcopy(self.base);self.refs={}
        for i,(f,src) in enumerate(zip(self.base.findall('Frame'),self.source.findall('Frame'))):
            f.find('AO').set('ThicknessScale',str(2+i*2));src.find('AO').set('ThicknessScale',str(2+i*2))
            E.SubElement(src,'LayerDef',ID='1',Name='smear',Visible='true',Locked='false')
            for k,color in [(0,'4294901760'),(1,'0')]:
                a=E.SubElement(src,'AO',ID=str(900000000+k),LayerId='1',TypeId='1',Color=color,ThicknessScale='.14')
                for j,(x,y) in enumerate([(15,10),(15,30)]):E.SubElement(a,'AP',ID=str(300000000+i*10000+k*2+j),X=str(x),Y=str(y),Index=str(j))
            self.refs[i,'900000000']=f.find('AO').get('ID')

    def test_actual_body_part_thickness_and_removal_preserve_geometry(self):
        out,counts=T.build(self.base,self.source,self.refs)
        for factor,root in out.items():
            for i,f in enumerate(root.findall('Frame')):
                fx=[a for a in f.findall('AO') if a.get('LayerId')=='1']
                self.assertEqual(len(fx),1)
                self.assertAlmostEqual(float(fx[0].get('ThicknessScale')),(2+i*2)*factor)
                original=self.source.findall('Frame')[i].findall('AO')[-2]
                self.assertEqual([p.attrib for p in fx[0].findall('AP')],[p.attrib for p in original.findall('AP')])
        self.assertTrue(all(r['removed_invisible_segments']==2 for r in counts))

    def test_explicit_neighbor_reference_uses_that_frame_thickness(self):
        self.refs[0,'900000000']=(1,self.base.findall('Frame')[1].find('AO').get('ID'))
        out,counts=T.build(self.base,self.source,self.refs)
        fx=next(a for a in out[1.].find('Frame').findall('AO') if a.get('LayerId')=='1')
        self.assertEqual(float(fx.get('ThicknessScale')),4.)

    def test_missing_anatomical_reference_fails(self):
        with self.assertRaises(ValueError):T.build(self.base,self.source,{})
