"""배경 판의 방 구조를 3D 상자 모형으로 세우고 판 위 경계에 맞춘 뒤, 보이는 모서리만 2D 선으로 투영한다(11-05 사용자:
"배경은 3D 써도 상관없다. 방 구조를 3D화하되 기둥 같은 건 포함, 사물(판자·블록)은 뺀다").

좌표: 카메라 원점, X 오른쪽, Y 바닥에서의 높이(카메라 높이 1), Z 앞쪽 깊이. 1점 투시(카메라 축 = 통로 방향)라
투시점 = 주점(cx, cy), u = cx + F·X/Z, v = cy + F·(1 − Y)/Z. 카메라가 평행 이동만 하는 컷이라 F는 결과 그림에
영향이 없어 고정한다(깊이 단위만 바뀜).
사용: PL_SP=<scratch> python room3d.py fit|show   → <scratch>/slice/room3d/ 에 params.json, lines.json, 확인 그림.
비공개 scratch 전용(판 그림은 저장소에 넣지 않는다)."""
import json, math, os, sys
import cv2, numpy as np

F = 1000.0
SP = os.environ.get('PL_SP', '')
OUT = os.path.join(SP, 'slice', 'room3d')

# 초기값: 판 그림을 눈으로 읽은 값(왼쪽 큰 기둥·오른쪽 벽기둥 바닥 v≈390 → Z≈11.2, 다음 줄 v≈340 → Z≈25.6 등)
P0 = dict(cx=724.0, cy=301.0, Xr=4.22, Xl=-5.08, Hc=3.38, Zb=90.0,
          pz0=11.2, ps=14.4, pw=0.62, pd=0.78, pin=0.0,      # 왼쪽 기둥: 첫 깊이·간격·X폭·Z폭·통로 쪽 돌출
          rp=0.45, rw=0.5,                                   # 오른쪽 벽기둥: 돌출·Z폭
          bd=0.22, bw=0.5,                                   # 가로보: 깊이(아래로)·Z폭
          lx1=-1.8, lx2=1.0, lbw=0.5, lbd=0.3,               # 세로보 두 줄: X 위치·폭·깊이
          dz0=18.5, dz1=22.7, dy=2.22)                        # 왼벽 출입구(첫 칸): Z 구간·윗변 높이
NPIL = 6
MID = os.environ.get('ROOM_MID', '0') == '1'
OUT = os.path.join(SP, 'slice', 'room3d' + os.environ.get('ROOM_TAG', ''))


def boxes(p):
    """(이름, 종류, x0, x1, y0, y1, z0, z1). 바닥·천장·벽도 얇은 상자. 사물은 넣지 않는다."""
    Zn, Zb, Xr, Xl, Hc = 1.2, p['Zb'], p['Xr'], p['Xl'], p['Hc']
    B = [('floor', 'room', -60, Xr, -0.05, 0.0, Zn, Zb),
         ('ceiling', 'room', -60, Xr, Hc, Hc + 0.05, Zn, Zb),
         ('wall_r', 'room', Xr, Xr + 0.05, 0.0, Hc, Zn, Zb),
         ('wall_back', 'room', Xl, Xr, 0.0, Hc, Zb, Zb + 0.05),
         ('wall_l', 'room', Xl - 0.05, Xl, 0.0, Hc, p['pz0'] + p['pd'], Zb)]
    for i in range(NPIL):
        z = p['pz0'] + i * p['ps']
        if z + p['pd'] >= Zb: break
        B.append((f'pillar_l{i}', 'pillar', Xl - p['pw'], Xl + p['pin'], 0.0, Hc, z, z + p['pd']))
        B.append((f'pillar_r{i}', 'pillar', Xr - p['rp'], Xr, 0.0, Hc, z, z + p['rw']))
        B.append((f'beam_t{i}', 'beam', Xl, Xr, Hc - p['bd'], Hc, z, z + p['bw']))
        if MID and z + p['ps'] / 2 + p['bw'] < Zb:   # 기둥 사이 중간 가로보(ROOM_MID=1)
            zm = z + p['ps'] / 2
            B.append((f'beam_m{i}', 'beam', Xl, Xr, Hc - p['bd'], Hc, zm, zm + p['bw']))
    for k in ('lx1', 'lx2'):
        B.append((f'beam_{k}', 'beam', p[k] - p['lbw'] / 2, p[k] + p['lbw'] / 2, Hc - p['lbd'], Hc, Zn, Zb))
    return B


