#!/usr/bin/env python3
"""임팩트 프레임 플립북 v2: 임팩트 장면을 프레임마다 전체 층 분해(밑색 + 반투명 명암 + 선 획)해 생성기가 그대로 재생하게 한다.

사용: python tools/fx_impact_book.py <effects.txt(Q 장면 목록)> <영상 폴더> <출력 txt> [--only 이름,이름]
- 장면 목록은 이펙트 사전의 Q 장면(이름 post:start, 장수 n)을 그대로 쓴다(51개, 사람 판정 임팩트에서 뽑은 것).
- 이전 Q 플립북은 흑백 2단계 먹 윤곽이라 연필 해칭 결·옅은 연필선·색 포인트가 뭉개졌다(2026-10-22 점검).
  여기서는 tools/effect_layers.py decompose를 화면 전체에 돌려 해칭을 선 획(획별 굵기·색)으로, 연필 회색을 반투명 명암 층으로 담는다.
- 구멍은 자기 바깥 윤곽(parent)에 붙인다(fx_flipbook 형식은 구멍을 첫 윤곽에만 붙여 윤곽이 많은 층에서 어긋난다).
- --glow(2026-10-22 사용자 지적): 반투명 명암 면을 여러 겹 쌓은 빛 번짐은 회색 띠 계단(물결)이 생긴다.
  스틱파이터 글로우 기능으로 바꾼다 — 프레임 바탕색 = 가장 많은 색(검정/흰색, 큰 바탕 면을 따로 그리지 않음),
  반대 톤은 선명한 단색 면(두 톤, Otsu), 밝은 면이면 경계 곡선에 글로우(번짐 폭은 원본 밝기가 경계에서 줄어드는 거리로 잰다),
  선 획은 면이 못 담는 것만(어두운 곳의 밝은 선·밝은 곳의 어두운 해칭), 밝은 획은 글로우.
출력(Drive만, 다른 작가 그림 유래). 좌표는 화면 높이 1, 왼쪽 위 원점:
  B impact <출처 post:start> <프레임 수> <화면 폭/높이> [BG <B> <G> <R>]
  F <층 수> <획 수>
  Y <B> <G> <R> <알파> <윤곽 수> [G <글로우 σ(화면 높이 비율)> <글로우 띠 폭(화면 높이 비율)>]
  C <구멍> <부모 윤곽 번호(층 안, 없으면 -1)> x0 y0 cx cy x1 y1 …
  S <B> <G> <R> <굵기(화면 높이 비율)> x0 y0 cx cy x1 y1 [G <글로우 σ>]
"""
import argparse
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2  # noqa: E402
import numpy as np  # noqa: E402

from effect_layers import decompose, line_layer, mask_strokes  # noqa: E402
from effect_vectorize import outline_mask, read_frame  # noqa: E402
from fx_gen import load_scenes  # noqa: E402

H = 540


def fmt(v):
    return f"{v:.4f}".rstrip("0").rstrip(".")


def frame_lines(doc):
    layers = [L for L in doc["layers"] if L["shapes"]]
    strokes = [(seg, ln["color"]) for ln in doc["lines"] for seg in ln["segs"]]
    out = [f"F {len(layers)} {len(strokes)}"]
    for L in layers:
        out.append(f"Y {' '.join(str(int(round(x))) for x in L['color'][:3])} {fmt(L.get('alpha', 1.0))} {len(L['shapes'])}")
        idx = {sh.get("cid", i): i for i, sh in enumerate(L["shapes"])}
        for sh in L["shapes"]:
            par = idx.get(sh.get("parent", -1), -1) if sh["hole"] else -1
            out.append(f"C {int(sh['hole'])} {par} " + " ".join(fmt(x / H) for x in sh["segs"] for x in x[:6]))
    for seg, col in strokes:
        c = seg[7:10] if len(seg) >= 10 else col
        out.append(f"S {' '.join(str(int(round(x))) for x in c[:3])} {fmt(seg[6] / H)} " + " ".join(fmt(x / H) for x in seg[:6]))
    return out


def border_bg(img):
    b = np.concatenate([img[:4].reshape(-1, 3), img[-4:].reshape(-1, 3), img[:, :4].reshape(-1, 3), img[:, -4:].reshape(-1, 3)])
    return np.median(b, 0)


