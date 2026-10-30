#!/usr/bin/env python3
"""SFA 오브젝트 단위 채점(2026-10-30, 사용자: "스파는 픽셀로 보는 게 아니라 오브젝트로 보는 거야, 대입하는 거야").
AI가 만든 장과 원본 장의 오브젝트를 하나씩 짝지어(헝가리안) 오브젝트마다 대입한 값을 비교한다.
  짝 비용 = 점 사이 평균 거리(화면 가로 % 단위 — 세로 좌표에 비율을 곱해 화소 비율로). 직선·곡선은 점 순서를 뒤집은 것도 본다. 종류가 다르면 +TYPE_PEN.
  맞음 = 같은 종류 + 평균 점 거리 ≤ tol.
숫자: 맞은 오브젝트(재현율 = 원본 중 맞힌 비율, 정밀도 = AI 것 중 맞은 비율), 평균 점 오차, 색·굵기·글로우 일치, 연결 F1, 면 F1, 배경색, 가림 순서 일치,
perfect(모두 일치 = 같은 영상). GPT 검토(10-30) 반영: 맞는 짝 수 먼저 최대화, 실제 그리는 순서, 원 점 방향·화면 비율, 짝 0개 장도 연결·면 셈.
구조 채점(align=True, 보조 — 10-30 영상을 '크기 무관'으로 잘못 읽어 만든 것. 사용자 뜻은 '일반 그림 도구 말고 스파로 그려라'. 기본은 제자리 비교): AI 그림 전체를 이동 + 같은 비율 확대로
원본에 맞춘 뒤 비교한다(회전은 안 함 — 기울어진 선은 틀림). 맞춘 배율·이동도 돌려준다. align=False는 제자리 비교.
"""
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

TYPE_PEN = 50.0
INVALID = 1e6   # 맞을 수 없는 짝(종류 다름·허용 오차 밖) — 헝가리안이 '맞는 짝 수'를 먼저 최대로 하게(GPT 검토 10-30)
NEED = {'1': 2, '2': 2, '3': 3}


def objs(fr, hwr=0.5625):
    """그리는 순서(레이어 → 연결 묶음 → DrawOrder, 렌더러와 같음)대로 오브젝트 목록. 좌표는 화면 화소 비율로(세로 × 비율) — 원·거리가 비율과 무관하게."""
    import sfa_tokens as K
    out = []
    pid = {}
    for k, (li, a) in enumerate(K.order_objects(None, fr)):
        aps = a.findall('AP')
        for j, p in enumerate(aps):
            pid[p.get('ID')] = (k, j)
        ga = float(a.get('GlowAlpha') or 0)
        glow = None
        if ga > 0 and float(a.get('GlowRadius') or 0) > 0 and float(a.get('GlowThickness') or 0) > 0:
            glow = (round(float(a.get('GlowRadius')), 1), round(float(a.get('GlowThickness')), 1), round(ga if ga > 1 else ga * 255),
                    int(float(a.get('GlowColor') or 0)) & 0xFFFFFF)
        out.append(dict(t=a.get('TypeId'), xy=[(float(p.get('X')), float(p.get('Y')) * hwr) for p in aps],
                        col=int(float(a.get('Color'))) & 0xFFFFFFFF, th=float(a.get('ThicknessScale') or 1), glow=glow,
                        layer=li, aps=aps, id=a.get('ID')))
    links = set()
    for k, o in enumerate(out):
        for j, p in enumerate(o['aps']):
            for ac in p.findall('AC'):
                q = pid.get(ac.get('ConnPtId'))
                if q:
                    links.add(tuple(sorted([(k, j), q])))
    return out, links


def fills(fr, O):
    """면마다 (색, 테두리로 쓴 오브젝트 번호들) — 면 칠 순서는 보지 않는다(사용자 10-30)."""
    idx = {o['id']: k for k, o in enumerate(O)}
    out = []
    for r in fr.findall('FR'):
        if (int(float(r.get('Color'))) & 0xFFFFFFFF) >> 24 == 0:
            continue
        out.append((int(float(r.get('Color'))) & 0xFFFFFFFF, tuple(sorted({idx[s.get('ObjId')] for s in r.findall('FS') if s.get('ObjId') in idx}))))
    return out


