#!/usr/bin/env python3
"""GPT 움직임 캡션(caption_en)의 장 번호를 학습 조각 기준으로 다시 매긴다 (2026-10-27).

캡션 번호는 시트 기준(k, 0부터)이다. 학습 조각이 시트 [w0, w1]이면: 구절(쉼표·세미콜론·마침표로 나눔)마다
숫자(장 번호·범위)를 조각과 겹치게 잘라 w0을 빼고, 숫자가 모두 조각 밖인 구절은 뺀다. 숫자 없는 구절(리듬·카메라 등)은 둔다.
'from/since/after N'(N<w0)은 조각 첫 장으로, 'through/until/to/by N'(N>w1)은 끝 장으로. 구절 안 조각 밖 숫자는 딸린
'and/then/while …' 부분 또는 'at/from… N' 말을 뺀다. 원칙: 조각에 없는 일을 적는 것(잘못된 라벨)이 덜 적는 것보다 해롭다 → 애매하면 뺀다.
한계: 숫자 없는 구절이 조각 밖 일을 말할 수 있다(예: 'Pullback'). 무작위 조각 1,385개 시험: 조각 밖 번호 0, 끊긴 문맥 3(공백 정리 전).
'one cut'/'N cuts'는 GPT cuts 중 조각 안 시작점으로 다시 센다. 장 번호가 아닌 숫자(예: 'holds five frames'의 낱말)는 건드리지 않는다.
사용(10-27 밤 2차부터): from caption_window import window_caption; window_caption(tag, cap, w0, w1). rewrite()는 비교용으로만 남김(결함은 아래 2차 설명).
"""
import re

NUM = re.compile(r'(?<![\w.])(\d+)(?:\s*[-–]\s*(\d+))?(?!\w|\.\d)')
WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']
# 컷 수는 구절 끝('…, two cuts.')만. 'at 0 cuts to …'(0번에서 장면 전환) 같은 동사 'cuts'는 건드리지 않는다
CUTS = re.compile(r'\b(?:(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:actual\s+|real\s+)?cuts?)(?=\s*(?:[.;,]|$))', re.I)


def _clause(c, w0, w1):
    """구절 하나. 반환: 새 구절 또는 None(조각 밖)."""
    hits = list(NUM.finditer(c))
    if not hits:
        return c
    out, pos, inside = [], 0, False
    for m in hits:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        after = c[m.end():m.end() + 8].lower()
        before = re.findall(r'([A-Za-z]+)\s*$', c[:m.start()])
        if m.group(2) is None and (re.match(r'\s*-?\s*frames?\b', after) or (before and before[0].lower() in ('hold', 'holds'))):
            # 길이('23 frames', 'Hold 95')는 장 번호가 아님 → 조각 길이 이하로만 줄임
            out.append(c[pos:m.start()])
            out.append(str(min(a, w1 - w0 + 1)))
            pos = m.end()
            inside = True
            continue
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


TGT = {'폭발': 'explosion', '연기': 'smoke', '먼지': 'dust', '파편': 'debris', '불': 'fire', '불티': 'embers', '섬광': 'flash',
       '빛번짐': 'glow bloom', '후광': 'halo', '빔': 'beam', '번개': 'lightning', '충격파': 'shockwave', '물보라': 'spray',
       '집중선': 'speed lines', '궤적선': 'motion trails', '잔상': 'afterimage', '임팩트프레임': 'impact frame'}
PH = {'응축': 'gathers', '발생': 'appears', '급팽창': 'bursts', '팽창': 'expands', '정점': 'peaks', '분열': 'splits',
      '흩어짐': 'scatters', '잔류': 'lingers', '소멸': 'fades'}
STYLE = set(('nkmr_fx twos ones threes on with and then mostly fixed camera pan pans one two three four five six cut cuts singles single '
             'hold holds held frames frame shaking slight slightly moving view zoom pullback lateral continuous mixed late early brief '
             'pairs transition at through from to the a of in by during').split())


def content_poor(cap):
    """리듬·카메라 낱말 말고 남은 내용 낱말이 4개 미만."""
    return len([w for w in re.findall(r'[A-Za-z]+', cap.lower()) if w not in STYLE]) < 4


