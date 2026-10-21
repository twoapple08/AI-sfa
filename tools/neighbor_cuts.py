"""이웃 컷 재고 조사(메타데이터만, 영상은 받지 않는다): 나카무라 컷과 같은 작품·같은 화수의 다른 애니메이터 게시물을 Sakugabooru에서 모은다.

사용: python tools/neighbor_cuts.py <출력 csv> [캐시 폴더]
입력: data/sakuga/posts_yutaka_nakamura.jsonl, judge_lists/auto_detect_list_2026-10-20.csv(디지털 186개)
절차:
1. 디지털 나카무라 게시물의 태그 종류를 tag.json으로 확인해 작품(copyright, type 3) 태그를 얻는다.
2. 작품 태그마다 post.json으로 그 작품 게시물 전체를 받는다(1초 간격, 캐시).
3. source(화수)가 같은 다른 게시물을 이웃 컷으로 본다. 나카무라 태그가 붙은 것은 뺀다. 작품 전체 단위 이웃(화수 무관)도 따로 표시한다.
출력: 작품, 화수, post_id, 애니메이터 태그, 일반 태그, 같은 화수 여부, 기준 나카무라 post_id
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = 'https://www.sakugabooru.com'
ROOT = os.path.join(os.path.dirname(__file__), '..')


def get(path, cache):
    key = os.path.join(cache, urllib.parse.quote(path, safe='') + '.json')
    if os.path.exists(key):
        return json.load(open(key))
    for i in range(4):
        try:
            req = urllib.request.Request(API + path, headers={'User-Agent': 'AI-sfa-research/0.1'})
            d = json.load(urllib.request.urlopen(req, timeout=30))
            json.dump(d, open(key, 'w'))
            time.sleep(1.0)
            return d
        except Exception:
            time.sleep(2 ** (i + 1))
    raise RuntimeError(path)


def tag_types(names, cache):
    out = {}
    for n in names:
        d = get('/tag.json?' + urllib.parse.urlencode({'name': n, 'limit': 50}), cache)
        for t in d:
            if t['name'] == n:
                out[n] = int(t['type'])
    return out


def main():
    out = sys.argv[1]
    cache = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, '.cache_sakuga')
    os.makedirs(cache, exist_ok=True)
    digital = {r['post_id'] for r in csv.DictReader(open(os.path.join(ROOT, 'data/style_kb/judge_lists/auto_detect_list_2026-10-20.csv')))
               if r['animator'] == 'yutaka_nakamura'}
    nak = [json.loads(x) for x in open(os.path.join(ROOT, 'data/sakuga/posts_yutaka_nakamura.jsonl'))]
    nak = [p for p in nak if str(p['id']) in digital]
    names = sorted({t for p in nak for t in p['tags'].split()})
    ty = tag_types(names, cache)
    copy = {n for n, t in ty.items() if t == 3}
    artist = set()
    series = {}
    for p in nak:
        for t in p['tags'].split():
            if t in copy:
                series.setdefault(t, []).append(p)
    rows = []
    seen = set()
    for s, ps in sorted(series.items()):
        allp, page = [], 1
        while True:
            d = get('/post.json?' + urllib.parse.urlencode({'tags': s, 'limit': 100, 'page': page}), cache)
            allp += d
            if len(d) < 100:
                break
            page += 1
        eps = {}
        for p in ps:
            eps.setdefault((p.get('source') or '').strip(), []).append(str(p['id']))
        for q in allp:
            tags = q['tags'].split()
            if 'yutaka_nakamura' in tags or (s, str(q['id'])) in seen:
                continue
            seen.add((s, str(q['id'])))
            src = (q.get('source') or '').strip()
            same = bool(src) and src in eps
            rows.append({'작품': s, '화수': src, 'post_id': q['id'], '같은화수': 'O' if same else '',
                         '기준_나카무라': ';'.join(eps.get(src, [])) if same else '', 'tags': ' '.join(tags)})
            artist.update(tags)
    at = tag_types(sorted(artist - set(ty)), cache)
    at.update(ty)
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['작품', '화수', 'post_id', '같은화수', '기준_나카무라', '애니메이터', '일반태그'])
        for r in rows:
            tags = r['tags'].split()
            w.writerow([r['작품'], r['화수'], r['post_id'], r['같은화수'], r['기준_나카무라'],
                        ' '.join(t for t in tags if at.get(t) == 1), ' '.join(t for t in tags if at.get(t) == 0)])
    print('작품', len(series), '이웃 게시물', len(rows), '같은 화수', sum(r['같은화수'] == 'O' for r in rows))


if __name__ == '__main__':
    main()
