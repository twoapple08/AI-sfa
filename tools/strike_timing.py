"""정리된 2D 포즈 추적(tools/pose_tracks.py)으로 몸동작 타이밍(빠름·멈춤)을 잰다. 나카무라 몸동작 역할(타격 타이밍·간격)용.

사용: python tools/strike_timing.py <tracks_all 폴더> <원본 영상 루트> <임팩트 판정 csv> <출력 json> [--animators yutaka_nakamura,nian41]
- 대상: 몸점수_중앙 ≥ 2.8 추적(pose_tracks.KEEP_SCORE).
- 프레임 지표(몸 크기 = 어깨 가운데~엉덩이 가운데 거리 중앙값 단위):
  몸 변화 = 17점의 앞 프레임 대비 평균 이동(골반 기준 상대), 손발 속도 = 손목·발목 중 최대 상대 이동.
  새 그림 = 몸 뼈대 영역(이번·앞 프레임 뼈대를 몸통 0.3 굵기로 그림)에서, 앞 프레임을 위상 상관으로 평행 이동 맞춘 뒤
  15단계 넘게 바뀐 픽셀 비율(%) > PIX_EPS.
  (포즈 변화량만으로는 나카무라에서 같은 그림·새 그림이 나뉘지 않았다 — 검출 떨림이 0.003~0.03로 실제 움직임과 겹침.)
  유지 길이 = 새 그림 사이 프레임 수(1s·2s·3s…).
- A. 임팩트 기준(impact_classify training='사용'): 임팩트 시작 f0 ±W 창. 임팩트 프레임(f0~f1+1)은 그림이 통째로 바뀌므로 뺀다.
  임팩트 직전 마지막 유지 길이(예비 동작 멈춤), 직전·직후 손발 속도, 유지 길이 분포를 기준(임팩트 ±2초 밖 창)과 비교.
- B. 빠른 동작 정점(임팩트 목록 없이, 애니메이터별): 손발 속도가 그 애니메이터 상위 3%이고 12프레임 안 최댓값인 프레임.
  작은 인물(몸통 < MIN_TORSO px)과 팔다리 길이 합이 앞 3프레임 중앙값의 0.67~1.5배를 벗어나는 정점(인물 바뀜)은 뺀다.
  정점 직전 멈춤(정점 앞 그림이 유지된 길이), 정점 그림 유지 길이, 정점까지 그림 수(정점 앞 8프레임 안 새 그림 수),
  간격 비(정점 프레임 이동 / 정점 앞 그림들의 평균 이동 — 크면 '갑자기 빨라짐').
출력은 집계값만(저장소 가능). 프레임 좌표는 원본 영상 프레임 번호.
"""
import argparse
import csv
import glob
import json
import os

import numpy as np

KEEP = 2.8
PIX_EPS = 20.0  # 몸 영역(흔들림 보정 후)에서 크게 바뀐 픽셀 %. 새 그림 40~80%, 흔들림·잡음 1~14%. nian41 280544 1180–1227 손 계수 22간격과 전부 일치
EXT = [9, 10, 15, 16]


SK = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16),
      (0, 5), (0, 6)]
LIMBS = [(5, 7), (7, 9), (6, 8), (8, 10), (11, 13), (13, 15), (12, 14), (14, 16)]
MIN_TORSO = 30  # 정점으로 셀 최소 몸통 길이(px). 작은 인물은 검출이 튄다(눈 확인 8개 중 2개)


def torso(K):
    P = K[:, :17, :2]
    v = np.nanmedian(np.linalg.norm((P[:, 5] + P[:, 6]) / 2 - (P[:, 11] + P[:, 12]) / 2, axis=1))
    return float(v) if np.isfinite(v) else 0.0


def limb_sum(K):
    P = K[:, :17, :2]
    return np.nansum(np.stack([np.linalg.norm(P[:, a] - P[:, b], axis=1) for a, b in LIMBS], 1), 1)


def per_frame(K):
    """K [T,133,3] → 몸 변화, 손발 속도 [T] (첫 프레임·빈 프레임 NaN)."""
    P = K[:, :17, :2]
    hip = (P[:, 11] + P[:, 12]) / 2
    sh = (P[:, 5] + P[:, 6]) / 2
    size = np.nanmedian(np.linalg.norm(sh - hip, axis=1))
    if not np.isfinite(size) or size < 5:
        return None
    R = (P - hip[:, None]) / size
    d = np.linalg.norm(np.diff(R, axis=0), axis=2)  # [T-1,17]
    body = np.r_[np.nan, np.nanmean(d, 1) if np.isfinite(d).any() else np.full(len(d), np.nan)]
    ext = np.r_[np.nan, np.nanmax(np.where(np.isfinite(d[:, EXT]), d[:, EXT], -1), 1)]
    ext[ext < 0] = np.nan
    ok = np.isfinite(R).all(-1).sum(1) >= 12
    bad = ~(ok & np.r_[False, ok[:-1]])
    body[bad] = np.nan
    ext[bad] = np.nan
    return body, ext


