#!/usr/bin/env python3
"""기법 태그(itano_circus, kutsuna_lightning) 원본 수집 + contact sheet 드라이버 (Drive 기준 재개).

사용 예:
  python tools/collect_technique.py --work /tmp/work --workers 2

목록: data/sakuga/techniques/posts_<tag>.jsonl (두 태그에 모두 있는 게시물은 itano_circus 쪽에 한 번만).
원본: Drive gdrive:AI-sfa/01_원본영상/기법_<tag>/<post>_<md5>.<ext> (md5 대조 뒤 업로드).
분석: Drive gdrive:AI-sfa/02_분석자료/기법/<post>/(contact_sheet.jpg, timing.json, done.json).
done.json이 Drive에 있으면 건너뛴다.
제외 표시(받지 않음): 에반게리온, 정지 이미지, 반려 작가(isuta_meister·katsumi_ishizuka·sota_shigetsugu)
공동 태그 중 itano_circus. 반려 작가 공동 태그 kutsuna_lightning은 쿠츠나 학습 전용으로 받는다(사용자 2026-10-18).
기존 자료(catalog·candidates_catalog)에 원본이 있으면 원본은 다시 올리지 않고 contact sheet만 만든다.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = 'gdrive:AI-sfa/01_원본영상'
ANAL = 'gdrive:AI-sfa/02_분석자료/기법'
ENV = {**os.environ, 'RCLONE_LOG_LEVEL': 'ERROR'}
REJ = {'isuta_meister', 'katsumi_ishizuka', 'sota_shigetsugu'}
DELETED = ('_후보검토/isuta_meister', '_후보검토/katsumi_ishizuka', '_후보검토/sota_shigetsugu')


def existing():
    ours = {}
    for fn in ('data/catalog.csv', 'data/sakuga/candidates/candidates_catalog.csv'):
        for x in csv.DictReader(open(f'{ROOT}/{fn}', encoding='utf-8-sig')):
            if x['drive_path'] and not any(d in x['drive_path'] for d in DELETED):
                ours[x['post_id']] = x['drive_path']
    return ours


def jobs():
    out, seen = [], set()
    for t in ('itano_circus', 'kutsuna_lightning'):
        for line in open(f'{ROOT}/data/sakuga/techniques/posts_{t}.jsonl', encoding='utf-8'):
            p = json.loads(line)
            if p['id'] in seen:
                continue
            seen.add(p['id'])
            tags = set(p['tags'].split())
            flags = []
            if any('evangelion' in x for x in tags):
                flags.append('evangelion')
            if tags & REJ and t != 'kutsuna_lightning':
                flags.append('rejected_artist:' + '+'.join(sorted(tags & REJ)))
            if p['file_ext'] not in ('mp4', 'webm', 'gif'):
                flags.append('static')
            out.append((t, p, flags))
    return out


def lsf(path, *extra):
    r = subprocess.run(['rclone', 'lsf', *extra, path], capture_output=True, text=True, env=ENV,
                       stdin=subprocess.DEVNULL)
    return r.stdout.split()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--work', required=True)
    ap.add_argument('--workers', type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    done = {x.split('/')[0] for x in lsf(ANAL, '-R', '--include', '*/done.json')}
    have_orig = set(lsf(f'{ORIG}/기법_itano_circus')) | set(lsf(f'{ORIG}/기법_kutsuna_lightning'))
    ours = existing()
    todo = [j for j in jobs() if str(j[1]['id']) not in done]
    print(f'total {len(jobs())}, done on drive {len(done)}, todo {len(todo)}', flush=True)
    lock = threading.Lock()

    def do(job):
        t, p, flags = job
        pid = str(p['id'])
        out = os.path.join(a.work, pid)
        os.makedirs(out, exist_ok=True)
        rec = {'post_id': pid, 'tag': t, 'md5': p['md5'], 'ext': p['file_ext'], 'flags': flags,
               'source': p['source'], 'tags': p['tags']}
        if t == 'kutsuna_lightning' and set(p['tags'].split()) & REJ:
            rec['scope'] = 'kutsuna_lightning_only(반려 작가 공동 태그, 사용자 허가 2026-10-18)'
        name = f"{pid}_{p['md5']}.{p['file_ext']}"
        if flags:
            rec['status'] = 'skipped'
        else:
            src = os.path.join(a.work, name)
            ok = False
            for k in range(4):
                r = subprocess.run(['curl', '-sS', '-A', 'AI-sfa-research/0.1', '-o', src,
                                    f"https://www.sakugabooru.com/data/{p['md5']}.{p['file_ext']}"],
                                   stdin=subprocess.DEVNULL)
                if r.returncode == 0 and os.path.exists(src) and hashlib.md5(open(src, 'rb').read()).hexdigest() == p['md5']:
                    ok = True
                    break
                time.sleep(2 ** (k + 1))
            if not ok:
                rec['status'] = 'download_fail'
            else:
                if pid in ours:
                    rec['drive_path'] = ours[pid]
                elif name in have_orig:
                    rec['drive_path'] = f'01_원본영상/기법_{t}/{name}'
                else:
                    up = subprocess.run(['rclone', 'copyto', src, f'{ORIG}/기법_{t}/{name}'], env=ENV,
                                        stdin=subprocess.DEVNULL)
                    rec['drive_path'] = f'01_원본영상/기법_{t}/{name}' if up.returncode == 0 else None
                r = subprocess.run(['python3', f'{ROOT}/tools/sakuga_timing.py', src, '--sheet',
                                    f'{out}/contact_sheet.jpg', '--json', f'{out}/timing.json'],
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
                os.remove(src)
                rec['status'] = 'collected' if rec['drive_path'] and r.returncode == 0 else 'partial'
        json.dump(rec, open(f'{out}/done.json', 'w', encoding='utf-8'), ensure_ascii=False)
        up = subprocess.run(['rclone', 'copy', out, f'{ANAL}/{pid}'], env=ENV, stdin=subprocess.DEVNULL)
        if up.returncode == 0:
            shutil.rmtree(out)
        with lock:
            print(pid, t, rec['status'], flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(do, todo))
    print('ALL_DONE', flush=True)


if __name__ == '__main__':
    main()
