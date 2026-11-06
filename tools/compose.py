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
사용: python tools/compose.py "<동작1> → <동작2> → ..." <출력.sfa> [--sheet 시트.sfa] [--style-dir stage2 작업 폴더] [--no-retime] [--facing 도]
"""
import copy, gzip, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_CLIP, MIN_LEN, BLEND, T0 = 6, 20, 4, 12.0
NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']


def _slice(ir, s, e):
    a = ir['actors'][0]
    return dict(frames=e - s + 1, aspect=ir.get('aspect', 0.5625), joints={k: [list(p) for p in a['joints'][k][s:e + 1]] for k in NAMES})


def library(style_dir=None):
    out = []
    if style_dir and os.path.exists(f'{style_dir}/out/summary.json'):
        tags = {t['segment']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_gpt_2026-11-05.json', encoding='utf-8'))}
        for s in json.load(open(f'{style_dir}/out/summary.json'))['segments']:
            t = tags.get(s['name'])
            if not t: continue
            ir = json.load(open(f"{style_dir}/out/{s['name']}.json")); N = ir['frames']; m = ir['actors'][0].get('train_mask') or [True] * N
            for a in t.get('actions', []):
                f, e = int(a['from']), min(int(a['to']), N - 1)
                if e - f + 1 < MIN_CLIP or not all(m[f:e + 1]): continue
                if any(ir['actors'][0]['joints'][k][n] is None for k in NAMES for n in range(f, e + 1)): continue
                out.append(dict(layer='style', src=s['name'], verb=a['verb'], detail=a['detail'], quality='좋음', **_slice(ir, f, e)))
    utags = {t['id']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_usersfa_gpt_2026-11-05.json', encoding='utf-8'))}
    for i, l in enumerate(gzip.open(f'{ROOT}/data/stage2/user_sfa_ir_2026-11-05.jsonl.gz', 'rt', encoding='utf-8')):
        sid = f'u{i:03d}'; t = utags.get(sid)
        if not t or t.get('quality') == '나쁨': continue
        ir = json.loads(l); N = ir['frames']
        for a in t.get('actions', []):
            f, e = int(a['from']), min(int(a['to']), N - 1)
            if e - f + 1 < MIN_CLIP: continue
            out.append(dict(layer='ref', src=sid, verb=a['verb'], detail=a['detail'], quality=t.get('quality'), **_slice(ir, f, e)))
    return out


def _grams(s):
    s = ''.join(ch for ch in s if not ch.isspace())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def pick(lib, verb, detail='', avoid=()):
    cand = [c for c in lib if c['verb'] == verb and c['src'] not in avoid] or [c for c in lib if c['verb'] == verb]
    if not cand: return None
    g = _grams(detail)
    def score(c):
        cg = _grams(c['detail']); sim = len(g & cg) / max(len(g | cg), 1) if g else 0
        return sim + (0.3 if c['layer'] == 'style' else 0) + (0.2 if c['quality'] == '좋음' else 0) + min(c['frames'], 24) / 120
    return max(cand, key=score)


def _torso(J, n, asp):
    return math.hypot(J['neck'][n][0] - J['pelvis'][n][0], (J['neck'][n][1] - J['pelvis'][n][1]) * asp) or 1e-6


def _norm(c):
    """조각 → 몸통 T0 크기, 첫 장 골반 원점 기준 좌표(이동 포함)."""
    J, asp = c['joints'], c['aspect']
    T = sorted(_torso(J, n, asp) for n in range(c['frames']))[c['frames'] // 2]
    k = T0 / T; p0 = J['pelvis'][0]
    return {n_: [[(p[0] - p0[0]) * k, (p[1] - p0[1]) * k] for p in J[n_]] for n_ in NAMES}


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


def compose(acts, lib, min_len=MIN_LEN, blend=BLEND):
    """acts: [(verb, detail)] → (ir, 쓴 조각 목록)."""
    J = {k: [] for k in NAMES}; used = []; picks = []
    for verb, detail in acts:
        c = pick(lib, verb, detail, avoid=used[-1:])
        if c is None: raise ValueError(f'조각 없음: {verb}')
        used.append(c['src']); picks.append(dict(verb=verb, src=c['src'], layer=c['layer'], frames=c['frames'], detail=c['detail']))
        C = _norm(c); C, F = _loop(C, c['frames'], min_len)
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
            P = J['pelvis'][-1]
            for k in NAMES: J[k] += [[P[0] + p[0], P[1] + p[1]] for p in C[k]]
        else:
            for k in NAMES: J[k] += [[50 + p[0], 60 + p[1]] for p in C[k]]
    N = len(J['pelvis'])
    ir = dict(schema='motion-ir/1', fps=[24, 24], aspect=0.5625, frames=N,
              actors=[dict(slot=0, color='blue', joints=J, thickness=[{} for _ in range(N)], hidden=[[] for _ in range(N)],
                           smear=[[] for _ in range(N)], head_fill=[True] * N, facing=[None] * N)])
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
    lib = library(opt('--style-dir'))
    ir, picks = compose(parse(args[0]), lib)
    fc = opt('--facing')
    out = args[1]; name = os.path.splitext(os.path.basename(out))[0]
    ir, root = T.finalize(ir, opt('--sheet'), center=True, name=name, facing=float(fc) if fc else None, retime='--no-retime' not in args)
    M.save_sfa(root, out, name)
    print(json.dumps(dict(frames=ir['frames'], picks=picks), ensure_ascii=False))
