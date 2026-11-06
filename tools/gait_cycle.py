"""애니메이션 원리로 걷기·달리기 주기 만들기(11-06 사용자 '추천대로', 걷기 출처 선택 1).

배경: 사용자 블라인드 판정(rekan_ABC)에서 어느 판도 '걷기라 부를 수 있는 것'이 없었다. 수집 SFA 걷기 조각은 13장 안팎으로 짧고 보폭이 작고,
HMDB 걷기는 카메라 쪽으로 걸어오는 것이 많다. 그래서 걷기·달리기는 실제 조각 대신 애니메이터의 표준 걸음 구조로 계산해 만든다.
**학습한 결과가 아니다**(계산 생성). 사용자가 직접 그린 주기를 주면 그것으로 바꿔 끼운다(선택 2).

구조(옆모습, 오른쪽을 향해 걷는다 — 방향은 finalize의 facing으로 바꾼다)
- 한 주기 = 두 걸음. 다리마다 위상 φ∈[0,1): [0, duty)는 지지(발이 땅에 고정 — 미끄러짐 0), [duty, 1)은 들어 옮기기(발이 다음 디딜 곳까지
  호를 그리며 이동, 가운데서 가장 높이). 두 다리는 반 주기 어긋난다.
  - 걷기: duty 0.6 → 두 발 동시 지지가 있다(접지·내려앉음·지나감·올라섬의 네 열쇠 자세가 이 위상에서 나온다).
  - 달리기: duty 0.35 → 두 발이 모두 뜨는 체공이 있다(접지·내려앉음·밀어내기·체공).
- 골반은 일정 속도로 나아가고 위아래로 흔들린다(걷기: 지나감 뒤 '올라섬'이 가장 높고 접지 직후 '내려앉음'이 가장 낮음 · 달리기: 지지 가운데가 가장 낮고 체공이 가장 높음).
  달리기의 들어 옮기기는 발뒤꿈치를 먼저 차올리고(높이 봉우리를 앞당김) 발을 늦게 앞으로 보낸다(shape).
- 무릎은 엉덩이–발목 거리로 두 뼈 역기구학(무릎은 앞쪽으로 굽음). 발이 닿지 않으면 다리를 편 채로 발목 쪽으로 뻗는다.
- 몸통은 앞으로 기울임(걷기 4°, 달리기 14°), 팔은 반대쪽 다리와 함께 앞뒤로(걷기 팔꿈치 조금 굽힘, 달리기 약 90°).
비율(몸통 = 1): 허벅지 0.85·정강이 0.8·위팔 0.7·아래팔 0.62·머리 0.75 — nian41 중앙값(0.92·0.77·0.75·0.5)과 수집 SFA(0.73·0.5·0.63·0.63)
사이(조각 잇기에서 키로 다시 맞춘다).
출력: motion-ir 관절(화면 %, 골반 (50, 60)에서 시작), compose의 조각과 같은 꼴.
"""
import math

NAMES = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']
THIGH, SHIN, UARM, FARM, HEAD = 0.85, 0.8, 0.7, 0.62, 0.75
L = THIGH + SHIN

# 걸음 종류별 값(길이는 다리 길이 L 배수, 각도는 도). period = 한 주기 장 수(24장/초 기준).
PRESETS = {
    '걷기': dict(period=24, duty=0.6, stride=1.2, hip=0.9, bob=0.035, bob_peak=0.6, lift=0.12, shape=(1.0, 1.0), lean=4, arm=22, elbow=(12, 28)),
    '달리기': dict(period=16, duty=0.35, stride=2.3, hip=0.86, bob=0.06, bob_peak=0.85, lift=0.5, shape=(1.5, 0.55), lean=14, arm=45, elbow=(80, 100)),
}
# 글의 빠르기 말 → 주기·보폭 배율
SPEED = [(('천천히', '느리게', '살금'), 1.3, 0.8), (('빠르게', '급히', '서둘러'), 0.85, 1.1), (('전력', '질주', '힘껏'), 0.8, 1.2)]


def params(verb, detail=''):
    p = dict(PRESETS['달리기' if verb == '달리기' else '걷기'])
    for words, pm, sm in SPEED:
        if any(w in (detail or '') for w in words):
            p['period'] = max(8, round(p['period'] * pm)); p['stride'] *= sm
    return p


def _ease(s):
    return 0.5 - 0.5 * math.cos(math.pi * s)


def _knee(hip, ank, a, b):
    """두 뼈 역기구학: 무릎은 +x(앞)으로 굽힘. 좌표는 몸통 단위·y 아래로 증가."""
    dx, dy = ank[0] - hip[0], ank[1] - hip[1]
    d = math.hypot(dx, dy) or 1e-9
    if d >= a + b - 1e-6:   # 닿지 않음 → 편 다리로 발목을 당김
        ux, uy = dx / d, dy / d
        return [hip[0] + ux * a, hip[1] + uy * a], [hip[0] + ux * (a + b), hip[1] + uy * (a + b)]
    d = max(d, abs(a - b) + 1e-6)
    al = math.acos(max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d))))
    th = math.atan2(dy, dx)
    c1 = [hip[0] + a * math.cos(th + al), hip[1] + a * math.sin(th + al)]
    c2 = [hip[0] + a * math.cos(th - al), hip[1] + a * math.sin(th - al)]
    return (c1 if c1[0] >= c2[0] else c2), list(ank)


