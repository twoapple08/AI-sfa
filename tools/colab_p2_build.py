"""P2 카메라 움직임 Colab 노트북을 만든다.

출력: tools/colab_p2_camera_flow.ipynb
노트북은 Drive 원본 영상마다 연속 프레임 광류(torchvision RAFT-large)를 구하고,
캐릭터 상자(rtmlib HumanArt 검출기)를 가린 배경 흐름에 닮음 변환을 RANSAC으로 맞춰
프레임별 카메라 값을 저장한다. 결과: Drive `AI-sfa/02_분석자료/P2_카메라/<애니메이터>/<post_id>.npz`

npz 내용
- cam: [N, 6] = tx, ty(화면 너비 비율), log_scale, rot(라디안), inlier 비율, 배경 흐름 중앙 크기(픽셀)
       i번째 값은 프레임 i-1 → i 변환(0번은 0)
- grid: [N, 9, 16, 2] float16 흐름 격자(화면 너비 비율), 흔들림·비강체 움직임 학습용
- boxes: 프레임별 캐릭터 상자 수
- fps, size
"""
import json
import os

from colab_p1_build import ROOT, code, md

VIDEO_DIRS = ["nian41", "optical-core", "riooo", "yukina_kosaka", "yutaka_nakamura_디지털"]


def build():
    cells = [
        md("""
# P2 카메라 움직임(광류) — Colab GPU

**런타임 → 모두 실행.** GPU는 A100 > L4 > T4. 끊기면 다시 '모두 실행'(끝난 영상은 건너뜀).

- 원본 영상 354개 전부를 처리한다. T4 기준 수 시간이 걸릴 수 있다. 진행은 영상마다 한 줄씩 찍힌다.
- 결과: 내 드라이브 `AI-sfa/02_분석자료/P2_카메라/` — Claude가 Drive에서 직접 읽는다.
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
# 3. 설정과 함수
import os, glob, time, shutil, traceback
import cv2, numpy as np, torch, torch.nn.functional as F
from torchvision.models.optical_flow import raft_large, Raft_Large_Weights
ROOT = '/content/drive/MyDrive/AI-sfa'
OUT = ROOT + '/02_분석자료/P2_카메라'
DIRS = %s
DEV = 'cuda' if torch.cuda.is_available() else 'cpu'
raft = raft_large(weights=Raft_Large_Weights.C_T_SKHT_V2).to(DEV).eval()
from rtmlib import Wholebody
DET = Wholebody(mode='performance', backend='onnxruntime', device=DEV).det_model
DET.score_thr = 0.3
H = 368  # RAFT 입력 높이(8의 배수). 너비는 비율대로 8의 배수

def prep(ims, w):
    t = torch.from_numpy(np.stack([cv2.cvtColor(cv2.resize(i, (w, H)), cv2.COLOR_BGR2RGB) for i in ims]))
    return (t.permute(0, 3, 1, 2).float() / 127.5 - 1).to(DEV)

def fit(flow, mask, W):
    # flow [H,w,2] 픽셀, mask True=배경. 닮음 변환 RANSAC → tx, ty(너비 비율), log_s, rot, inlier, 중앙 크기
    hh, ww = flow.shape[:2]
    ys, xs = np.mgrid[4:hh:8, 4:ww:8]
    m = mask[ys, xs]
    if m.sum() < 30: return [0, 0, 0, 0, 0, 0]
    p0 = np.stack([xs[m], ys[m]], 1).astype(np.float32)
    p1 = p0 + flow[ys[m], xs[m]]
    A, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=1.5, maxIters=2000)
    if A is None: return [0, 0, 0, 0, 0, float(np.median(np.linalg.norm(p1 - p0, axis=1)))]
    s = np.hypot(A[0, 0], A[1, 0]); r = np.arctan2(A[1, 0], A[0, 0])
    # 화면 중심 기준 이동으로 바꾼다
    c = np.array([ww / 2, hh / 2]); t = A[:, :2] @ c + A[:, 2] - c
    return [t[0] / ww, t[1] / ww, float(np.log(s)), float(r), float(inl.mean()), float(np.median(np.linalg.norm(p1 - p0, axis=1)))]

def run(src, dst):
    loc = '/content/cur.mp4'; shutil.copy(src, loc)
    cap = cv2.VideoCapture(loc); fps = cap.get(cv2.CAP_PROP_FPS)
    ok, prev = cap.read()
    if not ok: return 0
    h0, w0 = prev.shape[:2]; w = int(round(w0 * H / h0 / 8)) * 8
    def mask(im):
        b = np.asarray(DET(im)).reshape(-1, 4)
        mk = np.ones((H, w), bool)
        for x1, y1, x2, y2 in b * [w / w0, H / h0, w / w0, H / h0]:
            mk[max(0, int(y1)):int(y2) + 1, max(0, int(x1)):int(x2) + 1] = False
        return mk, len(b)
    pm, n0 = mask(prev); nb = [n0]
    cam = [[0] * 6]; grid = [np.zeros((9, 16, 2), np.float16)]
    B = 8; done_ = False
    while not done_:
        cur = []
        while len(cur) < B:
            ok, im = cap.read()
            if not ok: done_ = True; break
            cur.append(im)
        if not cur: break
        ms = [mask(im) for im in cur]
        a = prep([prev] + cur[:-1], w); b = prep(cur, w)
        with torch.no_grad():
            fl = raft(a, b)[-1]
        g = F.adaptive_avg_pool2d(fl, (9, 16)).permute(0, 2, 3, 1).cpu().numpy() / w
        fl = fl.permute(0, 2, 3, 1).cpu().numpy()
        masks = [pm] + [m for m, _ in ms]
        for k in range(len(cur)):
            cam.append(fit(fl[k], masks[k] & masks[k + 1], w)); grid.append(g[k].astype(np.float16))
        nb += [n for _, n in ms]; prev = cur[-1]; pm = ms[-1][0]
    cap.release()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    np.savez_compressed(dst, cam=np.array(cam, np.float32), grid=np.stack(grid), boxes=np.array(nb), fps=fps, size=[w0, h0])
    return len(cam)
""" % json.dumps(VIDEO_DIRS, ensure_ascii=False)),
        code("""
# 4. 전체 실행
vids = []
for d in DIRS:
    for p in sorted(glob.glob(f'{ROOT}/01_원본영상/{d}/**/*.mp4', recursive=True)):
        pid = os.path.basename(p).split('_')[0].split('.')[0]
        an = 'yutaka_nakamura' if d.startswith('yutaka') else d
        vids.append((p, f'{OUT}/{an}/{pid}.npz'))
print(len(vids), '영상')
t0 = time.time()
for k, (p, dst) in enumerate(vids):
    if os.path.exists(dst): continue
    t = time.time()
    try: n = run(p, dst)
    except Exception: traceback.print_exc(); continue
    print(k + 1, '/', len(vids), os.path.basename(dst), n, '프레임', round(time.time() - t), '초', '누적', round((time.time() - t0) / 60), '분')
"""),
    ]
    nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                                       "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "nbformat": 4, "nbformat_minor": 0}
    p = os.path.join(ROOT, "tools/colab_p2_camera_flow.ipynb")
    json.dump(nb, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    print(build())
