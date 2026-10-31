#!/usr/bin/env python3
"""번지는 이펙트 그림 → SFA: 밝기 층마다 불투명 면 + 그 테두리(안 보이는 곡선)에 맞춘 글로우 (2026-10-26).

사용자(2026-10-26): "글로우(크기는 그 오브젝트의 선 두께와도 연관)와 투명도 활용을 잘할수록 이펙트 퀄리티가 훨씬 올라간다."
지금 변환기(stack_layers_sfa --glow)는 가장 밝은 층에만 고정 글로우(반경 하나, 두께 100, 알파 180, 테두리 굵기 0.1 → 띠 8px)를 건다.
여기서는 층마다 번짐을 재서 글로우를 맞춘다.

모델(앱 셰이더, tools/sfa_render.py 머리말): 글로우 띠 폭 Wg = 8·굵기·(글로우두께/10), 흐림 sigma ≈ 글로우반경(1920폭 기준 px),
띠를 가우스로 흐린 커버리지 × 글로우색 × 알파를 화면 위에 덮고(srcOver), 그 위에 같은 곡선이 두른 면이 칠해진다
→ 글로우는 면 바깥 번짐으로 보인다. 아래 층부터: 글로우 i → 면 i.
맞춤: 층마다 (Wg, sigma, 알파)를 격자에서 골라, 지금까지 쌓은 그림(위 층은 면만)과 원본의 차이가 가장 작게(욕심 순서, 아래 층부터).
SFA 쓰기: 테두리 곡선은 색 투명(알파 0)·굵기 TS_GLOW(기본 1.0, '배' 파일과 같음), 글로우두께 = Wg·10/(8·TS_GLOW).
확인: 쓴 SFA를 sfa_render.py로 다시 그려 원본과 평균 차이를 '글로우 없음'·'지금 변환기식 고정 글로우'와 나란히 비교.

사용: python tools/glow_fit.py <이펙트 그림(검은 바탕)> <out.sfa> [--levels 5] [--check 비교.jpg]
"""
import argparse
import math
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from person_sfa import coarse  # noqa: E402
from effect_clip_sfa import argb  # noqa: E402

REF_W = 1920.0  # 글로우·굵기 단위 = 1920폭 화면 px
TS_MIN = 0.1


def band_glow(shapes, shape_hw, Wg, sig, q=0.25):
    """테두리 곡선들을 폭 Wg 띠로 그리고 sigma로 흐린 커버리지(0–1). 크기 줄여 계산(큰 sigma도 빠르게)."""
    H, W = shape_hw
    w, h = max(1, int(W * q)), max(1, int(H * q))
    m = np.zeros((h, w), np.uint8)
    for s in shapes:
        for x0, y0, cx, cy, x1, y1 in (g[:6] for g in s["segs"]):
            t = np.linspace(0, 1, 12)[:, None]
            P = (1 - t) ** 2 * [x0, y0] + 2 * (1 - t) * t * [cx, cy] + t ** 2 * [x1, y1]
            cv2.polylines(m, [np.round(P * q).astype(np.int32)], False, 255, max(1, int(round(Wg * q))), cv2.LINE_AA)
    a = m.astype(np.float32) / 255
    if sig * q > 0.05:
        a = cv2.GaussianBlur(a, (0, 0), sig * q)
    return np.clip(cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR), 0, 1)


def fill_mask(shapes, shape_hw):
    m = np.zeros(shape_hw, np.uint8)
    for s in shapes:
        pts = []
        for x0, y0, cx, cy, x1, y1 in (g[:6] for g in s["segs"]):
            t = np.linspace(0, 1, 8, endpoint=False)[:, None]
            pts.append((1 - t) ** 2 * [x0, y0] + 2 * (1 - t) * t * [cx, cy] + t ** 2 * [x1, y1])
        if pts:
            cv2.fillPoly(m, [np.round(np.vstack(pts)).astype(np.int32)], 0 if s["hole"] else 1)
    return m.astype(bool)


def decompose(img, n_levels):
    """밝기 층: 이펙트 픽셀(L>20) 밝기 분위수로 문턱 → 층 i 마스크 = L >= 문턱 i(바깥 넓게 → 안 좁게)."""
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    fx = L > 20
    ts = np.percentile(L[fx], np.linspace(0, 100, n_levels + 1)[:-1] + 100 / (2 * n_levels)) if fx.any() else []
    out = []
    for i, t in enumerate(ts):
        m = (cv2.GaussianBlur((L >= t).astype(np.float32), (0, 0), 2.0) > 0.5).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        if m.sum() < 200:
            continue
        hi = ts[i + 1] if i + 1 < len(ts) else 256
        band = (L >= t) & (L < hi)
        col = np.median(img[band if band.sum() > 50 else (L >= t)], 0)
        out.append((m, col))
    return out