def targets_sentence(shot, w0, w1):
    """GPT 구조 태그(targets·phases)에서 조각과 겹치는 대상의 단계를 영어 한 문장으로(내용이 다 빠진 조각 보충용)."""
    out = []
    for seg in shot['segments']:
        for t in seg['targets']:
            name = TGT.get(t['target'])
            if not name:
                continue
            best, ov = None, 0
            for p in t.get('phases', []):
                a, b = p['frames']
                o = min(b, w1) - max(a, w0) + 1
                if o > ov:
                    best, ov = p['phase'], o
            if best in PH and name not in [x[0] for x in out]:
                out.append((name, PH[best]))
    if not out:
        return ''
    s = ' and '.join(f'{n} {v}' for n, v in out)
    return s[0].upper() + s[1:] + f' at 0-{w1 - w0}.'


def normalize(cap):
    """GPT 검토본(10-27 밤) 캡션 39개에서 숫자 앞 띄어쓰기가 빠짐('at0-39', 'ones8-13') → 글자 바로 뒤 숫자 앞에 공백."""
    return re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', cap)


# ---- 2026-10-27 밤 2차: 구조 태그 기반 조각 캡션 (GPT 토론 2차 합의) ----
# rewrite()의 결함(GPT 지적, 코드로 확인): 'from N'(N<조각 시작)을 조각 첫 장으로 바꿔 '발생'처럼 읽힘, 'N frames'를 조각 길이로만 자름,
# 조각 밖 컷을 말한 구절의 낱말이 남음. window_caption()은
#  1) 조각이 컷 전체를 덮으면 GPT 캡션을 그대로 쓰고,
#  2) 아니면 GPT 구절 중 장 번호가 모두 조각 안인 구절만 번호를 옮겨 쓰고(구절 일부만 겹치면 통째로 뺌),
#     구조 태그(targets·phases·rhythm·camera·cuts)와 조각의 교집합으로 문장을 새로 만든다:
#     조각 전부터 있던 것 'already …', 조각 뒤에도 태그상 이어지는 것 'continues past the end',
#     컷 마지막 장까지 이어지면 'through the last visible frame', 홀드 길이는 교집합 길이로 다시 센다.
# 한계: '기타:' 대상(1,043개 중 약 40)과 자유 기술 change는 옮기지 않는다. 홀드 어휘(drifts·slight shake·background motion·fades)는
# 태그에 구조로 없어 조각이 컷 일부일 때는 쓰이지 않는다.

PH_NOW = {'응축': 'gathers', '발생': 'appears', '급팽창': 'bursts out', '팽창': 'expands', '정점': 'peaks', '분열': 'splits apart',
          '흩어짐': 'scatters', '잔류': 'lingers', '소멸': 'fades out'}
PH_ALREADY = {'응축': 'already gathering', '발생': 'already present', '급팽창': 'already bursting', '팽창': 'already expanding',
              '정점': 'already at its peak', '분열': 'already splitting', '흩어짐': 'already scattering', '잔류': 'already lingering',
              '소멸': 'already fading'}
SHAPE = {'띠·줄기': 'streaky bands', '뾰족한 끝': 'tapered tips', '둥근 덩어리': 'round billows', '방사형': 'a radial spread',
         '단색면': 'flat color fills', '점무리': 'particle clusters', '윤곽을 두른 빛': 'outlined glow', '고리': 'ring shapes',
         '각진 돌출': 'angular spikes', '구멍': 'hollow gaps', '각진 판·덩어리': 'angular chunks', '중첩 윤곽': 'layered outlines',
         '거친 흑백 획': 'rough black-and-white strokes', '찢어진 심': 'torn cores'}