def _pdist(a, b):
    """점 평균 거리(화면 가로 % 단위)와 점 순서를 뒤집었는지. 점 수가 다르거나 모자라면 맞을 수 없음."""
    n = NEED.get(a['t'], 2)
    if len(a['xy']) != len(b['xy']) or len(a['xy']) < n:
        return TYPE_PEN, False
    A, B = np.array(a['xy']), np.array(b['xy'])
    if a['t'] == '2':   # 원: 중심 거리 + 반지름 차(화면 화소 비율 좌표라 원 그대로). 점 방향은 연결 대응에만 쓴다
        d = float(np.linalg.norm(A.mean(0) - B.mean(0)) + abs(np.linalg.norm(A[1] - A[0]) - np.linalg.norm(B[1] - B[0])) / 2)
        f = bool(np.linalg.norm(A - B[::-1], axis=1).sum() < np.linalg.norm(A - B, axis=1).sum())
        return d, f
    d0 = np.linalg.norm(A - B, axis=1).mean()
    d1 = np.linalg.norm(A - B[::-1], axis=1).mean()
    return float(min(d0, d1)), bool(d1 < d0)


def _anchor(O):
    pts = []
    for o in O:
        pts += o['xy'] if o['t'] != '2' else [tuple(np.mean(o['xy'], 0))]
    return np.array(pts, float).reshape(-1, 2)


def _apply(O, s, t):
    return [dict(o, xy=[(x * s + t[0], y * s + t[1]) for x, y in o['xy']]) for o in O]


def _cost(P, A):
    C = np.zeros((len(P), len(A)))
    flip = np.zeros((len(P), len(A)), bool)
    for i, p in enumerate(P):
        for j, a in enumerate(A):
            d, f = _pdist(p, a)
            C[i, j] = d + (0 if p['t'] == a['t'] else TYPE_PEN)
            flip[i, j] = f
    return C, flip


def _fit(P, A, pairs, flip):
    """짝지은 점들로 배율 s·이동 t 최소제곱(p' = s p + t)."""
    X, Y = [], []
    for i, j in pairs:
        xp, xa = P[i]['xy'], A[j]['xy']
        if len(xp) != len(xa):
            continue
        if flip[i, j]:
            xp = xp[::-1]
        X += xp
        Y += xa
    if len(X) < 2:
        return None
    X, Y = np.array(X), np.array(Y)
    mx, my = X.mean(0), Y.mean(0)
    vx = ((X - mx) ** 2).sum()
    if vx < 1e-9:
        return None
    s = float(((X - mx) * (Y - my)).sum() / vx)
    if s <= 0:
        return None
    return s, my - s * mx


def match(P, A, tol):
    """맞는 짝 수를 먼저 최대로, 그다음 거리 합을 최소로(GPT 검토 10-30 반례: 최소 거리합이 맞는 짝 수를 줄이던 것)."""
    C, flip = _cost(P, A)
    ok_m = np.array([[P[i]['t'] == A[j]['t'] for j in range(len(A))] for i in range(len(P))]) & (C <= tol)
    ri, ci = linear_sum_assignment(np.where(ok_m, C, INVALID + C))
    return [(i, j) for i, j in zip(ri, ci) if ok_m[i, j]], C, flip


