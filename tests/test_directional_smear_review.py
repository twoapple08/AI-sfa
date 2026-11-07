import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import directional_smear_review as R
import event_context as C


class DirectionalSmearTests(unittest.TestCase):
    def setUp(self):
        self.event=json.loads((Path(__file__).resolve().parents[1]/'data/research/anime_smear_event_2026-11-06.json').read_text())
        area=dict(center_px=[50,10],size_px=[10,20],slant_px=0)
        self.a=dict(image_size=[100,100],frames=[dict(source_index=1392,points_px=[[10,10],[20,20],[30,20]],smear_active=False,smears=[area,area]),
            dict(source_index=1393,points_px=[[10,10],[20,20],[30,40]],smear_active=True,smears=[area,area])])
        self.c=C.create(self.event,0,[1392,1393])

    def test_shape_narrows_to_elbow_and_widens_at_tip(self):
        shape=R.ribbon([0,0],[10,0],6)
        np.testing.assert_allclose(shape[0][0],[0,0]);np.testing.assert_allclose(shape[2][2],[0,0])
        self.assertAlmostEqual(np.linalg.norm(shape[0][2]-shape[2][0]),6)
        root,_=R.build(self.a);self.assertEqual(R.inspect(root,self.a,self.c)['unique_points'],62)

    def test_floating_direction_follows_movement(self):
        direction,_=R.trajectory(self.a,1)
        self.assertGreater(direction[1],0)
        changed=copy.deepcopy(self.a);changed['frames'][1]['points_px'][2]=[30,0]
        direction2,_=R.trajectory(changed,1);self.assertLess(direction2[1],0)
        curve=R.geometry(self.a,1)[0][1]
        np.testing.assert_allclose(curve[2][2],curve[0][0])

    def test_current_hand_area_is_not_duplicated_in_air(self):
        row=copy.deepcopy(self.a['frames'][1]);row['smears'][0]=dict(center_px=[30,40],size_px=[10,20],slant_px=0)
        self.assertEqual(R.visibility(row),[True,False,True])

    def test_broken_link_fill_or_glow_rejected(self):
        for kind in ['link','fill','glow','inactive']:
            root,_=R.build(self.a)
            if kind=='link':root.findall('Frame')[1].findall('AO')[2].find('AP').find('AC').set('ConnPtId','9999')
            elif kind=='fill':root.findall('Frame')[1].find('FR').find('FS').set('ObjId','9999')
            elif kind=='glow':root.find('Frame').find('AO').set('GlowAlpha','.5')
            else:root.find('Frame').find('FR').set('Color','-16776961')
            with self.subTest(kind=kind),self.assertRaises(ValueError):R.inspect(root,self.a,self.c)

    def test_save_roundtrip_includes_serializable_visibility(self):
        a=copy.deepcopy(self.a);a['source_sha256']=self.event['source']['sha256']
        with tempfile.TemporaryDirectory() as folder:
            result=R.save(a,self.event,Path(folder))
            stored=json.loads((Path(folder)/'directional_smear.binding.json').read_text())
            self.assertEqual(stored,result)
            self.assertEqual(stored['directions'][1]['shape_visibility'],[True,True,True])
