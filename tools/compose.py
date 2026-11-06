"""실제 동작 조각 잇기(11-06 사용자 '추천대로', 선택 B): 글의 동작마다 실제 동작 구간을 찾아 이어 붙여 .sfa를 만든다.
(배경: 단계 5 모델은 글만으로 걷기·달리기 주기를 만들지 못함 — 스타일 층 학습 글에 걷기 0회·달리기 9회. 수집 SFA에는 8장 이상 걷기 14·달리기 47 구간.)

1) 조각 목록(library): GPT 태그의 동작(verb·detail·from·to)마다 그 장 범위를 잘라 조각 하나로.
   - 스타일 층: stage2 추출 결과(<작업 폴더>/out/*.json — 비공개 원본 좌표라 저장소에 없음, 작업 폴더를 인자로) + tags_gpt.
   - 참고 층: data/stage2/user_sfa_ir(공개, 사용자 수집 SFA) + tags_usersfa_gpt. 품질 '나쁨' 구간은 뺀다.
   - 학습 제외 장(train_mask False)이 들어간 동작은 뺀다. MIN_CLIP장 미만은 뺀다.
2) 고르기: 같은 동사 조각 중 점수 = 설명 글자 겹침(2글자 조각 Jaccard) + 스타일 층 가산 + 품질 '좋음' 가산 + 길이 가산. 같은 조각을 연달아 쓰지 않음.
3) 잇기: 조각마다 몸통 길이를 같은 크기(T0, 화면 %)로 맞추고(골반 기준 확대·축소, 이동 거리도 같은 배율), 앞 조각 끝 골반에서 시작하게 옮긴다.
   조각이 MIN_LEN장보다 짧으면 반복해 늘린다(걷기·달리기 주기). 이음매는 BLEND장을 끼워 두 자세를 골반 기준으로 섞는다(계산, GPU 없음 —
   나중에 모델 이어 만들기로 바꿀 자리).
4) 마무리: tokens_to_sfa.finalize(nian41 리듬 입히기·캐릭터 시트·굵기).
사용: python tools/compose.py "<동작1> → <동작2> → ..." <출력.sfa> [--sheet 시트.sfa] [--style-dir stage2 작업 폴더] [--no-retime] [--synth] [--loco-dir 이동 장면 폴더] [--facing 도]
걷기·달리기는 스타일 층 실제 조각 우선(없으면 계산 주기 gait_cycle, --synth면 항상 계산 주기 — 11-06 사용자 '로봇 같다'로 기본값에서 뺌). 다른 동작은 태그 앞 PRE·뒤 POST장을 함께 자른다(예비 동작·마무리).
"""
import copy, gzip, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_CLIP, MIN_LEN, BLEND, T0 = 6, 20, 4, 12.0
# 11-06 사용자 판정 'B의 펀치는 치고 난 뒤 동작이 없어 어색': 태그 범위가 치는 순간만 잡는다(nian41 펀치 4–7장, 앞뒤는 '자세 잡기' 태그).
# 걷기·달리기 아닌 동작은 태그 앞 PRE장(예비 동작)·뒤 POST장(마무리)을 같이 자른다. 학습 제외 장·빈 관절을 만나면 그 앞에서 멈춘다.
PRE, POST = 6, 9
H_PER_T = 2.7   # 키 ÷ 몸통(수집 SFA 걷기·달리기 조각 2.6–2.9) — 키를 T0 × 2.7로 맞춘다
NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']


def _slice(ir, s, e):
    a = ir['actors'][0]
    fc = a.get('facing') or [None] * ir['frames']
    return dict(frames=e - s + 1, aspect=ir.get('aspect', 0.5625), joints={k: [list(p) for p in a['joints'][k][s:e + 1]] for k in NAMES},
                facing=list(fc[s:e + 1]))


def _ok(ir, m, n):
    return 0 <= n < ir['frames'] and m[n] and all(ir['actors'][0]['joints'][k][n] is not None for k in NAMES)


HOLD = ('자세 잡기',)


