"""요소 트리 집계: 자동 탐지(auto_detect.py) 결과를 요소 트리에 붙여 요소별 나온 시간·시기별 비율·동반확률을 낸다.

사용: python tools/element_aggregate.py <탐지 폴더> <출력 csv>
입력(저장소): element_tree_2026-10-20.csv, source_format_2026-10-20.csv(연도),
  judge_lists/auto_detect_list_2026-10-20.csv(애니메이터), auto_detect/calibration_*_2026-10-21.csv(신뢰도)
계산(추론, 사람 확인 아님):
- 프레임(0.5초)별 요소 확률 = 요소 태그 확률의 최대값('all'은 0.05 미만을 버렸으므로 0으로 본다).
- 기대 나온 시간(초) = Σ 확률 × 0.5. 태그 확률이 화면 비중(주인공/배경)의 대리값을 겸한다(위치·크기는 재지 않음).
- 영상 비율 = 기대 나온 시간 / 영상 길이. 시기·애니메이터 비율 = 영상 비율의 평균(영상마다 같은 비중).
- 나카무라 점수 = √(구작 비율 × 신작 비율). 한쪽이 바닥값보다 작으면 바닥값(그 시기 영상 1개에서 0.5초 1프레임분)을 넣고
  나온 영상 수(기대 1초 이상)가 0인 시기가 있으면 '구작 전용' / '신작 전용'으로 표시한다.
- 하위 포함: 1단계 이상 요소는 자기 태그와 자손 태그를 합친 값도 낸다(부모를 적으면 자식이 따라오는 구조).
- 동반확률 = Σ min(부모 확률, 자식 확률) / Σ 부모 확률(나카무라 프레임 전체). 부모가 거의 안 나오면 비워 둔다.
- 접기 후보: 우리 자료 전체에서 나온 영상 0개이고 Danbooru 태그 수 최대값이 FOLD_COUNT 미만.
- 태그가 없고 CLIP 칸만 있는 요소는 'CLIP 대기'로 둔다(5단계).
몸동작 규칙(riooo·optical-core·yukina 몸동작 제외)은 판정의 동작 칸을 이 애니메이터에서 읽지 않는 것으로 적용한다.

판정만 있는 영상(자동 탐지 없음, 2026-10-21 추가):
- GPT G15–G17·H01–H04(이름:초:주|배, 분류 칸 안에서 이름을 찾는다. '열람불가' 행은 뺀다): 비율 = 초 × 화면 가중(주 1.0, 배 0.5) / 길이. GPT 추정값이다.
- 나머지 판정(G01–G04·G07·G08·G13·G14·Claude)은 나옴/안 나옴만 있다. 비율은 같은 그룹의 탐지 영상 중 그 요소가 나온 영상의
  비율 중앙값으로 메운다(대입값). 판정 어휘는 TERM으로 트리 요소에 붙인다.
- 상위 요소(0·1단계)의 판정 비율은 자기와 자손 가운데 최대값이다.
- 탐지와 판정이 둘 다 있는 영상은 합집합: 태그로 기대 1초 미만인데 판정에 나오면 판정 값(최소 1초분)을 쓴다.
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np

KB = os.path.join(os.path.dirname(__file__), '..', 'data', 'style_kb')
STEP = 0.5
PRESENT_SEC = 1.0
FOLD_COUNT = 1000
W_SCREEN = {'주': 1.0, '배': 0.5}
GROUPS = ['나카무라_구작', '나카무라_신작', '나카무라_경계·미상', 'nian41', 'optical-core', 'yukina_kosaka', 'riooo']


# 판정 어휘 -> 트리 요소 이름. 트리 이름과 같은 말은 따로 적지 않는다.
TERM = {
    '화염': '불', '불꽃': '불', '분진': '먼지', '흙먼지': '먼지', '광선': '광선·레이저', '빔': '광선·레이저', '붉은 광선': '광선·레이저',
    '백색 광선': '광선·레이저', '번개': '번개·전기', '전기': '번개·전기', '출혈': '피 튐', '혈흔': '핏자국',
    '임팩트프레임': '임팩트 프레임', '흑백 임팩트프레임': '흑백', '실루엣 임팩트프레임': '임팩트 프레임', '스피드선': '속도선',
    '스파크': '불씨·불티', '불꽃 튐': '불씨·불티', '불티': '불씨·불티', '불똥': '불씨·불티', '오라 방출': '오라', '청색 오라': '오라',
    '발광 입자': '빛 입자', '반짝임': '빛 입자', '참격궤적': '검광·궤적', '참격 궤적': '검광·궤적', '검 궤적': '검광·궤적',
    '검광': '검광·궤적', '바람·기류': '바람', '마법진·문양': '마법진', '문양 발광': '문양·룬', '백색 전환': '화면 전환(와이프)',
    '화이트아웃': '화면 전환(와이프)', '암전': '화면 전환(와이프)', '색 전환': '화면 전환(와이프)', '디졸브': '화면 전환(와이프)',
    '배경 전환': '화면 전환(와이프)', '아이리스 전환': '화면 전환(와이프)', '줌·돌진 카메라': '줌·돌진', '카메라 회전·궤도': '회전·궤도',
    '카메라 회전': '회전·궤도', '카메라 흔들림': '흔들림', '로우앵글·하이앵글': '구도', '어안·광각': '어안',
    '2차 움직임(망토·머리카락)': '2차 움직임', '옷자락 흔들림': '천·망토 휘날림', '렌즈플레어': '렌즈 플레어',
    '충격 섬광': '섬광', '백색 섬광': '섬광', '방사형 섬광': '섬광', '얼음 파편': '얼음 조각', '암석 파편': '돌·콘크리트 조각',
    '돌 파편': '돌·콘크리트 조각', '낙석': '돌·콘크리트 조각', '눈보라': '눈', '눈가루': '눈', '포구섬광': '총구 화염',
    '총구섬광': '총구 화염', '포구 섬광': '총구 화염', '탄도': '탄도 궤적', '방어막': '방어막·배리어', '증기': '흰 연기·증기',
    '기포': '거품', '구조물 붕괴': '건물 붕괴', '장미꽃잎': '흩날림(잎·꽃잎)', '꽃잎': '흩날림(잎·꽃잎)', '공간 왜곡': '공간·중력',
    '둔기': '도끼·둔기', '광선 궤적': '광선·레이저', '전격': '번개·전기', '빙결 공격': '얼음', '빛기둥': '빛줄기',
    '촉수 공격': '촉수', '주먹': '맨손 타격', '발차기': '맨손 타격', '메카': '로봇·메카',
}
# 같은 이름이 둘인 요소는 판정 칸으로 고른다.
TERM_BY_COL = {('무기', '촉수'): '46', ('상대·생물', '촉수'): '313', ('상대·생물', '체액'): '314'}
JUDGE_COLS = ('동작', '동작종류', '이펙트', '이펙트종류', '연출종류')
SEC_COLS = ('무기', '원소 이펙트', '충격·파괴', '연출', '지형·자연', '인공 배경', '탈것', '상대·생물', '장비·의상')
BODY_SKIP = {'riooo', 'optical-core', 'yukina_kosaka'}


def read(path):
    return list(csv.DictReader(open(path, encoding='utf-8-sig')))


def era(y):
    try:
        y = int(y)
    except ValueError:
        return '경계·미상'
    return '구작' if 2004 <= y <= 2011 else '신작' if y >= 2014 else '경계·미상'


def group(an, year):
    return '나카무라_' + era(year) if an == 'yutaka_nakamura' else an


def tag_counts():
    d = glob.glob(os.path.expanduser('~/.cache/huggingface/hub/models--SmilingWolf--wd-vit-tagger-v3/snapshots/*'))
    if not d:
        return {}
    return {r['name']: int(r['count']) for r in read(os.path.join(d[0], 'selected_tags.csv'))}


def confidence(tags):
    """요소 태그와 가장 많이 겹치는(자카드) 채점 개념의 AUC. GPT 정답 채점(양성 5개 이상)을 우선한다.
    흑백은 태그 점수의 AUC(예전 방식)를 쓴다. 시간 비율 AUC는 cv 지표 값이라 태그 집계와 맞지 않는다."""
    sys.path.insert(0, os.path.dirname(__file__))
    from auto_calibrate import CONCEPTS
    cal = {}
    for src in ('gpt', 'all'):
        p = os.path.join(KB, 'auto_detect', f'calibration_{src}_2026-10-21.csv')
        if os.path.exists(p):
            cal[src] = {r['개념']: r for r in read(p)}
    best = None
    for c, (_, t) in CONCEPTS.items():
        j = len(set(t) & set(tags)) / len(set(t) | set(tags))
        if j and (best is None or j > best[1]):
            best = (c, j)
    if not best:
        return None
    for src in ('gpt', 'all'):
        r = cal.get(src, {}).get(best[0])
        if r and int(r['정답_있음']) >= 5:
            a = float(r['AUC_예전' if best[0] == '흑백 임팩트' else 'AUC_시간비율'])
            return best[0], src, a, best[1]
    return None


def terms(v):
    """'a;기타:b;복합(c+d)' -> a, b, c, d"""
    for x in (v or '').split(';'):
        x = x.strip()
        if x.startswith('복합(') and x.endswith(')'):
            yield from (y.strip() for y in x[3:-1].split('+'))
        elif x:
            yield x[3:] if x.startswith('기타:') else x


def is_desc(k, n, parent):
    while k:
        k = parent.get(k)
        if k == n:
            return True
    return False


def judgments(tree, anim):
    """post_id -> {요소번호: ('초', 비율) | ('있음', None)} (판정 파일 전체)."""
    num, by_cat = {}, {}
    parent = {r['번호']: r['부모번호'] for r in tree}
    name = {r['번호']: r['요소'] for r in tree}
    for r in tree:
        num.setdefault(r['요소'], r['번호'])
        k = r['번호']
        while parent[k]:
            k = parent[k]
        by_cat[(name[k], r['요소'])] = r['번호']

    def find(term, col=None):
        if (col, term) in TERM_BY_COL:
            return TERM_BY_COL[(col, term)]
        return by_cat.get((col, term)) or num.get(TERM.get(term, term))

    out = {}
    files = glob.glob(os.path.join(KB, 'action_counts', '[0-9]*.csv')) + glob.glob(os.path.join(KB, 'ai_results', 'gpt_[GH]*.csv'))
    for f in files:
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            pid = r['post_id']
            if '열람불가' in (r.get('특이사항') or ''):
                continue
            d = out.setdefault(pid, {})
            for col in JUDGE_COLS:
                if col.startswith('동작') and anim.get(pid) in BODY_SKIP:
                    continue
                for t in terms(r.get(col)):
                    n = find(t)
                    if n and n not in d:
                        d[n] = ('있음', None)
            dur = float(r.get('길이초') or 0)
            for col in SEC_COLS:
                for t in filter(None, (x.strip() for x in (r.get(col) or '').split(';'))):
                    if t.count(':') < 2:
                        continue
                    nm, sec, scr = t.rsplit(':', 2)
                    if not sec.isdigit():
                        continue
                    n = find(nm, col)
                    if n and dur:
                        v = min(1.0, float(sec) * W_SCREEN.get(scr, 0.5) / dur)
                        old = d.get(n)
                        d[n] = ('초', max(v, old[1] if old and old[1] else 0.0))
    return out


def main():
    det, out = sys.argv[1:3]
    tree = read(os.path.join(KB, 'element_tree_2026-10-20.csv'))
    year = {r['post_id']: r['year'] for r in read(os.path.join(KB, 'source_format_2026-10-20.csv'))}
    anim = {r['post_id']: r['animator'] for r in read(os.path.join(KB, 'judge_lists', 'auto_detect_list_2026-10-20.csv'))}
    cnt = tag_counts()

    kids = {}
    for r in tree:
        kids.setdefault(r['부모번호'], []).append(r['번호'])
    own = {r['번호']: r['태그'].split() for r in tree}
    parent = {r['번호']: r['부모번호'] for r in tree}

    def sub(n):
        t = list(own[n])
        for k in kids.get(n, []):
            t += sub(k)
        return t

    subtags = {r['번호']: sub(r['번호']) for r in tree}

    vids = []  # 탐지 영상: (그룹, 길이, {요소번호: 프레임 확률 배열(자기)}, {요소번호: 하위 포함})
    for f in sorted(glob.glob(os.path.join(det, '*.json'))):
        d = json.load(open(f))
        pid = d['post_id']
        if pid not in anim or not d['all']:
            continue
        g = group(anim[pid], year.get(pid, ''))
        fr = d['all']
        P, Q = {}, {}
        for r in tree:
            n = r['번호']
            for tg, dst in ((own[n], P), (subtags[n], Q)):
                if tg:
                    dst[n] = np.array([max((x.get(t, 0.0) for t in tg), default=0.0) for x in fr])
        vids.append((pid, g, len(fr) * STEP, P, Q))
    detected = {v[0] for v in vids}

    # 영상별 요소 비율 표: (그룹, 출처, {요소번호: 비율}, {요소번호: 기대초 또는 None})
    level = {r['번호']: r['단계'] for r in tree}
    table = []
    for pid, g, dur, P, Q in vids:
        R = {}
        for r in tree:
            n = r['번호']
            a = (Q if level[n] != '2' else P).get(n)
            if a is not None:
                R[n] = float(a.sum()) * STEP / dur
        table.append((g, '탐지', R, dur, pid))

    # 대입값: 그룹별(없으면 전체) 탐지 영상 중 나온 영상의 비율 중앙값
    def present(R, n, dur):
        return R.get(n, 0.0) * dur >= PRESENT_SEC

    imp = {}
    for r in tree:
        n = r['번호']
        allv = [R[n] for g, src, R, dur, _ in table if present(R, n, dur)]
        for g in GROUPS:
            v = [R[n] for gg, src, R, dur, _ in table if gg == g and present(R, n, dur)]
            imp[(g, n)] = float(np.median(v)) if v else float(np.median(allv)) if allv else None
    fallback = float(np.median([x for x in imp.values() if x])) if any(imp.values()) else 0.01

    J = judgments(tree, anim)

    def judged(pid, g):
        """판정 요소 -> 비율(초 있으면 그 값, 없으면 대입값), 상위 요소는 자손 최대값."""
        base = {n: (v if kind == '초' else (imp.get((g, n)) or fallback)) for n, (kind, v) in J[pid].items()}
        R = {}
        for r in tree:
            n = r['번호']
            ks = [n] + ([k for k in base if k != n and is_desc(k, n, parent)] if level[n] != '2' else [])
            vals = [base[k] for k in ks if k in base]
            if vals:
                R[n] = max(vals)
        return R

    # 탐지+판정 영상: 태그로 1초 미만인데 판정이 '있음'이면 판정 값을 쓴다(합집합).
    n_merge = 0
    for g, src, R, dur, pid in table:
        if pid in J:
            for n, v in judged(pid, g).items():
                if R.get(n, 0.0) * dur < PRESENT_SEC:
                    R[n] = max(v, PRESENT_SEC / dur)
                    n_merge += 1
    n_judge = 0
    for pid, an in anim.items():
        if pid in detected or pid not in J:
            continue
        g = group(an, year.get(pid, ''))
        table.append((g, '판정', judged(pid, g), None, pid))
        n_judge += 1

    durs = [t[3] for t in table if t[3]]
    med_dur = float(np.median(durs)) if durs else 1.0
    rows = []
    for r in tree:
        n = r['번호']
        row = {k: r[k] for k in ('번호', '부모번호', '단계', '요소', '관계', '난이도', '태그', 'CLIP')}
        key = 'Q' if r['단계'] != '2' else 'P'
        has_tag = bool(subtags[n] if key == 'Q' else own[n])
        row['집계태그'] = '하위 포함' if key == 'Q' and subtags[n] != own[n] else '자기'
        row['일반빈도'] = max((cnt.get(t, 0) for t in subtags[n]), default='')
        ratio = {g: [] for g in GROUPS}
        seen = {g: 0 for g in GROUPS}
        jseen = 0
        for g, src, R, dur, pid in table:
            if src == '탐지' and not has_tag and pid not in J:
                continue
            v = R.get(n, 0.0)
            ratio[g].append(v)
            hit = v * dur >= PRESENT_SEC if src == '탐지' else n in R
            seen[g] += hit
            jseen += hit and (src == '판정' or pid in J and n in J[pid])
        if not any(ratio.values()) or (not has_tag and not jseen):
            row['상태'] = 'CLIP 대기' if r['CLIP'] else ''
            rows.append(row)
            continue
        m = {g: (float(np.mean(ratio[g])) if ratio[g] else 0.0) for g in GROUPS}
        for g in GROUPS:
            row[g + '_비율%'] = f'{100 * m[g]:.3f}'
            row[g + '_영상수'] = f'{seen[g]}/{len(ratio[g])}'
        o, w = m['나카무라_구작'], m['나카무라_신작']
        fo = STEP / med_dur / max(len(ratio['나카무라_구작']), 1)
        fw = STEP / med_dur / max(len(ratio['나카무라_신작']), 1)
        row['나카무라_점수%'] = f'{100 * math.sqrt(max(o, fo) * max(w, fw)):.3f}'
        so, sw = seen['나카무라_구작'], seen['나카무라_신작']
        row['시기'] = '공통' if so and sw else '구작 전용' if so else '신작 전용' if sw else '없음'
        row['전체_영상수'] = sum(seen.values())
        row['판정_영상수'] = jseen
        if not has_tag:
            row['상태'] = '판정만(태그 없음)' + (' + CLIP 보충' if r['CLIP'] else '')
        elif sum(seen.values()) == 0 and (row['일반빈도'] or 0) < FOLD_COUNT:
            row['상태'] = '접기 후보'
        else:
            row['상태'] = '태그' + (' + CLIP 보충' if r['CLIP'] else '')
        c = confidence(own[n]) if own[n] else None
        if r['단계'] == '0':
            row['신뢰도'] = '하위 참조'
        elif c:
            row['신뢰도'] = f'{c[0]} AUC {c[2]:.2f} ({c[1]}, 겹침 {c[3]:.2f})'
            if c[0] == '흑백 임팩트':
                row['신뢰도'] += '; 원화·연필 영상의 흑백과 구분 못 함'
        else:
            row['신뢰도'] = '미채점'
        par = r['부모번호']
        if par and r['단계'] == '2' and own.get(par) and own[n]:
            num = den = 0.0
            for pid, g, dur, P, Q in vids:
                if g.startswith('나카무라'):
                    num += float(np.minimum(P[par], P[n]).sum())
                    den += float(P[par].sum())
            row['동반확률'] = f'{num / den:.3f}' if den >= 2 else ''
        rows.append(row)

    cols = ['번호', '부모번호', '단계', '요소', '관계', '난이도', '상태', '신뢰도', '나카무라_점수%', '시기']
    cols += [g + s for g in GROUPS for s in ('_비율%', '_영상수')]
    cols += ['전체_영상수', '판정_영상수', '동반확률', '집계태그', '일반빈도', '태그', 'CLIP']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('탐지', len(vids), '판정만', n_judge, '판정으로 보탠 칸', n_merge)


if __name__ == '__main__':
    main()
