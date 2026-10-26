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


TIPS = False  # --tips: 불 층만 꺾인 점을 고정하고 사이만 다듬음 + 흐림을 줄이고 열림(가는 끝을 지움)을 뺌.
# 배경(연기·하늘)·로봇은 예전처럼 매끈하게 — 모두에 걸면 연기 가장자리에 잔톱니가 생겼다(2026-10-26)


def blob(mask, blur=2.0, tips=False):
    """덩어리를 매끈하게(흐림 후 반 넘는 곳) — 픽셀 계단·잔점을 없앤다."""
    if tips:
        blur = min(blur, 1.0)
    m = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), blur) > 0.5
    if tips:  # 열림은 3px 미만 불꽃 끝을 지운다 → 잔점은 넓이로만 거른다(MIN_AREA)
        return m.astype(np.uint8)
    return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def bg_lab(img):
    return cv2.cvtColor(cv2.bilateralFilter(img, 7, 30, 7), cv2.COLOR_BGR2LAB).astype(np.float32)


def bg_centers(labs, bgs, k):
    """배경 색 묶음 중심(Lab) — 여러 프레임을 한꺼번에 넣으면 영상 전체 공통 묶음. 넓은 것부터 정렬."""
    sample = np.concatenate([lab[bg > 0] for lab, bg in zip(labs, bgs)])
    cv2.setRNGSeed(0)
    _, lab_n, cent = cv2.kmeans(sample[:: max(1, len(sample) // 60000)], k, None,
                                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    return cent[np.argsort(-np.bincount(lab_n.ravel(), minlength=k))]


def bg_clusters(img, bg, k, cent=None):
    """배경 영역을 Lab k-평균 색 묶음으로 → 마스크 목록(넓은 것부터). 밝기만으로 나누면 색이 다른 하늘·연기·건물이 합쳐진다.
    cent를 주면(영상 공통 묶음) 그 순서를 그대로 쓴다 — 프레임마다 층 순서가 바뀌지 않게."""
    lab = bg_lab(img)
    if cent is None:
        cent = bg_centers([lab], [bg], k)
    idx = cv2.medianBlur(np.linalg.norm(lab[..., None, :] - cent[None, None], axis=3).argmin(2).astype(np.uint8), 5)
    return [(idx == c) & (bg > 0) for c in range(len(cent))]


def under(sel, upper, r):
    """아래 층을 위 층 밑으로 r px 넓힌다(위 층 자리로만). 배경은 불 자리를 비우고 둘 다 다듬기로 안쪽으로 당겨져
    그 틈으로 바탕색이 검은 선처럼 보였다(2026-10-26 사용자 앱 화면). 불 쪽을 넓히면 불꽃 끝이 둥글어지고 테가 생겨서, 배경 쪽을 넓힌다."""
    if r <= 0:
        return sel
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(r) + 1,) * 2)
    return (sel | (cv2.dilate(sel.astype(np.uint8), k).astype(bool) & (upper > 0))).astype(bool)


def shapes_of(mask, pad=4, tips=False):
    """가장자리에 닿은 면은 화면 밖으로 pad px 늘려 윤곽을 딴다 — 안 그러면 윤곽 다듬기가 안쪽으로 당겨 화면 둘레에 바탕색 틀이 보인다."""
    mk = cv2.copyMakeBorder(mask.astype(np.uint8), pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    _, sh = outline_mask(mk * 255, TOL, MIN_AREA, SIGMA, pin=tips)
    for s in sh:
        s["segs"] = [[v - pad for v in g[:6]] + list(g[6:]) for g in s["segs"]]
    out = []
    for s in sh:  # 작은 구멍은 버린다(위 층이 덮거나 눈에 안 띔)
        if s["hole"]:
            P = np.array([g[:2] for g in s["segs"]], np.float32)
            if len(P) < 3 or abs(cv2.contourArea(P)) < MIN_HOLE:
                continue
        out.append(s)
    return out


def fill_layer(wr, out, shapes, W, col, layer, glow=None):
    """한 층: 바깥 윤곽마다 FR(구멍 포함), 경계 곡선은 투명·최소 굵기, 지정 레이어.
    glow=(반경, 두께, ARGB, 알파 0–255): 투명 경계 곡선에 글로우만 걸어 면 둘레에 빛 번짐(글로우는 선 색과 따로 그려짐, docs/SFA-VIEWER)."""
    holes = {}
    for s in shapes:
        if s["hole"]:
            holes.setdefault(s.get("parent", -2), []).append(s)
    frs = []
    for o in (s for s in shapes if not s["hole"] and s["segs"]):
        fs = []
        for ci, c in enumerate([o] + holes.get(o.get("cid", -1), [])):
            for seg in c["segs"]:
                oid, p = wr.curve_ao(out, seg, W, 0, ecs.TS_MIN, glow if (glow and ci == 0) else None, layer=layer)
                fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}" />')
        frs.append(f'<FR Color="{col}">' + "".join(fs) + '</FR>')
    out.extend(frs)


def levels(region, L, n):
    """region 안 밝기(L) 분위로 n단계 문턱."""
    v = L[region > 0]
    return np.percentile(v, np.linspace(0, 100, n + 1)[:-1]) if v.size else []


def regions(img, robot):
    """불(따뜻하고 밝은 큰 덩어리)·배경 마스크와 밝기 L."""
    H, W = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    warm = ((hsv[..., 0] <= 35) | (hsv[..., 0] >= 170)) & (hsv[..., 1] > 90) & (hsv[..., 2] > 150)
    # 불은 로봇 자리도 포함해 그린다(로봇 층이 위에서 덮음) — 비워 두면 로봇 둘레에 틈이 생겨 로봇 층을 넓혀야 했고, 그게 굵은 갈색 테두리가 됐다
    fire = blob(warm | (L > 225), 3.0, TIPS)
    n, cc, st, _ = cv2.connectedComponentsWithStats(fire)  # 큰 덩어리만(배경의 붉은 잔무늬 제외)
    fire = np.isin(cc, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > H * W * 0.01]).astype(np.uint8)
    bg = (fire == 0).astype(np.uint8)  # 배경도 로봇 밑까지 칠함(로봇 층이 위에서 덮음)
    return L, fire, bg


