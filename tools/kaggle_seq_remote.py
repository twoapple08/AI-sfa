#!/usr/bin/env python3
"""서버에서 Kaggle GPU 학습을 원격으로(2026-10-30, 사용자: 컴퓨터 없이 학습). kaggle CLI를 부른다.
인증: 환경 변수 KAGGLE_USERNAME + KAGGLE_KEY(kaggle.json의 key) 또는 KAGGLE_API_TOKEN(새 방식 토큰). 환경 설정의 비밀값, 출력하지 않는다.
  push     : kaggle_seq_worker.py에 설정을 넣어 비공개 스크립트 커널로 올리고 실행(GPU·인터넷 켬, ckpt 자료가 있으면 입력으로)
             --prebuilt: push-data가 만든 자료 커널 출력을 입력으로 붙여 자료 만들기 없이 바로 학습(GPU 시간 아끼기, 10-31)
  push-data: 자료만 만드는 CPU 커널 aisfa-seq-data(GPU 시간 0). 끝나면 status/wait/pull에 --data
  push-encoder 파일: 이전 픽셀 지도 모델 인코더(seq_train vec-encoder)를 비공개 자료 aisfa-vec-encoder로 → push가 새 학습 때 이어 씀
  status   : 커널 상태
  wait     : 끝날 때까지 기다림(10분 간격, 최대 13시간)
  pull     : 결과(out/ckpt.pt·best.pt·log.jsonl·train_console.txt) 받기
  save-ckpt: 받은 ckpt.pt·best.pt·log.jsonl을 비공개 자료 aisfa-seq-ckpt로 올림(다음 push가 이어서 학습)
  to-drive 폴더 학습이름  : 받은 결과를 Drive seq/학습이름 으로 → PC(pc_seq_*.bat, 같은 학습 이름)가 이어서(사용자 10-30)
  from-drive 학습이름 폴더: PC가 Drive에 올린 학습 상태를 받음 → save-ckpt 폴더 로 Kaggle이 이어서
  학습 상태 한 파일(ckpt.pt)에 모델·최적화기·진행이 다 있어 GPU가 바뀌어도 이어진다(fp16↔bf16 배율 상태는 seq_train이 처리)
사용: python kaggle_seq_remote.py push-data | wait --data | push --prebuilt [--minutes 690] [--plan-minutes 0] | wait | pull 폴더 | save-ckpt 폴더
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ckpt_files  # noqa: E402  같은 폴더(예비 저장본 정리, GPT 재확인 R-05)

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = 'aisfa-seq-train'
DATA_KERNEL = 'aisfa-seq-data'
ENCODER = 'aisfa-vec-encoder'   # 이전 픽셀 지도 모델 인코더(seq_train vec-encoder 결과, 10-31 이어 쓰기)
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


def ckpt_exists(u, name=CKPT):
    out = kg('datasets', 'list', '--mine', '-s', name, '--csv', check=False)
    return any(l.split(',')[0] == f'{u}/{name}' for l in out.splitlines())


def worker_src(cfg):
    """작업자 원본의 CONFIG 줄을 이 실행 설정으로 바꾼다(CONFIG는 두 줄 이상일 수 있다)."""
    src = open(os.path.join(HERE, 'kaggle_seq_worker.py'), encoding='utf-8').read()
    src, n = re.subn(r"^CONFIG = \{.*?\}$", lambda m: 'CONFIG = ' + repr(cfg), src, count=1, flags=re.M | re.S)
    assert n == 1, 'CONFIG 줄을 못 찾음'
    return src


def kernel_meta(u, kname, gpu):
    return dict(id=f'{u}/{kname}', title=kname, code_file='kernel.py', language='python', kernel_type='script',
                is_private=True, enable_gpu=gpu, enable_internet=True, dataset_sources=[], competition_sources=[], kernel_sources=[])


def push_kernel(d, kname, cfg):
    out = kg('kernels', 'push', '-p', d)
    shutil.rmtree(d)
    print(out, flush=True)
    if 'error' in out.lower() or 'successfully pushed' not in out.lower():   # CLI가 실패해도 반환 코드 0인 경우가 있다(10-30 주간 한도 거절)
        raise SystemExit('올리기 실패 — 위 메시지 확인')
    print('올림:', f'https://www.kaggle.com/code/{user()}/{kname}', '설정', cfg, flush=True)


def push(a):
    if not a.cpu and not a.gpu_ok:   # 규칙: 사용자 지시 없이 Kaggle GPU 금지 — 실수로 --cpu를 빠뜨려도 GPU가 돌지 않게(코드 검토 11-01)
        raise SystemExit('GPU 실행은 사용자 지시가 있을 때만: --gpu-ok를 붙이거나, CPU면 --cpu')
    u = user()
    cfg = dict(branch=a.branch, session_minutes=a.minutes, plan_minutes=a.plan_minutes, tok_budget=a.tok_budget, extra=a.extra, smoke=a.smoke,
               mode='train', prebuilt=a.prebuilt, prebuilt_any_code=a.prebuilt_any_code, stages=not a.no_stages,
               init_encoder=not a.no_init_encoder)
    src = worker_src(cfg)
    d = tempfile.mkdtemp(prefix='kseq_')
    open(os.path.join(d, 'kernel.py'), 'w', encoding='utf-8').write(src)
    kname = getattr(a, 'kernel_name', '') or KERNEL + ('-smoke' if a.smoke else '')
    if kname == KERNEL and getattr(a, 'kernel_name', ''):
        raise SystemExit('--kernel-name은 공식 커널과 다른 이름이어야 한다')
    meta = kernel_meta(u, kname, not a.cpu)
    if a.accel and not a.cpu:
        meta['machine_shape'] = a.accel
    if not a.fresh and not (a.smoke and a.ckpt == CKPT) and ckpt_exists(u, a.ckpt):   # 시험은 본 학습 자료를 붙이지 않는다
        meta['dataset_sources'] = [f'{u}/{a.ckpt}']
        print('이어하기 자료를 입력으로:', f'{u}/{a.ckpt}', flush=True)
    if not a.no_init_encoder:   # 새로 시작할 때 인코더 이어 쓰기(이어하기면 작업자·seq_train이 무시)
        if not ckpt_exists(u, ENCODER):
            raise SystemExit(f'인코더 자료 {ENCODER} 없음 — push-encoder 먼저(또는 --no-init-encoder)')
        meta['dataset_sources'] = meta['dataset_sources'] + [f'{u}/{ENCODER}']
    if a.prebuilt:   # 자료 커널 출력을 입력으로(작업자가 판·설정·코드를 확인하고, 다르면 학습 전에 멈춘다)
        meta['kernel_sources'] = [f'{u}/{DATA_KERNEL}' + ('-smoke' if a.smoke else '')]
        print('미리 만든 자료를 입력으로:', meta['kernel_sources'][0], flush=True)
    elif not a.cpu:
        print('주의: --prebuilt 없이 GPU 실행 — 자료 만들기에 GPU 시간이 든다', flush=True)
    json.dump(meta, open(os.path.join(d, 'kernel-metadata.json'), 'w'), ensure_ascii=False, indent=1)
    push_kernel(d, kname, cfg)


def push_encoder(a):
    """인코더 파일을 비공개 자료로(있으면 새 판)."""
    u = user()
    d = tempfile.mkdtemp(prefix='kenc_')
    shutil.copy(a.file, os.path.join(d, 'vec_encoder.pt'))
    json.dump(dict(title=ENCODER, id=f'{u}/{ENCODER}', licenses=[dict(name='CC0-1.0')]), open(os.path.join(d, 'dataset-metadata.json'), 'w'))
    if ckpt_exists(u, ENCODER):
        print(kg('datasets', 'version', '-p', d, '-m', time.strftime('%Y-%m-%d %H:%M'), '-q'))
    else:
        print(kg('datasets', 'create', '-p', d, '-q'))   # 기본 비공개
    shutil.rmtree(d)
    print('인코더 자료 올림:', f'{u}/{ENCODER}', flush=True)


def push_data(a):
    """자료만 만드는 CPU 커널(GPU 끔). 출력 sd·sv·ss + data_info.json을 push --prebuilt가 입력으로 붙인다."""
    u = user()
    cfg = dict(branch=a.branch, smoke=a.smoke, mode='data', stages=not a.no_stages)
    d = tempfile.mkdtemp(prefix='kdata_')
    open(os.path.join(d, 'kernel.py'), 'w', encoding='utf-8').write(worker_src(cfg))
    kname = DATA_KERNEL + ('-smoke' if a.smoke else '')
    json.dump(kernel_meta(u, kname, False), open(os.path.join(d, 'kernel-metadata.json'), 'w'), ensure_ascii=False, indent=1)
    push_kernel(d, kname, cfg)


def kname_of(a):
    if getattr(a, 'kernel_name', ''):
        return a.kernel_name
    return (DATA_KERNEL if getattr(a, 'data', False) else KERNEL) + ('-smoke' if getattr(a, 'smoke', False) else '')


def status(a=None):
    out = kg('kernels', 'status', f'{user()}/{kname_of(a)}')
    print(out, flush=True)
    return out


def wait(a):
    t0 = time.time()
    while time.time() - t0 < a.hours * 3600:
        out = status(a).lower()
        if any(k in out for k in ('complete', 'error', 'cancel')):
            return
        time.sleep(600)
    print('기다림 한도 넘음', flush=True)


def data_check(a):
    """자료 커널의 data_info.json·done.json만 받아 정합성 요약을 보인다(11-01: 출력 파일이 수천 개라 기본 20개씩 목록을 받다
    요청 제한에 걸렸다 — 한 쪽 200개로 요청 수를 1/10로, 제한에 걸리면 2·4·8분 기다려 다시)."""
    os.makedirs(a.dir, exist_ok=True)
    for i, wait_s in enumerate((0, 120, 240, 480)):
        time.sleep(wait_s)
        out = kg('kernels', 'output', f'{user()}/{DATA_KERNEL}', '-p', a.dir, '--file-pattern', r'(^|/)(data_info|done)\.json$',
                 '--page-size', '200', check=False)
        if 'rate limit' not in out.lower():
            break
        print(f'요청 제한 — {(wait_s or 60) * 2 // 60}분 뒤 다시', flush=True)
    for p in sorted(glob.glob(os.path.join(a.dir, '**', 'done.json'), recursive=True)):
        d = json.load(open(p, encoding='utf-8'))
        print(os.path.basename(os.path.dirname(p)), d.get('frames'), '판', d.get('version'), (d.get('check') or {}).get('check'), flush=True)
    p = os.path.join(a.dir, 'data_info.json')
    if os.path.exists(p):
        i_ = json.load(open(p, encoding='utf-8'))
        print('커밋', i_.get('commit', '')[:8], '분', i_.get('minutes'), flush=True)


def pull(a):
    os.makedirs(a.dir, exist_ok=True)
    print(kg('kernels', 'output', f'{user()}/{kname_of(a)}', '-p', a.dir))
    for f in ('out/run.json', 'out/log.jsonl', 'data_info.json'):
        p = os.path.join(a.dir, f)
        if os.path.exists(p):
            print(f, open(p, encoding='utf-8').read()[-1500:], flush=True)


def save_ckpt(a):
    u = user()
    src = os.path.join(a.dir, 'out')
    if ckpt_files.promote(src) == 'locked':   # 예비 저장본이 최신이면 본 파일로(GPT 재확인 R-05)
        raise SystemExit(f'{src}/ckpt.pt.fallback을 본 파일로 옮기지 못함 — 잠금을 풀고 다시')
    if not os.path.exists(os.path.join(src, 'ckpt.pt')):
        raise SystemExit(f'{src}/ckpt.pt 없음 — pull 먼저')
    d = tempfile.mkdtemp(prefix='kckpt_')
    for f in ('ckpt.pt', 'best.pt', 'log.jsonl'):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), d)
    json.dump(dict(title=a.ckpt, id=f'{u}/{a.ckpt}', licenses=[dict(name='CC0-1.0')]), open(os.path.join(d, 'dataset-metadata.json'), 'w'))
    if ckpt_exists(u, a.ckpt):
        print(kg('datasets', 'version', '-p', d, '-m', time.strftime('%Y-%m-%d %H:%M'), '-q'))
    else:
        print(kg('datasets', 'create', '-p', d, '-q'))   # 기본 비공개
    shutil.rmtree(d)
    print('이어하기 자료 올림:', f'{u}/{a.ckpt}', flush=True)


DRIVE = 'gdrive:AI-sfa/02_분석자료/seq'


def to_drive(a):
    src = os.path.join(a.dir, 'out') if os.path.exists(os.path.join(a.dir, 'out')) else a.dir
    if ckpt_files.promote(src) == 'locked':   # GPT 재확인 R-05
        raise SystemExit(f'{src}/ckpt.pt.fallback을 본 파일로 옮기지 못함 — 잠금을 풀고 다시')
    inc = ' '.join(f'--include "{f}"' for f in ('ckpt.pt', 'best.pt', 'log.jsonl'))
    r = subprocess.run(f'rclone copy "{src}" "{DRIVE}/{a.run}" {inc}', shell=True)
    print('Drive에 올림:' if r.returncode == 0 else 'Drive 올리기 실패:', f'{DRIVE}/{a.run}', flush=True)


def from_drive(a):
    dst = os.path.join(a.dir, 'out')
    os.makedirs(dst, exist_ok=True)
    inc = ' '.join(f'--include "{f}"' for f in ('ckpt.pt', 'best.pt', 'log.jsonl'))
    r = subprocess.run(f'rclone copy "{DRIVE}/{a.run}" "{dst}" {inc}', shell=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(dst, 'ckpt.pt'))
    print('Drive에서 받음:' if ok else 'Drive 받기 실패:', dst, flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('push')
    p.add_argument('--branch', default='claude/new-session-gknz4t')
    p.add_argument('--minutes', type=float, default=690, help='Kaggle 한 번 실행 시간(GPU 최대 12시간 안)')
    p.add_argument('--plan-minutes', type=float, default=0)
    p.add_argument('--tok-budget', type=int, default=12288)
    p.add_argument('--extra', default='', help='seq_train 옵션 덧붙이기')
    p.add_argument('--accel', default='NvidiaTeslaT4', help='machine_shape(빈 값이면 기본 GPU)')
    p.add_argument('--fresh', action='store_true', help='이어하기 자료를 붙이지 않고 처음부터')
    p.add_argument('--smoke', action='store_true', help='흐름 확인(작은 자료·모델 몇 분, 별도 커널 aisfa-seq-train-smoke)')
    p.add_argument('--kernel-name', default='', help='비교 실험용 별도 커널 이름(공식 aisfa-seq-train 기록을 건드리지 않게, 예 aisfa-seq-coord2-ab)')
    p.add_argument('--cpu', action='store_true', help='GPU 끄고(주간 GPU 시간을 쓰지 않음)')
    p.add_argument('--gpu-ok', action='store_true', help='사용자가 GPU 실행을 지시했음(없으면 GPU push를 거부)')
    p.add_argument('--ckpt', default=CKPT, help='이어하기 자료 이름')
    p.add_argument('--prebuilt', action='store_true', help='push-data 커널 출력을 입력으로 붙여 자료 만들기 없이 학습')
    p.add_argument('--no-init-encoder', action='store_true', help='이전 픽셀 지도 모델 인코더 없이 ImageNet에서 출발')
    p.add_argument('--no-stages', action='store_true', help='해상도 단계(1080→720→480→360) 없이 360만(이어하기는 처음 설정을 따른다)')
    p.add_argument('--prebuilt-any-code', action='store_true', help='자료를 만든 뒤 자료 코드가 바뀌어도 그대로 씀(자료에 영향 없는 변경일 때만)')
    pe = sub.add_parser('push-encoder')
    pe.add_argument('file', help='seq_train.py vec-encoder로 만든 파일')
    pd = sub.add_parser('push-data')
    pd.add_argument('--branch', default='claude/new-session-gknz4t')
    pd.add_argument('--smoke', action='store_true', help='작은 자료(별도 커널 aisfa-seq-data-smoke)')
    pd.add_argument('--no-stages', action='store_true', help='1080·720·480 단계 자료 없이')
    st_ = sub.add_parser('status')
    st_.add_argument('--smoke', action='store_true')
    st_.add_argument('--data', action='store_true', help='자료 커널')
    w = sub.add_parser('wait')
    w.add_argument('--hours', type=float, default=13)
    w.add_argument('--smoke', action='store_true')
    w.add_argument('--data', action='store_true', help='자료 커널')
    for nm in ('pull', 'save-ckpt'):
        q = sub.add_parser(nm)
        q.add_argument('dir')
        q.add_argument('--smoke', action='store_true')
        if nm == 'pull':
            q.add_argument('--data', action='store_true', help='자료 커널 출력(약 1.5GB — 보통 받을 필요 없음, data_info.json만 보려면 status)')
        q.add_argument('--ckpt', default=CKPT, help='이어하기 자료 이름(시험은 다른 이름으로 — 본 학습이 시험 모델을 이어받지 않게)')
    q = sub.add_parser('data-check', help='자료 커널의 정합성 요약만 받기(data_info.json·done.json)')
    q.add_argument('dir')
    q = sub.add_parser('to-drive')
    q.add_argument('dir')
    q.add_argument('run')
    q = sub.add_parser('from-drive')
    q.add_argument('run')
    q.add_argument('dir')
    a = ap.parse_args()
    dict(push=push, status=status, **{'push-data': push_data, 'push-encoder': push_encoder}, wait=wait, pull=pull, **{'data-check': data_check}, **{'save-ckpt': save_ckpt, 'to-drive': to_drive, 'from-drive': from_drive})[a.cmd](a)


if __name__ == '__main__':
    main()
