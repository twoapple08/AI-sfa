# 지정 영역(배경 기준물)만으로 ORB 유사변환을 맞춰 배경 배율·이동을 잰다. 영역은 비율 x0,y0,x1,y1.
import sys,cv2,numpy as np
S,sh=sys.argv[1:3]; x0,y0,x1,y1=map(float,sys.argv[3].split(','))
orb=cv2.ORB_create(3000,fastThreshold=5); bf=cv2.BFMatcher(cv2.NORM_HAMMING,crossCheck=True)
def kp(i):
    g=cv2.cvtColor(cv2.imread(f'{S}/fr/{sh}/{i:03d}.png'),cv2.COLOR_BGR2GRAY); H,W=g.shape
    m=np.zeros_like(g); m[int(y0*H):int(y1*H),int(x0*W):int(x1*W)]=255
    return orb.detectAndCompute(g,m)
for p in sys.argv[4:]:
    i,j=map(int,p.split('-')); (ka,da),(kb,db)=kp(i),kp(j)
    if da is None or db is None: print(p,'no features'); continue
    mt=bf.match(da,db); P=np.float32([ka[x.queryIdx].pt for x in mt]); Q=np.float32([kb[x.trainIdx].pt for x in mt])
    M,mask=cv2.estimateAffinePartial2D(P,Q,method=cv2.RANSAC,ransacReprojThreshold=3) if len(mt)>=4 else (None,None)
    if M is None: print(p,'fit failed',len(mt)); continue
    print(f'{sh} {p:6s} matches {len(mt):4d} inliers {int(mask.sum()):4d} scale {np.hypot(M[0,0],M[1,0]):.2f} rot {np.degrees(np.arctan2(M[1,0],M[0,0])):5.1f} tx {M[0,2]:6.0f} ty {M[1,2]:6.0f}')
