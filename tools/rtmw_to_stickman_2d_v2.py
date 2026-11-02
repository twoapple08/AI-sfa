"""RTMW 133점(몸 0–16) → 2D 스틱맨 SFA 시제품 2(2026-11-03).

시제품 1(tools/rtmw_to_stickman_2d.py)에서 바꾼 것
- 사용자 판정(11-03): 앱에서 조작은 문제없음, 모션이 떨림. 골반·어깨가 생겼으니 **목도 추가**,
  머리를 뺀 상하체 **선을 두껍게**(뼈만 있는 느낌 줄이기).
- 중점 모델(GPT 8·9차 합의): 골반 = 엉덩이 중점, 목 = 어깨 중점을 정확히 지킨다. 독립 방향 11개
  (골반 가로축, 몸통, 어깨 가로축, 팔다리 8) + 골반 위치 2 = 장마다 13 변수.
- 배율: 장마다 관측 몸통(어깨 중점–엉덩이 중점) 길이를 9장 중앙값 + 5장 평균으로 매끄럽게 한 값(몸통 기준 배율).
  시제품 1의 '배율도 풀기'는 L90 팔다리에 끌려 몸통이 35/35장 짧아졌다.
- 떨림: 전 장을 한꺼번에 풀고, 이웃 장 사이 각도 차(주기적)·골반 이동(몸통 단위)에 벌점 λ를 준다.
  애니의 2·3장 정지가 부드러운 이동으로 바뀔 수 있다(정지 유지 여부는 사용자 판정 대기 항목).
- --keys(시제품 3, 11-03): λ를 줘도 떨림이 남았다(사용자). 원인은 원본의 3컷 작화(새 그림 307·310·…·334, 그 사이 정지)다.
  원본 그림 하나를 키포즈 하나로 풀고(같은 그림 장의 관측 평균), 그 구간 가운데 시각에 놓은 뒤 사이 장을 PCHIP으로 잇는다.
- 각도 사전: 관측 없는 뼈·장에만 이웃 장 관측 각도 보간값 쪽 0.01(시간 항이 있으므로 거의 영향 없음).
- 목·머리: 목 = 어깨 중점에서 몸통 방향으로 Ln, 머리 원 = 그 위 지름 D. 기본 Ln 0.17, D 0.5(몸통 단위).
  근거: B 300–334 RTMW에서 어깨 중점 → 귀 중점이 몸통의 0.417(10–90% 0.376–0.443) → 머리 중심(Ln + D/2 = 0.42)을 귀 높이에 둠.
  귀·코는 '확인된 관측'이 아니므로 머리 방향에는 쓰지 않는다(몸통 방향을 따름).
- 굵기: 기본은 모든 조각 1.0(앱 기본 스틱맨과 같음). 사용자가 굵은 몸 선(3.0 × 몸 크기 비례)을 본 뒤 굵기만 롤백했다(11-03).
  --thick-by-size를 주면 머리 원 1.0, 나머지 body_thick × (몸통 화면 % / 11.2)로 그린다(시제품 2 첫 판).

SFA: 15조각(머리 원, 목, 몸통, 어깨 2, 팔 4, 엉덩이 2, 다리 4). 점 ID 장마다 새로, 오브젝트 ID 유지, 파란점(골반) 하나.
Flags는 시제품 1(앱에서 조작 확인됨, 11-03 사용자)의 방식을 따른다. 목 조각은 새로 넣었으므로 앱 확인 전이다.

사용:
  python tools/rtmw_to_stickman_2d_v2.py 결과.jsonl.gz 영상.mp4 출력.sfa --start 300 --end 334 --crop-y 63 \
      --drop 301:8 301:10 302:8 302:10 ... [--lam 1.0] [--quantile 90] [--neck 0.17] [--head 0.5] [--body-thick 3.0] \
      [--report 보고.json] [--joints 관절.json]
"""
import argparse
import json
import os
import sys
import zipfile

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtmw_to_stickman_2d import (LSHO, RSHO, LHIP, RHIP, OBS, load_rtmw, pick_target, parse_drop, smooth)  # noqa: E402