CTOK = {'흰': 'white', '흰색': 'white', '노랑': 'yellow', '노란': 'yellow', '주황': 'orange', '검정': 'black', '검은': 'black',
        '회색': 'gray', '청록': 'cyan', '청록색': 'cyan', '빨강': 'red', '빨간': 'red', '붉은': 'red', '분홍': 'pink', '보라': 'purple',
        '보라색': 'purple', '파랑': 'blue', '파란': 'blue', '갈색': 'brown', '자홍': 'magenta', '자홍색': 'magenta', '회백색': 'off-white',
        '청색': 'blue', '회갈색': 'gray-brown', '하늘색': 'sky-blue', '초록': 'green', '녹색': 'green', '연두': 'lime', '연두색': 'lime',
        '회보라': 'gray-violet', '청회색': 'blue-gray', '회청색': 'blue-gray', '황갈색': 'tan', '황토색': 'ochre', '청백색': 'blue-white',
        '연보라': 'lavender', '흰노란': 'pale yellow', '연분홍': 'light pink', '검붉은': 'dark red', '검붉은색': 'dark red',
        '녹회색': 'green-gray', '회녹색': 'green-gray', '연회색': 'light gray', '황록색': 'yellow-green', '남회색': 'navy-gray',
        '남색': 'navy', '흰청록': 'white-cyan', '연노랑': 'light yellow', '연주황': 'light orange', '갈주황': 'brown-orange',
        '옅은': 'pale', '짙은': 'dark', '밝은': 'bright', '반투명': 'translucent', '흐린': 'faint', '선명한': 'vivid', '어두운': 'dark'}
CPART = {'심': 'core', '테': 'rim', '음영': 'shading', '번짐': 'haze', '면': 'fill', '끝': 'tips', '윤곽': 'outline', '외곽': 'outer edge'}
STEMS = {'flash': ['flash', 'glare', 'glint'], 'lightning': ['lightning', 'electric', 'bolt', 'branch'], 'embers': ['ember', 'spark', 'glint'],
         'glow bloom': ['glow', 'bloom'], 'halo': ['halo', 'aura', 'glow'], 'beam': ['beam', 'ray'], 'explosion': ['explosion', 'blast', 'burst'],
         'smoke': ['smoke', 'haze'], 'dust': ['dust', 'haze'], 'debris': ['debris', 'fragment', 'chunk', 'rock', 'shard'],
         'fire': ['fire', 'flame'], 'shockwave': ['shockwave', 'ring', 'wave'], 'spray': ['spray', 'splash'],
         'speed lines': ['speed line', 'radial', 'lines'], 'motion trails': ['trail', 'streak', 'arc'], 'afterimage': ['afterimage'],
         'impact frame': ['impact', 'monochrome', 'insert', 'black-white', 'white-black', 'hatching']}
CAM = {'팬': 'panning camera', '고정': 'fixed camera', '줌아웃': 'camera pulls back', '줌인': 'camera pushes in',
       '회전': 'rotating camera', '흔들림': 'shaking camera'}
RH = {'1s': 'ones', '2s': 'twos', '3s': 'threes'}


def _color(c):
    """'흰 심' → ('white', 'core'), '옅은 노랑' → ('pale yellow', None). 모르는 낱말이 있으면 None."""
    if c.startswith('기타'):
        return None
    ws, part = c.split(), None
    if ws and ws[-1] in CPART:
        part = CPART[ws.pop()]
    if not ws or any(w not in CTOK for w in ws):
        return None
    return ' '.join(CTOK[w] for w in ws), part


def _name(t):
    n = t['target']
    return TGT.get(n) or (OTHER.get(n[3:]) if n.startswith('기타:') else None)


def _a(w):
    return ('an ' if w[:1] in 'aeiou' else 'a ') + w


def _describe(t):
    name = _name(t)
    if not name:
        return None
    if t['target'].startswith('기타:') and any(w in name for w in ('white', 'black', 'red', 'gray', 'yellow', 'cyan', 'blue', 'pink', 'orange')):
        rs = []  # 이름에 색이 있으면 색 목록은 겹치므로 생략
    else:
        rs = [r for r in (_color(c) for c in t.get('color', [])) if r]
    base = list(dict.fromkeys(c for c, p in rs if not p))
    parts = [(c, p) for c, p in rs if p][:2 if len(base) < 3 else 1]
    if len(base) >= 3:  # 바탕색 셋 이상 = 장마다 색이 바뀌거나 여러 개체 → 한 색으로 묶지 않는다
        d = f"{name} in shifting colors ({', '.join(base[:3])})"
    else:
        d = (' and '.join(base) + ' ' if base else '') + name
    extra = [_a(f'{c} {p}') for c, p in parts]
    sh = [SHAPE[x] for x in t.get('shape', []) if x in SHAPE][:1]
    if extra or sh:
        d += ' with ' + ' and '.join(extra + sh)
    return d