def _bounds(acts, i):
    """i번째 동작의 앞뒤 여유가 넘지 않을 경계: 앞·뒤의 다른 동작(자세 잡기 제외) 범위. 11-06: n41_07 펀치 뒤 여유 9장이 킥(21장~)과
    카메라 줌아웃(키 43 → 20)까지 들어가 마지막에 캐릭터가 작아졌다 → 마무리는 '자세 잡기'까지만."""
    lo, hi = -1, 10 ** 9
    for j, b in enumerate(acts):
        if j == i or b['verb'] in HOLD: continue
        if int(b['to']) < int(acts[i]['from']): lo = max(lo, int(b['to']))
        if int(b['from']) > int(acts[i]['to']): hi = min(hi, int(b['from']))
    return lo, hi


def _margin(ir, m, f, e, verb, lo=-1, hi=10 ** 9):
    """태그 범위 [f, e]를 앞 PRE·뒤 POST장까지 늘린다(쓸 수 있는 장, (lo, hi) 안까지만). 걷기·달리기는 늘리지 않는다.
    → (시작, 끝, 핵심 시작 위치)"""
    if verb in LOCO: return f, e, 0
    s = f
    while s > f - PRE and s - 1 > lo and _ok(ir, m, s - 1): s -= 1
    t = e
    while t < e + POST and t + 1 < hi and _ok(ir, m, t + 1): t += 1
    return s, t, f - s


LOCO_CLIPS = f'{ROOT}/data/stage2/loco_style_clips_2026-11-06.json'


def loco_clips(loco_dir):
    """nian41·나카무라 영상의 실제 이동 장면(find_locomotion 후보 → Claude 원본 대조로 쓸 구간만, 좌표는 비공개 작업 폴더)."""
    out = []
    if not loco_dir or not os.path.exists(LOCO_CLIPS): return out
    for r in json.load(open(LOCO_CLIPS, encoding='utf-8'))['clips']:
        p = f"{loco_dir}/{r['name']}.json"
        if not os.path.exists(p): continue
        ir = json.load(open(p)); a = ir['actors'][r.get('actor', 0)]
        one = dict(ir, actors=[a])
        c = dict(layer='style', src=r['name'], verb=r['verb'], detail=r['detail'], quality='좋음', **_slice(one, r['from'], r['to']))
        if r.get('reverse'):   # 시간 거꾸로(뒷걸음 → 다가가기, 목록의 reason 참고)
            c['joints'] = {k: v[::-1] for k, v in c['joints'].items()}; c['facing'] = c['facing'][::-1]
        out.append(c)
    return out


