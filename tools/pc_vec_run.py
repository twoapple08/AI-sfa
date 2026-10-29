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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from vec_data import done_ok  # noqa: E402

DRIVE_BASE = 'gdrive:AI-sfa/02_분석자료/vec'
DRIVE = DRIVE_BASE + '/pc'  # main()에서 --run으로 바꾼다(1차 pc, 2차 pc2 …)


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
            r = subprocess.run(f'"{rclone}" copy "{out}" "{DRIVE}" --include "ckpt.pt" --include "best.pt" --include "log.jsonl" --include "train_console.txt"', shell=True)
            print(time.strftime('%H:%M'), 'Drive 중간 저장', '정상' if r.returncode == 0 else f'실패({r.returncode})', flush=True)


def ensure_drive(rclone, path):
    """Drive 폴더를 만든다. 안 되면(1차 뒤 접근 해제 등) 한 번 재연결(브라우저가 열림) 후 다시. 그래도 안 되면 '' — 시작 가중치가 필요하면 그 뒤에서 멈춘다."""
    def mk():
        return subprocess.run(f'"{rclone}" mkdir "{path}"', shell=True, capture_output=True).returncode == 0
    if mk():
        print('Drive 연결 정상:', path, flush=True)
        return rclone
    print('Drive 연결 안 됨 → 다시 로그인(브라우저에서 허용을 눌러 주세요)', flush=True)
    subprocess.run(f'"{rclone}" config reconnect gdrive: --auto-confirm', shell=True, stdout=subprocess.DEVNULL)  # 화면에 토큰이 나오지 않게
    if mk():
        print('Drive 다시 연결됨:', path, flush=True)
        return rclone
    print('Drive 연결 실패 — Drive 저장 없이 진행(시작 가중치가 필요하면 곧 멈춤)', flush=True)
    return ''


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
    print(f'[확인 1/4] 자료 만들기 정상 ({(time.time() - t0) / 60:.1f}분)', flush=True)
    sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --smoke --workers 2')  # 본 학습과 같은 배치(메모리 부족이면 조각을 줄여 계속 — 그 장치도 같이 확인)
    print('[확인 2/4] 짧은 시험 정상', flush=True)
    t1 = time.time()
    sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --hours 0.05 --workers 2')
    print(f'[확인 3/4] 3분 학습 정상 ({(time.time() - t1) / 60:.1f}분). 위 기록의 step 수로 속도를 잰다', flush=True)
    # 이어하기 시험(GPT 3차): 방금 저장된 ckpt.pt에서 이어서 짧게 — '이어서: 진행 …%' 줄이 나와야 함
    sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --hours 0.03 --workers 2 --resume "{os.path.join(out, "ckpt.pt")}"')
    print('[확인 4/4] 이어하기 정상', flush=True)
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
    ap.add_argument('--run', default='pc2', help='학습 이름 = Drive 폴더·이 PC 출력 폴더(1차 pc, 2차 pc2). 같은 이름이면 이어서')
    ap.add_argument('--init-from', default='pc', help='처음 시작할 때 가중치를 받아 올 이전 학습 이름(그 폴더의 best.pt, 없으면 best_fallback_last.pt). 빈 값이면 처음부터')
    ap.add_argument('--yield', dest='yield_', action='store_true', help='양보 모드(4060 PC, 사용자 10-29): 게임·클립 스튜디오와 같이 돌아도 되게 — 낮은 우선순위·작업자 절반·학습은 vec_train --yield')
    ap.add_argument('--check', action='store_true', help='빠른 확인(사용자 10-29, 1050 Ti 1시간): 파일 12개·장 6개·1080/360만, 짧은 시험(배치 1) + 3분 학습, Drive 올리기 시험')
    a = ap.parse_args()
    global DRIVE
    DRIVE = f'{DRIVE_BASE}/{a.run}'
    if a.rclone:  # Drive 폴더 만들기·재연결은 여기서(bat에 한글 경로를 두면 cmd가 줄을 잘못 읽었다, 4060 PC 10-29)
        a.rclone = ensure_drive(a.rclone, DRIVE)
    t_start = time.time()  # PC 사용 시간 계산의 시작(이전 저장본 받기도 포함)
    keep_awake()
    if a.check:
        return check(a)
    tools = os.path.join(a.root, 'repo', 'tools')
    data = os.path.join(a.root, 'vd')
    out = os.path.join(a.root, 'vec_out' if a.run == 'pc' else f'vec_out_{a.run}')  # 학습마다 따로(1차 ckpt.pt를 이어받아 '이미 100%'로 끝나지 않게)
    os.makedirs(out, exist_ok=True)
    py = sys.executable
    cpus = os.cpu_count() or 4
    if a.yield_:
        cpus = max(2, cpus // 2)  # 자료 만들기·읽기 작업자를 절반으로(게임 몫)
    yf = ' --low-priority' if a.yield_ else ''
    # 이어서: Drive에 이전 저장본이 있으면 받는다
    resume = ''
    if os.path.exists(os.path.join(out, 'ckpt.pt')):  # 이 PC에 남은 저장본도 이어서(GPT 2차 15)
        resume = os.path.join(out, 'ckpt.pt')
    if a.rclone and not resume:
        sh(f'"{a.rclone}" copy "{DRIVE}" "{out}" --include ckpt.pt --include best.pt --include log.jsonl', check=False)
        if os.path.exists(os.path.join(out, 'ckpt.pt')):  # 모델·최적화기·진행·최고 점수가 한 파일(GPT 검토 15·16)
            resume = os.path.join(out, 'ckpt.pt')
            print('이전 저장본에서 이어서(ckpt.pt)', flush=True)
    init = ''
    if not resume and a.init_from:  # 2차 학습: 1차 최고 모델의 가중치에서 출발. 실패하면 학습 전에 멈춘다(GPT 5차 2: 조용히 처음부터 하지 않게)
        ip = os.path.join(out, 'init.pt')
        if os.path.exists(ip):
            os.remove(ip)  # 예전에 남은 파일을 '받기 성공'으로 착각하지 않게
        src = f'{DRIVE_BASE}/{a.init_from}'
        for nm in ('best.pt', 'best_fallback_last.pt') if a.rclone else ():
            r = sh(f'"{a.rclone}" copyto "{src}/{nm}" "{ip}"', check=False)
            if r.returncode == 0 and os.path.exists(ip):
                try:
                    import torch
                    sd = torch.load(ip, map_location='cpu', weights_only=False)
                    assert isinstance(sd, dict) and len(sd) > 10
                except Exception as e:
                    print('받은 시작 가중치를 열 수 없음:', nm, e, flush=True)
                    os.remove(ip)
                    continue
                init = ip
                print('시작 가중치:', a.init_from, nm, flush=True)
                break
        if not init:
            raise SystemExit(f'1차 모델({src}/best.pt)을 받지 못해 멈춤. Drive 연결을 확인하거나, 처음부터 하려면: pc_vec_5060.bat(또는 4060) {a.hours} scratch')
    t0 = time.time()
    for res in ('1920', '1280', '854', '640'):
        d = os.path.join(data, res)
        rep = 1 if res in ('1920', '1280') else a.repeat  # 큰 화질은 만드는 데 오래 걸려 1번(GPT 검토 14)
        if done_ok(d, res=int(res), repeat=rep, max_frames=24, limit=0, seed=int(res), synth=0.3):  # 같은 설정으로 다 만든 표시가 있을 때만 건너뜀(GPT 2차 17)
            continue
        t1 = time.time()
        sh(f'cd /d "{tools}" && "{py}" -u vec_data.py "{d}" --res {res} --repeat {rep} --max-frames 24 --workers {cpus} --seed {res}{yf}')
        print(f'자료 {res}: {(time.time() - t1) / 60:.1f}분', flush=True)
        if res == '1920' and not resume:  # 1080 자료만으로 짧은 시험 먼저(오류면 여기서 멈춤)
            sh(f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{os.path.join(a.root, "smoke")}" --smoke --workers 2')
    print(f'자료 {(time.time() - t0) / 60:.1f}분', flush=True)
    # 남은 시간 = 요청 시간 − 지금까지(저장본 받기·자료 만들기) − 마무리(올리기·zip) 6분. 모자라면 학습하지 않고 종료(GPT 2차)
    left = a.hours - (time.time() - t_start) / 3600 - 0.1
    if left < 0.1:
        print('남은 시간이 없어 학습을 건너뜀(자료는 만들어 둠 — 다음 실행 때 바로 학습)', flush=True)
        return
    stop = threading.Event()
    up = None
    if a.rclone:
        up = threading.Thread(target=uploader, args=(out, a.rclone, stop), daemon=True)
        up.start()
    cmd = f'cd /d "{tools}" && "{py}" -u vec_train.py --data "{data}" --out "{out}" --hours {left:.2f} --workers {min(6, max(2, cpus - 2))}'
    if a.yield_:
        cmd += ' --yield'
    if resume:
        cmd += f' --resume "{resume}"'
    elif init:
        cmd += f' --init "{init}"'
    try:
        # 학습 화면 출력을 파일(train_console.txt)에도 남겨 Drive로 — 사람이 없을 때 멈춘 이유를 알 수 있게(4060 2차 첫 시도: 원인 모를 종료)
        print('$', cmd, flush=True)
        con = os.path.join(out, 'train_console.txt')
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')  # 파이프로 받을 때 한글이 cp949로 깨지지 않게
        pr = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env)
        for line in pr.stdout:
            print(line, end='', flush=True)
            with open(con, 'a', encoding='utf-8') as f:  # 줄마다 열고 닫기(열어 둔 파일은 Windows가 크기를 늦게 갱신해 올리기가 건너뜀)
                f.write(line)
        if pr.wait() != 0:
            raise subprocess.CalledProcessError(pr.returncode, cmd)
    finally:  # 학습이 오류로 끝나도 마지막 저장본은 올린다(GPT 검토 16)
        stop.set()
        if up is not None:
            up.join(timeout=600)  # 중간 올리기가 끝난 뒤 마지막 올리기(겹치지 않게)
            if up.is_alive():
                print('중간 올리기가 아직 끝나지 않음 — 마지막 올리기와 겹칠 수 있음(파일은 rclone이 덮어씀)', flush=True)
        shutil.copy(os.path.join(tools, 'vec_train.py'), out)
        keep = ['ckpt.pt', 'best.pt', 'best_fallback_last.pt', 'log.jsonl', 'vec_train.py', 'train_console.txt']  # 이어하기·결과에 필요한 것만(단계별 저장본까지 올리면 약 1GB)
        if a.rclone:
            inc = ' '.join(f'--include "{k}"' for k in keep)
            r = subprocess.run(f'"{a.rclone}" copy "{out}" "{DRIVE}" {inc}', shell=True)
            print('Drive에 올림:' if r.returncode == 0 else 'Drive 올리기 실패(바탕화면 zip 사용):', DRIVE, flush=True)
        import zipfile
        zdir = os.environ.get('AISFA_ZIP_DIR') or os.path.join(os.path.expanduser('~'), 'Desktop')  # 4060 PC: C 여유가 적어 W에(사용자 10-29)
        with zipfile.ZipFile(os.path.join(zdir, 'vec_out.zip'), 'w') as z:
            for k in keep:
                if os.path.exists(os.path.join(out, k)):
                    z.write(os.path.join(out, k), k)
        print('vec_out.zip 도 만듦:', zdir, '끝.', flush=True)


if __name__ == '__main__':
    main()
