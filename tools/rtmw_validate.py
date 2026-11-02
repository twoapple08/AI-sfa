"""기존 RTMW-x 결과(jsonl.gz, 장마다 {'f', 'p':[{'b':상자, 'k':133점 [x,y,점수]}]})를 영상과 대조해 검증한다.

검사(GPT 4차 합의 순서 1–4단계의 CPU 부분):
1. 133점 의미: COCO-WholeBody 순서 가정(0–16 몸, 17–19 왼발, 20–22 오른발, 91–111 왼손, 112–132 오른손)의
   '상대 대응 일관성' = 한 인물 결과에서 (같은쪽 거리합) < (교차 거리합)인 비율. 절대 근접도·점수 문턱이 없고,
   몸·손 좌우가 함께 뒤집혀도 통과한다 → 관절 정답률·좌우 정확도가 아니다(GPT 5차 지적).
2. 장 번호 대응(보조 근거): 모든 오프셋에서 결과가 1명인 '공통 장 집합'에서 상체·엉덩이 평균 중심과 색 마스크
   무게중심의 거리를 비교하고 표본 수를 함께 낸다. 1차 근거는 파일 해시·장 번호·디코딩 규칙이다.
3. 대상 대응: 상자 안 파랑/빨강 채도 픽셀 비율로 색 인물을 배정한다(배정 성공 ≠ 신원 정확도).
   이동은 두 가지로 낸다: ① 어깨2·엉덩이2 평균 중심 이동/몸통, ② 엉덩이 중점(11·12 평균) 이동/몸통.
   몸통 = 어깨 중점–엉덩이 중점 거리(파생점, 앱의 목–골반과 같지 않다).
4. 좌우 바뀜 후보: 인접 장에서 좌우를 맞바꾼 쪽이 관절 이동이 절반 이하로 작으면 후보로 센다(확정 아님).
   지속적인 뒤바뀜·가림 오검출·가까운 교차 사지는 잡지 못한다. 점수(1 초과 값 있음)는 확률이 아니다.

사용: python tools/rtmw_validate.py 결과.jsonl.gz 영상.mp4 [--range a b]... [--target-color blue|red]
"""
import sys, json, gzip, collections
import numpy as np, cv2

LW, RW, LA, RA = 9, 10, 15, 16
L_ARM, R_ARM = [5, 7, 9], [6, 8, 10]
L_LEG, R_LEG = [11, 13, 15], [12, 14, 16]

def load(path):
    R = {}
    for l in gzip.open(path, 'rt'):
        r = json.loads(l)
        R[r['f']] = [(np.array(p['b'], float), np.array(p['k'], float)) for p in r['p']]
    return R

def mapping_check(R):
    ok_hand = ok_foot = n_hand = n_foot = 0
    for ps in R.values():
        for _, k in ps:
            if k.shape[0] < 133:
                continue
            d = lambda i, j: np.hypot(*(k[i, :2] - k[j, :2]))
            n_hand += 1
            ok_hand += (d(LW, 91) + d(RW, 112)) < (d(LW, 112) + d(RW, 91))
            n_foot += 1
            ok_foot += (d(LA, 19) + d(RA, 22)) < (d(LA, 22) + d(RA, 19))
    return {'손 상대 대응 일관': [ok_hand, n_hand, round(ok_hand / max(1, n_hand), 4)],
            '발 상대 대응 일관': [ok_foot, n_foot, round(ok_foot / max(1, n_foot), 4)]}

def color_masks(fr):
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    sat = (hsv[..., 1] > 90) & (hsv[..., 2] > 40)
    h = hsv[..., 0]
    blue = sat & (h >= 90) & (h <= 135)
    red = sat & ((h <= 10) | (h >= 160))
    return sat, blue, red

def body_center(k):
    return k[[5, 6, 11, 12], :2].mean(0)