def fit(img, levels, grid_w, grid_s, grid_a, grid_in):
    """층마다 (면 안으로 줄이기 d, 띠 Wg, 흐림 sigma, 알파)를 격자에서 고른다. 줄이기: 면 경계가 딱딱하면 바깥 번짐을 못 내서
    (1차 시험: 맨 바깥 빨강 층이 띠 20·흐림 4로 거의 그대로 → 검은 바탕으로 번지는 원본과 달랐다) 면을 d px 줄이고 글로우가 그 자리를 메우게."""
    H, W = img.shape[:2]
    k = REF_W / W  # 그림 px → 1920폭 px(main에서 1920폭으로 키우므로 1)
    q = 0.5  # 차이 계산은 반 크기로(빠르게)
    sm = lambda x: cv2.resize(x, (int(W * q), int(H * q)), interpolation=cv2.INTER_AREA)
    target = sm(img.astype(np.float32))
    canvas = np.zeros_like(target)
    params, shapes_all = [], []
    cand = []  # 층마다 줄이기 후보별 (d, 윤곽, 면 마스크)
    for m, _ in levels:
        row = []
        for d in grid_in:
            mm = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))) if d else m
            if mm.sum() < 200:
                continue
            sh = coarse(mm, 2.0, 2.0, 150)
            row.append((d, sh, sm(fill_mask(sh, (H, W)).astype(np.float32)) > 0.5))
        cand.append(row)
    for i, (m, col) in enumerate(levels):
        best = None
        for d, sh, fm in cand[i]:
            for Wg in grid_w:
                for sg in grid_s:
                    cov = sm(band_glow(sh, (H, W), Wg / k, sg / k))
                    for al in grid_a:
                        a = (cov * al)[..., None]
                        c = canvas * (1 - a) + col * a
                        c[fm] = col
                        for j in range(i + 1, len(levels)):
                            c[cand[j][0][2]] = levels[j][1]  # 위 층은 줄이기 없는 면으로 가정
                        e = float(np.abs(c - target).mean())
                        if best is None or e < best[0]:
                            best = (e, d, sh, fm, Wg, sg, al)
        e, d, sh, fm, Wg, sg, al = best
        a = (sm(band_glow(sh, (H, W), Wg / k, sg / k)) * al)[..., None]
        canvas = canvas * (1 - a) + col * a
        canvas[fm] = col
        shapes_all.append(sh)
        params.append(dict(inset=d, Wg=Wg, sigma=sg, alpha=al, err=round(e, 2), color=col.round(0).tolist()))
        print(f"층 {i}: 줄이기 {d}px 띠 {Wg}px 흐림 {sg}px 알파 {al} → 차이 {e:.2f}")
    return shapes_all, params


class Writer:
    def __init__(self, W, H):
        self.W, self.H, self.oid, self.pid, self.out = W, H, 1, 1, []

    def ao(self, seg, color, ts, layer, glow, links):
        gr, gt, gc, ga = glow
        oid, p = self.oid, self.pid
        self.oid += 1
        self.pid += 3
        o = [f'<AO ID="{oid}" TypeId="3" Color="{color}" LayerId="{layer}" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
             f'GlowRadius="{round(gr)}" GlowThickness="{round(gt)}" GlowColor="{gc}" GlowAlpha="{round(ga)}">']
        for i, (x, y) in enumerate((seg[0:2], seg[2:4], seg[4:6])):
            link = links[0] if i == 0 else links[1] if i == 2 else None
            ac = f'<AC ConnPtId="{link}"/>' if link else ""
            o.append(f'<AP ID="{p + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / self.W * 100:.3f}" Y="{y / self.H * 100:.3f}">{ac}</AP>')
        self.out.append("".join(o) + "</AO>")
        return oid, p

    def fill(self, shapes, col, layer, ts, glow):
        holes = {}
        for s in shapes:
            if s["hole"]:
                holes.setdefault(s.get("parent", -2), []).append(s)
        for o in (s for s in shapes if not s["hole"] and s["segs"]):
            fs = []
            for ci, c in enumerate([o] + holes.get(o.get("cid", -1), [])):
                segs, base = c["segs"], self.pid
                n = len(segs)
                for i, s in enumerate(segs):
                    links = (base + 3 * (i - 1) + 2 if i > 0 else None, base + 3 * (i + 1) if i < n - 1 else None)
                    oid, p = self.ao(s, 0, ts if ci == 0 else TS_MIN, layer, glow if ci == 0 else (0, 0, 4294967295, 0), links)
                    fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}"/>')
            self.out.append(f'<FR Color="{col}">' + "".join(fs) + "</FR>")


