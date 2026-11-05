"""단계 5(글·길이·앞 동작 → 움직임) 학습 쌍: 처음부터 만들기 + 이어 만들기(앞 키프레임 CTX개를 주고 다음 구간).
(2026-11-05: 단계 3 시험이 3초 요청에 8–12장으로 끝냄, 자료 구간 중앙 14장 → 짧은 자료로 긴 동작을 만들려면 이어 만들기.
 확정 조건 '앞 장면 파일에서 이어지는 시스템'과 같은 틀.)

쌍 형식: {layer, src, kind: 'start'|'cont', frames(목표 장 수), prompt(목표 구간을 덮는 GPT 동작 문장), context(앞 키프레임 토큰, 이어 만들기만), tokens(목표)}
- 목표 구간 = 학습 제외 장으로 끊은 깨끗한 연속 부분 안에서 TARGET장 이하. 이어 만들기는 STEP장마다 나눈 경계에서.
- 글 = 목표 장 범위와 겹치는 동작(verb: detail)을 시간 순서로. 없으면 구간 문장.
사용: python tools/stage5_pack.py <stage2_easy 작업 폴더> <출력 jsonl>
"""
import gzip, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT  # noqa: E402
from stage3_pack import _slice  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET, STEP, CTX = 32, 8, 3   # 8장 간격으로 겹쳐 이어 만들기 쌍을 늘린다(24장 간격이면 이어 만들기 58쌍, 8장이면 404쌍 — 구간 중앙 14장)
K = 23   # 키프레임 하나 토큰 수


def runs(ir):
    N = ir['frames']; m = ir['actors'][0].get('train_mask') or [True] * N
    i = 0
    while i < N:
        if not m[i]: i += 1; continue
        j = i
        while j < N and m[j]: j += 1
        if j - i >= 8: yield i, j
        i = j


def text_for(tag, a, b, default):
    acts = sorted([x for x in (tag or {}).get('actions', []) if x['to'] >= a and x['from'] <= b], key=lambda x: x['from'])
    return ' → '.join(f"{x['verb']}: {x['detail']}" for x in acts) if acts else default


def pairs(ir, tag, default, layer, src):
    out = []
    for i, j in runs(ir):
        for s in range(i, j, STEP):
            e = min(j, s + TARGET)
            if e - s < 8: continue
            tgt = MT.encode(_slice(ir, s, e))
            row = dict(layer=layer, src=src, start=s, frames=e - s, prompt=text_for(tag, s, e - 1, default))
            if s == i:
                out.append(dict(row, kind='start', context=[], tokens=tgt))
            else:   # 앞 키프레임 CTX개: 앞 구간을 같은 방식으로 인코딩해 마지막 CTX개 묶음
                prev = MT.encode(_slice(ir, max(i, s - STEP), s))[1:-1]
                ctx = prev[-CTX * K:] if len(prev) >= K else prev
                if len(ctx) % K: continue
                out.append(dict(row, kind='cont', context=ctx, tokens=tgt))
    return out


def main(work, outp):
    tags = {t['segment']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_gpt_2026-11-05.json', encoding='utf-8'))}
    utags = {t['id']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_usersfa_gpt_2026-11-05.json', encoding='utf-8'))}
    rows = []
    for s in json.load(open(f'{work}/out/summary.json'))['segments']:
        ir = json.load(open(f"{work}/out/{s['name']}.json")); t = tags.get(s['name'])
        rows += pairs(ir, t, (t or {}).get('sentence', '스틱맨 액션'), 'style', s['name'])
    for i, l in enumerate(gzip.open(f'{ROOT}/data/stage2/user_sfa_ir_2026-11-05.jsonl.gz', 'rt', encoding='utf-8')):
        sid = f'u{i:03d}'; t = utags.get(sid)
        if t and t.get('quality') == '나쁨': continue
        rows += [dict(r, prompt='<ref> ' + r['prompt']) for r in pairs(json.loads(l), t, (t or {}).get('sentence', '스틱맨 동작'), 'ref', sid)]
    with open(outp, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    import collections
    c = collections.Counter((r['layer'], r['kind']) for r in rows)
    print('쌍', len(rows), dict(c), '목표 장 중앙', sorted(r['frames'] for r in rows)[len(rows) // 2])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
