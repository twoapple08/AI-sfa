"""P2 카메라 값(프레임별 닮음 변환)으로 임팩트 앞뒤 카메라 움직임 패턴을 잰다.

사용: python tools/camera_impact.py <P2 npz 폴더(애니메이터)> <임팩트 판정 csv> <애니메이터> <출력 json> [--win 24]
- 임팩트: impact_classify의 training='사용' 행. 시작 프레임을 0으로 둔다.
- 프레임별 지표(화면 너비 대비): 이동 |t|, 확대 |log s|, 회전 |r|(도), 흔들림 = 이동 방향이 앞 프레임과 반대(내적<0)이면서 |t|>0.002.
- 정지(같은 그림, P2에서 inlier=1·흐름 0)는 움직임 0으로 센다. 임팩트 프레임 자체(+1프레임)와 inlier < 0.5인 프레임은 뺀다
  (섬광·실루엣으로 그림이 통째로 바뀌면 광류가 가짜 카메라 움직임을 낸다).
- 비교 기준: 같은 영상들에서 임팩트 ±2초 밖 무작위 창의 평균.
- 출력: 시간(-win~+win)별 평균 곡선, 임팩트 직후 0~6프레임 / 직전 -12~-1 / 기준의 비, 종류(실루엣·단색섬광)별.
"""
import argparse
import csv
import json
import os

import numpy as np


def feats(cam):
    t = np.hypot(cam[:, 0], cam[:, 1])
    s = np.abs(cam[:, 2])
    r = np.degrees(np.abs(cam[:, 3]))
    d = cam[:, :2]
    rev = np.r_[False, (np.sum(d[1:] * d[:-1], 1) < 0) & (t[1:] > 0.002) & (t[:-1] > 0.002)]
    F = np.stack([t, s, r, rev.astype(float)], 1)
    F[cam[:, 4] < INLIER] = np.nan  # 카메라 추정이 불안정한 프레임(섬광·화면 전체 변화)은 뺀다
    return F


NAMES = ["이동", "확대", "회전", "흔들림"]
INLIER = 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("p2")
    ap.add_argument("impacts")
    ap.add_argument("animator")
    ap.add_argument("out")
    ap.add_argument("--win", type=int, default=24)
    a = ap.parse_args()
    W = a.win
    rows = [x for x in csv.DictReader(open(a.impacts, encoding="utf-8-sig"))
            if x["training"] == "사용" and x["animator"] == a.animator]
    rng = np.random.default_rng(0)
    seg = {"전체": [], "맞음_실루엣": [], "맞음_단색섬광": []}
    base = []
    by_vid = {}
    for x in rows:
        f0, f1 = (int(v) for v in x["frames"].split("-"))
        by_vid.setdefault(x["post_id"], []).append((f0, x["verdict"], f1))
    for pid, evs in by_vid.items():
        p = os.path.join(a.p2, pid + ".npz")
        if not os.path.exists(p):
            continue
        F = feats(np.load(p)["cam"])
        n = len(F)
        for f0, v, f1 in evs:
            if f0 - W < 0 or f0 + W >= n:
                continue
            w = F[f0 - W:f0 + W + 1].copy()
            w[W:W + (f1 - f0) + 2] = np.nan  # 임팩트 프레임 자체와 바로 다음 프레임(그림이 통째로 바뀜)은 뺀다
            seg["전체"].append(w)
            if v in seg:
                seg[v].append(w)
        far = np.ones(n, bool)
        for f0, _, _ in evs:
            far[max(0, f0 - 48):f0 + 48] = False
        cand = np.where(far[W:n - W])[0] + W
        for c in rng.choice(cand, min(len(cand), 5), replace=False) if len(cand) else []:
            base.append(F[c - W:c + W + 1])
    B = np.nanmean(np.concatenate(base), 0)
    out = {"animator": a.animator, "win": W, "baseline_per_frame": dict(zip(NAMES, B.round(5).tolist())),
           "baseline_windows": len(base)}
    for k, ws in seg.items():
        if not ws:
            continue
        S = np.stack(ws)  # [이벤트, 2W+1, 4]
        m = np.nanmean(S, 0)
        pre = np.nanmean(S[:, W - 12:W], (0, 1))
        post = np.nanmean(S[:, W:W + 7], (0, 1))
        late = np.nanmean(S[:, W + 7:], (0, 1))
        out[k] = {"events": len(ws),
                  "직전_-12~-1_대비기준": dict(zip(NAMES, (pre / B).round(2).tolist())),
                  "직후_0~6_대비기준": dict(zip(NAMES, (post / B).round(2).tolist())),
                  "이후_7~24_대비기준": dict(zip(NAMES, (late / B).round(2).tolist())),
                  "정점_프레임(임팩트 기준)": dict(zip(NAMES, (np.nanargmax(m, 0) - W).tolist())),
                  "직후_유효_비율": round(float(np.isfinite(S[:, W:W + 7, 0]).mean()), 2),
                  "curve": {nm: m[:, i].round(5).tolist() for i, nm in enumerate(NAMES)}}
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    for k in seg:
        if k in out:
            print(k, out[k]["events"], "직전", out[k]["직전_-12~-1_대비기준"], "직후", out[k]["직후_0~6_대비기준"],
                  "이후", out[k]["이후_7~24_대비기준"], "정점", out[k]["정점_프레임(임팩트 기준)"])
    print("기준", out["baseline_per_frame"])


if __name__ == "__main__":
    main()
