"""파편 영상에서 조각별 크기·방향·속도·감속·멈춤·회전·면 색을 잰다(P4).

사용: python tools/debris_measure.py <영상> <출력 json> [--start 22] [--bg-thr 28] [--min-area 20]
- 바탕: 첫 프레임 가장자리 색의 중앙값(단색 바탕 가정).
- 조각: 바탕과 색 차이 > bg-thr 인 픽셀의 연결 요소(넓이 ≥ min-area). 마지막 프레임에서 화면 중심에 가장 가까운
  큰 요소(남은 큐브)는 가림판으로 빼고, 가림판과 겹치는 요소는 조각에서 뺀다.
- 추적: start 프레임부터 앞 프레임 조각 중심과의 거리로 헝가리안 대응(거리 상한 = 앞 속도 + 40px).
- 조각별: 처음 위치(폭발 중심 기준 각도·거리), 크기(√넓이), 초기 속도(처음 3프레임), 속도 반감 프레임,
  멈춤 프레임(속도 < 0.5px/프레임 2연속), 누적 회전(최소 외접 사각형 각도 변화, 90° 모호성 보정), 면 색 3톤(밝음·중간·어두움).
좌표는 화면 높이 1 기준으로도 함께 낸다. 원본 영상은 저장소에 넣지 않고 통계만 둔다.
"""
import argparse
import json

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

CHUNK = 0.01  # 화면 높이 대비 크기(√넓이) 이상이면 덩어리, 미만이면 먼지


def frames(path):
    c = cv2.VideoCapture(path)
    out = []
    while True:
        ok, im = c.read()
        if not ok:
            break
        out.append(im)
    return out, c.get(cv2.CAP_PROP_FPS)