# 독립 방향 11개(각도 변수 순서)
DIRS = ['hip_span', 'torso', 'sho_span', 'uarm_l', 'farm_l', 'uarm_r', 'farm_r', 'thigh_l', 'shin_l', 'thigh_r', 'shin_r']
CHAIN = {'uarm_l': ('sho_l', 'elb_l'), 'farm_l': ('elb_l', 'wri_l'), 'uarm_r': ('sho_r', 'elb_r'), 'farm_r': ('elb_r', 'wri_r'),
         'thigh_l': ('hip_l', 'kne_l'), 'shin_l': ('kne_l', 'ank_l'), 'thigh_r': ('hip_r', 'kne_r'), 'shin_r': ('kne_r', 'ank_r')}
NODES = list(OBS)  # 관측 12점 이름(RTMW 5–16)


def unit(th):
    return np.stack([np.cos(th), np.sin(th)], -1)


def forward(th, t, s, L, hp=None, hs=None):
    """th: (T,11), t: (T,2), s: (T,), L: 길이 dict(몸통 단위, hip_span·sho_span은 전체 폭). → 노드 dict (T,2).
    hp·hs: (T,2) 골반·어깨 반폭 벡터(몸통 단위)를 직접 줄 때(키포즈 보간에서 몸 돌리기를 폭 변화로 흉내)."""
    sc = s[:, None]
    hp = L['hip_span'] / 2 * unit(th[:, 0]) if hp is None else hp
    hs = L['sho_span'] / 2 * unit(th[:, 2]) if hs is None else hs
    J = {'pel': t}
    J['hip_l'] = t + sc * hp
    J['hip_r'] = t - sc * hp
    J['neck'] = t + sc * L['torso'] * unit(th[:, 1])
    J['sho_l'] = J['neck'] + sc * hs
    J['sho_r'] = J['neck'] - sc * hs
    for i, d in enumerate(DIRS[3:], 3):
        a, b = CHAIN[d]
        J[b] = J[a] + sc * L[d] * unit(th[:, i])
    return J


def obs_arrays(K, W):
    P = np.stack([K[:, OBS[n], :2] for n in NODES], 1)       # (T,12,2)
    Wt = np.stack([W[:, OBS[n]] for n in NODES], 1)           # (T,12)
    return P, Wt


def raw_dirs(K, W):
    """관측 방향(라디안, 없으면 nan): 가로축은 오른쪽 → 왼쪽 점."""
    T = len(K)
    A = np.full((T, 11), np.nan)
    pt = lambda j: K[:, j, :2]  # noqa: E731
    ok = lambda *js: np.all([W[:, j] > 0 for j in js], 0)  # noqa: E731
    pairs = {'hip_span': (RHIP, LHIP), 'sho_span': (RSHO, LSHO)}
    for i, d in enumerate(DIRS):
        if d == 'torso':
            m = ok(LHIP, RHIP, LSHO, RSHO)
            v = (pt(LSHO) + pt(RSHO)) / 2 - (pt(LHIP) + pt(RHIP)) / 2
        elif d in pairs:
            a, b = pairs[d]
            m = ok(a, b)
            v = pt(b) - pt(a)
        else:
            a, b = (OBS[n] for n in CHAIN[d])
            m = ok(a, b)
            v = pt(b) - pt(a)
        A[m, i] = np.arctan2(v[m, 1], v[m, 0])
    prior = A.copy()
    idx = np.arange(T)
    for i in range(11):
        g = ~np.isnan(A[:, i])
        prior[:, i] = np.interp(idx, idx[g], np.unwrap(A[g, i])) if g.any() else (-np.pi / 2 if DIRS[i] == 'torso' else np.pi / 2)
    return A, prior


