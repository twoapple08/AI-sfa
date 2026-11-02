"""대상 인물의 '그림 구간'(같은 작화가 유지되는 연속 장)을 나누고 구간마다 대표 장을 고른다.

- 대상 마스크: HSV 채도 마스크 중 대상 색(blue / red / any). 인물이 둘이면 대상 색을 지정한다.
- 인접 장 변화 = 평행 이동 정렬 뒤 대상 실루엣 XOR/합집합(tools/anime_char_hold.py와 같은 계산).
- 변화 ≥ 높은 문턱(기본 0.3) → 새 그림 시작. 낮은 문턱(0.1)~높은 문턱 사이는 '애매'로 표시하고 확인 대상으로 둔다.
  애매한 쌍은 구간을 나누지 않지만 목록으로 낸다(라벨 확인용). 대상 없음(None)은 구간을 끊는다.
- 장 번호는 0부터 시작하는 디코딩 순서다. 경계 번호 = '새 그림의 첫 장'.
- 범위 시작·끝에서 잘린 구간은 partial=True로 표시한다(범위 밖에서 시작하거나 끝날 수 있음).
- 대표 장 = 각 구간의 첫 장. 대표 장 외에 접촉·가림·좌우 교차·대상 배정 경계 장은 라벨러가 따로 추가한다.

사용: python tools/drawing_segments.py 영상 시작장 끝장 [--color blue|red|any] [--hi 0.3] [--lo 0.1]
"""
import sys, json
import numpy as np, cv2

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import anime_char_hold as A

def target_mask(fr, color):
    h = int(fr.shape[0] * A.W / fr.shape[1])
    fr = cv2.resize(fr, (A.W, h), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
    sat = (hsv[..., 1] > 90) & (hsv[..., 2] > 40)
    hue = hsv[..., 0]
    if color == 'blue':
        sat &= (hue >= 90) & (hue <= 135)
    elif color == 'red':
        sat &= (hue <= 10) | (hue >= 160)
    return sat.astype(np.float32)

def segments(path, a, b, color='any', hi=0.3, lo=0.1):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, a)
    masks = []
    for _ in range(a, b + 1):
        ok, fr = cap.read()
        if not ok:
            break
        masks.append(target_mask(fr, color))
    ch = [A.change(x, y) for x, y in zip(masks, masks[1:])]
    segs, amb = [], []
    start = a
    for i, c in enumerate(ch):
        f2 = a + i + 1
        if c is None or c >= hi:
            segs.append([start, f2 - 1]); start = f2
        elif c >= lo:
            amb.append([f2 - 1, f2, round(c, 3)])
    segs.append([start, a + len(masks) - 1])
    out = []
    for s0, s1 in segs:
        out.append({'first': s0, 'last': s1, 'len': s1 - s0 + 1,
                    'partial': s0 == a or s1 == a + len(masks) - 1})
    return {'range': [a, a + len(masks) - 1], 'color': color, 'hi': hi, 'lo': lo,
            'segments': out, 'representatives': [s['first'] for s in out],
            'ambiguous_pairs': amb, 'none_pairs': [a + i for i, c in enumerate(ch) if c is None]}

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = lambda k, d: type(d)(args[args.index(k) + 1]) if k in args else d
    r = segments(args[0], int(args[1]), int(args[2]), opt('--color', 'any'), opt('--hi', 0.3), opt('--lo', 0.1))
    print(json.dumps(r, ensure_ascii=False))
