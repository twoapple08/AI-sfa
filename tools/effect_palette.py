#!/usr/bin/env python3
"""나카무라 임팩트 앞뒤 컬러 프레임에서 이펙트 색(밝고 채도 높은 픽셀)을 k-평균으로 묶어 팔레트를 만든다.
출력: 'P r g b 비율' 줄(밝기순). 반투명 겹침 이펙트의 바깥→안쪽 색으로 쓴다.
사용: python tools/effect_palette.py <나카무라 영상 폴더> <판정 csv> [--k 8]
"""
import argparse, csv, os
import cv2, numpy as np

ap = argparse.ArgumentParser(); ap.add_argument('vids'); ap.add_argument('judge'); ap.add_argument('--k', type=int, default=8)
a = ap.parse_args()
px = []
for r in csv.DictReader(open(a.judge, encoding='utf-8')):
    if r['animator'] != 'yutaka_nakamura' or r['claude_visual'] not in ('임팩트', '단색섬광'):
        continue
    p = os.path.join(a.vids, r['post_id'] + '.mp4')
    if not os.path.exists(p):
        continue
    f0, f1 = (int(x) for x in (r['frames'].split('-') + [r['frames']])[:2])
    v = cv2.VideoCapture(p)
    for f in (f0 - 3, f0 - 1, f1 + 1, f1 + 3):
        v.set(cv2.CAP_PROP_POS_FRAMES, max(0, f)); ok, img = v.read()
        if not ok:
            continue
        img = cv2.resize(img, (160, 90))
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        sel = img.reshape(-1, 3)[(hsv[:, 1] > 90) & (hsv[:, 2] > 150)]
        px.append(sel)
X = np.vstack(px).astype(np.float32)
_, lab, cen = cv2.kmeans(X, a.k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5), 5, cv2.KMEANS_PP_CENTERS)
cnt = np.bincount(lab.ravel(), minlength=a.k) / len(lab)
order = np.argsort(cen.sum(1))
for i in order:
    b, g, r_ = cen[i]
    print(f'P {int(r_)} {int(g)} {int(b)} {cnt[i]:.3f}')