def calib(K, W, q=90, symmetric=True):
    """길이(몸통 = 1): 장마다 관측 길이 / 관측 몸통의 q 분위. 가로폭은 전체 폭 하나로(중점 정의상 반폭은 그 절반)."""
    tor = np.linalg.norm((K[:, LSHO, :2] + K[:, RSHO, :2]) / 2 - (K[:, LHIP, :2] + K[:, RHIP, :2]) / 2, axis=1)
    okT = (W[:, [LSHO, RSHO, LHIP, RHIP]] > 0).all(1)
    L, n = {'torso': 1.0}, {}
    pairs = {'hip_span': ('hip_r', 'hip_l'), 'sho_span': ('sho_r', 'sho_l')}
    for d in DIRS:
        if d == 'torso':
            continue
        a, b = pairs.get(d, CHAIN.get(d))
        ja, jb = OBS[a], OBS[b]
        m = okT & (W[:, ja] > 0) & (W[:, jb] > 0)
        r = np.linalg.norm(K[m, jb, :2] - K[m, ja, :2], axis=1) / tor[m]
        L[d] = float(np.percentile(r, q)) if len(r) else 0.5
        n[d] = int(m.sum())
    if symmetric:
        for d in DIRS:
            if d.endswith('_l'):
                e = d[:-2] + '_r'
                L[d] = L[e] = max(L[d], L[e])
    return L, n, tor


def fit_all(K, W, L, S, lam=1.0, prior_w=0.01):
    T = len(K)
    P, Wt = obs_arrays(K, W)
    A, prior = raw_dirs(K, W)
    unobs = np.isnan(A)
    x0 = np.concatenate([prior, (K[:, LHIP, :2] + K[:, RHIP, :2]) / 2], 1).ravel()   # 장마다 [11 각도, 2 위치]
    NV = 13
    sw = np.sqrt(Wt)

    def resid(x):
        X = x.reshape(T, NV)
        th, t = X[:, :11], X[:, 11:]
        J = forward(th, t, S, L)
        M = np.stack([J[n] for n in NODES], 1)
        r_obs = ((M - P) / S[:, None, None] * sw[..., None]).ravel()
        d = np.angle(np.exp(1j * (th[1:] - th[:-1])))
        r_tmp = np.concatenate([(lam * d).ravel(), (lam * (t[1:] - t[:-1]) / S[1:, None]).ravel()])
        r_pr = (prior_w * np.angle(np.exp(1j * (th - prior))) * unobs).ravel()
        return np.concatenate([r_obs, r_tmp, r_pr])

    # 희소 구조: 관측 잔차는 자기 장, 시간 잔차는 이웃 두 장, 사전은 자기 변수
    n_obs, n_tmp = T * 24, (T - 1) * 13
    sp = lil_matrix((n_obs + n_tmp + T * 11, T * NV), dtype=int)
    for f in range(T):
        sp[f * 24:(f + 1) * 24, f * NV:(f + 1) * NV] = 1
    for f in range(T - 1):
        for i in range(11):
            r = n_obs + f * 11 + i
            sp[r, f * NV + i] = sp[r, (f + 1) * NV + i] = 1
        for c in range(2):
            r = n_obs + (T - 1) * 11 + f * 2 + c
            sp[r, f * NV + 11 + c] = sp[r, (f + 1) * NV + 11 + c] = 1
    for f in range(T):
        for i in range(11):
            sp[n_obs + n_tmp + f * 11 + i, f * NV + i] = 1
    sol = least_squares(resid, x0, jac_sparsity=sp, method='trf', x_scale='jac', max_nfev=2000)
    X = sol.x.reshape(T, NV)
    J = forward(X[:, :11], X[:, 11:], S, L)
    M = np.stack([J[n] for n in NODES], 1)
    err = np.linalg.norm(M - P, axis=2) / S[:, None]
    rms = [float(np.sqrt(np.mean(e[w > 0] ** 2))) if (w > 0).any() else None for e, w in zip(err, Wt)]
    return J, X, rms, unobs, sol


def accel(J, S, names=NODES):
    X = np.stack([J[n] for n in names], 1)
    return np.linalg.norm(X[2:] - 2 * X[1:-1] + X[:-2], axis=2) / S[1:-1, None]


def with_head(J, S, neck_len, head_d):
    u = J['neck'] - J['pel']
    u = u / np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-6)
    J = dict(J)
    J['head_base'] = J['neck'] + u * (S * neck_len)[:, None]
    J['head_t'] = J['head_base'] + u * (S * head_d)[:, None]
    return J