def glow_frame(img):
    """두 톤 그림. 프레임 바탕 = 넓은 쪽 톤 색(큰 바탕 면을 그리지 않음). 반대 톤: 굵은 부분 = 선명한 단색 면,
    가는 부분(해칭·가는 줄기, 폭 ≤ 약 4px) = 선 획. 면이 밝은 톤(빛)이면 경계에 글로우
    (σ = 원본에서 면 경계 밖 밝기가 15%로 줄어드는 거리의 절반). 반환: (바탕 BGR, 줄 목록)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gf = g.astype(np.float32)
    t, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    lo, hi = float(np.percentile(gf, 5)), float(np.percentile(gf, 99.5))
    light = (g > t).astype(np.uint8)
    bg_light = light.mean() > 0.5
    if not bg_light:  # 어두운 바탕의 빛: 번짐(중간 밝기)은 글로우가 그리므로 면은 밝은 핵심만
        light = (gf > lo + 0.7 * (hi - lo)).astype(np.uint8)
    lcol = np.median(img[light > 0], 0) if light.any() else np.array([255.0] * 3)
    dcol = np.median(img[light == 0], 0) if (light == 0).any() else np.array([0.0] * 3)
    bg, M, fcol = (lcol, 1 - light, dcol) if bg_light else (dcol, light, lcol)
    # 가는 덩어리(전체가 폭 ≤ 약 5px: 해칭·가는 줄기)는 선 획, 나머지는 면. 몸에 붙은 가시는 면에 남겨 뾰족함을 지킨다
    n, lab = cv2.connectedComponents(M, connectivity=8)
    dist = cv2.distanceTransform(M, cv2.DIST_L2, 3)
    mx = np.zeros(n, np.float32)
    np.maximum.at(mx, lab.reshape(-1), dist.reshape(-1))
    thin = ((mx[lab] <= 2.5) & (M > 0)).astype(np.uint8)
    thick_ = M & (1 - thin)
    out, nl = [], 0
    if thick_.sum() >= 30:
        _, shapes = outline_mask(thick_ * 255, 1.0, 12)
        glow = ""
        if not bg_light:
            d = cv2.distanceTransform(1 - thick_, cv2.DIST_L2, 3)
            prof = [float(gf[(d > r - 1) & (d <= r)].mean()) for r in range(1, 120) if ((d > r - 1) & (d <= r)).any()]
            r15 = next((r for r, v in enumerate(prof, 1) if (v - lo) < 0.15 * (hi - lo)), len(prof))
            sig = max(1.0, r15 / 3)
            glow = f" G {fmt(sig / H)} {fmt(sig / H)}"
        idx = {sh.get("cid", i): i for i, sh in enumerate(shapes)}
        out.append(f"Y {' '.join(str(int(round(x))) for x in fcol[:3])} 1 {len(shapes)}{glow}")
        for sh in shapes:
            par = idx.get(sh.get("parent", -1), -1) if sh["hole"] else -1
            out.append(f"C {int(sh['hole'])} {par} " + " ".join(fmt(x / H) for x in sh["segs"] for x in x[:6]))
        nl = 1
    strokes = [(seg, fcol) for seg in mask_strokes(img, thin, 1.0, 4)]
    for is_light in (True, False):  # 면이 못 담는 반대 톤 위 가는 선(밝은 곳의 어두운 해칭·어두운 곳의 밝은 선)
        _, segs, _ = line_layer(img, 1.0, light=is_light)
        for seg in segs:
            P = np.clip(np.round(np.array(seg[:6]).reshape(3, 2)).astype(int), 0, [img.shape[1] - 1, img.shape[0] - 1])
            on = thick_[P[:, 1], P[:, 0]].mean()
            fill_light = not bg_light
            if (is_light != fill_light and on > 0.5) or (is_light == fill_light and on < 0.5 and thin[P[:, 1], P[:, 0]].mean() < 0.5):
                strokes.append((seg, seg[7:10] if len(seg) >= 10 else fcol))
    for seg, c in strokes:
        out.append(f"S {' '.join(str(int(round(x))) for x in c[:3])} {fmt(seg[6] / H)} " + " ".join(fmt(x / H) for x in seg[:6])
                   + ("" if bg_light else f" G {fmt(max(1.0, seg[6]) / H)}"))
    return bg, [f"F {nl} {len(strokes)}"] + out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fx")
    ap.add_argument("videos")
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--glow", action="store_true", help="반투명 겹 대신 바탕색 + 단색 면 + 글로우(물결 없음)")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x}
    done = set()
    if os.path.exists(a.out):  # 이어 하기
        done = {l.split()[2] for l in open(a.out, encoding="utf-8") if l.startswith("B ")}
    for name, frs in load_scenes(a.fx):
        if (only and name not in only) or name in done:
            continue
        pid, start = name.split(":")
        v = glob.glob(os.path.join(a.videos, pid + "*.mp4"))
        if not v:
            print(name, "영상 없음", flush=True)
            continue
        t0, lines, W, bgs = time.time(), [], None, []
        for f in range(int(start), int(start) + len(frs)):
            img = read_frame(v[0], f, H)
            W = img.shape[1]
            if a.glow:
                bg, fl = glow_frame(img)
                bgs.append(bg)
                lines += fl
            else:
                doc, _ = decompose(img)
                lines += frame_lines(doc)
        bgtxt = (" BG " + " ".join(str(int(round(x))) for x in np.median(bgs, 0))) if bgs else ""
        with open(a.out, "a", encoding="utf-8") as fh:
            fh.write(f"B impact {name} {len(frs)} {fmt(W / H)}{bgtxt}\n" + "\n".join(lines) + "\n")
        print(name, "장수", len(frs), "초", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
