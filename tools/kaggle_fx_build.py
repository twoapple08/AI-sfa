"""Kaggle 노트북(P3 이펙트 분리: Grounding DINO + SAM 2)을 만든다.

출력: tools/kaggle_fx.ipynb — tools/kaggle_fx_worker.py 본문을 넣어 둔다. GPU 2장이면 구간을 반씩 나눠 동시에 돈다.
rclone 인증은 Kaggle 비밀값 RCLONE_GDRIVE_AUTH_B64에서만 읽는다(kaggle_build.py와 같은 방식).
"""
import json
import os

from colab_p1_build import ROOT, code, md


def setup_cell():
    """kaggle_build.py의 준비 셀(rclone 설정·설치)을 그대로 가져온다."""
    src = open(os.path.join(ROOT, "tools/kaggle_build.py"), encoding="utf-8").read()
    a = src.index("# 1. 준비")
    b = src.index("!pip -q install rtmlib")
    return src[a:b].replace('\\\\n', '\\n')


def build():
    worker = open(os.path.join(ROOT, "tools/kaggle_fx_worker.py"), encoding="utf-8").read()
    cells = [
        md("""
# AI-sfa P3 이펙트 분리 — Kaggle GPU

나카무라 영상의 폭발·연기·파편 구간(157구간, 약 5,500프레임)에서 **이펙트 영역만** 오려 Drive에 올린다.
(Grounding DINO로 '폭발·연기·파편…' 상자를 찾고 SAM 2가 오려 구간 전체로 따라간다. 사람은 뺀다.)

**설정(P1·P2 노트북과 같다):** Accelerator **GPU T4 x2**, Internet **On**, Secrets에 `RCLONE_GDRIVE_AUTH_B64` 붙이기.

**실행:** 오른쪽 위 **Save Version → Save & Run All (Commit)**. 결과: Drive `02_분석자료/이펙트_분리/`.
멈추면 다시 Save & Run All — 끝난 구간은 건너뛴다.
"""),
        code(setup_cell() + """!SAM2_BUILD_CUDA=0 pip -q install --no-build-isolation sam2
import torch; print('GPU 수:', torch.cuda.device_count(), [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
"""),
        code("""
# 2. 작업자 파일 쓰기 + 모델 미리 받기(두 작업자가 동시에 받다 충돌하지 않게)
open('/kaggle/working/kaggle_fx_worker.py', 'w', encoding='utf-8').write(%s)
import subprocess
subprocess.run(['python', '-c', "from sam2.sam2_video_predictor import SAM2VideoPredictor as P; P.from_pretrained('facebook/sam2.1-hiera-large', device='cpu'); from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection as M; AutoProcessor.from_pretrained('IDEA-Research/grounding-dino-base'); M.from_pretrained('IDEA-Research/grounding-dino-base')"], check=True)
print('준비 끝')
""" % json.dumps(worker, ensure_ascii=False)),
        code("""
# 3. 실행: GPU마다 작업자 하나. 5분마다 진행 상황을 찍는다
import subprocess, time, os
ng = max(1, torch.cuda.device_count())
procs = {}
for g in range(ng):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g))
    procs[g] = subprocess.Popen(['python', '/kaggle/working/kaggle_fx_worker.py', str(g), str(ng)], env=env,
                                stdout=open(f'/kaggle/working/fx{g}.log', 'w'), stderr=subprocess.STDOUT)
t0 = time.time()
while procs and time.time() - t0 < 11.6 * 3600:
    time.sleep(300)
    for g, pr in list(procs.items()):
        lines = [l for l in open(f'/kaggle/working/fx{g}.log', encoding='utf-8', errors='replace').read().splitlines() if '/' in l or '끝' in l or 'Error' in l]
        print(round((time.time() - t0) / 60), '분 GPU', g, '|', ' / '.join(lines[-2:])[-300:], flush=True)
        if pr.poll() is not None:
            del procs[g]
for pr in procs.values(): pr.terminate()
print('종료')
"""),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "kaggle": {"accelerator": "nvidiaTeslaT4", "isInternetEnabled": True}},
          "nbformat": 4, "nbformat_minor": 4}
    p = os.path.join(ROOT, "tools/kaggle_fx.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
