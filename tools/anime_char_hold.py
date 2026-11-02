"""nian41 인물(채도 높은 색) 영역에서 '평행 이동 정렬 뒤 실루엣 변화'를 장 쌍마다 잰다.

- 마스크: HSV 채도 S>90, 명도 V>40 (회색 배경 위 색 인물. 분홍 이펙트·붉은 피도 섞일 수 있음)
- 두 장의 마스크를 위상 상관으로 평행 이동 정렬한다. 이 정렬량은 인물 이동 + 카메라 이동이 섞인 값이다.
- 변화 = 정렬 뒤 XOR 면적 / 합집합 면적. 문턱 아래를 '정지 후보'로 센다(같은 그림이라는 확정이 아님).
- 2026-11-02 2판: 인물 없음(None)으로 끊길 때 그림 유지 길이를 빠뜨리던 집계를 고침.

사용: anime_char_hold.py 영상 [시작장 끝장] [--seq]
"""
import sys, json, collections
import numpy as np, cv2

W = 320
THRS = (0.10, 0.20, 0.30)

def char_mask(fr):
    h = int(fr.shape[0] * W / fr.shape[1])
    fr = cv2.resize(fr, (W, h), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    return ((hsv[..., 1] > 90) & (hsv[..., 2] > 40)).astype(np.float32)

def change(m1, m2):
    if m1.sum() < 30 or m2.sum() < 30:
        return None  # 인물 거의 없음
    (dx, dy), _ = cv2.phaseCorrelate(m1, m2)
    M = np.float32([[1, 0, -dx], [0, 1, -dy]])
    m2s = cv2.warpAffine(m2, M, (m2.shape[1], m2.shape[0]))
    b1, b2 = m1 > 0.5, m2s > 0.5
    u = (b1 | b2).sum()
    return float((b1 ^ b2).sum() / max(1, u))

def read_masks(path, a0=0, a1=10**9):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    masks, idx = [], -1
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        idx += 1
        if idx < a0:
            continue
        if idx > a1:
            break
        masks.append(char_mask(fr))
    return masks, fps

def changes(masks):
    return [change(x, y) for x, y in zip(masks, masks[1:])]

def hold_runs(ch, thr):
    """그림 하나가 유지된 장 수 목록. None(인물 없음)에서 구간을 끊는다."""
    runs, r, open_ = [], 1, False
    for c in ch:
        if c is None:
            if open_:
                runs.append(r)
            r, open_ = 1, False
            continue
        open_ = True
        if c < thr:
            r += 1
        else:
            runs.append(r); r = 1
    if open_:
        runs.append(r)
    return runs

def summary(path, a0=0, a1=10**9):
    masks, fps = read_masks(path, a0, a1)
    ch = changes(masks)
    valid = [c for c in ch if c is not None]
    out = {'file': path.split('/')[-1][:24], 'fps': round(fps, 3), 'range': [a0, a0 + len(masks) - 1],
           'pairs': len(ch), 'with_char': len(valid)}
    if valid:
        out['xor_pct10_25_50_75_90'] = np.percentile(valid, [10, 25, 50, 75, 90]).round(3).tolist()
        for thr in THRS:
            cnt = collections.Counter(min(x, 6) for x in hold_runs(ch, thr))
            out[f'thr{thr}'] = {'below_ratio': round(sum(c < thr for c in valid) / len(valid), 3),
                                'hold_len': {k: cnt[k] for k in sorted(cnt)}}
    return out, ch

if __name__ == '__main__':
    p = sys.argv[1]
    nums = [a for a in sys.argv[2:] if a.lstrip('-').isdigit()]
    a0 = int(nums[0]) if nums else 0
    a1 = int(nums[1]) if len(nums) > 1 else 10**9
    out, ch = summary(p, a0, a1)
    print(json.dumps(out, ensure_ascii=False))
    if '--seq' in sys.argv:
        print(' '.join('-' if c is None else f'{c:.2f}' for c in ch))