# ---- SFA ----
# (AO 번호, TypeId, 몸 여부(굵기 적용), [(점 이름@조각, Flags, 연결)])
PIECES = [
    (1, '2', False, [('head_t@head', 5, []), ('head_base@head', 5, ['head_base@neckp'])]),
    (2, '1', True, [('head_base@neckp', 5, ['head_base@head']), ('neck@neckp', 4, ['neck@torso'])]),
    (3, '1', True, [('neck@torso', 4, ['neck@neckp', 'neck@sho_l', 'neck@sho_r']), ('pel@torso', 3, ['pel@hip_l', 'pel@hip_r'])]),
    (4, '1', True, [('sho_l@sho_l', 5, ['sho_l@uarm_l']), ('neck@sho_l', 4, ['neck@torso'])]),
    (5, '1', True, [('sho_r@sho_r', 5, ['sho_r@uarm_r']), ('neck@sho_r', 4, ['neck@torso'])]),
    (6, '1', True, [('elb_l@uarm_l', 5, ['elb_l@farm_l']), ('sho_l@uarm_l', 4, ['sho_l@sho_l'])]),
    (7, '1', True, [('wri_l@farm_l', 5, []), ('elb_l@farm_l', 4, ['elb_l@uarm_l'])]),
    (8, '1', True, [('elb_r@uarm_r', 5, ['elb_r@farm_r']), ('sho_r@uarm_r', 4, ['sho_r@sho_r'])]),
    (9, '1', True, [('wri_r@farm_r', 5, []), ('elb_r@farm_r', 4, ['elb_r@uarm_r'])]),
    (10, '1', True, [('pel@hip_l', 2, ['pel@torso']), ('hip_l@hip_l', 5, ['hip_l@thigh_l'])]),
    (11, '1', True, [('pel@hip_r', 2, ['pel@torso']), ('hip_r@hip_r', 5, ['hip_r@thigh_r'])]),
    (12, '1', True, [('hip_l@thigh_l', 4, ['hip_l@hip_l']), ('kne_l@thigh_l', 5, ['kne_l@shin_l'])]),
    (13, '1', True, [('kne_l@shin_l', 4, ['kne_l@thigh_l']), ('ank_l@shin_l', 5, [])]),
    (14, '1', True, [('hip_r@thigh_r', 4, ['hip_r@hip_r']), ('kne_r@thigh_r', 5, ['kne_r@shin_r'])]),
    (15, '1', True, [('kne_r@shin_r', 4, ['kne_r@thigh_r']), ('ank_r@shin_r', 5, [])]),
]
FR0, AO0, PT0 = 5000, 3560000, 6680000
AO_STYLE = ('Color="-16777216" LayerId="0" ThicknessScale="{th}" ObjectScale="1.0" '
            'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0"')


def point_ids(n):
    names = [p[0] for _, _, _, pts in PIECES for p in pts]
    return {nm: PT0 + n * 100 + i + 1 for i, nm in enumerate(names)}


def frame_xml(n, Jn, to_pct, body_th, head_th=1.0):
    ids = point_ids(n)
    out = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
    for oid, typ, body, pts in PIECES:
        th = body_th if body else head_th
        out.append(f'<AO ID="{AO0 + oid}" TypeId="{typ}" DrawOrder="{AO0 + oid}" ' + AO_STYLE.format(th=f'{th:.3f}') + '>')
        for i, (nm, fl, acs) in enumerate(pts):
            x, y = to_pct(Jn[nm.split('@')[0]])
            out.append(f'<AP ID="{ids[nm]}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{ids[c]}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ''.join(out)


def sfa_xml(J, W, H, crop_y, name, body_th):
    T = len(J['pel'])
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - crop_y) / H)  # noqa: E731
    frames = [frame_xml(n, {k: v[n] for k, v in J.items()}, to_pct, body_th[n]) for n in range(T)]
    return ('<?xml version="1.0" encoding="UTF-8" ?>'
            f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{T}" BackgroundColor="-1">'
            + ''.join(frames) + '</Sequence>')


