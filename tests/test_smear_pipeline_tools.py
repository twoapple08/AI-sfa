"""스미어 단계 도구(배치·검사)의 합성 반례 시험. 실제 장면 품질·앱 표시 확인이 아니다."""
import sys,unittest
from pathlib import Path
import numpy as np
import xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import smear_from_labels as SL
import smear_checks as SC


def ao(parent,oid,pts,layer='0',color='-16777216'):
    a=E.SubElement(parent,'AO',ID=str(oid),TypeId='1',LayerId=layer,Color=color)
    for i,(x,y) in enumerate(pts):E.SubElement(a,'AP',ID=str(oid*10+i),X=str(x/11.52),Y=str(y/6.48))
    return a


def frame_with_arm(smear_end_x):
    """팔꿈치(100,100)→손(160,100). 스미어 묶음은 x=120..smear_end_x."""
    root=E.Element('Sequence');f=E.SubElement(root,'Frame')
    E.SubElement(f,'LayerDef',ID='0',Name='Layer 1');E.SubElement(f,'LayerDef',ID='1',Name='smear')
    ao(f,SL.BASE+3,[(100,100),(60,100)]);ao(f,SL.BASE+4,[(160,100),(100,100)])
    ao(f,SL.BASE+7,[(300,300),(300,350)]);ao(f,SL.BASE+8,[(300,400),(300,350)])
    ao(f,1300000000,[(120,90),(smear_end_x,110)],layer='1')
    return root


class Checks(unittest.TestCase):
    def test_tip_poking_out_is_caught(self):
        self.assertEqual(SC.tip_violations(frame_with_arm(150))['violations'][0]['overshoot_px'],10.0)
        self.assertEqual(SC.tip_violations(frame_with_arm(175))['violations'],[])

    def test_layer_number_defect_fails(self):
        r=frame_with_arm(175);f=r.find('Frame')
        ld=E.Element('LayerDef',ID='2',Name='outline_glow');f.insert(0,ld)  # 뒤에 깔려고 앞에 적었지만 번호는 가장 큼
        import sfa_layer_order as LO
        self.assertFalse(LO.check(r)['order_matches_ids'])
        LO.renumber_bottom_to_top(r);self.assertTrue(LO.check(r)['order_matches_ids'])


class Placement(unittest.TestCase):
    def test_items_skip_uncertain_and_mark_whole(self):
        labels=[dict(frame=5,actor='red',part='leg',box=[0,0,1,1],conf='S',user='빨강 다리 전체'),dict(frame=6,actor='red',part='arm',box=[0,0,1,1],conf='U')]
        it=SL.items_from_labels(labels,[[7,'blue','arm']])
        self.assertEqual([(i['frame'],i['whole'],i['box'] is None) for i in it],[(5,True,False),(7,False,True)])

    def test_clamp_tail_pulls_in_lone_end(self):
        xs=np.linspace(0,100,30);pts=np.stack([xs,np.where(np.arange(30)%2,5.,-5.)],1);pts[-1]=[100,40]
        q,changed=SL.clamp_tail(pts,[(0,0),(100,0)])
        self.assertGreater(changed,0);self.assertLessEqual(abs(q[-1][1]),5*1.15+1e-6)


if __name__=='__main__':
    unittest.main()


class DepthLevels(unittest.TestCase):
    def setUp(self):
        import sfa_depth_layers as D
        self.D=D;self.order=lambda k:(k[0],list(D.GROUPS).index(k[1]))

    def test_measured_beats_default_cycle(self):
        # 1173 유형: 검은 팔(0:armA)이 파란 팔(1:armA) 스미어 위. 검은 팔은 파란 몸통과도 겹치고(기본: 파랑 위),
        # 파란 몸통과 파란 팔은 같은 인물 순서. 기본끼리 이으면 측정과 순환 → 기본을 버려야 한다.
        overlap={((0,'armA'),(1,'core')),((1,'core'),(1,'armA')),('smear',(1,'armA'),(0,'armA'))}
        meas=[((0,'armA'),(1,'armA'),'over_smear',1600.)]
        level,dropped=self.D.assign_levels(overlap,meas,self.order)
        self.assertGreater(level[(0,'armA')],level[(1,'armA')])
        self.assertTrue(all(d[0]!='measured' for d in dropped))

    def test_default_keeps_single_level(self):
        overlap={((0,'armA'),(1,'armA'))}
        level,_=self.D.assign_levels(overlap,[],self.order)
        self.assertEqual(max(level.values()),0)

    def test_chains_ignore_ids(self):
        root=E.Element('Sequence');f=E.SubElement(root,'Frame')
        a=ao(f,600000001,[(0,0),(10,0)],layer='1');b=ao(f,13,[(10,0),(20,5)],layer='1')
        E.SubElement(a.findall('AP')[1],'AC',ConnPtId=b.findall('AP')[0].get('ID'))
        self.assertEqual(len(SC.smear_chains([a,b])),1)


