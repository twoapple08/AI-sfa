"""학습 장 전수 자동 점검(11-05 사용자 '학습에 사용된 것 중 오류 난 건 없는지'): 학습 장(train_mask)마다
빈 관절 · 화면 끝 몰림(목 y<6% 또는 골반 y>97%) · 몸통 길이 급변(구간 중앙 0.5배 미만/1.8배 초과) · 뼈 길이 이상(구간 중앙 대비 0.3–1.8 밖) ·
장 사이 튐(골반 기준 자세 변화 > 몸통 1.5, 스미어 표시 장 제외)을 센다. 자동 표시는 후보일 뿐이고 원본 겹침 눈 판정으로 가른다
(11-05: 스타일 층 심한 후보 89장 중 실제 오류 2장 — 빠른 동작·원근·작은 인물이 대부분).
사용: python tools/stage2_audit.py <stage2_easy 작업 폴더>
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json, glob, math, collections
import numpy as np
S = sys.argv[1] if len(sys.argv) > 1 else "."
BONES=[('neck','head_t'),('neck','elb_r'),('elb_r','wri_r'),('neck','elb_l'),('elb_l','wri_l'),('pelvis','kne_r'),('kne_r','ank_r'),('pelvis','kne_l'),('kne_l','ank_l')]
def L(J,n,p,q,asp=0.5625): return math.hypot(J[q][n][0]-J[p][n][0],(J[q][n][1]-J[p][n][1])*asp)
def audit(ir,name,out):
    a=ir['actors'][0]; J=a['joints']; N=ir['frames']; m=a.get('train_mask') or [True]*N
    sm=a.get('smear_mark') or [False]*N
    T=np.array([L(J,n,'neck','pelvis') if J['neck'][n] and J['pelvis'][n] else np.nan for n in range(N)])
    med=np.nanmedian(T)
    BL={b:np.nanmedian([L(J,n,*b)/T[n] for n in range(N) if J[b[0]][n] and J[b[1]][n] and T[n]>0]) for b in BONES}
    for n in range(N):
        if not m[n]: continue
        miss=[k for k in J if J[k][n] is None]
        if miss: out['빈 관절'].append((name,n,miss[:3])); continue
        if J['neck'][n][1]<6 or J['pelvis'][n][1]>97: out['화면 끝 몰림'].append((name,n))
        if T[n]<0.5*med or T[n]>1.8*med: out['몸통 길이 급변'].append((name,n,round(T[n]/med,2)))
        for b in BONES:
            r=L(J,n,*b)/T[n]/BL[b] if T[n]>0 and BL[b]>0 else 1
            if r>1.8 or r<0.3:
                out['뼈 길이 이상'].append((name,n,b[1],round(r,2)))
        if n>0 and m[n-1] and not sm[n] and all(J[k][n-1] for k in J):
            P0,P1=J['pelvis'][n-1],J['pelvis'][n]
            d=max(math.hypot((J[k][n][0]-P1[0])-(J[k][n-1][0]-P0[0]),((J[k][n][1]-P1[1])-(J[k][n-1][1]-P0[1]))*0.5625) for k in J)/T[n]
            if d>1.5: out['장 사이 튐(몸 기준)'].append((name,n,round(d,2)))
if __name__ == '__main__':
    out = collections.defaultdict(list)
    for p in sorted(glob.glob(S + '/out/*.json')):
        if p.endswith('summary.json'): continue
        audit(json.load(open(p)), p.rsplit('/', 1)[1][:-5], out)
    for k, v in out.items(): print(k, len(v), v[:12])
