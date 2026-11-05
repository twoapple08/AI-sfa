"""단계 3 학습 시험 자료: 글 → 동작 토큰 쌍(jsonl). 72장(3초) 넘는 구간은 72장씩 자른다.

- 스타일 층(nian41·나카무라 18구간): GPT 태그 문장(data/stage2/tags_gpt_2026-11-05.json), 학습 제외 장(train_mask False)이 들어간 조각은 버린다.
- 기본기 층(수집 SFA): 문장 = GPT 태그가 있으면 그것, 없으면 '스틱맨 동작'. 앞에 <ref> 표시(조건 29 ② 참고용 — 생성 때는 넣지 않는다).
사용: python tools/stage3_pack.py <stage2_easy 작업 폴더> <출력 jsonl>
"""
import gzip, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNK = 72


def _slice(ir, s, e):
    sub = json.loads(json.dumps(ir)); a = sub['actors'][0]
    a['joints'] = {n: v[s:e] for n, v in a['joints'].items()}
    for k in ('thickness', 'hidden', 'smear', 'head_fill', 'facing', 'train_mask', 'smear_mark', 'inferred'):
        if a.get(k): a[k] = a[k][s:e]
    if a.get('drawings'):
        a['drawings'] = [[max(x, s) - s, min(y, e - 1) - s] for x, y in a['drawings'] if y >= s and x < e]
    sub['frames'] = e - s
    return sub


def chunks(ir):
    """학습 제외 장(train_mask False)으로 끊은 연속 부분 → 72장 이하 조각(8장 미만은 버림)."""
    N = ir['frames']; m = ir['actors'][0].get('train_mask') or [True] * N
    i = 0
    while i < N:
        if not m[i]: i += 1; continue
        j = i
        while j < N and m[j]: j += 1
        for s in range(i, j, CHUNK):
            e = min(j, s + CHUNK)
            if e - s >= 8: yield s, _slice(ir, s, e)
        i = j


def main(work, outp):
    tags = {t['segment']: t for t in json.load(open(f'{ROOT}/data/stage2/tags_gpt_2026-11-05.json', encoding='utf-8'))}
    utp = f'{ROOT}/data/stage2/tags_usersfa_gpt_2026-11-05.json'
    utags = {t['id']: t for t in json.load(open(utp, encoding='utf-8'))} if os.path.exists(utp) else {}
    rows = []
    for s in json.load(open(f'{work}/out/summary.json'))['segments']:
        ir = json.load(open(f"{work}/out/{s['name']}.json"))
        sent = tags.get(s['name'], {}).get('sentence', '스틱맨 액션')
        for st, sub in chunks(ir):
            rows.append(dict(layer='style', src=s['name'], start=st, prompt=sent, tokens=MT.encode(sub)))
    for i, l in enumerate(gzip.open(f'{ROOT}/data/stage2/user_sfa_ir_2026-11-05.jsonl.gz', 'rt', encoding='utf-8')):
        ir = json.loads(l); sid = f'u{i:03d}'; t = utags.get(sid, {})
        if t.get('quality') == '나쁨': continue
        for st, sub in chunks(ir):
            rows.append(dict(layer='ref', src=sid, start=st, prompt='<ref> ' + t.get('sentence', '스틱맨 동작'), tokens=MT.encode(sub)))
    with open(outp, 'w', encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('쌍', len(rows), '스타일', sum(r['layer'] == 'style' for r in rows), '참고', sum(r['layer'] == 'ref' for r in rows),
          '토큰 최대', max(len(r['tokens']) for r in rows))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
