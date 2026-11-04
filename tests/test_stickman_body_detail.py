import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stickman_body_detail import mask_curves,apply_detail,strip_and_check
from stickman_clip import person_aos
from stickman_scene import JOINTS


class TestBodyDetail(unittest.TestCase):
    def sample(self):
        mask=np.zeros((160,200),bool);mask[50:140,60:180]=True
        mask[20:65,60:80]=True;mask[10:65,95:115]=True
        mask[0:4,0:4]=True
        curves=mask_curves(mask,2.)
        pose={n:np.array([100.,100.]) for n in JOINTS}
        pose['head_t']=np.array([100.,80.]);pose['pelvis']=np.array([100.,130.])
        frame=ET.fromstring('<Frame>'+person_aos(0,0,pose,lambda p:p/2,'blue')+'</Frame>')
        detailed,record=apply_detail(frame,curves,'blue',0,0,200,200,0)
        record['frame_index']=0
        return frame,detailed,record,curves

    def test_edit_network_and_original_skeleton_are_preserved(self):
        original,detailed,record,curves=self.sample()
        self.assertLess(sum(map(len,curves)),50)
        root=ET.Element('Sequence');root.append(detailed)
        restored=strip_and_check(root,[record]).find('Frame')
        # 서브트리 정렬을 제외한 기본 객체/채움/좌표/연결이 원래 상태로 돌아와야 한다.
        for tag in ['AO','FR']:
            self.assertEqual([ET.tostring(a) for a in original.findall(tag)],
                             [ET.tostring(a) for a in restored.findall(tag)])

    def test_detached_detail_is_rejected(self):
        _,detailed,record,_=self.sample();root=ET.Element('Sequence');root.append(detailed)
        added=set(record['added_objects'])
        node=next(a for a in detailed.findall('AO') if int(a.get('ID')) in added)
        node.find('AP').set('X','999')
        with self.assertRaises(ValueError):strip_and_check(root,[record])

    def test_empty_mask_does_not_create_a_body(self):
        with self.assertRaises(ValueError):mask_curves(np.zeros((100,100),bool))

    def test_missing_fill_is_rejected(self):
        _,detailed,record,_=self.sample();root=ET.Element('Sequence');root.append(detailed)
        detailed.remove(next(f for f in detailed.findall('FR') if int(f.get('ID')) in record['added_fills']))
        with self.assertRaises(ValueError):strip_and_check(root,[record])

    def test_missing_person_uses_hidden_edit_controls_only(self):
        _,_,_,curves=self.sample();pose={n:np.array([100.,100.]) for n in JOINTS}
        frame=ET.Element('Frame')
        detailed,record=apply_detail(frame,curves,'red',1,0,200,200,0,pose)
        self.assertTrue(record['created_hidden_base']);record['frame_index']=0
        root=ET.Element('Sequence');root.append(detailed)
        self.assertEqual(list(strip_and_check(root,[record]).find('Frame')),[])

    def test_crop_tag_excludes_detached_same_color_notes(self):
        mask=np.zeros((200,200),bool);mask[0:160,100:190]=True
        mask[50:90,20:50]=True
        self.assertEqual(len(mask_curves(mask,edge_bounds=(0,199,0,199))),1)