def frame_disp(K, W, tor):
    """이웃 장 사이 유효 관절 이동의 중앙값/몸통(장 1..T-1, 관측이 없으면 nan)."""
    out = []
    for t in range(1, len(K)):
        m = (W[t, 5:17] > 0) & (W[t - 1, 5:17] > 0)
        d = np.linalg.norm(K[t, 5:17, :2] - K[t - 1, 5:17, :2], axis=1)[m] / tor[t]
        out.append(float(np.median(d)) if len(d) else np.nan)
    return np.array(out)


def auto_thr(d, fallback=0.04, min_ratio=4.0):
    """정지/새 그림 문턱을 영상마다 정한다: log 이동량을 두 무리로 나누는 Otsu. 두 무리의 기하 평균 비가
    min_ratio 미만(뚜렷이 안 갈림)이거나 한쪽이 2장 미만이면 fallback.
    (실측: B 300–334 정지 0.007–0.016 / 새 그림 0.07+, A 1500–1523 정지 0.01–0.13 / 새 그림 0.29–2.4 — 인물이 작아 잡음이 큼)"""
    x = np.log10(np.maximum(d[~np.isnan(d)], 1e-3))
    if len(x) < 4:
        return fallback
    xs = np.sort(x)
    best, cut = -1, None
    for i in range(2, len(xs) - 1):
        a, b = xs[:i], xs[i:]
        v = len(a) * len(b) * (a.mean() - b.mean()) ** 2
        if v > best:
            best, cut = v, i
    if cut is None:
        return fallback
    a, b = xs[:cut], xs[cut:]
    if b.mean() - a.mean() < np.log10(min_ratio):
        return fallback
    return float(10 ** ((a.max() + b.min()) / 2))


def drawing_segments(K, W, tor, thr=0.04):
    """RTMW 관측으로 '같은 그림' 구간을 나눈다. 이웃 장 사이 유효 관절 이동의 중앙값/몸통 > thr이면 새 그림.
    thr=None이면 auto_thr로 영상마다 정한다. (B 300–334는 0.04로 확인 경계 328·331과 일치.)"""
    d = frame_disp(K, W, tor)
    if thr is None:
        thr = auto_thr(d)
    T = len(K)
    starts = [0] + [t for t in range(1, T) if not np.isnan(d[t - 1]) and d[t - 1] > thr]
    return [(s, (starts[i + 1] - 1) if i + 1 < len(starts) else T - 1) for i, s in enumerate(starts)]


def smooth_keys(xk, yk, sigma, x):
    """sigma: 수 하나 또는 키마다 배열(위치는 px 그대로 두고 sigma = 몸통 단위 × 키 배율)."""
    """키 값을 그대로 잇지 않고, 키 흔들림 크기 sigma 안에서 매끄러운 3차 스플라인으로 맞춰 키 값을 고른 뒤 PCHIP으로 x에서 잇는다(열마다).
    UnivariateSpline s = 키 수 × sigma²(잔차 제곱합 허용치). 키가 4개 미만이면 PCHIP으로 잇는다. 범위 밖은 끝값 유지.
    (11-03: B 걷기에서 키 2차 차분이 1차 차분과 같아(골반 0.110 대 0.109 몸통) 떨림으로 보였다. 큰 동작(A)은 sigma보다 훨씬 커서 거의 남는다.)"""
    from scipy.interpolate import UnivariateSpline
    yk = np.asarray(yk, float)
    if len(xk) < 4:
        return pchip_wrap(xk, yk, x)
    cols = yk.reshape(len(xk), -1)
    # 스플라인은 키 값의 흔들림만 깎는다(키 시각에서 읽음). 키 사이는 PCHIP으로 잇는다 —
    # 3차 스플라인을 그대로 이으면 빠른 동작(A)에서 키 사이가 넘쳐 가속도가 0.27 → 0.34로 늘었다(11-03).
    w = 1.0 / np.broadcast_to(np.asarray(sigma, float), (len(xk),))
    den = np.stack([UnivariateSpline(xk, c, w=w, k=3, s=len(xk))(xk) for c in cols.T], -1)
    return pchip_wrap(xk, den.reshape(yk.shape), x)


