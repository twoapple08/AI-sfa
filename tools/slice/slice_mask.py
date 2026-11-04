"""시험판(원본1032–1271) 인물 영역 마스크: 이 클립의 빨강/파랑 인물 색 + 외곽선 넓히기. 이 클립 전용 임시 방법(추론)."""
import cv2, numpy as np
def person_mask(bgr, grow=7):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    red = ((h <= 8) | (h >= 168)) & (s > 70) & (v > 40)
    blue = (h >= 95) & (h <= 125) & (s > 55) & (v > 40)
    m = (red | blue).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    keep = np.zeros_like(m)
    for i in range(1, n):
        w, h = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]
        if st[i, cv2.CC_STAT_AREA] >= 150 and w >= 10 and h / max(w, 1) < 4.5:   # 천장 빨간 배관(가늘고 긴 덩어리) 제외
            keep[lab == i] = 1
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # 내부 구멍(어두운 옷 주름·선) 메우기
    ff = keep.copy(); hh, ww = ff.shape; fl = np.zeros((hh + 2, ww + 2), np.uint8)
    cv2.floodFill(ff, fl, (0, 0), 1); keep = keep | (1 - ff)
    return cv2.dilate(keep, np.ones((2 * grow + 1, 2 * grow + 1), np.uint8))
