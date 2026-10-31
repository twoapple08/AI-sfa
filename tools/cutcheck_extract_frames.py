# 시트와 같은 방식(set(1,a) 뒤 차례 읽기)으로 장을 뽑고, 시트 칸과 대조해 정렬을 확인한다.
import csv,sys,os,cv2,numpy as np,glob
S=sys.argv[1]; R=sys.argv[2]  # scratch, repo csv
rows={r['id']:r for r in csv.DictReader(open(R,encoding='utf-8'))}
for sh in sys.argv[3:]:
    r=rows[sh]; sheet=cv2.imread(glob.glob(f'{S}/sheets/*_{sh}.jpg')[0])
    c=cv2.VideoCapture(f"{S}/src/{r['원본']}"); c.set(1,int(r['시작']))
    fr=[c.read()[1] for _ in range(int(r['장수']))]; fr=[f for f in fr if f is not None]
    os.makedirs(f'{S}/fr/{sh}',exist_ok=True); errs=[]
    for i,f in enumerate(fr):
        cv2.imwrite(f'{S}/fr/{sh}/{i:03d}.png',cv2.resize(f,(640,360),interpolation=cv2.INTER_AREA))
        y=28+(i//8)*162+18; x=(i%8)*256
        t=sheet[y:y+144,x:x+256].astype(float); g=cv2.resize(f,(256,144),interpolation=cv2.INTER_AREA).astype(float)
        e=np.abs(t-g).mean()
        # 앞뒤 한 장 어긋남과 비교
        alt=[np.abs(t-cv2.resize(fr[j],(256,144),interpolation=cv2.INTER_AREA).astype(float)).mean() for j in (i-1,i+1) if 0<=j<len(fr)]
        errs.append((e,min(alt) if alt else 99))
    bad=[i for i,(e,a) in enumerate(errs) if e>a+0.5]
    print(sh,len(fr),'frames; mean err %.2f; frames where neighbour fits better: %s'%(np.mean([e for e,_ in errs]),bad), fr[0].shape)