def _frame_refs(clause):
    """구절의 장 번호(범위) 목록과 길이 숫자 목록. 길이: 'N frames', 'hold(s) N'."""
    refs, lens = [], []
    for m in NUM.finditer(clause):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        after = clause[m.end():m.end() + 8].lower()
        before = re.findall(r'([A-Za-z]+)\s*$', clause[:m.start()])
        if m.group(2) is None and (re.match(r'\s*-?\s*frames?\b', after) or (before and before[0].lower() in ('hold', 'holds'))):
            lens.append((m, a))
        else:
            refs.append((m, a, b))
    return refs, lens


def _renumber(text, refs, w0):
    res, pos = [], 0
    for m, a, b in refs:
        res.append(text[pos:m.start()])
        res.append(f'{a - w0}' if a == b else f'{a - w0}-{b - w0}')
        pos = m.end()
    res.append(text[pos:])
    return ''.join(res)


def _inside_clauses(cap, w0, w1):
    """GPT 캡션에서 장 번호가 모두 조각 안인 문장(마침표·세미콜론 단위)만 번호를 옮겨 돌려준다.
    문장 일부만 빼면 목록의 명사가 떨어지므로('Green beams at 3-4, … pink at 22-24 …' → 'Pink at 0-2') 문장 통째로 판단한다."""
    body = cap[len('nkmr_fx,'):] if cap.startswith('nkmr_fx,') else cap
    out = []
    for s in re.split(r'(?<=[.;])\s+', body.strip()):
        s = s.strip().rstrip('.;')
        refs, lens = _frame_refs(s)
        if not refs or not all(w0 <= a and b <= w1 for _, a, b in refs) or not all(n <= w1 - w0 + 1 for _, n in lens):
            continue
        t = _renumber(s, refs, w0)
        t = ('Frame ' + t) if t[0].isdigit() else t[0].upper() + t[1:]
        out.append((t + '.', [(a, b) for _, a, b in refs]))
    return out


def _covered(name, colors, frames, clauses):
    """대상의 조각 안 장(frames)을 이름·색 낱말이 같은 GPT 문장들의 장 번호가 모두 덮으면 True(구조 문장 생략)."""
    stems = STEMS.get(name, [name])
    got = set()
    for text, refs in clauses:
        low = text.lower()
        if any(s in low for s in stems) or any(c in low for c in colors):
            for a, b in refs:
                got.update(range(a, b + 1))
    return bool(frames) and frames <= got


def _rhythm(g, w0, w1):
    runs = []
    for seg in g['segments']:
        for r in seg['rhythm']:
            a, b, code = r[0], r[1], r[2]
            lo, hi = max(a, w0), min(b, w1)
            if lo <= hi:
                runs.append((lo, hi, a, b, code))
    holds, hg, cnt = [], {}, {}
    for lo, hi, a, b, code in runs:
        if code.startswith('홀드'):
            n = hi - lo + 1
            rg = f'{lo - w0}' if lo == hi else f'{lo - w0}-{hi - w0}'
            if a < w0:
                holds.append(f'{n}-frame hold at {rg} already in progress')
            elif b > w1:
                holds.append(f'{n}-frame hold at {rg} continuing past the end')
            else:
                hg.setdefault(n, []).append(rg)
        elif code in RH:
            cnt[RH[code]] = cnt.get(RH[code], 0) + hi - lo + 1
    holds = [f"{n}-frame hold{'s' if len(v) > 1 else ''} at {_join(v)}" for n, v in hg.items()] + holds
    tot = sum(cnt.values())
    order = sorted(cnt, key=lambda k: -cnt[k])
    if not order:
        base = ''
    elif cnt[order[0]] >= 0.8 * tot:
        base = f'on {order[0]}'
    else:
        base = 'mixed ' + ' and '.join(order)
    return ', '.join(([base] if base else []) + holds)


