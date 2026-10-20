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
몸동작 규칙(riooo·optical-core·yukina 몸동작 제외)은 트리에 몸동작 분류가 없어 여기서는 적용할 행이 없다.
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
GROUPS = ['나카무라_구작', '나카무라_신작', '나카무라_경계·미상', 'nian41', 'optical-core', 'yukina_kosaka', 'riooo']


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

    def sub(n):
        t = list(own[n])
        for k in kids.get(n, []):
            t += sub(k)
        return t

    subtags = {r['번호']: sub(r['번호']) for r in tree}

    vids = []  # (그룹, 길이, {요소번호: 프레임 확률 배열(자기)}, {요소번호: 하위 포함})
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
        vids.append((g, len(fr) * STEP, P, Q))

    n_g = {g: sum(v[0] == g for v in vids) for g in GROUPS}
    med_dur = float(np.median([v[1] for v in vids])) if vids else 1.0
    rows = []
    for r in tree:
        n = r['번호']
        row = {k: r[k] for k in ('번호', '부모번호', '단계', '요소', '관계', '난이도', '태그', 'CLIP')}
        key = 'Q' if r['단계'] != '2' else 'P'
        has = bool(subtags[n] if key == 'Q' else own[n])
        row['집계태그'] = '하위 포함' if key == 'Q' and subtags[n] != own[n] else '자기'
        row['일반빈도'] = max((cnt.get(t, 0) for t in subtags[n]), default='')
        if not has:
            row['상태'] = 'CLIP 대기' if r['CLIP'] else ''
            rows.append(row)
            continue
        ratio = {g: [] for g in GROUPS}
        seen = {g: 0 for g in GROUPS}
        secs = 0.0
        for g, dur, P, Q in vids:
            a = (Q if key == 'Q' else P)[n]
            s = float(a.sum()) * STEP
            secs += s
            ratio[g].append(s / dur)
            seen[g] += s >= PRESENT_SEC
        m = {g: (float(np.mean(ratio[g])) if ratio[g] else 0.0) for g in GROUPS}
        for g in GROUPS:
            row[g + '_비율%'] = f'{100 * m[g]:.3f}'
            row[g + '_영상수'] = f'{seen[g]}/{n_g[g]}'
        o, w = m['나카무라_구작'], m['나카무라_신작']
        fo = STEP / med_dur / max(n_g['나카무라_구작'], 1)
        fw = STEP / med_dur / max(n_g['나카무라_신작'], 1)
        row['나카무라_점수%'] = f'{100 * math.sqrt(max(o, fo) * max(w, fw)):.3f}'
        so, sw = seen['나카무라_구작'], seen['나카무라_신작']
        row['시기'] = '공통' if so and sw else '구작 전용' if so else '신작 전용' if sw else '없음'
        row['전체_기대초'] = f'{secs:.1f}'
        row['전체_영상수'] = sum(seen.values())
        if sum(seen.values()) == 0 and (row['일반빈도'] or 0) < FOLD_COUNT:
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
        if par and r['단계'] == '2' and own.get(par):
            num = den = 0.0
            for g, dur, P, Q in vids:
                if g.startswith('나카무라'):
                    num += float(np.minimum(P[par], P[n]).sum())
                    den += float(P[par].sum())
            row['동반확률'] = f'{num / den:.3f}' if den >= 2 else ''
        rows.append(row)

    cols = ['번호', '부모번호', '단계', '요소', '관계', '난이도', '상태', '신뢰도', '나카무라_점수%', '시기']
    cols += [g + s for g in GROUPS for s in ('_비율%', '_영상수')]
    cols += ['전체_기대초', '전체_영상수', '동반확률', '집계태그', '일반빈도', '태그', 'CLIP']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print('영상', len(vids), {g: n_g[g] for g in GROUPS})


if __name__ == '__main__':
    main()
