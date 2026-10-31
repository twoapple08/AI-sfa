#!/usr/bin/env python3
"""그림 → VTracer(층 쌓기 'stacked' 모드) SVG → SFA (2026-10-26 실험 1, GPT 조사 제안의 외부 기준선).

VTracer는 색 영역을 아래에서 위로 겹쳐 쌓는 SVG를 낸다(stacked: 위 층이 아래를 덮어 구멍을 덜 만든다).
SVG 경로(M/L/C/Q/Z, translate)를 읽어 3차 곡선은 2차 두 개로 바꾸고(potrace_lines.cubic_to_quads), 경로마다 FR 하나(하위 경로 = Contour)로 쓴다.
사용: python tools/vtracer_sfa.py <그림> <출력.sfa> [--check 비교.jpg] [--speckle 4] [--color-precision 6] [--layer-diff 16]
"""
import argparse
import os
import re
import sys
import zipfile

import cv2
import numpy as np
import vtracer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import effect_clip_sfa as ecs  # noqa: E402
from effect_clip_sfa import Writer, argb  # noqa: E402
from potrace_lines import cubic_to_quads  # noqa: E402

TOK = re.compile(r"[MLCQZmlcqz]|-?\d*\.?\d+(?:e-?\d+)?")


def parse_path(d, dx, dy):
    """d 문자열 → 하위 경로 목록(각각 2차 곡선 [x0,y0,cx,cy,x1,y1] 목록). VTracer는 절대좌표 M/L/C/Z만 쓴다(Q도 처리)."""
    toks = TOK.findall(d)
    subs, cur, pos, start, i, cmd = [], [], None, None, 0, None
    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v
    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]; i += 1
            if cmd in "Zz":
                if pos is not None and start is not None and (abs(pos[0] - start[0]) > 1e-6 or abs(pos[1] - start[1]) > 1e-6):
                    cur.append([*pos, (pos[0] + start[0]) / 2, (pos[1] + start[1]) / 2, *start])
                if cur:
                    subs.append(cur)
                cur, pos = [], start
                continue
        if cmd == "M":
            if cur:
                subs.append(cur); cur = []
            pos = (num() + dx, num() + dy); start = pos; cmd = "L"
        elif cmd == "L":
            p = (num() + dx, num() + dy)
            cur.append([*pos, (pos[0] + p[0]) / 2, (pos[1] + p[1]) / 2, *p]); pos = p
        elif cmd == "C":
            c1 = (num() + dx, num() + dy); c2 = (num() + dx, num() + dy); p = (num() + dx, num() + dy)
            cur += cubic_to_quads(pos, c1, c2, p); pos = p
        elif cmd == "Q":
            c = (num() + dx, num() + dy); p = (num() + dx, num() + dy)
            cur.append([*pos, *c, *p]); pos = p
        else:
            i += 1
    if cur:
        subs.append(cur)
    return subs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--check")
    ap.add_argument("--speckle", type=int, default=4)
    ap.add_argument("--color-precision", type=int, default=6)
    ap.add_argument("--layer-diff", type=int, default=16)
    ap.add_argument("--corner", type=int, default=60)
    ap.add_argument("--length", type=float, default=4.0)
    a = ap.parse_args()
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    ecs.H = H
    svg = a.out + ".svg"
    vtracer.convert_image_to_svg_py(a.image, svg, colormode="color", hierarchical="stacked", mode="spline",
                                    filter_speckle=a.speckle, color_precision=a.color_precision, layer_difference=a.layer_diff,
                                    corner_threshold=a.corner, length_threshold=a.length, max_iterations=10, splice_threshold=45,
                                    path_precision=3)
    text = open(svg).read()
    wr, body = Writer(), []
    for m in re.finditer(r'<path d="([^"]+)" fill="#([0-9A-Fa-f]{6})"(?: transform="translate\(([-\d.]+),([-\d.]+)\)")?', text):
        d, col = m.group(1), m.group(2)
        dx, dy = float(m.group(3) or 0), float(m.group(4) or 0)
        rgb = [int(col[k:k + 2], 16) for k in (0, 2, 4)]
        fs = []
        for ci, sub in enumerate(parse_path(d, dx, dy)):
            for seg in sub:
                oid, p = wr.curve_ao(body, seg, W, 0, ecs.TS_MIN)
                fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="{ci}" />')
        if fs:
            body.append(f'<FR Color="{argb(rgb[::-1])}">' + "".join(fs) + "</FR>")
    name = os.path.splitext(os.path.basename(a.out))[0]
    bg = argb(img[0, 0])
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"{bg}\">\n<Frame BackgroundColor=\"{bg & 0xFFFFFFFF}\" ID=\"1\" Position=\"0\">"
           '<LayerDef ID="0" Name="VTracer" Visible="true" Locked="false" />\n' + "\n".join(body) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    os.remove(svg)
    print("AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 2))
    if a.check:
        import subprocess
        tmp = a.check + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sfa_render.py"), a.out, tmp, "--frames", "0",
                        "--size", f"{W}x{H}"], check=True, capture_output=True)
        rec = cv2.resize(cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0])), (W, H))
        cv2.imwrite(a.check, np.hstack([img, rec]))


if __name__ == "__main__":
    main()
