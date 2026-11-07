import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import event_context as C
import zigzag_smear_review as R


class ZigzagSmearTests(unittest.TestCase):
    def setUp(self):
        self.event=json.loads((Path(__file__).resolve().parents[1]/'data/research/anime_smear_event_2026-11-06.json').read_text())
        area=dict(center_px=[50,70],size_px=[12,24],slant_px=0)
        self.a=dict(source_sha256=self.event['source']['sha256'],image_size=[100,100],frames=[
            dict(source_index=1392,points_px=[[10,10],[20,20],[30,20]],smear_active=False,smears=[area,area]),
            dict(source_index=1393,points_px=[[10,10],[20,20],[30,40]],smear_active=True,smears=[area,area])])
        self.c=C.create(self.event,0,[1392,1393])

    def test_no_fill_and_active_strokes_opaque(self):
        root,_=R.build(self.a)
        report=R.inspect(root,self.a,self.c)
        self.assertEqual(report['unique_points'],176)
        self.assertFalse(root.findall('.//FR'));self.assertFalse(root.findall('.//FS'))
        self.assertTrue(all((int(a.get('Color'))&0xffffffff)>>24==255 for a in root.findall('Frame')[1].findall('AO')))

    def test_floating_width_orientation_does_not_flip_with_motion(self):
        before=R.geometry(self.a,1)[0]
        reverse=copy.deepcopy(self.a);reverse['frames'][0]['points_px'][2]=[30,60]
        after=R.geometry(reverse,1)[0]
        for left,right in zip(before,after):
            np.testing.assert_allclose(left[0],right[0]);np.testing.assert_allclose(left[-1],right[-1])

    def test_trapezoid_ends_not_pointed_and_speed_stretches_strokes(self):
        p=R.zigzag([0,0],[0,10],4,10)
        self.assertGreater(abs(p[0][0]),0);self.assertGreater(abs(p[-1][0]),abs(p[0][0]))
        fast=copy.deepcopy(self.a);fast['frames'][0]['points_px'][2]=[30,-20]
        self.assertGreater(R.geometry(fast,1)[1]['outer_arm_span_px'],R.geometry(self.a,1)[1]['outer_arm_span_px'])
        arm=R.geometry(self.a,1)[0][0];np.testing.assert_allclose(arm[0],self.a['frames'][1]['points_px'][1])

    def test_fill_alpha_or_broken_link_rejected(self):
        for kind in ['fill','alpha','link']:
            root,_=R.build(self.a)
            if kind=='fill':ET.SubElement(root.find('Frame'),'FR',Color='-1')
            elif kind=='alpha':root.findall('Frame')[1].findall('AO')[2].set('Color',str(0x990000ff))
            else:root.findall('Frame')[1].findall('AO')[2].find('AP').find('AC').set('ConnPtId','99999')
            with self.subTest(kind=kind),self.assertRaises(ValueError):R.inspect(root,self.a,self.c)

    def test_save_context_and_configurable_line_count(self):
        with tempfile.TemporaryDirectory() as folder:
            result=R.save(self.a,self.event,Path(folder),segments=20)
            stored=json.loads((Path(folder)/'zigzag_smear.binding.json').read_text())
            self.assertEqual(stored,result);self.assertEqual(result['report']['effect_line_objects'],60)
