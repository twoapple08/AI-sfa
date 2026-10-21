"""요소 순위 초안: element_aggregate.py 결과로 요소마다 충분 / 보충 필요 / 공백을 정하고 부족분 순위를 매긴다.

사용: python tools/element_rank.py <집계 csv> <출력 csv> [CLIP 점수 npz(clip_score.py)]
기준(docs/GAP-MAP-2026-10-20.md와 같은 건수 기준):
- 나카무라 나온 영상 수 N = 구작 + 신작 + 경계·미상(탐지는 기대 1초 이상, 판정은 '있음').
- 공백: N 0–2. 보충 필요: N 3–9, 또는 N ≥ 10이어도 한 시기에만 나옴(구작 전용·신작 전용). 충분: 나머지.
- 점수 = 필요도 × 부족도 × 난이도. 필요도는 사용자 미정이라 모두 1. 부족도: 공백 3, 보충 필요 2, 충분 1.
  같은 점수 안에서는 일반빈도(Danbooru 태그 수)가 큰 것을 앞에 둔다(흔히 쓰이는 요소 먼저).
- 보충 출처: 승낙 범위 안에서 3개 이상 영상에 나온 애니메이터.
  nian41은 모든 분류, riooo·optical-core·yukina는 원소 이펙트·충격·파괴·연출만(riooo는 불 제외).
- 신뢰도 '약함': 채점 개념이 없거나(미채점) AUC 0.80 미만이거나 태그 없이 판정만 있는 요소. 육안 확인 후보다.
- 0단계(큰 분류)는 순위에서 빼고, CLIP 대기·접기 후보는 순위 없이 남긴다.
- 2차 움직임과 장비·의상은 순위 포함 여부가 사용자 미정이라 '포함 미정'으로 표시한다.
- 육안 보정(2026-10-21): auto_detect/visual_check_2026-10-21.csv가 있으면 N = (N − 태그로 나온 영상) + 태그로 나온 영상 × 정밀도.
  표본은 태그로 나온 나카무라 영상에서만 뽑았으므로 판정으로 센 몫은 그대로 둔다. 표본이 6개 이하라 정밀도 오차가 크다.
- 측정상태(2026-10-21): 아래 순서로 처음 맞는 것을 적는다.
  1. 확정(GPT 확인): 공백 확인 목록(judge_lists/gpt_gapcheck_checklist)에 있고, H01–H04가 나카무라 186개 중 90% 이상을 봤다('열람불가' 행 제외).
     GPT가 일부만 봤으면 'GPT 부분 확인 n/186'.
  2. 확정(육안): 육안 정밀도 0.67 이상.
  3. 확정(채점): 신뢰도 약함이 아니다(채점 AUC 0.80 이상).
  4. CLIP 확인(AUC≥0.75): auto_detect/clip_calibration(clip_calibrate.py, GPT 초 단위 판정 기준)에서 AUC 0.75 이상인 요소다.
     그 요소의 임계 z로 '나옴'(임계 이상 프레임 2개 이상)인 나카무라 영상 수를 'CLIP_나카무라영상'에 적는다.
     보정이 없거나 AUC가 낮은 요소는 'CLIP 약함'(CLIP_Z 사용)이다.
  5. 미확정.
"""
import csv
import os
import sys

KB = os.path.join(os.path.dirname(__file__), '..', 'data', 'style_kb')
CLIP_Z = 2.0
CLIP_AUC = 0.75
CLIP_CAL = os.path.join(KB, 'auto_detect', 'clip_calibration_2026-10-21.csv')
N_NAK = 186
VISUAL = os.path.join(os.path.dirname(__file__), '..', 'data', 'style_kb', 'auto_detect', 'visual_check_2026-10-21.csv')
SUPP = ['nian41', 'optical-core', 'yukina_kosaka', 'riooo']
EFFECT_CATS = {'원소 이펙트', '충격·파괴', '연출'}
LACK = {'공백': 3, '보충 필요': 2, '충분': 1}


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def seen(v):
    return int(v.split('/')[0]) if v else 0


