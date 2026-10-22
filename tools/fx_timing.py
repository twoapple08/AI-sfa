#!/usr/bin/env python3
"""이펙트 시간 변화 재기: Kaggle 이펙트 분리 결과(tools/kaggle_fx_worker.py 마스크)로 이펙트가 어떻게 나타나·커지고·갈라지고·사라지는지 잰다.

사용: python tools/fx_timing.py <마스크 npz 폴더> <나카무라 영상 폴더> <구간 csv> <출력 json>
- 구간 csv: data/p3/fx_segments_2026-10-22.csv(post_id,start,end,tags,exclude). exclude가 있는 구간(제작 자료)은 뺀다.
  마스크는 _v3 → _v2 → 무표시 순으로 있는 것을 쓴다. 종류는 구간에 붙은 태그 각각으로 센다.
- 프레임 지표(이펙트 마스크 안, 높이 540):
  면적 비율, 덩어리 수(30px 이상 연결 요소), 밝기(HSV V 평균)·채도 평균, 무게중심 이동(화면 높이 단위),
  새 그림 여부: 앞 프레임과 흔들림 보정(위상 상관) 뒤 15단계 넘게 바뀐 픽셀이 마스크의 20% 초과
  (tools/strike_timing.py와 같은 기준, nian41 손 계수로 검증한 값).
- 수명(이펙트가 이어지는 구간: 면적 ≥ 0.5%가 3프레임 이상): 길이, 정점(최대 면적)까지 프레임, 정점 면적,
  정규화 곡선(수명을 10칸으로 나눠 면적/정점·밝기), 덩어리가 늘어난 횟수(갈라짐), 그림 유지 길이 분포.
출력은 집계값만(저장소 가능). 마스크·프레임은 원본 유래라 Drive에만 둔다.
"""
import csv
import glob
import json
import os
import sys

import cv2
import numpy as np

H = 540
PIX_EPS = 20.0
MIN_AREA = 0.005


def load_mask(p):
    z = np.load(p)
    shp = tuple(int(v) for v in z["shape"])
    return np.unpackbits(z["mask"], axis=-1)[..., :shp[2]].astype(bool), z["frames"]


def read_frames(video, frames, W):
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frames[0]))
    out = []
    for _ in frames:
        ok, im = cap.read()
        if not ok:
            break
        out.append(cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA))
    return out


def frame_stats(M, imgs):
    n = min(len(M), len(imgs))
    rows = []
    prev = None
    for i in range(n):
        m = M[i]
        a = float(m.mean())
        nc = 0
        if m.any():
            k, _, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
            nc = int((st[1:, cv2.CC_STAT_AREA] >= 30).sum())
        hsv = cv2.cvtColor(imgs[i], cv2.COLOR_BGR2HSV)
        v = float(hsv[..., 2][m].mean()) if m.any() else np.nan
        s = float(hsv[..., 1][m].mean()) if m.any() else np.nan
        ys, xs = np.nonzero(m)
        c = (float(xs.mean()) / H, float(ys.mean()) / H) if len(xs) else (np.nan, np.nan)
        new = np.nan
        g = cv2.cvtColor(imgs[i], cv2.COLOR_BGR2GRAY).astype(np.float32)
        if prev is not None and (m | M[i - 1]).any():
            pg = prev
            (dx, dy), _ = cv2.phaseCorrelate(pg, g)
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                pg = cv2.warpAffine(pg, np.float32([[1, 0, dx], [0, 1, dy]]), (g.shape[1], g.shape[0]), borderMode=cv2.BORDER_REPLICATE)
            u = m | M[i - 1]
            new = float((np.abs(g - pg)[u] > 15).mean() * 100 > PIX_EPS)
        prev = g
        rows.append((a, nc, v, s, c[0], c[1], new))
    return np.array(rows, float)


def lives(F):
    on = F[:, 0] >= MIN_AREA
    out, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j + 1 < len(on) and on[j + 1]:
                j += 1
            if j - i + 1 >= 3:
                out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def life_stats(F, a, b):
    L = F[a:b + 1]
    area = L[:, 0]
    pk = int(area.argmax())
    t = np.linspace(0, 1, len(L))
    bins = np.linspace(0, 1, 11)
    curve = [float(np.nanmean(area[(t >= bins[k]) & (t <= bins[k + 1])]) / area.max()) for k in range(10)]
    bright = [float(np.nanmean(L[(t >= bins[k]) & (t <= bins[k + 1]), 2])) for k in range(10)]
    new = np.where(np.isnan(L[:, 6]), 0, L[:, 6])
    idx = np.nonzero(new)[0]
    holds = np.diff(idx).tolist() if len(idx) > 1 else []
    splits = int((np.diff(L[:, 1]) > 0).sum())
    move = np.nansum(np.hypot(np.diff(L[:, 4]), np.diff(L[:, 5])))
    return {"len": len(L), "to_peak": pk, "peak_area": float(area.max()), "curve": curve, "bright": bright,
            "holds": holds, "splits": splits, "move_per_frame": float(move / max(1, len(L) - 1))}


def q(v):
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], float)
    if not len(v):
        return None
    return {"n": int(len(v)), "중앙": round(float(np.median(v)), 3), "사분위": [round(float(x), 3) for x in np.percentile(v, [25, 75])]}


def main():
    mdir, vdir, seg_csv, out = sys.argv[1:5]
    segs = list(csv.DictReader(open(seg_csv, encoding="utf-8-sig")))
    by_type = {}
    n_seg = 0
    for s in segs:
        if s.get("exclude"):  # 제작 자료 영상(다른 작가 원화 표기 섞임)은 뺀다
            continue
        p = next((q for q in (os.path.join(mdir, f"{s['post_id']}_{s['start']}{v}.npz") for v in ("_v3", "_v2", ""))
                  if os.path.exists(q)), "")
        v = glob.glob(os.path.join(vdir, s["post_id"] + "*.mp4"))
        if not os.path.exists(p) or not v:
            continue
        M, frames = load_mask(p)
        imgs = read_frames(v[0], frames, M.shape[2])
        F = frame_stats(M, imgs)
        n_seg += 1
        for a, b in lives(F):
            st = life_stats(F, a, b)
            for t in s["tags"].split(";"):
                by_type.setdefault(t, []).append(st)
    res = {"segments_used": n_seg, "min_area": MIN_AREA, "pix_eps": PIX_EPS, "types": {}}
    for t, L in by_type.items():
        hold = np.array([h for x in L for h in x["holds"]], int)
        res["types"][t] = {
            "수명수": len(L), "길이(프레임)": q([x["len"] for x in L]), "정점까지(프레임)": q([x["to_peak"] for x in L]),
            "정점면적(화면비)": q([x["peak_area"] for x in L]), "갈라짐(덩어리 증가 횟수)": q([x["splits"] for x in L]),
            "무게중심 이동(화면높이/프레임)": q([x["move_per_frame"] for x in L]),
            "면적곡선(정점=1, 수명 10칸)": np.round(np.nanmean([x["curve"] for x in L], 0), 3).tolist(),
            "밝기곡선(V, 수명 10칸)": np.round(np.nanmean([x["bright"] for x in L], 0), 1).tolist(),
            "그림유지": ({f"{k}s": round(float((hold == k).mean()), 3) for k in (1, 2, 3, 4)} |
                       {"5s+": round(float((hold >= 5).mean()), 3), "n": int(len(hold))}) if len(hold) else None}
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
