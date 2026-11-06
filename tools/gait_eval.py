"""걷기·달리기 판정 지표(11-06 GPT 재설계 답 · 사용자 '그래': '어디서 걷기가 사라지는지' 학습 없이 가리는 실험의 측정기).

한 숫자로 합격시키지 않는다. 지표마다 따로 재고, 반례(정지 인물 옆 이동·발목만 흔들기·킥 반복·발 교차)가 걷기로 통과하지 않는지 먼저 확인한다.
화면 % 좌표(motion-ir), y는 아래로 증가. 몸통 = 목–골반 길이(가로세로 비율 반영). 시간 단위는 '장'(초 단위는 출처 fps를 아는 경우만).

지표
- alternation: 두 발목의 앞뒤(가로) 차이 ÷ 몸통 부호가 진폭 AMP 이상으로 바뀐 횟수 → 걸음 수. 무릎도 같이 번갈아야 함(both_legs).
- periodicity: 골반 기준 상대 자세열(골반 이동 제거)의 자기 상관 최고값(지연 6–40장), 동작 진폭(상대 자세 표준편차)이 MIN_AMP 미만이면 0.
- support: 더 낮은(화면 아래) 발 = 지지 발(추정). 지지 발이 바뀐 횟수(높이 차 부호가 LIFT 몸통 이상으로 바뀜) · 지지 발이 정해진 장 비율.
- slide: 지지 중 발의 가로 이동(골반 아닌 화면 기준) 중앙값 ÷ 몸통 — 크면 발 미끄러짐(카메라가 따라가는 영상은 커질 수 있어 참고).
- still: 상대 자세 변화가 STILL 미만인 가장 긴 연속 장 수 ÷ 전체.
- travel: 골반 가로 이동 ÷ 몸통 ÷ 장(카메라 추적 영상은 0일 수 있어 판정에 안 씀).
걷기형(gait_like) = 걸음 ≥ 2 · 두 다리 함께 번갈아 · 주기성 ≥ PER · 지지 발 바뀜 ≥ 1 · 긴 정지 ≤ 0.5. (판정 기준은 이번 실험의 운영값 — 검증된 품질 기준 아님.)
"""
import math
import numpy as np

AMP, MIN_AMP, PER, STILL, LIFT, MIN_PERIOD = 0.15, 0.08, 0.3, 0.02, 0.05, 8


def _arr(ir, k, asp):
    v = np.array([p if p is not None else [np.nan, np.nan] for p in ir['actors'][0]['joints'][k]], float)
    v[:, 1] *= asp
    return v


