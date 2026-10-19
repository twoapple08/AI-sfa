"""impact_xclip.py 출력에 좁힌 정의 3분류(유력/재검사/아님유력)를 붙인다. 사용: python tools/impact_narrow_classify.py <xclip.csv> [out.csv]
점수 s = logit(xclip_pos)/3 + (ref_sim-0.55)/0.05 - 2*(cont>=0.6). 유력: s>=3·연속 아님. 아님유력: s<0이면서 (cont>=0.6 또는 색 남음). 나머지 재검사.
보정(2026-10-19, 사용자 판정·확정 86구간): 유력 24 중 아님 1, 아님유력 15 중 임팩트 0(반반 2)."""
import csv,sys,math,collections
R=list(csv.DictReader(open(sys.argv[1])))
f=lambda r,k:float(r[k] or 0)
def sc(r):
    x=min(max(f(r,'xclip_pos'),1e-4),1-1e-4); return math.log(x/(1-x))/3+(f(r,'ref_sim')-0.55)/0.05-(2 if f(r,'cont')>=0.6 else 0)
def cls(r):
    s=sc(r); c6=f(r,'cont')>=0.6; col=f(r,'mono')<0.85 and f(r,'invert')<0.5
    if s>=3 and not c6: return '유력',s,['X-CLIP·예시 유사도 높음']
    if s<0 and (c6 or col):
        return '아님유력',s,['X-CLIP·예시 유사도 낮음']+(['앞뒤와 이어짐(동화)'] if c6 else [])+(['색이 남음'] if col else [])
    w=['임팩트 쪽 기울기' if s>=1 else '아님 쪽 기울기' if s<0 else '중간']
    if s>=3 and c6: w.append('유사도 높으나 앞뒤와 이어짐(구간 어긋남 가능)')
    return '재검사',s,w
for r in R:
    c,s,w=cls(r); r['narrow_class']=c; r['narrow_score']=round(s,2); r['narrow_reason']='; '.join(w)
if __name__=='__main__':
    pos={'A_impact','T_confirmed'}; neg={'A_not','A_not_adjacent','T_not_impact'}
    print(collections.Counter((('pos' if r['label'] in pos else 'neg' if r['label'] in neg else r['label'] or 'unl'),r['narrow_class']) for r in R))
    if len(sys.argv)>2:
        with open(sys.argv[2],'w',newline='',encoding='utf-8') as g:
            w=csv.DictWriter(g,fieldnames=list(R[0])); w.writeheader(); w.writerows(R)
