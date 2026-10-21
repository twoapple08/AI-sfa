"""애니 파편 장면의 움직임 리듬을 잰다(P4). 조각 하나하나 대신 '카메라를 뺀 작은 움직임 덩어리'의 시간 변화를 본다.

사용: python tools/debris_scene.py <구간 json [[post_id, 요소, 시작초, 끝초], ...]> <영상 폴더> <출력 json>
- 구간: GPT 공백 확인 근거(evidence)의 '폭발 파편'·'붕괴' 초 단위 구간(앞뒤 0.2초 여유).
- 프레임 사이 광류(Farneback, 높이 360)에서 격자점 닮음 변환(RANSAC)을 카메라로 보고 빼, 남은 움직임 > 2px 픽셀의
  연결 요소 중 넓이 0.005%~1.5%를 '작은 움직임 덩어리'로 센다(파편·먼지·작은 물체; 인물 큰 덩어리는 넓이로 거른다).
- 멈춤: 앞 프레임과 거의 같은 프레임(회색조 평균 차 < 0.6)은 2컷·3컷 유지로 센다. 새 그림이 나올 때만 재고,
  그 이동을 지난 프레임 수로 나눠 유지 프레임들에 같은 속도로 채운다(작화 속도를 프레임당으로 맞춤).
- 구간별: 덩어리 수·속도(화면 높이 대비, 프레임당) 시간열, 최고 속도 프레임, 최고 뒤 속도 반감 프레임, 멈춤 비율.
영상 원본은 저장소에 넣지 않는다. 통계만 둔다.
"""
import glob
import json
import os
import sys

import cv2
import numpy as np

H = 360


def gray(im):
    h, w = im.shape[:2]
    return cv2.cvtColor(cv2.resize(im, (int(w * H / h), H)), cv2.COLOR_BGR2GRAY)


def small(g):
    return cv2.resize(g, (160, 90), interpolation=cv2.INTER_AREA).astype(np.int16)


def camera_residual(a, b):
    fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    hh, ww = a.shape
    ys, xs = np.mgrid[4:hh:8, 4:ww:8]
    p0 = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
    p1 = p0 + fl[ys.ravel(), xs.ravel()]
    A, _ = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC, ransacReprojThreshold=1.5)
    if A is None:
        return fl
    gy, gx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    cam = np.stack([A[0, 0] * gx + A[0, 1] * gy + A[0, 2] - gx, A[1, 0] * gx + A[1, 1] * gy + A[1, 2] - gy], -1)
    return fl - cam


def measure(video, t0, t1):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int((t0 - 0.2) * fps)))
    n = int((t1 - t0 + 0.4) * fps)
    prev, rows, holds, gap = None, [], 0, 1
    for _ in range(n):
        ok, im = cap.read()
        if not ok:
            break
        g = gray(im)
        if prev is not None:
            if np.abs(small(g) - small(prev)).mean() < 0.6:  # P2와 같은 기준(160×90)
                holds += 1
                gap += 1  # 같은 그림 유지: 다음 새 그림의 이동을 지난 프레임 수로 나눈다
                continue
            r = camera_residual(prev, g)
            mag = np.linalg.norm(r, axis=-1)
            m = (mag > 2).astype(np.uint8)
            k, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
            area = st[1:, 4] / m.size
            keep = np.where((area > 5e-5) & (area < 0.015))[0] + 1
            sp = [float(np.median(mag[lab == i])) / H / gap for i in keep]
            rows += [(len(keep), float(np.median(sp)) if sp else 0.0)] * gap  # 유지 프레임에도 같은 속도
            gap = 1
        prev = g
    if len(rows) < 3:
        return None
    cnt = np.array([r[0] for r in rows])
    spd = np.array([r[1] for r in rows])
    spd = np.convolve(np.pad(spd, 1, mode="edge"), np.ones(3) / 3, mode="valid")  # 한 프레임 섬광 튐 완화
    pk = int(spd.argmax())
    half = next((i - pk for i in range(pk, len(spd)) if spd[i] < spd[pk] / 2), None)
    return {"frames": len(rows), "fps": fps, "hold_ratio": round(holds / len(rows), 3),
            "peak_speed_h": round(float(spd[pk]), 4), "peak_frame": pk, "half_after_peak_frames": half,
            "blob_count_median": float(np.median(cnt)), "blob_count_max": int(cnt.max()),
            "speed_series_h": [round(float(x), 4) for x in spd], "count_series": cnt.tolist()}


def main():
    iv, vdir, out = sys.argv[1:4]
    res = []
    for pid, el, a, b in json.load(open(iv)):
        v = glob.glob(os.path.join(vdir, "**", f"{pid}_*.mp4"), recursive=True) + \
            glob.glob(os.path.join(vdir, "**", f"{pid}.mp4"), recursive=True)
        if not v:
            continue
        m = measure(v[0], a, b)
        if m:
            res.append({"post_id": pid, "element": el, "t0": a, "t1": b, **m})
            print(pid, el, a, b, m["frames"], m["hold_ratio"], m["peak_speed_h"], m["half_after_peak_frames"], flush=True)
    summ = {}
    for el in sorted({r["element"] for r in res}):
        rs = [r for r in res if r["element"] == el]
        hl = [r["half_after_peak_frames"] for r in rs if r["half_after_peak_frames"] is not None]
        summ[el] = {"intervals": len(rs), "hold_ratio_median": float(np.median([r["hold_ratio"] for r in rs])),
                    "peak_speed_h_median": float(np.median([r["peak_speed_h"] for r in rs])),
                    "half_after_peak_frames_p10_50_90": [float(x) for x in np.percentile(hl, [10, 50, 90])] if hl else None,
                    "blob_count_max_median": float(np.median([r["blob_count_max"] for r in rs]))}
    json.dump({"summary": summ, "intervals": res}, open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