class ManualFixes(unittest.TestCase):
    def test_pose_fix_moves_exactly_one_point(self):
        r=frame_with_arm(175)
        out,log=SL.apply_pose_fixes(r,[dict(frame=1,object=SL.BASE+4,**{'from':[160,100],'to':[200,120]})],1)
        a=[x for x in out.find('Frame').findall('AO') if x.get('ID')==str(SL.BASE+4)][0]
        self.assertAlmostEqual(float(a.findall('AP')[0].get('X'))*11.52,200,4)
        with self.assertRaises(ValueError):SL.apply_pose_fixes(r,[dict(frame=1,object=SL.BASE+4,**{'from':[999,999],'to':[0,0]})],1)

    def test_body_check_applies_scene_pose_fixes_to_reference(self):
        """장면 설정 자세 교정 장은 '기준+교정'과 같아야 통과, 교정과 다른 몸 변경은 여전히 잡는다."""
        import tempfile,zipfile,os
        fix=[dict(frame=1,object=SL.BASE+4,**{'from':[160,100],'to':[200,120]})]
        ref=frame_with_arm(175);good,_=SL.apply_pose_fixes(ref,fix,1)
        bad,_=SL.apply_pose_fixes(ref,[dict(fix[0],to=[201,120])],1)
        with tempfile.TemporaryDirectory() as d:
            def save(root,name):
                p=os.path.join(d,name)
                with zipfile.ZipFile(p,'w') as z:z.writestr('a.xml',E.tostring(root))
                return p
            r,g,b=save(ref,'r.sfa'),save(good,'g.sfa'),save(bad,'b.sfa')
            self.assertEqual(SC.run(g,r)['body']['frames_with_body_change'],[0])
            self.assertEqual(SC.run(g,r,pose_fixes=fix)['body']['frames_with_body_change'],[])
            self.assertEqual(SC.run(b,r,pose_fixes=fix)['body']['frames_with_body_change'],[0])

    def test_forced_streak_uses_given_length_and_arm_direction(self):
        import sfa_axial_smear as A
        m=dict(now=dict(hub=np.zeros(2),tip=np.array([60.,0.])),hub=np.zeros(2),tip=np.array([60.,0.]),angle=0.,length=60.,old_length=60.,
               limb_px=26.,smear_px=7.4,forced=True,total_px=110.,stretch_dir=[1.,0.])
        _,p,_=A.streak_geometry(m)
        self.assertAlmostEqual(p[1::2,0].max()-p[::2,0].min(),110*(A.F.FRONT_SHARE*max(A.F.FORWARD[:5])+A.F.BACK_SHARE*max(A.F.TRAIL[:6])),delta=15)
        self.assertGreater(p[:,0].max(),60)


class UserDepth(unittest.TestCase):
    def test_user_depth_overrides_measure_and_raises_front(self):
        import sfa_depth_layers as D
        sc={'depth_user':[dict(frame=1176,front='0:armA',back='1:armA',kind='over_smear')]}
        meas=[((1,'armA'),(0,'armA'),'body',80.)]  # 측정은 반대
        m=D.user_depth(meas,sc,1176);self.assertEqual(m,[((0,'armA'),(1,'armA'),'over_smear',1e9)])
        self.assertEqual(D.user_depth(meas,sc,1175),meas)
        order=lambda k:(k[0],0)
        level,_=D.assign_levels([((0,'armA'),(1,'armA'))],m,order)
        self.assertGreater(level[(0,'armA')],level[(1,'armA')])


class HiddenDepth(unittest.TestCase):
    def test_inferred_group_never_in_front(self):
        import sfa_depth_layers as D
        hidden = D.hidden_groups({5: [dict(actor='red', joints=['elb_l', 'wri_l', 'pelvis', 'head_t', 'head_b'])]}, 5, {'blue': 0, 'red': 1})
        self.assertIn((1, 'armB'), hidden); self.assertIn((1, 'core'), hidden); self.assertNotIn((1, 'armA'), hidden)
        overlap = {((0, 'core'), (1, 'armB')), ((0, 'armA'), (1, 'legA'))}
        meas = [((1, 'armB'), (0, 'core'), 'body', 1.9)]  # 추론 팔이 앞이라는 약한 측정 → 버리고 뒤로
        out = D.hidden_back(overlap, meas, hidden)
        self.assertIn(((0, 'core'), (1, 'armB'), 'body', 0.5), out)
        self.assertFalse(any(m[0] in hidden for m in out))
        self.assertEqual(D.hidden_back(overlap, meas, set()), meas)  # 추론 없으면 그대로


