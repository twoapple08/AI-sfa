import copy,json,sys,unittest
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import smear_density as S
import smear_clip_variants as V

class SmearClipVariantsTests(unittest.TestCase):
    def setUp(self):
        self.profile=json.loads((S.ROOT/'profiles/smear_density_v1_1_reference.json').read_text())
        self.points=[[100,100],[100,140],[112,100],[112,140],[124,100]]
        root=S.export_sfa(S.process(self.points,[852,480],self.profile),[852,480],self.profile)
        root.set('FrameCount','3');first=root.find('Frame')
        for i in [1,2]:
            f=copy.deepcopy(first);f.set('Position',str(i));f.set('ID',str(9000+i))
            for p in f.findall('.//AP'):
                p.set('ID',str(int(p.get('ID'))+10000*i))
                for c in p.findall('AC'):c.set('ConnPtId',str(int(c.get('ConnPtId'))+10000*i))
            root.append(f)
        self.base=root
        self.doc=dict(schema='sfa-smear-clip-input/1',canvas=[852,480],frame_count=3,events=[dict(id='probe',color=0xffff0000,frames=[dict(frame_index=i,points_px=self.points,axis_px=[[100,120],[124,120]]) for i in [0,1]])])

    def test_body_is_exact_and_only_transverse_component_changes(self):
        outputs,audit=V.build(self.base,self.doc,self.profile)
        a,b=(outputs[k].findall('Frame') for k in ['기본폭','좁힌폭'])
        for i,f in enumerate(self.base.findall('Frame')):
            for out in [a[i],b[i]]:self.assertEqual([E.tostring(c) for c in f],[E.tostring(c) for c in list(out)[:len(f)]])
        self.assertEqual(E.tostring(a[2]),E.tostring(self.base.findall('Frame')[2]))
        sa=[p for ao in a[0].findall('AO') if ao.get('LayerId')=='1' for p in ao.findall('AP')]
        sb=[p for ao in b[0].findall('AO') if ao.get('LayerId')=='1' for p in ao.findall('AP')]
        self.assertGreater(len(sa),0);self.assertEqual(len(sa),len(sb))
        for p,q in zip(sa,sb):
            self.assertEqual(p.get('X'),q.get('X'))
            ya=float(p.get('Y'))*4.8;yb=float(q.get('Y'))*4.8
            self.assertAlmostEqual(yb-120,.55*(ya-120),places=5)

    def test_capacity_retains_object_ids_for_changing_counts(self):
        self.doc['events'][0]['frames'][1]['points_px']=[[100,100],[100,140],[105,100],[105,140],[110,100]]
        outputs,audit=V.build(self.base,self.doc,self.profile)
        frames=outputs['기본폭'].findall('Frame')
        groups=[[a for a in f.findall('AO') if a.get('LayerId')=='1'] for f in frames[:2]]
        self.assertEqual([a.get('ID') for a in groups[0]],[a.get('ID') for a in groups[1]])
        self.assertTrue(any(a.get('Color')=='0' for a in groups[1]))
        self.assertFalse(set(p.get('ID') for a in groups[0] for p in a.findall('AP'))&set(p.get('ID') for a in groups[1] for p in a.findall('AP')))

    def test_rejects_bad_axis_duplicate_effect_and_ratio(self):
        for kind in ['axis','duplicate','ratio']:
            doc=copy.deepcopy(self.doc)
            if kind=='axis':doc['events'][0]['frames'][0]['axis_px']=[[0,0],[0,0]]
            elif kind=='duplicate':doc['events'].append(copy.deepcopy(doc['events'][0]))
            else:doc['canvas']=[852,600]
            with self.assertRaises(ValueError):V.build(self.base,doc,self.profile)
