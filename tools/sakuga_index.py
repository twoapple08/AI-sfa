#!/usr/bin/env python3
"""Sakugabooru 메타데이터 색인 도구 (영상은 내려받지 않음).

사용 예:
  python tools/sakuga_index.py fetch yutaka_nakamura nian41 --out data/sakuga
  python tools/sakuga_index.py summary data/sakuga --top 30

fetch는 공개 API(post.json/tag.json)만 요청하고 요청 사이에 지연을 둔다.
저장 내용: 게시물 ID·태그·점수·크기·해상도·출처 문자열·md5 (영상 본문 없음).
"""
import argparse
import collections
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = 'https://www.sakugabooru.com'
UA = 'AI-sfa-metadata-indexer/0.1 (personal research; low rate)'
KEEP = ('id', 'tags', 'score', 'md5', 'file_size', 'file_ext', 'source',
        'width', 'height', 'created_at', 'parent_id', 'rating', 'status')
TYPE_NAMES = {0: 'general', 1: 'artist', 3: 'copyright', 4: 'character',
              5: 'meta', 6: 'meta'}


def get_json(path, params, delay):
    url = f'{BASE}/{path}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
            time.sleep(delay)
            return data
        except Exception as e:  # network/5xx: back off and retry
            if attempt == 3:
                raise
            print(f'retry {attempt + 1}: {e}', file=sys.stderr)
            time.sleep(2 ** (attempt + 1))


def fetch_posts(tag, delay):
    posts, page = [], 1
    while True:
        batch = get_json('post.json', {'tags': tag, 'limit': 100, 'page': page}, delay)
        if not batch:
            return posts
        posts.extend({k: p.get(k) for k in KEEP} for p in batch)
        page += 1


def tag_types(delay):
    """유형별 전체 태그 목록을 한 번씩 받아 이름→유형/개수 표를 만든다."""
    table = {}
    for kind in (1, 3, 4, 5, 6):
        for r in get_json('tag.json', {'type': kind, 'limit': 0}, delay):
            table[r['name']] = {'type': r['type'], 'count': r['count']}
    return table


