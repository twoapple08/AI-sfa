import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import smear_curve_review as R
import event_context as C


class SmearCurveReviewTests(unittest.TestCase):
    def setUp(self):
        self.event = json.loads((Path(__file__).resolve().parents[1] / 'data/research/anime_smear_event_2026-11-06.json').read_text())
        self.a = dict(source_sha256=self.event['source']['sha256'],image_size=[100,100],frames=[
            dict(source_index=1392,curve_px=[[10,20],[60,0],[80,90]],widths_px=[2,8,1],active=True),
            dict(source_index=1393,curve_px=[[10,20],[60,0],[80,90]],widths_px=[2,8,1],active=False)])
        self.c = C.create(self.event,0,[1392,1393])

    def test_subdivision_preserves_quadratic_geometry(self):
        p = self.a['frames'][0]['curve_px']
        for i in range(9):
            q = R.segment(p,i/9,(i+1)/9)
            for t in [0,.2,.6,1]: np.testing.assert_allclose(R.quad(q,t),R.quad(p,(i+t)/9),atol=1e-12)

    def test_variants_share_geometry_and_keep_disappearance(self):
        a,b=R.build(self.a,'plain'),R.build(self.a,'variable_glow')
        self.assertEqual([p.attrib for p in a.findall('.//AP')],[p.attrib for p in b.findall('.//AP')])
        self.assertGreater(len({x.get('ThicknessScale') for x in b.findall('Frame')[0].findall('AO')}),1)
        self.assertEqual(R.inspect(b,self.c,self.a['frames'])['unique_points'],54)
        bad=copy.deepcopy(b);bad.findall('Frame')[1].find('AO').set('GlowAlpha','.5')
        with self.assertRaises(ValueError):R.inspect(bad,self.c,self.a['frames'])

    def test_missing_connection_or_reused_point_is_rejected(self):
        for kind in ['link','id']:
            bad=R.build(self.a,'plain')
            if kind=='link':
                p=bad.find('.//AP[@Index="2"]');p.remove(p.find('AC'))
            else:bad.findall('Frame')[1].find('.//AP').set('ID',bad.findall('Frame')[0].find('.//AP').get('ID'))
            with self.subTest(kind=kind),self.assertRaises(ValueError):R.inspect(bad,self.c,self.a['frames'])

    def test_wrong_source_or_bad_width_is_rejected(self):
        bad=copy.deepcopy(self.a);bad['source_sha256']='0'*64
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):R.save_review(bad,self.event,Path(tmp))
        bad=copy.deepcopy(self.a);bad['frames'][0]['widths_px'][1]=0
        with self.assertRaises(ValueError):R.build(bad,'variable_glow')