def layer_names(a, robot_any):
    """레이어 목록을 미리 고정한다(영상이면 모든 프레임이 같은 레이어 번호를 쓴다)."""
    n = ["배경색", "배경 묘사", "회로 선"]
    for i in range(a.fire_levels):
        n.append(f"폭발 {i + 1}" + (" (가장 어두움)" if i == 0 else " (중심부)" if i == a.fire_levels - 1 else ""))
    return n + (["로봇"] if robot_any else [])


def clip_shared(imgs, robots, a):
    """영상 공통 기준(실험 3): 밝기 문턱·색·배경 묶음을 프레임마다 따로 정하지 않고 클립 전체에서 한 번 정한다.
    프레임마다 따로 정하면 같은 불이 프레임마다 다른 단계·색으로 나뉘어 깜빡인다(추정, 이 실험으로 확인)."""
    R = [regions(im, rb) for im, rb in zip(imgs, robots)]
    sh = {}
    fL = np.concatenate([L[f > 0] for L, f, _ in R])
    if fL.size:
        sh["fire_ts"] = list(np.percentile(fL, np.linspace(0, 100, a.fire_levels + 1)[:-1]))
        sh["fire_cols"] = []
        for i, t in enumerate(sh["fire_ts"]):
            hi = sh["fire_ts"][i + 1] if i + 1 < len(sh["fire_ts"]) else 256
            px = np.concatenate([im[(f > 0) & (L >= t) & (L < hi)] for im, (L, f, _) in zip(imgs, R)])
            sh["fire_cols"].append(np.median(px, 0) if len(px) else np.zeros(3))
    if a.bg_k > 0:
        labs = [bg_lab(im) for im in imgs]
        sh["bg_cent"] = bg_centers(labs, [b for _, _, b in R], a.bg_k)
        cols = [[] for _ in range(a.bg_k)]
        for im, (_, _, b) in zip(imgs, R):
            for c, m in enumerate(bg_clusters(im, b, a.bg_k, sh["bg_cent"])):
                cols[c].append(im[m])
        sh["bg_cols"] = [np.median(np.concatenate(c), 0) if sum(len(x) for x in c) else np.zeros(3) for c in cols]
        sh["base"] = sh["bg_cols"][0]
    else:
        bL = np.concatenate([L[b > 0] for L, _, b in R])
        sh["bg_ts"] = list(np.percentile(bL, np.linspace(0, 100, a.bg_levels + 1)[:-1]))
        lo = np.percentile(bL, 30)
        sh["base"] = np.median(np.concatenate([im[(b > 0) & (L <= lo)] for im, (L, _, b) in zip(imgs, R)]), 0)
        sh["bg_cols"] = [np.median(np.concatenate([im[(b > 0) & (L >= t)] for im, (L, _, b) in zip(imgs, R)]), 0)
                         for t in sh["bg_ts"]]
    return sh


