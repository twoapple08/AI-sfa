#!/usr/bin/env python3
"""서버에서 Kaggle GPU 학습을 원격으로(2026-10-30, 사용자: 컴퓨터 없이 학습). kaggle CLI를 부른다.
인증: 환경 변수 KAGGLE_USERNAME + KAGGLE_KEY(kaggle.json의 key) 또는 KAGGLE_API_TOKEN(새 방식 토큰). 환경 설정의 비밀값, 출력하지 않는다.
  push     : kaggle_seq_worker.py에 설정을 넣어 비공개 스크립트 커널로 올리고 실행(GPU·인터넷 켬, ckpt 자료가 있으면 입력으로)
  status   : 커널 상태
  wait     : 끝날 때까지 기다림(10분 간격, 최대 13시간)
  pull     : 결과(out/ckpt.pt·best.pt·log.jsonl·train_console.txt) 받기
  save-ckpt: 받은 ckpt.pt·best.pt·log.jsonl을 비공개 자료 aisfa-seq-ckpt로 올림(다음 push가 이어서 학습)
사용: python kaggle_seq_remote.py push [--minutes 690] [--plan-minutes 0] | wait | pull 폴더 | save-ckpt 폴더
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = 'aisfa-seq-train'
CKPT = 'aisfa-seq-ckpt'


def user():
    """인증: KAGGLE_USERNAME + (KAGGLE_KEY 또는 새 방식 토큰 KAGGLE_API_TOKEN). 값은 출력하지 않는다."""
    u = os.environ.get('KAGGLE_USERNAME')
    if not u or not (os.environ.get('KAGGLE_KEY') or os.environ.get('KAGGLE_API_TOKEN')):
        raise SystemExit('KAGGLE_USERNAME과 KAGGLE_KEY(또는 KAGGLE_API_TOKEN) 비밀값이 없음 — 환경 설정에 넣고 새 세션에서 실행')
    return u


def kg(*args, check=True):
    """kaggle CLI. 출력은 그대로 보이되 인증값은 CLI가 출력하지 않는다."""
    try:
        import kaggle  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kaggle'], check=True)
    r = subprocess.run(['kaggle', *args], capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if check and r.returncode:
        raise SystemExit(f'kaggle {args[0]} {args[1] if len(args) > 1 else ""} 실패: {out[-800:]}')
    return out


def ckpt_exists(u):
    out = kg('datasets', 'list', '--mine', '-s', CKPT, '--csv', check=False)
    return f'{u}/{CKPT}' in out


def push(a):
    u = user()
    src = open(os.path.join(HERE, 'kaggle_seq_worker.py'), encoding='utf-8').read()
    cfg = dict(branch=a.branch, session_minutes=a.minutes, plan_minutes=a.plan_minutes, tok_budget=a.tok_budget, extra=a.extra)
    src, n = re.subn(r"^CONFIG = \{.*\}$", 'CONFIG = ' + repr(cfg), src, count=1, flags=re.M)
    assert n == 1, 'CONFIG 줄을 못 찾음'
    d = tempfile.mkdtemp(prefix='kseq_')
    open(os.path.join(d, 'kernel.py'), 'w', encoding='utf-8').write(src)
    meta = dict(id=f'{u}/{KERNEL}', title=KERNEL, code_file='kernel.py', language='python', kernel_type='script',
                is_private=True, enable_gpu=True, enable_internet=True, dataset_sources=[], competition_sources=[], kernel_sources=[])
    if a.accel:
        meta['machine_shape'] = a.accel
    if not a.fresh and ckpt_exists(u):
        meta['dataset_sources'] = [f'{u}/{CKPT}']
        print('이어하기 자료를 입력으로:', f'{u}/{CKPT}', flush=True)
    json.dump(meta, open(os.path.join(d, 'kernel-metadata.json'), 'w'), ensure_ascii=False, indent=1)
    print(kg('kernels', 'push', '-p', d))
    shutil.rmtree(d)
    print('올림:', f'https://www.kaggle.com/code/{u}/{KERNEL}', '설정', cfg, flush=True)


def status(_=None):
    out = kg('kernels', 'status', f'{user()}/{KERNEL}')
    print(out, flush=True)
    return out


def wait(a):
    t0 = time.time()
    while time.time() - t0 < a.hours * 3600:
        out = status().lower()
        if any(k in out for k in ('complete', 'error', 'cancel')):
            return
        time.sleep(600)
    print('기다림 한도 넘음', flush=True)


def pull(a):
    os.makedirs(a.dir, exist_ok=True)
    print(kg('kernels', 'output', f'{user()}/{KERNEL}', '-p', a.dir))
    for f in ('out/run.json', 'out/log.jsonl'):
        p = os.path.join(a.dir, f)
        if os.path.exists(p):
            print(f, open(p, encoding='utf-8').read()[-1500:], flush=True)


def save_ckpt(a):
    u = user()
    src = os.path.join(a.dir, 'out')
    if not os.path.exists(os.path.join(src, 'ckpt.pt')):
        raise SystemExit(f'{src}/ckpt.pt 없음 — pull 먼저')
    d = tempfile.mkdtemp(prefix='kckpt_')
    for f in ('ckpt.pt', 'best.pt', 'log.jsonl'):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), d)
    json.dump(dict(title=CKPT, id=f'{u}/{CKPT}', licenses=[dict(name='CC0-1.0')]), open(os.path.join(d, 'dataset-metadata.json'), 'w'))
    if ckpt_exists(u):
        print(kg('datasets', 'version', '-p', d, '-m', time.strftime('%Y-%m-%d %H:%M'), '-q'))
    else:
        print(kg('datasets', 'create', '-p', d, '-q'))   # 기본 비공개
    shutil.rmtree(d)
    print('이어하기 자료 올림:', f'{u}/{CKPT}', flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('push')
    p.add_argument('--branch', default='ccr-bccf15a6-d6ee46')
    p.add_argument('--minutes', type=float, default=690, help='Kaggle 한 번 실행 시간(GPU 최대 12시간 안)')
    p.add_argument('--plan-minutes', type=float, default=0)
    p.add_argument('--tok-budget', type=int, default=12288)
    p.add_argument('--extra', default='', help='seq_train 옵션 덧붙이기')
    p.add_argument('--accel', default='NvidiaTeslaT4', help='machine_shape(빈 값이면 기본 GPU)')
    p.add_argument('--fresh', action='store_true', help='이어하기 자료를 붙이지 않고 처음부터')
    sub.add_parser('status')
    w = sub.add_parser('wait')
    w.add_argument('--hours', type=float, default=13)
    for nm in ('pull', 'save-ckpt'):
        q = sub.add_parser(nm)
        q.add_argument('dir')
    a = ap.parse_args()
    dict(push=push, status=status, wait=wait, pull=pull, **{'save-ckpt': save_ckpt})[a.cmd](a)


if __name__ == '__main__':
    main()
