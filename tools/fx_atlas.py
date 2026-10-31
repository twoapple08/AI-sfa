#!/usr/bin/env python3
"""이펙트 벡터 자료집 항목 추출 1차 — 장면 영상 한 컷 → fx_atlas JSON (2026-10-27).

형식: docs/FX-ATLAS-FORMAT-2026-10-27.md (GPT 계획 1번: 레이어별 도형 + 덩어리 생성·분열·합체·소멸 + 프레임별 변화 + 관측 신뢰도).
도형 자체(윤곽 좌표)는 같은 설정의 palette_sfa SFA 파일을 가리키고(--sfa), 여기에는 시간·구조·형태 통계만 쓴다.
다른 작가 그림에서 뗀 것이므로 결과 JSON·SFA는 저장소에 넣지 않는다(Drive·scratch만).

1차 범위(규칙 기반, 판정 아님): 폭발 색 층(palette_sfa.classify)만 덩어리로 본다. 연기·번개·파편 종류 구분은 아직 없음.
사용: python tools/fx_atlas.py <영상> <out.json> --clip 926 31 [--k 16] [--sfa A_v3.sfa] [--kind explosion] [--source 239068]
"""
import argparse
import json
import os
import re
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palette_sfa as P  # noqa: E402

W, H = P.W, P.H
Q = 0.5  # 계산 해상도(1920×1080의 절반). 좌표는 1920×1080 기준으로 적는다.


