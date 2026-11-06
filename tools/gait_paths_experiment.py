"""걷기 보존 경로 실험(11-06): 원래 걷기형인 표본만 ② 토큰 왕복 ③ 리듬 보정 ④ 지금 반복 ⑤ 주기 맞춘 반복(+리듬)에 통과시켜 출처별로 센다.
사용: python tools/gait_paths_experiment.py <작업 폴더(hmdb_out/hmdb_ir.jsonl.gz 있는 곳)>"""
import sys,json,gzip,numpy as np,collections
sys.path.insert(0,'tools'); import gait_eval as G, motion_tokens as MT, retime as RT, compose as C
S=sys.argv[1]
def full(ir):
    a=ir['actors'][0]; N=ir['frames']
    for k in ('thickness','hidden','smear'): a.setdefault(k,[[] if k!='thickness' else {} for _ in range(N)])
    return ir
pos=[]
for ir in (json.loads(l) for l in gzip.open(S+'/hmdb_out/hmdb_ir.jsonl.gz','rt',encoding='utf-8')):
    if ir['source']['label'] in ('walk','run'): pos.append(('HMDB',ir['source']['label'],ir))
for c in C.library(None):
    if c['verb'] in ('걷기','달리기') and c['frames']>=8:
        pos.append(('수집SFA','walk' if c['verb']=='걷기' else 'run',dict(frames=c['frames'],aspect=c['aspect'],actors=[dict(joints=c['joints'])])))
crit=lambda m: m and (m['gait_like'] if m['gait_like'] is not None else m['step_like'])
res=collections.defaultdict(collections.Counter); base=collections.Counter(); rows=[]
for src,lab,ir in pos:
    m0=G.metrics(ir)
    if not crit(m0): continue
    key=(src,lab,'주기' if m0['gait_like'] is not None else '짧음(걸음만)'); base[key]+=1
    rt=MT.decode(MT.encode(full(json.loads(json.dumps(ir)))))
    r3=RT.retime(full(json.loads(json.dumps(ir))))
    clip=dict(layer='ref',src='x',verb='걷기',detail='',quality='좋음',frames=ir['frames'],aspect=ir['aspect'],joints=ir['actors'][0]['joints'])
    need=max(48,int(ir['frames']*2.5)); J,F=C._loop(C._norm(clip),ir['frames'],need); r4=dict(frames=F,aspect=0.5625,actors=[dict(joints=J)])
    r5=G.cycle_loop(ir,need)
    paths={'② 토큰 왕복':rt,'③ 리듬 보정':r3,'④ 지금 반복':r4,'⑤ 주기 맞춘 반복':r5,'⑤ + 리듬 보정':RT.retime(full(r5)) if r5 else None}
    for p,x in paths.items():
        # 반복한 결과(④⑤)는 길이가 늘어 주기성을 잴 수 있으므로 gait_like로 판정
        mx=G.metrics(x) if x else None
        ok=bool(mx and (mx['gait_like'] if p.startswith(('④','⑤')) and mx['gait_like'] is not None else crit(mx)))
        res[key][p]+=ok
for k in sorted(base): print(k,'분모',base[k],{p:f"{v}/{base[k]}" for p,v in sorted(res[k].items())})
json.dump({' / '.join(k):dict(n=base[k],**{p:v for p,v in res[k].items()}) for k in base},open(S+'/gait_paths.json','w'),ensure_ascii=False,indent=1)