def _foot(phi, cyc, p, v, P):
    """다리 위상 phi(0=접지)·주기 번호 cyc → 발목 (x, 땅 위 높이). 지지 중에는 디딘 자리에 고정."""
    S = p['stride'] * L; duty = p['duty']
    plant = v * (duty / 2) * P + cyc * S   # 지지 가운데에 엉덩이 바로 아래가 되도록 디딤
    if phi < duty: return plant, 0.0
    s = (phi - duty) / (1 - duty); xp, hp = p['shape']
    # 달리기: 발뒤꿈치가 먼저 엉덩이 쪽으로 차올라(높이 봉우리가 앞당겨짐) 발이 뒤에 남았다가 앞으로 나온다(가로 진행을 늦춤)
    return plant + S * _ease(s ** xp), p['lift'] * L * math.sin(math.pi * s ** hp)


def cycle(verb='걷기', frames=None, detail='', cycles=2, scale=4.0, aspect=0.5625):
    """걷기·달리기 관절 궤적. frames를 안 주면 cycles 주기. scale = 몸통 길이(화면 % 가로 기준)."""
    p = params(verb, detail); P = p['period']; N = frames or P * cycles
    S = p['stride'] * L; v = S / P
    J = {k: [] for k in NAMES}
    for n in range(N):
        t = n
        px = v * t
        step = ((t / P) * 2) % 1.0   # 걸음 위상(한 주기 두 걸음)
        py = -(p['hip'] * L + p['bob'] * L * math.cos(2 * math.pi * (step - p['bob_peak'])))   # 땅 y=0, 위가 음수
        pel = [px, py]
        leg = {}
        for side, off in (('r', 0.0), ('l', 0.5)):
            ph_all = t / P + off   # 오른 다리: n=0에 접지
            fx, fh = _foot(ph_all % 1.0, math.floor(ph_all), p, v, P)
            if side == 'l': fx -= 0.5 * S   # 왼 다리 디딤은 반 주기(반 보폭 × 2 걸음 중 하나) 뒤
            kn, an = _knee(pel, [fx, -fh], THIGH, SHIN)
            leg[side] = (kn, an)
        lean = math.radians(p['lean'])
        neck = [pel[0] + math.sin(lean), pel[1] - math.cos(lean)]
        hb = list(neck)
        ht = [hb[0] + HEAD * math.sin(lean * 0.6), hb[1] - HEAD * math.cos(lean * 0.6)]
        arms = {}
        for side, sg in (('r', -1), ('l', 1)):   # 오른팔은 오른다리와 반대(오른다리 접지 = 앞일 때 오른팔 뒤)
            sw = sg * math.cos(2 * math.pi * t / P)   # +1 앞 · −1 뒤
            ang = math.radians(p['arm'] * sw + p['lean'] * 0.5)
            el = [neck[0] + UARM * math.sin(ang), neck[1] + UARM * math.cos(ang)]
            bend = math.radians(p['elbow'][0] + (p['elbow'][1] - p['elbow'][0]) * (0.5 + 0.5 * sw))
            fa = ang + bend   # 아래팔은 앞쪽으로 굽음
            wr = [el[0] + FARM * math.sin(fa), el[1] + FARM * math.cos(fa)]
            arms[side] = (el, wr)
        pts = dict(head_t=ht, head_b=hb, neck=neck, pelvis=pel, elb_r=arms['r'][0], wri_r=arms['r'][1], elb_l=arms['l'][0], wri_l=arms['l'][1],
                   kne_r=leg['r'][0], ank_r=leg['r'][1], kne_l=leg['l'][0], ank_l=leg['l'][1])
        for k in NAMES: J[k].append(pts[k])
    x0, y0 = J['pelvis'][0]
    out = {k: [[50 + (q[0] - x0) * scale, 60 + (q[1] - y0) * scale / aspect] for q in J[k]] for k in NAMES}
    return dict(frames=N, aspect=aspect, joints=out, period=P)


def clip(verb, detail='', need=None, cycles=2):
    """compose 조각 꼴(layer='synth'). need장 이상, 주기 단위로 끊는다."""
    p = params(verb, detail); P = p['period']
    n = max(cycles, math.ceil((need or 0) / P)) * P
    c = cycle(verb, n, detail)
    return dict(layer='synth', src=f'synth_{verb}', verb=verb, detail=detail, quality='좋음', frames=c['frames'], aspect=c['aspect'],
                joints=c['joints'])