def gpt_check():
    """공백 확인(H01–H04): (확인한 나카무라 영상 집합, {요소번호: 나온 영상 집합}, 확인 목록 요소번호 집합)."""
    import glob
    ck = os.path.join(KB, 'judge_lists', 'gpt_gapcheck_checklist_2026-10-21.csv')
    if not os.path.exists(ck):
        return set(), {}, set()
    key = {(r['분류'], r['요소']): r['번호'] for r in csv.DictReader(open(ck, encoding='utf-8'))}
    checked, present = set(), {}
    for f in glob.glob(os.path.join(KB, 'ai_results', 'gpt_H*.csv')):
        for r in csv.DictReader(open(f, encoding='utf-8-sig')):
            if '열람불가' in (r.get('특이사항') or ''):
                continue
            checked.add(r['post_id'])
            for (cat, nm), n in key.items():
                for t in (r.get(cat) or '').split(';'):
                    if t.strip().rsplit(':', 2)[0] == nm:
                        present.setdefault(n, set()).add(r['post_id'])
    return checked, present, set(key.values())


def clip_counts(path):
    """요소번호 -> (CLIP으로 나온 나카무라 영상 수, 믿을 만한가). 보정 파일에서 AUC ≥ CLIP_AUC인 요소는 그 요소의 임계 z를 쓰고,
    나머지는 CLIP_Z를 쓰되 '약함'으로 둔다. '나옴' = 임계 이상 프레임이 2개 이상."""
    import numpy as np
    if not path or not os.path.exists(path):
        return {}
    cal = {}
    if os.path.exists(CLIP_CAL):
        for r in csv.DictReader(open(CLIP_CAL, encoding='utf-8')):
            if r['상태'] == '보정됨' and r['AUC'] not in ('', 'nan') and float(r['AUC']) >= CLIP_AUC:
                cal[r['번호']] = float(r['임계_z'])
    nak = {r['post_id'] for r in csv.DictReader(open(os.path.join(KB, 'judge_lists', 'auto_detect_list_2026-10-20.csv')))
           if r['animator'] == 'yutaka_nakamura'}
    d = np.load(path)
    z = d['score'].astype(np.float32)
    out = {}
    for j, n in enumerate(d['elements']):
        n = str(n)
        t = cal.get(n, CLIP_Z)
        out[n] = (sum(1 for (a, b), p in zip(d['t_index'], d['post_ids'])
                      if str(p) in nak and int((z[a:b, j] >= t).sum()) >= 2), n in cal)
    return out