def main():
    args = sys.argv[1:]
    res_path, vid = args[0], args[1]
    ranges = []
    while '--range' in args:
        i = args.index('--range'); ranges.append((int(args[i + 1]), int(args[i + 2]))); del args[i:i + 3]
    target = 'blue'
    if '--target-color' in args:
        target = args[args.index('--target-color') + 1]
    R = load(res_path)
    out = {'장 수(결과 파일)': len(R), '장 번호 연속': sorted(R) == list(range(min(R), max(R) + 1))}
    out['133점 순서 가정의 상대 대응 일관성(정답률 아님)'] = mapping_check(R)

    cap = cv2.VideoCapture(vid)
    nvid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); W = cap.get(cv2.CAP_PROP_FRAME_WIDTH); H = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    out['영상'] = {'장': nvid, '크기': [W, H]}
    # 2. 장 번호 대응: 1명 장의 몸 중심 vs 색 마스크 무게중심
    cents = {}
    idx = -1
    while True:
        ok, fr = cap.read()
        if not ok: break
        idx += 1
        if idx % 3: continue  # 3장마다 표본
        sat, _, _ = color_masks(cv2.resize(fr, (int(W // 4), int(H // 4))))
        ys, xs = np.nonzero(sat)
        if len(xs) > 50: cents[idx] = np.array([xs.mean() * 4, ys.mean() * 4])
    common = [f for f in cents if all(len(R.get(f + o, [])) == 1 for o in range(-2, 3))]
    off_err = {}
    for off in range(-2, 3):
        e = [np.hypot(*(body_center(R[f + off][0][1]) - cents[f])) for f in common]
        off_err[off] = round(float(np.median(e)), 1) if e else None
    out['장 번호 오프셋별 상체·엉덩이 평균중심-색마스크중심 거리 중앙값(px), 공통 장 집합'] = {'표본 장 수': len(common), '거리': off_err}

    # 3·4. 구간별 대상 대응·좌우 바뀜 후보
    for a, b in ranges:
        seq = []
        for f in range(a, b + 1):
            cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, fr = cap.read()
            _, blue, red = color_masks(fr)
            m = blue if target == 'blue' else red
            best = None
            for bx, k in R.get(f, []):
                x0, y0, x1, y1 = [int(v) for v in bx]
                x0, y0 = max(0, x0), max(0, y0)
                share = m[y0:y1, x0:x1].sum() / max(1, (y1 - y0) * (x1 - x0))
                other = (red if target == 'blue' else blue)[y0:y1, x0:x1].sum() / max(1, (y1 - y0) * (x1 - x0))
                if share > other and (best is None or share > best[0]):
                    best = (share, k)
            seq.append((f, None if best is None else best[1]))
        got = [s for s in seq if s[1] is not None]
        jumps, hipj, swaps = [], [], []
        for (f1, k1), (f2, k2) in zip(seq, seq[1:]):
            if k1 is None or k2 is None: continue
            torso = np.hypot(*(k1[[5, 6], :2].mean(0) - k1[[11, 12], :2].mean(0))) or 1
            jumps.append(np.hypot(*(body_center(k2) - body_center(k1))) / torso)
            hipj.append(np.hypot(*(k2[[11, 12], :2].mean(0) - k1[[11, 12], :2].mean(0))) / torso)
            for Lj, Rj, name in ((L_ARM, R_ARM, '팔'), (L_LEG, R_LEG, '다리')):
                same = np.linalg.norm(k1[Lj, :2] - k2[Lj, :2]) + np.linalg.norm(k1[Rj, :2] - k2[Rj, :2])
                sw = np.linalg.norm(k1[Lj, :2] - k2[Rj, :2]) + np.linalg.norm(k1[Rj, :2] - k2[Lj, :2])
                if sw < 0.5 * same:
                    swaps.append((f1, f2, name))
        out[f'구간 {a}-{b}'] = {'대상 배정된 장': f'{len(got)}/{len(seq)}',
                               '상체·엉덩이 평균중심 이동/몸통 중앙·최대': [round(float(np.median(jumps)), 3), round(float(max(jumps)), 3)] if jumps else None,
                               '엉덩이 중점 이동/몸통 중앙·최대': [round(float(np.median(hipj)), 3), round(float(max(hipj)), 3)] if hipj else None,
                               '좌우 바뀜 후보(장쌍, 부위)': swaps}
    print(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))

if __name__ == '__main__':
    main()
