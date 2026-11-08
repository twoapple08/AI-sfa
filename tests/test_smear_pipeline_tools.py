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

    def test_forced_streak_uses_given_length_and_arm_direction(self):
        import sfa_axial_smear as A
        m=dict(now=dict(hub=np.zeros(2),tip=np.array([60.,0.])),hub=np.zeros(2),tip=np.array([60.,0.]),angle=0.,length=60.,old_length=60.,
               limb_px=26.,smear_px=7.4,forced=True,total_px=110.,stretch_dir=[1.,0.])
        _,p,_=A.streak_geometry(m)
        self.assertAlmostEqual(p[1::2,0].max()-p[::2,0].min(),110*(A.F.FRONT_SHARE*max(A.F.FORWARD[:5])+A.F.BACK_SHARE*max(A.F.TRAIL[:6])),delta=15)
        self.assertGreater(p[:,0].max(),60)