PLURAL = {'embers', 'motion trails', 'speed lines', 'glowing cracks', 'particles', 'specks', 'thin lines', 'dark red glowing lines'}
# '기타:' 대상(10-27 밤 태그 43종 전부) — 색이 이름에 들어 있으면 이름 그대로 쓴다
OTHER = {'발광 균열': 'glowing cracks', '검붉은 발광 선': 'dark red glowing lines', '흰 분출': 'white gush', '검은 번짐': 'black smear',
         '노란 발광 띠': 'yellow glowing band', '지면의 발광 선': 'glowing line on the ground', '가는 붉은 선': 'thin red line',
         '회색 안개': 'gray mist', '하단 회색 구름': 'low gray cloud', '검붉은 번짐': 'dark red smear', '검은 입자': 'black particles',
         '검은 가는 선': 'thin black line', '청록 수직 발광 면': 'vertical cyan glowing plane', '노란 기하학 발광': 'yellow geometric glow',
         '푸른 분출과 입자': 'blue gush with particles', '흰 발광 입자': 'white glowing particles', '히트 문자': 'hit lettering',
         '얼음 분출': 'ice burst', '붉은 발광 기류': 'red glowing current', '청록 가는 선': 'thin cyan line', '회색 띠형 궤적': 'gray band trail',
         '흰 기둥형 분출': 'white pillar gush', '주황 꼬리': 'orange tail', '회색 이동막': 'moving gray veil', '청백 파형': 'blue-white wave',
         '노란 뱀형 에너지': 'yellow serpentine energy', '붉은 분출': 'red gush', '확장 균열': 'spreading cracks', '흑백 가로 띠': 'black-and-white horizontal band',
         '흰 삼각형 파동': 'white triangular wave', '분홍 발광 장': 'pink glowing field', '흰 나선 띠': 'white spiral band', '주황 가지광': 'orange branching light',
         '주황 발광 면': 'orange glowing plane', '노란 고리형 발광': 'yellow ring glow', '흰 발광 줄기': 'white glowing streak',
         '청록 발광 입방체': 'cyan glowing cube', '흰 점 깜빡임': 'blinking white dots', '발광 구체': 'glowing orb', '정체 불명 흰 곡선': 'unidentified white curve',
         '검은 점상 비산물': 'black speck spatter', '발광 고리': 'glowing ring', '미세 비산물': 'fine spatter'}
PLURAL |= {'black particles', 'white glowing particles', 'spreading cracks', 'blinking white dots'}
VERB_PL = {'appears': 'appear', 'expands': 'expand', 'bursts out': 'burst out', 'peaks': 'peak', 'splits apart': 'split apart',
           'scatters': 'scatter', 'lingers': 'linger', 'fades out': 'fade out', 'gathers': 'gather'}


def _join(xs):
    return ', '.join(xs[:-1]) + ' and ' + xs[-1] if len(xs) > 1 else xs[0]


def _ranges(rs):
    """[(lo, hi)] 조각 기준 → 'at 1, 3 and 5-7'(맞닿은 범위는 합침) / 다섯 개 이상이면 'repeatedly between 1 and 15'."""
    m = []
    for a, b in sorted(rs):
        if m and a <= m[-1][1] + 1:
            m[-1] = (m[-1][0], max(b, m[-1][1]))
        else:
            m.append((a, b))
    rs = m
    txt = [f'{a}' if a == b else f'{a}-{b}' for a, b in rs]
    if len(txt) >= 5:
        return f'repeatedly between {rs[0][0]} and {rs[-1][1]}'
    return 'at ' + _join(txt)


