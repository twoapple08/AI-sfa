"""요소 순위 초안: element_aggregate.py 결과로 요소마다 충분 / 보충 필요 / 공백을 정하고 부족분 순위를 매긴다.

사용: python tools/element_rank.py <집계 csv> <출력 csv>
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
"""
import csv
import sys

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


def main():
    src, out = sys.argv[1:3]
    rows = list(csv.DictReader(open(src, encoding='utf-8')))
    by = {r['번호']: r for r in rows}

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
        o.update({'판정': lab, '나카무라_영상수': n, '구작': r['나카무라_구작_영상수'], '신작': r['나카무라_신작_영상수'],
                  '시기': r['시기'], '나카무라_점수%': r['나카무라_점수%'], '보충_출처': '; '.join(sup),
                  '신뢰도': r['신뢰도'], '신뢰도_약함': 'O' if weak else '', '동반확률': r.get('동반확률', ''),
                  '일반빈도': r['일반빈도'],
                  '점수': LACK[lab] * int(r['난이도'] or 1),
                  '비고': '포함 미정' if cat == '장비·의상' or under(r, '2차 움직임') else ''})
        res.append(o)
    ranked = sorted((o for o in res if '점수' in o), key=lambda o: (-o['점수'], -num(o['일반빈도']), -num(o['나카무라_점수%'])))
    for i, o in enumerate(ranked, 1):
        o['순위'] = i
    rest = [o for o in res if '점수' not in o]
    cols = ['순위', '점수', '판정', '분류', '상위', '요소', '관계', '난이도', '나카무라_영상수', '구작', '신작', '시기',
            '나카무라_점수%', '보충_출처', '신뢰도_약함', '신뢰도', '동반확률', '일반빈도', '비고', '집계상태', '번호']
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(ranked + rest)
    from collections import Counter
    print(Counter(o['판정'] for o in res))


if __name__ == '__main__':
    main()
