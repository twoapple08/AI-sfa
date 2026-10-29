#!/usr/bin/env python3
"""PC방(RTX 5060)에서 영상 → SFA 딥러닝: 자료 → 짧은 시험 → 학습, 15분마다 Drive로 중간 저장, 다음 실행 때 이어서 (2026-10-29).
pc_vec.bat이 설치를 마친 뒤 부른다. 사용자 10-29: 자리를 비울 수 있으니 Drive 자동 올리기(2번), 연결 정보는 지우지 않음.
Drive: gdrive:AI-sfa/02_분석자료/vec/pc/ 에 ckpt.pt(모델·최적화기·진행·최고 점수 한 파일)·best.pt·log.jsonl.
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import threading
import time

DRIVE = 'gdrive:AI-sfa/02_분석자료/vec/pc'


def sh(cmd, check=True):
    print('$', cmd, flush=True)
    return subprocess.run(cmd, shell=True, check=check)


def keep_awake():
    """Windows 절전 막기(관리자 권한 필요 없음, 이 프로그램이 도는 동안만)."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        print('절전 막기 켬', flush=True)
    except Exception as e:
        print('절전 막기 실패(무시):', e, flush=True)


def uploader(out, rclone, stop, every=900):
    while not stop.wait(every):
        if os.path.exists(os.path.join(out, 'ckpt.pt')):
            subprocess.run(f'"{rclone}" copy "{out}" "{DRIVE}" --include "ckpt.pt" --include "best.pt" --include "log.jsonl"', shell=True)
            print(time.strftime('%H:%M'), 'Drive 중간 저장', flush=True)


def check(a):
    tools = os.path.join(a.root, 'repo', 'tools')
    data = os.path.join(a.root, 'vd_check')
    out = os.path.join(a.root, 'check_out')
    py = sys.executable
    cpus = os.cpu_count() or 4
    t0 = time.time()
    import torch
    print('GPU', torch.cuda.get_device_name(0), round(torch.cuda.get_device_properties(0).total_memory / 2**30, 1), 'GB', flush=True)
    for res in ('1920', '640'):
        sh(f'cd /d "{tools}" && "{py}" -u vec_data.py "{os.path.join(data, res)}" --res {res} --limit 12 --max-frames 6 --workers {cpus} --seed {res}')
    print(f'[확인 1/3] 자료 만들기 정상 ({(time.time() - t0) / 60:.1f}분)', flush=True)
    sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --smoke --workers 2')  # 본 학습과 같은 배치(메모리 부족이면 조각을 줄여 계속 — 그 장치도 같이 확인)
    print('[확인 2/3] 짧은 시험 정상', flush=True)
    t1 = time.time()
    sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --hours 0.05 --workers 2')
    print(f'[확인 3/3] 3분 학습 정상 ({(time.time() - t1) / 60:.1f}분). 위 기록의 step 수로 속도를 잰다', flush=True)
    if a.rclone:
        r = subprocess.run(f'"{a.rclone}" copy "{out}" "{DRIVE}_check" --include "*.json*"', shell=True)
        print('Drive 올리기', '정상' if r.returncode == 0 else '실패', flush=True)
    print(f'빠른 확인 끝 {(time.time() - t0) / 60:.1f}분. 이 창 아래쪽을 사진으로 보내 주세요.', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=r'C:\aisfa\vec')
    ap.add_argument('--hours', type=float, default=1.2)
    ap.add_argument('--repeat', type=int, default=2)
    ap.add_argument('--rclone', default='')
    ap.add_argument('--check', action='store_true', help='빠른 확인(사용자 10-29, 1050 Ti 1시간): 파일 12개·장 6개·1080/360만, 짧은 시험(배치 1) + 3분 학습, Drive 올리기 시험')
    a = ap.parse_args()
    keep_awake()
    if a.check:
        return check(a)
    tools = os.path.join(a.root, 'repo', 'tools')
    data = os.path.join(a.root, 'vd')
    out = os.path.join(a.root, 'vec_out')
    os.makedirs(out, exist_ok=True)
    py = sys.executable
    cpus = os.cpu_count() or 4
    # 이어서: Drive에 이전 저장본이 있으면 받는다
    resume = ''
    if a.rclone:
        sh(f'"{a.rclone}" copy "{DRIVE}" "{out}" --include ckpt.pt --include best.pt --include log.jsonl', check=False)
        if os.path.exists(os.path.join(out, 'ckpt.pt')):  # 모델·최적화기·진행·최고 점수가 한 파일(GPT 검토 15·16)
            resume = os.path.join(out, 'ckpt.pt')
            print('이전 저장본에서 이어서(ckpt.pt)', flush=True)
    t0 = time.time()
    for res in ('1920', '1280', '854', '640'):
        d = os.path.join(data, res)
        if os.path.exists(os.path.join(d, '_done.json')):  # 다 만든 표시가 있을 때만 건너뜀(GPT 검토 17)
            continue
        rep = 1 if res in ('1920', '1280') else a.repeat  # 큰 화질은 만드는 데 오래 걸려 1번(GPT 검토 14)
        t1 = time.time()
        sh(f'cd /d "{tools}" && "{py}" -u vec_data.py "{d}" --res {res} --repeat {rep} --max-frames 24 --workers {cpus} --seed {res}')
        print(f'자료 {res}: {(time.time() - t1) / 60:.1f}분', flush=True)
        if res == '1920' and not resume:  # 1080 자료만으로 짧은 시험 먼저(오류면 여기서 멈춤)
            sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{os.path.join(a.root, "smoke")}" --smoke --workers 2')
    print(f'자료 {(time.time() - t0) / 60:.1f}분', flush=True)
    stop = threading.Event()
    if a.rclone:
        threading.Thread(target=uploader, args=(out, a.rclone, stop), daemon=True).start()
    # 남은 시간 = 요청 시간 − 자료 만들기에 쓴 시간(자료가 오래 걸려도 PC 사용 시간을 넘지 않게)
    left = max(0.2, a.hours - (time.time() - t0) / 3600)
    cmd = f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --hours {left:.2f} --workers {min(6, max(2, cpus - 2))}'
    if resume:
        cmd += f' --resume "{resume}"'
    try:
        sh(cmd)
    finally:  # 학습이 오류로 끝나도 마지막 저장본은 올린다(GPT 검토 16)
        stop.set()
        shutil.copy(os.path.join(tools, 'vec_train.py'), out)
        if a.rclone:
            r = subprocess.run(f'"{a.rclone}" copy "{out}" "{DRIVE}" --exclude "*.tmp"', shell=True)
            print('Drive에 올림:' if r.returncode == 0 else 'Drive 올리기 실패(바탕화면 zip 사용):', DRIVE, flush=True)
        shutil.make_archive(os.path.join(os.path.expanduser('~'), 'Desktop', 'vec_out'), 'zip', out)
        print('바탕화면 vec_out.zip 도 만듦. 끝.', flush=True)


if __name__ == '__main__':
    main()
