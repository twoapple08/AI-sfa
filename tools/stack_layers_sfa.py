#!/usr/bin/env python3
"""이펙트 컷 → '층층이 쌓는' SFA (2026-10-25 사용자 지시).

사용자: "색을 설치하는 방식은 층층이 쌓는 방식으로 레이어로 구간을 쪼개고 —
기본으로 깔리는 배경색 | 배경 묘사 오브젝트들 | 회로 선 같은 거 | 폭발 가장 어두운 부분 | 다음으로 밝은 부분 | … | 폭발 가장 밝은 부분(중심부) | 로봇 오브젝트".
- 각 층은 '그 밝기 이상인 곳 전체'를 통째로 채운 덩어리(밝을수록 좁다). 위 층이 아래 층을 덮으므로 이웃 경계를 맞출 필요가 없고
  곡선이 적다(docs/SFA-CURVE-OPTIMIZATION-2026-10-25.md 원칙: 점을 따라가지 말고 곡선으로 형태를 만든다).
- 영역: 폭발 = 따뜻한 색이면서 밝은 곳(색으로 직접. GDINO 상자는 화면 전체를 잡았다), 로봇 = 부위 지도(tools/part_masks.py --prompts)의 '로봇'.
- 레이어마다 SFA LayerDef를 따로 두고 이름을 붙인다.
사용: python tools/stack_layers_sfa.py <그림> <출력.sfa> [--parts 부위.npz] [--fire-levels 6] [--check 비교.jpg]
원본 장면에서 딴 결과이므로 저장소에 넣지 않는다.
"""
import argparse
import os
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_clip_sfa import Writer, argb, thick  # noqa: E402
from effect_layers import joined_strokes, line_layer  # noqa: E402
from effect_vectorize import outline_mask  # noqa: E402
import effect_clip_sfa as ecs  # noqa: E402

TOL, SIGMA = 2.5, 3.0  # 덩어리 윤곽: 크게 다듬고 넉넉한 오차(곡선 하나가 길게 휘게)
MIN_AREA, MIN_HOLE = 60, 200


def blob(mask, blur=2.0):
    """덩어리를 매끈하게(흐림 후 반 넘는 곳) — 픽셀 계단·잔점을 없앤다."""
    m = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), blur) > 0.5
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def shapes_of(mask):
    _, sh = outline_mask(mask * 255, TOL, MIN_AREA, SIGMA)
    out = []
    for s in sh:  # 작은 구멍은 버린다(위 층이 덮거나 눈에 안 띔)
        if s["hole"]:
            P = np.array([g[:2] for g in s["segs"]], np.float32)
            if len(P) < 3 or abs(cv2.contourArea(P)) < MIN_HOLE:
                continue
        out.append(s)
    return out


def fill_layer(wr, out, shapes, W, col, layer):
    """한 층: 바깥 윤곽마다 FR(구멍 포함), 경계 곡선은 투명·최소 굵기, 지정 레이어."""
    holes = {}
    for s in shapes:
        if s["hole"]:
            holes.setdefault(s.get("parent", -2), []).append(s)
    frs = []
    for o in (s for s in shapes if not s["hole"] and s["segs"]):
        fs = []
        for ci, c in enumerate([o] + holes.get(o.get("cid", -1), [])):
            for seg in c["segs"]:
                oid, p = wr.curve_ao(out, seg, W, 0, ecs.TS_MIN, layer=layer)
                fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}" />')
        frs.append(f'<FR Color="{col}">' + "".join(fs) + '</FR>')
    out.extend(frs)


