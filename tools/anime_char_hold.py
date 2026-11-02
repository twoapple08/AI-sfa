"""nian41 인물(채도 높은 색) 영역만으로 '인물 그림이 바뀐 장'을 잰다.
- 마스크: HSV 채도 S>90, 명도 V>40 (회색 배경 위 색 인물. 분홍 이펙트·붉은 피도 섞일 수 있음)
- 카메라 이동 보정: 두 장의 마스크를 위상 상관으로 평행 이동 정렬한 뒤 비교
- 바뀜 정도 = 정렬 뒤 두 마스크의 XOR 면적 / 합집합 면적 (실루엣 변화)
사용: char_hold.py 영상 [시작장 끝장]
"""
import sys, json, collections
import numpy as np, cv2

p = sys.argv[1]
a0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
a1 = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
cap = cv2.VideoCapture(p)
fps = cap.get(cv2.CAP_PROP_FPS)
W = 320
masks = []
idx = -1
while True:
    ok, fr = cap.read()
    if not ok:
        break
    idx += 1
    if idx < a0:
        continue
    if idx > a1:
        break
    h = int(fr.shape[0] * W / fr.shape[1])
    fr = cv2.resize(fr, (W, h), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 90) & (hsv[..., 2] > 40)).astype(np.float32)
    masks.append(m)

def change(m1, m2):
    s1, s2 = m1.sum(), m2.sum()
    if s1 < 30 or s2 < 30:
        return None  # 인물 거의 없음
    (dx, dy), _ = cv2.phaseCorrelate(m1, m2)
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    m2s = cv2.warpAffine(m2, M, (m2.shape[1], m2.shape[0]))
    b1, b2 = m1 > 0.5, m2s > 0.5
    u = (b1 | b2).sum()
    return float((b1 ^ b2).sum() / max(1, u))

ch = [change(x, y) for x, y in zip(masks, masks[1:])]
valid = [c for c in ch if c is not None]
out = {'file': p.split('/')[-1][:24], 'fps': round(fps, 3), 'range': [a0, a0 + len(masks) - 1],
       'pairs': len(ch), 'with_char': len(valid)}
if valid:
    out['xor_pct10_25_50_75_90'] = np.percentile(valid, [10, 25, 50, 75, 90]).round(3).tolist()
    for thr in (0.10, 0.20, 0.30):
        runs = []; r = 0
        for c in ch:
            if c is None:
                if r: runs.append(r + 1)
                r = 0; continue
            if c < thr:
                r += 1
            else:
                runs.append(r + 1); r = 0
        runs.append(r + 1)
        same = sum(1 for c in valid if c < thr) / len(valid)
        cnt = collections.Counter(min(x, 6) for x in runs)
        out[f'thr{thr}'] = {'same_ratio': round(same, 3), 'hold_len': {k: cnt[k] for k in sorted(cnt)}}
print(json.dumps(out, ensure_ascii=False))
if '--seq' in sys.argv:
    print(' '.join('-' if c is None else f'{c:.2f}' for c in ch))
