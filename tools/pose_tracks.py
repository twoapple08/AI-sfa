"""RTMW 포즈(Kaggle·Colab 출력 jsonl.gz)를 컷별 사람 추적으로 정리한다.

사용: python tools/pose_tracks.py <포즈 jsonl.gz> <원본 영상> <출력 npz>
1. 컷 나누기: 원본 영상의 HSV 히스토그램 상관 < CUT_CORR 또는 회색조 정규화 상관 < CUT_NCC인 프레임.
2. 추적: 컷 안에서 앞 프레임 사람과 상자 IoU·몸 중심 거리로 헝가리안 대응. 2프레임 넘게 놓치면 끝낸다.
3. 정리(추적마다):
   - 신뢰도 낮은 점(KP_THR 미만), 화면 테두리(EDGE)의 점, 얼굴 클로즈업(CLOSEUP) 프레임의 몸·손·발 점은 비운다(NaN).
   - 좌우 뒤바뀜: 좌우를 바꾼 쪽이 앞 프레임과 훨씬 가까우면(SWAP_RATIO) 바꾼다(몸·손·발 묶음 단위).
   - 튀는 점: 앞뒤 프레임이 가깝고 가운데만 멀리 떨어진 점(몸 크기의 SPIKE배)은 비운다.
   - 빈칸 메우기: 추적 안 GAP 프레임 이하 빈칸만 직선 보간. 더 긴 빈칸은 그대로 둔다.
   - 멈춤(같은 그림 유지)은 동작 정보라 평활하지 않는다.
출력 npz: kp [추적, 최대길이, 133, 3](빈칸 NaN), start, length, shot, area(평균 상자 넓이), quality(QCOLS), cuts, fps, n_frames
원본 포즈·정리 결과는 다른 작가 영상에서 나온 자료라 저장소에 넣지 않는다(Drive·서버 임시 폴더만).
"""
import gzip
import warnings
import json
import sys

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

warnings.filterwarnings("ignore", category=RuntimeWarning)  # 빈 점(NaN)만 있는 구간의 평균·중앙값 경고
CUT_CORR = 0.55
CUT_NCC = 0.2  # 회색조 정규화 상관이 이보다 낮고 색 상관도 0.9 미만이면 컷(어두운 장면 컷 대응)
CLOSEUP = 0.25  # 얼굴 점 세로 폭이 화면 높이의 이 비율 이상이면 클로즈업 → 몸·손·발 점을 버린다
EDGE = 0.015  # 화면 테두리에서 이 비율 안쪽의 점은 화면 밖 추정값으로 보고 버린다
KP_THR = 1.0  # RTMW SimCC 점수(대략 0~10). P1 비교의 몸 점수 중앙값 2.5~3.4
SWAP_RATIO = 0.6
SPIKE = 0.35
GAP = 3
MAX_MISS = 2

# COCO-WholeBody 133점 좌우 짝: 몸 17(1-16), 발 6(17-22), 얼굴 68(23-90, 대칭), 손 21×2(91-111 왼, 112-132 오)
BODY_LR = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16), (17, 20), (18, 21), (19, 22)]
HAND_LR = [(91 + i, 112 + i) for i in range(21)]


def cuts(video):
    cap = cv2.VideoCapture(video)
    prev, pg, out, i = None, None, [0], 0
    fps = cap.get(cv2.CAP_PROP_FPS)
    while True:
        ok, im = cap.read()
        if not ok:
            break
        sm = cv2.resize(im, (160, 90))
        h = cv2.calcHist([cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)], [0, 1], None, [16, 8], [0, 180, 0, 256])
        cv2.normalize(h, h)
        g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None:
            corr = cv2.compareHist(prev, h, cv2.HISTCMP_CORREL)
            # 어두운 장면끼리는 색 분포가 비슷해 상관만으로는 컷을 놓친다 → 밝기 구조 차이(정규화 상관)도 본다
            a, b = g - g.mean(), pg - pg.mean()
            ncc = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
            if corr < CUT_CORR or (ncc < CUT_NCC and corr < 0.9):
                out.append(i)
        prev, pg, i = h, g, i + 1
    return out, fps, i


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def track(frames, cut_list, n):
    shot_of = np.searchsorted(cut_list, np.arange(n), side="right") - 1
    tracks, active = [], []  # track: dict(shot, start, kps list, boxes list, miss)
    for f in range(n):
        ppl = frames[f] if f < len(frames) else []
        if f in cut_list:
            active = []
        cost = np.ones((len(active), len(ppl)))
        for i, t in enumerate(active):
            for j, p in enumerate(ppl):
                b = t["boxes"][-1]
                c1 = np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])
                c2 = np.array([(p["b"][0] + p["b"][2]) / 2, (p["b"][1] + p["b"][3]) / 2])
                diag = np.hypot(b[2] - b[0], b[3] - b[1]) + 1e-6
                cost[i, j] = 1 - iou(b, p["b"]) + 0.5 * min(1.0, np.linalg.norm(c1 - c2) / diag)
        used = set()
        if len(active) and len(ppl):
            ri, ci = linear_sum_assignment(cost)
            for i, j in zip(ri, ci):
                if cost[i, j] < 1.2:
                    t = active[i]
                    t["kps"] += [None] * t["miss"] + [np.array(ppl[j]["k"], np.float32)]
                    t["boxes"] += [t["boxes"][-1]] * t["miss"] + [ppl[j]["b"]]
                    t["miss"] = 0
                    used.add(j)
                    t["hit"] = True
        for t in active:
            if not t.pop("hit", False):
                t["miss"] += 1
        active = [t for t in active if t["miss"] <= MAX_MISS]
        for j, p in enumerate(ppl):
            if j not in used:
                t = {"shot": int(shot_of[f]), "start": f, "kps": [np.array(p["k"], np.float32)], "boxes": [p["b"]],
                     "miss": 0}
                tracks.append(t)
                active.append(t)
    return tracks


