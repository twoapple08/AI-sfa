"""단계 4(글 → 정지 포즈) 학습 쌍 + 포즈 검사.

포즈 하나 = 동작 토큰 키프레임 1개(<motion> <t1> x y s + 뼈 10개 각도·길이 </motion>, motion_tokens와 같은 어휘).
- 스타일 층: GPT 태그 actions 중 그 장을 덮는 동작의 verb + detail이 글. 학습 제외 장은 뺀다.
- 기본기 층(수집 SFA): GPT 태그(있으면) actions의 verb + detail, 없으면 '스틱맨 자세'. 앞에 <ref>.
- 비슷한 자세 줄이기: 골반 기준·몸통 단위로 0.1 격자에 반올림한 자세가 같으면 하나만(10-28 유사 중복과 같은 기준).
- plausible(): 디코딩한 포즈가 사람 몸으로 말이 되는지 — 좌우 같은 뼈 길이 비 ≤ 5(원근으로 한쪽이 짧아지는 정상 자세가 많다 — 2.5면 정답 자료 7%가 걸림, 5면 0.8%), 다리(허벅지+정강이) ≥ 0.6 몸통, 팔·다리 뼈 ≥ 0.1 몸통.
사용: python tools/stage4_pack.py <stage2_easy 작업 폴더> <출력 jsonl>
"""
import gzip, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT  # noqa: E402
from stage3_pack import _slice  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pose_key(ir, k):
    J = ir['actors'][0]['joints']; asp = ir.get('aspect', 0.5625); P = J['pelvis'][k]
    T = math.hypot(J['neck'][k][0] - P[0], (J['neck'][k][1] - P[1]) * asp) or 1
    return tuple(round((J[n][k][0] - P[0]) / T, 1) for n in MT.NAMES if n in J) + \
        tuple(round((J[n][k][1] - P[1]) * asp / T, 1) for n in MT.NAMES if n in J)


def one(ir, k):
    sub = _slice(ir, k, k + 1)
    sub['actors'][0].pop('drawings', None)
    return MT.encode(sub)


def text_at(tag, k, default, near=3):
    acts = [a for a in (tag or {}).get('actions', []) if a['from'] <= k <= a['to']]
    if not acts:   # GPT는 시트 표본 장으로 범위를 적어 사이 장이 빈다 → near장 안의 가장 가까운 동작
        cand = [(min(abs(k - a['from']), abs(k - a['to'])), a) for a in (tag or {}).get('actions', [])]
        cand = [c for c in cand if c[0] <= near]
        if cand: acts = [min(cand, key=lambda c: c[0])[1]]
    return ' / '.join(f"{a['verb']}: {a['detail']}" for a in acts) if acts else default


def plausible(ir):
    J = ir['actors'][0]['joints']; asp = ir.get('aspect', 0.5625)
    d = lambda a, b: math.hypot(J[a][0][0] - J[b][0][0], (J[a][0][1] - J[b][0][1]) * asp)
    T = d('neck', 'pelvis') or 1e-6
    pairs = [(('neck', 'elb_r'), ('neck', 'elb_l')), (('elb_r', 'wri_r'), ('elb_l', 'wri_l')),
             (('pelvis', 'kne_r'), ('pelvis', 'kne_l')), (('kne_r', 'ank_r'), ('kne_l', 'ank_l'))]
    for a, b in pairs:
        la, lb = d(*a), d(*b)
        if min(la, lb) < 0.1 * T or max(la, lb) / max(min(la, lb), 1e-6) > 5.0: return False
    return d('pelvis', 'kne_r') + d('kne_r', 'ank_r') >= 0.6 * T and d('pelvis', 'kne_l') + d('kne_l', 'ank_l') >= 0.6 * T