def comps(im, bg, thr, min_area, block=None):
    d = np.abs(im.astype(np.int16) - bg.astype(np.int16)).max(-1)
    m = (d > thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    out = []
    for i in range(1, n):
        if st[i, 4] < min_area:
            continue
        mk = lab == i
        if block is not None and (mk & block).sum() > 0.3 * mk.sum():
            continue
        ys, xs = np.nonzero(mk)
        rect = cv2.minAreaRect(np.stack([xs, ys], 1).astype(np.float32))
        out.append({"c": cen[i].tolist(), "area": int(st[i, 4]), "angle": float(rect[2]),
                    "pix": im[mk].reshape(-1, 3)})
    return out


def tones(pix):
    if len(pix) < 9:
        return None
    g = pix.mean(1)
    q = np.percentile(g, [15, 50, 85])
    return [np.median(pix[np.abs(g - v) <= np.abs(g - v).min() + 8], 0).round().tolist() for v in q]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--start", type=int, default=22)
    ap.add_argument("--bg-thr", type=int, default=28)
    ap.add_argument("--min-area", type=int, default=20)
    a = ap.parse_args()
    F, fps = frames(a.video)
    H, W = F[0].shape[:2]
    edge = np.concatenate([F[0][0], F[0][-1], F[0][:, 0], F[0][:, -1]])
    bg = np.median(edge, 0)
    # 남은 큐브(가림판): 마지막 프레임에서 중심에 가장 가까운 큰 요소
    d = np.abs(F[-1].astype(np.int16) - bg.astype(np.int16)).max(-1)
    n, lab, st, cen = cv2.connectedComponentsWithStats(cv2.morphologyEx((d > a.bg_thr).astype(np.uint8),
                                                                        cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)), 8)
    big = [i for i in range(1, n) if st[i, 4] > 0.01 * H * W]
    ci = min(big, key=lambda i: np.linalg.norm(cen[i] - [W / 2, H / 2]))
    block = cv2.dilate((lab == ci).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    center = cen[ci]
    tracks, active = [], []
    for f in range(a.start, len(F)):
        cs = comps(F[f], bg, a.bg_thr, a.min_area, block)
        used = set()
        if active and cs:
            C = np.array([[np.linalg.norm(np.subtract(t["c"][-1], c["c"])) for c in cs] for t in active])
            ri, cj = linear_sum_assignment(C)
            for i, j in zip(ri, cj):
                t = active[i]
                v = np.linalg.norm(np.subtract(t["c"][-1], t["c"][-2])) if len(t["c"]) > 1 else 60
                if C[i, j] < v + 40:
                    t["c"].append(cs[j]["c"]); t["area"].append(cs[j]["area"]); t["angle"].append(cs[j]["angle"])
                    t["pix"].append(cs[j]["pix"]); t["end"] = f; used.add(j)
        active = [t for t in active if t["end"] == f]
        for j, c in enumerate(cs):
            if j not in used:
                t = {"start": f, "end": f, "c": [c["c"]], "area": [c["area"]], "angle": [c["angle"]], "pix": [c["pix"]]}
                tracks.append(t); active.append(t)
    res = []
    for t in tracks:
        P = np.array(t["c"])
        if len(P) < 4:
            continue
        v = np.linalg.norm(np.diff(P, axis=0), axis=1)
        v0 = float(v[:3].mean())
        half = next((i for i, x in enumerate(v) if x < v0 / 2), None)
        stop = next((i for i in range(len(v) - 1) if v[i] < 0.5 and v[i + 1] < 0.5), None)
        ang = np.unwrap(np.radians(np.array(t["angle"])) * 4) / 4  # minAreaRect 90° 모호성
        rel = P[0] - center
        res.append({"start": t["start"], "frames": len(P), "size_px": float(np.sqrt(np.median(t["area"]))),
                    "size_h": float(np.sqrt(np.median(t["area"])) / H),
                    "dir_deg": float(np.degrees(np.arctan2(-(P[min(3, len(P) - 1)] - P[0])[1],
                                                           (P[min(3, len(P) - 1)] - P[0])[0]))),
                    "start_dist_h": float(np.linalg.norm(rel) / H), "v0_h_per_frame": v0 / H,
                    "half_life_frames": half, "stop_frame": None if stop is None else t["start"] + stop,
                    "travel_h": float(np.linalg.norm(P[-1] - P[0]) / H),
                    "rot_deg": float(np.degrees(np.abs(ang[-1] - ang[0]))),
                    "tones_bgr": tones(np.concatenate(t["pix"][:3]))})
    q = lambda x: [round(float(v), 4) for v in np.percentile(x, [10, 50, 90])] if len(x) else None  # noqa: E731

    def stats(rs):
        sz = np.array([r["size_h"] for r in rs]); v0 = np.array([r["v0_h_per_frame"] for r in rs])
        hl = np.array([r["half_life_frames"] for r in rs if r["half_life_frames"] is not None])
        stops = np.array([r["stop_frame"] for r in rs if r["stop_frame"] is not None])
        return {"count": len(rs), "size_h_p10_50_90": q(sz), "v0_h_per_frame_p10_50_90": q(v0),
                "half_life_frames_p10_50_90": q(hl), "stop_frame_p10_50_90": q(stops),
                "stopped_ratio": round(len(stops) / max(len(rs), 1), 2),
                "travel_h_p10_50_90": q(np.array([r["travel_h"] for r in rs])),
                "rot_deg_p10_50_90": q(np.array([r["rot_deg"] for r in rs])),
                "dir_hist_8_from_east_ccw": np.histogram([r["dir_deg"] % 360 for r in rs], 8, (0, 360))[0].tolist(),
                "first_frame_p10_50_90": q(np.array([r["start"] for r in rs])),
                "size_v0_corr": round(float(np.corrcoef(sz, v0)[0, 1]), 3) if len(rs) > 2 else None}

    summary = {"video_frames": len(F), "fps": fps, "size": [W, H], "bg_bgr": bg.round().tolist(),
               "center_px": center.round(1).tolist(), "chunk_min_size_h": CHUNK,
               "chunks": stats([r for r in res if r["size_h"] >= CHUNK]),
               "dust": stats([r for r in res if r["size_h"] < CHUNK])}
    json.dump({"summary": summary, "fragments": res}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