def levels(region, L, n):
    """region 안 밝기(L) 분위로 n단계 문턱."""
    v = L[region > 0]
    return np.percentile(v, np.linspace(0, 100, n + 1)[:-1]) if v.size else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--parts")
    ap.add_argument("--fire-levels", type=int, default=6)
    ap.add_argument("--bg-levels", type=int, default=3)
    ap.add_argument("--robot-levels", type=int, default=3)
    ap.add_argument("--check")
    a = ap.parse_args()
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    ecs.H = H
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    robot = np.zeros((H, W), np.uint8)
    if a.parts:
        z = np.load(a.parts)
        names = [str(v) for v in z["names"]]
        lab = cv2.resize(z["label"], (W, H), interpolation=cv2.INTER_NEAREST)
        if "로봇" in names:
            robot = blob(lab == names.index("로봇"), 1.5)
    warm = ((hsv[..., 0] <= 35) | (hsv[..., 0] >= 170)) & (hsv[..., 1] > 90) & (hsv[..., 2] > 150)
    fire = blob((warm | (L > 225)) & (robot == 0), 3.0)
    n, cc, st, _ = cv2.connectedComponentsWithStats(fire)  # 큰 덩어리만(배경의 붉은 잔무늬 제외)
    fire = np.isin(cc, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > H * W * 0.01]).astype(np.uint8)
    bg = ((fire == 0) & (robot == 0)).astype(np.uint8)

    wr = Writer()
    body, names_out = [], []

    def lid(name):
        names_out.append(name)
        return len(names_out) - 1

    # 1. 배경 바탕색: 화면 전체 사각형 하나
    # 바탕색 = 배경에서 어두운 쪽 30%의 중앙값(전체 중앙값은 폭발 언저리 빛·로봇이 섞여 갈색이 됐다)
    sel0 = (bg > 0) & (L <= np.percentile(L[bg > 0], 30)) if bg.any() else bg > 0
    base = np.median(img[sel0], 0) if sel0.any() else np.zeros(3)
    k = lid("배경색")
    rect = {"hole": False, "cid": 0, "parent": -1,
            "segs": [[x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, x1, y1] for (x0, y0), (x1, y1) in
                     zip([(0, 0), (W, 0), (W, H), (0, H)], [(W, 0), (W, H), (0, H), (0, 0)])]}
    fill_layer(wr, body, [rect], W, argb(base), k)
    # 2. 배경 묘사: 배경 안 밝기 단계(바탕보다 밝은 무늬부터)
    k = lid("배경 묘사")
    for t in list(levels(bg, L, a.bg_levels))[1:]:
        m = blob((bg > 0) & (L >= t), 1.0)
        sel = (bg > 0) & (L >= t)
        if sel.any():
            fill_layer(wr, body, shapes_of(m), W, argb(np.median(img[sel], 0)), k)
    # 3. 회로 선: 배경 안 '주변보다 밝은 가는 선' → 선 객체
    k = lid("회로 선")
    # 회로 선은 붉은·노란 가는 선: 회색 밝기 톱햇(110 이상)은 붉은 선을 놓쳤다 → 채널 최댓값으로 '주변보다 밝은 가는 선'
    mx = img.max(2)
    th = cv2.morphologyEx(mx, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    hm = ((th > 35) & (cv2.erode(bg, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
    for seg in joined_strokes(img, hm, 2.0, min_len=10, sigma=2.0):
        wr.curve_ao(body, seg, W, argb(seg[7:10]), max(ecs.TS_MIN, thick(seg[6], W) * ecs.LINE_SCALE), layer=k)
    # 4. 폭발: 가장 어두운 부분(폭발 전체) → … → 가장 밝은 중심부
    ts = list(levels(fire, L, a.fire_levels))
    for i, t in enumerate(ts):
        hi = ts[i + 1] if i + 1 < len(ts) else 256
        sel = (fire > 0) & (L >= t) & (L < hi)
        m = fire if i == 0 else blob((fire > 0) & (L >= t), 2.0)
        if sel.any() and m.any():
            k = lid(f"폭발 {i + 1}" + (" (가장 어두움)" if i == 0 else " (중심부)" if i == len(ts) - 1 else ""))
            fill_layer(wr, body, shapes_of(m), W, argb(np.median(img[sel], 0)), k)
    # 5. 로봇: 몸체 밝기 단계 + 어두운 선
    if robot.any():
        k = lid("로봇")
        rts = list(levels(robot, L, a.robot_levels))
        for i, t in enumerate(rts):
            hi = rts[i + 1] if i + 1 < len(rts) else 256
            sel = (robot > 0) & (L >= t) & (L < hi)
            m = robot if i == 0 else blob((robot > 0) & (L >= t), 1.5)
            if sel.any() and m.any():
                fill_layer(wr, body, shapes_of(m), W, argb(np.median(img[sel], 0)), k)
        dm, _, _ = line_layer(img, 1.5, valid=cv2.erode(robot, np.ones((5, 5), np.uint8)))
        for seg in joined_strokes(img, dm, 2.0, min_len=6, sigma=1.5):
            wr.curve_ao(body, seg, W, argb(seg[7:10]), max(ecs.TS_MIN, thick(seg[6], W) * ecs.LINE_SCALE), layer=k)

    defs = "".join(f'<LayerDef ID="{i}" Name="{n}" Visible="true" Locked="false" />' for i, n in enumerate(names_out))
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"{argb(base)}\">\n<Frame BackgroundColor=\"{argb(base) & 0xFFFFFFFF}\" ID=\"1\" Position=\"0\">"
           + defs + "\n" + "\n".join(body) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    print("레이어", names_out, "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 2))
    if a.check:
        import subprocess
        tmp = a.check + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sfa_render.py"), a.out, tmp, "--frames", "0", "--size", f"{W}x{H}"],
                       check=True, capture_output=True)
        rec = cv2.resize(cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0])), (W, H))
        cv2.imwrite(a.check, np.hstack([img, rec]))


if __name__ == "__main__":
    main()
