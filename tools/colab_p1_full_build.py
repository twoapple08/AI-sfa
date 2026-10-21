"""P1 전체 포즈 재추출 Colab 노트북(RTMW-x 133점)을 만든다.

출력: tools/colab_p1_rtmw_full.ipynb
P1 모델 비교(tools/p1_pose_eval.py)에서 RTMW-x를 골랐다. 비교 때 쓴 '상자 없으면 화면 전체' 대체 규칙은
사람 없는 장면에 거짓 뼈대를 만들었으므로 여기서는 쓰지 않는다(검출 상자가 없으면 빈 프레임).
결과: Drive `AI-sfa/02_분석자료/포즈_RTMW/<애니메이터>/<post_id>.jsonl.gz`
줄마다 {"f": 프레임, "p": [{"b": [x1,y1,x2,y2], "k": [[x,y,점수]×133]}]}
"""
import json
import os

from colab_p1_build import ROOT, code, md

VIDEO_DIRS = ["yutaka_nakamura_디지털", "nian41", "riooo", "yukina_kosaka", "optical-core"]


def build():
    cells = [
        md("""
# P1 전체 포즈 재추출(RTMW-x 133점) — Colab GPU

**런타임 → 모두 실행.** GPU는 T4 이상. 끊기면 다시 '모두 실행'(끝난 영상은 건너뜀).

- 원본 영상 354개 전부, 모든 프레임. 나카무라 → nian41 → 보충 3명 순서.
- 결과: 내 드라이브 `AI-sfa/02_분석자료/포즈_RTMW/` — Claude가 Drive에서 직접 읽는다.
- 3번 칸 출력의 `ONNX 장치`가 CUDAExecutionProvider면 GPU로 도는 것이다.
"""),
        code("""
# 1. 준비
!pip -q install rtmlib onnxruntime-gpu
import torch; print('GPU:', torch.cuda.is_available() and torch.cuda.get_device_name(0))
"""),
        code("""
# 2. 드라이브 연결
from google.colab import drive
drive.mount('/content/drive')
"""),
        code("""
# 3. 설정
import os, glob, gzip, json, time, shutil, traceback
import cv2, numpy as np
import onnxruntime as ort
try: ort.preload_dlls()  # torch에 든 CUDA·cuDNN을 먼저 불러 ONNX가 GPU를 쓰게 한다
except Exception as e: print('preload_dlls 실패:', e)
from rtmlib import Wholebody
DEV = 'cuda' if 'CUDAExecutionProvider' in ort.get_available_providers() else 'cpu'
WB = Wholebody(mode='performance', backend='onnxruntime', device=DEV)
WB.det_model.score_thr = 0.3
try: print('ONNX 장치:', WB.det_model.session.get_providers()[0], WB.pose_model.session.get_providers()[0])
except Exception: print('ONNX 장치:', DEV)
ROOT = '/content/drive/MyDrive/AI-sfa'
OUT = ROOT + '/02_분석자료/포즈_RTMW'
DIRS = %s

def r(a, n): return np.round(np.asarray(a, dtype=float), n)

def run(src, dst):
    loc = '/content/cur.mp4'; shutil.copy(src, loc)
    cap = cv2.VideoCapture(loc); tmp = '/content/cur.jsonl.gz'; n = det = 0
    with gzip.open(tmp, 'wt', encoding='utf-8') as f:
        while True:
            ok, im = cap.read()
            if not ok: break
            b = np.asarray(WB.det_model(im)).reshape(-1, 4); ppl = []
            if len(b):
                kp, sc = WB.pose_model(im, bboxes=b)
                for bb, k, s in zip(b, kp, sc):
                    ppl.append({'b': r(bb, 1).tolist(), 'k': np.concatenate([r(k, 1), r(s, 3)[:, None]], 1).tolist()})
                det += 1
            f.write(json.dumps({'f': n, 'p': ppl}, separators=(',', ':')) + '\\n'); n += 1
    cap.release()
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(tmp, dst)
    return n, det
""" % json.dumps(VIDEO_DIRS, ensure_ascii=False)),
        code("""
# 4. 전체 실행
vids = []
for d in DIRS:
    for p in sorted(glob.glob(f'{ROOT}/01_원본영상/{d}/**/*.mp4', recursive=True)):
        pid = os.path.basename(p).split('_')[0].split('.')[0]
        an = 'yutaka_nakamura' if d.startswith('yutaka') else d
        vids.append((p, f'{OUT}/{an}/{pid}.jsonl.gz'))
print(len(vids), '영상')
t0 = time.time()
for k, (p, dst) in enumerate(vids):
    if os.path.exists(dst): continue
    t = time.time()
    try: n, det = run(p, dst)
    except Exception: traceback.print_exc(); continue
    print(k + 1, '/', len(vids), os.path.basename(dst), n, '프레임', '사람', det, round(time.time() - t), '초', '누적', round((time.time() - t0) / 60), '분')
"""),
    ]
    nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                       "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 0}
    p = os.path.join(ROOT, "tools/colab_p1_rtmw_full.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
