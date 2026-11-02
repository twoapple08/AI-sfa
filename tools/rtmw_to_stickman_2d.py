"""RTMW 133점(몸 0–16만 사용) → 2D 스틱맨 SFA 시제품(8차 A안의 2D판, 2026-11-03).

모형(docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md 8차 §1의 2D판)
- 뼈 13개: 골반 → 엉덩이 좌우·목, 목 → 어깨 좌우, 어깨 → 팔꿈치 → 손목, 엉덩이 → 무릎 → 발목.
  골반 = 엉덩이 중점, 목 = 어깨 중점(관측 파생점). 관측은 RTMW 5–16 12점.
- 변수: 장마다 화면 각도 13 + 골반 위치 2 + 배율 s. 뼈 길이 L0는 보정 집합의 L50(진단용 리그, 실제 길이 아님),
  단위는 몸통(어깨 중점–엉덩이 중점) = 1.
- 배율: 8차 합의는 '대상 × 범위 상수'였지만, B 300–334는 인물이 화면 안쪽으로 걸어가 몸통이 약 220 → 118px로
  줄어든다(실측). 그래서 이 시제품은 장마다 s를 풀고 9장 이동 중앙값 + 5장 평균으로 매끄럽게 한 뒤 각도를 다시 푼다.
  (상수 배율 조건과의 비교는 하지 않았다.)
- 시간 항 없음(장 사이 각도를 함께 푸는 손실은 없다). 각도 사전은 13개 뼈 모두에 있다: 관측된 뼈는 그 장의 관측 뼈 방향, 관측 없는 뼈는 이웃 장 관측 각도의 보간값. 잔차 계수 0.01(제곱합에서 1e-4). (11-03 GPT 9차 지적으로 설명 정정, 동작은 그대로)
- 머리: 코·귀가 '확인된' 장이 없으므로(B는 뒷모습) 머리는 골반 → 목 방향의 연장(지름 0.75 몸통, 앱 틀 비 8.4/11.2).
- 실현 가능성: 관측 뼈 길이 d > s·L0인 뼈·장을 센다(어떤 깊이로도 맞출 수 없는 관측).

SFA: 오브젝트 ID는 장끼리 유지, 점 ID는 장마다 새로(11-02 규칙). 14조각(머리 원 + 뼈 13).
Flags는 앱 기본 스틱맨 틀(data/app_templates/stickman_default.sfa)의 방식을 넓혔다: 뿌리(골반) 3,
뿌리에 붙는 끝 2, 부모 끝에 붙는 끝 4, 바깥 끝 5. 어깨·엉덩이 조각은 틀에 없으므로 이 확장은 앱 확인 전이다.

사용:
  python tools/rtmw_to_stickman_2d.py 결과.jsonl.gz 영상.mp4 출력.sfa --start 300 --end 334 \
      [--target-color blue] [--crop-y 63] [--drop 301:10 303:10 ...] [--calib-drop 301:8 ...] [--report 보고.json] [--joints 관절.json]
"""
import argparse
import gzip
import json
import zipfile

import numpy as np
from scipy.optimize import least_squares

LSHO, RSHO, LELB, RELB, LWRI, RWRI, LHIP, RHIP, LKNE, RKNE, LANK, RANK = range(5, 17)
# 노드: 관측 12점(RTMW 번호) + 가상 'pel'(엉덩이 중점)·'neck'(어깨 중점)
# 뼈(부모 → 자식). 순서가 각도 변수 순서다.
BONES = [('pel', 'hip_l'), ('pel', 'hip_r'), ('pel', 'neck'),
         ('neck', 'sho_l'), ('neck', 'sho_r'),
         ('sho_l', 'elb_l'), ('elb_l', 'wri_l'), ('sho_r', 'elb_r'), ('elb_r', 'wri_r'),
         ('hip_l', 'kne_l'), ('kne_l', 'ank_l'), ('hip_r', 'kne_r'), ('kne_r', 'ank_r')]