def convert(img, a, wr, robot, names_out, sh=None):
    """그림 한 장 → 층 쌓기 AO/FR 목록. sh(clip_shared 결과)가 있으면 문턱·색을 그것으로 고정."""
    H, W = img.shape[:2]
    L, fire, bg = regions(img, robot)
    body = []
    lid = names_out.index
    # 1. 배경 바탕색: 화면 전체 사각형 하나
    # 바탕색 = 배경에서 어두운 쪽 30%의 중앙값(전체 중앙값은 폭발 언저리 빛·로봇이 섞여 갈색이 됐다)
    if sh:
        base = sh["base"]
    else:
        sel0 = (bg > 0) & (L <= np.percentile(L[bg > 0], 30)) if bg.any() else bg > 0
        if a.bg_k > 0 and bg.sum() > 100:  # 색 묶음 방식이면 바탕색 = 가장 넓은 묶음 색(층 사이 틈·가장자리에 보여도 티 안 나게)
            sel0 = bg_clusters(img, bg, a.bg_k)[0]
        base = np.median(img[sel0], 0) if sel0.any() else np.zeros(3)
    rect = {"hole": False, "cid": 0, "parent": -1,
            "segs": [[x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, x1, y1] for (x0, y0), (x1, y1) in
                     zip([(0, 0), (W, 0), (W, H), (0, H)], [(W, 0), (W, H), (0, H), (0, 0)])]}
    fill_layer(wr, body, [rect], W, argb(base), lid("배경색"))
    # 2. 배경 묘사
    k = lid("배경 묘사")
    if a.bg_k > 0 and bg.sum() > 100:
        # 색 묶음: 밝기만으로 나누니 청록 하늘·보라 연기·건물처럼 색이 다르고 밝기가 비슷한 곳이 한 덩어리가 됐다(2026-10-26 생성 그림)
        cl = bg_clusters(img, bg, a.bg_k, sh["bg_cent"] if sh else None)
        if not sh:
            cl = sorted(cl, key=lambda m: -m.sum())
        for c, sel in enumerate(cl):
            if c == 0:  # 가장 넓은 묶음은 바탕색 층이 이미 덮음 → 나머지를 넓은 것부터 위에
                continue
            m = blob(under(sel, fire, a.overlap), 1.0)
            if sel.sum() > 50 and m.any():
                fill_layer(wr, body, shapes_of(m), W, argb(sh["bg_cols"][c] if sh else np.median(img[sel], 0)), k)
    else:  # 밝기 단계(바탕보다 밝은 무늬부터)
        ts = sh["bg_ts"] if sh else list(levels(bg, L, a.bg_levels))
        for j, t in enumerate(ts):
            if j == 0:
                continue
            sel = (bg > 0) & (L >= t)
            m = blob(under(sel, fire, a.overlap), 1.0)
            if sel.any():
                fill_layer(wr, body, shapes_of(m), W, argb(sh["bg_cols"][j] if sh else np.median(img[sel], 0)), k)
    # 3. 회로 선: 배경 안 '주변보다 밝은 가는 선' → 선 객체
    k = lid("회로 선")
    # 회로 선은 붉은·노란 가는 선: 회색 밝기 톱햇(110 이상)은 붉은 선을 놓쳤다 → 채널 최댓값으로 '주변보다 밝은 가는 선'
    th = cv2.morphologyEx(img.max(2), cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    hm = ((th > 35) & (cv2.erode(bg, np.ones((5, 5), np.uint8)) > 0)).astype(np.uint8)
    for seg in joined_strokes(img, hm, 2.0, min_len=10, sigma=2.0):
        wr.curve_ao(body, seg, W, argb(seg[7:10]), max(ecs.TS_MIN, thick(seg[6], W) * ecs.LINE_SCALE), layer=k)
    # 4. 폭발: 가장 어두운 부분(폭발 전체) → … → 가장 밝은 중심부
    ts = sh["fire_ts"] if sh and "fire_ts" in sh else list(levels(fire, L, a.fire_levels))
    for i, t in enumerate(ts):
        hi = ts[i + 1] if i + 1 < len(ts) else 256
        sel = (fire > 0) & (L >= t) & (L < hi)
        m = fire if i == 0 else blob((fire > 0) & (L >= t), 2.0, TIPS)
        if not (m.any() and (sel.any() or sh)):
            continue
        k = lid(layer_names(a, False)[3 + i])
        col = sh["fire_cols"][i] if sh and "fire_cols" in sh else np.median(img[sel], 0)
        if a.feather > 0 and i > 0:  # 넓고 옅은 번짐 먼저
            r = int(round(a.feather))
            wide = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) & fire
            fill_layer(wr, body, shapes_of(wide, tips=TIPS), W, argb(col, 0.35), k)
        core = i == len(ts) - 1
        glow = (a.glow, 100.0, argb(col), 180.0) if (core and a.glow > 0) else None
        fill_layer(wr, body, shapes_of(m, tips=TIPS), W, argb(col), k, glow)
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
        # 밝은 가는 선(역광 테두리·반사광): 회로 선과 같은 톱햇, 로봇 안쪽만
        thr = cv2.morphologyEx(img.max(2), cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        hm = ((thr > 30) & (cv2.erode(robot, np.ones((3, 3), np.uint8)) > 0)).astype(np.uint8)
        for seg in joined_strokes(img, hm, 1.5, min_len=8, sigma=1.5):
            wr.curve_ao(body, seg, W, argb(seg[7:10]), max(ecs.TS_MIN, thick(seg[6], W) * ecs.LINE_SCALE), layer=k)
        dm, _, _ = line_layer(img, 1.5, valid=cv2.erode(robot, np.ones((5, 5), np.uint8)))
        for seg in joined_strokes(img, dm, 2.0, min_len=6, sigma=1.5):
            wr.curve_ao(body, seg, W, argb(seg[7:10]), max(ecs.TS_MIN, thick(seg[6], W) * ecs.LINE_SCALE), layer=k)
    return body, base


def read_frames(path, start, n, step):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    out = []
    while len(out) < n:
        ok, f = cap.read()
        if not ok:
            break
        out.append(f)
        for _ in range(step - 1):
            cap.read()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="그림, 또는 --clip이면 영상")
    ap.add_argument("out")
    ap.add_argument("--parts")
    ap.add_argument("--fire-levels", type=int, default=6)
    ap.add_argument("--bg-levels", type=int, default=3)
    ap.add_argument("--robot-levels", type=int, default=3)
    ap.add_argument("--bg-k", type=int, default=0, help="배경을 색 묶음 k개로(0이면 밝기 단계 --bg-levels). 생성 그림처럼 배경 색이 여러 가지면 9 안팎")
    ap.add_argument("--feather", type=float, default=0.0,
                    help="폭발 층마다 넓고 옅은(알파 0.35) 번짐 층을 이 반경(px)만큼 먼저 깐다. 0이면 끔")
    ap.add_argument("--glow", type=float, default=0.0, help="중심부 층 둘레 글로우 반경(px). 0이면 끔")
    ap.add_argument("--clip", type=int, nargs=2, metavar=("시작", "장수"), help="영상의 시작 프레임부터 장수만큼(24,24 그대로 한 장씩)")
    ap.add_argument("--shared", action="store_true", help="영상: 문턱·색·배경 묶음을 클립 전체 공통으로(실험 3)")
    ap.add_argument("--hold", type=float, default=6.0, help="영상: 직전 장과 평균 차가 이보다 작으면 같은 그림(걸이)으로 보고 직전 그림을 다시 씀. 0이면 끔")
    ap.add_argument("--check")
    ap.add_argument("--overlap", type=float, default=4.0, help="배경 층을 불 밑으로 이만큼(px) 넓혀 틈을 덮음. 0이면 끔")
    ap.add_argument("--tips", action="store_true", help="테두리 마감: 불꽃 끝·가시를 살린다(꺾인 점 고정 다듬기, 흐림↓, 열림 끔)")
    a = ap.parse_args()
    global TIPS
    TIPS = a.tips
    imgs = read_frames(a.image, a.clip[0], a.clip[1], 1) if a.clip else [cv2.imread(a.image)]
    H, W = imgs[0].shape[:2]
    ecs.H = H
    robot = np.zeros((H, W), np.uint8)
    if a.parts:
        z = np.load(a.parts)
        names = [str(v) for v in z["names"]]
        lab = cv2.resize(z["label"], (W, H), interpolation=cv2.INTER_NEAREST)
        if "로봇" in names:
            robot = blob(lab == names.index("로봇"), 1.5)
    names_out = layer_names(a, robot.any())
    sh = clip_shared(imgs, [robot] * len(imgs), a) if a.shared else None
    wr = Writer()
    defs = "".join(f'<LayerDef ID="{i}" Name="{n}" Visible="true" Locked="false" />' for i, n in enumerate(names_out))
    frames, base, src = [], None, []
    for pos, img in enumerate(imgs):
        # 원화는 2·3장 걸이가 많다(c0426: 같은 그림 사이 평균 차 3.5, 바뀔 때 29–139). 같은 그림이면 직전 그림을 그대로 다시 변환해
        # 같은 SFA 그림이 되게 한다 — 압축 잡음 때문에 따로 변환하면 걸어 둔 장에서도 층 경계가 흔들린다.
        if src and a.hold > 0 and np.abs(img.astype(np.float32) - src[-1]).mean() < a.hold:
            img = src[-1]
        src.append(img)
        body, b = convert(img, a, wr, robot, names_out, sh)
        base = b if base is None else base
        frames.append(f'<Frame BackgroundColor="{argb(b) & 0xFFFFFFFF}" ID="{pos + 1}" Position="{pos}">' + defs + "\n"
                      + "\n".join(body) + "\n</Frame>")
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"{len(frames)}\" BackgroundColor=\"{argb(base)}\">\n" + "\n".join(frames) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    print("프레임", len(frames), "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 2))
    if a.check:
        import subprocess
        tmp = a.check + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sfa_render.py"), a.out, tmp, "--frames",
                        ",".join(map(str, range(len(frames)))), "--size", f"{W}x{H}"], check=True, capture_output=True)
        recs = [cv2.resize(cv2.imread(os.path.join(tmp, f)), (W, H)) for f in sorted(os.listdir(tmp))]
        if len(imgs) == 1:
            cv2.imwrite(a.check, np.hstack([imgs[0], recs[0]]))
        else:  # 깜빡임: 원본에 없는 프레임 간 변화(|Δ렌더 − Δ원본| 평균), 원본과의 차이
            fl = np.mean([np.abs((recs[i + 1].astype(np.float32) - recs[i]) - (imgs[i + 1].astype(np.float32) - imgs[i])).mean()
                          for i in range(len(recs) - 1)])
            err = np.mean([np.abs(r.astype(np.float32) - o).mean() for r, o in zip(recs, imgs)])
            print("깜빡임", round(float(fl), 2), "원본차", round(float(err), 2))
            np.save(a.check + ".npy", np.stack(recs))


if __name__ == "__main__":
    main()
