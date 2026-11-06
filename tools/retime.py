"""생성 동작에 nian41 그림 유지 리듬을 입힌다(11-06 사용자 '그래', 선택 ②: 동작은 참고 층(<ref>)으로 만들고 리듬은 나중에).

입력 동작(장마다 관절이 부드럽게 이어진 motion-ir)을 '그림'으로 다시 나눈다:
- 장마다 움직임 속도(골반 기준 자세 변화, 몸통 단위)를 재고, 빠른 장은 1장 유지, 보통은 2장, 거의 멈춘 장은 3장(더 느리면 4장).
- 속도 기준은 이 동작 안의 분위수로 잡아 전체 비율이 nian41 통계(data/stage2/style_features: 1장 31% · 2장 61% · 3장 5% · 4장+ 3%)에 가깝게.
- 그림 하나 = 그 그림 첫 장 자세를 유지 장 수만큼 그대로(골반 위치도 같이 — 애니메이션 '2s' 원리). drawings에 기록.
보간 대신 유지로 바꾸는 것이라 동작 내용은 그대로이고 리듬만 바뀐다. 사용: retime(ir) → 새 ir(복사).
"""
import copy, json, math, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def target_share(ref='nian41'):
    a = json.load(open(f'{ROOT}/data/stage2/style_features_2026-11-05.json', encoding='utf-8'))['aggregate'][ref]['hold_share']
    return {1: a['1'], 2: a['2'], 3: a['3'], 4: a['4+']}


def speeds(ir, slot=0):
    a = ir['actors'][slot]; J = a['joints']; N = ir['frames']; asp = ir.get('aspect', 0.5625)
    def rel(n):
        P = J['pelvis'][n]; T = math.hypot(J['neck'][n][0] - P[0], (J['neck'][n][1] - P[1]) * asp) or 1
        return np.array([[(J[k][n][0] - P[0]) / T, (J[k][n][1] - P[1]) * asp / T] for k in J if k not in ('pelvis', 'head_b')])
    R = [rel(n) for n in range(N)]
    v = [0.0] + [float(np.linalg.norm(R[n] - R[n - 1], axis=1).mean()) for n in range(1, N)]
    return np.array(v)


def retime(ir, slot=0, share=None):
    share = share or target_share()
    out = copy.deepcopy(ir); a = out['actors'][slot]; J = a['joints']; N = out['frames']
    v = speeds(ir, slot)
    # 분위수 기준: 빠른 쪽 share[1] → 1장, 가장 느린 share[3]+share[4] → 3장(그중 더 느린 share[4] → 4장), 나머지 2장.
    # 그림 수 비율을 맞추려면 장 수 기준이 아니라 그림 기준이어야 하므로 그림 하나가 차지하는 장 수로 가중(1장 그림은 장 1개, 2장 그림은 2개…).
    w = {h: share[h] * h for h in share}; tw = sum(w.values())
    q1 = np.quantile(v, 1 - w[1] / tw); q34 = np.quantile(v, (w[3] + w[4]) / tw); q4 = np.quantile(v, w[4] / tw)
    D, n = [], 0
    while n < N:
        s = v[min(n + 1, N - 1)]
        h = 1 if s >= q1 else 4 if s <= q4 else 3 if s <= q34 else 2
        e = min(N - 1, n + h - 1)
        for k in J:
            p = J[k][n]
            for m in range(n + 1, e + 1): J[k][m] = list(p)
        fc = a.get('facing')   # 몸 방향도 그림과 함께 유지(11-06 조각 잇기가 방향을 넘기기 시작)
        if fc and len(fc) == N:
            for m in range(n + 1, e + 1): fc[m] = fc[n]
        D.append([n, e]); n = e + 1
    a['drawings'] = D
    return out


def hold_share(ir, slot=0):
    D = ir['actors'][slot].get('drawings') or []
    hs = [e - s + 1 for s, e in D[1:-1]]
    c = {'1': sum(h == 1 for h in hs), '2': sum(h == 2 for h in hs), '3': sum(h == 3 for h in hs), '4+': sum(h >= 4 for h in hs)}
    t = sum(c.values()) or 1
    return {k: round(x / t, 3) for k, x in c.items()}
