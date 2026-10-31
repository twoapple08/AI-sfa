# 2026-10-20 임팩트 전수 분류용 일회성 스크립트. 경로는 /home/user/imp 작업 폴더 기준(docs/IMPACT-CLASSIFY-RESULT-2026-10-20.md 참고).
import csv,subprocess,collections,os,sys
from concurrent.futures import ThreadPoolExecutor
T=dict(l.rstrip('\n').split('\t')[:2] for l in open('/home/user/impact_targets.tsv'))
R=[o for o in csv.DictReader(open('/home/user/imp/judged_final.csv')) if o['verdict'].startswith('맞음') or o['verdict']=='애매']
def pick(s,e,k=24):
    n=e-s+1
    return list(range(s,e+1)) if n<=k else sorted({s+round(i*(n-1)/(k-1)) for i in range(k)})
by=collections.defaultdict(set)
for o in R: by[o['post_id']]|=set(pick(int(o['start']),int(o['end'])))
D='/home/user/imp/FR'
def run(p):
    fs=sorted(by[p]); os.makedirs(f'{D}/{p}',exist_ok=True)
    sel='+'.join(f'eq(n\\,{f})' for f in fs)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',T[p],'-vf',f"select='{sel}',scale=960:-2",'-vsync','0','-y',f'{D}/{p}/tmp_%05d.png'])
    for k,f in enumerate(fs):
        a=f'{D}/{p}/tmp_{k+1:05d}.png'
        if os.path.exists(a): os.rename(a,f'{D}/{p}/f{f:05d}.png')
    return p,len(fs),len(os.listdir(f'{D}/{p}'))
with ThreadPoolExecutor(4) as ex:
    bad=[r for r in ex.map(run,list(by)) if r[1]!=r[2]]
print(len(by),'bad',bad)
