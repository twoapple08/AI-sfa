"""두 장(같은 영상)을 화면 전체 기준으로 정렬한 뒤 남는 픽셀 차이를 잰다. **보조 근거용**이다.

측정하는 것: 지정 영역에서 채널 최대 절대차가 문턱(기본 40)을 넘는 픽셀 비율(정렬 전·후), 평균 잔차.
측정하지 않는 것: 작화 동일성 자체, 관절 오차, 검출 정확도.

한계(GPT 4차 지적, 2026-11-02 2판에 반영):
1. 전역 비율은 작은 대상을 놓친다. 인물·관절 주변 영역(--roi)을 따로 본다.
2. 아핀 정렬은 형상 차이 일부를 흡수하거나 엉뚱한 해로 갈 수 있다. ECC 상관계수, 행렬, 유효 겹침, 변환 크기를
   기록하고, 허용 범위를 벗어나면 status='판정 불가'로 둔다(허용 범위는 잠정값, 검증 표본으로 조정).
3. 문턱 아래 차이는 비율에서 빠진다. 낮은 비율이 픽셀 동일성을 증명하지 않는다 → 평균 잔차를 함께 낸다.
4. dx·dy는 영상 간 정합값이다. 물리적 카메라 이동으로 확정하지 않는다.
5. scale = sqrt(|det A|)는 요약값이다. 회전·전단·비등방 변형은 행렬을 직접 본다.

사용: python tools/frame_pair_aligned_diff.py 영상 장A 장B [--roi x0 y0 x1 y1] [--translation]
"""
import sys, json
import numpy as np, cv2

# 잠정 허용 범위(검증 표본으로 조정 예정)
MAX_SHIFT_FRAC = 0.25   # 이동량 ≤ 화면 폭·높이의 25%
SCALE_RANGE = (0.8, 1.25)
MAX_SHEAR = 0.1         # |A - sR| 성분 상한(대략적 전단·비등방 검사)
MIN_CC = 0.5            # ECC 상관계수 하한
MIN_OVERLAP = 0.7       # 비교 영역 중 정렬 뒤 유효 픽셀 비율 하한

def grab(path, idx):
    c = cv2.VideoCapture(path)
    c.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = c.read()
    if not ok:
        raise SystemExit(f'장 {idx}를 읽지 못함')
    return f

def default_roi(H, W):
    return (int(W * .03), int(H * .1), int(W * .97), int(H * .95))

def aligned_diff(a, b, thr=40, roi=None, translation=False):
    ga, gb = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32) for x in (a, b))
    H, W = ga.shape
    x0, y0, x1, y1 = roi or default_roi(H, W)
    R = lambda d: d[y0:y1, x0:x1]
    d0 = np.abs(a.astype(int) - b.astype(int)).max(2)
    out = {'roi': [x0, y0, x1, y1], 'thr': thr,
           'raw_changed': round(float((R(d0) > thr).mean()) * 100, 3),
           'raw_mean_abs': round(float(R(d0).mean()), 3)}
    mode = cv2.MOTION_TRANSLATION if translation else cv2.MOTION_AFFINE
    out['model'] = 'translation' if translation else 'affine'
    try:
        w = np.eye(2, 3, dtype=np.float32)
        cc, w = cv2.findTransformECC(ga, gb, w, mode,
                                     (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), None, 5)
    except cv2.error:
        out.update(status='판정 불가', reason='정렬 실패')
        return out
    b2 = cv2.warpAffine(b, w, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    valid = cv2.warpAffine(np.ones((H, W), np.uint8), w, (W, H),
                           flags=cv2.INTER_NEAREST + cv2.WARP_INVERSE_MAP) > 0
    d1 = np.abs(a.astype(int) - b2.astype(int)).max(2)
    v = R(valid)
    overlap = float(v.mean())
    A = w[:, :2].astype(float)
    s = float(np.sqrt(abs(np.linalg.det(A))))
    # 회전+균등 배율로 근사한 뒤 남는 성분(전단·비등방)
    U, _, Vt = np.linalg.svd(A)
    shear = float(np.abs(A - s * (U @ Vt)).max())
    dx, dy = float(w[0, 2]), float(w[1, 2])
    out.update(ecc_cc=round(float(cc), 4), matrix=[[round(float(x), 5) for x in row] for row in w],
               dx=round(dx, 2), dy=round(dy, 2), scale=round(s, 5), shear=round(shear, 4),
               overlap=round(overlap, 3),
               aligned_changed=round(float((R(d1)[v] > thr).mean()) * 100, 3) if v.any() else None,
               aligned_mean_abs=round(float(R(d1)[v].mean()), 3) if v.any() else None)
    bad = []
    if abs(dx) > MAX_SHIFT_FRAC * W or abs(dy) > MAX_SHIFT_FRAC * H: bad.append('이동 과대')
    if not (SCALE_RANGE[0] <= s <= SCALE_RANGE[1]): bad.append('배율 범위 밖')
    if shear > MAX_SHEAR: bad.append('전단·비등방 과대')
    if cc < MIN_CC: bad.append('상관 낮음')
    if overlap < MIN_OVERLAP: bad.append('유효 겹침 부족')
    out['status'] = '판정 불가' if bad else '정렬 유효'
    if bad: out['reason'] = ', '.join(bad)
    return out

if __name__ == '__main__':
    args = sys.argv[1:]
    roi = None
    if '--roi' in args:
        i = args.index('--roi'); roi = tuple(int(x) for x in args[i + 1:i + 5]); del args[i:i + 5]
    tr = '--translation' in args
    args = [x for x in args if x != '--translation']
    v, i, j = args[0], int(args[1]), int(args[2])
    print(json.dumps(aligned_diff(grab(v, i), grab(v, j), roi=roi, translation=tr), ensure_ascii=False))
