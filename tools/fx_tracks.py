#!/usr/bin/env python3
"""이펙트 형태 사전 2판 — 깨끗하게 자른 이펙트 35구간에서 '움직이는 덩어리(트랙)'를 층째로 뽑는다 (2026-10-24).

1판(tools/fx_shapes.py)은 자동 마스크에서 정지 장면 몇 장만 뽑았다. 2판은 사용자·GPT·Claude가 고친 마스크(Drive
`04_SFA시험작/이펙트35_최종/`과 같은 마스크)를 쓰고, 덩어리를 장마다 이어 붙여 **모양이 어떻게 변하는지(커짐·흩어짐·사라짐)**까지 담는다.
- 장마다 마스크의 연결 덩어리(화면 대비 --min-area 이상)를 앞 장 덩어리와 겹침(IoU > --iou)으로 잇는다. --min-len 장 이상 이어진 것만 트랙.
- 각 장의 덩어리 안을 tools/effect_layers.py로 층 분해(밑색 + 반투명 명암 겹, 경계는 포물선 조각 = 2차 베지어).
- 좌표: 장마다 덩어리 중심 원점, 크기 = 면적 제곱근 1. 그 장의 화면 위치·크기는 F 줄에 따로 둔다(궤적·확대 속도).
- 4:3 원본은 effect_clip_sfa처럼 가운데 16:9로 자른다.
출력(다른 작가 그림 유래라 Drive에만, 저장소에는 통계 CSV만):
  T <트랙> <구간번호> <게시물> <첫 장(원본 프레임)> <장 수>
  F <장 순서> <중심x(화면 폭 비)> <중심y(화면 높이 비)> <크기(면적 제곱근/화면 높이)> <층 수>
  Y <B> <G> <R> <알파> <윤곽 수>      ← 층(아래 → 위)
  C <구멍 0/1> x0 y0 cx cy x1 y1 …   ← 윤곽(2차 베지어 사슬)
통계 CSV: 트랙, 구간, 게시물, 첫장, 장수, 처음·최대·끝 크기, 최대 크기 장 순서, 이동 거리, 평균 색(BGR), 평균 층 수
사용: python tools/fx_tracks.py <jobs.txt> <영상 폴더> <마스크 폴더들(콤마, 앞쪽 우선)> <출력.txt> <통계.csv> [--thumbs 폴더]
  jobs.txt 한 줄 = `<번호> <게시물> <시작> <끝> <영상 파일명>`, 마스크 이름 = `<게시물>_<시작>_click.npz` 또는 `_v3.npz`
"""
import argparse
import csv
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import decompose  # noqa: E402
from effect_vectorize import read_frame  # noqa: E402

H = 540


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def find_mask(dirs, p, s, n):
    for d in dirs:
        for suf in ("_click", "_v3"):
            q = os.path.join(d, f"{p}_{s}{suf}.npz")
            if os.path.exists(q):
                return q
    return None