def clean(K, W, H):
    """K [T,133,3] (빈 프레임 NaN). W·H는 화면 크기."""
    K = K.copy()
    K[K[..., 2] < KP_THR] = np.nan
    edge = (K[..., 0] < EDGE * W) | (K[..., 0] > (1 - EDGE) * W) | (K[..., 1] < EDGE * H) | (K[..., 1] > (1 - EDGE) * H)
    K[edge] = np.nan
    face = K[:, 23:91, 1]
    span = np.nanmax(face, 1) - np.nanmin(face, 1)
    close = np.isfinite(span) & (span > CLOSEUP * H)
    K[np.ix_(close, np.r_[5:23, 91:133])] = np.nan
    T = len(K)
    size = np.nanmedian(np.nanmax(K[:, :17, 1], 1) - np.nanmin(K[:, :17, 1], 1)) if T else 1.0
    size = size if np.isfinite(size) and size > 1 else 100.0
    nswap = nspike = nfill = 0
    for t in range(1, T):
        for group in (BODY_LR, HAND_LR):
            a = np.array([i for i, _ in group])
            b = np.array([j for _, j in group])
            cur, prv = K[t, :, :2], K[t - 1, :, :2]
            d0 = np.nanmean(np.r_[np.linalg.norm(cur[a] - prv[a], axis=1), np.linalg.norm(cur[b] - prv[b], axis=1)])
            d1 = np.nanmean(np.r_[np.linalg.norm(cur[b] - prv[a], axis=1), np.linalg.norm(cur[a] - prv[b], axis=1)])
            if np.isfinite(d0) and np.isfinite(d1) and d1 < SWAP_RATIO * d0 and d0 > 0.05 * size:
                K[t, np.r_[a, b]] = K[t, np.r_[b, a]]
                nswap += 1
    for t in range(1, T - 1):
        p, c, n = K[t - 1, :, :2], K[t, :, :2], K[t + 1, :, :2]
        near = np.linalg.norm(p - n, axis=1) < SPIKE * size / 2
        far = (np.linalg.norm(c - p, axis=1) > SPIKE * size) & (np.linalg.norm(c - n, axis=1) > SPIKE * size)
        bad = near & far
        if bad.any():
            K[t, bad] = np.nan
            nspike += int(bad.sum())
    for j in range(K.shape[1]):
        ok = np.isfinite(K[:, j, 0])
        idx = np.where(ok)[0]
        for a, b in zip(idx, idx[1:]):
            if 1 < b - a <= GAP + 1:
                w = np.linspace(0, 1, b - a + 1)[1:-1, None]
                K[a + 1:b, j] = K[a, j] * (1 - w) + K[b, j] * w
                nfill += b - a - 1
    return K, (nswap, nspike, nfill)


QCOLS = ["몸점수_중앙", "몸점_보임비율", "팔다리비_이탈"]


def track_quality(K):
    """사람다움 지표(지우지 않고 붙여 둔다. 학습 자료를 고를 때 거른다).
    팔다리비_이탈: 위팔/아래팔, 넓적다리/정강이, 어깨폭/엉덩이폭 비의 로그가 사람 표준(1, 1, 1.4)에서 벗어난 정도의 중앙값."""
    body = K[:, 5:17]
    sc = float(np.nanmedian(body[..., 2])) if np.isfinite(body[..., 2]).any() else 0.0
    vis = float(np.isfinite(body[..., 0]).mean())
    L = lambda a, b: np.linalg.norm(K[:, a, :2] - K[:, b, :2], axis=1)  # noqa: E731
    r = np.stack([np.log((L(5, 7) + L(6, 8)) / (L(7, 9) + L(8, 10))),
                  np.log((L(11, 13) + L(12, 14)) / (L(13, 15) + L(14, 16))),
                  np.log(L(5, 6) / L(11, 12) / 1.4)], 1)
    dev = float(np.nanmedian(np.abs(r))) if np.isfinite(r).any() else np.nan
    return [sc, vis, dev]


def main():
    pose, video, out = sys.argv[1:4]
    frames = [json.loads(l)["p"] for l in gzip.open(pose, "rt")]
    cut_list, fps, n = cuts(video)
    cap = cv2.VideoCapture(video)
    W, H = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    n = max(n, len(frames))
    trs = [t for t in track(frames, cut_list, n) if len([k for k in t["kps"] if k is not None]) >= 6]
    L = max((len(t["kps"]) for t in trs), default=1)
    kp = np.full((len(trs), L, 133, 3), np.nan, np.float32)
    stats = np.zeros(3, int)
    for i, t in enumerate(trs):
        K = np.stack([k if k is not None else np.full((133, 3), np.nan, np.float32) for k in t["kps"]])
        K, st = clean(K, W, H)
        kp[i, :len(K)] = K
        stats += st
    area = [float(np.mean([(b[2] - b[0]) * (b[3] - b[1]) for b in t["boxes"]])) for t in trs]
    quality = [track_quality(kp[i, :len(t["kps"])]) for i, t in enumerate(trs)]
    np.savez_compressed(out, kp=kp, start=[t["start"] for t in trs], length=[len(t["kps"]) for t in trs],
                        shot=[t["shot"] for t in trs], area=area, quality=np.array(quality, np.float32),
                        quality_cols=np.array(QCOLS), cuts=cut_list, fps=fps, n_frames=n)
    print(json.dumps({"frames": n, "cuts": len(cut_list), "tracks": len(trs),
                      "swap": int(stats[0]), "spike_pts": int(stats[1]), "filled_pts": int(stats[2])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
