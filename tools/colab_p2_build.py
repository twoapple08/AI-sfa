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

VIDEO_DIRS = ["yutaka_nakamura_디지털", "nian41", "riooo", "yukina_kosaka", "optical-core"]  # 몸 학습 우선순위 순


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
import onnxruntime as ort
try: ort.preload_dlls()  # torch에 든 CUDA·cuDNN을 먼저 불러 ONNX가 GPU를 쓰게 한다
except Exception as e: print('preload_dlls 실패:', e)
print('ONNX 가능 장치:', ort.get_available_providers())
from rtmlib import Wholebody
DET = Wholebody(mode='performance', backend='onnxruntime', device=DEV).det_model
DET.score_thr = 0.3
try: print('검출기 장치:', DET.session.get_providers()[0])
except Exception: pass
H = 368  # RAFT 입력 높이(8의 배수). 너비는 비율대로 8의 배수
DET_EVERY = 6  # 캐릭터 상자는 6프레임마다 검출하고 사이 프레임은 앞 상자를 10퍼센트 넓혀 쓴다
UPDATES = 6  # RAFT 반복 횟수(기본 12). 전역 카메라 추정에는 6으로 충분

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
    last = [None]
    def mask(im, i):
        if i %% DET_EVERY == 0 or last[0] is None:
            b = np.asarray(DET(im)).reshape(-1, 4)
            c = (b[:, :2] + b[:, 2:]) / 2; hw = (b[:, 2:] - b[:, :2]) * 0.55
            last[0] = np.concatenate([c - hw, c + hw], 1)
        mk = np.ones((H, w), bool)
        for x1, y1, x2, y2 in last[0] * [w / w0, H / h0, w / w0, H / h0]:
            mk[max(0, int(y1)):int(y2) + 1, max(0, int(x1)):int(x2) + 1] = False
        return mk, len(last[0])
    pm, n0 = mask(prev, 0); nb = [n0]; fi = 1
    cam = [[0] * 6]; grid = [np.zeros((9, 16, 2), np.float16)]
    B = 16; done_ = False; nstill = 0; T = dict(읽기=0., 검출=0., 광류=0., 맞춤=0.)
    small = lambda im: cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (160, 90), interpolation=cv2.INTER_AREA).astype(np.int16)
    while not done_:
        t0 = time.time(); cur = []
        while len(cur) < B:
            ok, im = cap.read()
            if not ok: done_ = True; break
            cur.append(im)
        if not cur: break
        T['읽기'] += time.time() - t0; t0 = time.time()
        ms = [mask(im, fi + k) for k, im in enumerate(cur)]; fi += len(cur)
        T['검출'] += time.time() - t0; t0 = time.time()
        pairs = [prev] + cur
        # 애니의 정지 프레임(같은 그림 유지)은 광류를 계산하지 않고 카메라 정지로 기록한다
        moving = [k for k in range(len(cur)) if np.abs(small(pairs[k]) - small(pairs[k + 1])).mean() > 0.6]
        fl = g = None
        if moving:
            a = prep([pairs[k] for k in moving], w); b = prep([pairs[k + 1] for k in moving], w)
            with torch.no_grad():
                fl = raft(a, b, num_flow_updates=UPDATES)[-1]
            g = F.adaptive_avg_pool2d(fl, (9, 16)).permute(0, 2, 3, 1).cpu().numpy() / w
            fl = fl.permute(0, 2, 3, 1).cpu().numpy()
        T['광류'] += time.time() - t0; t0 = time.time()
        masks = [pm] + [m for m, _ in ms]; pos = {k: j for j, k in enumerate(moving)}
        for k in range(len(cur)):
            if k in pos:
                j = pos[k]; cam.append(fit(fl[j], masks[k] & masks[k + 1], w)); grid.append(g[j].astype(np.float16))
            else:
                nstill += 1; cam.append([0, 0, 0, 0, 1.0, 0]); grid.append(np.zeros((9, 16, 2), np.float16))
        nb += [n for _, n in ms]; prev = cur[-1]; pm = ms[-1][0]
        T['맞춤'] += time.time() - t0
    cap.release()
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    np.savez_compressed(dst, cam=np.array(cam, np.float32), grid=np.stack(grid), boxes=np.array(nb), fps=fps, size=[w0, h0])
    return f"{len(cam)} 프레임(정지 {nstill}) " + ' '.join(f'{k} {v:.0f}' for k, v in T.items())
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
    print(k + 1, '/', len(vids), os.path.basename(dst), n, '| 합계', round(time.time() - t), '초', '누적', round((time.time() - t0) / 60), '분')
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