def frame_facing(K, W, tor, min_frac=0.05):
    """발끝 방향(엄지발가락 x − 발뒤꿈치 x, 두 발 평균)으로 장마다 앞쪽을 정한다: +1 화면 오른쪽, −1 왼쪽, 0 불분명.
    |값| < min_frac × 몸통이면 0(발이 카메라 쪽·반대쪽을 향함). K는 23점(발 17–22 포함)이어야 한다."""
    T = len(K)
    out = np.zeros(T)
    if K.shape[1] < 23:
        return out
    for t in range(T):
        v = [K[t, toe, 0] - K[t, heel, 0] for toe, heel in ((17, 19), (20, 22)) if W[t, toe] > 0 and W[t, heel] > 0]
        if v and abs(np.mean(v)) >= min_frac * tor[t]:
            out[t] = np.sign(np.mean(v))
    return out


def fix_knees(J, facing, roots=(('hip_l', 'kne_l', 'ank_l'), ('hip_r', 'kne_r', 'ank_r'))):
    """무릎이 앞쪽(발끝 방향)과 반대로 꺾였으면 뿌리–발목 선을 기준으로 무릎을 대칭으로 옮긴다(길이 유지).
    화면 좌표(y 아래)에서 앞쪽이 +x이면 정상 꺾임은 cross(허벅지, 정강이) > 0. facing 0인 장은 건드리지 않는다.
    반환: 고친 (장, 다리) 목록."""
    fixed = []
    for root, kn, an in roots:
        R_, K_, A_ = J[root], J[kn].copy(), J[an]
        th, sh = K_ - R_, A_ - K_
        cr = th[:, 0] * sh[:, 1] - th[:, 1] * sh[:, 0]
        bad = (facing != 0) & (cr * facing < 0)
        d = A_ - R_
        p = K_ - R_
        proj = (p * d).sum(1, keepdims=True) / np.maximum((d * d).sum(1, keepdims=True), 1e-9) * d
        K_[bad] = (R_ + 2 * proj - p)[bad]
        J[kn] = K_
        fixed += [(int(t), kn) for t in np.flatnonzero(bad)]
    return fixed


def pchip_wrap(xk, yk, x):
    """키 시각 xk의 값 yk(각도는 미리 풀어 둠)를 PCHIP으로 잇는다(넘침 없음). 범위 밖은 끝값 유지."""
    from scipy.interpolate import PchipInterpolator
    if len(xk) == 1:
        return np.repeat(yk[:1], len(x), 0)
    xc = np.clip(x, xk[0], xk[-1])
    return PchipInterpolator(xk, yk, axis=0)(xc)


