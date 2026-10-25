#!/usr/bin/env python3
"""형태 사전 2판 트랙을 새 장면에 배치해 SFA로 그린다 — 첫 이펙트 생성기 (2026-10-25, 계획 A단계).

트랙(tools/fx_tracks.py 출력) = 한 이펙트 덩어리가 장마다 변하는 기록(밑색 + 반투명 명암 겹, 2차 베지어 윤곽).
장면 파일(JSON)의 '배치' 하나마다 트랙을 골라 위치·크기·회전·속도·색을 바꿔 그린다. 같은 트랙도 바꾸면 다른 이펙트가 된다.
  {"frames": 전체 장 수, "bg": [B, G, R], "fps": 24,
   "items": [{"track": 6, "start": 0, "x": 0.7, "y": 0.2, "scale": 0.5, "rot": 0, "speed": 1.0,
              "tint": [B, G, R, 세기 0–1], "alpha": 1.0, "hold": 0, "flip": false}, …]}
- x, y = 화면 비(0–1) 중심. scale = 원래 크기의 배수(트랙의 장별 크기 변화는 그대로 따른다). rot = 도(시계 방향).
- dir = 트랙의 긴 축을 이 방향(도, -90 = 위)으로 돌린다(rot 대신, 광선·가시에 씀).
- speed = 재생 빠르기(0.5 = 두 배 느리게). hold = 마지막 장을 더 붙들 장 수.
- keep_core = 흰 심을 흰 채로 남기는 정도(0–1, 기본 0.75 — 0이면 심까지 목표 색).
- tint = 색상(hue)을 목표 색 쪽으로 돌리고 채도를 올린다(밝기는 유지 — 흰 심은 흰 채로, 둘레가 목표 색). 알파는 층 알파에 곱한다.
- 층 순서와 이음새는 effect_clip_sfa와 같다(밑색 모두 먼저 어두운 → 밝은, 명암은 뒤, 밑색만 같은 색 이음새 선).
사용: python tools/fx_track_play.py <트랙.txt> <장면.json> <출력.sfa> [--preview 미리보기.mp4]
"""
import argparse
import json
import math
import os
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_clip_sfa import H, Writer, argb, thick  # noqa: E402
from effect_layers import SEAM  # noqa: E402

W = 960


