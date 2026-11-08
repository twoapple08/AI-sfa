"""원본 프레임에서 스미어 톱니 가닥이 늘어진 방향을 잰다(사용자 확인 스미어 상자 안).

축 = 인물색 마스크에서 열기(9px)로 떼어 낸 가닥 경계의 결(구조 텐서의 작은 고유값 쪽 벡터),
부호 = 몸 덩어리 중심 → 몸에서 먼 가닥 쪽. 일치도(coherence)=(λ1-λ0)/(λ1+λ0).
적용 규칙(2026-11-08): 일치도 >= .30 이거나 사람이 눈으로 확인한 것만 쓴다. 측정 축이 팔 축과 25° 이내면
부호는 팔꿈치→손 바깥쪽(가닥이 팔을 따라 누우면 뿌리 쪽 판단이 불안정: 1036/1037이 서로 반대로 나옴).
원본 프레임·라벨은 비공개이며 이 도구는 그 값을 저장소에 넣지 않는다(방향 단위벡터만 장면 설정에 둔다).
"""
import numpy as np

COHERENCE_MIN=.30
AXIS_SNAP_DEG=25.


def strands_box(mask,box,tip,pad=12,kernel=9):
    import cv2
    H,W=mask.shape;x0,y0,x1,y1=[int(v) for v in box]
    x0=max(0,x0-pad);y0=max(0,y0-pad);x1=min(W,x1+pad);y1=min(H,y1+pad)
    m=(mask[y0:y1,x0:x1]>0).astype(np.uint8)
    if m.sum()<30:return None
    body=cv2.morphologyEx(m,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(kernel,kernel)))
    teeth=(m>0)&(body==0)
    if teeth.sum()<20:return None
    f=cv2.GaussianBlur(m.astype(np.float32),(0,0),1.2)
    gx=cv2.Sobel(f,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(f,cv2.CV_32F,0,1,ksize=3)
    sel=cv2.dilate(teeth.astype(np.uint8),np.ones((3,3),np.uint8))>0
    J=np.array([[np.sum(gx[sel]**2),np.sum(gx[sel]*gy[sel])],[np.sum(gx[sel]*gy[sel]),np.sum(gy[sel]**2)]],float)
    w,v=np.linalg.eigh(J);axis=v[:,0];coh=float((w[1]-w[0])/max(w[1]+w[0],1e-9))
    ys,xs=np.nonzero(teeth);Q=np.stack([xs+x0,ys+y0],1).astype(float)
    if body.sum()>15:
        db=cv2.distanceTransform((body==0).astype(np.uint8),cv2.DIST_L2,3)[ys,xs]
        far=Q[db>=np.percentile(db,60)];by,bx=np.nonzero(body);ref=np.array([bx.mean()+x0,by.mean()+y0]);basis='body'
        s=float(np.sign((far.mean(0)-ref)@axis))
    else:
        s=float(np.sign((Q.mean(0)-np.asarray(tip,float))@axis));basis='tip'
    axis=axis*(s if s!=0 else 1.)
    return dict(dir=axis.tolist(),coherence=coh,teeth=int(teeth.sum()),sign_basis=basis)


def decide(measure,arm,eye_ok=False):
    """측정값 → (사용 여부, 최종 방향, 이유)."""
    if measure is None:return False,None,'no_measure'
    d=np.asarray(measure['dir'],float);arm=np.asarray(arm,float);arm=arm/max(np.linalg.norm(arm),1e-9)
    if measure['coherence']<COHERENCE_MIN and not eye_ok:return False,None,'low_coherence'
    axis_deg=float(np.degrees(np.arccos(min(1.,abs(float(d@arm))))))
    if axis_deg<=AXIS_SNAP_DEG:
        d=d*(1. if d@arm>=0 else -1.);why='along_arm_outward'
    else:why='measured_sign'
    return True,(d/np.linalg.norm(d)).tolist(),why+('_eye' if measure['coherence']<COHERENCE_MIN else '')