OBS = dict(sho_l=LSHO, sho_r=RSHO, elb_l=LELB, elb_r=RELB, wri_l=LWRI, wri_r=RWRI,
           hip_l=LHIP, hip_r=RHIP, kne_l=LKNE, kne_r=RKNE, ank_l=LANK, ank_r=RANK)
HEAD_LEN = 8.4 / 11.2


def load_rtmw(path):
    R = {}
    for line in gzip.open(path, 'rt'):
        r = json.loads(line)
        R[r['f']] = [(np.array(p['b'], float), np.array(p['k'], float)[:17]) for p in r['p']]
    return R


def pick_target(R, frames, video=None, color='blue'):
    """장마다 사람 하나. 한 명이면 그대로, 여럿이면 상자 안 대상 색 비율(tools/rtmw_validate.py와 같은 마스크)로 고른다."""
    cap = None
    out = []
    for f in frames:
        ps = R.get(f, [])
        if not ps:
            out.append(None)
            continue
        if len(ps) == 1:
            out.append(ps[0][1])
            continue
        import cv2
        from rtmw_validate import color_masks
        if cap is None:
            cap = cv2.VideoCapture(video)
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        _, blue, red = color_masks(fr)
        m = blue if color == 'blue' else red
        best = max(ps, key=lambda p: m[max(0, int(p[0][1])):int(p[0][3]), max(0, int(p[0][0])):int(p[0][2])].mean())
        out.append(best[1])
    return out


def node_obs(k, w):
    """한 장의 관측 노드 좌표·가중(가상 노드는 두 점이 모두 있을 때만)."""
    P, W = {}, {}
    for n, j in OBS.items():
        P[n], W[n] = k[j, :2], w[j]
    for n, a, b in (('pel', LHIP, RHIP), ('neck', LSHO, RSHO)):
        P[n] = (k[a, :2] + k[b, :2]) / 2
        W[n] = min(w[a], w[b])
    return P, W


def calib_lengths(K, Wc, q=50, symmetric=False):
    """Lq: 뼈마다 (관측 길이 / 그 장의 몸통)의 q 분위(기본 50 = 진단용, 90 = 목표 리그 후보). 몸통 = 1.
    symmetric: 좌우 같은 뼈는 두 값의 큰 쪽으로 맞춘다(짧은 쪽은 원근 단축이 더 많았다고 본다 — 가정)."""
    L, n_used = [], []
    for a, b in BONES:
        r = []
        for k, w in zip(K, Wc):
            P, W = node_obs(k, w)
            torso = np.linalg.norm(P['neck'] - P['pel'])
            if W[a] > 0 and W[b] > 0 and W['neck'] > 0 and W['pel'] > 0 and torso > 1e-6:
                r.append(np.linalg.norm(P[b] - P[a]) / torso)
        L.append(float(np.percentile(r, q)) if r else 1.0)
        n_used.append(len(r))
    L[BONES.index(('pel', 'neck'))] = 1.0
    if symmetric:
        for i, (a, b) in enumerate(BONES):
            if b.endswith('_l'):
                j = BONES.index((a[:-2] + '_r' if a.endswith('_l') else a, b[:-2] + '_r'))
                L[i] = L[j] = max(L[i], L[j])
    return np.array(L), n_used


def forward(theta, t, s, L):
    J = {'pel': np.asarray(t, float)}
    for (a, b), th, l in zip(BONES, theta, L):
        J[b] = J[a] + s * l * np.array([np.cos(th), np.sin(th)])
    return J


