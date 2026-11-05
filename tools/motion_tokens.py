"""스틱맨 중간 표현(motion-ir/1) ↔ 동작 토큰(단계 3 거대 모델 학습용, LottieGPT식 키프레임 + 의미 단위).

키프레임 하나 = 23토큰: <t{장 간격}> <x{골반 x}> <y{골반 y}> <s{몸통 길이}> + 뼈마다 <a{각도}>(<l{길이}>, 몸통 제외)
- 10 뼈 = 목→골반(몸통), 목→팔꿈치 r/l, 팔꿈치→손목 r/l, 골반→무릎 r/l, 무릎→발목 r/l, 목→머리 꼭대기. 화면 기준 각도, ANG_BINS칸.
- 뼈 길이 토큰: 화면 투영 길이 / 몸통(원근·가림으로 바뀜). 길이 없이 10초판 고정 비율(RATIO)로 되살리면 끝점 오차 중앙 0.21–0.22 몸통(11-05 측정)이라 넣었다.
- 골반 위치 x·y는 화면 %를 POS_BINS칸(화면 밖 −50…150% 허용), 몸통 길이는 화면 폭 %를 로그 SCALE_BINS칸.
- 키프레임: 원본 그림 구간(drawings)이 있으면 그 가운데 장, 없으면 KEY_STEP장마다. 사이 장은 디코딩 때 각도·위치 직선 보간.
- 숨김·스미어·몸 방향은 이번 판에 넣지 않는다(시험 범위: 자세 흐름).
"""
import math
import numpy as np

ANG_BINS, POS_BINS, SCALE_BINS, MAX_GAP, KEY_STEP = 72, 128, 32, 12, 2
LEN_BINS, LEN_LO, LEN_HI = 16, 0.15, 1.8   # 뼈 길이 / 몸통(화면에 보이는 투영 길이 — 원근·가림으로 바뀐다)
BONES = [('neck', 'pelvis'), ('neck', 'elb_r'), ('elb_r', 'wri_r'), ('neck', 'elb_l'), ('elb_l', 'wri_l'),
         ('pelvis', 'kne_r'), ('kne_r', 'ank_r'), ('pelvis', 'kne_l'), ('kne_l', 'ank_l'), ('neck', 'head_t')]
RATIO = {('neck', 'elb_r'): 0.70, ('elb_r', 'wri_r'): 0.44, ('neck', 'elb_l'): 0.70, ('elb_l', 'wri_l'): 0.44,
         ('pelvis', 'kne_r'): 0.91, ('kne_r', 'ank_r'): 0.75, ('pelvis', 'kne_l'): 0.91, ('kne_l', 'ank_l'): 0.75,
         ('neck', 'head_t'): 0.75 + 0.0}   # 몸통 단위(10초판). 목→머리 꼭대기 = 머리 지름
NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']
VOCAB = ([f'<t{i}>' for i in range(1, MAX_GAP + 1)] + [f'<x{i}>' for i in range(POS_BINS)] + [f'<y{i}>' for i in range(POS_BINS)]
         + [f'<s{i}>' for i in range(SCALE_BINS)] + [f'<a{i}>' for i in range(ANG_BINS)] + [f'<l{i}>' for i in range(LEN_BINS)] + ['<motion>', '</motion>'])


def _q(v, lo, hi, n):
    return int(min(n - 1, max(0, round((v - lo) / (hi - lo) * (n - 1)))))


def _dq(i, lo, hi, n):
    return lo + i / (n - 1) * (hi - lo)


