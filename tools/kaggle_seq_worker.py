#!/usr/bin/env python3
"""Kaggle GPU 작업자(2026-10-30, 재설계 영상 → 스파 문장 학습): 저장소 받기 → 자료(학습 + 늘리기 1벌, 시험) → 학습 → /kaggle/working/out.
kaggle_seq_remote.py가 CONFIG를 채워 Kaggle 스크립트 커널로 올린다(사용자 컴퓨터 없이). 이어하기: 입력 자료(ckpt 자료)에 ckpt.pt가 있으면 그것부터.
T4는 bf16이 없어 seq_train이 fp16 + GradScaler로 돈다. GPU는 1개만 쓴다.
"""
import glob
import json
import os
import shutil
import subprocess
import time

CONFIG = {'branch': 'ccr-bccf15a6-d6ee46', 'session_minutes': 690, 'plan_minutes': 0, 'tok_budget': 12288, 'extra': '', 'smoke': False}

T0 = time.time()


def sh(cmd):
    print('$', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def main():
    c = CONFIG
    out = '/kaggle/working/out'
    os.makedirs(out, exist_ok=True)
    sh('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true')
    sh('pip install -q skia-python')
    repo = '/kaggle/tmp/AI-sfa'
    if not os.path.isdir(repo):
        sh(f'git clone -q --depth 1 -b {c["branch"]} https://github.com/twoapple08/AI-sfa {repo}')
    sh(f'cd {repo} && git log --oneline -1')
    tools = f'{repo}/tools'
    # 이어하기: 입력 자료에 이전 학습 상태가 있으면 출력 폴더로(학습이 그 자리에서 이어서 한다)
    prev = sorted(glob.glob('/kaggle/input/**/ckpt.pt', recursive=True))
    if prev and not os.path.exists(f'{out}/ckpt.pt'):
        d = os.path.dirname(prev[0])
        for f in ('ckpt.pt', 'best.pt', 'log.jsonl'):
            if os.path.exists(f'{d}/{f}'):
                shutil.copy(f'{d}/{f}', out)
        print('이전 학습 상태에서 이어서:', d, flush=True)
    cpus = os.cpu_count() or 4
    data, val = '/kaggle/tmp/sd', '/kaggle/tmp/sv'
    t1 = time.time()
    if c.get('smoke'):   # 흐름 확인용(GPU 없이 몇 분): 아주 작은 자료·모델
        sh(f'cd {tools} && python -u seq_data.py {data} --maxlen 1024 --max-frames 6 --every 40 --aug 1 --workers {cpus}')
        sh(f'cd {tools} && python -u seq_data.py {val} --maxlen 1024 --max-frames 4 --holdout --workers {cpus}')
    else:
        sh(f'cd {tools} && python -u seq_data.py {data} --maxlen 2048 --max-frames 300 --aug 1 --workers {cpus}')
        sh(f'cd {tools} && python -u seq_data.py {val} --maxlen 2048 --max-frames 40 --holdout --workers {cpus}')
    print(f'자료 {(time.time() - t1) / 60:.1f}분', flush=True)
    left = c['session_minutes'] - (time.time() - T0) / 60 - (2 if c.get('smoke') else 20)   # 자료 읽기·마지막 검증·저장 몫
    if left < (1 if c.get('smoke') else 10):
        raise SystemExit('남은 시간이 없음')
    cmd = (f'cd {tools} && python -u seq_train.py train {data} {val} {out} --minutes {left:.0f} --plan-minutes {c["plan_minutes"]:.0f}'
           f' --tok-budget {c["tok_budget"]} {c["extra"]}')
    print('$', cmd, flush=True)
    con = open(f'{out}/train_console.txt', 'a', encoding='utf-8')
    pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    for line in pr.stdout:
        print(line, end='', flush=True)
        con.write(line)
        con.flush()
    rc = pr.wait()
    for f in ('seq_train.py', 'sfa_tokens.py'):
        shutil.copy(f'{tools}/{f}', out)
    json.dump(dict(rc=rc, minutes=(time.time() - T0) / 60, config=c), open(f'{out}/run.json', 'w'))
    print('끝', rc, f'{(time.time() - T0) / 60:.0f}분', flush=True)
    if rc:
        raise SystemExit(rc)


if __name__ == '__main__':
    main()