def raw_angles(K, W):
    """장 × 뼈 관측 각도(관측 없으면 nan), 뼈마다 시간축 풀기 후 보간."""
    T = len(K)
    A = np.full((T, len(BONES)), np.nan)
    for t in range(T):
        P, Wt = node_obs(K[t], W[t])
        for i, (a, b) in enumerate(BONES):
            if Wt[a] > 0 and Wt[b] > 0:
                d = P[b] - P[a]
                A[t, i] = np.arctan2(d[1], d[0])
    prior = A.copy()
    idx = np.arange(T)
    for i in range(len(BONES)):
        good = ~np.isnan(A[:, i])
        if good.sum() == 0:
            prior[:, i] = -np.pi / 2 if BONES[i] == ('pel', 'neck') else np.pi / 2
            continue
        un = np.unwrap(A[good, i])
        prior[:, i] = np.interp(idx, idx[good], un)
    return A, prior


def fit_frame(k, w, L, prior, s0=None, s_fixed=None, prior_w=0.01):
    P, W = node_obs(k, w)
    torso_px = max(np.linalg.norm(P['neck'] - P['pel']), 1.0)
    obs_nodes = [n for n in OBS if W[n] > 0]

    def unpack(x):
        th, t = x[:13], x[13:15]
        s = s_fixed if s_fixed is not None else np.exp(x[15])
        return th, t, s

    def resid(x):
        th, t, s = unpack(x)
        J = forward(th, t, s, L)
        r = [(J[n] - P[n]) / torso_px * np.sqrt(W[n]) for n in obs_nodes]
        r.append(prior_w * np.angle(np.exp(1j * (th - prior))))
        return np.concatenate([np.ravel(v) for v in r])

    x0 = list(prior) + list(P['pel'])
    if s_fixed is None:
        x0.append(np.log(s0 if s0 else torso_px))
    sol = least_squares(resid, np.array(x0, float), method='lm')  # 사전 항 13개가 있어 잔차 수 ≥ 변수 수
    th, t, s = unpack(sol.x)
    J = forward(th, t, s, L)
    rms = float(np.sqrt(np.mean([np.sum((J[n] - P[n]) ** 2) for n in obs_nodes]))) / torso_px if obs_nodes else None
    return th, t, s, J, rms


