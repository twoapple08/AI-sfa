"""직진 갈래 스미어의 기하 규칙 검사(합성 입력). 실제 장면 품질·앱 호환의 근거가 아니다."""
import sys,unittest,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import sfa_axial_smear as A
import smear_density as D
import test_sfa_swept_smear as fixtures


def thrust(back=False,angle=0.):
    """팔꿈치 (0,0) → 손 (60,0). 손이 팔 축으로 18px 나가거나(내지르기) 들어온다(거둬들이기)."""
    m=fixtures.SweptSmearTests().motion(angle)
    m['now']=dict(hub=np.zeros(2),tip=np.array([60.,0.]))
    step=np.array([-18. if not back else 18.,0.])
    m['hub']=step;m['tip']=m['now']['tip']+step;m['length']=60.;m['old_length']=60.
    return dict(m,limb_px=26.,smear_px=7.4,frame=10)


class AxialStreak(unittest.TestCase):
    def profile(self):return json.loads(A.SW.PROFILE.read_text())

    def test_thrust_is_axial_and_teeth_point_outward(self):
        for back in (False,True):
            m=thrust(back);self.assertTrue(A.is_axial(m))
            fam,p,acc=A.streak_geometry(m);self.assertEqual((fam,acc),('flow_axial_streak',[]))
            bis=p[1::2]-(p[:-1:2]+p[2::2])/2
            # 거둬들이기에서도 팔꿈치→손 바깥쪽(+x)
            self.assertTrue((bis[:,0]>0).all())
            density=D.process(p,(1152,648),self.profile())
            self.assertTrue(A.check_streak(m,density)['passed'])

    def test_tip_inside_streak_and_width_follows_limb(self):
        m=thrust();_,p,_=A.streak_geometry(m)
        self.assertGreater(p[:,0].max(),60+0.25*60)  # 손끝보다 앞으로 뻗는다
        self.assertLess(p[::2,0].max(),60)          # 뿌리는 손끝 뒤
        self.assertAlmostEqual(np.ptp(p[1::2,1]),A.WIDTH*26.,places=6)

    def test_thicker_smear_lines_mean_fewer_strands(self):
        thin=A.streak_geometry(dict(thrust(),smear_px=4.))[1];thick=A.streak_geometry(dict(thrust(),smear_px=20.))[1]
        self.assertGreater(len(thin),len(thick));self.assertEqual(len(thick),2*3+1)

    def test_classification_thresholds_and_override(self):
        m=thrust()
        for deg,kind,why in ((10,'straight','angle'),(25,'straight','needs_review'),(50,'rotation','angle')):
            self.assertEqual(A.classify(dict(m,angle=np.radians(deg))),(kind,why))
        self.assertEqual(A.classify(dict(m,angle=np.radians(25)),{'10':'rotation'}),('rotation','override'))

    def test_rotation_drops_shallow_teeth_near_joint(self):
        m=dict(fixtures.SweptSmearTests().motion(.8),smear_px=7.4)
        r=A.rotation_radii(m);self.assertGreaterEqual(len(r),4);self.assertGreater(r[0],A.F.RADII[0])
        fam,p,_=A.rotation_geometry(m);self.assertEqual(fam,'flow_axial_rotation')
        density=D.process(p,(1152,648),self.profile())
        self.assertTrue(A.check_rotation(m,density)['passed'])


class StretchDirection(unittest.TestCase):
    def test_measured_direction_overrides_arm_axis(self):
        # 사용자 11-08(1160): 팔은 위로 서 있어도 원본 가닥이 오른쪽이면 갈래도 오른쪽
        m=dict(thrust(),stretch_dir=[0.,-1.])
        _,p,_=A.streak_geometry(m);bis=p[1::2]-(p[:-1:2]+p[2::2])/2
        self.assertTrue((bis[:,1]<0).all());self.assertTrue((np.abs(bis[:,0])<1e-6).all())
        density=D.process(p,(1152,648),json.loads(A.SW.PROFILE.read_text()))
        self.assertTrue(A.check_streak(m,density)['passed'])

    def test_decide_rule(self):
        import smear_stretch_direction as SD
        arm=[1.,0.]
        self.assertEqual(SD.decide(None,arm)[0],False)
        self.assertEqual(SD.decide(dict(dir=[0.,1.],coherence=.1),arm)[2],'low_coherence')
        use,d,why=SD.decide(dict(dir=[-0.98,0.2],coherence=.6),arm)  # 팔 축 근처는 바깥쪽 부호
        self.assertTrue(use);self.assertGreater(d[0],0);self.assertEqual(why,'along_arm_outward')
        use,d,why=SD.decide(dict(dir=[0.,-1.],coherence=.2),arm,eye_ok=True)
        self.assertEqual((use,why),(True,'measured_sign_eye'));self.assertLess(d[1],0)


if __name__=='__main__':
    unittest.main()