def library(style_dir=None, loco_dir=None):
    out = loco_clips(loco_dir)
    if style_dir and os.path.exists(f'{style_dir}/out/summary.json'):
        tags = {t['segment']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_gpt_2026-11-05.json', encoding='utf-8'))}
        for s in json.load(open(f'{style_dir}/out/summary.json'))['segments']:
            t = tags.get(s['name'])
            if not t: continue
            ir = json.load(open(f"{style_dir}/out/{s['name']}.json")); N = ir['frames']; m = ir['actors'][0].get('train_mask') or [True] * N
            for i, a in enumerate(t.get('actions', [])):
                f, e = int(a['from']), min(int(a['to']), N - 1)
                if e - f + 1 < MIN_CLIP or not all(m[f:e + 1]): continue
                if any(ir['actors'][0]['joints'][k][n] is None for k in NAMES for n in range(f, e + 1)): continue
                f2, e2, core = _margin(ir, m, f, e, a['verb'], *_bounds(t['actions'], i))
                out.append(dict(layer='style', src=s['name'], verb=a['verb'], detail=a['detail'], quality='좋음', core=[core, core + e - f],
                                **_slice(ir, f2, e2)))
    utags = {t['id']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_usersfa_gpt_2026-11-05.json', encoding='utf-8'))}
    for i, l in enumerate(gzip.open(f'{ROOT}/data/stage2/user_sfa_ir_2026-11-05.jsonl.gz', 'rt', encoding='utf-8')):
        sid = f'u{i:03d}'; t = utags.get(sid)
        if not t or t.get('quality') == '나쁨': continue
        ir = json.loads(l); N = ir['frames']
        for i, a in enumerate(t.get('actions', [])):
            f, e = int(a['from']), min(int(a['to']), N - 1)
            if e - f + 1 < MIN_CLIP: continue
            f2, e2, core = _margin(ir, [True] * N, f, e, a['verb'], *_bounds(t['actions'], i))
            out.append(dict(layer='ref', src=sid, verb=a['verb'], detail=a['detail'], quality=t.get('quality'), core=[core, core + e - f],
                            **_slice(ir, f2, e2)))
    return out


def _grams(s):
    s = ''.join(ch for ch in s if not ch.isspace())
    return {s[i:i + 2] for i in range(len(s) - 1)}


LOCO = ('걷기', '달리기')


def travel(c):
    """조각 안 골반 가로 이동 ÷ 몸통(이동하는 걷기·달리기를 고르는 기준, 11-06: 제자리걸음 조각이 뽑혀 걷기로 안 보임)."""
    J, asp = c['joints'], c['aspect']
    T = sorted(_torso(J, n, asp) for n in range(c['frames']))[c['frames'] // 2]
    return abs(J['pelvis'][-1][0] - J['pelvis'][0][0]) / T / max(c['frames'], 1)


_GC = {}


def _gait(c):
    import gait_eval as G
    k = (c['src'], c['frames'], c['verb'])
    if k not in _GC:
        _GC[k] = G.metrics(dict(frames=c['frames'], aspect=c['aspect'], actors=[dict(joints=c['joints'])])) or {}
    return _GC[k]


def pick(lib, verb, detail='', avoid=()):
    cand = [c for c in lib if c['verb'] == verb and c['src'] not in avoid] or [c for c in lib if c['verb'] == verb]
    if not cand: return None
    # 11-06: 걷기·달리기 아닌 동작은 스타일 층(nian41·나카무라) 조각이 있으면 그 안에서만 고른다(몸동작 스타일 = 두 작가 규칙 ·
    # 설명 글 겹침 때문에 수집 SFA 펀치 u008(13장)이 nian41 펀치 10개를 이기던 것)
    # 11-06 사용자 '공식 걷기는 로봇 같다' → 걷기·달리기도 스타일 층 실제 조각이 있으면 그 안에서만
    if any(c['layer'] == 'style' for c in cand): cand = [c for c in cand if c['layer'] == 'style']
    g = _grams(detail)
    def score(c):
        cg = _grams(c['detail']); sim = len(g & cg) / max(len(g | cg), 1) if g else 0
        mv = min(travel(c) / 0.08, 1.0) * 0.3 if verb in LOCO else 0   # 걷기·달리기는 실제로 앞으로 나아가는 조각 우선
        if verb in LOCO:   # 11-06 걷기 판정(gait_eval): 실제 걸음 교대·지지 바뀜이 있는 조각 우선(제자리·정면 조각 u441은 걸음 0으로 재짐)
            gm = _gait(c)
            mv += (0.5 if gm.get('gait_like') else 0.35 if gm.get('step_like') else 0) + min(gm.get('steps_ankle', 0), 4) * 0.05
        return sim + mv + (0.3 if c['layer'] == 'style' else 0) + (0.2 if c['quality'] == '좋음' else 0) + min(_core_len(c), 24) / 120
    return max(cand, key=score)


def _core_len(c):
    k = c.get('core'); return k[1] - k[0] + 1 if k else c['frames']


def _torso(J, n, asp):
    return math.hypot(J['neck'][n][0] - J['pelvis'][n][0], (J['neck'][n][1] - J['pelvis'][n][1]) * asp) or 1e-6


def _norm(c):
    """조각 → 몸통 T0 크기, 첫 장 골반 원점 기준 좌표(이동 포함)."""
    J, asp = c['joints'], c['aspect']
    # 크기 = 머리 위 ~ 더 먼 발목 키의 90분위(11-06: 수집 SFA는 작가마다 다리 비율이 달라 몸통으로 맞추면 펀치 조각(키 2.4 몸통)이
    # 걷기 조각(2.85)보다 작게 보였다 → 같은 캐릭터가 조각마다 같은 키로 보이게)
    Hs = sorted(max(math.hypot(J['head_t'][n][0] - J[a][n][0], (J['head_t'][n][1] - J[a][n][1]) * asp) for a in ('ank_r', 'ank_l'))
                for n in range(c['frames']))
    Hh = Hs[min(len(Hs) - 1, int(len(Hs) * 0.9))] or 1e-6
    # 11-06: 카메라 줌·원근으로 조각 안에서 크기가 바뀌면(나카무라 달리기 nkm_16 키 23 → 38) 장마다 맞춘다. 장 크기 = max(키, 몸통 × 2.7)
    # (웅크리면 키만 줄고, 카메라 쪽으로 숙이면 몸통만 줄어 둘 중 큰 쪽) 9장 이동 평균. 조각 90분위와 1.25배 넘게 다른 장이 있을 때만.
    F = c['frames']
    size = [max(max(math.hypot(J['head_t'][n][0] - J[a][n][0], (J['head_t'][n][1] - J[a][n][1]) * asp) for a in ('ank_r', 'ank_l')),
                _torso(J, n, asp) * H_PER_T) for n in range(F)]
    sz = sorted(size)[min(F - 1, int(F * 0.9))] or 1e-6
    if max(sz / max(x, 1e-6) for x in size) > 1.25:
        sm = [sum(size[max(0, i - 4):i + 5]) / len(size[max(0, i - 4):i + 5]) for i in range(F)]
        ks = [T0 * H_PER_T / max(x, 1e-6) for x in sm]
    else:
        ks = [T0 * H_PER_T / Hh] * F
    out = {n_: [] for n_ in NAMES}; P = [0.0, 0.0]
    for n in range(F):
        if n: P = [P[0] + (J['pelvis'][n][0] - J['pelvis'][n - 1][0]) * ks[n], P[1] + (J['pelvis'][n][1] - J['pelvis'][n - 1][1]) * ks[n]]
        pv = J['pelvis'][n]
        for n_ in NAMES: out[n_].append([P[0] + (J[n_][n][0] - pv[0]) * ks[n], P[1] + (J[n_][n][1] - pv[1]) * ks[n]])
    return out


def _loop(J, F, need):
    """F장 조각을 need장 이상으로 반복(골반 이동은 이어서 누적)."""
    if F >= need: return J, F
    out = {k: list(v) for k, v in J.items()}; n = F
    dx, dy = J['pelvis'][-1][0] - J['pelvis'][0][0], J['pelvis'][-1][1] - J['pelvis'][0][1]
    rep = 1
    while n < need:
        for k in NAMES: out[k] += [[p[0] + dx * rep, p[1] + dy * rep] for p in J[k]]
        n += F; rep += 1
    return out, n


CAM_LO, CAM_HI, CAM_SMOOTH = 30.0, 70.0, 9


def follow(J, lo=CAM_LO, hi=CAM_HI, w=CAM_SMOOTH):
    """따라가는 카메라(11-06: 걷기 2주기 + 달리기 2주기 이동이 화면 폭보다 길어 캐릭터가 화면 밖으로 나감).
    골반 x가 [lo, hi] 안이면 카메라는 멈춰 있고, 벗어날 때만 벗어난 만큼 옮긴다(가장자리 따라가기). 갑자기 움직이지 않게 w장 이동 평균.
    카메라가 움직이는 동안은 땅에 디딘 발도 화면에서 뒤로 흐른다(배경 없는 화면에서 카메라 이동은 그렇게 보임)."""
    o, off = 0.0, []
    for p in J['pelvis']:
        x = p[0] + o
        if x > hi: o -= x - hi
        elif x < lo: o += lo - x
        off.append(o)
    h = w // 2; N = len(off)
    sm = [sum(off[max(0, i - h):min(N, i + h + 1)]) / (min(N, i + h + 1) - max(0, i - h)) for i in range(N)]
    return {k: [[q[0] + sm[n], q[1]] for n, q in enumerate(v)] for k, v in J.items()}


def _cmean(fs):
    fs = [f for f in fs if f is not None]
    if not fs: return None
    x = sum(math.cos(math.radians(f)) for f in fs); y = sum(math.sin(math.radians(f)) for f in fs)
    return math.degrees(math.atan2(y, x)) % 360 if math.hypot(x, y) > 1e-6 else None


def _side(f):
    """몸 방향(도) → 화면에서 얼굴이 향한 쪽: +1 오른쪽(180–360, 시트 '좌측' 쪽) · −1 왼쪽 · 0 정면/후면 근처(±20°)."""
    if f is None: return 0
    s = math.sin(math.radians(f))
    return 0 if abs(s) < 0.34 else (1 if s < 0 else -1)


def _clip_dir(c, C, verb):
    """조각이 향한 화면 쪽. 걷기·달리기 = 골반 이동 방향, 그 밖 = 몸 방향(없으면 손목을 가장 멀리 뻗은 쪽)."""
    if verb in LOCO:
        dx = C['pelvis'][-1][0] - C['pelvis'][0][0]
        if abs(dx) > 1e-6: return 1 if dx > 0 else -1
    d = _side(_cmean(c.get('facing') or []))
    if d: return d
    best = max(range(len(C['neck'])), key=lambda n: max(abs(C[w][n][0] - C['neck'][n][0]) for w in ('wri_r', 'wri_l')))
    w = max(('wri_r', 'wri_l'), key=lambda w: abs(C[w][best][0] - C['neck'][best][0]))
    return 1 if C[w][best][0] >= C['neck'][best][0] else -1


def _front_half(f, side, lim=20):
    """포즈로 잰 몸 방향은 뒤쪽으로 치우친다(n41_07 펀치 10–20장: 원본은 옆모습인데 207–237로 잼 → 가면이 사라짐). 향한 쪽 옆모습
    (오른쪽 270 · 왼쪽 90)에서 뒤쪽으로 lim°까지만 허용하고, 앞쪽(정면 쪽)은 그대로 둔다."""
    if f is None or not side: return f
    base = 270.0 if side > 0 else 90.0
    d = ((f - base + 180) % 360) - 180   # 오른쪽 옆(270) 기준: + 정면 쪽(→360) · − 뒤쪽(→180)
    if side < 0: d = -d                  # 왼쪽 옆(90) 기준: 정면(0) 쪽이 −
    if d < -lim: d = -lim
    return (base + (d if side > 0 else -d)) % 360


def _lerp_angle(a, b, t):
    if a is None or b is None: return b if t >= 0.5 else a
    d = ((b - a + 180) % 360) - 180
    return (a + d * t) % 360


def _smooth_facing(fs, w=5):
    """몸 방향 떨림 줄이기(포즈 추정 방향은 장마다 흔들림): 펼친(unwrap) 각도의 w장 이동 평균."""
    if any(f is None for f in fs) or len(fs) < 3: return fs
    u = [fs[0]]
    for f in fs[1:]: u.append(u[-1] + ((f - u[-1] + 180) % 360) - 180)
    h = w // 2; N = len(u)
    return [round((sum(u[max(0, i - h):i + h + 1]) / len(u[max(0, i - h):i + h + 1])) % 360, 2) for i in range(N)]


def compose(acts, lib, min_len=MIN_LEN, blend=BLEND, synth=False, camera=True):
    """acts: [(verb, detail)] → (ir, 쓴 조각 목록). synth: 걷기·달리기는 애니메이션 원리로 계산한 주기(gait_cycle)를 쓴다
    (11-06 사용자 판정: 실제 걷기 조각은 어느 판도 걷기로 안 보임 · 걷기 출처 선택 1 '추천대로')."""
    J = {k: [] for k in NAMES}; used = []; picks = []; FC = []; want = None
    for verb, detail in acts:
        c = None if (synth and verb in LOCO) else pick(lib, verb, detail, avoid=used[-1:])
        if c is None and verb in LOCO:   # 실제 조각이 없을 때만 계산 주기(11-06 사용자: 공식 걷기는 로봇 같다 → 기본값 아님)
            import gait_cycle as GC
            c = GC.clip(verb, detail, need=min_len)
        if c is None: raise ValueError(f'조각 없음: {verb}')
        used.append(c['src']); picks.append(dict(verb=verb, src=c['src'], layer=c['layer'], frames=c['frames'], detail=c['detail']))
        C = _norm(c)
        # 몸 방향(11-06 사용자: 가면이 계속 정면만 봄 — 조각 잇기가 방향을 넘기지 않았다). 첫 조각의 화면 쪽을 기준으로,
        # 반대쪽을 향한 조각은 좌우를 뒤집는다(골반 기준, 몸 방향 f → 360 − f).
        d = _clip_dir(c, C, verb); fcs = list(c.get('facing') or [None] * c['frames'])
        if want is None: want = d
        if d and d != want:
            C = {k: [[-p[0], p[1]] for p in v] for k, v in C.items()}
            fcs = [None if f is None else (360 - f) % 360 for f in fcs]
        if all(f is None for f in fcs): fcs = [270.0 if want > 0 else 90.0] * c['frames']   # 방향 없는 조각(계산·수집 SFA) = 옆모습
        else: fcs = [_front_half(f, want) for f in fcs]
        if verb in LOCO and c['layer'] != 'synth':   # 반복은 걷기·달리기만(11-06 GPT: 짧은 펀치까지 반복하던 것). 주기를 잴 수 있으면 주기 맞춘 반복(경로 실험: HMDB 달리기 8/8 vs 지금 반복 5/8)
            import gait_eval as G
            cl = G.cycle_loop(dict(frames=c['frames'], aspect=c['aspect'], actors=[dict(joints=C)]), min_len) if c['frames'] >= 2 * 8 + 4 else None
            if cl: C, F = cl['actors'][0]['joints'], cl['frames']
            else: C, F = _loop(C, c['frames'], min_len)
            fm = _cmean(fcs); fcs = [fm] * F   # 반복한 걷기·달리기는 조각 평균 방향
        else:
            F = c['frames']
        fcs = _smooth_facing(fcs)
        if J['pelvis']:
            P = J['pelvis'][-1]
            last = {k: [J[k][-1][0] - P[0], J[k][-1][1] - P[1]] for k in NAMES}
            first = {k: [C[k][0][0] - C['pelvis'][0][0], C[k][0][1] - C['pelvis'][0][1]] for k in NAMES}
            for b in range(1, blend + 1):   # 이음매: 골반 기준 자세를 직선으로 섞고, 골반은 앞 조각 끝 속도로 조금씩
                t = b / (blend + 1)
                v = [J['pelvis'][-1][0] - J['pelvis'][-2][0], J['pelvis'][-1][1] - J['pelvis'][-2][1]] if len(J['pelvis']) > 1 else [0, 0]
                pp = [P[0] + v[0] * b * 0.5, P[1] + v[1] * b * 0.5]
                for k in NAMES:
                    r = [last[k][0] + (first[k][0] - last[k][0]) * t, last[k][1] + (first[k][1] - last[k][1]) * t]
                    J[k].append([pp[0] + r[0], pp[1] + r[1]])
                FC.append(_lerp_angle(FC[-1], fcs[0], t))
            P = J['pelvis'][-1]
            for k in NAMES: J[k] += [[P[0] + p[0], P[1] + p[1]] for p in C[k]]
        else:
            for k in NAMES: J[k] += [[50 + p[0], 60 + p[1]] for p in C[k]]
        FC += fcs
    if camera: J = follow(J)
    N = len(J['pelvis'])
    ir = dict(schema='motion-ir/1', fps=[24, 24], aspect=0.5625, frames=N,
              actors=[dict(slot=0, color='blue', joints=J, thickness=[{} for _ in range(N)], hidden=[[] for _ in range(N)],
                           smear=[[] for _ in range(N)], head_fill=[True] * N, facing=FC)])
    return ir, picks


def parse(text):
    acts = []
    for a in text.split('→'):
        a = a.strip()
        if not a: continue
        v, _, d = a.partition(':')
        acts.append((v.strip(), d.strip()))
    return acts


if __name__ == '__main__':
    import tokens_to_sfa as T, motion_ir as M
    args = sys.argv[1:]
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    lib = library(opt('--style-dir'), opt('--loco-dir'))
    ir, picks = compose(parse(args[0]), lib, synth='--synth' in args)
    fc = opt('--facing')
    out = args[1]; name = os.path.splitext(os.path.basename(out))[0]
    ir, root = T.finalize(ir, opt('--sheet'), center=True, name=name, facing=float(fc) if fc else None, retime='--no-retime' not in args)
    M.save_sfa(root, out, name)
    print(json.dumps(dict(frames=ir['frames'], picks=picks), ensure_ascii=False))
