#!/usr/bin/env python3
"""영상 LoRA 컷 시트(GPT 움직임 태깅용, 2026-10-27 2판): 모든 장 번호 + 홀드 표시(= 같은 그림: 10 넘게 다른 픽셀 0.05% 미만, ~ 거의 같음: 3% 미만·평균 차 1.5 미만).
1판의 평균 차 2.0 기준은 3장 리듬의 새 그림까지 홀드로 표시했다(GPT 시험 30에서 s0056·s0083·s0293 지적). 15장씩 b## 폴더로 나눈다. 원본 그림이라 결과는 Drive·scratch만."""
import csv,os,json,cv2,numpy as np
S='/tmp/claude-0/-home-user/6f3d02b3-1633-5b44-bb76-a14a91a6f8f0/scratchpad'
cap=csv.DictReader(open(S+'/wanlora/captions.csv',encoding='utf-8'))
train={r['shot'] for r in cap}
done={json.loads(l)['shot'] for l in open('data/style_kb/ai_results/gpt_SHOT_MOTION_30_2026-10-27.jsonl',encoding='utf-8')}
shots=[s for s in csv.DictReader(open(S+'/nk_shots/shots.csv',encoding='utf-8')) if s['id'] in train and s['id'] not in done]
out=S+'/nk_sheets_all'; os.makedirs(out,exist_ok=True)
for k,s in enumerate(shots):
    batch=f"b{k//15+1:02d}"; os.makedirs(f"{out}/{batch}",exist_ok=True)
    c=cv2.VideoCapture(S+'/nk_src/'+s['원본']); c.set(1,int(s['시작']))
    fr=[c.read()[1] for _ in range(int(s['장수']))]; fr=[f for f in fr if f is not None]
    cells=[]; prev=None
    for i,f in enumerate(fr):
        g=cv2.cvtColor(cv2.resize(f,(427,240),interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY).astype(np.int16)
        mark=''
        if prev is not None:
            d=np.abs(g-prev); p=(d>10).mean()*100; m=d.mean()
            mark='  =' if p<0.05 else ('  ~' if (p<3 and m<1.5) else '')
        prev=g
        t=cv2.copyMakeBorder(cv2.resize(f,(256,144),interpolation=cv2.INTER_AREA),18,0,0,0,cv2.BORDER_CONSTANT,value=(30,30,30))
        col=(0,255,255) if mark=='  =' else ((0,170,255) if mark else (255,255,255))
        cv2.putText(t,f"{i}{mark}",(4,13),0,0.45,col,1,cv2.LINE_AA); cells.append(t)
    while len(cells)%8: cells.append(np.zeros_like(cells[0]))
    sheet=np.vstack([np.hstack(cells[j:j+8]) for j in range(0,len(cells),8)])
    hdr=np.zeros((28,sheet.shape[1],3),np.uint8)
    cv2.putText(hdr,f"{s['id']}  {len(fr)} frames  (0-based)  '=' same drawing  '~' nearly same",(6,20),0,0.6,(255,255,255),1,cv2.LINE_AA)
    cv2.imwrite(f"{out}/{batch}/{s['id']}.jpg",np.vstack([hdr,sheet]),[cv2.IMWRITE_JPEG_QUALITY,85])
print(len(shots),'sheets in',len(os.listdir(out)),'batches')