def metrics(ir):
    asp = ir.get('aspect', 0.5625)
    N = ir['frames']
    if N < 8: return None
    J = {k: _arr(ir, k, asp) for k in ('neck', 'pelvis', 'kne_r', 'kne_l', 'ank_r', 'ank_l', 'wri_r', 'wri_l', 'elb_r', 'elb_l', 'head_t')}
    tor = np.nanmedian(np.linalg.norm(J['neck'] - J['pelvis'], axis=1)) or 1e-6
    def steps(a, b):
        d = (J[a][:, 0] - J[b][:, 0]) / tor; n = s = 0
        for x in d:
            if not np.isfinite(x) or abs(x) < AMP: continue
            g = 1 if x > 0 else -1
            if s and g != s: n += 1
            s = g
        return n
    st_a, st_k = steps('ank_l', 'ank_r'), steps('kne_l', 'kne_r')
    rel = np.stack([(J[k] - J['pelvis']) / tor for k in J if k != 'pelvis'], 1)   # (N, 10, 2)
    flat = rel.reshape(N, -1); flat = flat - np.nanmean(flat, 0)
    amp = float(np.nanmean(np.nanstd(flat, 0)))
    per, lag = 0.0, None
    measurable = N >= 2 * MIN_PERIOD + 4   # 짧은 조각(수집 SFA 걷기 대부분 13장)은 한 주기를 다 담지 못해 주기성 '측정 불가'
    if amp >= MIN_AMP and measurable:
        X = np.nan_to_num(flat); cs = []
        for L in range(1, min(48, N - 4)):
            a, b = X[:-L], X[L:]
            den = np.sqrt((a * a).sum() * (b * b).sum()) or 1e-9
            cs.append(float((a * b).sum() / den))
        # 11-06: 부드러운 동작은 짧은 지연에서 늘 상관이 높다 → 상관이 한 번 내려간(극소) 뒤 처음 다시 올라온 봉우리를 주기로
        i = 1
        while i < len(cs) - 1 and not (cs[i] <= cs[i - 1] and cs[i] <= cs[i + 1]): i += 1
        for j in range(i + 1, len(cs) - 1):
            if cs[j] >= cs[j - 1] and cs[j] >= cs[j + 1] and j + 1 >= MIN_PERIOD:
                per, lag = cs[j], j + 1; break
    # 지지(추정): 더 낮은(화면 아래) 발 = 지지 발, 바뀜 = (오른발 높이 − 왼발 높이)/몸통의 부호가 진폭 LIFT 이상으로 바뀐 횟수.
    # (11-06: '지지 중 발이 화면에서 멈춤' 조건은 카메라가 따라가는 영상·제자리 걷기에서 지지 발이 뒤로 흐르므로 쓰지 않는다.
    #  발바닥 막대가 없어 접촉 기하를 관측한 것이 아니라 추정이다.)
    ya, yb = J['ank_r'][:, 1], J['ank_l'][:, 1]
    dy = (ya - yb) / tor; sw = s_ = 0; foot = np.full(N, -1)
    for n, x in enumerate(dy):
        if not np.isfinite(x) or abs(x) < LIFT: foot[n] = foot[n - 1] if n else -1; continue
        g = 0 if x > 0 else 1   # 오른발이 더 아래(y 큼) → 오른발 지지
        if s_ and g != s_ - 1: sw += 1
        s_ = g + 1; foot[n] = g
    sup = foot >= 0
    xs = []
    for n in range(1, N):   # 지지 발의 화면 가로 이동(참고 — 카메라 추적 영상에서는 커짐)
        if foot[n] >= 0 and foot[n] == foot[n - 1]:
            k = 'ank_r' if foot[n] == 0 else 'ank_l'
            xs.append(abs(J[k][n, 0] - J[k][n - 1, 0]) / tor)
    slide = float(np.median(xs)) if xs else None
    dpose = np.r_[0, np.nanmean(np.linalg.norm(np.diff(rel, axis=0), axis=2), axis=1)]
    run = best = 0
    for d in dpose:
        run = run + 1 if d < STILL else 0; best = max(best, run)
    travel = float(abs(J['pelvis'][-1, 0] - J['pelvis'][0, 0]) / tor / N)
    m = dict(frames=N, steps_ankle=st_a, steps_knee=st_k, amp=round(amp, 3), periodicity=round(per, 3), period=lag,
             support=round(float(sup.mean()), 3), support_switch=sw, slide=round(slide, 3) if slide is not None else None,
             still=round(best / N, 3), travel=round(travel, 4), period_measurable=measurable)
    # 주기성을 잴 수 없는 짧은 조각은 '걸음 교대·지지 바뀜'만으로 걸음형(step_like)을 따로 표시하고 gait_like는 판정하지 않는다(None)
    m['step_like'] = bool(st_a >= 1 and st_k >= 1 and sw >= 1 and m['still'] <= 0.5)
    m['gait_like'] = bool(st_a >= 2 and st_k >= 1 and per >= PER and sw >= 1 and m['still'] <= 0.5) if measurable else None
    return m


# ---------- 반례(걷기로 통과하면 안 되는 것) ----------
def _base(N=48):
    J = dict(head_t=[50, 30], head_b=[50, 37], neck=[50, 38], pelvis=[50, 60], elb_r=[53, 47], wri_r=[54, 55], elb_l=[47, 47], wri_l=[46, 55],
             kne_r=[52, 72], ank_r=[52, 84], kne_l=[48, 72], ank_l=[48, 84])
    return {k: [list(v) for _ in range(N)] for k, v in J.items()}, N


def _ir(J, N):
    return dict(frames=N, aspect=0.5625, actors=[dict(joints=J)])