def window_caption(g, cap, w0, w1):
    """학습 조각 [w0, w1](시트 장 번호) 캡션. g = GPT 태그 한 줄(dict), cap = normalize한 caption_en."""
    first, last = g['segments'][0]['frames'][0], g['segments'][-1]['frames'][1]
    cuts = [c for c in g['cuts'] if w0 < c <= w1]
    refs, lens = _frame_refs(cap)
    if (w0 - first) + (last - w1) <= 3 and all(w0 <= a and b <= w1 for _, a, b in refs) and all(n <= w1 - w0 + 1 for _, n in lens):
        n = 1 + len(cuts)  # 잘린 1–3장에 컷이 있었을 수 있으므로 컷 수만 다시 센다
        rep = f"{WORDS[n] if n < len(WORDS) else n} cut{'s' if n > 1 else ''}"
        # 조각이 컷 거의 전체(4N+1 맞춤으로 끝 1–3장만 빠짐)이고 캡션 번호가 모두 안 → GPT 캡션 그대로
        return CUTS.sub(lambda m: rep[0].upper() + rep[1:] if m.group(0)[0].isupper() else rep, _renumber(cap, refs, w0))
    clauses = _inside_clauses(cap, w0, w1)
    sents = [t for t, _ in clauses]
    tg = {}  # 같은 묘사의 대상은 구간(segment)을 넘어 합친다
    for seg in g['segments']:
        for t in seg['targets']:
            d = _describe(t)
            if not d:
                continue
            e = tg.setdefault(d, {'name': _name(t), 'ph': [], 'cols': [c[0] for c in (_color(x) for x in t.get('color', [])) if c]})
            e['ph'] += [(p['frames'][0], p['frames'][1], p['phase']) for p in t.get('phases', []) if max(p['frames'][0], w0) <= min(p['frames'][1], w1)]
    for d, e in tg.items():
        ph = sorted(e['ph'])
        if not ph:
            continue
        a0, b1 = ph[0][0], max(b for _, b, _ in ph)
        inside = {k for x, y, _ in ph for k in range(max(x, w0), min(y, w1) + 1)}
        if a0 >= w0 and b1 <= w1 and _covered(e['name'], e['cols'], inside, clauses):
            continue  # 조각 안에서 시작·끝나고 GPT 문장이 이미 말함
        pl = e['name'] in PLURAL
        groups = []  # (동사, [(lo, hi)]) — 이어지는 같은 동사는 묶는다
        for i, (a, b, phase) in enumerate(ph):
            if i == 0 and a < w0:
                v = PH_ALREADY.get(phase)
                v = v and (('are ' if pl else 'is ') + v)
            else:
                v = PH_NOW.get(phase)
                v = v and (VERB_PL[v] if pl else v)
            if not v:
                continue
            r = (max(a, w0) - w0, min(b, w1) - w0)
            if groups and groups[-1][0] == v and not v.startswith(('is ', 'are ')):
                groups[-1][1].append(r)
            else:
                groups.append((v, [r]))
        if not groups:
            continue
        bits = [f'{v} {_ranges(rs)}' for v, rs in groups]
        if b1 > w1:
            bits[-1] += ', continuing past the end'
        elif b1 == w1 == last and ph[-1][2] != '소멸':
            bits[-1] += ', through the last visible frame'
        txt = d + ' ' + ('; '.join(bits) if any(',' in b for b in bits) else _join(bits))
        sents.append(txt[0].upper() + txt[1:] + '.')
    cams = []
    for seg in g['segments']:
        a, b = seg['frames']
        if max(a, w0) <= min(b, w1):
            for c in seg.get('camera', []):
                if c in CAM and CAM[c] not in cams:
                    cams.append(CAM[c])
    n = 1 + len(cuts)
    word = WORDS[n] if n < len(WORDS) else str(n)
    cut = f"{word} cut{'s' if n > 1 else ''}"
    if cuts:
        cut += ', new shot' + ('s' if len(cuts) > 1 else '') + ' at ' + _join([str(c - w0) for c in cuts])
    rh = _rhythm(g, w0, w1)
    camtxt = (', then '.join(cams) if len(cams) <= 2 else 'mixed camera moves (' + ', '.join(c.replace(' camera', '').replace('camera ', '') for c in cams) + ')') if cams else 'camera unclear'
    tail = (rh + '; ' if rh else '') + camtxt + ', ' + cut + '.'
    sents.append(tail[0].upper() + tail[1:])
    return 'nkmr_fx, ' + ' '.join(sents)
