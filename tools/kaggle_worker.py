"""Kaggle GPU 작업자: P1(RTMW-x 포즈 전체 추출) 또는 P2(카메라 광류)를 영상마다 Drive에서 받아 처리하고 Drive에 올린다.

사용: CUDA_VISIBLE_DEVICES=<gpu> python kaggle_worker.py <p1|p2> <작업자 번호> <작업자 수>
- rclone 원격 이름은 gdrive(노트북이 설정). 끝난 영상(Drive에 결과 있음)은 건너뛴다.
- 결과 형식은 Colab 노트북(tools/colab_p1_full_build.py, tools/colab_p2_build.py)과 같다.
"""
import gzip
import json
import os
import subprocess
import sys
import time
import traceback

import cv2
import numpy as np

TASK, WID, NW = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
SRC = "gdrive:AI-sfa/01_원본영상"
DIRS = ["yutaka_nakamura_디지털", "nian41", "riooo", "yukina_kosaka", "optical-core"]  # 몸 학습 우선순위 순
OUT = {"p1": "gdrive:AI-sfa/02_분석자료/포즈_RTMW", "p2": "gdrive:AI-sfa/02_분석자료/P2_카메라"}[TASK]
EXT = {"p1": ".jsonl.gz", "p2": ".npz"}[TASK]
TMP = f"/tmp/w_{TASK}_{WID}"
os.makedirs(TMP, exist_ok=True)


def rc(*a):
    return subprocess.run(["rclone", *a], capture_output=True, text=True)


def log(*a):
    print(time.strftime("%H:%M:%S"), TASK, WID, *a, flush=True)


import onnxruntime as ort  # noqa: E402

try:
    ort.preload_dlls()  # torch에 든 CUDA·cuDNN을 먼저 불러 ONNX가 GPU를 쓰게 한다
except Exception as e:
    log("preload_dlls 실패", e)
import torch  # noqa: E402
from rtmlib import Wholebody  # noqa: E402

ODEV = "cuda" if "CUDAExecutionProvider" in ort.get_available_providers() else "cpu"
WB = Wholebody(mode="performance", backend="onnxruntime", device=ODEV)
WB.det_model.score_thr = 0.3
try:
    log("ONNX 장치", WB.det_model.session.get_providers()[0], "torch", torch.cuda.get_device_name(0))
except Exception:
    log("ONNX 장치", ODEV)


def r(a, n):
    return np.round(np.asarray(a, dtype=float), n)


# ---------- P1: 모든 프레임 RTMW-x 133점. 검출 상자 없으면 빈 프레임(거짓 뼈대 방지) ----------
def run_p1(loc, dst):
    cap = cv2.VideoCapture(loc)
    n = det = 0
    with gzip.open(dst, "wt", encoding="utf-8") as f:
        while True:
            ok, im = cap.read()
            if not ok:
                break
            b = np.asarray(WB.det_model(im)).reshape(-1, 4)
            ppl = []
            if len(b):
                kp, sc = WB.pose_model(im, bboxes=b)
                for bb, k, s in zip(b, kp, sc):
                    ppl.append({"b": r(bb, 1).tolist(), "k": np.concatenate([r(k, 1), r(s, 3)[:, None]], 1).tolist()})
                det += 1
            f.write(json.dumps({"f": n, "p": ppl}, separators=(",", ":")) + "\n")
            n += 1
    cap.release()
    return f"{n} 프레임 사람 {det}"


# ---------- P2: RAFT-large 광류 + 캐릭터 가림 + 닮음 변환 RANSAC ----------
if TASK == "p2":
    import torch.nn.functional as F
    from torchvision.models.optical_flow import Raft_Large_Weights, raft_large

    DEV = "cuda" if torch.cuda.is_available() else "cpu"
    RAFT = raft_large(weights=Raft_Large_Weights.C_T_SKHT_V2).to(DEV).eval()
H, DET_EVERY, UPDATES, B = 368, 6, 6, 16


def prep(ims, w):
    t = torch.from_numpy(np.stack([cv2.cvtColor(cv2.resize(i, (w, H)), cv2.COLOR_BGR2RGB) for i in ims]))
    return (t.permute(0, 3, 1, 2).float() / 127.5 - 1).to(DEV)


def fit(flow, mask):
    hh, ww = flow.shape[:2]
    ys, xs = np.mgrid[4:hh:8, 4:ww:8]
    m = mask[ys, xs]
    if m.sum() < 30:
        return [0, 0, 0, 0, 0, 0]
    p0 = np.stack([xs[m], ys[m]], 1).astype(np.float32)
    p1 = p0 + flow[ys[m], xs[m]]
    A, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=1.5, maxIters=2000)
    med = float(np.median(np.linalg.norm(p1 - p0, axis=1)))
    if A is None:
        return [0, 0, 0, 0, 0, med]
    s = np.hypot(A[0, 0], A[1, 0])
    rot = np.arctan2(A[1, 0], A[0, 0])
    c = np.array([ww / 2, hh / 2])
    t = A[:, :2] @ c + A[:, 2] - c
    return [t[0] / ww, t[1] / ww, float(np.log(s)), float(rot), float(inl.mean()), med]


