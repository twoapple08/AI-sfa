#!/usr/bin/env python3
"""그림·정답 정합성 검사(2026-11-01, GPT 1라운드 검토 ①): 학습 입력 그림(원래 SFA 렌더)과 정답(토큰 복원 SFA 렌더)이 같은 그림인가.
좌표를 칸 단위로 맞추며 생기는 1화소 미만 가장자리 어긋남(안티에일리어싱)은 허용한다: 두 그림을 σ=1.5로 흐린 뒤 비교한다.
사용(모듈): mismatch(seq, fr) → (어긋난 화소 수, 정답 토큰 수)
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
import sfa_tokens as K  # noqa: E402

TOL = 24          # 채널 차이 허용(이보다 크면 다름)
SIGMA = 1.5       # 비교 전 흐림
W = 640


def tolerant_diff(a, b, tol=TOL, sigma=SIGMA):
    """두 그림을 가우스 σ로 흐린 뒤 채널 차이가 tol을 넘는 화소 수. 좌표 칸 맞춤(0.025% ≈ 640폭 0.16화소)으로 선 가장자리
    밝기가 최대 40가량 바뀌는 것은 σ=1.5에서 사라진다(11-01 실측 최대 21). 숨긴 면처럼 넓은 차이는 그대로 잡힌다."""
    import cv2
    x = cv2.GaussianBlur(a.astype(np.float32), (0, 0), sigma)
    y = cv2.GaussianBlur(b.astype(np.float32), (0, 0), sigma)
    return int((np.abs(x - y).max(2) > tol).sum())


def mismatch(seq, fr, w=W):
    """(어긋난 화소 수, 정답 토큰 수). 전역 렌더 설정(R.PARAMS)은 바꿨다가 반드시 되돌린다(GPT 재확인 11-01: 되돌리지 않아
    뒤이은 1080 학습 영상의 선 굵기가 36→12화소로 바뀌었는데 검사값은 0이었다)."""
    hwr = float(seq.get('HeightWidthRatio') or 0.5625) or 0.5625
    h = max(2, int(round(w * hwr)))
    saved = dict(R.PARAMS)
    try:
        R.PARAMS['pad'] = 0.0
        R.PARAMS['thick_mul'] = w / 1920
        t, _ = K.encode(seq, fr)
        a = R.render_frame(seq, fr, w, h)[..., :3]
        b = R.render_frame(seq, K.decode(t), w, h)[..., :3]
        return tolerant_diff(a, b), len(t)
    finally:
        R.PARAMS.clear()
        R.PARAMS.update(saved)
