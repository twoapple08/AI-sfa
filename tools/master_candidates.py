"""고수 후보 명단(메타데이터만, 영상은 받지 않는다): 공백 분야 태그를 많이 가진 Sakugabooru 애니메이터와 나카무라식 태그 비율을 센다.

사용: python tools/master_candidates.py <출력 csv> [캐시 폴더] [상위 애니메이터 수]
- 애니메이터: 게시물 수 상위 N명(artist_unknown 제외) + 지정 후보(EXTRA).
- 분야 태그(GAP): 공백·보충 필요 분야에 대응하는 일반 태그. 애니메이터+태그 게시물 수를 post.xml의 count로 센다.
- 스타일 태그(STYLE): 나카무라와 가까운지 보는 대리 지표. 애니메이터별 비율 벡터와 나카무라 비율 벡터의 코사인 유사도를 낸다.
  태그 비율만 본 대리값이다. 실제 섞임은 블라인드 시험으로 정한다(docs/BLIND-TEST-DESIGN-2026-10-21.md).
- 한계: 게시물 수에는 셀 시대 작업도 섞인다. 연도는 아직 보지 않는다.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = 'https://www.sakugabooru.com'
GAP = ['vehicle', 'missiles', 'liquid', 'creatures', 'animals', 'crowd', 'mecha', 'wind']
STYLE = ['smears', 'debris', 'yutapon_cubes', 'background_animation', 'smoke', 'explosions', 'beams', 'lightning', 'fire']
EXTRA = ['weilin_zhang', 'yutaka_nakamura', 'nian41', 'riooo', 'optical-core', 'yukina_kosaka']


def fetch(path, cache, raw=False):
    key = os.path.join(cache, urllib.parse.quote(path, safe=''))
    if os.path.exists(key):
        return open(key, encoding='utf-8').read()
    for i in range(4):
        try:
            req = urllib.request.Request(API + path, headers={'User-Agent': 'AI-sfa-research/0.1'})
            s = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
            open(key, 'w', encoding='utf-8').write(s)
            time.sleep(1.0)
            return s
        except Exception:
            time.sleep(2 ** (i + 1))
    raise RuntimeError(path)


def count(tags, cache):
    s = fetch('/post.xml?' + urllib.parse.urlencode({'tags': tags, 'limit': 1}), cache)
    m = re.search(r'count="(\d+)"', s)
    return int(m.group(1)) if m else 0


def main():
    out = sys.argv[1]
    cache = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', '.cache_sakuga')
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    os.makedirs(cache, exist_ok=True)
    arts = json.loads(fetch('/tag.json?' + urllib.parse.urlencode({'type': 1, 'order': 'count', 'limit': top + 1}), cache))
    names = [a['name'] for a in arts if a['name'] != 'artist_unknown'][:top]
    total = {a['name']: a['count'] for a in arts}
    for e in EXTRA:
        if e not in names:
            names.append(e)
    rows = []
    for k, a in enumerate(names):
        n = total.get(a) or count(a, cache)
        r = {'애니메이터': a, '게시물': n}
        for t in GAP + STYLE:
            r[t] = count(f'{a} {t}', cache)
        rows.append(r)
        print(k + 1, len(names), a, flush=True)
    def vec(r):
        return [r[t] / max(r['게시물'], 1) for t in STYLE]
    base = vec(next(r for r in rows if r['애니메이터'] == 'yutaka_nakamura'))
    nb = sum(x * x for x in base) ** 0.5
    for r in rows:
        v = vec(r)
        nv = sum(x * x for x in v) ** 0.5
        r['나카무라_유사도'] = f'{sum(x * y for x, y in zip(v, base)) / (nv * nb):.3f}' if nv and nb else ''
        r['분야_합'] = sum(r[t] for t in GAP)
    rows.sort(key=lambda r: -r['분야_합'])
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, ['애니메이터', '게시물', '분야_합', '나카무라_유사도'] + GAP + STYLE)
        w.writeheader()
        w.writerows(rows)
    print('애니메이터', len(rows))


if __name__ == '__main__':
    main()
