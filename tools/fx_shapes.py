#!/usr/bin/env python3
"""이펙트 층 형태 사전: Kaggle 이펙트 분리(tools/kaggle_fx_worker.py v3 물체별 마스크)에서 종류별 실제 형태를 '층째로' 뽑는다.

사용: python tools/fx_shapes.py <마스크 npz 폴더> <나카무라 영상 폴더> <구간 csv> <출력 txt> [--per-seg 3] [--min-area 0.003]
- 구간마다 이펙트 면적이 큰 프레임 몇 장(--per-seg)을 고르고, 물체별 마스크(라벨: explosion·smoke·fire·rocks·sparks …)마다
  연결 덩어리(화면 대비 min-area 이상)를 하나의 형태로 본다. 사람 물체는 뺀다.
- 덩어리 면적/볼록 껍질 < 0.35(깨진 마스크)는 뺀다. 고르는 프레임은 서로 6프레임 이상 떨어뜨린다.
- 덩어리 안을 tools/effect_layers.py로 층 분해(밑색 + 반투명 명암 겹, 경계는 포물선 조각) → 덩어리 중심 원점, 크기 = 면적 제곱근 1로 맞춘다.
- 종류: 라벨 낱말로 explosion / smoke / fire / rock / spark / other.
- 제작 자료 구간(csv exclude)은 뺀다.
출력(앱·생성기용 글자 형식, 다른 작가 그림 유래라 Drive에만):
  L <종류> <출처 post:frame:obj> <층 수> <원래 크기(화면높이비)>
  Y <B> <G> <R> <알파> <윤곽 수>      ← 층(아래 → 위)
  C <구멍 0/1> x0 y0 cx cy x1 y1 …   ← 윤곽(2차 베지어 사슬)
"""
import argparse
import csv
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import decompose  # noqa: E402

H = 540


def kind_of(label):
    l = label.lower()
    for k, ws in (("explosion", ("explo", "flash", "shock")), ("smoke", ("smoke", "dust", "cloud")), ("fire", ("fire",)),
                  ("rock", ("rock", "stone", "rubble", "debris")), ("spark", ("spark",))):
        if any(w in l for w in ws):
            return k
    return "other"


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("masks")
    ap.add_argument("videos")
    ap.add_argument("segments")
    ap.add_argument("out")
    ap.add_argument("--per-seg", type=int, default=3)
    ap.add_argument("--min-area", type=float, default=0.003)
    a = ap.parse_args()
    lines, count = [], {}
    for s in csv.DictReader(open(a.segments, encoding="utf-8-sig")):
        if s.get("exclude"):
            continue
        p = os.path.join(a.masks, f"{s['post_id']}_{s['start']}_v3.npz")
        v = glob.glob(os.path.join(a.videos, s["post_id"] + "*.mp4"))
        if not os.path.exists(p) or not v:
            continue
        z = np.load(p)
        if "obj_mask" not in z.files or len(z["labels"]) == 0:
            continue
        shp = tuple(int(x) for x in z["shape"])
        n, Wd = shp[0], shp[2]
        frames = z["frames"]
        pick = []
        for i in np.argsort(-z["area"]):  # 면적 큰 프레임부터, 서로 6프레임 이상 떨어지게(같은 모양 반복 방지)
            if all(abs(int(i) - j) >= 6 for j in pick):
                pick.append(int(i))
            if len(pick) >= a.per_seg:
                break
        cap = cv2.VideoCapture(v[0])
        for fi in sorted(int(i) for i in pick if z["area"][i] > 0):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frames[fi]))
            ok, im = cap.read()
            if not ok:
                continue
            img = cv2.resize(im, (Wd, H), interpolation=cv2.INTER_AREA)
            for oi, lab in enumerate(z["labels"]):
                lab = str(lab)
                if "person" in lab:
                    continue
                om = np.unpackbits(z["obj_mask"][oi, fi], axis=-1)[:, :Wd].astype(np.uint8)
                if om.mean() > 0.3:  # 배경을 통째로 잡은 물체(v3 기본 합집합에서도 뺐다)
                    continue
                k, cc, st, cen = cv2.connectedComponentsWithStats(om, 8)
                for c in range(1, k):
                    area = st[c, cv2.CC_STAT_AREA] / (H * Wd)
                    if area < a.min_area:
                        continue
                    valid = (cc == c).astype(np.uint8)
                    hull = cv2.convexHull(cv2.findNonZero(valid))
                    if valid.sum() / max(cv2.contourArea(hull), 1) < 0.35:  # 너덜너덜한 덩어리(깨진 마스크)는 형태로 쓰지 않는다
                        continue
                    doc, _ = decompose(img, valid=valid)
                    layers = [L for L in doc["layers"] if L["shapes"]]
                    if not layers:
                        continue
                    cx, cy = cen[c]
                    sz = np.sqrt(valid.sum())
                    kd = kind_of(lab)
                    count[kd] = count.get(kd, 0) + 1
                    lines.append(f"L {kd} {s['post_id']}:{int(frames[fi])}:{oi} {len(layers)} {fmt(sz / H)}")
                    for L in layers:
                        lines.append(f"Y {' '.join(str(int(round(x))) for x in L['color'][:3])} {fmt(L['alpha'])} {len(L['shapes'])}")
                        for sh in L["shapes"]:
                            seg = np.array(sh["segs"], float).reshape(-1, 2)
                            seg = ((seg - [cx, cy]) / sz).reshape(-1)
                            lines.append(f"C {int(sh['hole'])} " + " ".join(fmt(x) for x in seg))
        print(s["post_id"], s["start"], dict(count), flush=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("형태", sum(count.values()), dict(count), "크기MB", round(os.path.getsize(a.out) / 1e6, 2))


if __name__ == "__main__":
    main()