def counterexamples():
    out = {}
    J, N = _base();
    for k in J: J[k] = [[p[0] + 0.8 * n, p[1]] for n, p in enumerate(J[k])]
    out['정지 인물 옆으로 이동'] = _ir(J, N)
    J, N = _base()
    for n in range(N): J['ank_r'][n][0] += 6 * math.sin(n / 2.0); J['ank_l'][n][0] -= 6 * math.sin(n / 2.0)
    out['발목만 흔들기'] = _ir(J, N)
    J, N = _base()
    for n in range(N):
        ph = (n % 16) / 16; lift = math.sin(ph * math.pi) if ph < 0.5 else 0
        J['kne_r'][n] = [52 + 8 * lift, 72 - 6 * lift]; J['ank_r'][n] = [52 + 18 * lift, 84 - 14 * lift]
    out['킥 반복(한 다리)'] = _ir(J, N)
    J, N = _base()
    for n in range(N):
        s = 1 if (n // 3) % 2 else -1
        J['ank_r'][n][0] += 5 * s; J['ank_l'][n][0] -= 5 * s; J['kne_r'][n][0] += 2 * s; J['kne_l'][n][0] -= 2 * s
    out['발 교차 뒤집기(3장마다)'] = _ir(J, N)
    return out


def walk_synth(N=48, period=16, slide=0.0):
    """합성 걷기(양성 대조): 두 다리가 반 주기 어긋나 앞뒤로, 들린 발만 올라감. slide > 0이면 지지 발도 미끄러짐."""
    J, N = _base(N)
    for n in range(N):
        for side, ph0 in (('r', 0.0), ('l', 0.5)):
            ph = ((n / period) + ph0) % 1.0
            sw = math.sin(2 * math.pi * ph)
            lift = max(0.0, math.sin(2 * math.pi * ph)) * 3
            x0 = 50 + (2 if side == 'r' else -2)
            J[f'ank_{side}'][n] = [x0 + 7 * sw + slide * n * (1 if lift == 0 else 0), 84 - lift]
            J[f'kne_{side}'][n] = [x0 + 4 * sw, 72 - lift * 0.5]
        J['wri_r'][n][0] = 54 - 3 * math.sin(2 * math.pi * n / period); J['wri_l'][n][0] = 46 + 3 * math.sin(2 * math.pi * n / period)
    return _ir(J, N)


# ---------- 경로 실험(①–⑤) ----------
def cycle_loop(ir, need):
    """⑤ 주기 맞춘 반복: 주기(자기 상관 지연)를 찾고, 자세가 가장 비슷하게 돌아오는 [s, s+P) 구간만 반복. 이음매 2장은 골반 기준 자세를 섞고
    골반은 한 주기 이동량만큼 이어 간다. 주기를 못 찾으면 None."""
    m = metrics(ir)
    if not m or not m['period']: return None
    J = ir['actors'][0]['joints']; N = ir['frames']; P = m['period']; asp = ir.get('aspect', 0.5625)
    keys = [k for k in J]
    def rel(n):
        p = J['pelvis'][n]; return np.array([[J[k][n][0] - p[0], (J[k][n][1] - p[1]) * asp] for k in keys])
    best, s0 = 1e9, 0
    for s in range(0, N - P):
        d = float(np.linalg.norm(rel(s) - rel(s + P)))
        if d < best: best, s0 = d, s
    seg = list(range(s0, s0 + P))
    out = {k: [] for k in keys}; off = [0.0, 0.0]
    dx, dy = J['pelvis'][s0 + P][0] - J['pelvis'][s0][0], J['pelvis'][s0 + P][1] - J['pelvis'][s0][1]
    while len(out['pelvis']) < need:
        for i, n in enumerate(seg):
            for k in keys: out[k].append([J[k][n][0] + off[0], J[k][n][1] + off[1]])
        off = [off[0] + dx, off[1] + dy]
        # 이음매 2장 섞기: 다음 반복 첫 장과 지금 끝 장 사이
        L = len(out['pelvis'])
        if L >= 2:
            for k in keys:
                a = out[k][-1]; b = [J[k][seg[0]][0] + off[0], J[k][seg[0]][1] + off[1]]
                out[k][-1] = [(a[0] * 2 + b[0]) / 3, (a[1] * 2 + b[1]) / 3]
    for k in keys: out[k] = out[k][:need]
    return dict(frames=need, aspect=asp, actors=[dict(joints=out)])
