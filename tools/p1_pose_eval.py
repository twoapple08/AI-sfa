"""P1 포즈 모델 비교 평가(정답 없음, 서버 CPU).

Colab 노트북(tools/colab_p1_pose_compare.ipynb)이 Drive `02_분석자료/P1_포즈비교/<모델>/`에 저장한
결과를 읽어 COCO 몸 17점 기준으로 모델을 비교한다. 정답 라벨이 없으므로 다음 대리 지표를 쓴다.

- det: 몸 17점 중 신뢰 점이 8개 이상인 주인물이 있는 프레임 비율
- jitter: 신뢰 점의 2차 차분(가속도) 중앙값 / 상자 대각선 (낮을수록 매끈)
- swap: 좌우를 바꾸면 직전 프레임과 훨씬 가까워지는 프레임 비율(좌우 뒤바뀜)
- agree: 다른 모델들 중앙값과의 거리 < 0.1 × 상자 대각선인 점 비율(PCK@0.1, 합의도)

합의도는 '다른 모델이 맞다'는 가정을 깔고 있으므로 표본 그림 확인과 함께 판단한다.

사용: python tools/p1_pose_eval.py <P1_포즈비교 폴더> [--out 결과.json]
"""
import argparse
import glob
import json
import os
from collections import defaultdict

import numpy as np

THR = {"rtmw_x": 1.0}  # SimCC 점수는 범위가 다르다(0~10 내외). 나머지는 히트맵/확률 점수 0.3
LR = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]


def thr(model):
    return THR.get(model, 0.3)


def load(root):
    data = defaultdict(dict)  # model -> clipkey -> (clip, frames[list of people])
    for d in sorted(glob.glob(os.path.join(root, "*"))):
        m = os.path.basename(d)
        if m.startswith("_") or not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.json")):
            if os.path.basename(f).startswith("_"):
                continue
            j = json.load(open(f))
            data[m][os.path.basename(f)[:-5]] = j
    return data


def main_track(frames, t):
    """프레임마다 주인물 1명을 고른다: 첫 프레임은 신뢰 점 합 최대, 이후 직전 중심에 가장 가까운 사람."""
    out, prev = [], None
    for ppl in frames:
        best, bs = None, -1e9
        for p in ppl:
            k = np.asarray(p["kp"], float)[:17]
            good = k[:, 2] > t
            if good.sum() < 1:
                continue
            c = k[good, :2].mean(0)
            s = k[good, 2].sum() - (0 if prev is None else np.linalg.norm(c - prev) / 50.0)
            if s > bs:
                best, bs = k, s
        out.append(best)
        if best is not None and (best[:, 2] > t).sum() >= 8:
            prev = best[best[:, 2] > t, :2].mean(0)
    return out


def diag(k, good):
    p = k[good, :2]
    if len(p) < 2:
        return np.nan
    return float(np.linalg.norm(p.max(0) - p.min(0)))


def eval_all(root):
    data = load(root)
    models = sorted(data)
    tracks = {m: {ck: main_track(j["frames"], thr(m)) for ck, j in data[m].items()} for m in models}
    clips = sorted(set.intersection(*[set(data[m]) for m in models])) if models else []
    res = {}
    for m in models:
        t = thr(m)
        per = defaultdict(lambda: defaultdict(list))
        for ck in clips:
            an = data[m][ck]["clip"]["animator"]
            tr = tracks[m][ck]
            for i, k in enumerate(tr):
                ok = k is not None and (k[:, 2] > t).sum() >= 8
                per[an]["det"].append(float(ok))
                if not ok:
                    continue
                good = k[:, 2] > t
                dg = diag(k, good)
                # jitter
                if 0 < i < len(tr) - 1 and tr[i - 1] is not None and tr[i + 1] is not None:
                    g = good & (tr[i - 1][:, 2] > t) & (tr[i + 1][:, 2] > t)
                    if g.sum() >= 4:
                        acc = np.linalg.norm(tr[i + 1][g, :2] - 2 * k[g, :2] + tr[i - 1][g, :2], axis=1)
                        per[an]["jitter"].append(float(np.median(acc) / dg))
                # swap
                if i > 0 and tr[i - 1] is not None:
                    pk = tr[i - 1]
                    sw = k.copy()
                    for a, b in LR:
                        sw[[a, b]] = sw[[b, a]]
                    g = good & (pk[:, 2] > t) & (sw[:, 2] > t)
                    if g.sum() >= 6:
                        d0 = np.linalg.norm(k[g, :2] - pk[g, :2], axis=1).mean()
                        d1 = np.linalg.norm(sw[g, :2] - pk[g, :2], axis=1).mean()
                        per[an]["swap"].append(float(d1 < 0.5 * d0 and d0 > 0.05 * dg))
                # agreement vs median of other models
                others = []
                for o in models:
                    if o == m:
                        continue
                    ok2 = tracks[o][ck][i]
                    if ok2 is not None and (ok2[:, 2] > thr(o)).sum() >= 8:
                        others.append(np.where((ok2[:, 2] > thr(o))[:, None], ok2[:, :2], np.nan))
                if len(others) >= 2:
                    med = np.nanmedian(np.stack(others), 0)
                    g = good & ~np.isnan(med[:, 0])
                    if g.sum():
                        dist = np.linalg.norm(k[g, :2] - med[g], axis=1) / dg
                        per[an]["agree"].extend((dist < 0.1).astype(float).tolist())
        res[m] = {an: {k: (round(float(np.mean(v)), 4) if v else None) for k, v in d.items()} for an, d in per.items()}
        allv = defaultdict(list)
        for d in per.values():
            for k, v in d.items():
                allv[k].extend(v)
        res[m]["_all"] = {k: (round(float(np.mean(v)), 4) if v else None) for k, v in allv.items()}
    return {"clips": len(clips), "models": models, "result": res}


def table(r):
    rows = ["| 모델 | det | jitter | swap | agree |", "|---|---|---|---|---|"]
    for m in r["models"]:
        a = r["result"][m]["_all"]
        rows.append(f"| {m} | {a.get('det')} | {a.get('jitter')} | {a.get('swap')} | {a.get('agree')} |")
    return "\n".join(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out")
    a = ap.parse_args()
    r = eval_all(a.root)
    if a.out:
        json.dump(r, open(a.out, "w"), ensure_ascii=False, indent=1)
    print("구간", r["clips"])
    print(table(r))
