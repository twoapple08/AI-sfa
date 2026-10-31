"""학습된 2D→3D 올리기 모델(tools/lift_train.py)을 정리된 애니 포즈 추적(tools/pose_tracks.py)에 적용한다.

사용: python tools/lift_apply.py <lifter.pt> <tracks_all 폴더> <출력 폴더> [--min-score 2.8] [--min-len 12]
- 대상: 몸점수_중앙 ≥ min-score 이고 길이 ≥ min-len 인 추적(pose_tracks.KEEP_SCORE 기준).
- 입력 만들기는 학습과 같다: COCO 몸 17점, 골반(엉덩이 가운데) 중심, 몸 크기(엉덩이-어깨 가운데 거리 중앙값) 1,
  빠진 점은 (0, 0, 보임 0). 화면 y는 아래로 증가(학습 투영과 같은 방향).
- 창(학습 창 길이)을 절반씩 겹쳐 돌리고 겹친 프레임은 가운데에 가중을 둬 평균한다. 추적이 창보다 짧으면 끝 프레임을 반복해 채운다.
- 후처리: 뼈 길이를 추적별 중앙값으로 고정(기본 켬, --no-bone-fix로 끔). --smooth k로 시간축 이동평균(기본 끔).
- 출력: <출력>/<애니메이터>/<post_id>.npz — y3d [추적, 최대길이, 18, 3](카메라 좌표 미터, 골반 기준, 빈칸 NaN),
  track(원래 추적 번호), start, length, fps. 몸 2D가 비어 있던 프레임은 NaN으로 남긴다.
원본 영상에서 나온 결과라 저장소에 넣지 않는다(Drive·서버 임시 폴더만).
"""
import argparse
import glob
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lift_train import Lifter  # noqa: E402


def norm_input(K):
    """K [T,133,3] (NaN 빈칸) → [T,17,3] (x, y, 보임), 학습과 같은 정규화."""
    X = K[:, :17, :2].astype(np.float32)
    vis = np.isfinite(X).all(-1)
    hip = (X[:, 11] + X[:, 12]) / 2
    sh = (X[:, 5] + X[:, 6]) / 2
    s = np.nanmedian(np.linalg.norm(sh - hip, axis=1))
    if not np.isfinite(s) or s < 1:
        return None
    hipf = hip.copy()
    ok = np.isfinite(hipf).all(1)
    if not ok.any():
        return None
    idx = np.arange(len(hipf))
    for k in range(2):  # 골반이 빈 프레임은 앞뒤에서 보간
        hipf[:, k] = np.interp(idx, idx[ok], hipf[ok, k])
    Xn = (X - hipf[:, None]) / s
    Xn[~vis] = 0
    return np.concatenate([Xn, vis[..., None].astype(np.float32)], -1)


def run(model, X, win, dev):
    T = len(X)
    if T < win:
        X = np.concatenate([X, np.repeat(X[-1:], win - T, 0)])
    starts = list(range(0, len(X) - win + 1, win // 2))
    if starts[-1] != len(X) - win:
        starts.append(len(X) - win)
    w = np.hanning(win + 2)[1:-1].astype(np.float32)
    acc = np.zeros((len(X), 18, 3), np.float32)
    wsum = np.zeros(len(X), np.float32)
    with torch.no_grad():
        batch = torch.from_numpy(np.stack([X[s:s + win] for s in starts])).to(dev)
        Y = model(batch).cpu().numpy()
    for s, y in zip(starts, Y):
        acc[s:s + win] += y * w[:, None, None]
        wsum[s:s + win] += w
    return (acc / wsum[:, None, None])[:T]


PARENTS = [-1, 0, 1, 2, 2, 2, 4, 5, 6, 7, 0, 0, 10, 11, 12, 13, 14, 15]  # mocap_unify.PARENTS


def fix_bones(Y):
    """뼈 길이를 추적 전체 중앙값으로 고정한다(골반에서 바깥쪽으로, 뼈 방향은 그대로). Y [T,18,3], NaN 프레임은 그대로."""
    ok = np.isfinite(Y).all((1, 2))
    if ok.sum() < 2:
        return Y
    L = np.array([np.median(np.linalg.norm(Y[ok, j] - Y[ok, p], axis=1)) if p >= 0 else 0
                  for j, p in enumerate(PARENTS)])
    Z = Y.copy()
    for j, p in enumerate(PARENTS):  # 부모가 항상 앞 번호라 순서대로 다시 쌓으면 된다
        if p < 0:
            continue
        d = Y[ok, j] - Y[ok, p]
        n = np.linalg.norm(d, axis=1, keepdims=True)
        Z[ok, j] = Z[ok, p] + d / np.maximum(n, 1e-6) * L[j]
    return Z


def smooth_time(Y, k):
    """k프레임(홀수) 중앙 이동평균. 빠름·멈춤 타이밍을 무디게 하므로 기본은 끈다."""
    if k <= 1 or len(Y) < k:
        return Y
    pad = np.concatenate([np.repeat(Y[:1], k // 2, 0), Y, np.repeat(Y[-1:], k // 2, 0)])
    c = np.cumsum(np.concatenate([np.zeros((1,) + Y.shape[1:], Y.dtype), pad]), 0)
    return (c[k:] - c[:-k]) / k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("tracks")
    ap.add_argument("out")
    ap.add_argument("--min-score", type=float, default=2.8)
    ap.add_argument("--min-len", type=int, default=12)
    ap.add_argument("--no-bone-fix", action="store_true", help="뼈 길이 고정을 끈다")
    ap.add_argument("--smooth", type=int, default=0, help="시간축 이동평균 프레임 수(홀수, 0=끔)")
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    st = torch.load(a.ckpt, map_location=dev)
    win = st["win"]
    model = Lifter(win).to(dev)
    model.load_state_dict(st["model"])
    model.eval()
    print("모델 단계", st["step"], "창", win, "장치", dev)
    n_tr = n_fr = 0
    for f in sorted(glob.glob(os.path.join(a.tracks, "*", "*.npz"))):
        z = np.load(f)
        if z["quality"].ndim < 2:
            continue
        an, pid = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-4]
        keep = [i for i, (L, q) in enumerate(zip(z["length"], z["quality"])) if q[0] >= a.min_score and L >= a.min_len]
        if not keep:
            continue
        outs, starts, lens, used = [], [], [], []
        for i in keep:
            L = int(z["length"][i])
            K = z["kp"][i, :L]
            X = norm_input(K)
            if X is None:
                continue
            Y = smooth_time(run(model, X, win, dev), a.smooth)
            if not a.no_bone_fix:
                Y = fix_bones(Y)
            Y[np.isfinite(K[:, :17, 0]).sum(1) < 6] = np.nan  # 몸 2D가 거의 빈 프레임
            outs.append(Y)
            used.append(i)
            starts.append(int(z["start"][i]))
            lens.append(L)
        if not outs:
            continue
        M = max(lens)
        y3d = np.full((len(outs), M, 18, 3), np.nan, np.float32)
        for k, Y in enumerate(outs):
            y3d[k, :len(Y)] = Y
        os.makedirs(os.path.join(a.out, an), exist_ok=True)
        np.savez_compressed(os.path.join(a.out, an, pid + ".npz"), y3d=y3d, track=np.array(used),
                            start=np.array(starts), length=np.array(lens), fps=z["fps"])
        n_tr += len(outs)
        n_fr += sum(lens)
    print("추적", n_tr, "프레임", n_fr)


if __name__ == "__main__":
    main()
