#!/usr/bin/env python3
"""사용자 판정용 원 해상도 묶음 생성: 구간 앞뒤 2프레임 PNG + 1/4속 영상 + 판정표.csv → Drive 업로드.

사용: python tools/make_judge_bundle.py <list.csv> <작업폴더> <Drive 대상 폴더>
list.csv 열: post_id,tag,frames,basis (data/style_kb/judge_lists/). 원본은 Sakugabooru에서 md5 대조로 받고 쓴 뒤 지운다.
"""
import csv,hashlib,os,subprocess,sys
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV={**os.environ,'RCLONE_LOG_LEVEL':'ERROR'}
lst,B,dest=sys.argv[1:4]
md5={}
for x in csv.DictReader(open(R+'/data/catalog.csv',encoding='utf-8-sig')): md5[x['post_id']]=(x['md5'],x['ext'])
for x in csv.DictReader(open(R+'/data/sakuga/candidates/candidates_catalog.csv',encoding='utf-8-sig')): md5.setdefault(x['post_id'],(x['md5'],x['ext']))
L=list(csv.DictReader(open(lst,encoding='utf-8')))
L.sort(key=lambda x:(int(x['post_id']),int(x['frames'].split('-')[0]) if x['frames'][0].isdigit() else -1))
S=B; os.makedirs(B,exist_ok=True); os.makedirs(S+'/dl',exist_ok=True); idx=[]
for n,r in enumerate(L,1):
    pid=r['post_id']; m,ext=md5[pid]; src=f'{S}/dl/{pid}.{ext}'
    row={'no':f'{n:03d}','post_id':pid,'tag':r['tag'],'frames':r['frames'],'folder':'','claude_basis':r['basis'][:120],'user_judgement':'(임팩트/아님/부분)'}
    if not r['frames'][0].isdigit():
        row['folder']='(구간 미지정: 원본 영상 전체를 봐야 함)'; idx.append(row); continue
    if not os.path.exists(src):
        subprocess.run(['curl','-sS','-A','AI-sfa-research/0.1','-o',src,f'https://www.sakugabooru.com/data/{m}.{ext}'],stdin=subprocess.DEVNULL)
        if hashlib.md5(open(src,'rb').read()).hexdigest()!=m: print('MD5FAIL',pid,flush=True); row['folder']='(원본 다운로드 실패)'; idx.append(row); os.remove(src); continue
    a,b=[int(v) for v in (r['frames'].split('-')+[r['frames']])[:2]]; s,e=max(0,a-2),b+2
    d=f'{B}/{n:03d}_{pid}_f{a}-{b}'; os.makedirs(d,exist_ok=True)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',src,'-vf',f'select=between(n\\,{s}\\,{e})','-vsync','0','-start_number',str(s),f'{d}/f%04d.png'])
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',src,'-vf',f'trim=start_frame={max(0,s-12)}:end_frame={e+13},setpts=4*(PTS-STARTPTS)','-an','-c:v','libx264','-crf','16',f'{d}/slow_quarter.mp4'])
    row['folder']=os.path.basename(d); idx.append(row)
    if n==len(L) or L[n]['post_id']!=pid: os.remove(src)
    if n%50==0: print('progress',n,len(L),flush=True)
with open(B+'/판정표.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f,fieldnames=list(idx[0])); w.writeheader(); w.writerows(idx)
r=subprocess.run(['rclone','copy',B,dest,'--transfers','8','--exclude','dl/**'],env=ENV)
print('DONE',len(idx),'upload_rc',r.returncode,flush=True)