def cmd_fetch(a):
    os.makedirs(a.out, exist_ok=True)
    for tag in a.tags:
        posts = fetch_posts(tag, a.delay)
        path = os.path.join(a.out, f'posts_{tag}.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for p in posts:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
        print(f'{tag}: {len(posts)} posts -> {path}')
    with open(os.path.join(a.out, 'tag_types.json'), 'w', encoding='utf-8') as f:
        json.dump(tag_types(a.delay), f, ensure_ascii=False, sort_keys=True)


def load(dirpath):
    cache = json.load(open(os.path.join(dirpath, 'tag_types.json'), encoding='utf-8'))
    sets = {}
    for fn in sorted(os.listdir(dirpath)):
        if fn.startswith('posts_') and fn.endswith('.jsonl'):
            with open(os.path.join(dirpath, fn), encoding='utf-8') as f:
                sets[fn[6:-6]] = [json.loads(l) for l in f]
    return sets, cache


def cmd_summary(a):
    sets, cache = load(a.dir)
    for root, posts in sets.items():
        size = sum(p['file_size'] or 0 for p in posts)
        exts = collections.Counter(p['file_ext'] for p in posts)
        print(f'\n## {root}: {len(posts)} posts, {size / 2**30:.2f} GiB, {dict(exts)}')
        by_type = collections.defaultdict(collections.Counter)
        for p in posts:
            for t in p['tags'].split():
                info = cache.get(t)
                kind = TYPE_NAMES.get(info['type'], str(info['type'])) if info else 'general'
                if t != root:
                    by_type[kind][t] += 1
        for kind in ('artist', 'general', 'copyright', 'meta'):
            top = by_type[kind].most_common(a.top)
            print(f'- {kind}: ' + ', '.join(f'{t}({n})' for t, n in top))


def cmd_profiles(a):
    """count>=min_count인 artist마다 최근 게시물 최대 100개의 태그·점수만 모은다(재개 가능)."""
    types = json.load(open(os.path.join(a.dir, 'tag_types.json'), encoding='utf-8'))
    artists = sorted(k for k, v in types.items() if v['type'] == 1 and v['count'] >= a.min_count)
    path = os.path.join(a.dir, 'artist_profiles.jsonl')
    done = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            done = {json.loads(l)['artist'] for l in f}
    with open(path, 'a', encoding='utf-8') as f:
        for i, name in enumerate(artists):
            if name in done or name == 'artist_unknown':
                continue
            batch = get_json('post.json', {'tags': name, 'limit': 100}, a.delay)
            f.write(json.dumps({'artist': name, 'n': len(batch),
                                'posts': [[p['tags'], p['score']] for p in batch]},
                               ensure_ascii=False) + '\n')
            f.flush()
            if i % 50 == 0:
                print(f'{i}/{len(artists)} {name}', file=sys.stderr)


def cmd_similar(a):
    """뿌리 artist의 general 태그 비율 벡터와 cosine 유사도를 계산한다."""
    import math
    import statistics
    types = json.load(open(os.path.join(a.dir, 'tag_types.json'), encoding='utf-8'))
    profs = {}
    with open(os.path.join(a.dir, 'artist_profiles.jsonl'), encoding='utf-8') as f:
        for l in f:
            r = json.loads(l)
            profs[r['artist']] = r
    # 제작 자료·지역(국적 무관 지시)·형식 태그는 스타일 벡터에서 뺀다
    skip = {'animated', 'production_materials', 'genga', 'illustration', 'web', 'remake',
            'presumed', 'eastern', 'western', 'artist_unknown', 'translated', 'storyboard',
            'layout', 'rough', 'correction', 'comparison', 'settei', 'sakuga_guide',
            # 소재(무엇을 그렸나) 태그: 스타일 유사도를 왜곡하므로 제외
            'mecha', 'creatures', 'animals', 'vehicle', 'vehicles', 'food', 'dancing', 'sports'}

    def vec(posts):
        c = collections.Counter()
        for tags, _ in posts:
            for t in set(tags.split()):
                if t not in types and t not in skip:
                    c[t] += 1
        n = max(len(posts), 1)
        return {t: v / n for t, v in c.items()}

    def cos(x, y):
        dot = sum(v * y.get(t, 0) for t, v in x.items())
        nx = math.sqrt(sum(v * v for v in x.values()))
        ny = math.sqrt(sum(v * v for v in y.values()))
        return dot / (nx * ny) if nx and ny else 0.0

    for root in a.roots:  # 뿌리는 전체 게시물 파일이 있으면 그것을 쓴다
        full = os.path.join(a.dir, f'posts_{root}.jsonl')
        if os.path.exists(full):
            with open(full, encoding='utf-8') as f:
                ps = [json.loads(l) for l in f]
            profs[root] = {'artist': root, 'n': len(ps),
                           'posts': [[p['tags'], p['score']] for p in ps]}
    vecs = {k: vec(r['posts']) for k, r in profs.items()
            if r['n'] >= a.min_posts or k in a.roots}
    df = collections.Counter(t for v in vecs.values() for t in v)
    idf = {t: math.log(len(vecs) / c) for t, c in df.items()}
    vecs = {k: {t: x * idf[t] for t, x in v.items()} for k, v in vecs.items()}
    out = {}
    for root in a.roots:
        rv = vecs[root]
        rows = []
        for k, v in vecs.items():
            if k in a.roots:
                continue
            scores = [s for _, s in profs[k]['posts']]
            region = sum('eastern' in t.split() for t, _ in profs[k]['posts']) / profs[k]['n']
            rows.append({'artist': k, 'sim': round(cos(rv, v), 4), 'n': profs[k]['n'],
                         'median_score': statistics.median(scores),
                         'top_tags': [t for t, _ in sorted(v.items(), key=lambda x: -x[1])[:6]],
                         'yutapon_cubes': round(v.get('yutapon_cubes', 0), 2),
                         'eastern': round(region, 2)})
        rows.sort(key=lambda r: -r['sim'])
        out[root] = rows[:a.top]
        print(f'\n## {root}')
        for r in rows[:a.top]:
            print(r)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('tags', nargs='+')
    f.add_argument('--out', required=True)
    f.add_argument('--delay', type=float, default=1.0)
    s = sub.add_parser('summary')
    s.add_argument('dir')
    s.add_argument('--top', type=int, default=25)
    pr = sub.add_parser('profiles')
    pr.add_argument('dir')
    pr.add_argument('--min-count', type=int, default=30)
    pr.add_argument('--delay', type=float, default=1.0)
    si = sub.add_parser('similar')
    si.add_argument('dir')
    si.add_argument('roots', nargs='+')
    si.add_argument('--min-posts', type=int, default=20)
    si.add_argument('--top', type=int, default=40)
    si.add_argument('--json')
    a = ap.parse_args()
    {'fetch': cmd_fetch, 'summary': cmd_summary, 'profiles': cmd_profiles,
     'similar': cmd_similar}[a.cmd](a)


if __name__ == '__main__':
    main()
