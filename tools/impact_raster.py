"""나카무라식 임팩트 프레임 래스터 설계(잉크 농도 0=흰, 1=검정, 960x540). make_cube가 반투명 단계 곡선으로 바꿔 SFA에 넣는다.
대상(큐브)·빛 폭발·마른 붓 결로만 구성하고 파편은 넣지 않는다."""
import math, numpy as np, cv2
RW, RH = 960, 540
Y, X = np.mgrid[0:RH, 0:RW].astype(np.float32)

def ang_noise(rng, n, freqs=((2000, 1.0), (500, .6), (120, .35), (30, .25))):
    """각도 방향 고주파 줄무늬 노이즈(0..1): 붓·연필 결."""
    out = np.zeros(n, np.float32)
    for k, w in freqs:
        v = rng.random(k + 1).astype(np.float32)
        out += w * np.interp(np.linspace(0, k, n), np.arange(k + 1), v)
    out -= out.min(); out /= out.max() + 1e-6
    return out

def polar(c, sy=1.0):
    dx, dy = X - c[0], (Y - c[1]) / sy
    return np.hypot(dx, dy), np.arctan2(dy, dx)

def sample(arr, th):
    n = len(arr)
    i = ((th + math.pi) / (2 * math.pi) * (n - 1)).astype(np.int32)
    return arr[np.clip(i, 0, n - 1)]

def streak_tex(rng, c, th_bins=3000, sy=1.0):
    """방사 방향 결: 각도별 값 + 반지름 방향 저주파로 끊김."""
    r, th = polar(c, sy)
    a = sample(ang_noise(rng, th_bins), th)
    b = sample(ang_noise(rng, th_bins, ((800, 1.0), (200, .5))), th)
    seg = 0.5 + 0.5 * np.sin(r / (40 + 60 * b) + b * 20)          # 결 끊김
    return a, seg, r, th

def lin_tex(rng, ang, n=3000):
    """평행 방향 결(스미어)."""
    u = X * math.cos(ang + math.pi / 2) + Y * math.sin(ang + math.pi / 2)
    v = ang_noise(rng, n)
    i = ((u - u.min()) / (u.max() - u.min()) * (n - 1)).astype(np.int32)
    return v[i]

def poly_mask(pts, scale=.5):
    m = np.zeros((RH, RW), np.uint8)
    cv2.fillPoly(m, [np.round(np.array(pts) * scale).astype(np.int32)], 1)
    return m.astype(np.float32)

def smear(mask, c, rng, amt=60, sy=1.0):
    """마스크를 바깥 방향으로 각도별 다른 길이만큼 끌어내 털·결이 있는 가장자리."""
    r, th = polar(c, sy)
    L = sample(ang_noise(rng, 2500), th) ** 2 * amt
    out = mask.copy()
    for k in np.linspace(0, 1, 10):
        d = L * k
        sx = (X - c[0]) / (r + 1e-3) * d; syy = (Y - c[1]) / (r + 1e-3) * d
        mx = cv2.remap(mask, (X - sx).astype(np.float32), (Y - syy).astype(np.float32), cv2.INTER_LINEAR)
        out = np.maximum(out, mx * (1 - k * .5))
    return out

def burst(c, R, rng, sx=1.2, sy=.85, spread=.55):
    """가는 결로 이루어진 빛 폭발(1=빛): 경계가 수천 개 가는 줄로 갈라짐."""
    r, th = polar(c, 1.0)
    rr = np.hypot((X - c[0]) / sx, (Y - c[1]) / sy)
    a = sample(ang_noise(rng, 3000), th)
    edge = R * (1 + spread * (a ** 1.6) * 2.2)
    return np.clip((edge - rr) / (R * .25) + .5, 0, 1)

def dry(mask, c, rng, amt, gap=.55):
    """마른 붓: 털처럼 바깥으로 끌린 가장자리 + 덩어리 안 결 사이 흰 틈."""
    m = smear(mask, c, rng, amt)
    a, seg, r, th = streak_tex(rng, c)
    edge = cv2.GaussianBlur(mask, (0, 0), 6)
    inner_gap = (a > gap + .4 * edge) * (seg > .45)            # 가장자리 쪽일수록 틈 많음
    return np.clip(m * (1 - inner_gap * .85), 0, 1)

