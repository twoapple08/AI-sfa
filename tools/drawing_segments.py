"""대상 인물의 '그림 구간 **후보**'(같은 작화가 유지되는 연속 장 후보)를 나누고 후보 대표 장을 고른다.

2판(11-02, GPT 6차 반영):
- 출력은 자동 **후보**다(candidate_*). 확인 전에는 한 포즈 복사에 쓰지 않는다.
- --verified 확인 파일(사람·AI 원본 판정)을 주면 확인 경계를 반영한 verified_segments를 따로 낸다.
  구간 안의 모든 인접 쌍이 '같음'으로 확인된 구간만 pose_copy_ok=True. 복사 가능한 것은 루트 기준 상대 포즈뿐이고,
  화면 루트 위치·전역 배율은 장별 관측을 유지한다.
- 색 마스크가 비어 계산이 안 된 쌍은 mask_none_pairs(마스크 없음)다. 대상 부재로 확정하지 않는다.
- 반례(기록): B 325–333은 파란 마스크로 한 후보 구간(경계 점수 0.283·0.255 < 0.3)이었으나, 원본 확인 결과
  325–327 / 328–330 / 331–333 세 그림이었다.

- 대상 마스크: HSV 채도 마스크 중 대상 색(blue / red / any). 인물이 둘이면 대상 색을 지정한다.
- 인접 장 변화 = 평행 이동 정렬 뒤 대상 실루엣 XOR/합집합(tools/anime_char_hold.py와 같은 계산).
- 변화 ≥ 높은 문턱(기본 0.3) → 새 그림 시작. 낮은 문턱(0.1)~높은 문턱 사이는 '애매'로 표시하고 확인 대상으로 둔다.
  애매한 쌍은 구간을 나누지 않지만 목록으로 낸다(라벨 확인용). 마스크 없음(None)은 구간을 끊는다(대상 부재 확정 아님).
- 장 번호는 0부터 시작하는 디코딩 순서다. 경계 번호 = '새 그림의 첫 장'.
- 범위 시작·끝에서 잘린 구간은 partial=True로 표시한다(범위 밖에서 시작하거나 끝날 수 있음).
- 대표 장 = 각 구간의 첫 장. 대표 장 외에 접촉·가림·좌우 교차·대상 배정 경계 장은 라벨러가 따로 추가한다.

사용: python tools/drawing_segments.py 영상 시작장 끝장 [--color blue|red|any] [--hi 0.3] [--lo 0.1] [--verified 확인.json]
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
    last = a + len(masks) - 1
    out = [{'first': s0, 'last': s1, 'len': s1 - s0 + 1, 'partial': s0 == a or s1 == last} for s0, s1 in segs]
    return {'range': [a, last], 'color': color, 'hi': hi, 'lo': lo,
            'candidate_segments': out, 'candidate_representatives': [s['first'] for s in out],
            'ambiguous_pairs': amb, 'mask_none_pairs': [a + i for i, c in enumerate(ch) if c is None]}

def check_verified(ver, video_sha256=None, color=None):
    """확인 파일 바인딩·모순 검사(GPT 7차). 문제가 있으면 ValueError."""
    errs = []
    if video_sha256 is not None and ver.get('video_sha256') != video_sha256:
        errs.append('영상 SHA-256 불일치')
    tgt = ver.get('target_color')
    if color is not None and tgt != color:   # GPT 8차: 대상 색을 검사하는 호출에서는 필드가 없어도 거부
        errs.append(f'대상 색 불일치 또는 누락({tgt} ≠ {color})')
    # GPT 8차: 장 번호 규칙은 설명 문자열이 아니라 기계 판독 필드로 검사한다(누락도 거부).
    if ver.get('frame_index_base') != 0 or ver.get('frame_order') != 'decode':
        errs.append('장 번호 규칙 필드(frame_index_base: 0, frame_order: decode) 누락 또는 불일치')
    b, nb = set(ver.get('boundaries', [])), set(ver.get('not_boundaries', []))
    if b & nb:
        errs.append(f'경계이면서 비경계: {sorted(b & nb)}')
    for f0, f1 in ver.get('same_pairs', []):
        if f1 != f0 + 1:
            errs.append(f'같음 쌍이 인접 쌍이 아님: {[f0, f1]}')
        if f1 in b:
            errs.append(f'같음 쌍인데 뒤 장이 새 그림 첫 장: {[f0, f1]}')
    if errs:
        raise ValueError('; '.join(errs))

def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''):
            h.update(ch)
    return h.hexdigest()

def apply_verified(res, ver):
    """확인 파일: {'video_sha256', 'target_color', 'boundaries':[새 그림 첫 장...], 'not_boundaries':[...], 'same_pairs':[[f,f+1],...]}
    호출 전에 check_verified로 바인딩·모순을 검사한다(CLI는 자동으로 한다)."""
    a, last = res['range']
    starts = {s['first'] for s in res['candidate_segments']}
    vb = {f for f in ver.get('boundaries', []) if a < f <= last}
    nb = {f for f in ver.get('not_boundaries', []) if a < f <= last}
    starts = sorted((starts | vb) - nb)
    same = {tuple(x) for x in ver.get('same_pairs', [])}
    segs = []
    for i, s0 in enumerate(starts):
        s1 = (starts[i + 1] - 1) if i + 1 < len(starts) else last
        pairs = [(f, f + 1) for f in range(s0, s1)]
        ok = all(p in same for p in pairs) and (s0 == s1 or bool(pairs))
        segs.append({'first': s0, 'last': s1, 'len': s1 - s0 + 1, 'partial': s0 == a or s1 == last,
                     'pose_copy_ok': bool(ok and s1 > s0), 'verified_boundary': s0 in vb})
    res['verified_source'] = ver.get('source')
    res['verified_boundaries_added'] = sorted(vb - {s['first'] for s in res['candidate_segments']})
    res['verified_segments'] = segs
    return res

if __name__ == '__main__':
    args = sys.argv[1:]
    opt = lambda k, d: type(d)(args[args.index(k) + 1]) if k in args else d
    r = segments(args[0], int(args[1]), int(args[2]), opt('--color', 'any'), opt('--hi', 0.3), opt('--lo', 0.1))
    if '--verified' in args:
        ver = json.load(open(args[args.index('--verified') + 1], encoding='utf-8'))
        check_verified(ver, sha256(args[0]), opt('--color', 'any'))   # 해시·대상·모순이 안 맞으면 멈춘다
        r = apply_verified(r, ver)
    print(json.dumps(r, ensure_ascii=False))
