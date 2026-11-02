"""두 장(같은 영상)의 화면 전체를 아핀(ECC)으로 정렬한 뒤 바뀐 픽셀 비율을 잰다.

용도: '그림은 같고 화면만 움직였나'를 가르는 보조 근거.
- 정렬 뒤 비율이 0에 가까우면: 화면 전체가 같은 그림이 이동·확대된 것(작화 같음).
- 정렬 뒤에도 크면: 작화 변화, 인물만의 이동, 파편·이펙트 변화 중 무엇인지 이 값만으로는 가를 수 없다.
비교 영역은 위 10%·아래 5%·좌우 3%를 뺀 화면(자막 띠·가장자리 제외). 바뀜 = 채널 최대 절대차 > 40.

사용: python tools/frame_pair_aligned_diff.py 영상 장A 장B
"""
import sys, json
import numpy as np, cv2

def grab(path, idx):
    c = cv2.VideoCapture(path)
    c.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, f = c.read()
    if not ok:
        raise SystemExit(f'장 {idx}를 읽지 못함')
    return f

def aligned_diff(a, b, thr=40):
    ga, gb = (cv2.cvtColor(x, cv2.COLOR_BGR2GRAY).astype(np.float32) for x in (a, b))
    H, W = ga.shape
    crop = lambda d: d[int(H * .1):int(H * .95), int(W * .03):int(W * .97)]
    raw = float((crop(np.abs(a.astype(int) - b.astype(int)).max(2)) > thr).mean())
    out = {'raw_changed': round(raw * 100, 3)}
    try:
        w = np.eye(2, 3, dtype=np.float32)
        _, w = cv2.findTransformECC(ga, gb, w, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5), None, 5)
        b2 = cv2.warpAffine(b, w, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
        al = float((crop(np.abs(a.astype(int) - b2.astype(int)).max(2)) > thr).mean())
        out.update(aligned_changed=round(al * 100, 3), dx=round(float(w[0, 2]), 2), dy=round(float(w[1, 2]), 2),
                   scale=round(float(np.sqrt(abs(np.linalg.det(w[:, :2])))), 5))
    except cv2.error:
        out['aligned_changed'] = None  # 정렬 실패(장면 전환 등)
    return out

if __name__ == '__main__':
    v, i, j = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    print(json.dumps(aligned_diff(grab(v, i), grab(v, j)), ensure_ascii=False))
