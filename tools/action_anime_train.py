"""애니 GPT 판정(T03 등)으로 동작 분류기를 직접 학습하고 T02로 평가한다(8동작).

사용: python tools/action_anime_train.py <서버 data 폴더> <애니 3D 폴더(lift_apply 출력)> <3d|2d|both>
- data 폴더에 T03/T03_동작/T03_목록.csv, gpt_T02/T02_목록.csv, tracks_all/ 이 있어야 한다(원본 유래라 저장소 밖).
- 정답: data/style_kb/ai_results/gpt_T03_2026-10-22.csv(학습), gpt_T02_2026-10-21.csv(평가). '판단 불가'·'뼈대 틀림'은 뺀다.
- 특징: 3d = action_classifier.feats(관절 쌍 거리·속도, 방향 무관), 2d = pose_actions 지표 + 몸통 기울기 범위·골반 수직 변위·화면 몸 크기 변화.
- 분류기: 로지스틱(C=0.1), 랜덤 포레스트, 그레이디언트 부스팅(모두 class_weight balanced). T03 5겹 교차검증과 T02 일치를 낸다.
결과(2026-10-22, 35000단계 3D·뼈 고정): 3d 랜덤 포레스트 T02 34/67(51%), T03 CV 51%, 다수결 34%. 2d 단독 41~46%, 합침 47~49%.
"""
import sys
import csv
import numpy as np
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import action_classifier as ac  # noqa: E402
import pose_actions as pa  # noqa: E402
from collections import Counter
D=sys.argv[1];ANI=sys.argv[2]
CL=['공격','막기·회피','피격','이동','점프·공중','쓰러짐·누움','대기','기타']
MODE=sys.argv[3]
TR=D+'/tracks_all'
def feat2d(an,pid,st,L):
    """화면 2D: pose_actions 지표 6개 + 몸통 기울기 범위 + 골반 수직 변위(위로 +) + 화면 상 몸 크기 변화."""
    p=os.path.join(TR,an,pid+'.npz')
    if not os.path.exists(p): return None
    z=np.load(p)
    for K,s0,LL in zip(z['kp'],z['start'],z['length']):
        if s0<=st and st+L<=s0+LL:
            W=K[st-s0:st-s0+L]
            ft=pa.feats(W)
            if ft is None: return None
            P=W[:,:17,:2];hip=(P[:,11]+P[:,12])/2;sh=(P[:,5]+P[:,6])/2
            size=np.nanmedian(np.linalg.norm(sh-hip,axis=1))
            ang=np.degrees(np.arctan2(np.abs((sh-hip)[:,0]),-(sh-hip)[:,1]))
            dy=-(hip[-1,1]-hip[0,1])/size if np.isfinite(hip[[0,-1],1]).all() else 0
            sz=np.linalg.norm(sh-hip,axis=1)/size
            return np.r_[list(ft.values()),np.nanmax(ang)-np.nanmin(ang),dy,np.nanmax(sz)-np.nanmin(sz)]
    return None
def load(lst,gpt):
    L={r['시트']:r for r in csv.DictReader(open(lst,encoding='utf-8-sig'))}
    X,Y=[],[]
    for r in csv.DictReader(open(gpt,encoding='utf-8-sig')):
        if r['동작'] not in CL or '뼈대 틀림' in r.get('메모','') or r['시트'] not in L: continue
        q=L[r['시트']];f=ac.anime_window(ANI,q['애니메이터'],q['post_id'],int(q['시작프레임']),int(q['길이']))
        g=feat2d(q['애니메이터'],q['post_id'],int(q['시작프레임']),int(q['길이']))
        if MODE=='2d': f=g
        elif MODE=='both': f=None if (f is None or g is None) else np.r_[f,g]
        if f is not None and np.isfinite(f).all(): X.append(f);Y.append(r['동작'])
    return np.array(X),np.array(Y)
Xtr,Ytr=load(D+'/T03/T03_동작/T03_목록.csv','data/style_kb/ai_results/gpt_T03_2026-10-22.csv')
Xte,Yte=load(D+'/gpt_T02/T02_목록.csv','data/style_kb/ai_results/gpt_T02_2026-10-21.csv')
print('train',len(Ytr),dict(Counter(Ytr)));print('test',len(Yte),dict(Counter(Yte)))
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_predict,StratifiedKFold
maj=Counter(Ytr).most_common(1)[0][0]
print('다수결(대기) T02',round(float((Yte==maj).mean()),3))
ms={'logreg':make_pipeline(StandardScaler(),LogisticRegression(max_iter=3000,C=0.1,class_weight='balanced')),
    'rf':RandomForestClassifier(500,min_samples_leaf=2,class_weight='balanced',random_state=0),
    'hgb':HistGradientBoostingClassifier(max_iter=200,learning_rate=0.05,class_weight='balanced',random_state=0)}
for n,m in ms.items():
    cv=cross_val_predict(m,Xtr,Ytr,cv=StratifiedKFold(5,shuffle=True,random_state=0))
    m.fit(Xtr,Ytr);p=m.predict(Xte)
    print(n,'T03 5겹 CV',round(float((cv==Ytr).mean()),3),'T02',int((p==Yte).sum()),'/',len(Yte),round(float((p==Yte).mean()),3))
    if n=='rf':
        print(' T02 혼동 상위',Counter((a,b) for a,b in zip(Yte,p) if a!=b).most_common(6))
        print(' 클래스별 T02 맞음',{c:f"{int(((p==c)&(Yte==c)).sum())}/{int((Yte==c).sum())}" for c in CL})
