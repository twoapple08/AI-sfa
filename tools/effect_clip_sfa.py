#!/usr/bin/env python3
"""이펙트 재현 시험: 영상 구간을 프레임마다 '그림 과정' 층(tools/effect_layers.py)으로 분해해 SFA 한 편으로 만든다.

사용: python tools/effect_clip_sfa.py <영상> <시작프레임> <끝프레임(포함)> <출력.sfa> [--k 8] [--tol 1.0] [--step 1]
      [--check 비교.jpg]  (SFA를 서버 렌더러 tools/sfa_render.py로 다시 그려 원본과 Lab ΔE를 잰다)
      [--mask 분리.npz] [--bg 0,0,0]  (tools/kaggle_fx_worker.py 이펙트 마스크 안만 분해 → 이펙트만 있는 SFA, 바탕색 BGR)
- 층 → SFA(AGENTS.md 이펙트 그리기 원칙·그림 과정 그대로 그리기):
  밑색: FR(불투명) + 경계 곡선(TypeId 3, 밑색과 같은 색, 굵기 = 이음새 SEAM px)  ← 이웃 영역 사이 틈 막기
  명암: FR(반투명 알파) + 경계 곡선(투명, 아주 가늘게) — 바깥 넓고 옅게 → 안쪽 좁고 진하게
  선: 곡선 획(TypeId 3, 굵기·색 = 분해에서 잰 획별 굵기·색). 어두운 선 다음 밝은 선.
- 채우기 한 묶음 = 바깥 윤곽 하나(Contour 0) + 그 안의 구멍들(Contour 1..). 뷰어 규칙(docs/SFA-VIEWER) 그대로.
- 좌표: 분해 해상도(높이 540) 픽셀 → SFA 0~100. 선 굵기: 화면 폭 1920 기준 w = 1.14·8·ThicknessScale.
- AO·점 ID는 시퀀스 전체에서 고유(프레임마다 다른 그림이라 트위닝 대응을 만들지 않는다). 재생은 (24,24) 기준.
원본 영상에서 딴 그림이므로 결과 SFA·비교 그림은 저장소에 넣지 않는다(Drive·서버 임시 폴더만).
"""
import argparse
import os
import sys
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_layers import SEAM, decompose, delta_e  # noqa: E402
from effect_vectorize import read_frame  # noqa: E402

H = 540


def argb(bgr, a=1.0):
    b, g, r = (int(round(min(255, max(0, v)))) for v in bgr[:3])
    v = (int(round(a * 255)) << 24) | (r << 16) | (g << 8) | b
    return v - (1 << 32) if v >= 1 << 31 else v


def thick(px_at_h, W):
    """분해 해상도에서 px 굵기 → ThicknessScale(화면 폭 1920 기준 선 폭 = 1.14·8·TS)."""
    return max(0.02, px_at_h * (1920 / W) / (1.14 * 8))


