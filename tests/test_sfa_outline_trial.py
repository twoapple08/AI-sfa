import sys,unittest,copy
from pathlib import Path
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from sfa_outline_trial import build

class OutlineTrialTests(unittest.TestCase):
    def setUp(self):
        self.root=E.fromstring('<Sequence Name="probe" HeightWidthRatio=".5625"><Frame Position="0"><LayerDef ID="0" Visible="true"/><AO ID="4560002" TypeId="1" Color="-16777216" LayerId="0" ThicknessScale="2" GlowRadius="0" GlowThickness="0" GlowAlpha="0"><AP ID="10" X="10" Y="10" Flags="3"><AC ConnPtId="12"/></AP><AP ID="11" X="20" Y="10" Flags="9"/></AO><AO ID="99" TypeId="1" Color="-16777216" LayerId="0" ThicknessScale=".3"><AP ID="12" X="10" Y="10" Flags="9"><AC ConnPtId="10"/></AP><AP ID="13" X="20" Y="30" Flags="9"/></AO><AO ID="100" TypeId="1" Color="0" LayerId="0" ThicknessScale=".05"><AP ID="14" X="0" Y="0"/></AO></Frame></Sequence>')
    def test_stroke_is_behind_and_preserves_every_original_node(self):
        before=E.tostring(self.root);root,report=build(self.root)
        self.assertEqual(E.tostring(self.root),before);f=root.find('Frame');old=self.root.find('Frame');count=report['rows'][0]['outline_objects']
        self.assertEqual(count,2);self.assertEqual([E.tostring(c) for c in list(f)[count+1:]],[E.tostring(c) for c in old])
        self.assertEqual(f[0].tag,'LayerDef');copies=f.findall('AO')[:2]
        self.assertAlmostEqual(float(copies[0].get('ThicknessScale')),2.4)
        self.assertAlmostEqual(float(copies[1].get('ThicknessScale')),.7)
        by={p.get('ID'):p for a in copies for p in a.findall('AP')}
        for p in by.values():
            for c in p.findall('AC'):self.assertIn(c.get('ConnPtId'),by)
        self.assertTrue(all(p.get('Flags')=='9' for p in by.values()))
    def test_glow_opacity_and_global_fresh_point_ids(self):
        f=copy.deepcopy(self.root.find('Frame'));f.set('Position','1')
        for p in f.findall('.//AP'):
            p.set('ID',str(int(p.get('ID'))+100))
            for c in p.findall('AC'):c.set('ConnPtId',str(int(c.get('ConnPtId'))+100))
        self.root.append(f);root,report=build(self.root,'glow');seen=set()
        for f in root.findall('Frame'):
            copies=[a for a in f.findall('AO') if a.get('LayerId')==str(report['outline_layer'])]
            self.assertTrue(all(a.get('GlowAlpha')=='255' for a in copies));self.assertTrue(all(float(a.get('GlowThickness'))>10 for a in copies))
            ids={p.get('ID') for a in copies for p in a.findall('AP')};self.assertFalse(ids&seen);seen|=ids
    def test_bad_mode_and_width_fail(self):
        with self.assertRaises(ValueError):build(self.root,'filled')
        with self.assertRaises(ValueError):build(self.root,edge_ratio=0)