def main():
    src, out = sys.argv[1:3]
    checked, present, cklist = gpt_check()
    clip = clip_counts(sys.argv[3] if len(sys.argv) > 3 else '')
    rows = list(csv.DictReader(open(src, encoding='utf-8')))
    by = {r['번호']: r for r in rows}
    vis = {v['번호']: v for v in csv.DictReader(open(VISUAL, encoding='utf-8'))} if os.path.exists(VISUAL) else {}

    def top(r):
        while r['부모번호']:
            r = by[r['부모번호']]
        return r['요소']

    def under(r, name):
        while r:
            if r['요소'] == name:
                return True
            r = by.get(r['부모번호'])
        return False

    res = []
    for r in rows:
        if r['단계'] == '0':
            continue
        cat = top(r)
        o = {'번호': r['번호'], '분류': cat, '상위': by[r['부모번호']]['요소'] if r['단계'] == '2' else '',
             '요소': r['요소'], '관계': r['관계'], '난이도': r['난이도'], '집계상태': r['상태']}
        if not r.get('나카무라_점수%'):
            o['판정'] = '미측정(CLIP 대기)' if 'CLIP' in r['상태'] else '미측정'
            res.append(o)
            continue
        if r['상태'] == '접기 후보':
            o['판정'] = '접기'
            res.append(o)
            continue
        n_old, n_new = seen(r['나카무라_구작_영상수']), seen(r['나카무라_신작_영상수'])
        n = n_old + n_new + seen(r['나카무라_경계·미상_영상수'])
        n_raw, v = n, vis.get(r['번호'])
        if v:
            t = int(v['태그_나온_나카무라영상'])
            n = round(max(n - t, 0) + t * float(v['정밀도']))
        if n <= 2:
            lab = '공백'
        elif n < 10 or r['시기'] in ('구작 전용', '신작 전용'):
            lab = '보충 필요'
        else:
            lab = '충분'
        sup = []
        for a in SUPP:
            if a != 'nian41' and (cat not in EFFECT_CATS or (a == 'riooo' and under(r, '불'))):
                continue
            k = seen(r.get(a + '_영상수'))
            if k >= 3:
                sup.append(f'{a} {k}')
        weak = r['신뢰도'] == '미채점' or '판정만' in r['상태']
        if 'AUC' in r['신뢰도']:
            weak = weak or num(r['신뢰도'].split('AUC ')[1].split()[0]) < 0.80
        if v:
            weak = float(v['정밀도']) < 0.67
        o.update({'판정': lab, '나카무라_영상수': n, '보정전_영상수': n_raw if v else '',
                  '육안_정밀도': v['정밀도'] if v else '', '구작': r['나카무라_구작_영상수'], '신작': r['나카무라_신작_영상수'],
                  '시기': r['시기'], '나카무라_점수%': r['나카무라_점수%'], '보충_출처': '; '.join(sup),
                  '신뢰도': r['신뢰도'], '신뢰도_약함': 'O' if weak else '', '동반확률': r.get('동반확률', ''),
                  '일반빈도': r['일반빈도'],
                  '점수': LACK[lab] * int(r['난이도'] or 1),
                  '비고': '; '.join(x for x in (
                      '포함 미정' if cat == '장비·의상' or under(r, '2차 움직임') else '',
                      '태그 무효(육안 정밀도 0.2 미만) → CLIP 재측정' if v and float(v['정밀도']) < 0.2 else '') if x)})
        res.append(o)
    for o in res:
        n = o['번호']
        v = vis.get(n)
        st = '미확정'
        if n in cklist and checked:
            st = '확정(GPT 확인)' if len(checked) >= 0.9 * N_NAK else f'GPT 부분 확인 {len(checked)}/{N_NAK}'
            o['GPT_확인영상'] = len(checked)
            o['GPT_나옴영상'] = len(present.get(n, ()))
        elif v and float(v['정밀도']) >= 0.67:
            st = '확정(육안)'
        elif '점수' in o and not o.get('신뢰도_약함'):
            st = '확정(채점)'
        elif n in clip and clip[n][1]:
            st = 'CLIP 확인(AUC≥0.75)'
        elif n in clip:
            st = 'CLIP 약함'
        if n in clip:
            o['CLIP_나카무라영상'] = clip[n][0]
        o['측정상태'] = st
    ranked = sorted((o for o in res if '점수' in o), key=lambda o: (-o['점수'], -num(o['일반빈도']), -num(o['나카무라_점수%'])))
    for i, o in enumerate(ranked, 1):
        o['순위'] = i
    rest = [o for o in res if '점수' not in o]
    cols = ['순위', '점수', '판정', '분류', '상위', '요소', '관계', '난이도', '나카무라_영상수', '보정전_영상수', '육안_정밀도', '구작', '신작', '시기',
            '나카무라_점수%', '보충_출처', '측정상태', 'GPT_확인영상', 'GPT_나옴영상', 'CLIP_나카무라영상', '신뢰도_약함', '신뢰도', '동반확률', '일반빈도', '비고', '집계상태', '번호']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(ranked + rest)
    from collections import Counter
    print(Counter(o['판정'] for o in res))


if __name__ == '__main__':
    main()