def score(pred_fr, ans_fr, tol=1.0, align=False, hwr=0.5625):
    """한 장 채점. 돌려주는 합산용 수(tp·n_*)로 여러 장 전체 F1을 낸다(짝 0개인 장도 빠지지 않게)."""
    P, lp = objs(pred_fr, hwr)
    A, la = objs(ans_fr, hwr)
    scale, shift = 1.0, (0.0, 0.0)
    if align and P and A:
        # 처음: 무게중심·크기(점 흩어짐) 맞추기 → 짝짓기 → 짝으로 배율·이동 다시 맞추기
        ap, aa = _anchor(P), _anchor(A)
        sp, sa = np.sqrt(((ap - ap.mean(0)) ** 2).sum(1).mean()), np.sqrt(((aa - aa.mean(0)) ** 2).sum(1).mean())
        sc = sa / sp if sp > 1e-6 and sa > 1e-6 else 1.0
        cand = [(1.0, np.zeros(2)), (sc, aa.mean(0) - sc * ap.mean(0))]
        best = None
        for s0, t0 in cand:
            s_, t_ = s0, t0
            for _ in range(3):
                good, _, fl = match(_apply(P, s_, t_), A, 10 * tol)
                f = _fit(P, A, good, fl)
                if f is None:
                    break
                s_, t_ = f
            n_ok = len(match(_apply(P, s_, t_), A, tol)[0])
            if best is None or n_ok > best[0]:
                best = (n_ok, s_, t_)
        _, scale, shift = best
        P = _apply(P, scale, shift)
    ok, C, flip = match(P, A, tol) if P and A else ([], None, None)
    m = dict(ok)
    # 연결: 짝지은 점으로 옮긴 AI 연결 vs 원본 연결. 짝 없는 오브젝트에 걸린 연결은 틀림(AI) / 놓침(원본)
    def mp(i, k):
        j = m[i]
        return (j, (len(P[i]['xy']) - 1 - k) if flip[i, j] else k)
    lp2 = {tuple(sorted([mp(*x), mp(*y)])) for x, y in lp if x[0] in m and y[0] in m}
    tp_l = len(lp2 & la)
    # 면: (색, 테두리 오브젝트 → 원본 번호로 옮김) 같은 것끼리
    fa = fills(ans_fr, A)
    fp_ = [(c, tuple(sorted(m[i] for i in objs_ if i in m)) if all(i in m for i in objs_) else None) for c, objs_ in fills(pred_fr, P)]
    left = list(fa)
    tp_f = 0
    for x in fp_:
        if x[1] is not None and x in left:
            left.remove(x)
            tp_f += 1
    bg_same = (int(float(pred_fr.get('BackgroundColor', '-1'))) & 0xFFFFFFFF) == (int(float(ans_fr.get('BackgroundColor', '-1'))) & 0xFFFFFFFF)
    r = dict(pred=len(P), ans=len(A), match=len(ok), recall=len(ok) / len(A) if A else float(not P),
             precision=len(ok) / len(P) if P else float(not A), pt_err=None, color=None, thick=None, glow=None,
             link_tp=tp_l, link_pred=len(lp), link_ans=len(la), link_f1=f1(tp_l, len(lp), len(la)),
             fill_tp=tp_f, fill_pred=len(fp_), fill_ans=len(fa), fill_f1=f1(tp_f, len(fp_), len(fa)),
             bg=bg_same, order=None, scale=float(scale), shift=tuple(float(v) for v in shift))
    if ok:
        r['pt_err'] = float(np.mean([C[i, j] for i, j in ok]))
        r['color'] = float(np.mean([P[i]['col'] == A[j]['col'] for i, j in ok]))
        r['thick'] = float(np.mean([abs(math.log(max(P[i]['th'], 1e-3) / max(A[j]['th'], 1e-3))) < 0.05 for i, j in ok]))
        r['glow'] = float(np.mean([P[i]['glow'] == A[j]['glow'] for i, j in ok]))
    # 가림 순서: 영상이 달라지는 쌍만 — 원본에서 경계 상자가 겹치고(여백 0.5) 색이 다른 짝 쌍의 앞뒤(실제 그리는 순서)가 같은 비율
    if len(ok) >= 2:
        def box(o):
            xy = np.array(o['xy'])
            if o['t'] == '2' and len(xy) >= 2:
                c, rr = xy[:2].mean(0), np.linalg.norm(xy[1] - xy[0]) / 2
                return c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr
            return xy[:, 0].min(), xy[:, 1].min(), xy[:, 0].max(), xy[:, 1].max()
        bx = {j: box(A[j]) for j in m.values()}
        same = tot = 0
        items = sorted(m.items())
        for x in range(len(items)):
            for y in range(x + 1, len(items)):
                (i1, j1), (i2, j2) = items[x], items[y]
                b1, b2 = bx[j1], bx[j2]
                if A[j1]['col'] == A[j2]['col'] or b1[2] + 0.5 < b2[0] or b2[2] + 0.5 < b1[0] or b1[3] + 0.5 < b2[1] or b2[3] + 0.5 < b1[1]:
                    continue
                tot += 1
                same += (i1 < i2) == (j1 < j2)
        r['order'] = same / tot if tot else None
    r['perfect'] = (r['match'] == len(A) == len(P) and r['bg'] and r['link_f1'] == 1.0 and r['fill_f1'] == 1.0
                    and (not ok or (r['color'] == 1.0 and r['thick'] == 1.0 and r['glow'] == 1.0)) and r['order'] in (None, 1.0))
    return r


def f1(tp, n_pred, n_ans):
    if n_pred == 0 and n_ans == 0:
        return 1.0
    p = tp / n_pred if n_pred else 0.0
    q = tp / n_ans if n_ans else 0.0
    return 2 * p * q / (p + q) if p + q else 0.0