def smooth(v, med=9, avg=5):
    v = np.asarray(v, float)
    m = np.array([np.median(v[max(0, i - med // 2):i + med // 2 + 1]) for i in range(len(v))])
    return np.array([m[max(0, i - avg // 2):i + avg // 2 + 1].mean() for i in range(len(m))])


def feasibility(K, W, L, S):
    """관측 뼈 길이 d > s·L0 인 뼈·장(어떤 깊이로도 맞출 수 없음) 목록."""
    bad = []
    for t, (k, w) in enumerate(zip(K, W)):
        P, Wt = node_obs(k, w)
        for i, (a, b) in enumerate(BONES):
            if Wt[a] > 0 and Wt[b] > 0:
                d = np.linalg.norm(P[b] - P[a])
                if d > S[t] * L[i]:
                    bad.append((t, f'{a}->{b}', round(float(d / (S[t] * L[i])), 3)))
    return bad


# ---- SFA ----
# (AO 번호, TypeId, [(점 이름, Flags, 연결할 점 이름들) Index0, Index1]) — 이름은 같은 조각 안에서만 유일하면 된다.
PIECES = [
    (1, '2', [('head_t', 5, []), ('neck@head', 5, ['neck@torso'])]),
    (2, '1', [('neck@torso', 4, ['neck@head', 'neck@sho_l', 'neck@sho_r']), ('pel@torso', 3, ['pel@hip_l', 'pel@hip_r'])]),
    (3, '1', [('sho_l@sho_l', 5, ['sho_l@uarm_l']), ('neck@sho_l', 4, ['neck@torso'])]),
    (4, '1', [('sho_r@sho_r', 5, ['sho_r@uarm_r']), ('neck@sho_r', 4, ['neck@torso'])]),
    (5, '1', [('elb_l@uarm_l', 5, ['elb_l@farm_l']), ('sho_l@uarm_l', 4, ['sho_l@sho_l'])]),
    (6, '1', [('wri_l@farm_l', 5, []), ('elb_l@farm_l', 4, ['elb_l@uarm_l'])]),
    (7, '1', [('elb_r@uarm_r', 5, ['elb_r@farm_r']), ('sho_r@uarm_r', 4, ['sho_r@sho_r'])]),
    (8, '1', [('wri_r@farm_r', 5, []), ('elb_r@farm_r', 4, ['elb_r@uarm_r'])]),
    (9, '1', [('pel@hip_l', 2, ['pel@torso']), ('hip_l@hip_l', 5, ['hip_l@thigh_l'])]),
    (10, '1', [('pel@hip_r', 2, ['pel@torso']), ('hip_r@hip_r', 5, ['hip_r@thigh_r'])]),
    (11, '1', [('hip_l@thigh_l', 4, ['hip_l@hip_l']), ('kne_l@thigh_l', 5, ['kne_l@shin_l'])]),
    (12, '1', [('kne_l@shin_l', 4, ['kne_l@thigh_l']), ('ank_l@shin_l', 5, [])]),
    (13, '1', [('hip_r@thigh_r', 4, ['hip_r@hip_r']), ('kne_r@thigh_r', 5, ['kne_r@shin_r'])]),
    (14, '1', [('kne_r@shin_r', 4, ['kne_r@thigh_r']), ('ank_r@shin_r', 5, [])]),
]
FR0, AO0, PT0 = 5000, 2560000, 7680000
AO_STYLE = ('Color="-16777216" LayerId="0" ThicknessScale="{th}" ObjectScale="1.0" '
            'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0"')


def point_ids(n):
    """장 n의 점 이름 → 새 ID(장마다 새로, 이웃 장 공유 없음)."""
    names = [p[0] for _, _, pts in PIECES for p in pts]
    return {nm: PT0 + n * 100 + i + 1 for i, nm in enumerate(names)}


def frame_xml(n, J, to_pct, thick='1.0'):
    ids = point_ids(n)
    out = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
    for oid, typ, pts in PIECES:
        out.append(f'<AO ID="{AO0 + oid}" TypeId="{typ}" DrawOrder="{AO0 + oid}" ' + AO_STYLE.format(th=thick) + '>')
        for i, (nm, fl, acs) in enumerate(pts):
            x, y = to_pct(J[nm.split('@')[0]])
            out.append(f'<AP ID="{ids[nm]}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{ids[c]}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ''.join(out)


def sfa_xml(Js, W, H, crop_y, name, thick='1.0'):
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - crop_y) / H)  # noqa: E731
    frames = [frame_xml(i, J, to_pct, thick) for i, J in enumerate(Js)]
    return ('<?xml version="1.0" encoding="UTF-8" ?>'
            f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">'
            + ''.join(frames) + '</Sequence>')


def with_head(J, L):
    u = J['neck'] - J['pel']
    n = np.linalg.norm(u)
    u = u / n if n > 1e-6 else np.array([0.0, -1.0])
    J = dict(J)
    J['head_t'] = J['neck'] + u * n * HEAD_LEN / L[BONES.index(('pel', 'neck'))]
    return J


def parse_drop(items):
    out = {}
    for it in items or []:
        f, j = it.split(':')
        out.setdefault(int(f), set()).add(int(j))
    return out


def run(R, frames, L=None, drop=None, calib_drop=None, min_score=1.5, video=None, color='blue', q=50, symmetric=False):
    K = pick_target(R, frames, video, color)
    if any(k is None for k in K):
        raise SystemExit('구간 안에 대상이 없는 장이 있다')
    drop, calib_drop = drop or {}, calib_drop or {}
    W = []  # 오답·판정 불가 점은 보정·피팅 모두에서 뺀다(빠진 뼈는 이웃 장 각도로 채움)
    for f, k in zip(frames, K):
        w = (k[:, 2] >= min_score).astype(float)
        for j in drop.get(f, set()) | calib_drop.get(f, set()):
            w[j] = 0
        W.append(w)
    n_used = None
    if L is None:
        L, n_used = calib_lengths(K, W, q, symmetric)
    A, prior = raw_angles(K, W)
    s1 = [fit_frame(k, w, L, pr)[2] for k, w, pr in zip(K, W, prior)]
    S = smooth(s1)
    fits = [fit_frame(k, w, L, pr, s_fixed=s) for k, w, pr, s in zip(K, W, prior, S)]
    Js = [with_head(f[3], L) for f in fits]
    rep = {
        'frames': [frames[0], frames[-1]], 'n': len(frames),
        'quantile': q, 'symmetric': symmetric,
        'L0_torso_units': {f'{a}->{b}': round(float(l), 3) for (a, b), l in zip(BONES, L)},
        'calib_samples': dict(zip([f'{a}->{b}' for a, b in BONES], n_used)) if n_used else None,
        'scale_raw_px_per_torso': [round(float(v), 1) for v in s1],
        'scale_smoothed': [round(float(v), 1) for v in S],
        'rms_resid_torso': [None if f[4] is None else round(f[4], 4) for f in fits],
        'unobserved_bone_frames': [(frames[t], f'{a}->{b}') for t in range(len(frames)) for i, (a, b) in enumerate(BONES) if np.isnan(A[t, i])],
        'infeasible_d_gt_sL0': [(frames[t], b, r) for t, b, r in feasibility(K, W, L, S)],
    }
    return Js, rep, K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rtmw')
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--target-color', default='blue')
    ap.add_argument('--crop-y', type=float, default=0.0)
    ap.add_argument('--width', type=float, default=0, help='화면 폭 px(0이면 영상 폭)')
    ap.add_argument('--drop', nargs='*', help='피팅·보정에서 뺄 점(장:RTMW번호), 알려진 오답')
    ap.add_argument('--calib-drop', nargs='*', help='판정 불가 점(장:번호) — 보정·피팅에서 빼고 이웃 장 각도로 채움')
    ap.add_argument('--min-score', type=float, default=1.5)
    ap.add_argument('--quantile', type=float, default=50, help='뼈 길이 분위(50 진단용, 90 목표 리그 후보)')
    ap.add_argument('--symmetric', action='store_true', help='좌우 뼈 길이를 큰 쪽으로 맞춤')
    ap.add_argument('--name', default='stickman_proto')
    ap.add_argument('--thick', default='1.0')
    ap.add_argument('--report')
    ap.add_argument('--joints', help='장마다 관절 좌표(px) JSON — 비교 영상용')
    a = ap.parse_args()
    import cv2
    cap = cv2.VideoCapture(a.video)
    Wv = a.width or cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    H = Wv * 9 / 16
    R = load_rtmw(a.rtmw)
    frames = list(range(a.start, a.end + 1))
    Js, rep, _ = run(R, frames, drop=parse_drop(a.drop), calib_drop=parse_drop(a.calib_drop),
                     min_score=a.min_score, video=a.video, color=a.target_color, q=a.quantile, symmetric=a.symmetric)
    xml = sfa_xml(Js, Wv, H, a.crop_y, a.name, a.thick)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    rep.update(video_size=[Wv, cap.get(cv2.CAP_PROP_FRAME_HEIGHT)], screen_16x9=[Wv, H], crop_y=a.crop_y,
               drop=a.drop, calib_drop=a.calib_drop, min_score=a.min_score)
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.joints:
        json.dump([{k: [round(float(v[0]), 2), round(float(v[1]), 2)] for k, v in J.items()} for J in Js],
                  open(a.joints, 'w'), ensure_ascii=False)
    r = [v for v in rep['rms_resid_torso'] if v is not None]
    print('SFA', a.out, '장', len(Js), '잔차 RMS/몸통 중앙·최대', round(float(np.median(r)), 4), round(float(max(r)), 4),
          '실현 불가 뼈·장', len(rep['infeasible_d_gt_sL0']), '/', len(Js) * 13)


if __name__ == '__main__':
    main()