class Writer:
    def __init__(self):
        self.oid = 1
        self.pid = 1
        self.xoff = 0  # --fit pad: 좁은 그림을 16:9 화면 가운데에 놓을 때 x 이동(px)

    def curve_ao(self, out, seg, W, color, ts, glow=None):
        """glow=(GlowRadius, GlowThickness, GlowColor ARGB, GlowAlpha 0–255) — 스틱파이터 글로우(가우스 번짐)."""
        x0, y0, cx, cy, x1, y1 = seg[:6]
        oid, p = self.oid, self.pid
        self.oid += 1
        self.pid += 3
        gr, gt, gc, ga = glow if glow else (0.0, 0.0, 4294967295, 0.0)
        out.append(f'<AO ID="{oid}" TypeId="3" Color="{color}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" '
                   f'ObjectScale="1.0" GlowRadius="{gr:.1f}" GlowThickness="{gt:.1f}" GlowColor="{gc}" GlowAlpha="{ga:.1f}">')
        for i, (x, y) in enumerate(((x0, y0), (cx, cy), (x1, y1))):
            out.append(f'<AP ID="{p + i}" Flags="5" Index="{i}" X="{(x + self.xoff) / W * 100:.3f}" Y="{y / H * 100:.3f}" />')
        out.append('</AO>')
        return oid, p

    def fill(self, out, shapes, W, fill_col, edge_col, ts, glow=None):
        """한 층의 윤곽들 → 바깥 윤곽마다 FR 하나(구멍 포함)."""
        outers = [s for s in shapes if not s["hole"] and s["segs"]]
        holes = {}
        for s in shapes:
            if s["hole"] and s["segs"]:
                holes.setdefault(s.get("parent", -2), []).append(s)
        frs = []
        for o in outers:
            contours = [o] + holes.get(o.get("cid", -1), [])
            fs = []
            for ci, c in enumerate(contours):
                for seg in c["segs"]:
                    oid, p = self.curve_ao(out, seg, W, edge_col, ts, glow)
                    fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}" />')
            frs.append(f'<FR Color="{fill_col}">' + "".join(fs) + '</FR>')
        out.extend(frs)


SHADE_SEAM = 0.0  # 명암 층 테두리 선 굵기(SEAM 배수, 0 = 투명 선). 2026-10-24 '외곽선 현상' 시험에서 0.6을 써 보니
# 반투명 면 위에 같은 알파 선이 겹쳐 밝은 선이 생겼다(020·017) → 0으로 두고 effect_layers에서 명암 면을 1px 넓힌다.


def frame_xml(doc, pos, wr, W, bg):
    out = [f'<Frame BackgroundColor="{bg & 0xFFFFFFFF}" ID="{pos + 1}" Position="{pos}">',
           '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />']
    # 밑색을 모두 먼저(어두운 것 → 밝은 것), 명암은 그 뒤에. 밑색 이음새 선(SEAM)은 이웃 영역으로 반 굵기만큼 넘어가는데,
    # 덩어리마다 '밑색 → 명암' 순서로 그리면 뒤에 그린 어두운 밑색의 이음새가 앞 덩어리의 밝은 명암 위에 검은 선으로 남았다(2026-10-24 016·017·020).
    bases = sorted((L for L in doc["layers"] if L["kind"] == "base"), key=lambda L: sum(L["color"][:3]))
    for L in bases + [L for L in doc["layers"] if L["kind"] != "base"]:
        if L["kind"] == "base":
            c = argb(L["color"])
            wr.fill(out, L["shapes"], W, c, c, thick(SEAM, W))
        else:
            c = argb(L["color"], L["alpha"])
            wr.fill(out, L["shapes"], W, c, c if SHADE_SEAM > 0 else 0, thick(SEAM * SHADE_SEAM, W) if SHADE_SEAM > 0 else 0.02)
    for ln in doc["lines"]:
        for seg in ln["segs"]:
            wr.curve_ao(out, seg, W, argb(seg[7:10] if len(seg) >= 10 else ln["color"]), thick(seg[6], W))
    out.append('</Frame>')
    return "\n".join(out)


def decontaminate(img, valid, de, band):
    """마스크 가장자리 띠(band px)에서 주변 배경색과 Lab ΔE < de인 픽셀을 마스크에서 뺀다.
    주변 배경색 = 마스크 바깥 픽셀만으로 낸 큰 흐림(정규화 합성곱) — 장면마다 다른 바탕(흰·보라 우주 등)을 따라간다."""
    import cv2
    m = (valid > 0).astype(np.float32)
    out = 1.0 - m
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= 100 / 255
    lab[..., 1:] -= 128
    ks = (31, 31)
    num = cv2.blur(lab * out[..., None], ks)
    den = cv2.blur(out, ks)[..., None]
    bgl = num / np.maximum(den, 1e-3)
    inner = cv2.erode(valid, np.ones((2 * band + 1, 2 * band + 1), np.uint8))
    edge = (valid > 0) & (inner == 0) & (den[..., 0] > 0.02)
    close = np.linalg.norm(lab - bgl, axis=-1) < de
    v = valid.copy()
    v[edge & close] = 0
    return v


