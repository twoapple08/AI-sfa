"""포즈 자료(RTMW 133점: 0 코, 5·6 왼·오른 어깨, 11·12 왼·오른 골반)에서 장마다 몸 방향(facing)을 계산해 중간 표현에 넣는다
(가면 방향 3/3, 사용자 11-05). 스틱맨 관절 12개에는 어깨 폭·얼굴 방향이 없어 따로 구한다.

방향 정의(motion_ir): 0 정면 · 90 시트 '우측'(캐릭터가 화면 왼쪽을 봄 — 예시 시트 우측 칸의 가면이 머리 왼쪽) · 180 후면 · 270 '좌측'.
- 정면 성분 c = (왼 어깨 x − 오른 어깨 x + 왼 골반 x − 오른 골반 x) / 2 / (SHOULDER × 몸통 길이), −1..1로 자름.
  정면이면 캐릭터의 왼쪽이 화면 오른쪽이라 c > 0, 후면이면 c < 0.
- 옆 방향 부호: 코가 어깨 가운데보다 화면 왼쪽이면 '우측'(90) 쪽. 코 신뢰도가 낮으면 양 귀 가운데로.
- 각도 = atan2(옆 크기 × 부호, c). 흔들림 방지: 칸(0/90/180/270)으로 바꾼 뒤 앞뒤 2장(5장 창) 다수결, 자료 없는 장은 12장까지 앞 값 유지,
  새 칸은 4장 이상 이어질 때만 바꿈(처음 시험: 다수결만으로는 1,440장에서 154번 바뀌고 7장 안에 정면→좌측→우측→정면이 있었다).
인물 대응: 스틱맨 목과 가장 가까운 포즈의 어깨 가운데(영상 화소 = x × sx, y × sy + oy; 이 클립 sx 11.52, sy 6.48, oy 63).
"""
import gzip, json, math
from collections import Counter

L_SH, R_SH, L_HIP, R_HIP, NOSE, L_EAR, R_EAR = 5, 6, 11, 12, 0, 3, 4
MIN_SCORE = 1.0
SHOULDER = 0.5   # 정면 어깨·골반 폭 / 몸통 길이 기준(작을수록 정면 쪽 — 0.6에서 3/4 자세가 측면으로 넘어갔다)
FRONT_ZONE, BACK_ZONE = 55.0, 35.0   # 반측면 칸이 없어 3/4 자세는 정면으로(정면 ±55°, 후면 ±35°, 나머지 측면)


def load_rtmw(path):
    R = {}
    for line in gzip.open(path, 'rt'):
        r = json.loads(line)
        R[int(r['f'])] = [p['k'] for p in r['p']]
    return R


def yaw_of(k):
    """한 사람 키포인트 → 방향(도) 또는 None."""
    if min(k[i][2] for i in (L_SH, R_SH, L_HIP, R_HIP)) < MIN_SCORE:
        return None
    sh = ((k[L_SH][0] + k[R_SH][0]) / 2, (k[L_SH][1] + k[R_SH][1]) / 2)
    hp = ((k[L_HIP][0] + k[R_HIP][0]) / 2, (k[L_HIP][1] + k[R_HIP][1]) / 2)
    T = math.dist(sh, hp)
    if T < 1e-6:
        return None
    dx = ((k[L_SH][0] - k[R_SH][0]) + (k[L_HIP][0] - k[R_HIP][0])) / 2
    c = max(-1.0, min(1.0, dx / (SHOULDER * T)))
    if k[NOSE][2] >= MIN_SCORE:
        s = k[NOSE][0] - sh[0]
    elif min(k[L_EAR][2], k[R_EAR][2]) >= MIN_SCORE:
        s = (k[L_EAR][0] + k[R_EAR][0]) / 2 - sh[0]
    else:
        s = 0.0
    side = math.sqrt(max(0.0, 1 - c * c)) * (1 if s < 0 else -1)
    return math.degrees(math.atan2(side, c)) % 360


def to_view(a):
    if a is None: return None
    d = lambda t: min(abs(a - t) % 360, 360 - abs(a - t) % 360)
    if d(0) <= FRONT_ZONE: return 0.0
    if d(180) <= BACK_ZONE: return 180.0
    return 90.0 if d(90) < d(270) else 270.0


def debounce(views, need=4):
    """새 칸이 need장 이상 이어질 때만 바꾼다(포즈 추정 흔들림으로 칸이 왔다 갔다 하는 것 방지)."""
    out, cur = [], None
    for i, v in enumerate(views):
        if v != cur and (cur is None or all(x == v for x in views[i:i + need])):
            cur = v
        out.append(cur)
    return out


def smooth(views, win=2, hold=12):
    out, last, gap = [], None, 0
    for i in range(len(views)):
        w = [v for v in views[max(0, i - win):i + win + 1] if v is not None]
        if w:
            last, gap = Counter(w).most_common(1)[0][0], 0
            out.append(last)
        else:
            gap += 1
            out.append(last if gap <= hold else None)
    return out


def apply(ir, R, frame0, sx=11.52, sy=6.48, oy=63.0, max_dist=120.0):
    """ir에 장별 facing을 채운다. frame0 = ir 0장의 원본 장 번호. 반환: 인물별 {raw 칸 분포, 최종 분포}."""
    rep = {}
    for a in ir['actors']:
        raw = []
        for n in range(ir['frames']):
            nk = a['joints']['neck'][n]
            if nk is None:
                raw.append(None); continue
            px = (nk[0] * sx, nk[1] * sy + oy)
            best, bd = None, max_dist
            for k in R.get(frame0 + n, []):
                if min(k[L_SH][2], k[R_SH][2]) < MIN_SCORE: continue
                m = ((k[L_SH][0] + k[R_SH][0]) / 2, (k[L_SH][1] + k[R_SH][1]) / 2)
                d = math.dist(px, m)
                if d < bd: best, bd = k, d
            raw.append(to_view(yaw_of(best)) if best else None)
        fin = debounce(smooth(raw))
        a['facing'] = fin
        rep[a['slot']] = dict(raw=dict(Counter(raw)), final=dict(Counter(fin)),
                              switches=sum(1 for x, y in zip(fin, fin[1:]) if x != y))
    return rep