def edge_field(rng, c, r0, sy=.85, var=.9):
    """화면 가장자리에서 중심 쪽으로 파고드는 마른 붓 검정(빛이 먹은 자리가 결로 갈라짐)."""
    r, th = polar(c, sy)
    a = sample(ang_noise(rng, 3000), th)
    b = sample(ang_noise(rng, 600, ((600, 1.0), (60, .7))), th)
    reach = r0 * (1 + var * (a ** 1.8) + .35 * b)
    return np.clip((r - reach) / 30, 0, 1)

def compose(k, sub, cam, faces):
    rng = np.random.default_rng(3000 + k * 17 + sub * 5)
    top, right, front = faces
    c = np.array(cam(0, 0, 1.2)) * .5
    ct = np.mean(np.array(top), 0) * .5
    T, Rt, F = poly_mask(top), poly_mask(right), poly_mask(front)
    cube = np.maximum(np.maximum(T, Rt), F)
    sides = np.maximum(Rt, F)
    if k == 0:   # IF1 어둠 속 큐브: 흰 윗면, 털처럼 번진 검은 옆면, 가장자리에서 빛을 먹어 들어오는 검정
        ink = edge_field(rng, c, 230, var=1.3)
        ink = np.maximum(ink, dry(sides, c, rng, 70, .7))
        ink *= 1 - T
        ink = np.maximum(ink, dry(T * 0 + (1 - cube) * 0, c, rng, 1))
    elif k == 1: # IF2 반전: 흰 화면, 검은 큐브가 바깥으로 털처럼 번짐, 윗면에서 빛
        ink = dry(cube, c, rng, 280, .6)
        ink = np.maximum(ink, edge_field(rng, c, 470, var=.8) * .95)
        ink *= 1 - burst(ct, 38, rng, 1.0, 1.0, 1.5)
    elif k == 2: # IF3 큰 빛: 중심 빛이 화면을 밀어내고 검정은 결로 갈라진 가장자리만
        ink = edge_field(rng, c, 300, var=1.1) * (1 - burst(c, 190, rng, 1.3, .85, 1.2))
    elif k == 3: # IF4 실루엣 반전: 검은 화면 속 흰 큐브(옆면은 옅은 연필 톤), 빛이 윤곽에서 새어 나옴
        field = 1 - burst(c, 150, rng, 1.25, .9, 1.4) * .95
        ink = field * (1 - cube)
        ink = np.maximum(ink, sides * .4 * (lin_tex(rng, 1.1) > .35))
    elif k == 4: # IF5 사선 스미어: 검은 큐브가 사선으로 끌리며 결이 남음, 바탕엔 같은 방향 마른 붓
        ang = -.35
        t = lin_tex(rng, ang)
        m = cube.copy()
        for d in range(1, 40):
            sh = cv2.warpAffine(cube, np.float32([[1, 0, -d * 12 * math.cos(ang)], [0, 1, -d * 12 * math.sin(ang)]]), (RW, RH))
            m = np.maximum(m, sh * (t > .15 + d / 46))
        u = lin_tex(rng, ang + .015)
        bg = (u > .78).astype(np.float32) * .9
        ink = np.maximum(m, bg) * (1 - burst(ct, 50, rng, 1.6, .6, 1.4))
    else:        # IF6 풀림: 회색 결로 빛이 꺼지며 다음 컷으로(투명 단계로 옅어짐)
        ink = edge_field(rng, c, 260, var=1.0) * .75
        ink = np.maximum(ink, dry(cube, c, rng, 120, .5) * .6)
        ink *= 1 - burst(c, 150, rng, 1.3, .8, .7) * .8
    if k == 0:                                              # 흰 윗면 윤곽(4B 굵은 선, 끝이 끊김)
        o = np.zeros((RH, RW), np.float32)
        q = np.round(np.array(top) * .5).astype(np.int32)
        for i_ in range(4):
            a_, b_ = q[i_], q[(i_ + 1) % 4]
            cut = rng.uniform(.75, .95)
            cv2.line(o, tuple(int(v) for v in a_), tuple(int(v) for v in (a_ + (b_ - a_) * cut)), 1.0, 3, cv2.LINE_AA)
        ink = np.maximum(ink, o)
    ink = cv2.GaussianBlur(ink.astype(np.float32), (0, 0), .7)
    return np.clip(ink, 0, 1)