def holds(pix):
    """새 그림 프레임 위치와 각 그림의 유지 길이."""
    new = np.where(pix > PIX_EPS)[0]
    return new, np.diff(new)


def last_hold_before(new, t):
    """t 바로 앞에 보이던 그림이 유지된 길이(t 이전 마지막 새 그림 ~ t). t가 새 그림이 아니어도 t에서 끊어 잰다."""
    b = new[new < t]
    return int(t - b[-1]) if len(b) else None


def first_hold_after(new, t):
    a = new[new > t]
    return int(a[1] - a[0]) if len(a) >= 2 else None


def q(v):
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], float)
    if not len(v):
        return None
    return {"n": int(len(v)), "중앙": round(float(np.median(v)), 3), "사분위": [round(float(x), 3) for x in np.percentile(v, [25, 75])]}


def hold_dist(h):
    h = np.asarray(h, int)
    if not len(h):
        return None
    return {f"{k}s": round(float((h == k).mean()), 3) for k in (1, 2, 3, 4)} | {"5s+": round(float((h >= 5).mean()), 3),
                                                                           "n": int(len(h))}


def find_video(vroot, an, pid):
    d = "yutaka_nakamura_디지털" if an == "yutaka_nakamura" else an
    v = (glob.glob(os.path.join(vroot, d, "**", f"{pid}_*.mp4"), recursive=True) +
         glob.glob(os.path.join(vroot, d, "**", f"{pid}.mp4"), recursive=True))
    return v[0] if v else None


def pixel_diffs(video, items):
    """items [(start, kp [L,133,3])] → 추적별 인물 상자 안 앞 프레임 대비 차이 [L] (첫 프레임·빈 상자 NaN). 영상은 한 번만 읽는다."""
    import cv2
    out = [np.full(len(k), np.nan) for _, k in items]
    sizes = [torso(k) for _, k in items]
    end = max(st + len(k) for st, k in items)
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, min(st for st, _ in items))
    t = min(st for st, _ in items)
    prev = None
    while t < end:
        ok, im = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            for j, (st, K) in enumerate(items):
                i = t - st
                if not 0 < i < len(K):
                    continue
                pts = K[i, :17, :2][np.isfinite(K[i, :17, 0])]
                if len(pts) < 6:
                    continue
                x0, y0 = pts.min(0)
                x1, y1 = pts.max(0)
                m = 0.25 * max(x1 - x0, y1 - y0) + 8
                xa, ya = int(max(0, x0 - m)), int(max(0, y0 - m))
                xb, yb = int(min(g.shape[1], x1 + m)), int(min(g.shape[0], y1 + m))
                if xb - xa < 8 or yb - ya < 8:
                    continue
                # 몸 뼈대(이번·앞 프레임)를 몸통 길이의 0.3 굵기로 그린 영역만 본다 — 상자 안 흐르는 배경·이펙트를 덜 센다
                mask = np.zeros((yb - ya, xb - xa), np.uint8)
                th = max(3, int(0.3 * sizes[j]))
                for kk in (K[i], K[i - 1]):
                    for p_, q_ in SK:
                        if np.isfinite(kk[p_, 0]) and np.isfinite(kk[q_, 0]):
                            cv2.line(mask, (int(kk[p_, 0] - xa), int(kk[p_, 1] - ya)),
                                     (int(kk[q_, 0] - xa), int(kk[q_, 1] - ya)), 1, th)
                if mask.sum() < 30:
                    continue
                cur = g[ya:yb, xa:xb].astype(np.float32)
                pv = prev[ya:yb, xa:xb].astype(np.float32)
                # 카메라 흔들림·이동 보정: 앞 프레임 상자를 위상 상관으로 평행 이동 맞춤(같은 그림이면 차이가 0 근처로 돌아온다)
                (dx, dy), _ = cv2.phaseCorrelate(pv, cur)
                if abs(dx) > 0.5 or abs(dy) > 0.5:
                    pv = cv2.warpAffine(pv, np.float32([[1, 0, dx], [0, 1, dy]]), (pv.shape[1], pv.shape[0]),
                                        borderMode=cv2.BORDER_REPLICATE)
                d = np.abs(cur - pv) > 15
                out[j][i] = float(d[mask > 0].mean() * 100)  # 몸 영역에서 크게 바뀐 픽셀 % (압축 잡음은 거의 15를 넘지 않는다)
        prev = g
        t += 1
    return out


