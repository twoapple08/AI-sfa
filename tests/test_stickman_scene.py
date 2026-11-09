import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from stickman_scene import apply_scene, load_scene, JOINTS
from stickman_projection import guard_hidden_chains
from rtmw_to_stickman_2d import OBS
import stickman_clip as sc


def pose(x):
    return {name: np.array([x, 50.]) for name in JOINTS}


class TestScene(unittest.TestCase):
    def scene(self):
        return dict(schema=1, rig='stickman-2d-11-v1', start=0, end=6, cuts=[4])

    def test_contact_is_geometric_and_does_not_cross_cut(self):
        poses = [dict(blue=pose(10), red=pose(90)) for _ in range(7)]
        before = copy.deepcopy(poses)
        scene = self.scene()
        scene['contacts'] = [dict(id='block', start=2, end=3, feather=2,
                                  members=[['blue', 'wri_r']], target=['red', 'ank_r'])]
        out, report = apply_scene(poses, list(range(7)), scene)
        np.testing.assert_array_equal(out[2]['blue']['wri_r'], out[2]['red']['ank_r'])
        self.assertLess(out[1]['blue']['wri_r'][0], 90)
        np.testing.assert_array_equal(out[4]['blue']['wri_r'], before[4]['blue']['wri_r'])
        np.testing.assert_array_equal(poses[2]['blue']['wri_r'], before[2]['blue']['wri_r'])
        # 인물 사이 AC가 생기지 않는지는 실제 생성된 파일에서도 검사한다.
        fr = E.fromstring('<Frame>' + ''.join(sc.person_aos(2, slot, out[2][color], lambda v: v, color)
                                             for slot, color in enumerate(('blue', 'red'))) + '</Frame>')
        for slot in (0, 1):
            pts = {p.get('ID') for a in fr.findall('AO') if (int(a.get('ID'))-sc.AO0)//100 == slot for p in a.findall('AP')}
            for p in fr.iter('AP'):
                if p.get('ID') in pts:
                    self.assertTrue(all(a.get('ConnPtId') in pts for a in p.findall('AC')))

    def test_visible_view_hides_invented_body_on_detected_actor(self):
        """근접에서 검출이 몸을 지어내도 지정 조각만 보이고, 키 관절은 원본 판독 좌표로 보간된다(11-09)."""
        poses = [dict(blue=pose(10), red=pose(90)) for _ in range(7)]
        poses[2]['red'] = None  # 검출 없는 장도 틀을 빌려 같은 지정을 받는다
        before = copy.deepcopy(poses)
        scene = self.scene()
        scene['visible_views'] = [dict(actor='red', start=1, end=3, visible_segments=[4, 3], thick=6.5,
                                       keys={'1': dict(wri_r=[0, 0]), '3': dict(wri_r=[20, 40])})]
        out, report = apply_scene(poses, list(range(7)), scene)
        for f in (1, 2, 3):
            self.assertEqual(out[f]['red']['_visible_segments'], [3, 4])
        np.testing.assert_allclose(out[2]['red']['wri_r'], [10, 20])
        self.assertEqual(out[2]['red']['_thick'], 6.5)
        self.assertNotIn('_thick', out[0]['red'])
        self.assertNotIn('_visible_segments', out[0]['red'])
        np.testing.assert_array_equal(poses[1]['red']['wri_r'], before[1]['red']['wri_r'])
        j = out[1]['red']
        fr = E.fromstring('<Frame>'+sc.person_aos(1, 1, j, lambda v:v, 'red', visible_segments=j['_visible_segments'])+'</Frame>')
        self.assertEqual([int(a.get('ID')) % 100 for a in fr.findall('AO') if a.get('Color') != '0'], [3, 4])
        scene['visible_views'][0]['end'] = 5  # 컷(4)을 넘으면 거부
        with self.assertRaises(ValueError):
            apply_scene(poses, list(range(7)), scene)

    def test_partial_leg_uses_same_rig_and_one_root(self):
        poses = [dict(blue=pose(10), red=pose(90)) for _ in range(7)]
        poses[1]['red'] = None
        scene = self.scene()
        scene['partials'] = [dict(actor='red', start=1, end=1, visible_segments=[7, 8],
                                  keys={'1': dict(pelvis=[150, 150], kne_r=[100, 100], ank_r=[60, 70])})]
        out, _ = apply_scene(poses, list(range(7)), scene)
        j = out[1]['red']
        fr = E.fromstring('<Frame>'+sc.person_aos(1, 1, j, lambda v:v, 'red', visible_segments=j['_visible_segments'])+'</Frame>')
        self.assertEqual(len(fr.findall('AO')), 11)
        self.assertEqual(sum(p.get('Flags') == '3' for p in fr.iter('AP')), 1)
        self.assertEqual([int(a.get('ID')) % 100 for a in fr.findall('AO') if a.get('Color') != '0'], [7, 8])
        self.assertIsNone(fr.find('FR'))

    def test_profile_is_shared_by_different_scenes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'scene.json'
            path.write_text(json.dumps(self.scene()))
            _, a = load_scene(path)
            changed = self.scene()
            changed.update(start=100, end=110, cuts=[])
            path.write_text(json.dumps(changed))
            _, b = load_scene(path)
            self.assertEqual(a['profile_sha256'], b['profile_sha256'])
            changed['rig'] = 'unknown'
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                load_scene(path)

    def test_hidden_child_does_not_reappear_but_visible_kick_is_kept(self):
        j = {name: np.zeros((2, 2)) for name in JOINTS}
        j['kne_r'][:] = [100, 800]
        j['ank_r'][:] = [110, 650]
        wax = np.ones((2, 23, 2))
        wax[0, OBS['ank_r']] = 0
        side = np.zeros((2, 23), int)
        side[:, OBS['kne_r']] = 1
        events = guard_hidden_chains(j, (wax, side, (0, 1151, 63, 719)))
        np.testing.assert_array_equal(j['ank_r'][0], [110, 950])
        np.testing.assert_array_equal(j['ank_r'][1], [110, 650])
        self.assertEqual(len(events), 1)

    def test_profile_rejects_serializer_flag_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'scene.json'
            path.write_text(json.dumps(self.scene()))
            original = sc.person_aos
            with patch.object(sc, 'person_aos', side_effect=lambda *a, **kw: original(*a, **kw).replace('Flags="5"', 'Flags="6"')):
                with self.assertRaises(ValueError):
                    load_scene(path)

    def test_conflicting_contacts_are_rejected(self):
        scene = self.scene()
        e = dict(id='one', start=2, end=3, members=[['blue','wri_r']], target=['red','ank_r'])
        scene['contacts'] = [e, dict(e, id='two')]
        with self.assertRaises(ValueError):
            apply_scene([dict(blue=pose(10), red=pose(90)) for _ in range(7)], list(range(7)), scene)


if __name__ == '__main__':
    unittest.main()
