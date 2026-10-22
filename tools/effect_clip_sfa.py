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
            out.append(f'<AP ID="{p + i}" Flags="5" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}" />')
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


def frame_xml(doc, pos, wr, W, bg):
    out = [f'<Frame BackgroundColor="{bg & 0xFFFFFFFF}" ID="{pos + 1}" Position="{pos}">',
           '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />']
    for L in doc["layers"]:
        if L["kind"] == "base":
            c = argb(L["color"])
            wr.fill(out, L["shapes"], W, c, c, thick(SEAM, W))
        else:
            wr.fill(out, L["shapes"], W, argb(L["color"], L["alpha"]), 0, 0.02)
    for ln in doc["lines"]:
        for seg in ln["segs"]:
            wr.curve_ao(out, seg, W, argb(seg[7:10] if len(seg) >= 10 else ln["color"]), thick(seg[6], W))
    out.append('</Frame>')
    return "\n".join(out)


def main():
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
    ap.add_argument("--bg", default="0,0,0")
    ap.add_argument("--grow", type=int, default=2, help="마스크 넓히기(px): 이펙트 가장자리 선까지 담는다")
    a = ap.parse_args()
    bg = [int(v) for v in a.bg.split(",")]
    masks = None
    if a.mask:
        import cv2
        z = np.load(a.mask)
        shp = tuple(int(v) for v in z["shape"])
        M = np.unpackbits(z["mask"], axis=-1)[..., :shp[2]].astype(np.uint8)
        k = np.ones((2 * a.grow + 1, 2 * a.grow + 1), np.uint8)
        masks = {int(f): cv2.dilate(M[i], k) for i, f in enumerate(z["frames"])}
    frames = list(range(a.start, a.end + 1, a.step))
    wr = Writer()
    body, stats, imgs = [], [], []
    W = None
    for pos, f in enumerate(frames):
        img = read_frame(a.video, f, H)
        W = img.shape[1]
        valid = None
        if masks is not None:
            valid = masks.get(f, np.zeros(img.shape[:2], np.uint8))
            if valid.shape != img.shape[:2]:
                import cv2
                valid = cv2.resize(valid, (W, H), interpolation=cv2.INTER_NEAREST)
        # 분해는 원본 그림으로 한다(바깥을 바탕색으로 칠하면 이펙트 가장자리가 선으로 잡혔다). 비교 그림만 바깥을 바탕색으로
        doc, _ = decompose(img, a.k, a.tol, valid=valid)
        if valid is not None:
            img = np.where(valid[..., None] > 0, img, np.array(bg, np.uint8))
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
