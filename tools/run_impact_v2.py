#!/usr/bin/env python3
"""임팩트 프레임 전체 재검사 드라이버 (impact_scan2, Drive 기준 재개).

사용 예:
  python tools/run_impact_v2.py --work /tmp/work --workers 3

대상: data/catalog.csv의 yutaka_nakamura 영상(mp4·gif·webm, discarded 제외)과
작업 15 편입 3명(intake_index_*.csv, presumed 제외).
원본은 Sakugabooru(md5)에서 임시로 받아 md5를 대조하고, 검사 뒤 지운다.
결과는 Drive gdrive:AI-sfa/02_분석자료/impact_v2/<post>/(impact.json, v2_f*.jpg)에 바로 올린다.
Drive에 impact.json이 이미 있는 게시물은 건너뛴다. 진행 기록은 Drive impact_v2/_progress.log에 덧붙인다.
"""
import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVE = 'gdrive:AI-sfa/02_분석자료/impact_v2'
ENV = {**os.environ, 'RCLONE_LOG_LEVEL': 'ERROR'}


def jobs():
    out = []
    for x in csv.DictReader(open(f'{ROOT}/data/catalog.csv', encoding='utf-8-sig')):
        if 'yutaka_nakamura' in x['artists'] and x['status'] != 'discarded' and x['ext'] in ('mp4', 'gif', 'webm'):
            out.append(('yutaka_nakamura', x['post_id'], x['md5'], x['ext']))
    for fn in ('intake_index_riooo_optical-core_2026-10-18.csv', 'intake_index_yukina_kosaka_2026-10-18.csv'):
        for x in csv.DictReader(open(f'{ROOT}/data/sakuga/candidates/{fn}', encoding='utf-8')):
            if x['presumed'] != 'True':
                md5 = os.path.basename(x['drive_path']).split('_', 1)[1].rsplit('.', 1)[0]
                out.append((x['artist'], x['post_id'], md5, x['ext']))
    return out


def done_on_drive():
    r = subprocess.run(['rclone', 'lsf', '-R', '--include', '*/impact.json', DRIVE],
                       capture_output=True, text=True, env=ENV, stdin=subprocess.DEVNULL)
    return {line.split('/')[0] for line in r.stdout.split()}


def download(md5, ext, dest):
    for k in range(4):
        r = subprocess.run(['curl', '-sS', '-A', 'AI-sfa-research/0.1', '-o', dest,
                            f'https://www.sakugabooru.com/data/{md5}.{ext}'], stdin=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.exists(dest) and hashlib.md5(open(dest, 'rb').read()).hexdigest() == md5:
            return True
        time.sleep(2 ** (k + 1))
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--work', required=True)
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    done = done_on_drive()
    todo = [j for j in jobs() if j[1] not in done]
    print(f'total {len(jobs())}, on drive {len(done)}, todo {len(todo)}', flush=True)
    lock = threading.Lock()
    log = os.path.join(a.work, '_progress.log')

    def do(job):
        artist, pid, md5, ext = job
        out = os.path.join(a.work, pid)
        os.makedirs(out, exist_ok=True)
        src = os.path.join(a.work, f'{pid}.{ext}')
        if not download(md5, ext, src):
            line = f'{pid}\t{artist}\tDOWNLOAD_FAIL'
        else:
            r = subprocess.run(['python3', f'{ROOT}/tools/impact_scan2.py', src, '--json', f'{out}/impact.json',
                                '--sheets', out], capture_output=True, text=True, stdin=subprocess.DEVNULL)
            os.remove(src)
            up = subprocess.run(['rclone', 'copy', out, f'{DRIVE}/{pid}'], env=ENV, stdin=subprocess.DEVNULL)
            line = f'{pid}\t{artist}\trc={r.returncode}\tupload={up.returncode}\t{r.stdout.strip()[:160]}'
            if r.returncode == 0 and up.returncode == 0:
                shutil.rmtree(out)
        with lock:
            with open(log, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
            print(line, flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(do, todo))
    subprocess.run(['rclone', 'copyto', log, f'{DRIVE}/_progress_{int(time.time())}.log'], env=ENV)
    print('ALL_DONE', flush=True)


if __name__ == '__main__':
    main()
