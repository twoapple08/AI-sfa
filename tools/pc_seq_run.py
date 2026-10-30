#!/usr/bin/env python3
"""PC에서 재설계 학습(영상 → 스파 문장, 2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): 자료 → 학습 → 15분마다 Drive 저장 → 다음 실행 때 이어서.
pc_seq_*.bat이 설치를 마친 뒤 부른다. Drive: gdrive:AI-sfa/02_분석자료/seq/<run>/ 에 ckpt.pt·best.pt·log.jsonl·train_console.txt.
Drive 연결·절전 막기·화면 기록·올리기는 pc_vec_run.py의 것을 그대로 쓴다.
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pc_vec_run as P  # noqa: E402

DRIVE_BASE = 'gdrive:AI-sfa/02_분석자료/seq'
KEEP = ['ckpt.pt', 'best.pt', 'log.jsonl', 'train_console.txt', 'seq_train.py', 'sfa_tokens.py']


def upload(rclone, out, drive, names):
    inc = ' '.join(f'--include "{k}"' for k in names)
    return subprocess.run(f'"{rclone}" copy "{out}" "{drive}" {inc}', shell=True).returncode == 0


def uploader(out, rclone, drive, stop, every=900):
    while not stop.wait(every):
        if os.path.exists(os.path.join(out, 'ckpt.pt')):
            ok = upload(rclone, out, drive, ['ckpt.pt', 'best.pt', 'log.jsonl', 'train_console.txt'])
            print(time.strftime('%H:%M'), 'Drive 중간 저장', '정상' if ok else '실패', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=r'C:\aisfa\seq')
    ap.add_argument('--hours', type=float, default=3.0, help='이번 실행 시간(자료 만들기 포함)')
    ap.add_argument('--plan-hours', type=float, default=0, help='전체 학습 계획(여러 번 나눠 돌릴 때). 0이면 이번 실행 시간(이어할 땐 그만큼 늘림)')
    ap.add_argument('--rclone', default='')
    ap.add_argument('--run', default='s1')
    ap.add_argument('--yield', dest='yield_', action='store_true')
    ap.add_argument('--quick', action='store_true', help='몇 분짜리 시험(1050 Ti): 작은 자료 + 실제 모델 크기로 4분 학습·1분 이어하기, 속도·메모리 측정')
    ap.add_argument('--tok-budget', type=int, default=12288)
    a = ap.parse_args()
    drive = f'{DRIVE_BASE}/{a.run}' + ('_quick' if a.quick else '')
    if a.rclone:
        a.rclone = P.ensure_drive(a.rclone, drive)
    t_start = time.time()
    P.keep_awake()
    tools = os.path.join(a.root, 'repo', 'tools')
    py = sys.executable
    cpus = os.cpu_count() or 4
    if a.yield_:
        cpus = max(2, cpus // 2)
    lp = ' --low-priority' if a.yield_ else ''
    extra = (' ' + os.environ['AISFA_SEQ_TRAIN_ARGS']) if os.environ.get('AISFA_SEQ_TRAIN_ARGS') else ''   # 학습 옵션 덧붙이기(예: --grad-ckpt)
    import torch
    if torch.cuda.is_available():
        print('GPU', torch.cuda.get_device_name(0), round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1), 'GB',
              '계산 능력', torch.cuda.get_device_capability(0), flush=True)
    else:
        print('GPU 없음(CPU로 진행 — 매우 느림)', flush=True)
    if a.quick:
        data, val, out = (os.path.join(a.root, x) for x in ('sd_quick', 'sv_quick', 'quick_out'))
        if os.path.exists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        t0 = time.time()
        P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{data}" --maxlen 2048 --max-frames 30 --every 12 --workers {cpus}{lp}')
        P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{val}" --maxlen 2048 --max-frames 10 --holdout --workers {cpus}{lp}')
        print(f'[1/3] 자료(파일 12개 중 1개) 정상 {(time.time() - t0) / 60:.1f}분', flush=True)
        base = f'cd /d "{tools}" && "{py}" -u seq_train.py train "{data}" "{val}" "{out}" --log-every 20 --val-minutes 2 --val-n 64 --tok-budget {a.tok_budget}' + extra
        P.run_logged(base + ' --minutes 4 --plan-minutes 60' + (' --yield' if a.yield_ else ''), out)
        print('[2/3] 4분 학습 정상 — 위 줄의 걸음 수·GPU 메모리로 본 학습 속도를 계산', flush=True)
        P.run_logged(base + ' --minutes 1', out)
        print('[3/3] 이어하기 정상', flush=True)
        if a.rclone:
            print('Drive 올리기', '정상' if upload(a.rclone, out, drive, ['log.jsonl', 'train_console.txt']) else '실패', drive, flush=True)
        print(f'빠른 시험 끝 {(time.time() - t_start) / 60:.1f}분. 이 창 아래쪽을 사진으로 보내 주세요.', flush=True)
        return
    data, val = os.path.join(a.root, 'sd'), os.path.join(a.root, 'sv')
    out = os.path.join(a.root, f'out_{a.run}')
    os.makedirs(out, exist_ok=True)
    if a.rclone and not os.path.exists(os.path.join(out, 'ckpt.pt')):   # 다른 PC에서 하던 것도 이어서
        P.sh(f'"{a.rclone}" copy "{drive}" "{out}" --include ckpt.pt --include best.pt --include log.jsonl', check=False)
        if os.path.exists(os.path.join(out, 'ckpt.pt')):
            print('Drive의 이전 저장본에서 이어서', flush=True)
    t0 = time.time()
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{data}" --maxlen 2048 --max-frames 300 --aug 1 --workers {cpus}{lp}')
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{val}" --maxlen 2048 --max-frames 40 --holdout --workers {cpus}{lp}')
    shv = os.path.join(a.root, 'ss')   # 위치 시험: 학습 파일 10개 중 1개에 학습에 없던 고정 이동(GPT 3차)
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{shv}" --maxlen 2048 --max-frames 8 --every 10 --fixed 6,4,1.05 --workers {cpus}{lp}')
    print(f'자료 {(time.time() - t0) / 60:.1f}분', flush=True)
    left = a.hours * 60 - (time.time() - t_start) / 60 - 12   # 자료 읽기(몇 분)·마무리 올리기 몫
    if left < 5:
        print('남은 시간이 없어 학습을 건너뜀(자료는 만들어 둠 — 다음 실행 때 바로 학습)', flush=True)
        return
    stop = threading.Event()
    up = None
    if a.rclone:
        up = threading.Thread(target=uploader, args=(out, a.rclone, drive, stop), daemon=True)
        up.start()
    plan = a.plan_hours * 60   # 0이면 seq_train이 처음엔 이번 실행 시간, 이어할 땐 이번 실행만큼 늘림
    cmd = (f'cd /d "{tools}" && "{py}" -u seq_train.py train "{data}" "{val}" "{out}" --minutes {left:.0f} --plan-minutes {plan:.0f}'
           f' --tok-budget {a.tok_budget} --shift-val "{shv}"' + (' --yield' if a.yield_ else '') + extra)
    try:
        P.run_logged(cmd, out)
    finally:
        stop.set()
        if up is not None:
            up.join(timeout=600)
        for f in ('seq_train.py', 'sfa_tokens.py'):
            shutil.copy(os.path.join(tools, f), out)
        if a.rclone:
            ok = upload(a.rclone, out, drive, KEEP)
            print('Drive에 올림:' if ok else 'Drive 올리기 실패(zip 사용):', drive, flush=True)
        import zipfile
        zdir = os.environ.get('AISFA_ZIP_DIR') or os.path.join(os.path.expanduser('~'), 'Desktop')
        with zipfile.ZipFile(os.path.join(zdir, f'seq_{a.run}.zip'), 'w') as z:
            for k in KEEP:
                if os.path.exists(os.path.join(out, k)):
                    z.write(os.path.join(out, k), k)
        print(f'seq_{a.run}.zip 도 만듦:', zdir, '끝.', flush=True)


if __name__ == '__main__':
    main()
