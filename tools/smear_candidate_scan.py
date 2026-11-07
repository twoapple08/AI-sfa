"""연속 애니 프레임의 색 경계·가는 획·시간 변화 기반 스미어 후보 탐색. 의미 확정/학습 아님."""
import argparse,json,hashlib
from pathlib import Path
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]


def color_masks(rgb):
    a=rgb.astype(np.float32);r,g,b=(a[:,:,i] for i in range(3))
    hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV);s=hsv[:,:,1]
    return {'red':((r>1.22*g)&(r>1.10*b)&(r>45)&(s>45)).astype(np.uint8),
            'blue':((b>1.13*r)&(g>1.06*r)&(b>40)&(s>40)).astype(np.uint8)}


def scan(rgb,previous=None,following=None,threshold=.28):
    if rgb.ndim!=3 or rgb.shape[2]!=3 or rgb.dtype!=np.uint8:raise ValueError('uint8 RGB 입력 필요')
    if any(x is not None and x.shape!=rgb.shape for x in [previous,following]):raise ValueError('이웃 프레임 크기 불일치')
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);grayf=gray.astype(np.float32)
    temporal=np.zeros(gray.shape,np.float32)
    for other in [previous,following]:
        if other is not None:temporal=np.maximum(temporal,np.abs(grayf-cv2.cvtColor(other,cv2.COLOR_RGB2GRAY).astype(np.float32)))
    scale=rgb.shape[1]/1152
    odd=lambda n:max(3,int(round(n*scale))|1)
    window=odd(17);box=lambda a:cv2.boxFilter(a.astype(np.float32),-1,(window,window),normalize=True)
    change=np.minimum(1,box(temporal)/30)
    gx=cv2.Sobel(grayf,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(grayf,cv2.CV_32F,0,1,ksize=3)
    xx,yy,xy=box(gx*gx),box(gy*gy),box(gx*gy)
    coherence=np.sqrt((xx-yy)**2+4*xy*xy)/(xx+yy+1e-5)
    edges=(cv2.Canny(gray,55,130)>0).astype(np.float32);detail=np.minimum(1,box(edges)/.2)
    candidates=[]
    for actor,mask in color_masks(rgb).items():
        # 내부 음영/검은 옷 주름을 톱니 경계로 오인하지 않도록 바깥 윤곽만 사용한다.
        close=odd(3);joined=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((close,close),np.uint8))
        contours,_=cv2.findContours(joined,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        silhouette=np.zeros_like(mask)
        for contour in contours:
            if cv2.contourArea(contour)>=max(12,12*scale*scale):cv2.drawContours(silhouette,[contour],-1,1,-1)
        mask=silhouette
        teeth=np.zeros(mask.shape,np.float32)
        for size,weight in [(3,.3),(7,.7)]:
            k=odd(size);opened=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k)))
            teeth+=weight*(mask-opened)
        # 가는 색 돌기의 밀집과 국소 평행선을 후보로 쓴다. 움직임만으로 선택하지 않는다.
        rough=np.minimum(1,box(teeth)/.045)
        score=rough*(.40+.35*coherence+.25*detail)*(.6+.4*change)
        seeds=((score>=threshold)&(teeth>.1)).astype(np.uint8)
        size=odd(7);groups=cv2.dilate(seeds,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(size,size)))
        count,labels,stats,_=cv2.connectedComponentsWithStats(groups,8)
        for i in range(1,count):
            x,y,w,h,area=map(int,stats[i]);pixels=(labels[y:y+h,x:x+w]==i)&(seeds[y:y+h,x:x+w]>0);support=int(pixels.sum())
            if support<max(12,round(12*scale*scale)) or max(w,h)<5*scale:continue
            values=score[y:y+h,x:x+w][pixels]
            region_score=float(np.mean(values))*(.3+.7*min(1,support/(50*scale*scale)))
            if region_score<.45:continue
            candidates.append(dict(actor=actor,box=[max(0,x-4),max(0,y-4),min(rgb.shape[1],x+w+4),min(rgb.shape[0],y+h+4)],
                                   score=region_score,peak=float(values.max()),support_pixels=support,
                                   roughness=float(np.mean(rough[y:y+h,x:x+w][pixels])),
                                   coherence=float(np.mean(coherence[y:y+h,x:x+w][pixels])),
                                   temporal_change=float(np.mean(change[y:y+h,x:x+w][pixels])),status='needs_review'))
    return sorted(candidates,key=lambda c:c['score'],reverse=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--frames',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source-start',type=int,default=0);parser.add_argument('--threshold',type=float,default=.28);args=parser.parse_args()
    if not 0<args.threshold<1:parser.error('후보 임계값은 0과 1 사이')
    dest=args.output.resolve()
    if dest==ROOT or ROOT in dest.parents or dest.exists():parser.error('새 비공개 출력 경로 필요')
    files=sorted(args.frames.glob('*.png'))
    if not files:parser.error('PNG 프레임 없음')
    cv2.setNumThreads(2)
    read=lambda p:cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB)
    prev=None;current=read(files[0]);following=read(files[1]) if len(files)>1 else None;rows=[]
    for i,path in enumerate(files):
        candidates=scan(current,prev,following,args.threshold);rows.append(dict(frame_index=i,source_index=args.source_start+i,file=path.name,pixel_sha256=hashlib.sha256(current.tobytes()).hexdigest(),candidates=candidates))
        prev,current=current,following;following=read(files[i+2]) if i+2<len(files) else None
        if (i+1)%60==0:print('scanned',i+1,flush=True)
    dest.mkdir(parents=True);report=dict(schema='smear-candidate-scan/1',frames=len(rows),candidate_frames=sum(bool(r['candidates']) for r in rows),candidate_regions=sum(len(r['candidates']) for r in rows),threshold=args.threshold,method='colored thin protrusions + local contour roughness + edge coherence + neighbor-frame change',source_palette='red/blue biased heuristic',semantic_smear_detection_verified=False,probability_calibrated=False,training_ready=False,rows=rows)
    (dest/'candidates.private.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print({k:v for k,v in report.items() if k!='rows'})


if __name__=='__main__':main()