def keypose_fit(K, W, L, S, tor, thr=None, lam_key=0.05, key_sigma=(0.06, 0.05)):
    """원본 그림 하나 = 키포즈 하나. 같은 그림 구간의 관측을 평균해 키포즈를 풀고, 구간 가운데 시각에 놓은 뒤
    그 사이 장은 PCHIP으로 이어 24장 모두 움직이게 한다(3컷 작화의 끊김 → 부드러운 이동).
    - 키끼리 벌점 기본 0.05(A 1500–1523: 그림 하나에 몸통 1.5배 이상 이동·몸 돌리기가 있어 0.3에서 잔차 0.5 이상).
    - 골반·어깨 가로선은 각도가 아니라 반폭 벡터를 이어, 몸이 돌 때 선이 화면 안에서 빙글 돌지 않고 폭이 줄었다 펴진다."""
    if thr is None:
        thr = auto_thr(frame_disp(K, W, tor))
    segs = drawing_segments(K, W, tor, thr)
    Kk, Wk, Sk, ck = [], [], [], []
    for s, e in segs:
        w = W[s:e + 1]
        cnt = w.sum(0)
        k = np.zeros((K.shape[1], 3))
        k[:, :2] = (K[s:e + 1, :, :2] * w[..., None]).sum(0) / np.maximum(cnt, 1)[:, None]
        k[:, 2] = K[s:e + 1, :, 2].mean(0)
        Kk.append(k)
        Wk.append((cnt > 0).astype(float))
        Sk.append(S[s:e + 1].mean())
        ck.append((s + e) / 2)
    Kk, Wk, Sk, ck = np.array(Kk), np.array(Wk), np.array(Sk), np.array(ck)
    Jk, Xk, rms_k, unobs_k, sol = fit_all(Kk, Wk, L, Sk, lam_key)
    th = np.unwrap(Xk[:, :11], axis=0)
    tt = np.arange(len(K), dtype=float)
    hpk, hsk = L['hip_span'] / 2 * unit(Xk[:, 0]), L['sho_span'] / 2 * unit(Xk[:, 2])
    if key_sigma:   # 키 흔들림 깎기(각도 sigma rad, 위치·가로선은 몸통 단위 sigma)
        sa, sp = key_sigma
        th_all = smooth_keys(ck, th, sa, tt)
        t_all = smooth_keys(ck, Xk[:, 11:], sp * Sk, tt)
        hp, hs = smooth_keys(ck, hpk, sp, tt), smooth_keys(ck, hsk, sp, tt)
    else:
        th_all = pchip_wrap(ck, th, tt)
        t_all = pchip_wrap(ck, Xk[:, 11:], tt)
        hp, hs = pchip_wrap(ck, hpk, tt), pchip_wrap(ck, hsk, tt)
    J = forward(th_all, t_all, S, L, hp, hs)
    P, Wt = obs_arrays(K, W)
    M = np.stack([J[n] for n in NODES], 1)
    err = np.linalg.norm(M - P, axis=2) / S[:, None]
    rms = [float(np.sqrt(np.mean(e[w > 0] ** 2))) if (w > 0).any() else None for e, w in zip(err, Wt)]
    keypose_fit.last_thr = thr
    return J, rms, segs, rms_k, unobs_k, sol


