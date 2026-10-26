#!/usr/bin/env python3
"""인물 그림 → '사람이 그리는 방식' SFA (2026-10-26, docs/USER-SFA-TECHNIQUES-2026-10-26.md).

사용자 SFA 5개(A 4 + B 1)에서 본 방식 그대로:
- 레이어: 아래부터 배경 → 부위별 밑색(옷·얼굴·입·눈·눈동자·머리카락·선글라스) → 명암 → 선화(맨 위, 선 전용).
- 밑색: 부위마다 불투명 면을 **성긴 곡선 몇 개**로 닫는다(사람 그림: 면당 경계 조각 약 6). 경계는 투명 곡선(안 보임).
  선화가 덮으니 가장자리는 정확할 필요 없고, 이웃과 틈이 없게 부위 면을 3px 넓힌다.
- 명암: 면을 겹겹이 쌓지 않고 **반투명 굵은 붓선**(사람 그림: 알파 10–51의 선). 부위 안 '밑색보다 어두운 곳'의 뼈대를 따라
  그 폭만큼 굵은 선을 반투명으로 긋는다(두 단계: 그늘, 깊은 그늘).
- 선화: 선화 지도(tools/lineart_map.py)의 가운데 줄기를 이어 붙인 획. **이어지는 곡선은 끝점을 연결(AC)**해 한 줄로,
  굵기는 선 진하기에 따라 ThicknessScale 0.1(가는 결)–0.3(주 윤곽)(사람 그림 중앙 0.2–0.3, 앱 하한 0.1).
- 화면: 세로 그림을 16:9 가운데에(높이 그대로).
사용(samenv 필요 없음): python tools/person_sfa.py <그림> <선화지도.png> <부위.npz> <출력.sfa> [--check 비교.jpg]
원본(사용자 그림체 LoRA 생성물)과 결과는 저장소에 넣지 않는다.
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
from effect_layers import joined_strokes  # noqa: E402
from effect_vectorize import outline_mask  # noqa: E402
from effect_clip_sfa import argb  # noqa: E402

# 아래 → 위. 속눈썹은 선화로만(면 없음).
FILL_ORDER = ["배경", "옷", "얼굴", "입", "눈", "눈동자", "머리카락", "선글라스"]
TS_MIN, TS_MAX = 0.1, 0.3


class W2:
    """끝점 연결(AC)을 쓰는 작성기. 좌표는 16:9 화면(폭 CW, 높이 H) 백분율."""

    def __init__(self, CW, H, xoff):
        self.oid, self.pid, self.CW, self.H, self.xoff = 1, 1, CW, H, xoff
        self.out = []

    def _ao(self, pts, color, ts, layer, links=(None, None)):
        oid, p = self.oid, self.pid
        self.oid += 1
        self.pid += 3
        o = [f'<AO ID="{oid}" TypeId="3" Color="{color}" LayerId="{layer}" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" '
             f'ObjectScale="1.0" GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
        for i, (x, y) in enumerate(pts):
            flag = 8 if i == 0 else 9  # 사용자 파일의 점 표시(시작 8, 나머지 9)
            link = links[0] if i == 0 else links[1] if i == 2 else None
            ac = f'<AC ConnPtId="{link}"/>' if link else ""
            o.append(f'<AP ID="{p + i}" Flags="{flag}" Index="{i}" X="{(x + self.xoff) / self.CW * 100:.3f}" Y="{y / self.H * 100:.3f}">{ac}</AP>')
        o.append("</AO>")
        self.out.append("".join(o))
        return oid, p

    def chain(self, segs, color, ts_list, layer):
        """이어지는 곡선들: i번 끝점(p+2)과 i+1번 시작점(다음 p)을 서로 연결."""
        n = len(segs)
        base = self.pid
        ids = []
        for i, s in enumerate(segs):
            prev_end = base + 3 * (i - 1) + 2 if i > 0 else None
            next_start = base + 3 * (i + 1) if i < n - 1 else None
            ids.append(self._ao([s[0:2], s[2:4], s[4:6]], color if not isinstance(color, list) else color[i], ts_list[i], layer,
                                (prev_end, next_start)))
        return ids

    def fill(self, shapes, col, layer):
        """바깥 윤곽마다 FR(구멍 포함). 경계 곡선은 투명(색 0)·최소 굵기, 윤곽 안에서 연결."""
        holes = {}
        for s in shapes:
            if s["hole"]:
                holes.setdefault(s.get("parent", -2), []).append(s)
        n = 0
        for o in (s for s in shapes if not s["hole"] and s["segs"]):
            fs = []
            for ci, c in enumerate([o] + holes.get(o.get("cid", -1), [])):
                segs = c["segs"]
                ids = self.chain(segs, 0, [TS_MIN] * len(segs), layer)
                fs += [f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}"/>'
                       for oid, p in ids]
            self.out.append(f'<FR Color="{col}">' + "".join(fs) + "</FR>")
            n += 1
        return n


def drop_doubles(runs, H, W, r=2, cover=0.8):
    """나란히 붙은 두 줄을 하나로: 굵은 곡선부터 그려 두고, 곡선의 80% 이상이 이미 그린 선 r px 안에 들면 뺀다.
    선화 지도의 굵은 선이 속이 빈 테두리로 잡히면 뼈대가 두 줄이 됐다(2026-10-26 광사 머리 가장자리·코트 끝).
    긴 줄기부터 남기자 가는 쪽이 살고 굵은 윤곽이 빠져 강약이 사라졌다 → 굵기 순.
    빼낸 곡선 때문에 줄기가 끊기면 남은 곡선을 이어진 토막끼리 나눠 반환한다(연결 AC가 실제로 맞닿은 끝끼리만 되게)."""
    def pts(s):
        t = np.linspace(0, 1, max(3, int(math.dist(s[0:2], s[4:6]))))[:, None]
        P = (1 - t) ** 2 * np.array(s[0:2]) + 2 * (1 - t) * t * np.array(s[2:4]) + t ** 2 * np.array(s[4:6])
        return np.clip(np.round(P).astype(int), 0, [W - 1, H - 1])
    occ = np.zeros((H, W), np.uint8)
    keep = [[True] * len(g) for g in runs]
    order = sorted(((gi, si) for gi, g in enumerate(runs) for si in range(len(g))),
                   key=lambda t: (-runs[t[0]][t[1]][6], -math.dist(runs[t[0]][t[1]][0:2], runs[t[0]][t[1]][4:6])))
    dropped = 0
    for gi, si in order:
        P = pts(runs[gi][si])
        if occ[P[:, 1], P[:, 0]].mean() >= cover:
            keep[gi][si] = False
            dropped += 1
        else:
            cv2.polylines(occ, [P.astype(np.int32)], False, 1, 2 * r + 1)
    out = []
    for g, kg in zip(runs, keep):
        cur = []
        for s, kp in zip(g, kg):
            if kp:
                cur.append(s)
            elif cur:
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
    return out, dropped


def coarse(mask, tol=4.0, sigma=4.0, min_area=150):
    """성긴 윤곽: 크게 다듬고 넉넉한 오차로 맞춘다(면당 곡선 조각 적게)."""
    pad = 6
    mk = cv2.copyMakeBorder(mask.astype(np.uint8), pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    _, sh = outline_mask(mk * 255, tol, min_area, sigma)
    for s in sh:
        s["segs"] = [[v - pad for v in g[:6]] for g in s["segs"]]
    return [s for s in sh if not s["hole"] or len(s["segs"]) >= 3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("linemap")
    ap.add_argument("parts")
    ap.add_argument("out")
    ap.add_argument("--check")
    ap.add_argument("--shade-alpha", type=float, default=0.3)
    ap.add_argument("--black", action="store_true", help="선 색을 검정 하나로(원본 선 색을 따르면 눈·머리 끝 선이 노랑·회색으로 흐렸다)")
    ap.add_argument("--clean", action="store_true", help="끊긴 틈 잇기(--gap px) + 나란한 두 줄 하나로")
    ap.add_argument("--gap", type=float, default=8.0)
    ap.add_argument("--lines-only", action="store_true", help="채색(배경 색 묶음·밑색·명암) 없이 흰 바탕 + 선화만")
    a = ap.parse_args()
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    CW = int(round(H * 16 / 9))
    xoff = (CW - W) / 2
    lm = cv2.cvtColor(cv2.resize(cv2.imread(a.linemap), (W, H)), cv2.COLOR_BGR2GRAY)
    z = np.load(a.parts)
    names = [str(v) for v in z["names"]]
    lab = cv2.resize(z["label"], (W, H), interpolation=cv2.INTER_NEAREST)
    line = lm < 200
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    wr = W2(CW, H, xoff)
    layers, stats = [], {"면": 0, "면 경계 조각": 0, "명암 붓선": 0, "선 곡선": 0}

    def lid(nm):
        layers.append(nm)
        return len(layers) - 1

    # 1) 배경: 흰 바탕 사각형 + 배경 안 색 묶음(노란 원 등)을 성긴 면으로
    bgcol = np.median(img[(lab == names.index("배경")) & ~line], 0) if "배경" in names and not a.lines_only else np.array([255, 255, 255])
    k = lid("배경")
    rect = {"hole": False, "cid": 0, "parent": -1,
            "segs": [[x0, y0, (x0 + x1) / 2, (y0 + y1) / 2, x1, y1] for (x0, y0), (x1, y1) in
                     zip([(-xoff, 0), (W + xoff, 0), (W + xoff, H), (-xoff, H)], [(W + xoff, 0), (W + xoff, H), (-xoff, H), (-xoff, 0)])]}
    stats["면"] += wr.fill([rect], argb(bgcol), k)
    bgm = (lab == names.index("배경")) & ~line
    if bgm.sum() > 1000 and not a.lines_only:
        lab3 = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
        smp = lab3[bgm][:: max(1, int(bgm.sum() // 40000))]
        cv2.setRNGSeed(0)
        _, lbl, cent = cv2.kmeans(smp, 3, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
        idx = np.linalg.norm(lab3[..., None, :] - cent[None, None], axis=3).argmin(2)
        big = np.argsort(-np.bincount(lbl.ravel(), minlength=3))
        for c in big[1:]:
            m = (idx == c) & (lab == names.index("배경"))
            m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            if m.sum() > 2000:
                sh = coarse(m, 3.0, 3.0, 800)
                stats["면"] += wr.fill(sh, argb(np.median(img[(idx == c) & bgm], 0)), k)
                stats["면 경계 조각"] += sum(len(s["segs"]) for s in sh)
    # 2) 부위 밑색: 부위 안을 색 묶음(최대 3, 가까운 묶음은 합침)으로 나눠 묶음마다 불투명 면 — 한 부위에 색이 둘 이상일 수 있다
    #    (1차 시험: '옷'에 베이지 코트와 검은 목폴라가 같이 있어 한 색으로 칠하자 검정이 회색 명암 덩어리가 됐고, 흰 머리 끝의 파랑·노란 눈동자도 빠졌다)
    lab3 = cv2.cvtColor(cv2.bilateralFilter(img, 7, 25, 7), cv2.COLOR_BGR2LAB).astype(np.float32)
    bases = []  # (부위, 묶음 마스크, 색, 밝기)
    for nm in ([] if a.lines_only else FILL_ORDER[1:]):
        if nm not in names:
            continue
        m = (lab == names.index(nm))
        if m.sum() < 200:
            continue
        sel = m & ~line
        if sel.sum() < 100:
            continue
        smp = lab3[sel][:: max(1, int(sel.sum() // 30000))]
        kk = 3 if sel.sum() > 3000 else 1
        cv2.setRNGSeed(0)
        _, lbl, cent = cv2.kmeans(smp, kk, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
        # 가까운 묶음 합치기(ΔE < 18)
        groups = list(range(kk))
        for i in range(kk):
            for j in range(i):
                if np.linalg.norm(cent[i] - cent[j]) < 18:
                    groups = [groups[j] if g == groups[i] else g for g in groups]
        idx = np.linalg.norm(lab3[..., None, :] - cent[None, None], axis=3).argmin(2)
        gidx = np.array(groups)[idx]
        gidx = cv2.medianBlur(gidx.astype(np.uint8), 7)
        k = lid(nm)
        parts_g = sorted(set(groups), key=lambda g: -int(((gidx == g) & m).sum()))
        for gi, g in enumerate(parts_g):
            gm = (gidx == g) & m
            if gi > 0 and gm.sum() < max(300, 0.03 * m.sum()):
                continue
            if gi == 0:
                gm = m  # 가장 넓은 묶음은 부위 전체를 깐다(나머지가 위에 얹힘)
            gm = cv2.morphologyEx(gm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
            mm = cv2.dilate(gm, np.ones((7, 7), np.uint8)) if gi == 0 else gm
            small = nm in ("눈동자", "입", "눈")
            sh = coarse(mm, 2.0 if small else 4.0, 1.5 if small else 4.0, 30 if small else 150)
            px = img[(gidx == g) & sel]
            if len(px) == 0:
                continue
            Lp = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB)[:, 0, 0].astype(np.float32)
            lt = (Lp >= np.percentile(Lp, 20)) & (Lp <= np.percentile(Lp, 80))  # 가운데 톤(밝은 쪽만 쓰자 베이지 코트가 흰색이 됐다)
            col = np.median(px[lt], 0)
            stats["면"] += wr.fill(sh, argb(col), k)
            stats["면 경계 조각"] += sum(len(s["segs"]) for s in sh)
            bases.append((nm, ((gidx == g) & sel), col, float(np.median(Lp[lt]))))
    # 3) 명암: 묶음 안 밑색보다 어두운 곳 → 뼈대를 따라 그 폭만큼 반투명 붓선(사람 그림처럼 옅게). 너무 넓은 그늘은 폭을 줄여 여러 줄로 보이게 하지 않고 건너뛴다
    k = lid("명암") if bases else None
    for nm, gm, col0, bL in bases:
        if bL < 40:
            continue  # 검은 옷 같은 아주 어두운 밑색은 명암 생략
        sm = (gm & (L < bL - 16)).astype(np.uint8)
        sm = cv2.morphologyEx(sm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        sm = (cv2.GaussianBlur(sm.astype(np.float32), (0, 0), 1.5) > 0.5).astype(np.uint8)
        if sm.sum() < 150:
            continue
        col = np.median(img[sm > 0], 0)
        # 넓은 그늘(폭 26px 넘음)은 붓선 하나로 덮으면 소시지 덩어리가 됐다(1차 시험 코트) → 그 부분만 성긴 반투명 면, 가는 그늘은 붓선
        wide = cv2.morphologyEx(sm, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (27, 27)))
        if wide.sum() > 400:
            wide = cv2.dilate(wide, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) & sm
            sh = coarse(wide, 3.0, 3.0, 300)
            stats["면"] += wr.fill(sh, argb(col, a.shade_alpha), k)
            stats["면 경계 조각"] += sum(len(s["segs"]) for s in sh)
        thin = (sm & (1 - wide)).astype(np.uint8)
        segs = joined_strokes(img, thin, tol=2.5, min_len=8, sigma=2.5) if thin.sum() > 100 else []
        groups = {}
        for s in segs:
            groups.setdefault(s[10], []).append(s)
        for g in groups.values():
            ts = [max(TS_MIN, s[6] * (1920 / CW) / (1.14 * 8)) for s in g]
            wr.chain(g, argb(col, a.shade_alpha), ts, k)
            stats["명암 붓선"] += len(g)
    # 4) 선화(맨 위): 진한 선 0.3, 옅은 결 0.1, 이어지는 곡선 끝점 연결
    k = lid("선화")
    px_lo, px_hi = TS_MIN * 1.14 * 8 * CW / 1920, TS_MAX * 1.14 * 8 * CW / 1920
    segs = joined_strokes(img, line.astype(np.uint8), tol=1.5, min_len=6, sigma=1.5, dark=lm, wrange=(px_lo, px_hi), taper=0.6,
                          bridge=a.clean, gap=a.gap)
    groups = {}
    for s in segs:
        groups.setdefault(s[10], []).append(s)
    runs = list(groups.values())
    if a.clean:
        runs, stats["겹친 곡선 뺌"] = drop_doubles(runs, H, W)
    for g in runs:
        ts = [min(TS_MAX, max(TS_MIN, s[6] * (1920 / CW) / (1.14 * 8))) for s in g]
        if a.black:
            cols = [argb(np.array([24, 24, 24]))] * len(g)
        else:
            cols = [argb(np.minimum(np.array(s[7:10]), 90)) for s in g]  # 선 색: 원본 선 색(너무 밝으면 어둡게)
        wr.chain(g, cols, ts, k)
        stats["선 곡선"] += len(g)
    defs = "".join(f'<LayerDef ID="{i}" Name="{n}" Visible="true" Locked="false"/>' for i, n in enumerate(layers))
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"{argb(bgcol)}\">\n<Frame BackgroundColor=\"{argb(bgcol) & 0xFFFFFFFF}\" ID=\"1\" Position=\"0\">"
           + defs + "\n" + "\n".join(wr.out) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    stats["AO"] = wr.oid - 1
    stats["MB"] = round(os.path.getsize(a.out) / 1e6, 2)
    print(stats, "레이어", layers)
    if a.check:
        tmp = a.check + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), a.out, tmp,
                        "--frames", "0", "--size", f"{CW}x{H}"], check=True, capture_output=True)
        rec = cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0]))
        rec = rec[:, int(xoff):int(xoff) + W]
        cv2.imwrite(a.check, np.hstack([img, cv2.resize(rec, (W, H))]))


if __name__ == "__main__":
    main()