def load_tracks(root, vroot, animators):
    for an in animators:
        for f in sorted(glob.glob(os.path.join(root, an, "*.npz"))):
            z = np.load(f)
            if z["quality"].ndim < 2:
                continue
            pid = os.path.basename(f)[:-4]
            v = find_video(vroot, an, pid)
            if v is None:
                continue
            keep = [i for i, (L, qq) in enumerate(zip(z["length"], z["quality"])) if qq[0] >= KEEP and L >= 24]
            items = [(int(z["start"][i]), z["kp"][i, :int(z["length"][i])]) for i in keep]
            if not items:
                continue
            pix = pixel_diffs(v, items)
            for (st, K), px in zip(items, pix):
                r = per_frame(K)
                if r is not None:
                    yield an, pid, st, (px, r[1], torso(K), limb_sum(K))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks")
    ap.add_argument("videos")
    ap.add_argument("impacts")
    ap.add_argument("out")
    ap.add_argument("--animators", default="yutaka_nakamura,nian41")
    ap.add_argument("--win", type=int, default=24)
    a = ap.parse_args()
    W = a.win
    ans = a.animators.split(",")
    imp = {}
    for x in csv.DictReader(open(a.impacts, encoding="utf-8-sig")):
        if x["training"] == "사용":
            f0, f1 = (int(v) for v in x["frames"].split("-"))
            imp.setdefault(x["post_id"], []).append((f0, f1))
    import pickle
    cp = os.environ.get("STRIKE_CACHE")
    if cp and os.path.exists(cp):
        tracks = pickle.load(open(cp, "rb"))
    else:
        tracks = list(load_tracks(a.tracks, a.videos, ans))
        if cp:
            pickle.dump(tracks, open(cp, "wb"))
    out = {"pix_eps": PIX_EPS, "win": W, "tracks": {an: sum(1 for t in tracks if t[0] == an) for an in ans}}

    # A. 임팩트 기준
    A = {"pre_curve": [], "pre_new": [], "post_curve": [], "post_new": [], "pre_hold": [], "post_hold": [], "pre_ext": [], "post_ext": [],
         "hold_pre": [], "hold_post": [], "base_ext": [], "base_hold": []}
    rng = np.random.default_rng(0)
    for an, pid, st, (body, ext, _, _) in tracks:
        evs = imp.get(pid, [])
        T = len(body)
        new, _ = holds(body)
        far = np.ones(T, bool)
        for f0, f1 in evs:
            t0, t1 = f0 - st, f1 - st
            far[max(0, t0 - 48):max(0, t1 + 48)] = False
            # 임팩트 섬광에서 장면 바뀜으로 추적이 끊기므로 직전·직후를 따로 잰다(같은 인물 연결은 보장하지 않음)
            if t0 >= 12 and T >= t0 - 2:  # 직전 12프레임 이상을 덮고 임팩트 2프레임 안까지 이어짐
                te = min(T, t0)
                c = np.full(W, np.nan)
                c2 = np.full(W, np.nan)
                lo = max(1, te - W)
                c[W - (te - lo):] = ext[lo:te]
                c2[W - (te - lo):] = np.where(np.isfinite(body[lo:te]), body[lo:te] > PIX_EPS, np.nan)
                A["pre_curve"].append(c)
                A["pre_new"].append(c2)
                A["pre_hold"].append(last_hold_before(new, te))
                A["pre_ext"].append(np.nanmean(ext[te - 6:te]))
                pn = new[(new >= lo) & (new < te)]
                A["hold_pre"] += np.diff(pn).tolist()
            if t1 + 1 >= -3 and T - max(t1 + 2, 1) >= 12:  # 임팩트 끝 3프레임 안에서(또는 그 전부터) 시작해 끝 뒤로 12프레임 이상 이어짐
                ts = max(t1 + 2, 1)
                c = np.full(W, np.nan)
                c2 = np.full(W, np.nan)
                hi = min(T, ts + W)
                c[:hi - ts] = ext[ts:hi]
                c2[:hi - ts] = np.where(np.isfinite(body[ts:hi]), body[ts:hi] > PIX_EPS, np.nan)
                A["post_curve"].append(c)
                A["post_new"].append(c2)
                A["post_hold"].append(first_hold_after(new, ts - 1))
                A["post_ext"].append(np.nanmean(ext[ts:ts + 6]))
                pn = new[(new >= ts) & (new < hi)]
                A["hold_post"] += np.diff(pn).tolist()
        cand = np.where(far[W:T - W])[0] + W
        for c in (rng.choice(cand, min(len(cand), 3), replace=False) if len(cand) else []):
            A["base_ext"].append(np.nanmean(ext[c - 6:c]))
            bn = new[(new >= c - W) & (new < c + W)]
            A["base_hold"] += np.diff(bn).tolist()
    if A["pre_curve"] or A["post_curve"]:
        base = float(np.nanmean(A["base_ext"]))
        mc = lambda k, r: np.round(np.nanmean(np.stack(A[k]), 0), r).tolist() if A[k] else None  # noqa: E731
        out["A_임팩트기준"] = {
            "직전_추적수": len(A["pre_curve"]), "직후_추적수": len(A["post_curve"]), "기준_손발속도": round(base, 4),
            "직전6_손발속도/기준": round(float(np.nanmean(A["pre_ext"])) / base, 2),
            "직후6_손발속도/기준": round(float(np.nanmean(A["post_ext"])) / base, 2),
            "직전_마지막유지(프레임)": q(A["pre_hold"]), "직후_첫유지(프레임)": q(A["post_hold"]),
            "유지분포_직전24": hold_dist(A["hold_pre"]), "유지분포_직후24": hold_dist(A["hold_post"]),
            "유지분포_기준": hold_dist(A["base_hold"]),
            "곡선_직전_손발속도(-W~-1)": mc("pre_curve", 4), "곡선_직전_새그림비율": mc("pre_new", 3),
            "곡선_직후_손발속도(f1+1~)": mc("post_curve", 4), "곡선_직후_새그림비율": mc("post_new", 3)}

    # B. 빠른 동작 정점
    out["B_빠른동작정점"] = {}
    for an in ans:
        tr = [t for t in tracks if t[0] == an]
        if not tr:
            continue
        allext = np.concatenate([t[3][1] for t in tr])
        thr = float(np.nanpercentile(allext, 97))
        R = {"pre_stop": [], "post_stop": [], "drawings8": [], "jump_ratio": [], "peak": [], "all_hold": [],
             "where": [], "drop_small": 0, "drop_swap": 0}
        for _, pid, st, (body, ext, tor, limb) in tr:
            new, h = holds(body)
            R["all_hold"] += h.tolist()
            T = len(ext)
            for t in range(8, T - 8):
                if not (ext[t] >= thr) or ext[t] < np.nanmax(ext[max(0, t - 6):t + 7]):
                    continue
                if tor < MIN_TORSO:
                    R["drop_small"] += 1
                    continue
                ref = np.median(limb[t - 3:t])
                if not (ref > 0 and 0.67 <= limb[t] / ref <= 1.5 and 0.67 <= limb[t + 1] / ref <= 1.5):
                    R["drop_swap"] += 1  # 팔다리 길이 합이 갑자기 바뀜 = 다른 인물·검출 튐
                    continue
                R["peak"].append(ext[t])
                R["where"].append([pid, st + t])
                R["pre_stop"].append(last_hold_before(new, t))
                a_ = new[new > t]
                R["post_stop"].append(int(a_[0] - t) if len(a_) else None)  # 정점 그림이 유지된 길이
                pn = new[(new >= t - 8) & (new < t)]
                R["drawings8"].append(len(pn))
                prev = ext[pn]
                prev = prev[np.isfinite(prev)]
                R["jump_ratio"].append(ext[t] / np.mean(prev) if len(prev) else None)
        out["B_빠른동작정점"][an] = {
            "정점수": len(R["peak"]), "제외_작은인물": R["drop_small"], "제외_인물바뀜": R["drop_swap"],
            "정점기준(상위3%)": round(thr, 4), "정점_손발속도": q(R["peak"]),
            "정점전_멈춤(마지막유지)": q(R["pre_stop"]), "정점그림_유지": q(R["post_stop"]),
            "정점앞8프레임_새그림수": q(R["drawings8"]), "간격비(정점/앞그림평균)": q(R["jump_ratio"]),
            "유지분포_전체": hold_dist(R["all_hold"]), "정점_위치(post_id,원프레임)": R["where"]}
    allpix = np.concatenate([t[3][0] for t in tracks])
    allpix = allpix[np.isfinite(allpix)]
    out["픽셀차_분포(log10 구간:개수)"] = dict(zip([f"{x:.2f}" for x in np.arange(-2, 2.01, 0.25)[:-1]],
                                           np.histogram(np.log10(allpix + 1e-3), np.arange(-2, 2.01, 0.25))[0].tolist()))
    json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
    s = {k: v for k, v in out.get("A_임팩트기준", {}).items() if not k.startswith("곡선")}
    print(json.dumps({"tracks": out["tracks"], "pix": out["픽셀차_분포(log10 구간:개수)"], "A": s,
                      "B": {an: {k: v for k, v in b.items() if k != "정점_위치(post_id,원프레임)"}
                            for an, b in out["B_빠른동작정점"].items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
