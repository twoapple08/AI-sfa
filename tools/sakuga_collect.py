#!/usr/bin/env python3
"""catalog.csv의 원본 영상을 Google Drive 01_원본영상으로 수집한다.

사용 예:
  python tools/sakuga_collect.py data/catalog.csv --remote gdrive:AI-sfa --inventory data/drive_inventory.csv

- 서버 디스크를 거치지 않고 `rclone copyurl`로 Drive에 바로 올린다.
- 올린 뒤 Drive가 계산한 md5를 catalog의 md5와 대조한다. 다르면 지우고 실패로 센다.
- Drive에 같은 md5 파일이 이미 있으면 건너뛴다. duplicate_of가 있는 행은 받지 않는다.
- 요청 사이 간격은 --delay초(기본 1.0, 최소 1.0).
- --inventory: Drive에 실제로 있는 원본 목록(post_id,md5,drive_path,size)을 쓴다. 메타데이터만 담는다.
"""
import argparse
import csv
import json
import subprocess
import sys
import time

BASE = 'https://www.sakugabooru.com/data'


def rclone(*args, check=True):
    r = subprocess.run(['rclone', '-q', *args], capture_output=True, text=True)
    err = '\n'.join(l for l in r.stderr.splitlines() if 'NOTICE' not in l)
    if check and r.returncode:
        raise RuntimeError(f'rclone {args[0]} 실패({r.returncode}): {err[-500:]}')
    return r


def drive_files(remote):
    """01_원본영상 아래 파일들의 {경로: (md5, 크기)}."""
    r = rclone('lsjson', '-R', '--files-only', '--hash', f'{remote}/01_원본영상', check=False)
    if r.returncode:
        return {}
    return {f'01_원본영상/{e["Path"]}': ((e.get('Hashes') or {}).get('md5', ''), e['Size'])
            for e in json.loads(r.stdout or '[]')}


def write_inventory(path, rows, files):
    by_path = {r['drive_path']: r for r in rows}
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['post_id', 'md5', 'drive_path', 'size', 'md5_ok'])
        for p in sorted(files):
            md5, size = files[p]
            r = by_path.get(p)
            w.writerow([r['post_id'] if r else '', md5, p, size, bool(r) and md5 == r['md5']])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('catalog')
    ap.add_argument('--remote', default='gdrive:AI-sfa')
    ap.add_argument('--delay', type=float, default=1.0)
    ap.add_argument('--limit', type=int, default=0, help='이번에 받을 최대 개수(0=전부)')
    ap.add_argument('--inventory')
    a = ap.parse_args()
    delay = max(a.delay, 1.0)

    with open(a.catalog, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f)]
    want = [r for r in rows if not r['duplicate_of']]
    files = drive_files(a.remote)
    have = {md5 for md5, _ in files.values()}
    todo = [r for r in want if r['md5'] not in have]
    if a.limit:
        todo = todo[:a.limit]
    print(f'catalog {len(rows)}행, 대상 {len(want)}, Drive 보유 {len(want) - len([r for r in want if r["md5"] not in have])}, '
          f'이번 수집 {len(todo)} ({sum(float(r["size_mb"]) for r in todo):.0f} MB)', flush=True)

    ok = fail = 0
    for i, r in enumerate(todo, 1):
        dest = f'{a.remote}/{r["drive_path"]}'
        url = f'{BASE}/{r["md5"]}.{r["ext"]}'
        t0 = time.time()
        try:
            rclone('copyurl', url, dest)
            got = rclone('lsjson', '--hash', dest).stdout
            md5 = ((json.loads(got)[0].get('Hashes') or {}).get('md5', '')) if got.strip() not in ('', '[]') else ''
            if md5 != r['md5']:
                rclone('deletefile', dest, check=False)
                raise RuntimeError(f'md5 불일치 {md5 or "(없음)"}')
            ok += 1
            print(f'[{i}/{len(todo)}] ok {r["post_id"]} {r["size_mb"]}MB {time.time() - t0:.1f}s', flush=True)
        except Exception as e:  # 한 파일 실패로 전체를 멈추지 않는다
            fail += 1
            print(f'[{i}/{len(todo)}] FAIL {r["post_id"]}: {e}', flush=True)
        time.sleep(delay)

    print(f'완료: 성공 {ok}, 실패 {fail}', flush=True)
    if a.inventory:
        write_inventory(a.inventory, rows, drive_files(a.remote))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
