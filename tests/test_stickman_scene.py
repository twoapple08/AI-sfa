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
        # 머리 지름은 구간 흐름(head_d)으로 고정: 키가 작게 읽혀도 지름은 지정값, 중심은 유지
        sc2 = self.scene()
        sc2['visible_views'] = [dict(actor='red', start=1, end=3, visible_segments=[1, 2],
                                     keys={'1': dict(head_t=[0, 0], head_b=[0, 20])}, head_d={'1': 100, '3': 140})]
        o2, _ = apply_scene([dict(blue=pose(10), red=pose(90)) for _ in range(7)], list(range(7)), sc2)
        for f, dia in ((1, 100), (2, 120)):
            np.testing.assert_allclose(np.linalg.norm(o2[f]['red']['head_t'] - o2[f]['red']['head_b']), dia)
            np.testing.assert_allclose((o2[f]['red']['head_t'] + o2[f]['red']['head_b']) / 2, [0, 10])
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


class TestKeyedPoseAndDespike(unittest.TestCase):
    def test_polar_interpolation_keeps_limb_length(self):
        from stickman_scene import keyed_pose
        keys = {'0': dict(neck=[0, 0], elb_r=[100, 0]), '2': dict(neck=[0, 0], elb_r=[-100, 1])}
        mid = keyed_pose(keys, 1, {'neck', 'elb_r'})
        self.assertAlmostEqual(float(np.linalg.norm(mid['elb_r'])), 100, delta=1)  # 직선 보간이면 0 근처로 접힘

    def test_despike_fixes_lone_jump_not_fast_motion(self):
        from stickman_scene import despike
        def p(wx):
            q = pose(0); q['neck'] = np.array([0., 0.]); q['pelvis'] = np.array([0., 100.]); q['wri_r'] = np.array([wx, 50.]); return q
        poses = [dict(blue=p(x)) for x in (10, 12, 90, 14, 16)]
        out, log = despike(poses, list(range(5)), [], set())
        np.testing.assert_allclose(out[2]['blue']['wri_r'], [13, 50])
        fast = [dict(blue=p(x)) for x in (0, 40, 80, 120, 160)]  # 빠른 움직임: 앞뒤가 서로 멀다 → 그대로
        out2, log2 = despike(fast, list(range(5)), [], set())
        self.assertEqual(log2, [])
        out3, log3 = despike(poses, list(range(5)), [2], set())  # 컷을 넘으면 그대로
        self.assertEqual(log3, [])
        out4, log4 = despike(poses, list(range(5)), [], {(2, 'blue')})  # 수동 지정 장은 제외
        self.assertEqual(log4, [])

    def test_despike_length_keeps_direction(self):
        from stickman_scene import despike
        def p(L):
            q = pose(0); q['neck'] = np.array([0., 0.]); q['pelvis'] = np.array([0., 300.])
            q['elb_r'] = np.array([100., 0.]); q['wri_r'] = np.array([100. + L, 0.]); return q
        poses = [dict(blue=p(L)) for L in (100, 104, 20, 98, 102)]
        out, log = despike(poses, list(range(5)), [], set())
        np.testing.assert_allclose(out[2]['blue']['wri_r'], [201, 0], atol=0.5)
        self.assertTrue(any(x['joint'] == 'wri_r' for x in log))


class TestKeyEval(unittest.TestCase):
    def test_sfa_joints_round_trip_and_error(self):
        """키 평가 도구가 SFA 점을 관절 이름·원본 픽셀로 되돌리고, 머리 지름 단위 오차를 잰다."""
        import stickman_key_eval as KE
        j = pose(100); j['wri_r'] = np.array([300., 263.]); j['head_t'] = np.array([100., 100.]); j['head_b'] = np.array([100., 160.])
        to_pct = lambda p: (100 * p[0] / 1152, 100 * (p[1] - 63) / 648)
        xml = '<Sequence><Frame>' + sc.person_aos(0, 1, j, to_pct, 'red') + '</Frame></Sequence>'
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'a.sfa')
            with __import__('zipfile').ZipFile(p, 'w') as z:
                z.writestr('a.xml', xml)
            got = KE.sfa_joints(p, 10, 63)
            np.testing.assert_allclose(got[(10, 1)]['wri_r'], [300, 263], atol=0.1)
            scene = dict(visible_views=[dict(actor='red', keys={'10': dict(wri_r=[330, 263], head_t=[0, 0], head_b=[0, 60])})])
            rows = KE.evaluate(p, scene, 10, 63, {'blue': 0, 'red': 1})
            self.assertEqual(len(rows), 1)  # 머리 키는 위치 오차에서 뺀다
            self.assertAlmostEqual(rows[0]['err_px'] / rows[0]['head_d'], 0.5, places=2)
