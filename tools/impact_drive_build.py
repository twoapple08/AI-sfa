# 2026-10-20 임팩트 전수 분류용 일회성 스크립트. 경로는 /home/user/imp 작업 폴더 기준(docs/IMPACT-CLASSIFY-RESULT-2026-10-20.md 참고).
import csv,os,shutil,collections
from PIL import Image
I='/home/user/imp'; OUT=f'{I}/drive/05_임팩트 프레임 분류'
shutil.rmtree(f'{I}/drive',ignore_errors=True)
sf={r['post_id']:r for r in csv.DictReader(open('/home/user/AI-sfa/data/style_kb/source_format_2026-10-20.csv'))}
loc={}
for d in ('R1','R2','R3','M4','S0','S1','S2'):
    if not os.path.exists(f'{I}/{d}/index.csv'): continue
    for r in csv.DictReader(open(f'{I}/{d}/index.csv')): loc.setdefault(r['key'],(d,int(r['row']),12 if d=='M4' else 10))
cache={}
def strip(key,dst):
    d,row,rp=loc[key]; sh=(row-1)//rp+1; y=((row-1)%rp)*96
    p=f'{I}/{d}/sheet_{sh:03d}.png'
    if p not in cache: cache.clear(); cache[p]=Image.open(p).convert('RGB')
    im=cache[p]; box=im.crop((0,y,im.width,y+96))
    # 오른쪽 흰 여백 자르기
    bb=Image.eval(box,lambda v:255-v).getbbox(); box=box.crop((0,0,bb[2] if bb else im.width,96))
    box.save(dst)
out=list(csv.DictReader(open(f'{I}/judged_final.csv')))
out.sort(key=lambda o:(o['post_id'],int(o['start'])))
rows=[];miss=[]
for o in out:
    v=o['verdict']; an=sf[o['post_id']]['animator']
    pen=o.get('medium2')=='연필' and o.get('pencil_strength') in ('2','3')
    if v=='맞음_단색섬광': top='임팩트 프레임 맞음/단색섬광'
    elif v in ('맞음_실루엣','맞음_옆에서찾음'): top='임팩트 프레임 맞음/실루엣이미지'
    elif v=='애매': top='임팩트 프레임 애매'
    else: top='임팩트 프레임 아님'
    tag=''.join(t for t,c in (('(연필)',pen),('(옆에서찾음)',v=='맞음_옆에서찾음'),('(옆에실제)',v=='아님_옆에실제'),('(자동)',o['by'].startswith('자동'))) if c)
    name=f"{an}_{o['post_id']}_f{o['start']}-{o['end']}{tag}"
    d=f'{OUT}/{top}/{an}/{name}'; os.makedirs(d,exist_ok=True)
    if o['key'] in loc: strip(o['key'],f'{d}/문맥띠_앞3_후보_뒤3.png')
    else: miss.append(o['key'])
    if top!='임팩트 프레임 아님':
        fd=f"{I}/FR/{o['post_id']}"
        for f in range(int(o['start']),int(o['end'])+1):
            s=f'{fd}/f{f:05d}.png'
            if os.path.exists(s): os.link(s,f'{d}/f{f:05d}.png')
    rows.append({'drive_folder':f'{top}/{an}/{name}','animator':an,'post_id':o['post_id'],'year':sf[o['post_id']]['year'],'frames':f"{o['start']}-{o['end']}",'n':o['n'],
      'verdict':v,'judged_by':o['by'],'reason':o['reason'],'adjacent_cells':o['adjacent_cells'],'medium_strip':o['medium'],'medium_hr':o.get('medium2',''),'pencil_strength':o.get('pencil_strength',''),'medium_note':o.get('medium_note','')})
w=csv.DictWriter(open(f'{OUT}/임팩트_판정표.csv','w',newline='',encoding='utf-8-sig'),fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
P=[r for r in rows if r['pencil_strength'] in ('2','3') and r['medium_hr']=='연필']
w=csv.DictWriter(open(f'{OUT}/연필_임팩트_목록.csv','w',newline='',encoding='utf-8-sig'),fieldnames=list(rows[0])); w.writeheader(); w.writerows(P)
print('rows',len(rows),'nostrip',len(miss),miss[:5]); print(collections.Counter(r['drive_folder'].split('/')[0]+'/'+r['drive_folder'].split('/')[1] for r in rows)); print('pencil',len(P))