def keyframes(a, N):
    D = a.get('drawings')
    ks = sorted({(s + e) // 2 for s, e in D}) if D else list(range(0, N, KEY_STEP))
    if ks[-1] != N - 1: ks.append(N - 1)
    out, prev = [], None
    for k in ks:            # 간격이 MAX_GAP을 넘으면 사이에 키를 더 넣는다
        while prev is not None and k - prev > MAX_GAP:
            prev += MAX_GAP; out.append(prev)
        out.append(k); prev = k
    return [k for k in out if a['joints']['neck'][k] and a['joints']['pelvis'][k]]


def encode(ir, slot=0):
    """→ 토큰 목록(키프레임이 없거나 관절이 빠진 키는 건너뜀)."""
    a = ir['actors'][slot]; J = a['joints']; asp = ir.get('aspect', 0.5625); N = ir['frames']
    toks, prev = ['<motion>'], None
    for k in keyframes(a, N):
        if any(J[p][k] is None or J[q][k] is None for p, q in BONES): continue
        P = J['pelvis'][k]; T = math.hypot(J['neck'][k][0] - P[0], (J['neck'][k][1] - P[1]) * asp) or 1e-3
        gap = 1 if prev is None else min(MAX_GAP, k - prev)
        toks += [f'<t{gap}>', f'<x{_q(P[0], -50, 150, POS_BINS)}>', f'<y{_q(P[1], -50, 150, POS_BINS)}>',
                 f'<s{_q(math.log(T), math.log(1), math.log(80), SCALE_BINS)}>']
        for p, q in BONES:
            dx, dy = J[q][k][0] - J[p][k][0], (J[q][k][1] - J[p][k][1]) * asp
            toks.append(f'<a{_q(math.atan2(dy, dx), -math.pi, math.pi, ANG_BINS + 1) % ANG_BINS}>')
            if (p, q) != ('neck', 'pelvis'):
                toks.append(f'<l{_q(math.hypot(dx, dy) / T, LEN_LO, LEN_HI, LEN_BINS)}>')
        prev = k
    return toks + ['</motion>']


def decode(toks, aspect=0.5625):
    """토큰 → motion-ir/1(장 = 키 간격 합 + 1, 사이 장 보간). 잘못된 토큰 묶음은 건너뛴다."""
    body = [t for t in toks if t not in ('<motion>', '</motion>')]
    keys, i = [], 0
    K = 4 + 10 + 9
    while i + K <= len(body):
        g = body[i:i + K]
        try:
            gap = int(g[0][2:-1]) if g[0].startswith('<t') else None
            x = _dq(int(g[1][2:-1]), -50, 150, POS_BINS) if g[1].startswith('<x') else None
            y = _dq(int(g[2][2:-1]), -50, 150, POS_BINS) if g[2].startswith('<y') else None
            T = math.exp(_dq(int(g[3][2:-1]), math.log(1), math.log(80), SCALE_BINS)) if g[3].startswith('<s') else None
            angs = [int(t[2:-1]) / ANG_BINS * 2 * math.pi - math.pi for t in g[4:] if t.startswith('<a')]
            lens = [_dq(int(t[2:-1]), LEN_LO, LEN_HI, LEN_BINS) for t in g[4:] if t.startswith('<l')]
        except ValueError:
            i += 1; continue
        if None in (gap, x, y, T) or len(angs) != 10 or len(lens) != 9:
            i += 1; continue
        keys.append((gap, x, y, T, angs, lens)); i += K
    if not keys:
        return None
    times = np.cumsum([0] + [k[0] for k in keys[1:]])
    N = int(times[-1]) + 1
    def pose(x, y, T, angs, lens):
        J = {'pelvis': (x, y)}
        Ls = [T] + [T * l for l in lens]
        for (p, q), th, L in zip(BONES, angs, Ls):
            if (p, q) == ('neck', 'pelvis'):
                J['neck'] = (x - L * math.cos(th), y - L * math.sin(th) / aspect); continue
            b = J[p]; J[q] = (b[0] + L * math.cos(th), b[1] + L * math.sin(th) / aspect)
        J['head_b'] = J['neck']
        return J
    P = [pose(*k[1:]) for k in keys]
    names = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']
    joints = {n: [] for n in names}
    for f in range(N):
        j = int(np.searchsorted(times, f, side='right') - 1); j2 = min(j + 1, len(keys) - 1)
        w = 0 if j2 == j else (f - times[j]) / (times[j2] - times[j])
        for n in names:
            a_, b_ = P[j][n], P[j2][n]
            joints[n].append([a_[0] + (b_[0] - a_[0]) * w, a_[1] + (b_[1] - a_[1]) * w])
    return dict(schema='motion-ir/1', fps=[24, 24], aspect=aspect, frames=N,
                actors=[dict(slot=0, color='blue', joints=joints, thickness=[{} for _ in range(N)], hidden=[[] for _ in range(N)],
                             smear=[[] for _ in range(N)], head_fill=[True] * N, facing=[None] * N)],
                camera=[[0.0, 0.0, 1.0] for _ in range(N)], timeline=[], source=dict(generated=True))
