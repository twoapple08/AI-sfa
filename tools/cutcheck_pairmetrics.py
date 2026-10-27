# 인접 장(또는 지정 쌍)의 연속성 측정: 회색 NCC, 색 히스토그램 상관, ORB 특징 + RANSAC 유사변환(내점 수·배율·이동).
import sys,cv2,numpy as np,glob
S=sys.argv[1]
orb=cv2.ORB_create(2000); bf=cv2.BFMatcher(cv2.NORM_HAMMING,crossCheck=True)
def load(sh,i): return cv2.imread(f'{S}/fr/{sh}/{i:03d}.png')
def m(a,b):
    ga,gb=[cv2.cvtColor(x,cv2.COLOR_BGR2GRAY) for x in (a,b)]
    za,zb=[(g.astype(float)-g.mean())/(g.std()+1e-6) for g in (ga,gb)]
    ncc=(za*zb).mean()
    ha,hb=[cv2.calcHist([cv2.cvtColor(x,cv2.COLOR_BGR2HSV)],[0,1,2],None,[8,4,4],[0,180,0,256,0,256]) for x in (a,b)]
    hc=cv2.compareHist(ha,hb,cv2.HISTCMP_CORREL)
    ka,da=orb.detectAndCompute(ga,None); kb,db=orb.detectAndCompute(gb,None)
    inl,sc,tx,ty=0,0,0,0
    if da is not None and db is not None and len(ka)>8 and len(kb)>8:
        mt=bf.match(da,db)
        if len(mt)>=8:
            p=np.float32([ka[x.queryIdx].pt for x in mt]); q=np.float32([kb[x.trainIdx].pt for x in mt])
            M,mask=cv2.estimateAffinePartial2D(p,q,method=cv2.RANSAC,ransacReprojThreshold=4)
            if M is not None:
                inl=int(mask.sum()); sc=float(np.hypot(M[0,0],M[1,0])); tx,ty=M[0,2],M[1,2]
    return ncc,hc,inl,sc,tx,ty
sh=sys.argv[2]
n=len(glob.glob(f'{S}/fr/{sh}/*.png'))
pairs=[tuple(map(int,p.split('-'))) for p in sys.argv[3:]] or [(i,i+1) for i in range(n-1)]
print(f'{sh}  pair    NCC   hist  inl  scale   tx    ty')
for i,j in pairs:
    ncc,hc,inl,sc,tx,ty=m(load(sh,i),load(sh,j))
    print(f'{sh} {i:2d}-{j:2d} {ncc:6.2f} {hc:6.2f} {inl:4d} {sc:5.2f} {tx:6.0f} {ty:6.0f}')
