#!/usr/bin/env python3
"""학습 조각 캡션의 '사실표' 만들기와 조각 캡션 검사 (2026-10-27 밤, GPT 토론 3차 제안).

조각 범위는 wan_lora_dataset.py와 같은 계산(앞뒤 1–2장 옆 컷 구간 제거 → 33장 이하 4N+1 조각)을 태그만으로 재현한다.
  sheet: 경우 B 조각(window_caption이 GPT 캡션을 그대로 쓰지 않는 조각)마다 GPT가 캡션을 쓸 사실을 JSONL로 낸다.
         장 번호는 모두 조각 기준(0부터). 태그 값은 GPT 원문 그대로(한국어), 조각과의 교집합·앞뒤 연장 여부만 Claude가 계산.
  check: GPT가 쓴 조각 캡션 JSONL({"shot","w0","w1","caption"})을 사실표와 대조해 기계 검사한다.
사용: python tools/window_factsheet.py sheet TAGS.jsonl... -o facts.jsonl
      python tools/window_factsheet.py check TAGS.jsonl... --captions gpt_window_captions.jsonl
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from caption_window import WORDS, _frame_refs, _inside_clauses, normalize, whole_ok, window_caption  # noqa: E402


def windows(g, chunk=33, min_len=17):
    segs = [s['frames'] for s in g['segments']]
    while len(segs) > 1 and segs[0][1] - segs[0][0] < 2:
        segs = segs[1:]
    while len(segs) > 1 and segs[-1][1] - segs[-1][0] < 2:
        segs = segs[:-1]
    k0, k1 = segs[0][0], segs[-1][1]
    L = k1 - k0 + 1
    if L < min_len:
        return []
    m = -(-L // chunk)
    st = [round(i * L / m) for i in range(m)] + [L]
    out = []
    for i in range(m):
        ln = (st[i + 1] - st[i] - 1) // 4 * 4 + 1
        if ln >= min_len:
            out.append((k0 + st[i], k0 + st[i] + ln - 1))
    return out


def facts(g, w0, w1):
    rel = lambda a, b: [max(a, w0) - w0, min(b, w1) - w0]  # noqa: E731
    segs, events = [], []
    for si, s in enumerate(g['segments']):
        a, b = s['frames']
        if max(a, w0) > min(b, w1):
            continue
        segs.append({'seg': si, 'frames': rel(a, b), 'new_shot': w0 < a <= w1, 'camera': s.get('camera', []),
                     'rhythm': [{'frames': rel(r[0], r[1]), 'code': r[2], 'starts_before': r[0] < w0, 'continues_after': r[1] > w1}
                                for r in s['rhythm'] if max(r[0], w0) <= min(r[1], w1)]})
        for t in s['targets']:
            ph = [p for p in t.get('phases', []) if max(p['frames'][0], w0) <= min(p['frames'][1], w1)]
            if not ph:
                continue
            events.append({'seg': si, 'target': t['target'], 'color': t.get('color', []), 'shape': t.get('shape', []),
                           'change': t.get('change', []), 'visibility': t.get('visibility'),
                           'phases': [{'phase': p['phase'], 'frames': rel(*p['frames']), 'starts_before': p['frames'][0] < w0,
                                       'continues_after': p['frames'][1] > w1} for p in ph],
                           'target_outside_window': (out := min(p['frames'][0] for p in t['phases']) < w0 or max(p['frames'][1] for p in t['phases']) > w1),
                           # 색표는 대상 전체 속성 → 조각이 대상 일부만 보고 색이 셋 이상이거나 '색 단계 변화'면 시트에서 이 조각의 실제 색을 확인
                           'color_scope_check': out and (len({c for c in t.get('color', []) if not c.endswith(('심', '테', '음영'))}) >= 3
                                                         or '색 단계 변화' in t.get('change', []))})
    last = g['segments'][-1]['frames'][1]
    return {'segments': segs, 'events': events, 'window_ends_at_shot_end': w1 == last,
            'cuts_in_window': [c - w0 for c in g['cuts'] if w0 < c <= w1]}


def load(paths):
    for p in paths:
        for line in open(p, encoding='utf-8'):
            if line.strip():
                yield json.loads(line)


def sheet(a):
    n = 0
    with open(a.o, 'w', encoding='utf-8') as fh:
        for g in load(a.tags):
            cap = normalize(g['caption_en'])
            for w0, w1 in windows(g):
                if whole_ok(g, cap, w0, w1):
                    continue
                f = {'shot': g['shot'], 'w0': w0, 'w1': w1, 'length': w1 - w0 + 1,
                     'sheet_frames': f'{w0}-{w1}', 'original_caption': g['caption_en'],
                     'original_sentences_inside': [t for t, _ in _inside_clauses(cap, w0, w1)], **facts(g, w0, w1),
                     'claude_draft': window_caption(g, cap, w0, w1)}
                fh.write(json.dumps(f, ensure_ascii=False) + '\n')
                n += 1
    print(f'사실표 {n}조각 → {a.o}')


META = re.compile(r'\b(unresolved|uncertain|undetermined|establish|recorded|tag|tags|window caption)\b', re.I)


def check(a):
    tags = {g['shot']: g for g in load(a.tags)}
    caps = list(load([a.captions]))
    bad = 0
    for c in caps:
        g, w0, w1, cap = tags[c['shot']], c['w0'], c['w1'], c['caption']
        ln, f, errs = w1 - w0 + 1, facts(tags[c['shot']], w0, w1), []
        if (w0, w1) not in windows(g):
            errs.append('조각 범위가 학습 조각과 다름')
        if not cap.startswith('nkmr_fx, '):
            errs.append('nkmr_fx 접두사 없음')
        if len(cap.split()) > 60:
            errs.append(f'{len(cap.split())}단어')
        if re.search(r'[A-Za-z]\d', cap) or re.search(r'[가-힣]', cap) or META.search(cap):
            errs.append('붙은 숫자/한글/판정 낱말')
        refs, _ = _frame_refs(cap)
        out = [(x, y) for _, x, y in refs if not (0 <= x <= y <= ln - 1)]
        if out:
            errs.append(f'조각 밖 번호 {out}')
        nums = {n for _, x, y in refs for n in (x, y)}
        for s in f['cuts_in_window']:
            if s not in nums:
                errs.append(f'새 컷 {s} 언급 없음')
        n = 1 + len(f['cuts_in_window'])
        if not re.search(rf"\b({WORDS[n] if n < len(WORDS) else n}|{n})\s+cuts?\b", cap, re.I):
            errs.append(f'컷 수 {n} 없음')
        miss = [e['target'] for e in f['events'] if not e['phases'][0]['starts_before'] and e['phases'][0]['frames'][0] not in nums]
        if miss:
            errs.append(f'시작 장 번호가 안 보이는 대상(확인) {miss}')
        if errs:
            bad += 1
            print(c['shot'], f'{w0}-{w1}', '; '.join(errs))
    print(f'검사 {len(caps)}조각, 문제 {bad}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['sheet', 'check'])
    ap.add_argument('tags', nargs='+')
    ap.add_argument('-o', default='window_facts.jsonl')
    ap.add_argument('--captions')
    a = ap.parse_args()
    (sheet if a.mode == 'sheet' else check)(a)


if __name__ == '__main__':
    main()