def crop169(a, interp):
    h, w = a.shape[:2]
    tw = round(h * 16 / 9)
    if abs(w - tw) <= 2:
        return a
    th = round(w * 9 / 16)
    y0 = (h - th) // 2
    return cv2.resize(a[y0:y0 + th], (tw, h), interpolation=interp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("videos")
    ap.add_argument("masks")
    ap.add_argument("out")
    ap.add_argument("stats")
    ap.add_argument("--min-area", type=float, default=0.002)
    ap.add_argument("--iou", type=float, default=0.2)
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--thumbs", help="트랙마다 4장 그림(원본 덩어리만) — GPT 종류 판정용, Drive에만")
    a = ap.parse_args()
    dirs = a.masks.split(",")
    lines, rows, tid = [], [], 0
    if a.thumbs:
        os.makedirs(a.thumbs, exist_ok=True)
    for job in open(a.jobs, encoding="utf-8"):
        num, p, s, e, f = job.split()[:5]
        s, e = int(s), int(e)
        mp = find_mask(dirs, p, s, num)
        if not mp:
            print(num, "마스크 없음")
            continue
        z = np.load(mp)
        shp = tuple(int(v) for v in z["shape"])
        M = np.unpackbits(z["mask"], axis=-1)[..., :shp[2]]
        fidx = {int(fr): i for i, fr in enumerate(z["frames"])}
        tracks, live = [], []  # live = [(트랙 번호, 앞 장 덩어리 마스크)]
        imgs = {}
        for fr in range(s, e + 1):
            if fr not in fidx:
                continue
            img = read_frame(os.path.join(a.videos, f), fr, H)
            m = M[fidx[fr]]
            if m.shape != img.shape[:2]:
                m = cv2.resize(m, (img.shape[1], H), interpolation=cv2.INTER_NEAREST)
            img, m = crop169(img, cv2.INTER_CUBIC), crop169(m, cv2.INTER_NEAREST)
            W = img.shape[1]
            imgs[fr - s] = img
            k, cc, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
            comps = [(cc == c).astype(np.uint8) for c in range(1, k) if st[c, cv2.CC_STAT_AREA] / (H * W) >= a.min_area]
            nxt, used = [], set()
            for comp in comps:
                best, bi = 0.0, -1
                for li, (t, prev) in enumerate(live):
                    if li in used:
                        continue
                    iou = (comp & prev).sum() / max((comp | prev).sum(), 1)
                    if iou > best:
                        best, bi = iou, li
                if best > a.iou:
                    used.add(bi)
                    t = live[bi][0]
                else:
                    t = len(tracks)
                    tracks.append([])
                tracks[t].append((fr - s, comp))
                nxt.append((t, comp))
            live = nxt
        for tr in tracks:
            if len(tr) < a.min_len:
                continue
            tid += 1
            sizes, cents, cols, nl = [], [], [], []
            body = []
            for fi, comp in tr:
                img = imgs[fi]
                W = img.shape[1]
                ys, xs = np.nonzero(comp)
                cx, cy, sz = xs.mean(), ys.mean(), np.sqrt(comp.sum())
                doc, _ = decompose(img, valid=comp)
                layers = [L for L in doc["layers"] if L["shapes"]]
                sizes.append(sz / H)
                cents.append((cx / W, cy / H))
                cols.append(img[comp > 0].mean(0))
                nl.append(len(layers))
                body.append(f"F {fi} {fmt(cx / W)} {fmt(cy / H)} {fmt(sz / H)} {len(layers)}")
                for L in layers:
                    body.append(f"Y {' '.join(str(int(round(x))) for x in L['color'][:3])} {fmt(L['alpha'])} {len(L['shapes'])}")
                    for sh in L["shapes"]:
                        seg = np.array(sh["segs"], float).reshape(-1, 2)
                        seg = ((seg - [cx, cy]) / sz).reshape(-1)
                        body.append(f"C {int(sh['hole'])} " + " ".join(fmt(x) for x in seg))
            lines.append(f"T {tid} {num} {p} {s + tr[0][0]} {len(tr)}")
            lines.extend(body)
            c = np.array(cents)
            col = np.mean(cols, 0)
            rows.append({"트랙": tid, "구간": num, "게시물": p, "첫장": s + tr[0][0], "장수": len(tr),
                         "처음크기": round(sizes[0], 4), "최대크기": round(max(sizes), 4), "끝크기": round(sizes[-1], 4),
                         "최대장": int(np.argmax(sizes)), "이동": round(float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum()), 4),
                         "평균색BGR": " ".join(str(int(v)) for v in col), "평균층수": round(float(np.mean(nl)), 1)})
            if a.thumbs:  # 원본 덩어리만 4장(밖은 검정) — 종류 판정용
                pick = sorted(set(np.linspace(0, len(tr) - 1, 4).round().astype(int)))
                th = []
                for j in pick:
                    fi, comp = tr[j]
                    im = np.where(comp[..., None] > 0, imgs[fi], 0).astype(np.uint8)
                    im = cv2.resize(im, (320, 180))
                    cv2.putText(im, f"{s + fi}", (4, 16), 0, 0.5, (0, 255, 0), 1)
                    th.append(im)
                while len(th) < 4:
                    th.append(np.zeros_like(th[0]))
                bar = np.zeros((24, 1280, 3), np.uint8)
                cv2.putText(bar, f"track {tid}  seg {num}  post {p}  frames {len(tr)}", (6, 17), 0, 0.55, (255, 255, 255), 1)
                cv2.imwrite(os.path.join(a.thumbs, f"track_{tid:04d}.jpg"), np.vstack([bar, np.hstack(th)]), [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(num, p, "트랙", sum(1 for t in tracks if len(t) >= a.min_len), "누계", tid, flush=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    with open(a.stats, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["트랙"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("트랙", tid, "크기MB", round(os.path.getsize(a.out) / 1e6, 1))


if __name__ == "__main__":
    main()
