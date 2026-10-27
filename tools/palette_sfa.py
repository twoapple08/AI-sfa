#!/usr/bin/env python3
"""장면 영상 → 공통 팔레트의 평면 색 면 SFA (각진 모양 유지, 홀드 재사용) — 폭발 복원 기준작 A 1차 (2026-10-27).

GPT 계획(docs/GPT-FX-PLAN-2026-10-27.md) 2단계. 품질 천장 시험(불 벽)에서 지금 변환기가 3–4색 평면을 밝기 10단계로 쪼개고
각진 조각을 둥글게 뭉갰다 → 이 도구는
1. 클립 전체에서 Lab k-평균으로 공통 팔레트 K색(장마다 색이 흔들리지 않게),
2. 장마다 픽셀을 가장 가까운 팔레트 색으로(가장자리 잡티는 최빈값 필터로 정리),
3. 색마다 면: 넓은 색부터 아래에, 2px 넓혀 밑에 깔아 틈을 막고(under), 윤곽은 작은 오차·약한 다듬기로 꺾인 점을 살린다,
4. 앞 장과 평균 차가 --hold보다 작으면 앞 장 그림을 그대로(나카무라 2·3장 유지).
글로우는 2차에서(밝은 폭발 층에 glow_fit 방식). 글로우 값은 정수로 쓴다(앱이 소수점 글로우를 끈다, 2026-10-27 확인).
좌표·굵기 단위: 1920×1080로 키워서 딴다(앱·렌더러의 굵기·글로우가 절대 px).
사용: python tools/palette_sfa.py <영상> <out.sfa> --clip 926 31 [--k 16] [--check 비교.mp4]
"""
import argparse
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glow_fit import Writer  # noqa: E402
from person_sfa import coarse  # noqa: E402
from effect_clip_sfa import argb  # noqa: E402

W, H = 1920, 1080


def palette(frames, k):
    lab = np.concatenate([cv2.cvtColor(f, cv2.COLOR_BGR2LAB).reshape(-1, 3)[::37] for f in frames]).astype(np.float32)
    cv2.setRNGSeed(0)
    _, _, cent = cv2.kmeans(lab, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5), 4, cv2.KMEANS_PP_CENTERS)
    bgr = cv2.cvtColor(cent.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).reshape(-1, 3)
    return cent, bgr


def label(frame, cent, mode=7):
    lab = cv2.cvtColor(cv2.bilateralFilter(frame, 7, 20, 7), cv2.COLOR_BGR2LAB).astype(np.float32)
    idx = np.linalg.norm(lab[..., None, :] - cent[None, None], axis=3).argmin(2).astype(np.uint8)
    return cv2.medianBlur(idx, mode)


def frame_xml(wr, idx, bgr, order, layer_of, tol, sigma, min_area, grow):
    n = 0
    for ci in order:
        m = (idx == ci).astype(np.uint8)
        if m.sum() < min_area:
            continue
        m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))  # 밑에 깔아 틈 막기
        sh = coarse(m, tol, sigma, min_area)
        if sh:
            wr.fill(sh, argb(bgr[ci]), layer_of[ci], 0.1, (0, 0, 4294967295, 0))
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--clip", type=int, nargs=2, required=True)
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--tol", type=float, default=1.5, help="윤곽 맞춤 오차 px(작을수록 꺾인 점이 산다)")
    ap.add_argument("--sigma", type=float, default=1.5, help="윤곽 다듬기(작을수록 각진 모양 유지)")
    ap.add_argument("--min-area", type=int, default=120)
    ap.add_argument("--grow", type=int, default=2)
    ap.add_argument("--hold", type=float, default=3.0)
    ap.add_argument("--check")
    a = ap.parse_args()
    c = cv2.VideoCapture(a.video)
    c.set(1, a.clip[0])
    src = [c.read()[1] for _ in range(a.clip[1])]
    frames = [cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC) for f in src]
    cent, bgr = palette(frames, a.k)
    # 넓은 색부터 아래(배경이 먼저). 레이어 = 팔레트 색 하나
    area = sum(np.bincount(label(f, cent).ravel(), minlength=a.k) for f in frames[::4])
    order = list(np.argsort(-area))
    layer_of = {ci: li for li, ci in enumerate(order)}
    wr = Writer(W, H)
    body, prev_small, prev_xml, held = [], None, None, 0
    for fi, f in enumerate(frames):
        small = cv2.resize(src[fi], (214, 120)).astype(np.float32)
        if prev_small is not None and a.hold > 0 and float(np.abs(small - prev_small).mean()) < a.hold:
            xml = prev_xml  # 같은 그림 유지(오브젝트 번호도 같게 — 사용자 파일처럼 같은 오브젝트가 이어짐)
            held += 1
        else:
            start = len(wr.out)
            frame_xml(wr, label(f, cent), bgr, order, layer_of, a.tol, a.sigma, a.min_area, a.grow)
            xml = "\n".join(wr.out[start:])
            prev_small = small
        prev_xml = xml
        defs = "".join(f'<LayerDef ID="{li}" Name="색{li}" Visible="true" Locked="false"/>' for li in range(a.k))
        body.append(f'<Frame BackgroundColor="{argb(bgr[order[0]])}" ID="{fi + 1}" Position="{fi}">' + defs + "\n" + xml + "\n</Frame>")
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"{len(frames)}\" BackgroundColor=\"{argb(bgr[order[0]])}\">\n" + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    print("장", len(frames), "홀드 재사용", held, "AO", wr.oid - 1, "MB", round(os.path.getsize(a.out) / 1e6, 2), "팔레트", a.k)
    if a.check:
        tmp = a.out + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), a.out, tmp,
                        "--frames", ",".join(map(str, range(len(frames)))), "--size", f"{W}x{H}"], check=True, capture_output=True)
        rs = sorted(os.listdir(tmp))
        vw = cv2.VideoWriter(a.check, cv2.VideoWriter_fourcc(*"mp4v"), 24, (1708, 480))
        errs = []
        for fi, f in enumerate(src):
            r = cv2.resize(cv2.imread(os.path.join(tmp, rs[fi])), (854, 480))
            errs.append(float(np.abs(r.astype(np.float32) - f.astype(np.float32)).mean()))
            fr = np.hstack([f, r])
            cv2.putText(fr, "original", (8, 26), 0, 0.8, (255, 255, 255), 2)
            cv2.putText(fr, "SFA", (862, 26), 0, 0.8, (255, 255, 255), 2)
            vw.write(fr)
        vw.release()
        print("원본 차 평균", round(float(np.mean(errs)), 2))


if __name__ == "__main__":
    main()
