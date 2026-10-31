#!/usr/bin/env python3
"""학습 모델 비교 시트(2026-10-29): 같은 시험 장면에 모델 여러 개(1차 best·2차 best …)를 fp32로 돌려 나란히 그린다.
줄 = 시험 장면(영상 경로:장 번호), 칸 = 영상 | 모델마다 [선·끝점·면 겹침, 선 색, 그리는 순서].
숫자: 선 픽셀, 끝점 후보, 면 픽셀, 배경색 예측(중앙값). 영상 원본·프레임은 저장소에 넣지 않는다(시트는 scratch에).
사용: python vec_compare.py 출력.jpg --model 1차=best1.pt --model 2차=best2.pt --scene 영상.mp4:40 --scene 애니.mp4:405
"""
import argparse
import os
import subprocess
import sys

import cv2
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vec_train as T  # noqa: E402


def load(path):
    ck = torch.load(path, map_location='cpu', weights_only=False)
    net = T.Net(pretrained=False)
    net.load_state_dict(ck['model'] if isinstance(ck, dict) and 'model' in ck else ck)
    return net.eval()


def frames(video, ks):
    out = []
    for k in ks:
        p = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f'select=eq(n\\,{k})', '-vsync', '0', '-frames:v', '1',
                            '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True)
        im = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), 1)
        if im is None:
            raise SystemExit(f'장을 못 읽음: {video}:{k}')
        out.append(im[..., ::-1])
    return out


def sig(a):
    return 1 / (1 + np.exp(-a))


def panels(p, img):
    c, pts, fill = sig(p[0]), sig(p[1]), sig(p[4])
    a = sig(p[5:21])
    ov = (img * 0.35).astype(np.uint8)
    ov[c > 0.5] = (255, 0, 0)
    ov[fill > 0.5] = (ov[fill > 0.5] * 0.5 + np.array([0, 120, 0])).astype(np.uint8)
    hp = cv2.applyColorMap((np.clip(pts, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)[..., ::-1]
    ov = np.ascontiguousarray(np.where((pts > 0.3)[..., None], hp, ov))
    line = np.zeros_like(img)
    lc = (np.stack([a[1], a[2], a[3]], -1) * 255).astype(np.uint8)
    line[c > 0.5] = lc[c > 0.5]
    order = np.ascontiguousarray(cv2.applyColorMap((a[15] * 255).astype(np.uint8), cv2.COLORMAP_JET)[..., ::-1])
    stats = dict(선=int((c > 0.5).sum()), 끝점=int((pts > 0.3).sum()), 면=int((fill > 0.5).sum()),
                 배경=tuple(int(v) for v in (np.median(sig(p[25:28]).reshape(3, -1), 1) * 255)))
    return [ov, line, order], stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--model', action='append', required=True, help='이름=경로')
    ap.add_argument('--scene', action='append', required=True, help='영상경로:장번호')
    ap.add_argument('--width', type=int, default=640)
    a = ap.parse_args()
    models = [(m.split('=', 1)[0], load(m.split('=', 1)[1])) for m in a.model]
    print('칸 번호:', ', '.join(f'M{i + 1}={n}' for i, (n, _) in enumerate(models)), flush=True)
    rows = []
    for sc in a.scene:
        v, k = sc.rsplit(':', 1)
        k = int(k)
        fr = frames(v, [max(k - 1, 0), k, k + 1])
        H0, W0 = fr[1].shape[:2]
        W = a.width
        H = max(32, int(round(W * H0 / W0 / 32)) * 32)
        fr = [cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA) for f in fr]
        x = torch.from_numpy(np.concatenate(fr, -1).astype(np.float32).transpose(2, 0, 1) / 255.0)[None]
        cells = [fr[1].copy()]
        cv2.putText(cells[0], f'scene {len(rows) + 1} frame {k}', (5, 16), 0, 0.5, (255, 0, 0), 1)
        for mi, (name, net) in enumerate(models):
            with torch.no_grad():
                p = net(x)[0].numpy()
            pn, st = panels(p, fr[1])
            for im, lab in zip(pn, ('line/point/fill', 'line color', 'draw order')):
                cv2.putText(im, f'M{mi + 1} {lab}', (5, 16), 0, 0.5, (255, 255, 0), 1)  # 그림 글씨는 영문만 — 모델 이름은 아래 출력의 M번호
            cells += pn
            print(os.path.basename(v), k, name, st, flush=True)
        rows.append(np.hstack(cells))
    w = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, w - r.shape[1]), (0, 0))) for r in rows]
    sheet = np.vstack(rows)
    scale = min(1.0, 2400 / sheet.shape[1])
    cv2.imwrite(a.out, cv2.cvtColor(cv2.resize(sheet, None, fx=scale, fy=scale), cv2.COLOR_RGB2BGR))
    print('시트:', a.out)


if __name__ == '__main__':
    main()
