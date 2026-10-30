#!/usr/bin/env python3
"""SFA 오브젝트 단위 채점(2026-10-30, 사용자: "스파는 픽셀로 보는 게 아니라 오브젝트로 보는 거야, 대입하는 거야").
AI가 만든 장과 원본 장의 오브젝트를 하나씩 짝지어(헝가리안) 오브젝트마다 대입한 값을 비교한다.
  짝 비용 = 점 사이 평균 거리(SFA 단위, 0–100 = 화면 폭/높이). 직선·곡선은 점 순서를 뒤집은 것도 본다. 종류가 다르면 +TYPE_PEN.
  맞음 = 같은 종류 + 평균 점 거리 ≤ tol.
숫자: 맞은 오브젝트(재현율 = 원본 중 맞힌 비율, 정밀도 = AI 것 중 맞은 비율), 평균 점 오차, 색·굵기 일치, 연결 F1, 가림 순서 일치.
"""
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

TYPE_PEN = 50.0


def objs(fr):
    out = []
    pid = {}
    for k, a in enumerate(fr.findall('AO')):
        aps = a.findall('AP')
        for j, p in enumerate(aps):
            pid[p.get('ID')] = (k, j)
        out.append(dict(t=a.get('TypeId'), xy=[(float(p.get('X')), float(p.get('Y'))) for p in aps],
                        col=int(float(a.get('Color'))) & 0xFFFFFFFF, th=float(a.get('ThicknessScale') or 1),
                        layer=a.get('LayerId', '0'), aps=aps))
    links = set()
    for k, o in enumerate(out):
        for j, p in enumerate(o['aps']):
            for ac in p.findall('AC'):
                q = pid.get(ac.get('ConnPtId'))
                if q:
                    links.add(tuple(sorted([(k, j), q])))
    return out, links


def _pdist(a, b):
    if len(a['xy']) != len(b['xy']) or not a['xy']:
        return TYPE_PEN, False
    A, B = np.array(a['xy']), np.array(b['xy'])
    d0 = np.linalg.norm(A - B, axis=1).mean()
    if a['t'] == '2':   # 원은 지름 양끝 두 점 — 중심·반지름으로 비교
        c0, c1 = A.mean(0), B.mean(0)
        r0, r1 = np.linalg.norm(A[1] - A[0]) / 2, np.linalg.norm(B[1] - B[0]) / 2
        return float(np.linalg.norm(c0 - c1) + abs(r0 - r1)), False
    d1 = np.linalg.norm(A - B[::-1], axis=1).mean()
    return float(min(d0, d1)), bool(d1 < d0)


def score(pred_fr, ans_fr, tol=1.0):
    P, lp = objs(pred_fr)
    A, la = objs(ans_fr)
    r = dict(pred=len(P), ans=len(A), match=0, recall=0.0, precision=0.0, pt_err=None, color=None, thick=None,
             link_f1=None, order=None)
    if not P or not A:
        r['recall'] = 0.0 if A else 1.0
        r['precision'] = 0.0 if P else 1.0
        return r
    C = np.zeros((len(P), len(A)))
    flip = np.zeros((len(P), len(A)), bool)
    for i, p in enumerate(P):
        for j, a in enumerate(A):
            d, f = _pdist(p, a)
            C[i, j] = d + (0 if p['t'] == a['t'] else TYPE_PEN)
            flip[i, j] = f
    ri, ci = linear_sum_assignment(C)
    ok = [(i, j) for i, j in zip(ri, ci) if P[i]['t'] == A[j]['t'] and C[i, j] <= tol]
    r['match'] = len(ok)
    r['recall'] = len(ok) / len(A)
    r['precision'] = len(ok) / len(P)
    if ok:
        r['pt_err'] = float(np.mean([C[i, j] for i, j in ok]))
        r['color'] = float(np.mean([P[i]['col'] == A[j]['col'] for i, j in ok]))
        r['thick'] = float(np.mean([abs(math.log(max(P[i]['th'], 1e-3) / max(A[j]['th'], 1e-3))) < 0.05 for i, j in ok]))
        # 연결: 짝지은 점끼리 옮긴 AI 연결 vs 원본 연결(짝 안 된 오브젝트에 걸린 원본 연결은 놓친 것으로 센다)
        m = dict(ok)
        n_pts = {i: len(P[i]['xy']) for i, _ in ok}

        def mp(i, k):
            j = m[i]
            return (j, (n_pts[i] - 1 - k) if flip[i, j] else k)
        lp2 = {tuple(sorted([mp(*x), mp(*y)])) for x, y in lp if x[0] in m and y[0] in m}
        tp = len(lp2 & la)
        prec = tp / len(lp) if lp else (1.0 if not la else 0.0)
        rec = tp / len(la) if la else (1.0 if not lp else 0.0)
        r['link_f1'] = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        # 가림 순서: 짝지은 오브젝트 쌍의 앞뒤(레이어 → 장 안 순서)가 같은 비율
        if len(ok) >= 2:
            rank_p = {i: k for k, i in enumerate(sorted(m))}
            rank_a = {j: k for k, j in enumerate(sorted(m.values()))}
            same = tot = 0
            items = list(m.items())
            for x in range(len(items)):
                for y in range(x + 1, min(len(items), x + 40)):
                    (i1, j1), (i2, j2) = items[x], items[y]
                    tot += 1
                    same += (rank_p[i1] < rank_p[i2]) == (rank_a[j1] < rank_a[j2])
            r['order'] = same / tot if tot else None
    return r
