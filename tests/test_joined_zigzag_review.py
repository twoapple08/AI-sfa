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
import joined_zigzag_review as R
import zigzag_smear_review as Z


class JoinedZigzagTests(unittest.TestCase):
    def setUp(self):
        self.event=json.loads((Path(__file__).resolve().parents[1]/'data/research/anime_smear_event_2026-11-06.json').read_text())
        areas=[dict(center_px=[20,60],size_px=[12,30]),dict(center_px=[70,30],size_px=[10,20])]
        self.a=dict(source_sha256=self.event['source']['sha256'],image_size=[100,100],frames=[
            dict(source_index=1392,points_px=[[10,10],[20,20],[20,40]],smear_active=False,smears=areas),
            dict(source_index=1393,points_px=[[10,10],[20,20],[20,60]],smear_active=True,smears=areas)])
        self.c=C.create(self.event,0,[1392,1393])

    def test_overlap_becomes_one_chain_without_reducing_density(self):
        shapes,visible,record=R.plan(self.a,1)
        self.assertEqual(record['merged_group'],1);self.assertEqual(visible,[True,False,True])
        np.testing.assert_allclose(shapes[0][0],[20,20])
        self.assertGreater(record['joined_length_px'],record['old_arm_length_px'])
        self.assertLessEqual(record['new_pitch_px'],record['original_pitch_px'])
        np.testing.assert_allclose(shapes[2],Z.geometry(self.a,1,38)[0][2])

    def test_separated_shapes_are_not_merged(self):
        a=copy.deepcopy(self.a);a['frames'][1]['smears'][0]['center_px']=[20,150]
        self.assertIsNone(R.plan(a,1)[2]['merged_group'])

    def test_hidden_overlap_or_fill_cannot_reappear(self):
        for kind in ['overlap','fill']:
            root,cap,records=R.build(self.a)
            if kind=='overlap':root.findall('Frame')[1].findall('AO')[2+cap[0]].set('Color',str(0xff0000ff))
            else:ET.SubElement(root.find('Frame'),'FR',Color='-1')
            with self.subTest(kind=kind),self.assertRaises(ValueError):R.inspect(root,self.a,self.c,cap,records)

    def test_binding_save_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            result=R.save(self.a,self.event,Path(folder))
            self.assertEqual(json.loads((Path(folder)/'single_length_smear.binding.json').read_text()),result)
            self.assertEqual(result['report']['merged_source_indices'],[1393])
            self.assertFalse(result['app_editing_verified'])
