import sys,os,unittest,xml.etree.ElementTree as E
import numpy as np
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','tools'))
from stickman_projection import projected_joints, constrain_head_contact
from rtmw_to_stickman_2d import OBS
import stickman_clip as sc
class TestProjection(unittest.TestCase):
 def test_shortened_arm_and_straight_kick(self):
  T=4;K=np.zeros((T,23,3));K[:,:,2]=5
  pts={'sho_l':[0,0],'sho_r':[0,0],'hip_l':[0,100],'hip_r':[0,100],'elb_l':[10,0],'wri_l':[20,0],'elb_r':[-20,0],'wri_r':[-40,0],'kne_l':[80,100],'ank_l':[160,100],'kne_r':[0,180],'ank_r':[0,250]}
  for n,j in OBS.items():K[:,j,:2]=pts[n]
  fallback={n:np.tile(np.array(p,dtype=float),(T,1)) for n,p in pts.items()};fallback['neck']=np.zeros((T,2));fallback['pel']=np.tile([0.,100.],(T,1))
  fallback['elb_l'][:]=[50,20];fallback['wri_l'][:]=[60,40]
  W=np.ones((T,23));half=(np.ones((T,23,2)),np.zeros((T,23),int),(-1000,1000,-1000,1000))
  out,rep=projected_joints(K,W,half,[10,11,12,13],[(10,10),(11,11),(12,12),(13,13)],fallback,np.full(T,100.))
  np.testing.assert_allclose(out['elb_l'],np.tile([10,0],(T,1)),atol=1e-8)
  np.testing.assert_allclose(out['wri_l'],np.tile([20,0],(T,1)),atol=1e-8)
  np.testing.assert_allclose(out['ank_l']-out['kne_l'],out['kne_l']-out['pelvis'])
  # 관측 없는 축은 상상 좌표로 대체하지 않는다.
  half[0][:,9,:]=0
  out,_=projected_joints(K,W,half,[10,11,12,13],[(10,13)],fallback,np.full(T,100.))
  np.testing.assert_allclose(out['wri_l'],fallback['wri_l'])
 def test_head_translation_connected_white_fill(self):
  names={n for _,_,pts in sc.BODY for _,n,_,_ in pts};J={n:np.array([20.,20.]) for n in names};J['head_b']=np.array([30.,25.]);J['head_t']=np.array([30.,5.])
  fr=E.fromstring('<Frame>'+sc.person_aos(0,0,J,lambda p:p,'blue')+'</Frame>');pts={x.get('ID'):x for x in fr.iter('AP')}
  for p in pts.values():
   for ac in p.findall('AC'):
    q=pts[ac.get('ConnPtId')];self.assertEqual((p.get('X'),p.get('Y')),(q.get('X'),q.get('Y')))
  self.assertEqual(sum(x.get('Flags')=='3' for x in pts.values()),1)
  self.assertEqual(fr.find('FR').get('Color'),'-1')
  self.assertEqual(fr.findall('AO')[-1].get('TypeId'),'2')
  hidden=[a for a in fr.findall('AO') if a.get('Color')=='0']
  self.assertEqual([int(a.get('ID'))-sc.AO0 for a in hidden],[11])

 def test_white_head_occludes_body_stroke(self):
  from sfa_render import render_frame
  names={n for _,_,pts in sc.BODY for _,n,_,_ in pts}
  J={n:np.array([20.,20.]) for n in names}
  J.update(neck=np.array([50.,50.]),pelvis=np.array([50.,80.]),head_t=np.array([50.,40.]),head_b=np.array([50.,60.]))
  root=E.fromstring('<Sequence HeightWidthRatio="1"><Frame BackgroundColor="-1"><LayerDef ID="0"/>'+sc.person_aos(0,0,J,lambda p:p,'red')+'</Frame></Sequence>')
  im=render_frame(root,root.find('Frame'),200,200)
  np.testing.assert_array_equal(im[110,100],[255,255,255])
  self.assertLess(int(im[150,100,1]),100)  # 원 밖 몸통은 빨강으로 남는다.

 def test_separated_head_moves_minimally_and_keeps_diameter(self):
  from sfa_render import render_frame
  names={n for _,_,pts in sc.BODY for _,n,_,_ in pts}
  J={n:np.array([20.,20.]) for n in names}
  J.update(neck=np.array([50.,70.]),pelvis=np.array([50.,90.]),head_t=np.array([50.,30.]),head_b=np.array([50.,50.]))
  root=E.fromstring('<Sequence HeightWidthRatio="1"><Frame BackgroundColor="-1"><LayerDef ID="0"/>'+sc.person_aos(0,0,J,lambda p:p,'red')+'</Frame></Sequence>')
  im=render_frame(root,root.find('Frame'),200,200)
  np.testing.assert_array_equal(im[120,100],[255,255,255])  # 머리 중심이60으로 내려와 긴 목선을 덮는다.
  np.testing.assert_array_equal(im[80,100],[255,255,255])  # 이전 머리 위치는 비워진다.
  head=root.find('Frame').findall('AO')[-1]
  self.assertEqual([(p.get('X'),p.get('Y')) for p in head.findall('AP')],[('50.0000','50.0000'),('50.0000','70.0000')])
  np.testing.assert_array_equal(J['head_t'],[50.,30.])  # 호출자가 가진 원좌표는 수정하지 않는다.
  pts={p.get('ID'):p for p in root.iter('AP')}
  for p in pts.values():
   for ac in p.findall('AC'):
    q=pts[ac.get('ConnPtId')]
    self.assertEqual((p.get('X'),p.get('Y')),(q.get('X'),q.get('Y')))

 def test_contact_keeps_bowed_head_and_is_continuous_at_boundary(self):
  neck=np.array([[0.,0.],[0.,0.],[0.,0.]])
  center=np.array([[0.,-3.],[10.-1e-6,0.],[10.+1e-6,0.]])
  a,b=center+[0.,-10.],center+[0.,10.]
  top,bottom,shift=constrain_head_contact(neck,a,b)
  np.testing.assert_array_equal(top[0],a[0]);np.testing.assert_array_equal(bottom[0],b[0])
  np.testing.assert_allclose(np.linalg.norm(top-bottom,axis=1),20.)
  np.testing.assert_allclose(shift[2],[-1e-6,0.],atol=1e-12)
  self.assertLess(np.linalg.norm((top[1]+bottom[1])/2-(top[2]+bottom[2])/2),2e-6)
