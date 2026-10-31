#!/usr/bin/env python3
"""Kaggle 작업자(2026-10-30, 재설계 영상 → 스파 문장 학습): 저장소 받기 → 자료(학습 + 늘리기 1벌, 시험) → 학습 → /kaggle/working/out.
kaggle_seq_remote.py가 CONFIG를 채워 Kaggle 스크립트 커널로 올린다(사용자 컴퓨터 없이). 이어하기: 입력 자료(ckpt 자료)에 ckpt.pt가 있으면 그것부터.
T4는 bf16이 없어 seq_train이 fp16 + GradScaler로 돈다. GPU는 1개만 쓴다.
mode='data'(10-31): CPU 커널에서 자료만 만들어 /kaggle/working/{sd1920,sd1280,sd854,sd,sv,ss}에 남긴다(GPU 시간 0). 판·코드 표시는 data_info.json.
stages=True(기본, 10-31 복원): 해상도 단계 1080 → 720 → 480 → 360 학습(seq_train --stages).
prebuilt=True: GPU 학습이 그 커널 출력(입력으로 붙음)을 그대로 쓴다. 자료 판·설정·코드가 다르면 GPU 시간을 쓰기 전에 멈춘다.
"""
import glob
import hashlib
import json
import os
import shutil
import subprocess
import time

CONFIG = {'branch': 'ccr-bccf15a6-d6ee46', 'session_minutes': 690, 'plan_minutes': 0, 'tok_budget': 12288, 'extra': '', 'smoke': False,
          'mode': 'train', 'prebuilt': False, 'prebuilt_any_code': False, 'stages': True,
          'init_encoder': True}

T0 = time.time()
SPLITS = ('sd', 'sv', 'ss')   # 학습(+늘리기), 시험 파일, 위치 시험
HIRES = (1920, 1280, 854)     # 해상도 단계(사용자 10-29·10-31): 1080 → 720 → 480 → 기본 360(sd). 영상(mp4)으로 저장
CODE = ('seq_data.py', 'sfa_render.py', 'sfa_tokens.py', 'vec_data.py')   # 자료 내용을 정하는 코드(바뀌었는데 판을 안 올린 경우를 잡는다)