def blob_features(m, scale):
    """덩어리 하나(0/1 마스크, Q 해상도) → 형태 특징."""
    a = float(m.sum())
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    outer = max((c for i, c in enumerate(cs) if hier[0][i][3] < 0), key=cv2.contourArea)
    holes = sum(1 for i in range(len(cs)) if hier[0][i][3] >= 0 and cv2.contourArea(cs[i]) > 20)
    mo = cv2.moments(m, True)
    cx, cy = mo["m10"] / mo["m00"], mo["m01"] / mo["m00"]
    mu20, mu02, mu11 = mo["mu20"] / mo["m00"], mo["mu02"] / mo["m00"], mo["mu11"] / mo["m00"]
    ang = 0.5 * np.degrees(np.arctan2(2 * mu11, mu20 - mu02))
    lam = np.sqrt(((mu20 - mu02) / 2) ** 2 + mu11 ** 2)
    l1, l2 = (mu20 + mu02) / 2 + lam, (mu20 + mu02) / 2 - lam
    per = cv2.arcLength(outer, True)
    hull = cv2.convexHull(outer, returnPoints=False)
    spikes, tips = 0, []
    if hull is not None and len(hull) > 3 and len(outer) > 3:
        try:
            d = cv2.convexityDefects(outer, hull)
        except cv2.error:
            d = None
        if d is not None:
            deep = d[:, 0, 3] / 256.0 > 0.04 * np.sqrt(a)  # 깊은 오목 = 돌출부 사이
            spikes = int(deep.sum())
    # 끝 뾰족함: 다각형 근사의 꼭짓점 내각 중 60° 미만 개수
    ap = cv2.approxPolyDP(outer, 0.01 * per, True)[:, 0, :].astype(float)
    sharp = 0
    for i in range(len(ap)):
        p0, p1, p2 = ap[i - 1], ap[i], ap[(i + 1) % len(ap)]
        v1, v2 = p0 - p1, p2 - p1
        cosv = (v1 @ v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
        if np.degrees(np.arccos(np.clip(cosv, -1, 1))) < 60:
            sharp += 1
    x, y, w, h = cv2.boundingRect(outer)
    return {
        "center": [round(cx / Q, 1), round(cy / Q, 1)],
        "area": round(a / (Q * Q) / scale ** 2, 5),
        "bbox": [round(x / Q), round(y / Q), round(w / Q), round(h / Q)],
        "angle_deg": round(float(ang), 1),
        "elongation": round(float(np.sqrt(max(l1, 1e-9) / max(l2, 1e-9))), 2),
        "roughness": round(per ** 2 / (4 * np.pi * a), 2),
        "holes": int(holes),
        "spikes": spikes,
        "sharp_tips": sharp,
        "touches_edge": bool(x <= 1 or y <= 1 or x + w >= m.shape[1] - 1 or y + h >= m.shape[0] - 1),
    }


def sfa_glow(path):
    """palette_sfa SFA에서 층(LayerId)별 글로우 값(정수) 하나씩."""
    with zipfile.ZipFile(path) as z:
        xml = z.read(z.namelist()[0]).decode("utf-8")
    out = {}
    for m in re.finditer(r'<AO [^>]*LayerId="(\d+)"[^>]*GlowRadius="(\d+)"[^>]*GlowThickness="(\d+)"[^>]*GlowColor="(-?\d+)"[^>]*GlowAlpha="(\d+)"', xml):
        lid = int(m[1])
        if lid not in out and int(m[2]) > 0:
            out[lid] = {"radius": int(m[2]), "thickness": int(m[3]), "color_argb": int(m[4]), "alpha": int(m[5])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--clip", type=int, nargs=2, required=True)
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--min-area", type=int, default=400, help="덩어리 최소 면적(1920 기준 px²)")
    ap.add_argument("--hold", type=float, default=3.0)
    ap.add_argument("--sfa", help="같은 컷의 palette_sfa 결과(도형·글로우 출처)")
    ap.add_argument("--kind", default="explosion")
    ap.add_argument("--source", default="")
    a = ap.parse_args()
    c = cv2.VideoCapture(a.video)
    fps = c.get(cv2.CAP_PROP_FPS)
    c.set(1, a.clip[0])
    src = [c.read()[1] for _ in range(a.clip[1])]
    frames = [cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC) for f in src]
    cent, bgr = P.palette(frames, a.k)
    fx = P.classify(cent)
    mix = P.find_mix([P.label(f, cent) for f in frames[::5]], fx, a.k)
    area_all = sum(np.bincount(P.label(f, cent).ravel(), minlength=a.k) for f in frames[::4])
    order = list(np.argsort(-area_all))
    sw, sh = int(W * Q), int(H * Q)
    masks, layer_frac, holds, prev_small = [], [], [], None
    for f, s in zip(frames, src):
        idx = P.relabel_band(P.label(f, cent), cent, fx, mix)
        small = cv2.resize(s, (214, 120)).astype(np.float32)
        holds.append(bool(prev_small is not None and float(np.abs(small - prev_small).mean()) < a.hold))
        prev_small = small
        E = cv2.resize(np.isin(idx, np.where(fx)[0]).astype(np.uint8), (sw, sh), interpolation=cv2.INTER_NEAREST)
        masks.append(E)
        cnt = np.bincount(idx[np.isin(idx, np.where(fx)[0])].ravel(), minlength=a.k)
        layer_frac.append({int(order.index(ci)): round(float(cnt[ci] / max(cnt.sum(), 1)), 3) for ci in np.where(fx)[0] if cnt[ci]})
    # 정규화: 원점 = 첫 관측 장의 폭발 중심, 크기 = 최대 면적의 제곱근
    tot = np.array([m.sum() / (Q * Q) for m in masks])
    first = int(np.argmax(tot > a.min_area)) if (tot > a.min_area).any() else 0
    ys, xs = np.nonzero(masks[first])
    origin = [round(xs.mean() / Q, 1), round(ys.mean() / Q, 1)] if len(xs) else [W / 2, H / 2]
    scale = float(np.sqrt(tot.max())) if tot.max() > 0 else 1.0
    # 덩어리와 추적(겹침 비율 ≥ 0.2면 부모·자식)
    blobs, frames_out, prev = [], [], []
    for fi, m in enumerate(masks):
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        cur = []
        for j in range(1, n):
            if st[j, cv2.CC_STAT_AREA] / (Q * Q) < a.min_area:
                continue
            bm = (lab == j).astype(np.uint8)
            b = {"id": len(blobs), "frame": fi, "parents": [], "children": []}
            b.update(blob_features(bm, scale))
            for p in prev:
                ov = float((bm & p["_m"]).sum())
                if ov / min(bm.sum(), p["_m"].sum()) >= 0.2:
                    b["parents"].append(p["id"])
                    blobs[p["id"]]["children"].append(b["id"])
            b["_m"] = bm
            blobs.append(b)
            cur.append(b)
        g = {"frame": fi, "hold": holds[fi], "fx_area": round(float(tot[fi]) / scale ** 2, 5), "blobs": [b["id"] for b in cur],
             "layer_fraction": layer_frac[fi]}
        if cur:
            ys, xs = np.nonzero(m)
            g["center"] = [round(xs.mean() / Q, 1), round(ys.mean() / Q, 1)]
        frames_out.append(g)
        prev = cur
    for b in blobs:
        b.pop("_m")
        b["event"] = ("birth" if not b["parents"] else "merge" if len(b["parents"]) > 1 else "continue")
        if len(b["children"]) > 1:
            b["event"] += "+split"
        if not b["children"] and b["frame"] < len(masks) - 1:
            b["event"] += "+death"
    # 단계(규칙): 발생 = 첫 관측, 급팽창 = 면적 증가율 최대 장, 피크 = 최대 면적, 소멸 시작 = 피크 뒤 면적이 피크의 70% 아래로 처음 내려간 장
    gr = np.diff(tot, prepend=tot[0])
    peak = int(np.argmax(tot))
    decay = next((i for i in range(peak, len(tot)) if tot[i] < 0.7 * tot[peak]), None)
    phases = {"onset": first, "rapid_expansion": int(np.argmax(gr)), "peak": peak, "decay_start": decay}
    for i in range(1, len(frames_out)):
        a0, a1 = frames_out[i - 1].get("center"), frames_out[i].get("center")
        if a0 and a1:
            frames_out[i]["velocity"] = [round((a1[0] - a0[0]) / scale, 4), round((a1[1] - a0[1]) / scale, 4)]
    # 화면 이동(카메라): 폭발 밖 배경의 위상 상관(밝기 변화가 크면 신뢰도 낮음)
    cam = []
    for i in range(1, len(src)):
        g0 = cv2.cvtColor(cv2.resize(src[i - 1], (sw, sh)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        g1 = cv2.cvtColor(cv2.resize(src[i], (sw, sh)), cv2.COLOR_BGR2GRAY).astype(np.float32)
        bgm = ((masks[i - 1] | masks[i]) == 0).astype(np.float32)
        (dx, dy), resp = cv2.phaseCorrelate(g0 * bgm, g1 * bgm)
        cam.append({"frame": i, "dx": round(dx / Q, 1), "dy": round(dy / Q, 1), "confidence": round(float(resp), 2)})
    doc = {
        "format": "fx_atlas/0.1",
        "source": {"post": a.source, "start_frame": a.clip[0], "frames": a.clip[1], "fps": round(fps, 3), "size": [W, H]},
        "kind": a.kind,
        "norm": {"origin": origin, "scale_px": round(scale, 1), "note": "area는 scale_px² 단위, velocity는 scale_px/장"},
        "layers": [{"layer": order.index(ci), "role": "fx" if fx[ci] else ("band" if mix[ci] else "background"),
                    "color_bgr": [int(v) for v in bgr[ci]], "lab": [round(float(v), 1) for v in cent[ci]]} for ci in order],
        "phases": phases,
        "frames": frames_out,
        "blobs": blobs,
        "camera": cam,
        "observation": {"band_removed": "relabel_band(위치 기준)", "edge_clipped_blobs": sum(b["touches_edge"] for b in blobs),
                        "notes": "덩어리 = 폭발 색 층 합집합의 연결 요소. 촬영 글로우는 관측에서 빼고 glow 값으로 재설계."},
    }
    if a.sfa:
        doc["shapes"] = {"sfa": os.path.basename(a.sfa), "glow_by_layer": sfa_glow(a.sfa)}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    ev = {}
    for b in blobs:
        for e in b["event"].split("+"):
            ev[e] = ev.get(e, 0) + 1
    print("장", len(frames), "덩어리", len(blobs), "사건", ev, "단계", phases, "홀드", sum(holds))


if __name__ == "__main__":
    main()