def run(R, frames, drop=None, min_score=1.5, video=None, color='blue', q=90, symmetric=True, lam=1.0,
        neck_len=0.17, head_d=0.5, keys=False, key_thr=None, lam_key=0.05, key_sigma=(0.06, 0.05), knee_fix=True):
    K = pick_target(R, frames, video, color)
    if any(k is None for k in K):
        raise SystemExit('구간 안에 대상이 없는 장이 있다')
    K = np.array(K)
    drop = drop or {}
    W = (K[:, :, 2] >= min_score).astype(float)
    for t, f in enumerate(frames):
        for j in drop.get(f, set()):
            W[t, j] = 0
    L, n_cal, tor = calib(K, W, q, symmetric)
    S = smooth(tor)
    segs = None
    if keys:
        J, rms, segs, rms_k, unobs, sol = keypose_fit(K, W, L, S, tor, key_thr, lam_key, key_sigma)
        unobs_frames = [((frames[segs[k][0]], frames[segs[k][1]]), DIRS[i]) for k, i in zip(*np.nonzero(unobs))]
    else:
        J, X, rms, unobs, sol = fit_all(K, W, L, S, lam)
        unobs_frames = [(frames[t], DIRS[i]) for t, i in zip(*np.nonzero(unobs))]
    facing = frame_facing(K, W, tor)
    knee_fixed = fix_knees(J, facing) if knee_fix else []
    J = with_head(J, S, neck_len, head_d)
    rep = {
        'model': '중점 11방향, 몸통 기준 배율, ' + ('키포즈(원본 그림 하나 = 키 하나) + PCHIP 보간' if keys else '전 장 동시 풀이'),
        'lam': lam_key if keys else lam, 'quantile': q, 'symmetric': symmetric,
        'keypose_segments': [(frames[s], frames[e]) for s, e in segs] if segs else None, 'key_thr': round(keypose_fit.last_thr, 4) if keys else None,
        'neck_len': neck_len, 'head_d': head_d, 'L_torso_units': {k: round(v, 3) for k, v in L.items()},
        'calib_samples': n_cal, 'scale_obs_torso_px': [round(float(v), 1) for v in tor],
        'scale_smoothed': [round(float(v), 1) for v in S],
        'rms_resid_torso': [None if v is None else round(v, 4) for v in rms],
        'accel_median_torso': {'fit': round(float(np.median(accel(J, S))), 4)},
        'unobserved_dir_frames': unobs_frames,
        'facing': [int(x) for x in facing], 'knee_fixed': [(frames[t], k) for t, k in knee_fixed],
        'key_sigma': list(key_sigma) if (keys and key_sigma) else None,
        'optimizer': {'status': int(sol.status), 'nfev': int(sol.nfev), 'cost': round(float(sol.cost), 5)},
    }
    return J, S, rep, K, W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rtmw')
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--target-color', default='blue')
    ap.add_argument('--crop-y', type=float, default=0.0)
    ap.add_argument('--drop', nargs='*', help='뺄 점(장:RTMW번호)')
    ap.add_argument('--min-score', type=float, default=1.5)
    ap.add_argument('--quantile', type=float, default=90)
    ap.add_argument('--no-symmetric', action='store_true')
    ap.add_argument('--lam', type=float, default=1.0, help='이웃 장 변화 벌점(0이면 매 장 독립과 같음)')
    ap.add_argument('--keys', action='store_true', help='원본 그림 하나 = 키포즈 하나로 풀고 사이 장을 PCHIP으로 잇기')
    ap.add_argument('--key-thr', type=float, default=None, help='새 그림 판정 문턱(이웃 장 관절 이동 중앙값/몸통). 비우면 영상마다 자동')
    ap.add_argument('--lam-key', type=float, default=0.05, help='키포즈끼리 변화 벌점')
    ap.add_argument('--key-sigma', type=float, nargs=2, default=[0.06, 0.05], help='키 흔들림 깎기: 각도 rad, 위치 몸통 단위(0 0이면 끔)')
    ap.add_argument('--no-knee-fix', action='store_true')
    ap.add_argument('--neck', type=float, default=0.17)
    ap.add_argument('--head', type=float, default=0.5)
    ap.add_argument('--body-thick', type=float, default=1.0, help='몸 조각 굵기 배율(기본 1.0 = 앱 기본)')
    ap.add_argument('--thick-by-size', action='store_true', help='몸 굵기를 몸통 화면 %에 비례(몸통 11.2%일 때 body_thick)')
    ap.add_argument('--name', default='stickman_proto2')
    ap.add_argument('--report')
    ap.add_argument('--joints')
    a = ap.parse_args()
    import cv2
    cap = cv2.VideoCapture(a.video)
    Wv = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    H = Wv * 9 / 16
    R = load_rtmw(a.rtmw)
    frames = list(range(a.start, a.end + 1))
    J, S, rep, _, _ = run(R, frames, parse_drop(a.drop), a.min_score, a.video, a.target_color, a.quantile,
                          not a.no_symmetric, a.lam, a.neck, a.head, a.keys, a.key_thr, a.lam_key,
                          tuple(a.key_sigma) if any(a.key_sigma) else None, not a.no_knee_fix)
    body_th = (a.body_thick * (100 * S * rep['L_torso_units']['torso'] / Wv) / 11.2 if a.thick_by_size
               else np.full(len(frames), a.body_thick))
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', sfa_xml(J, Wv, H, a.crop_y, a.name, body_th))
    rep.update(body_thick=[round(float(v), 3) for v in body_th], drop=a.drop, crop_y=a.crop_y, screen_16x9=[Wv, H])
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.joints:
        json.dump([{k: [round(float(v[n, 0]), 2), round(float(v[n, 1]), 2)] for k, v in J.items()} for n in range(len(frames))],
                  open(a.joints, 'w'), ensure_ascii=False)
    r = [v for v in rep['rms_resid_torso'] if v is not None]
    print('SFA', os.path.basename(a.out), '장', len(frames), 'λ', rep['lam'], '잔차 RMS/몸통 중앙·최대', round(float(np.median(r)), 4),
          round(float(max(r)), 4), '가속도 중앙', rep['accel_median_torso']['fit'], '굵기', round(float(body_th[0]), 2), '→',
          round(float(body_th[-1]), 2), '풀이', rep['optimizer'])


if __name__ == '__main__':
    main()
