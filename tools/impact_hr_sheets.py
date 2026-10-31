# 2026-10-20 임팩트 전수 분류용 일회성 스크립트. 경로는 /home/user/imp 작업 폴더 기준(docs/IMPACT-CLASSIFY-RESULT-2026-10-20.md 참고).
import csv,subprocess,collections,os
from PIL import Image,ImageDraw
T=dict(l.rstrip('\n').split('\t')[:2] for l in open('/home/user/impact_targets.tsv'))
R=[o for o in csv.DictReader(open('/home/user/imp/judged_final.csv')) if o['verdict'].startswith('맞음') or o['verdict']=='애매']
R.sort(key=lambda o:(o['post_id'],int(o['start'])))
by=collections.defaultdict(list)
for i,o in enumerate(R): o['i']=i; by[o['post_id']].append(o)
os.makedirs('/home/user/imp/HR/f',exist_ok=True)
for p,L in by.items():
    fs=sorted({(int(o['start'])+int(o['end']))//2 for o in L})
    sel='+'.join(f'eq(n\\,{f})' for f in fs)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',T[p],'-vf',f"select='{sel}',scale=480:270",'-vsync','0','-y',f'/home/user/imp/HR/f/{p}_%04d.png'])
    for k,f in enumerate(fs):
        for o in L:
            if (int(o['start'])+int(o['end']))//2==f: o['img']=f'/home/user/imp/HR/f/{p}_{k+1:04d}.png'
W,H,C,RW=480,270,4,3
sheets=[R[i:i+C*RW] for i in range(0,len(R),C*RW)]
w=csv.writer(open('/home/user/imp/HR/index.csv','w',newline='')); w.writerow(['sheet','cell','key','verdict','medium_before'])
for s,S in enumerate(sheets,1):
    im=Image.new('RGB',(W*C,(H+18)*RW),'white'); d=ImageDraw.Draw(im)
    for j,o in enumerate(S):
        x,y=(j%C)*W,(j//C)*(H+18)
        if os.path.exists(o.get('img','')): im.paste(Image.open(o['img']),(x,y+18))
        d.text((x+4,y+3),f"{j+1}  {o['key']}",fill='black')
        w.writerow([s,j+1,o['key'],o['verdict'],o['medium']])
    im.save(f'/home/user/imp/HR/sheet_{s:03d}.png')
print(len(R),len(sheets))