def door_edges(p):
    """왼벽 출입구 윤곽(벽 면 위 사각형, 구멍은 뚫지 않음)."""
    x, a, b, t = p['Xl'], p['dz0'], p['dz1'], p['dy']
    pts = [(x, 0, a), (x, t, a), (x, t, b), (x, 0, b)]
    return [(pts[i], pts[i + 1]) for i in range(3)]


def proj(p, P):
    X, Y, Z = P
    return p['cx'] + F * X / Z, p['cy'] + F * (1 - Y) / Z


FACES = [  # 상자 면: (축, 쪽, 꼭짓점 순서용 나머지 두 축)
    (0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]


def box_faces(b):
    _, _, x0, x1, y0, y1, z0, z1 = b
    lo, hi = (x0, y0, z0), (x1, y1, z1)
    out = []
    for ax, side in FACES:
        o = [i for i in range(3) if i != ax]
        c = (lo, hi)[side][ax]
        quad = []
        for s, t in ((0, 0), (1, 0), (1, 1), (0, 1)):
            P = [0, 0, 0]; P[ax] = c; P[o[0]] = (lo, hi)[s][o[0]]; P[o[1]] = (lo, hi)[t][o[1]]
            quad.append(tuple(P))
        n = [0, 0, 0]; n[ax] = 1 if side else -1
        front = (np.dot(n, quad[0]) < 0)          # 카메라(원점)를 향한 면
        out.append((quad, n, c, ax, front))
    return out


def zbuffer(p, B, W, H):
    zb = np.full((H, W), np.inf, np.float32)
    uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    rx, ry = (uu - p['cx']) / F, -(vv - p['cy']) / F       # 광선 방향 (rx, 1 + ry·?, 1): Y = 1 + ry·Z
    for b in B:
        for quad, n, c, ax, front in box_faces(b):
            if not front: continue
            pts = np.array([proj(p, q) for q in quad], np.float64)
            if not np.all(np.isfinite(pts)): continue
            pts = np.clip(pts, -1e5, 1e5).astype(np.int32)
            m = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(m, pts, 1)
            ys, xs = np.nonzero(m)
            if not len(ys): continue
            if ax == 2: z = np.full(len(ys), c, np.float32)
            elif ax == 0: z = c / rx[ys, xs]
            else: z = (c - 1) / ry[ys, xs]
            z = np.where(z > 0, z, np.inf)
            zb[ys, xs] = np.minimum(zb[ys, xs], z)
    return zb


def edges3d(p, B):
    """상자 모서리 중 앞을 향한 면에 닿은 것 + 출입구. (P, Q, 종류)"""
    E = []
    for b in B:
        name, kind = b[0], b[1]
        fs = box_faces(b)
        _, _, x0, x1, y0, y1, z0, z1 = b
        lo, hi = (x0, y0, z0), (x1, y1, z1)
        for ax in range(3):
            o = [i for i in range(3) if i != ax]
            for s in (0, 1):
                for t in (0, 1):
                    P = [0, 0, 0]; Q = [0, 0, 0]
                    P[ax], Q[ax] = lo[ax], hi[ax]
                    P[o[0]] = Q[o[0]] = (lo, hi)[s][o[0]]; P[o[1]] = Q[o[1]] = (lo, hi)[t][o[1]]
                    adj = [f for f in fs if (f[3] == o[0] and f[2] == P[o[0]]) or (f[3] == o[1] and f[2] == P[o[1]])]
                    if any(f[4] for f in adj): E.append((tuple(P), tuple(Q), kind))
    E += [(a, b, 'detail') for a, b in door_edges(p)]
    return E


def visible_segments(p, E, zb, W, H, step=2.0, tol=0.03):
    """모서리를 화면에서 촘촘히 샘플해 깊이 버퍼보다 앞(허용 3%)인 구간만 남긴다."""
    segs = []
    for P, Q, kind in E:
        P, Q = np.array(P, float), np.array(Q, float)
        a, b = proj(p, P), proj(p, Q)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = int(min(max(L / step, 2), 4000))
        ts = np.linspace(0, 1, n)
        # 깊이 보간은 3D에서(투영은 비선형)
        X = P[None] + (Q - P)[None] * ts[:, None]
        u = p['cx'] + F * X[:, 0] / X[:, 2]; v = p['cy'] + F * (1 - X[:, 1]) / X[:, 2]
        ins = (u >= 0) & (u < W) & (v >= 0) & (v < H)
        ui, vi = np.clip(u.astype(int), 0, W - 1), np.clip(v.astype(int), 0, H - 1)
        # 이웃 3×3 최소 깊이(모서리 화소가 옆 면 깊이를 보는 문제 완화)
        zmin = np.full(n, np.inf)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                zmin = np.minimum(zmin, zb[np.clip(vi + dy, 0, H - 1), np.clip(ui + dx, 0, W - 1)])
        vis = ins & (X[:, 2] <= zmin * (1 + tol) + 0.05)
        i = 0
        while i < n:
            if not vis[i]: i += 1; continue
            j = i
            while j + 1 < n and vis[j + 1]: j += 1
            if j > i:
                segs.append(((float(u[i]), float(v[i])), (float(u[j]), float(v[j])), kind, float(X[i, 2]), float(X[j, 2])))
            i = j + 1
    return [s for s in segs if math.hypot(s[0][0] - s[1][0], s[0][1] - s[1][1]) >= 6]


def evidence(plate):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    gray = cv2.GaussianBlur(cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    ed = cv2.Canny(gray, 20, 60) > 0
    la_p = os.path.join(OUT, 'lineart.png')
    if os.path.exists(la_p):
        ed |= cv2.imread(la_p, 0) < 180
    dt = cv2.distanceTransform((~ed).astype(np.uint8), cv2.DIST_L2, 3)
    return ed, dt


def score(p, dt, W, H):
    B = boxes(p)
    zb = zbuffer(p, B, W, H)
    S = visible_segments(p, edges3d(p, B), zb, W, H, step=4.0)
    tot, n = 0.0, 0
    for a, b, k, *_ in S:
        L = math.hypot(b[0] - a[0], b[1] - a[1]); m = max(int(L / 4), 2)
        us = np.linspace(a[0], b[0], m); vs = np.linspace(a[1], b[1], m)
        d = np.minimum(dt[np.clip(vs.astype(int), 0, H - 1), np.clip(us.astype(int), 0, W - 1)], 12.0)
        tot += float(d.sum()); n += m
    return tot / max(n, 1), S


COLK = {'room': (0, 0, 255), 'pillar': (0, 150, 0), 'beam': (200, 0, 200), 'detail': (0, 140, 255)}


def draw(plate, S, path, extra=''):
    ov = plate.copy(); wb = np.full_like(plate, 255)
    for a, b, k, *r in S:
        w2 = max(1, int(round(2 * r[0]))) if len(r) == 1 else 2   # 굵기 조각이면 굵기 비례
        for im, w in ((ov, 1), (wb, w2)):
            cv2.line(im, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), COLK[k], w, cv2.LINE_AA)
    if extra: cv2.putText(wb, extra, (8, 24), 0, 0.7, (0, 0, 0), 2)
    cv2.imwrite(path, np.vstack([ov, wb]))


def thickness_pieces(S, zref, t0=1.0, step=1.1, t_min=0.1, t_max=8.0):
    """거리에 따른 굵기(11-05 사용자, 스틱맨 거리 굵기와 같은 원근 규칙): 굵기 = t0 × zref / Z.
    기준 zref = 왼쪽 맨 앞 기둥 앞면 깊이(사용자 지정), t0 = 1.0(앱 기본 굵기). 앱은 객체마다 굵기 하나라
    깊이가 변하는 선은 깊이 비 step(10%)마다 조각으로 나누고 조각 가운데 깊이(기하 평균)로 굵기를 준다."""
    out = []
    for a, b, k, za, zb in S:
        n = max(1, int(math.ceil(abs(math.log(zb / za)) / math.log(step))))
        for i in range(n):
            t0_, t1_ = i / n, (i + 1) / n
            # 3D 깊이 보간: 화면 위 비율 s에서 1/Z가 선형
            def at(t):
                return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            iz0 = 1 / za + (1 / zb - 1 / za) * t0_; iz1 = 1 / za + (1 / zb - 1 / za) * t1_
            zm = 1 / math.sqrt(iz0 * iz1)
            out.append((at(t0_), at(t1_), k, float(np.clip(t0 * zref / zm, t_min, t_max))))
    return out


def export(p, S):
    """판 좌표 선(굵기 조각) → 장마다 판 위치만큼 옮긴 SFA. 배경 객체 ID는 모든 장에서 같고 점 ID는 장마다 새로.
    스틱맨은 기존 SFA에서 복사(plate.py와 같은 방식)."""
    import copy, zipfile, xml.etree.ElementTree as ET
    sys.path.insert(0, os.path.join(SP, 'scripts'))
    meta = json.load(open(os.path.join(SP, 'slice', 'plate', 'plate_meta.json')))
    off = {int(k): v for k, v in meta['offsets'].items()}
    OUTF = [int(v) for v in os.environ.get('ROOM_FRAMES', '1042,1062,1072,1102,1122').split(',')]
    import perspective_lines as PL
    W, H = 960, 540
    LAY = ((0, 'background.room'), (1, 'background.pillar'), (2, 'background.ceiling_beam'), (3, 'background.opening'), (6, 'actor.stickman'))
    LID = {'room': 0, 'pillar': 1, 'beam': 2, 'detail': 3}
    seq = ET.Element('Sequence', dict(Name='sfa_slice_room3d_v1', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount=str(len(OUTF)), BackgroundColor='-1'))
    for pos, f in enumerate(OUTF):
        fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
        for lid, nm in LAY:
            ET.SubElement(fr, 'LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked='false'))
        pid = 1 + pos * 100000
        dx, dy = off[f]
        for oid, (a, b, k, th) in enumerate(S, start=1):
            ao = ET.SubElement(fr, 'AO', dict(ID=str(oid), TypeId='1', Color='-12566464', LayerId=str(LID[k]), DrawOrder=str(oid),
                                              ThicknessScale=f'{th:.3f}', ObjectScale='1.0', GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0'))
            for i, (x, y) in enumerate((a, b)):
                ET.SubElement(ao, 'AP', dict(ID=str(pid), Flags=('9', '8')[i], Index=str(i), X=f'{(x - dx) / W * 100:.3f}', Y=f'{(y - dy) / H * 100:.3f}')); pid += 1
        m = {}
        for ao in PL.sroot.findall('Frame')[f - 432].findall('AO'):
            ao = copy.deepcopy(ao); ao.set('LayerId', '6')
            for ap in ao.iter('AP'): m[ap.get('ID')] = str(pid); ap.set('ID', str(pid)); pid += 1
            fr.append(ao)
        for ac in fr.iter('AC'): ac.set('ConnPtId', m.get(ac.get('ConnPtId'), ac.get('ConnPtId')))
    path = os.path.join(OUT, 'sfa_slice_room3d_v1.sfa')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('sfa_slice_room3d_v1.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
    # 확인 그림: SFA 렌더(굵기 포함) + 원본 겹침
    import sfa_render as R
    R.PARAMS.update(pad=0.0, thick_mul=1.0)
    rows = []
    for pos, f in enumerate(OUTF):
        fr = seq.findall('Frame')[pos]
        rend = cv2.cvtColor(R.render_frame(seq, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
        PL.B.set(1, f + 7); ok, im = PL.B.read(); im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
        dx, dy = off[f]; ov = im.copy()
        for a, b, k, th in S:
            cv2.line(ov, (int(a[0] - dx), int(a[1] - dy)), (int(b[0] - dx), int(b[1] - dy)), (0, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(rend, f'orig {f}', (6, 28), 0, 0.8, (0, 0, 255), 2)
        rows.append(np.hstack([ov, rend]))
    cv2.imwrite(os.path.join(OUT, 'room3d_frames.png'), cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5))
    print('SFA', path, '배경 객체', len(S), '장', OUTF)


def main():
    os.makedirs(OUT, exist_ok=True)
    plate = cv2.imread(os.path.join(SP, 'slice', 'plate', 'plate.png'))
    H, W = plate.shape[:2]
    ed, dt = evidence(plate)
    pp = os.path.join(OUT, 'params.json')
    p = dict(P0)
    if os.path.exists(pp) and sys.argv[1:2] != ['reset']: p.update(json.load(open(pp)))
    s0, S = score(p, dt, W, H)
    print('초기 평균 거리', round(s0, 2), '선', len(S))
    if sys.argv[1:2] in (['fit'], ['reset']):
        from scipy.optimize import minimize
        groups = [['cx', 'cy'], ['Xr', 'Hc'], ['Xl', 'pz0', 'ps'], ['pw', 'pd', 'pin', 'rp', 'rw'], ['bd', 'bw'],
                  ['lx1', 'lx2', 'lbw', 'lbd'], ['dz0', 'dz1', 'dy'], ['Zb']]
        # 범위 제한(11-05): 범위가 없으면 맞추기 어려운 구조물을 숨겨(보 깊이 음수 등) 평균 거리를 낮추는 퇴화가 생겼다.
        BND = dict(cx=(P0['cx'] - 30, P0['cx'] + 30), cy=(P0['cy'] - 20, P0['cy'] + 20), Xr=(3.5, 5.0), Xl=(-6.0, -4.5), Hc=(3.0, 3.8),
                   pz0=(10.0, 12.5), ps=(12.0, 17.0), pw=(0.3, 1.2), pd=(0.4, 1.2), pin=(-0.1, 0.4), rp=(0.2, 0.8), rw=(0.3, 1.0),
                   bd=(0.1, 0.5), bw=(0.3, 1.0), lx1=(-2.5, -1.0), lx2=(0.3, 1.8), lbw=(0.3, 0.9), lbd=(0.15, 0.5),
                   dz0=(17.0, 21.0), dz1=(21.0, 24.0), dy=(1.8, 2.8), Zb=(60.0, 120.0))
        for rnd in range(int(os.environ.get('ROOM_ROUNDS', 1))):
            for g in groups:
                x0 = np.array([p[k] for k in g])
                def f(x):
                    q = dict(p); q.update(zip(g, x))
                    return score(q, dt, W, H)[0]
                r = minimize(f, x0, method='Powell', bounds=[BND[k] for k in g], options=dict(maxiter=150, xtol=1e-3, ftol=1e-3))
                p.update(zip(g, map(float, r.x)))
                print(rnd, g, round(r.fun, 3), flush=True)
        json.dump(p, open(pp, 'w'), indent=1)
    s1, S = score(p, dt, W, H)
    B = boxes(p); zb = zbuffer(p, B, W, H)
    S = visible_segments(p, edges3d(p, B), zb, W, H, step=1.0)
    print('최종 평균 거리', round(s1, 2), '선', len(S), {k: round(v, 3) for k, v in p.items()})
    T = thickness_pieces(S, zref=p['pz0'])
    json.dump(dict(zref=p['pz0'], lines=[[list(a), list(b), k, th] for a, b, k, th in T]), open(os.path.join(OUT, 'lines.json'), 'w'))
    draw(plate, T, os.path.join(OUT, 'room3d_fit.png'), f'mean edge dist {s1:.2f}px  lines {len(S)} pieces {len(T)}')
    print('굵기 조각', len(T), '굵기 범위', round(min(t[3] for t in T), 2), round(max(t[3] for t in T), 2))
    if sys.argv[1:2] in (['export'], ['fit'], ['reset']):
        export(p, T)


if __name__ == '__main__':
    main()
