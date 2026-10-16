#!/usr/bin/env python3
"""Sakugabooru collector: metadata first, typed tags, resumable, polite. Personal use only.

Usage (run from the repository root):
  python -m pipeline.collect_sakuga tags  DATA_DIR                 # all tags with type/count -> tags.json
  python -m pipeline.collect_sakuga posts DATA_DIR "fighting" --max 500   # post metadata -> posts.jsonl
  python -m pipeline.collect_sakuga stats DATA_DIR                 # tag/artist counts from collected posts
  python -m pipeline.collect_sakuga media DATA_DIR --max 200       # download files for collected posts

Everything resumes: re-running skips posts/files already stored (md5 checked). Requests are
spaced (default 1.5 s). Standard library only.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE = 'https://www.sakugabooru.com'
USER_AGENT = 'AI-sfa-personal-research/0.1 (personal, non-commercial)'
# Moebooru tag types. Sakugabooru labels may differ; raw numbers are always kept.
TAG_TYPES = {0: 'general', 1: 'artist', 3: 'copyright', 4: 'character', 5: 'meta'}
TRAINING_EXCLUDED_TYPES = {'copyright'}      # user decision: work titles are not learned


class Client:
    def __init__(self, delay=1.5, retries=4, opener=None):
        self.delay, self.retries, self._last = delay, retries, 0.0
        self.opener = opener or urllib.request.urlopen

    def _wait(self):
        gap = time.monotonic() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.monotonic()

    def get(self, path, params=None, raw=False, stream_to=None):
        url = path if path.startswith('http') else BASE + path
        if params:
            url += '?' + urllib.parse.urlencode(params)
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                with self.opener(req, timeout=60) as resp:
                    if stream_to is not None:
                        tmp = Path(str(stream_to) + '.part')
                        md5 = hashlib.md5()
                        with open(tmp, 'wb') as out:
                            while True:
                                chunk = resp.read(1 << 20)
                                if not chunk:
                                    break
                                md5.update(chunk)
                                out.write(chunk)
                        return tmp, md5.hexdigest()
                    data = resp.read()
                    return data if raw else json.loads(data.decode('utf-8'))
            except Exception as exc:  # network errors, 5xx, bad JSON
                if attempt == self.retries:
                    raise
                wait = 2 ** (attempt + 1)
                print(f'  재시도 {attempt + 1}/{self.retries} ({exc}); {wait}s 대기', file=sys.stderr)
                time.sleep(wait)


def load_tags(data_dir):
    path = Path(data_dir) / 'tags.json'
    if not path.exists():
        return {}
    return {t['name']: t for t in json.loads(path.read_text(encoding='utf-8'))}


def cmd_tags(client, data_dir):
    tags = client.get('/tag.json', {'limit': 0, 'order': 'count'})
    Path(data_dir, 'tags.json').write_text(json.dumps(tags, ensure_ascii=False), encoding='utf-8')
    counts = Counter(TAG_TYPES.get(t.get('type'), str(t.get('type'))) for t in tags)
    print(f'태그 {len(tags)}개 저장. 종류별: {dict(counts)}')


def typed_tags(tag_string, tag_table):
    out = {}
    for name in tag_string.split():
        info = tag_table.get(name)
        kind = TAG_TYPES.get(info.get('type'), str(info.get('type'))) if info else 'unknown'
        out.setdefault(kind, []).append(name)
    return out


def cmd_posts(client, data_dir, query, max_posts, per_page=100):
    data_dir = Path(data_dir)
    store = data_dir / 'posts.jsonl'
    seen = set()
    if store.exists():
        for line in store.read_text(encoding='utf-8').splitlines():
            if line.strip():
                seen.add(json.loads(line)['id'])
    tag_table = load_tags(data_dir)
    added, page = 0, 1
    with open(store, 'a', encoding='utf-8') as out:
        while added < max_posts:
            posts = client.get('/post.json', {'tags': query, 'limit': per_page, 'page': page})
            if not posts:
                break
            for p in posts:
                if p['id'] in seen:
                    continue
                record = {k: p.get(k) for k in ('id', 'md5', 'file_url', 'file_ext', 'file_size',
                                                 'width', 'height', 'score', 'rating', 'created_at',
                                                 'source', 'tags')}
                record['typed_tags'] = typed_tags(p.get('tags', ''), tag_table)
                record['query'] = query
                out.write(json.dumps(record, ensure_ascii=False) + '\n')
                seen.add(p['id'])
                added += 1
                if added >= max_posts:
                    break
            page += 1
    print(f'새 post {added}개 추가 (총 {len(seen)}개)')


def iter_posts(data_dir):
    store = Path(data_dir) / 'posts.jsonl'
    if store.exists():
        for line in store.read_text(encoding='utf-8').splitlines():
            if line.strip():
                yield json.loads(line)


def cmd_stats(data_dir, top=30):
    posts = list(iter_posts(data_dir))
    by_kind = {}
    for p in posts:
        for kind, names in p.get('typed_tags', {}).items():
            by_kind.setdefault(kind, Counter()).update(names)
    report = {'posts': len(posts), 'top': {k: c.most_common(top) for k, c in by_kind.items()}}
    Path(data_dir, 'stats.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"post {len(posts)}개")
    for kind in ('artist', 'general', 'meta', 'unknown'):
        if kind in report['top']:
            print(f"[{kind}]", ', '.join(f'{n}({c})' for n, c in report['top'][kind][:15]))


def cmd_media(client, data_dir, max_files):
    data_dir = Path(data_dir)
    media = data_dir / 'media'
    media.mkdir(exist_ok=True)
    index = data_dir / 'index.csv'
    new_index = not index.exists()
    done = 0
    with open(index, 'a', newline='', encoding='utf-8-sig') as fh:
        writer = csv.writer(fh)
        if new_index:
            writer.writerow(['id', 'file', 'md5', 'score', 'artists', 'general_tags', 'meta_tags'])
        for p in iter_posts(data_dir):
            if done >= max_files:
                break
            if not p.get('file_url'):
                continue
            target = media / f"{p['id']}.{p.get('file_ext') or 'bin'}"
            meta = media / f"{p['id']}.json"
            if target.exists() and hashlib.md5(target.read_bytes()).hexdigest() == p.get('md5'):
                continue
            tmp, digest = client.get(p['file_url'], stream_to=target)
            if p.get('md5') and digest != p['md5']:
                tmp.unlink(missing_ok=True)
                print(f"  md5 불일치로 건너뜀: {p['id']}", file=sys.stderr)
                continue
            os.replace(tmp, target)
            sidecar = dict(p)
            sidecar['training_tags'] = {k: v for k, v in p.get('typed_tags', {}).items()
                                        if k not in TRAINING_EXCLUDED_TYPES}
            meta.write_text(json.dumps(sidecar, ensure_ascii=False, indent=1), encoding='utf-8')
            tt = p.get('typed_tags', {})
            writer.writerow([p['id'], target.name, p.get('md5'), p.get('score'),
                             ' '.join(tt.get('artist', [])), ' '.join(tt.get('general', [])),
                             ' '.join(tt.get('meta', []))])
            done += 1
            print(f"  [{done}/{max_files}] {target.name}")
    print(f'파일 {done}개 받음')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('command', choices=['tags', 'posts', 'stats', 'media'])
    ap.add_argument('data_dir')
    ap.add_argument('query', nargs='?', default='')
    ap.add_argument('--max', type=int, default=200)
    ap.add_argument('--delay', type=float, default=1.5)
    a = ap.parse_args(argv)
    Path(a.data_dir).mkdir(parents=True, exist_ok=True)
    client = Client(delay=a.delay)
    if a.command == 'tags':
        cmd_tags(client, a.data_dir)
    elif a.command == 'posts':
        cmd_posts(client, a.data_dir, a.query, a.max)
    elif a.command == 'stats':
        cmd_stats(a.data_dir)
    else:
        cmd_media(client, a.data_dir, a.max)


if __name__ == '__main__':
    main()
