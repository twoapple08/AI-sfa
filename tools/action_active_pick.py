"""동작 정답 추가 뽑기(능동 학습): T03으로 학습한 3D 랜덤 포레스트가 드문 동작(공격·점프·막기·피격)일 확률이 높은 창을 동작마다 120개, 무작위 160개를 뽑는다.

사용: python tools/action_active_pick.py <서버 data 폴더> <애니 3D 폴더> <출력 행 csv> → tools/action_sheets.py --all --tag T04 로 시트를 만든다.
T02·T03 구간과 같은 영상에서 24프레임 안이면 뺀다. 같은 영상 선택끼리도 24프레임 띄운다.
"""
import sys,csv,numpy as np
sys.path.insert(0,'tools');import action_classifier as ac
from collections import defaultdict
from sklearn.ensemble import RandomForestClassifier
D,ANI,OUT=sys.argv[1:4]
CL=['공격','막기·회피','피격','이동','점프·공중','쓰러짐·누움','대기','기타'];RARE=['공격','점프·공중','막기·회피','피격']
def feat(q): return ac.anime_window(ANI,q['애니메이터'],q['post_id'],int(q['시작프레임']),int(q['길이']))
L={r['시트']:r for r in csv.DictReader(open(D+'/T03/T03_동작/T03_목록.csv',encoding='utf-8-sig'))}
X,Y=[],[]
for r in csv.DictReader(open('data/style_kb/ai_results/gpt_T03_2026-10-22.csv',encoding='utf-8-sig')):
    if r['동작'] in CL and '뼈대 틀림' not in r['메모']:
        f=feat(L[r['시트']])
        if f is not None and np.isfinite(f).all(): X.append(f);Y.append(r['동작'])
m=RandomForestClassifier(500,min_samples_leaf=2,class_weight='balanced',random_state=0).fit(np.array(X),np.array(Y))
ex=defaultdict(list)
for p in [D+'/T03/T03_동작/T03_목록.csv',D+'/gpt_T02/T02_목록.csv']:
    for r in csv.DictReader(open(p,encoding='utf-8-sig')): ex[r['post_id']].append(int(r['시작프레임']))
rows=[r for r in csv.DictReader(open(D+'/pose_actions_all.csv',encoding='utf-8')) if r['애니메이터'] in ('yutaka_nakamura','nian41')
      and all(abs(int(r['시작프레임'])-s)>=24 for s in ex[r['post_id']])]
rng=np.random.default_rng(4);cand=[rows[i] for i in rng.choice(len(rows),min(3000,len(rows)),replace=False)]
F,keep=[],[]
for r in cand:
    f=feat(r)
    if f is not None and np.isfinite(f).all(): F.append(f);keep.append(r)
P=m.predict_proba(np.array(F));ci={c:i for i,c in enumerate(m.classes_)}
chosen=set()
for c in RARE:
    order=np.argsort(-P[:,ci[c]])
    n=0
    for i in order:
        if i not in chosen: chosen.add(int(i));n+=1
        if n>=120: break
rest=[i for i in range(len(keep)) if i not in chosen]
chosen|=set(int(i) for i in rng.choice(rest,160,replace=False))
# 같은 영상 겹침 줄이기: 같은 post_id에서 24프레임 안 중복 제거
sel,seen=[],defaultdict(list)
for i in sorted(chosen):
    r=keep[i];s=int(r['시작프레임'])
    if all(abs(s-t)>=24 for t in seen[r['post_id']]): sel.append(r);seen[r['post_id']].append(s)
with open(OUT,'w',encoding='utf-8',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(sel[0].keys()));w.writeheader();w.writerows(sel)
print('후보',len(keep),'선택',len(sel))