def load_tracks(path, want):
    """필요한 트랙만 읽는다(파일이 수백 MB). → {트랙: [장 {cx, cy, size, layers: [(bgr, alpha, [(hole, segs[k,6])])]}]}"""
    T, cur, frame, layer = {}, None, None, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            tag = line[:2]
            if tag == "T ":
                p = line.split()
                cur = int(p[1]) if int(p[1]) in want else None
                if cur is not None:
                    T[cur] = []
                continue
            if cur is None:
                continue
            p = line.split()
            if tag == "F ":
                frame = {"cx": float(p[2]), "cy": float(p[3]), "size": float(p[4]), "layers": []}
                T[cur].append(frame)
            elif tag == "Y ":
                layer = ([float(p[1]), float(p[2]), float(p[3])], float(p[4]), [])
                frame["layers"].append(layer)
            elif tag == "C ":
                v = np.array(p[2:], float)
                layer[2].append((p[1] == "1", v[: len(v) // 6 * 6].reshape(-1, 6)))
    return T


def tint_color(bgr, tint, keep_core=0.75):
    if not tint or tint[3] <= 0:
        return bgr
    px = np.uint8([[np.clip(bgr, 0, 255)]])
    h, s, v = cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0].astype(float)
    th, ts, _ = cv2.cvtColor(np.uint8([[np.clip(tint[:3], 0, 255)]]), cv2.COLOR_BGR2HSV)[0, 0].astype(float)
    k = tint[3]
    dh = ((th - h + 90) % 180) - 90  # 색상환에서 가까운 쪽으로
    h2 = (h + k * dh) % 180
    # 아주 밝고 거의 흰 심만 흰 채로 두고(빛의 심), 나머지는 목표 채도까지 올린다(분홍으로 바래지 않게)
    core = max(0.0, (v - 215) / 40) * (1.0 if s < 60 else 0.0)
    s2 = s + k * max(0.0, ts - s) * (1.0 - keep_core * core)
    out = cv2.cvtColor(np.uint8([[[h2, np.clip(s2, 0, 255), v]]]), cv2.COLOR_HSV2BGR)[0, 0]
    return out.astype(float).tolist()


def inside(pt, segs):
    poly = np.concatenate([segs[:, 0:2], segs[:, 4:6]]).astype(np.float32)
    return cv2.pointPolygonTest(poly.reshape(-1, 1, 2), (float(pt[0]), float(pt[1])), False) >= 0


def axis_deg(fr):
    """트랙 장의 긴 축 방향(도, 화면 좌표 — y 아래로). 가장 큰 층의 윤곽 점으로 주성분."""
    pts = np.concatenate([s.reshape(-1, 2) for _, _, cs in fr["layers"] for _, s in cs if len(s)])
    pts = pts - pts.mean(0)
    w, v = np.linalg.eigh(np.cov(pts.T))
    d = v[:, np.argmax(w)]
    return math.degrees(math.atan2(d[1], d[0]))


def place(fr, it):
    """정규화 윤곽 → 화면 픽셀(위치·크기·회전·뒤집기)."""
    sz = fr["size"] * it.get("scale", 1.0) * H
    cx, cy = it["x"] * W, it["y"] * H
    a = math.radians(it.get("rot", 0.0))
    ca, sa = math.cos(a), math.sin(a)
    fx = -1.0 if it.get("flip") else 1.0

    def tf(segs):
        P = segs.reshape(-1, 2) * sz
        P[:, 0] *= fx
        Q = np.stack([P[:, 0] * ca - P[:, 1] * sa + cx, P[:, 0] * sa + P[:, 1] * ca + cy], 1)
        return Q.reshape(-1, 6)
    return tf


def item_layers(fr, it):
    tf = place(fr, it)
    out = []
    for bgr, alpha, conts in fr["layers"]:
        segs = [(hole, tf(s)) for hole, s in conts if len(s)]
        outers = [s for h, s in segs if not h]
        shapes = [{"hole": False, "segs": s.tolist(), "cid": i, "parent": -1} for i, s in enumerate(outers)]
        for h, s in segs:  # 구멍은 첫 점을 품는 바깥 윤곽에 붙인다(사전에는 부모 번호가 없다)
            if h:
                par = next((i for i, o in enumerate(outers) if inside(s[0, :2], o)), None)
                if par is not None:
                    shapes.append({"hole": True, "segs": s.tolist(), "cid": -1, "parent": par})
        out.append({"base": alpha >= 0.999, "color": tint_color(bgr, it.get("tint"), it.get("keep_core", 0.75)),
                    "alpha": alpha * it.get("alpha", 1.0), "shapes": shapes})
    return out


def frame_xml(pos, items_layers, wr, bg):
    out = [f'<Frame BackgroundColor="{bg & 0xFFFFFFFF}" ID="{pos + 1}" Position="{pos}">',
           '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false" />']
    for layers in items_layers:  # 배치마다 따로: 앞 배치 위에 뒤 배치가 덮인다
        bases = sorted((L for L in layers if L["base"]), key=lambda L: sum(L["color"][:3]))
        for L in bases + [L for L in layers if not L["base"]]:
            c = argb(L["color"], min(1.0, L["alpha"]))
            if L["base"] and L["alpha"] >= 0.999:
                wr.fill(out, L["shapes"], W, c, c, thick(SEAM, W))
            else:
                wr.fill(out, L["shapes"], W, c, 0, 0.02)
    out.append("</Frame>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks")
    ap.add_argument("scene")
    ap.add_argument("out")
    ap.add_argument("--preview")
    a = ap.parse_args()
    sc = json.load(open(a.scene, encoding="utf-8"))
    items = sc["items"]
    T = load_tracks(a.tracks, {int(it["track"]) for it in items})
    missing = {int(it["track"]) for it in items} - set(T)
    if missing:
        sys.exit(f"사전에 없는 트랙: {sorted(missing)}")
    bg = argb(sc.get("bg", [0, 0, 0]))
    wr, body = Writer(), []
    for pos in range(sc["frames"]):
        active = []
        for it in items:
            tr = T[int(it["track"])]
            k = pos - it.get("start", 0)
            if k < 0:
                continue
            src = int(k * it.get("speed", 1.0))
            if src >= len(tr):
                if src < len(tr) + it.get("hold", 0):
                    src = len(tr) - 1
                else:
                    continue
            if "dir" in it and "rot" not in it:  # 긴 축을 원하는 방향으로(예: -90 = 위로 솟음). 트랙 첫 장 기준으로 한 번 정한다
                ax = axis_deg(tr[0])
                r = it["dir"] - ax
                it["rot"] = min((r, r + 180, r - 180), key=abs) if it.get("either_end", True) else r
            active.append(item_layers(tr[src], it))
        body.append(frame_xml(pos, active, wr, bg))
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" "
           f"RatioX=\"16\" RatioY=\"9\" FrameCount=\"{sc['frames']}\" BackgroundColor=\"{bg}\">\n" + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + ".xml", xml)
    print("장", sc["frames"], "배치", len(items), "AO", wr.oid - 1, "크기MB", round(os.path.getsize(a.out) / 1e6, 2))
    if a.preview:
        from sfa_render import iter_frames, render_frame
        vw = cv2.VideoWriter(a.preview, cv2.VideoWriter_fourcc(*"mp4v"), sc.get("fps", 24), (W, H))
        for seq, el in iter_frames(a.out):
            vw.write(np.asarray(render_frame(seq, el, W, H))[..., :3][..., ::-1].copy())
        vw.release()


if __name__ == "__main__":
    main()