class FrontLimbDepth(unittest.TestCase):
    def test_front_arm_over_torso_but_never_over_own_head(self):
        """앞 팔 > 몸통 > 뒤 팔. 머리는 따로 묶어 같은 인물 팔다리보다 늘 위(11-10 사용자 '머리 레이어가 왜 몸 뒤로')."""
        import sfa_depth_layers as D
        overlap = {((1, 'core'), (1, 'armA')), ((1, 'core'), (1, 'armB')), ((1, 'armA'), (1, 'head')), ((1, 'core'), (1, 'head'))}
        meas = D.front_order(overlap, [], [dict(frame=5, actor='red', arm='r')], {'blue': 0, 'red': 1})
        self.assertIn(((1, 'armA'), (1, 'core'), 'body', 0.8), meas)
        self.assertIn(((1, 'core'), (1, 'armB'), 'body', 0.8), meas)
        self.assertFalse(any(m[1] == (1, 'head') for m in meas))  # 추정만으로 팔을 얼굴 위로 올리지 않는다
        # 다른 인물 때문에 팔이 한 칸 올라가도 머리 기본(head_top 500)이 머리를 함께 올린다
        meas += [((1, 'head'), (1, 'armA'), 'head_top', 500.), ((1, 'head'), (1, 'core'), 'head_top', 500.),
                 ((1, 'armA'), (0, 'core'), 'body', 60.)]
        overlap |= {((0, 'core'), (1, 'armA'))}
        order = lambda k: (k[0], list(D.GROUPS).index(k[1]))
        level, _ = D.assign_levels(overlap, meas, order)
        self.assertGreaterEqual(level[(1, 'head')], level[(1, 'armA')])
        self.assertGreaterEqual(level[(1, 'armA')], level[(1, 'core')])

    def test_mask_is_head_cape_is_torso(self):
        import sfa_depth_layers as D
        mask = E.Element('AO', ID='4570003', TypeId='1', Color='-65536'); cape = E.Element('AO', ID='4570010', TypeId='3', Color='-1207959552')
        self.assertEqual(D.part_of_body(4570003, mask), (0, 'head'))
        self.assertEqual(D.part_of_body(4570010, cape), (0, 'core'))
        self.assertEqual(D.part_of_body(4560101), (1, 'head'))

    def test_split_lower_moves_only_forearm(self):
        import sfa_depth_layers as D
        f = E.Element('Frame'); E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1')
        for k in (3, 4):
            ao(f, D.BASE + k, [(k, 0), (k + 1, 0)])
        own = {str(D.BASE + 3): (0, 'armA'), str(D.BASE + 4): (0, 'armA')}
        out = D.split_lower(f, own, {(0, 'armA_lo'): 2})
        self.assertEqual(out[str(D.BASE + 4)], (0, 'armA_lo')); self.assertEqual(out[str(D.BASE + 3)], (0, 'armA'))

    def test_front_sides_needs_clear_score_gap(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
        import stickman_clip as sc
        k = np.zeros((133, 3)); k[:, 2] = 3.0
        self.assertIsNone(sc.front_sides(k))  # 차이 없음 → 정하지 않음
        k[7, 2] = k[9, 2] = 1.0  # 왼팔(팔꿈치·손목) 점수 낮음 → 오른팔이 앞
        self.assertEqual(sc.front_sides(k), {'arm': 'r'})


class AppDrawOrder(unittest.TestCase):
    def test_copies_registered_in_first_frame_keep_source_order(self):
        """앱은 같은 레이어 안을 ID 첫 등장 순서로 그린다. 칸 복사본이 뒤 장에서 처음 나와도 원래 순서를 지켜야 한다."""
        import sfa_depth_layers as D
        def seq(spec):
            r = E.Element('Sequence')
            for objs in spec:
                f = E.SubElement(r, 'Frame'); E.SubElement(f, 'LayerDef', ID='0', Name='Layer 1')
                for oid in objs: ao(f, oid, [(0, 0), (10, 10)])
            return r
        src = seq([[1, 2, 3], [1, 2, 3]])           # 의도: 1 < 2 < 3 (3이 맨 위)
        out = seq([[2, 3], [600000001, 2, 3]])      # 1의 복사본이 둘째 장에서 처음 나오면 앱에선 맨 위가 된다
        rep = D.register_order(out, src, {('1', 0): 600000001})
        self.assertEqual(rep['remaining_inversion_ids'], 0)
        first = [a.get('ID') for a in out.find('Frame').findall('AO')]
        self.assertEqual(first, ['600000001', '2', '3'])
        reg = out.find('Frame').findall('AO')[0]
        self.assertEqual(reg.get('Color'), '0'); self.assertEqual(list(reg.iter('AC')), [])
        others = {p.get('ID') for a in out.iter('AO') if a is not reg for p in a.iter('AP')}
        self.assertFalse({p.get('ID') for p in reg.iter('AP')} & others)  # 등록용 점 ID는 파일 어디와도 겹치지 않음


class BackView(unittest.TestCase):
    def test_back_view_puts_crossing_limb_over_head(self):
        import sfa_depth_layers as D
        sc = {'back_views': [dict(actor='blue', start=10, end=12)]}
        self.assertEqual(D.back_slots(sc, 11, {'blue': 0, 'red': 1}), {0})
        self.assertEqual(D.back_slots(sc, 13, {'blue': 0, 'red': 1}), set())
        head = (np.array([0., 0.]), 20.)
        through = [(np.array([0., 18.]), np.array([-40., -5.]), 4, 'a')]   # 목에서 시작해 머리 원을 가로지름
        below = [(np.array([0., 18.]), np.array([30., 60.]), 4, 'b')]      # 목에서 아래로
        self.assertTrue(D.crosses_head(through, head)); self.assertFalse(D.crosses_head(below, head))