def sh(cmd):
    print('$', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def data_args(c, cpus):
    """자료마다 seq_data 옵션. 자료 커널과 학습 커널이 같은 함수를 써서 설정이 어긋나지 않게 한다."""
    smoke = c.get('smoke')
    w = f'--workers {cpus}'
    sd = f'--maxlen 2048 --max-frames {6 if smoke else 300}{" --every 40" if smoke else ""} --aug 1 --synth 0.3 {w}'   # 페인트 합성: 흰 바탕이 너무 많아 학습에 넣음(사용자 10-29)
    hi = {f'sd{r}': f'{sd} --W {r} --video' for r in HIRES} if c.get('stages', True) else {}
    return dict(
        **hi,
        sd=sd,
        sv=f'--maxlen 2048 --max-frames {4 if smoke else 40} --holdout {w}',
        ss=f'--maxlen 2048 --max-frames {4 if smoke else 8} --every {40 if smoke else 10} --fixed 6,4,1.05 {w}')   # 위치 시험: 학습 파일 10개 중 1개에 학습에 없던 고정 이동(GPT 3차)


def code_hash(tools):
    return {f: hashlib.sha256(open(f'{tools}/{f}', 'rb').read()).hexdigest()[:16] for f in CODE}


def clone(c):
    sh('pip install -q skia-python')
    repo = '/kaggle/tmp/AI-sfa'
    if not os.path.isdir(repo):
        sh(f'git clone -q --depth 1 -b {c["branch"]} https://github.com/twoapple08/AI-sfa {repo}')
    sh(f'cd {repo} && git log --oneline -1')
    commit = subprocess.run(f'cd {repo} && git rev-parse HEAD', shell=True, capture_output=True, text=True).stdout.strip()
    return repo, commit


def make_data(c):
    """자료만 만들기(CPU 커널): /kaggle/working/{sd,sv,ss} + data_info.json."""
    repo, commit = clone(c)
    tools = f'{repo}/tools'
    cpus = os.cpu_count() or 4
    work = '/kaggle/working'
    info = dict(commit=commit, branch=c['branch'], smoke=bool(c.get('smoke')), code=code_hash(tools), cpus=cpus, splits={})
    for name, args in data_args(c, cpus).items():
        t1 = time.time()
        sh(f'cd {tools} && python -u seq_data.py {work}/{name} {args}')
        d = json.load(open(f'{work}/{name}/done.json', encoding='utf-8'))
        info['splits'][name] = dict(minutes=round((time.time() - t1) / 60, 1), frames=d['frames'], npz=d['npz'], version=d['version'],
                                    mb=round(sum(os.path.getsize(p) for p in glob.glob(f'{work}/{name}/*.npz')) / 2 ** 20))
        print(name, info['splits'][name], flush=True)
    info['minutes'] = round((time.time() - T0) / 60, 1)
    json.dump(info, open(f'{work}/data_info.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('자료 끝', json.dumps(info, ensure_ascii=False), flush=True)


def find_prebuilt(c, tools, cpus):
    """입력으로 붙은 자료 커널 출력에서 sd·sv·ss를 찾아 지금 코드로 '같은 설정으로 다 만듦'인지 확인. 하나라도 아니면 멈춘다(GPU 시간 보호)."""
    infos = sorted(glob.glob('/kaggle/input/**/data_info.json', recursive=True))
    if not infos:
        raise SystemExit('미리 만든 자료(data_info.json)가 입력에 없음 — push-data를 먼저 끝내거나 --prebuilt 없이')
    root = os.path.dirname(infos[0])
    info = json.load(open(infos[0], encoding='utf-8'))
    print('미리 만든 자료:', root, '만든 판', info.get('commit', '')[:8], flush=True)
    if bool(info.get('smoke')) != bool(c.get('smoke')):
        raise SystemExit(f'미리 만든 자료의 smoke={info.get("smoke")}가 이 실행과 다름')
    diff = [f for f, h in code_hash(tools).items() if info.get('code', {}).get(f) != h]
    if diff:
        msg = f'자료를 만든 뒤 바뀐 코드: {diff}'
        if not c.get('prebuilt_any_code'):
            raise SystemExit(msg + ' — 자료를 다시 만들거나(push-data), 자료에 영향 없는 변경이면 --prebuilt-any-code')
        print('경고:', msg, '(--prebuilt-any-code로 그대로 씀)', flush=True)
    out = {}
    for name, args in data_args(c, cpus).items():
        d = f'{root}/{name}'
        r = subprocess.run(f'cd {tools} && python -u seq_data.py {d} {args} --check', shell=True)
        if r.returncode:
            raise SystemExit(f'미리 만든 자료 {name}가 지금 판·설정과 다름 — push-data로 다시 만들 것')
        out[name] = d
    return out


def main():
    c = CONFIG
    if c.get('mode') == 'data':
        return make_data(c)
    out = '/kaggle/working/out'
    os.makedirs(out, exist_ok=True)
    sh('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true')
    repo, _ = clone(c)
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
    t1 = time.time()
    if c.get('prebuilt'):
        dirs = find_prebuilt(c, tools, cpus)
    else:
        dirs = {name: f'/kaggle/tmp/{name}' for name in data_args(c, cpus)}
        for name, args in data_args(c, cpus).items():
            sh(f'cd {tools} && python -u seq_data.py {dirs[name]} {args}')
    data, val, shv = dirs['sd'], dirs['sv'], dirs['ss']
    stages = ','.join(dirs[f'sd{r}'] for r in HIRES) if c.get('stages', True) else ''
    print(f'자료 {(time.time() - t1) / 60:.1f}분', flush=True)
    enc = ''
    if c.get('init_encoder') and not os.path.exists(f'{out}/ckpt.pt'):   # 새로 시작할 때만(이어하기는 저장본 그대로)
        found = sorted(glob.glob('/kaggle/input/**/vec_encoder.pt', recursive=True))
        if not found:
            raise SystemExit('인코더 파일(vec_encoder.pt)이 입력에 없음 — push-encoder 먼저 또는 --no-init-encoder')
        enc = f' --init-encoder {found[0]}'
    left = c['session_minutes'] - (time.time() - T0) / 60 - (2 if c.get('smoke') else 20)   # 자료 읽기·마지막 검증·저장 몫
    if left < (1 if c.get('smoke') else 10):
        raise SystemExit('남은 시간이 없음')
    cmd = (f'cd {tools} && python -u seq_train.py train {data} {val} {out} --minutes {left:.0f} --plan-minutes {c["plan_minutes"]:.0f}'
           f' --tok-budget {c["tok_budget"]} --shift-val {shv}' + (f' --stages {stages}' if stages else '') + enc + f' {c["extra"]}')
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
