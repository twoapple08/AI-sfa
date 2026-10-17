#!/usr/bin/env python3
"""Drive '00_목록'용 수집 목록 CSV를 만든다.

사용 예:
  python tools/sakuga_catalog.py data/sakuga data/style_kb/observations.jsonl data/catalog.csv

열: post_id, url, md5, ext, size_mb, artists, presumed, roles, tags,
    duplicate_of, drive_path, status
- roles: 어느 뿌리/승낙 작가 목록에서 왔는지(여러 개 가능)
- duplicate_of: 같은 md5가 이미 나온 post_id(두 작가 목록에 겹친 게시물)
- status: 지식베이스에 관찰 기록이 있으면 analyzed, 아니면 indexed
"""
import csv
import json
import os
import sys

ROLE = {'yutaka_nakamura': '뿌리:이펙트·배경·연출', 'nian41': '뿌리:인체·캐릭터'}


def main(src, obs_path, out):
    types = json.load(open(os.path.join(src, 'tag_types.json'), encoding='utf-8'))
    analyzed = set()
    if os.path.exists(obs_path):
        with open(obs_path, encoding='utf-8') as f:
            analyzed = {json.loads(l)['post'] for l in f}
    rows, by_id, first_md5 = [], {}, {}
    for fn in sorted(os.listdir(src)):
        if not (fn.startswith('posts_') and fn.endswith('.jsonl')):
            continue
        root = fn[6:-6]
        with open(os.path.join(src, fn), encoding='utf-8') as f:
            for p in map(json.loads, f):
                if p['id'] in by_id:  # 다른 작가 목록에도 있는 같은 게시물
                    by_id[p['id']]['roles'] += ' | ' + ROLE.get(root, root)
                    continue
                tags = p['tags'].split()
                artists = [t for t in tags if types.get(t, {}).get('type') == 1]
                dup = first_md5.setdefault(p['md5'], p['id'])
                r = {'post_id': p['id'], 'url': f"https://www.sakugabooru.com/post/show/{p['id']}",
                     'md5': p['md5'], 'ext': p['file_ext'],
                     'size_mb': round((p['file_size'] or 0) / 1e6, 2),
                     'artists': ' '.join(artists), 'presumed': 'presumed' in tags,
                     'roles': ROLE.get(root, root),
                     'tags': ' '.join(t for t in tags if t not in artists),
                     'duplicate_of': '' if dup == p['id'] else dup,
                     'drive_path': f"01_원본영상/{root}/{p['id']}_{p['md5']}.{p['file_ext']}",
                     'status': 'analyzed' if p['id'] in analyzed else 'indexed'}
                by_id[p['id']] = r
                rows.append(r)
    with open(out, 'w', encoding='utf-8-sig', newline='') as f:  # BOM: 구글시트/엑셀 한글 깨짐 방지
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(rows)} rows -> {out}; analyzed={sum(r["status"] == "analyzed" for r in rows)}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
