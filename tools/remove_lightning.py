#!/usr/bin/env python3
"""장면에서 번개(빛 이펙트)를 떼어 내고 그 자리의 배경(바위 + 불)을 메운다 (2026-10-26).

사용자: "바위와 불은 하나의 배경이야. 통합하고 번개를 따로 빼면서 비는 부분을 알아서 채워 봐. 외부 프로그램이든 뭐든 써도 상관없어."
1. 지울 자리: scene_layers.split의 번개(하늘색 + 흰 심)를 넓히고, 그 둘레 40px 안의 푸른 번짐(파랑이 빨강보다 센 곳)까지.
2. 앞뒤 장에서 가져오기: 나카무라 불은 2–3장씩 같은 그림을 쓰고 번개는 장마다 자리가 바뀐다 → 앞뒤 ±6장 중 그 픽셀이 안 가려졌고
   지울 자리 둘레(띠)가 지금 장과 거의 같은(평균 차 < 문턱) 가장 가까운 장의 픽셀을 쓴다. 실제 그림이라 가장 정확하다.
3. 남은 곳: LaMa(big-lama, CPU)로 메운다. 장마다 따로 메우므로 깜빡일 수 있어 2를 먼저 쓴다.
4. 번개 레이어 = max(0, 원본 − 메운 배경): 빛을 더하는 층(SFA에선 선 + 글로우로 옮길 것).
출력: <out>/bg/f000.png…, <out>/light/f000.png…, <out>/fill_src.npy(픽셀별 출처: 0 원본, 1 앞뒤 장, 2 LaMa), <out>/cmp.mp4, <out>/sheet.jpg
사용: LAMA_MODEL=<big-lama.pt> <venv>/python tools/remove_lightning.py <영상> <out> --clip 1128 32
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scene_layers import split  # noqa: E402


def erase_mask(im, light):
    m = cv2.dilate(light.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))
    near = cv2.dilate(light.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (81, 81))) > 0
    b, g, r = [im[..., i].astype(int) for i in range(3)]
    blueish = near & (b > r * 0.75 + 15) & (b > 40)  # 번개 빛이 바위·불을 푸르게 물들인 곳
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(int)
    # 빛 번짐(흰·분홍 안개): 번개 둘레에서 채도가 불(약 250)보다 크게 떨어진 밝은 곳. 1차 시험에서 이걸 안 지우자 LaMa가 둘레의 번짐을 보고 희뿌옇게 메웠다
    near2 = cv2.dilate(light.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (121, 121))) > 0
    bloom = near2 & (hsv[..., 1] < 200) & (hsv[..., 2] > 90)
    m = (m > 0) | blueish | bloom
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return cv2.dilate(m, np.ones((5, 5), np.uint8)) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--clip", type=int, nargs=2, default=(1128, 32))
    ap.add_argument("--reach", type=int, default=6, help="앞뒤 몇 장까지 찾나")
    ap.add_argument("--ring-tol", type=float, default=10.0, help="지울 자리 둘레 평균 차가 이보다 작아야 그 장을 씀")
    a = ap.parse_args()
    for d in ("bg", "light"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    c = cv2.VideoCapture(a.video)
    c.set(1, a.clip[0])
    F = [c.read()[1] for _ in range(a.clip[1])]
    M = [erase_mask(im, split(im)["light"]) for im in F]
    n = len(F)
    out, src = [], []
    lama = None
    for t in range(n):
        im = F[t].copy()
        todo = M[t].copy()
        s = np.zeros(todo.shape, np.uint8)
        ring = (cv2.dilate(M[t].astype(np.uint8), np.ones((25, 25), np.uint8)) > 0) & ~M[t]
        for dt in sorted(range(-a.reach, a.reach + 1), key=abs):
            u = t + dt
            if dt == 0 or not (0 <= u < n) or not todo.any():
                continue
            rr = ring & ~M[u]
            if rr.sum() < 50:
                continue
            diff = float(np.abs(F[u][rr].astype(np.float32) - F[t][rr].astype(np.float32)).mean())
            if diff > a.ring_tol:
                continue
            take = todo & ~M[u]
            im[take] = F[u][take]
            s[take] = 1
            todo &= ~take
        if todo.any():
            if lama is None:
                from simple_lama_inpainting import SimpleLama
                lama = SimpleLama()
            res = np.asarray(lama(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), (todo * 255).astype(np.uint8)))
            res = cv2.cvtColor(res[: im.shape[0], : im.shape[1]], cv2.COLOR_RGB2BGR)
            im[todo] = res[todo]
            s[todo] = 2
        out.append(im)
        src.append(s)
        light = np.clip(F[t].astype(int) - im.astype(int), 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(a.out, "bg", f"f{t:03d}.png"), im)
        cv2.imwrite(os.path.join(a.out, "light", f"f{t:03d}.png"), light)
        print(t, "지움", int(M[t].sum()), "앞뒤 장", int((s == 1).sum()), "LaMa", int((s == 2).sum()), flush=True)
    np.save(os.path.join(a.out, "fill_src.npy"), np.stack(src))
    h, w = F[0].shape[:2]
    vw = cv2.VideoWriter(os.path.join(a.out, "cmp.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 24, (w * 3 // 2, h // 2))
    sheet = []
    for t in range(n):
        light = np.clip(F[t].astype(int) - out[t].astype(int), 0, 255).astype(np.uint8)
        cells = [cv2.resize(x, (w // 2, h // 2)) for x in (F[t], out[t], light)]
        for x, lab in zip(cells, ("original", "background (filled)", "lightning (added light)")):
            cv2.putText(x, lab, (6, 22), 0, 0.6, (0, 255, 0), 2)
        row = np.hstack(cells)
        vw.write(row)
        if t in (0, n // 3, 2 * n // 3, n - 1):
            sheet.append(row)
    vw.release()
    cv2.imwrite(os.path.join(a.out, "sheet.jpg"), np.vstack(sheet), [cv2.IMWRITE_JPEG_QUALITY, 88])
    allsrc = np.stack(src)
    print("비율: 앞뒤 장", round(float((allsrc == 1).sum() / max(1, (allsrc > 0).sum())), 3), "LaMa", round(float((allsrc == 2).sum() / max(1, (allsrc > 0).sum())), 3))


if __name__ == "__main__":
    main()