def write_sfa(path, W, H, levels, shapes_all, params, mode, ts_glow):
    """mode: 'fit' 맞춘 글로우 / 'none' 글로우 없음 / 'fixed' 지금 변환기식(가장 밝은 층만 반경 10, 두께 100, 알파 180, 굵기 0.1)."""
    wr = Writer(W, H)
    defs = []
    for i, ((m, col), sh) in enumerate(zip(levels, shapes_all)):
        defs.append(f'<LayerDef ID="{i}" Name="층{i}" Visible="true" Locked="false"/>')
        c = argb(col)
        if mode == "fit":
            p = params[i]
            gt = p["Wg"] * 10 / (8 * ts_glow)
            glow, ts = (p["sigma"], gt, c, p["alpha"] * 255), ts_glow
        elif mode == "fixed" and i == len(levels) - 1:
            glow, ts = (10.0, 100.0, c, 180.0), TS_MIN
        else:
            glow, ts = (0, 0, 4294967295, 0), TS_MIN
        wr.fill(sh, c, i, ts, glow)
    name = os.path.splitext(os.path.basename(path))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"4278190080\">\n<Frame BackgroundColor=\"4278190080\" ID=\"1\" Position=\"0\">"
           + "".join(defs) + "\n" + "\n".join(wr.out) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    return wr.oid - 1


def render(sfa, W, H):
    tmp = sfa + "_r"
    os.makedirs(tmp, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), sfa, tmp,
                    "--frames", "0", "--size", f"{W}x{H}"], check=True, capture_output=True)
    return cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--levels", type=int, default=5)
    ap.add_argument("--ts-glow", type=float, default=1.0, help="글로우 거는 테두리 곡선 굵기('배' 파일 1.0)")
    ap.add_argument("--check")
    a = ap.parse_args()
    img = cv2.imread(a.image)
    # 렌더러·앱의 굵기·글로우는 화면 크기와 상관없는 절대 px(앱 내보내기 1920폭에서 맞춘 값) → 1920폭으로 키워 맞춘다
    img = cv2.resize(img, (int(REF_W), int(round(img.shape[0] * REF_W / img.shape[1]))), interpolation=cv2.INTER_CUBIC)
    H, W = img.shape[:2]
    levels = decompose(img, a.levels)
    shapes_all, params = fit(img, levels, grid_w=[10, 30, 60, 120, 200], grid_s=[4, 10, 20, 35, 60], grid_a=[0.35, 0.7, 1.0], grid_in=[0, 8, 16, 28])
    base = os.path.splitext(a.out)[0]
    shapes0 = [coarse(m, 2.0, 2.0, 150) for m, _ in levels]
    rows, report = [img], {}
    for mode, path in (("fit", a.out), ("none", base + "_noglow.sfa"), ("fixed", base + "_fixed.sfa")):
        n = write_sfa(path, W, H, levels, shapes_all if mode == "fit" else shapes0, params, mode, a.ts_glow)  # 비교판은 줄이기 없는 면
        r = render(path, W, H)
        if r.shape[:2] != (H, W):
            r = cv2.resize(r, (W, H))
        e = float(np.abs(r.astype(np.float32) - img.astype(np.float32)).mean())
        report[mode] = dict(AO=n, KB=round(os.path.getsize(path) / 1024, 1), 차이=round(e, 2))
        cv2.putText(r, f"{mode} diff {e:.2f}", (12, 36), 0, 1.0, (255, 255, 255), 2)
        rows.append(r)
    print(report)
    print("층별 글로우", [{k: p[k] for k in ("inset", "Wg", "sigma", "alpha", "err")} for p in params])
    if a.check:
        cv2.putText(rows[0], "original", (12, 36), 0, 1.0, (255, 255, 255), 2)
        sheet = np.vstack([np.hstack(rows[:2]), np.hstack(rows[2:])])
        cv2.imwrite(a.check, cv2.resize(sheet, None, fx=0.5, fy=0.5), [cv2.IMWRITE_JPEG_QUALITY, 90])


if __name__ == "__main__":
    main()
