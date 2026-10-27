#!/usr/bin/env python3
"""GPT 움직임 캡션(caption_en)의 장 번호를 학습 조각 기준으로 다시 매긴다 (2026-10-27).

캡션 번호는 시트 기준(k, 0부터)이다. 학습 조각이 시트 [w0, w1]이면: 구절(쉼표·세미콜론·마침표로 나눔)마다
숫자(장 번호·범위)를 조각과 겹치게 잘라 w0을 빼고, 숫자가 모두 조각 밖인 구절은 뺀다. 숫자 없는 구절(리듬·카메라 등)은 둔다.
'from/since/after N'(N<w0)은 조각 첫 장으로, 'through/until/to/by N'(N>w1)은 끝 장으로. 구절 안 조각 밖 숫자는 딸린
'and/then/while …' 부분 또는 'at/from… N' 말을 뺀다. 원칙: 조각에 없는 일을 적는 것(잘못된 라벨)이 덜 적는 것보다 해롭다 → 애매하면 뺀다.
한계: 숫자 없는 구절이 조각 밖 일을 말할 수 있다(예: 'Pullback'). 무작위 조각 1,385개 시험: 조각 밖 번호 0, 끊긴 문맥 3(공백 정리 전).
'one cut'/'N cuts'는 GPT cuts 중 조각 안 시작점으로 다시 센다. 장 번호가 아닌 숫자(예: 'holds five frames'의 낱말)는 건드리지 않는다.
사용: from caption_window import rewrite; rewrite(cap, w0, w1, cuts)
"""
import re

NUM = re.compile(r'(?<![\w.])(\d+)(?:\s*[-–]\s*(\d+))?(?!\w|\.\d)')
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
CUTS = re.compile(r'\b(?:(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:actual\s+|real\s+)?cuts?)\b', re.I)


def _clause(c, w0, w1):
    """구절 하나. 반환: 새 구절 또는 None(조각 밖)."""
    hits = list(NUM.finditer(c))
    if not hits:
        return c
    out, pos, inside = [], 0, False
    for m in hits:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        prev = re.findall(r'([A-Za-z]+)\s*$', c[:m.start()])
        prev = prev[0].lower() if prev else ''
        if prev in ('from', 'since', 'after') and a < w0 <= b or (prev in ('from', 'since', 'after') and a < w0 and m.group(2) is None):
            a = b = w0  # 조각 앞에서 시작해 이어지는 것 → 조각 첫 장부터
        if prev in ('through', 'until', 'till', 'to', 'by') and b > w1 and m.group(2) is None:
            a = b = w1  # 조각 뒤까지 이어지는 것 → 조각 끝 장까지
        lo, hi = max(a, w0), min(b, w1)
        if lo > hi:  # 이 숫자는 조각 밖 → 그대로 두되 표시
            rep = None
        else:
            inside = True
            rep = f'{lo - w0}' if lo == hi else f'{lo - w0}-{hi - w0}'
        out.append(c[pos:m.start()])
        out.append(rep if rep is not None else '\0')
        pos = m.end()
    out.append(c[pos:])
    if not inside:
        return None
    s = ''.join(out)
    # 조각 밖 숫자가 낀 나열('at 0-1, 14 and 17')은 그 숫자와 붙은 'and'/','만 정리
    s = re.sub(r'(,\s*|\s+and\s+)\0', '', s)
    s = re.sub(r'\0(,\s*|\s+and\s+)', '', s)
    s = re.sub(r'\s+(?:and|then|while)\s+[^\d\0,;]*?\0[^,;.]*', '', s)  # 'and rising again from 35' 같은 딸린 부분 통째로
    s = re.sub(r'\s*\b(?:at|from|through|by|until|till|to|after|since|in|during)\s+\0', '', s)
    s = s.replace('\0', '')
    return re.sub(r'\s{2,}', ' ', s)


LIST_ONLY = re.compile(r'^(?:[\d\s,–-]|and)+[.;]?$')


def rewrite(cap, w0, w1, cuts):
    head = ''
    if cap.startswith('nkmr_fx,'):
        head, cap = 'nkmr_fx,', cap[len('nkmr_fx,'):]
    sents = re.split(r'(?<=[.;])\s+', cap.strip())
    keep = []
    for s in sents:
        raw = re.split(r',\s+', s)
        parts = []
        for p in raw:  # 숫자만 있는 조각('14 and 17')은 앞 구절의 나열 → 붙인다
            if parts and LIST_ONLY.match(p.strip()):
                parts[-1] += ', ' + p
            else:
                parts.append(p)
        new = []
        for i, p in enumerate(parts):
            r = _clause(p, w0, w1)
            if r is not None and r.strip(' .;,'):
                new.append(r.strip())
        if not new:
            continue
        t = ', '.join(x.rstrip(',') for x in new)
        t = re.sub(r'^(?:and|then|with)\s+', '', t, flags=re.I)  # 앞 구절이 빠져 접속사로 시작하면 떼기
        if s.rstrip().endswith(('.', ';')) and not t.endswith(('.', ';')):
            t += s.rstrip()[-1]
        if keep and keep[-1].endswith('.') or not keep:
            t = t[0].upper() + t[1:]
        keep.append(t)
    n = 1 + sum(1 for c in cuts if w0 < c <= w1)
    word = WORDS[n] if n < len(WORDS) else str(n)
    body = ' '.join(keep)
    rep = f"{word} cut{'s' if n > 1 else ''}"
    body = CUTS.sub(lambda m: rep[0].upper() + rep[1:] if m.group(0)[0].isupper() else rep, body)
    body = re.sub(r'\s+([,;.])', r'\1', body)
    return (head + ' ' + body).strip() if head else body