def main():
    global H
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("out")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tol", type=float, default=1.0)
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--check")
    ap.add_argument("--mask")
    ap.add_argument("--bg", default="auto", help="프레임 바탕색 B,G,R. auto = 마스크가 있으면 검정, 없으면 그림 가장자리 색(2026-10-25 사용자: 흰 그림에 검은 틀이 보임 — 바탕 검정이 화면 가장자리에 드러남)")
    ap.add_argument("--grow", type=int, default=0, help="마스크 넓히기(px, 음수면 좁히기). 2026-10-24 기본 2→0: 넓히면 배경색 띠가 외곽선처럼 남았다")
    ap.add_argument("--decontam", type=float, default=25.0,
                    help="배경 오염 빼기(Lab ΔE, 0=끔, 2026-10-24 기본 25 — 외곽선 현상 019 시험에서 95% ΔE 10→2.6): 마스크 가장자리 띠에서 주변 배경색(마스크 바깥 근처 평균)과 이보다 가까운 픽셀을 뺀다 "
                         "(2026-10-23: 흰·보라 배경이 테두리로 들어옴)")
    ap.add_argument("--band", type=int, default=6, help="--decontam이 보는 가장자리 띠 두께(px)")
    ap.add_argument("--fit", default="crop", choices=["crop", "pad", "none"],
                    help="16:9가 아닌 원본(4:3 등): crop = 위아래를 잘라 16:9로 채움(2026-10-23 사용자: 목표 16:9 고정). "
                         "SFA 화면은 16:9라 그대로 두면 가로로 늘어난다(2026-10-24 008·015·035). "
                         "pad = 높이를 화면에 맞추고 가운데에 둔다(세로 그림, 2026-10-25 사용자). 분해는 그림만 한다 — 흰 여백까지 넣고 분해하니 옅은 살색이 흰색에 묶였다")
    ap.add_argument("--height", type=int, default=540, help="분해 해상도 높이(기본 540). 세로 인물 그림은 1080 이상(540에선 선이 덩어리로 뭉개짐)")
    ap.add_argument("--shade-min", type=int, help="명암 조각 최소 넓이(px). 기본 = 밑색과 같은 20. 2026-10-25 최적화: 200이면 명암 곡선 절반")
    ap.add_argument("--levels", help="명암 단계(쉼표). 기본 14단계. 셀 채색 그림은 0.12,0.25,0.4,0.55,0.7,0.85로 충분")
    ap.add_argument("--shade-tol", type=float, help="명암 윤곽만 곡선 오차(px). 기본 = --tol")
    ap.add_argument("--line-dark", type=int, help="어두운 선으로 볼 최대 밝기(기본 140). 흰 머리·옅은 회색 선이 점선으로 끊기는 인물 그림은 200")
    ap.add_argument("--line-fill", action="store_true", help="어두운 선을 획 대신 선 모양 채우기 면으로(인물 선화: 획은 점선·덩어리가 됨)")
    ap.add_argument("--compact", action="store_true", help="용량 최적화 묶음 = 명암만 곡선 오차 2px + --shade-min 200 + 명암 6단계. 밑색·선은 --tol 그대로(2026-10-25: 전부 2px로 하니 인물 윤곽이 자글자글해짐)")
    a = ap.parse_args()
    if a.compact:
        a.shade_tol = a.shade_tol or 2.0
        a.shade_min = a.shade_min or 200
        a.levels = a.levels or "0.12,0.25,0.4,0.55,0.7,0.85"
    levels = [float(v) for v in a.levels.split(",")] if a.levels else None
    H = a.height
    bg = None if a.bg == "auto" else [int(v) for v in a.bg.split(",")]
    masks = None
    if a.mask:
        import cv2
        z = np.load(a.mask)
        shp = tuple(int(v) for v in z["shape"])
        M = np.unpackbits(z["mask"], axis=-1)[..., :shp[2]].astype(np.uint8)
        k = np.ones((2 * abs(a.grow) + 1, 2 * abs(a.grow) + 1), np.uint8)
        op = cv2.dilate if a.grow >= 0 else cv2.erode
        masks = {int(f): op(M[i], k) for i, f in enumerate(z["frames"])}
    frames = list(range(a.start, a.end + 1, a.step))
    wr = Writer()
    body, stats, imgs = [], [], []
    W = None
    for pos, f in enumerate(frames):
        img = read_frame(a.video, f, H)
        wr.xoff = 0
        W = img.shape[1]
        valid = None
        if masks is not None:
            valid = masks.get(f, np.zeros(img.shape[:2], np.uint8))
            if valid.shape != img.shape[:2]:
                import cv2
                valid = cv2.resize(valid, (W, H), interpolation=cv2.INTER_NEAREST)
        tw = round(H * 16 / 9)
        if a.fit == "crop" and abs(W - tw) > 2:  # 가운데 16:9를 잘라 높이 H로 키운다(그림과 마스크를 같이)
            import cv2
            th = round(W * 9 / 16)
            y0 = (H - th) // 2
            img = cv2.resize(img[y0:y0 + th], (tw, H), interpolation=cv2.INTER_CUBIC)
            if valid is not None:
                valid = cv2.resize(valid[y0:y0 + th], (tw, H), interpolation=cv2.INTER_NEAREST)
            W = tw
        elif a.fit == "pad" and W < tw - 2:
            wr.xoff = (tw - W) // 2
        if valid is not None and a.decontam > 0:
            valid = decontaminate(img, valid, a.decontam, a.band)
        # 분해는 원본 그림으로 한다(바깥을 바탕색으로 칠하면 이펙트 가장자리가 선으로 잡혔다). 비교 그림만 바깥을 바탕색으로
        doc, _ = decompose(img, a.k, a.tol, valid=valid, shade_min=a.shade_min, levels=levels, shade_tol=a.shade_tol, line_dark=a.line_dark, line_fill=a.line_fill)
        if valid is not None:
            img = np.where(valid[..., None] > 0, img, np.array(bg or [0, 0, 0], np.uint8))
        if bg is None:
            bg = [0, 0, 0] if a.mask else [int(v) for v in np.median(np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]]), axis=0)]
        if wr.xoff:
            pad = np.empty((H, tw, 3), np.uint8)
            pad[:] = np.array(bg, np.uint8)
            pad[:, wr.xoff:wr.xoff + W] = img
            img, W = pad, tw
        body.append(frame_xml(doc, pos, wr, W, argb(bg)))
        stats.append(doc["stats"])
        imgs.append(img)
        print(f, doc["stats"], flush=True)
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" "
           f"RatioX=\"16\" RatioY=\"9\" FrameCount=\"{len(frames)}\" BackgroundColor=\"{argb(bg)}\">\n"
           + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".xml", xml)
    print("프레임", len(frames), "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 1))
    if a.check:
        import cv2
        import subprocess
        tmp = a.check + "_r"
        idx = sorted({0, len(frames) // 2, len(frames) - 1})
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sfa_render.py"), a.out, tmp,
                        "--frames", ",".join(map(str, idx)), "--size", f"{W}x{H}"], check=True, capture_output=True)
        rows = []
        for i in idx:
            r = cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[idx.index(i)]))
            r = cv2.resize(r, (W, H))
            de = delta_e(imgs[i], r)
            print(f"SFA 다시 그림 프레임 {frames[i]}: ΔE 평균 {de.mean():.2f} 95% {np.percentile(de, 95):.2f}")
            rows.append(np.hstack([imgs[i], r]))
        cv2.imwrite(a.check, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])


if __name__ == "__main__":
    main()