def run_p2(loc, dst):
    cap = cv2.VideoCapture(loc)
    fps = cap.get(cv2.CAP_PROP_FPS)
    ok, prev = cap.read()
    if not ok:
        return "빈 영상"
    h0, w0 = prev.shape[:2]
    w = int(round(w0 * H / h0 / 8)) * 8
    last = [None]

    def mask(im, i):
        if i % DET_EVERY == 0 or last[0] is None:
            b = np.asarray(WB.det_model(im)).reshape(-1, 4)
            c = (b[:, :2] + b[:, 2:]) / 2
            hw = (b[:, 2:] - b[:, :2]) * 0.55
            last[0] = np.concatenate([c - hw, c + hw], 1)
        mk = np.ones((H, w), bool)
        for x1, y1, x2, y2 in last[0] * [w / w0, H / h0, w / w0, H / h0]:
            mk[max(0, int(y1)):int(y2) + 1, max(0, int(x1)):int(x2) + 1] = False
        return mk, len(last[0])

    small = lambda im: cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (160, 90),  # noqa: E731
                                  interpolation=cv2.INTER_AREA).astype(np.int16)
    pm, n0 = mask(prev, 0)
    nb, fi, nstill = [n0], 1, 0
    cam = [[0] * 6]
    grid = [np.zeros((9, 16, 2), np.float16)]
    done = False
    while not done:
        cur = []
        while len(cur) < B:
            ok, im = cap.read()
            if not ok:
                done = True
                break
            cur.append(im)
        if not cur:
            break
        ms = [mask(im, fi + k) for k, im in enumerate(cur)]
        fi += len(cur)
        pairs = [prev] + cur
        # 애니의 정지 프레임(같은 그림 유지)은 광류를 계산하지 않고 카메라 정지로 기록한다
        moving = [k for k in range(len(cur)) if np.abs(small(pairs[k]) - small(pairs[k + 1])).mean() > 0.6]
        if moving:
            a = prep([pairs[k] for k in moving], w)
            b = prep([pairs[k + 1] for k in moving], w)
            with torch.no_grad():
                fl = RAFT(a, b, num_flow_updates=UPDATES)[-1]
            g = F.adaptive_avg_pool2d(fl, (9, 16)).permute(0, 2, 3, 1).cpu().numpy() / w
            fl = fl.permute(0, 2, 3, 1).cpu().numpy()
        masks = [pm] + [m for m, _ in ms]
        pos = {k: j for j, k in enumerate(moving)}
        for k in range(len(cur)):
            if k in pos:
                cam.append(fit(fl[pos[k]], masks[k] & masks[k + 1]))
                grid.append(g[pos[k]].astype(np.float16))
            else:
                nstill += 1
                cam.append([0, 0, 0, 0, 1.0, 0])
                grid.append(np.zeros((9, 16, 2), np.float16))
        nb += [n for _, n in ms]
        prev = cur[-1]
        pm = ms[-1][0]
    cap.release()
    with open(dst, "wb") as fh:
        np.savez_compressed(fh, cam=np.array(cam, np.float32), grid=np.stack(grid), boxes=np.array(nb), fps=fps,
                            size=[w0, h0])
    return f"{len(cam)} 프레임(정지 {nstill})"


def main():
    vids = []
    for d in DIRS:
        an = "yutaka_nakamura" if d.startswith("yutaka") else d
        done = set(rc("lsf", f"{OUT}/{an}").stdout.split())
        for rel in sorted(rc("lsf", "-R", "--files-only", "--include", "*.mp4", f"{SRC}/{d}").stdout.splitlines()):
            pid = os.path.basename(rel).split("_")[0].split(".")[0]
            if pid + EXT not in done:
                vids.append((f"{SRC}/{d}/{rel}", f"{OUT}/{an}/{pid}{EXT}"))
    mine = vids[WID::NW]
    log("남은 영상", len(vids), "내 몫", len(mine))
    t0 = time.time()
    for k, (src, dst) in enumerate(mine):
        t = time.time()
        loc = f"{TMP}/cur.mp4"
        out = f"{TMP}/out{EXT}"
        try:
            rc("copyto", src, loc)
            msg = (run_p1 if TASK == "p1" else run_p2)(loc, out)
            up = rc("copyto", out, dst)
            if up.returncode:
                log("올리기 실패", dst, up.stderr[-300:])
                continue
        except Exception:
            traceback.print_exc()
            continue
        log(k + 1, "/", len(mine), os.path.basename(dst), msg, round(time.time() - t), "초", "누적",
            round((time.time() - t0) / 60), "분")
    log("끝")


if __name__ == "__main__":
    main()
