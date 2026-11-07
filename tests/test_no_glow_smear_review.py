import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import event_context as C
import no_glow_smear_review as R


class NoGlowSmearTests(unittest.TestCase):
    def setUp(self):
        self.event=json.loads((Path(__file__).resolve().parents[1]/'data/research/anime_smear_event_2026-11-06.json').read_text())
        shape=dict(center_px=[50,50],size_px=[10,20],slant_px=4)
        self.a=dict(image_size=[100,100],source_sha256=self.event['source']['sha256'],frames=[
            dict(source_index=1392,points_px=[[10,10],[20,20],[25,35]],smear_active=False,smears=[copy.deepcopy(shape),copy.deepcopy(shape)]),
            dict(source_index=1393,points_px=[[10,10],[20,15],[30,20]],smear_active=True,smears=[copy.deepcopy(shape),copy.deepcopy(shape)])])
        self.c=C.create(self.event,0,[1392,1393])

    def test_axes_preserved_and_all_glow_zero(self):
        plain,smear=R.build(self.a,False),R.build(self.a,True)
        report=R.inspect(plain,smear,self.c,self.a)
        self.assertEqual(report['unique_smear_version_points'],92)
        self.assertTrue(report['axes_identical']);self.assertTrue(report['all_glow_zero'])

    def test_axis_change_or_glow_or_wrong_activation_rejected(self):
        for kind in ['axis','glow','active']:
            plain,smear=R.build(self.a,False),R.build(self.a,True)
            if kind=='axis':smear.find('.//AP').set('X','99')
            elif kind=='glow':smear.findall('Frame')[1].findall('AO')[2].set('GlowThickness','2')
            else:smear.findall('Frame')[0].findall('AO')[2].set('Color','-16776961')
            with self.subTest(kind=kind),self.assertRaises(ValueError):R.inspect(plain,smear,self.c,self.a)

    def test_geometry_responds_to_spread_and_slant(self):
        first=R.build(self.a,True)
        changed=copy.deepcopy(self.a);changed['frames'][1]['smears'][0]['size_px']=[20,40];changed['frames'][1]['smears'][0]['slant_px']=-6
        second=R.build(changed,True)
        self.assertEqual([p.attrib for p in first.findall('Frame')[1].findall('AO')[0].findall('AP')],
                         [p.attrib for p in second.findall('Frame')[1].findall('AO')[0].findall('AP')])
        self.assertNotEqual([(p.get('X'),p.get('Y')) for p in first.findall('Frame')[1].findall('AO')[2].findall('AP')],
                            [(p.get('X'),p.get('Y')) for p in second.findall('Frame')[1].findall('AO')[2].findall('AP')])
        bad=copy.deepcopy(self.a);bad['frames'][1]['smears'][0]['slant_px']=float('nan')
        with self.assertRaises(ValueError):R.build(bad,True)
