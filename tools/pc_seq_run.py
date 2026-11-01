#!/usr/bin/env python3
"""PC에서 재설계 학습(영상 → 스파 문장, 2026-10-30, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md): 자료 → 학습 → 15분마다 Drive 저장 → 다음 실행 때 이어서.
pc_seq_*.bat이 설치를 마친 뒤 부른다. Drive: gdrive:AI-sfa/02_분석자료/seq/<run>/ 에 ckpt.pt·best.pt·log.jsonl·train_console.txt.
Drive 연결·절전 막기·화면 기록·올리기는 pc_vec_run.py의 것을 그대로 쓴다.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pc_vec_run as P  # noqa: E402
import ckpt_files  # noqa: E402

DRIVE_BASE = 'gdrive:AI-sfa/02_분석자료/seq'
HIRES = (1920, 1280, 854)   # 해상도 단계 자료 폭(kaggle_seq_worker.HIRES와 같게)
KEEP = ['ckpt.pt', 'best.pt', 'log.jsonl', 'train_console.txt', 'seq_train.py', 'sfa_tokens.py']
SHEETS = 'judge_sheet_*.png'   # 판정 고정 그림 시트(11-01)


def upload(rclone, out, drive, names):
    inc = ' '.join(f'--include "{k}"' for k in names)
    return subprocess.run(f'"{rclone}" copy "{out}" "{drive}" {inc}', shell=True).returncode == 0


def uploader(out, rclone, drive, stop, every=900):
    while not stop.wait(every):
        if os.path.exists(os.path.join(out, 'ckpt.pt')):
            ok = upload(rclone, out, drive, ['ckpt.pt', 'best.pt', 'log.jsonl', 'train_console.txt', SHEETS])
            print(time.strftime('%H:%M'), 'Drive 중간 저장', '정상' if ok else '실패', flush=True)


def last_step(out):
    """출력 폴더 log.jsonl 마지막 기록의 걸음 수(없으면 None)."""
    p = os.path.join(out, 'log.jsonl')
    if not os.path.exists(p):
        return None
    lines = [x for x in open(p, encoding='utf-8').read().splitlines() if x.strip()]
    return json.loads(lines[-1]).get('step') if lines else None


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
    ap.add_argument('--no-init-encoder', action='store_true', help='이전 픽셀 지도 모델 인코더 없이 ImageNet에서 출발')
    ap.add_argument('--no-stages', action='store_true', help='해상도 단계(1080→720→480→360) 없이 360만')
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
        P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{data}" --maxlen 2048 --max-frames 30 --every 12 --synth 0.3 --workers {cpus}{lp}')
        P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{val}" --maxlen 2048 --max-frames 10 --holdout --workers {cpus}{lp}')
        st = ''
        if not a.no_stages:   # 4분은 계획 60분의 첫 단계(1080, 20%) 안 → 가장 무거운 1080의 속도·메모리를 잰다
            hi = [os.path.join(a.root, f'sd_quick{r}') for r in HIRES]
            for r, d in zip(HIRES, hi):
                P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{d}" --W {r} --video --maxlen 2048 --max-frames 30 --every 12 --synth 0.3 --workers {cpus}{lp}')
            st = ' --stages "' + ','.join(hi) + '"'
        print(f'[1/3] 자료(파일 12개 중 1개) 정상 {(time.time() - t0) / 60:.1f}분', flush=True)
        base = (f'cd /d "{tools}" && "{py}" -u seq_train.py train "{data}" "{val}" "{out}" --log-every 20 --val-minutes 2 --val-n 64 --tok-budget {a.tok_budget}'
                + st + extra)
        # 빠른 시험의 시간은 벽시계(자료·모델 준비 포함). 마지막 평가 몫을 작게 주지 않으면 기본 20분 몫 때문에 0걸음으로 끝난다(GPT 코드 검토 I-04)
        quick = ' --final-reserve-min 0.5 --gen-minutes 0 --val-n 16'
        P.run_logged(base + quick + ' --minutes 4 --plan-minutes 60' + (' --yield' if a.yield_ else ''), out)
        s1 = last_step(out)
        if not s1:
            raise SystemExit(f'[2/3] 실패: 4분 동안 학습 걸음 0 — train_console.txt 확인(걸음 {s1})')
        print(f'[2/3] 4분 학습 정상 — {s1}걸음. 위 줄의 걸음 수·GPU 메모리로 본 학습 속도를 계산', flush=True)
        P.run_logged(base + quick + ' --minutes 2', out)
        s2 = last_step(out)
        if not s2 or s2 <= s1:
            raise SystemExit(f'[3/3] 실패: 이어하기에서 걸음이 늘지 않음({s1} → {s2})')
        print(f'[3/3] 이어하기 정상 — {s1} → {s2}걸음', flush=True)
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
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{data}" --maxlen 2048 --compose 40000 --workers {cpus}{lp}')   # 조합 문제(11-01)
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{val}" --maxlen 2048 --max-frames 40 --holdout --workers {cpus}{lp}')
    shv = os.path.join(a.root, 'ss')   # 위치 시험: 학습 파일 10개 중 1개에 학습에 없던 고정 이동(GPT 3차)
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{shv}" --maxlen 2048 --max-frames 8 --every 10 --fixed 6,4,1.05 --workers {cpus}{lp}')
    vkd = os.path.join(a.root, 'sc')   # 실제·조합 고정 검증(11-01 GPT 1라운드 D)
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{vkd}" --maxlen 2048 --compose 1200 --seed 7777 --workers {cpus}{lp}')
    sj = os.path.join(a.root, 'sj')   # 판정 자료(11-01, 판정 기준 §2): 평가 목록 고정 장 × 이동 4방향 + 단계 해상도 비교용 몇 장
    P.sh(f'cd /d "{tools}" && "{py}" -u seq_judge.py build "{sj}"')
    st = ''
    if not a.no_stages:   # 해상도 단계(사용자 10-29·10-31): 1080 → 720 → 480 → 360. 영상(mp4)으로 저장해 작다(합계 약 0.5GB)
        hi = [os.path.join(a.root, f'sd{r}') for r in HIRES]
        for r, d in zip(HIRES, hi):
            P.sh(f'cd /d "{tools}" && "{py}" -u seq_data.py "{d}" --W {r} --video --maxlen 2048 --compose 40000 --workers {cpus}{lp}')
        st = ' --stages "' + ','.join(hi) + '"'
    print(f'자료 {(time.time() - t0) / 60:.1f}분', flush=True)
    deadline = t_start + a.hours * 3600 - 5 * 60   # 절대 마감(Kaggle 작업자와 같은 방식, 11-01) — 마무리 올리기 5분. 학습기가 마지막 평가 몫을 남긴다
    left = (deadline - time.time()) / 60
    if left < 5:
        print('남은 시간이 없어 학습을 건너뜀(자료는 만들어 둠 — 다음 실행 때 바로 학습)', flush=True)
        return
    stop = threading.Event()
    up = None
    if a.rclone:
        up = threading.Thread(target=uploader, args=(out, a.rclone, drive, stop), daemon=True)
        up.start()
    enc = ''
    if not a.no_init_encoder and not os.path.exists(os.path.join(out, 'ckpt.pt')):   # 새로 시작할 때만 인코더 이어 쓰기(10-31)
        ef = os.path.join(a.root, 'vec_encoder.pt')
        if a.rclone and not os.path.exists(ef):
            P.sh(f'"{a.rclone}" copyto "{DRIVE_BASE}/vec_encoder.pt" "{ef}"', check=False)
        if not os.path.exists(ef):
            raise SystemExit(f'인코더 파일 없음({DRIVE_BASE}/vec_encoder.pt) — 사진을 보내 주세요(또는 --no-init-encoder)')
        enc = f' --init-encoder "{ef}"'
    plan = a.plan_hours * 60   # 학습 진행 분(읽기·평가 제외, 11-01). 0이면 seq_train이 처음엔 이번 실행 시간, 이어할 땐 이번 실행만큼 늘림
    cmd = (f'cd /d "{tools}" && "{py}" -u seq_train.py train "{data}" "{val}" "{out}" --minutes {left:.0f} --deadline {deadline:.0f} --plan-minutes {plan:.0f}'
           f' --tok-budget {a.tok_budget} --shift-val "{shv}" --judge "{sj}" --val-kind "{vkd}" --gen-minutes 20' + st + enc + (' --yield' if a.yield_ else '') + extra)
    try:
        P.run_logged(cmd, out)
    finally:
        stop.set()
        if up is not None:
            up.join(timeout=600)
        for f in ('seq_train.py', 'sfa_tokens.py'):
            shutil.copy(os.path.join(tools, f), out)
        if ckpt_files.promote(out) == 'locked':   # 예비 저장본만 최신이면 본 파일로(GPT 재확인 R-05)
            print('경고: 출력 폴더의 ckpt.pt.fallback이 최신이다 — 잠금을 풀고 python tools/ckpt_files.py 폴더 로 옮긴 뒤 올릴 것', flush=True)
        if a.rclone:
            ok = upload(a.rclone, out, drive, KEEP + [SHEETS])
            print('Drive에 올림:' if ok else 'Drive 올리기 실패(zip 사용):', drive, flush=True)
        import zipfile
        zdir = os.environ.get('AISFA_ZIP_DIR') or os.path.join(os.path.expanduser('~'), 'Desktop')
        with zipfile.ZipFile(os.path.join(zdir, f'seq_{a.run}.zip'), 'w') as z:
            for k in KEEP + sorted(os.path.basename(x) for x in glob.glob(os.path.join(out, SHEETS))):
                if os.path.exists(os.path.join(out, k)):
                    z.write(os.path.join(out, k), k)
        print(f'seq_{a.run}.zip 도 만듦:', zdir, '끝.', flush=True)


if __name__ == '__main__':
    main()