def main(work, outp):
    tags = {t['segment']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_gpt_2026-11-05.json', encoding='utf-8'))}
    utp = f'{ROOT}/data/stage2/tags_usersfa_gpt_2026-11-05.json'
    utags = {t['id']: t for t in json.load(open(utp, encoding='utf-8'))} if os.path.exists(utp) else {}
    rows, seen = [], set()
    def add(layer, src, ir, k, prompt):
        J = ir['actors'][0]['joints']
        if any(J[n][k] is None for n in MT.NAMES if n in J): return
        key = pose_key(ir, k)
        if key in seen: return
        seen.add(key); rows.append(dict(layer=layer, src=src, frame=k, prompt=prompt, tokens=one(ir, k)))
    for s in json.load(open(f'{work}/out/summary.json'))['segments']:
        ir = json.load(open(f"{work}/out/{s['name']}.json")); m = ir['actors'][0].get('train_mask') or [True] * ir['frames']
        for k in range(ir['frames']):
            if m[k]: add('style', s['name'], ir, k, text_at(tags.get(s['name']), k, '스틱맨 액션 자세'))
    for i, l in enumerate(gzip.open(f'{ROOT}/data/stage2/user_sfa_ir_2026-11-05.jsonl.gz', 'rt', encoding='utf-8')):
        ir = json.loads(l); sid = f'u{i:03d}'; t = utags.get(sid)
        if t and t.get('quality') == '나쁨': continue
        for k in range(ir['frames']):
            add('ref', sid, ir, k, '<ref> ' + text_at(t, k, '스틱맨 자세'))
    with open(outp, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    ok = sum(plausible(MT.decode(r['tokens'])) for r in rows)
    print('포즈', len(rows), '스타일', sum(r['layer'] == 'style' for r in rows), '참고', sum(r['layer'] == 'ref' for r in rows),
          '정답 자료 plausible 비율', round(ok / len(rows), 3))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])


# ---- 평가(2026-11-05): 출처(구간) 단위로 떼어 둔 평가 자료로 채점 ----
def pose_vec(ir):
    """디코딩한 포즈 → 골반 기준·몸통 단위 관절 벡터(22개 수)."""
    import numpy as np
    J = ir['actors'][0]['joints']; asp = ir.get('aspect', 0.5625); P = J['pelvis'][0]
    T = math.hypot(J['neck'][0][0] - P[0], (J['neck'][0][1] - P[1]) * asp) or 1
    return np.array([[(J[n][0][0] - P[0]) / T, (J[n][0][1] - P[1]) * asp / T] for n in MT.NAMES if n not in ('pelvis', 'head_b')]).ravel()


def split(rows, frac=0.1, seed=0):
    """출처(구간 id) 단위로 평가 자료를 뗀다 — 같은 구간의 이웃 장이 학습·평가에 함께 들어가 외우기로 맞히는 것을 막는다."""
    import random
    srcs = sorted({r['src'] for r in rows}); random.Random(seed).shuffle(srcs)
    style = [s for s in srcs if not s.startswith('u')]; ref = [s for s in srcs if s.startswith('u')]
    held = set(style[:max(1, round(len(style) * frac))] + ref[:max(1, round(len(ref) * frac))])
    return [r for r in rows if r['src'] not in held], [r for r in rows if r['src'] in held], sorted(held)


def score(gen_tokens, train_rows, ref_rows=None, copy_thr=0.15):
    """생성 포즈 채점: 디코딩 가능 비율, plausible 비율, 학습 포즈 베끼기 비율(가장 가까운 학습 포즈와 평균 관절 거리 < copy_thr 몸통).
    ref_rows(평가 정답)를 주면 같은 거리로 '정답도 학습 포즈와 얼마나 가까운지'를 함께 내서 기준선으로 쓴다."""
    import numpy as np
    TR = np.stack([pose_vec(MT.decode(r['tokens'])) for r in train_rows])
    def near(v): return float(np.min(np.linalg.norm((TR - v).reshape(len(TR), -1, 2), axis=2).mean(1)))
    dec = [MT.decode(t) for t in gen_tokens]
    ok = [d for d in dec if d is not None]
    out = dict(n=len(gen_tokens), decoded=len(ok) / max(len(dec), 1),
               plausible=sum(plausible(d) for d in ok) / max(len(dec), 1))
    if ok:
        ds = [near(pose_vec(d)) for d in ok]
        out.update(copy_rate=sum(x < copy_thr for x in ds) / len(ds), near_median=float(np.median(ds)))
    if ref_rows:
        rs = [near(pose_vec(MT.decode(r['tokens']))) for r in ref_rows]
        out.update(ref_copy_rate=sum(x < copy_thr for x in rs) / len(rs), ref_near_median=float(np.median(rs)))
    return out
