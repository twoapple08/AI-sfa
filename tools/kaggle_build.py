"""Kaggle 노트북(P1 포즈 전체 추출 + P2 카메라 광류 동시 실행)을 만든다.

출력: tools/kaggle_p1p2.ipynb — tools/kaggle_worker.py 본문을 넣어 둔다.
GPU 0은 P2, GPU 1은 P1. GPU가 1장이면 P2 → P1 순서로 한다.
rclone 인증은 Kaggle 비밀값 RCLONE_GDRIVE_AUTH_B64(클라우드 환경 변수와 같은 값)에서만 읽는다.
"""
import json
import os

from colab_p1_build import ROOT, code, md


def build():
    worker = open(os.path.join(ROOT, "tools/kaggle_worker.py"), encoding="utf-8").read()
    cells = [
        md("""
# AI-sfa P1·P2 — Kaggle GPU

**처음 한 번만 설정(오른쪽 패널 또는 메뉴):**
1. **Settings → Accelerator → GPU T4 x2**
2. **Settings → Internet → On**(휴대폰 인증한 계정만 켤 수 있다)
3. **Add-ons → Secrets**에 `RCLONE_GDRIVE_AUTH_B64`를 추가하고(값은 Claude 클라우드 환경 변수에 넣은 것과 같은 값) 이 노트북에 체크해 붙인다. 대화에는 붙이지 않는다.

**실행:** 오른쪽 위 **Save Version → Save & Run All (Commit)**을 누르면 브라우저를 닫아도 최대 12시간 돈다.
결과는 영상마다 Drive에 바로 올라간다(P2 → `02_분석자료/P2_카메라/`, P1 → `02_분석자료/포즈_RTMW/`).
12시간이 지나 멈추면 다시 Save & Run All을 누르면 끝난 영상은 건너뛴다. Kaggle GPU는 주 30시간까지 무료.
"""),
        code("""
# 1. 준비: rclone 설치·설정(인증값은 출력하지 않는다), 라이브러리
import os, json, base64, subprocess, pathlib
from kaggle_secrets import UserSecretsClient
raw = UserSecretsClient().get_secret('RCLONE_GDRIVE_AUTH_B64').strip()
d = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4)))
p = pathlib.Path.home() / '.config/rclone'; p.mkdir(parents=True, exist_ok=True)
lines = ['[gdrive]', 'type = drive', 'scope = drive.readonly,drive.file']
if d.get('client_id'): lines.append('client_id = ' + d['client_id'])
if d.get('client_secret'): lines.append('client_secret = ' + d['client_secret'])
lines.append('token = ' + d['token'])
(p / 'rclone.conf').write_text('\\n'.join(lines) + '\\n'); os.chmod(p / 'rclone.conf', 0o600)
del raw, d, lines
!cd /tmp && curl -sSLo rc.zip https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qo rc.zip && cp rclone-*/rclone /usr/local/bin/
!rclone lsd gdrive:AI-sfa 2>/dev/null | head -3
!pip -q install rtmlib onnxruntime-gpu onnx onnx2torch
import torch; print('GPU 수:', torch.cuda.device_count(), [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
"""),
        code("""
# 2. 작업자 파일 쓰기
open('/kaggle/working/kaggle_worker.py', 'w', encoding='utf-8').write(%s)
print('작업자 준비')
""" % json.dumps(worker, ensure_ascii=False)),
        code("""
# 3. 실행: GPU 0 = P2(카메라), GPU 1 = P1(포즈). 5분마다 진행 상황을 찍는다
import subprocess, time, os
ng = torch.cuda.device_count()
def start(task, gpu):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
    return subprocess.Popen(['python', '/kaggle/working/kaggle_worker.py', task, '0', '1'], env=env,
                            stdout=open(f'/kaggle/working/{task}.log', 'w'), stderr=subprocess.STDOUT)
# 두 작업자가 같은 모델 파일을 동시에 받다 충돌하지 않도록 먼저 한 번 받아 둔다
subprocess.run(['python', '-c', "from rtmlib import Wholebody; Wholebody(mode='performance', backend='onnxruntime', device='cpu')"], check=True)
plan = [('p2', 0), ('p1', 1)] if ng >= 2 else [('p2', 0)]
procs = {t: start(t, g) for t, g in plan}
t0 = time.time()
while procs and time.time() - t0 < 11.6 * 3600:
    time.sleep(300)
    for t, pr in list(procs.items()):
        tail = open(f'/kaggle/working/{t}.log', encoding='utf-8', errors='replace').read().splitlines()[-2:]
        print(round((time.time() - t0) / 60), '분', t, '|', ' / '.join(tail), flush=True)
        if pr.poll() is not None:
            del procs[t]
            if ng < 2 and t == 'p2': procs['p1'] = start('p1', 0)
for pr in procs.values(): pr.terminate()
print('종료')
"""),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True}},
          "nbformat": 4, "nbformat_minor": 4}
    p = os.path.join(ROOT, "tools/kaggle_p1p2.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
