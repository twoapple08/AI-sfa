"""배경 판의 방 구조를 3D 상자 모형으로 세우고 판 위 경계에 맞춘 뒤, 보이는 모서리만 2D로 투영한다(11-05 사용자:
"배경은 3D 써도 상관없다. 방 구조를 3D화하되 기둥 같은 건 포함, 사물(판자·블록)은 뺀다").

좌표: 카메라 원점, X 오른쪽, Y 바닥에서의 높이(카메라 높이 1), Z 앞쪽 깊이. 1점 투시(카메라 축 = 통로 방향)라
투시점 = 주점(cx, cy), u = cx + F·X/Z, v = cy + F·(1 − Y)/Z. 카메라가 평행 이동만 하는 컷이라 F는 결과 그림에
영향이 없어 고정한다(깊이 단위만 바뀜).

v2(11-05 사용자 지적 반영):
- 선은 끝까지(색이 비슷하다고 자르지 않음): 가림을 화면 깊이 버퍼가 아니라 시선-상자 교차로 정확히 계산하고,
  면이 맞닿아 평평하게 이어지는 곳(같은 평면)만 선을 없앤다(모서리 주변 네 칸 점유로 판정).
- 가로보는 건물 폭 전체(왼쪽 열린 공간까지). 벽은 두께 있는 상자이고 문 자리를 실제로 비운다 → 문틀·문설주가 저절로.
  오른쪽 벽 문 2개 추가.
- 굵기 = 1.0 × (왼쪽 맨 앞 기둥 앞면 깊이 / 깊이). 가로·세로(X·Y축) 모서리는 깊이가 일정해 선 하나에 정확한 굵기,
  안쪽으로 뻗는(Z축) 모서리는 가까울수록 넓은 사다리꼴 채우기 면(테두리 선은 투명).
사용: PL_SP=<scratch> python room3d.py show|fit|export   → <scratch>/slice/room3d/ 에 params.json, 확인 그림, SFA.
비공개 scratch 전용(판 그림은 저장소에 넣지 않는다)."""
import json, math, os, sys
import cv2, numpy as np

F = 1000.0
SP = os.environ.get('PL_SP', '')
OUT = os.path.join(SP, 'slice', 'room3d' + os.environ.get('ROOM_TAG', ''))
APP_PX = 8 * 1.14 * 960 / 1920   # 굵기 1.0의 화면 폭(960 기준 px): 앱 1920 폭에서 8×1.14px

P0 = dict(cx=724.0, cy=301.0, Xr=4.22, Xl=-5.08, Hc=3.38, Zb=90.0,
          pz0=11.2, ps=14.4, pw=0.62, pd=0.78, pin=0.0,      # 왼쪽 기둥: 첫 깊이·간격·X폭·Z폭·통로 쪽 돌출
          rp=0.45, rw=0.5,                                   # 오른쪽 벽기둥: 돌출·Z폭
          bd=0.22, bw=0.5,                                   # 가로보: 깊이(아래로)·Z폭
          lx1=-1.8, lx2=1.0, lbw=0.5, lbd=0.3,               # 세로보 두 줄: X 위치·폭·깊이
          dz0=18.5, dz1=22.7, dy=2.22,                       # 왼벽 문(첫 칸): Z 구간·윗변 높이(문 높이는 양쪽 공통)
          rd1a=20.2, rd1b=22.7, rd2a=31.3, rd2b=35.6,        # 오른벽 문 2개(판 x 908–930, 845–860에서 읽음)
          tw=0.3)                                            # 벽 두께
NPIL = 6
XOPEN = -40.0   # 왼쪽 열린 공간 끝(화면 밖)
MID = os.environ.get('ROOM_MID', '0') == '1'


def wall_pieces(name, x0, x1, za, zb, doors, dy, Hc):
    """두께 있는 벽: 문 높이 아래는 문 사이 조각, 위는 한 띠 → 문 자리가 실제로 비고 평평한 곳엔 선이 안 생긴다."""
    B, z = [], za
    for a, b in sorted(doors):
        if a > z: B.append((f'{name}_lo{len(B)}', 'room', x0, x1, 0.0, dy, z, a))
        z = max(z, b)
    if z < zb: B.append((f'{name}_lo{len(B)}', 'room', x0, x1, 0.0, dy, z, zb))
    B.append((f'{name}_hi', 'room', x0, x1, dy, Hc, za, zb))
    return B


def boxes(p):
    """(이름, 종류, x0, x1, y0, y1, z0, z1). 바닥·천장·벽도 상자. 사물은 넣지 않는다."""
    Zn, Zb, Xr, Xl, Hc, tw = 1.2, p['Zb'], p['Xr'], p['Xl'], p['Hc'], p['tw']
    B = [('floor', 'room', XOPEN - 20, Xr + tw, -0.3, 0.0, Zn, Zb + tw),
         ('ceiling', 'room', XOPEN - 20, Xr + tw, Hc, Hc + 0.3, Zn, Zb + tw),
         ('wall_back', 'room', Xl - tw, Xr + tw, 0.0, Hc, Zb, Zb + tw)]
    B += wall_pieces('wall_r', Xr, Xr + tw, Zn, Zb, [(p['rd1a'], p['rd1b']), (p['rd2a'], p['rd2b'])], p['dy'], Hc)
    B += wall_pieces('wall_l', Xl - tw, Xl, p['pz0'] + p['pd'], Zb, [(p['dz0'], p['dz1'])], p['dy'], Hc)
    for i in range(NPIL):
        z = p['pz0'] + i * p['ps']
        if z + p['pd'] >= Zb: break
        B.append((f'pillar_l{i}', 'pillar', Xl - p['pw'], Xl + p['pin'], 0.0, Hc, z, z + p['pd']))
        B.append((f'pillar_r{i}', 'pillar', Xr - p['rp'], Xr, 0.0, Hc, z, z + p['rw']))
        B.append((f'beam_t{i}', 'beam', XOPEN, Xr, Hc - p['bd'], Hc, z, z + p['bw']))   # 건물 폭 전체
        if MID and z + p['ps'] / 2 + p['bw'] < Zb:
            zm = z + p['ps'] / 2
            B.append((f'beam_m{i}', 'beam', XOPEN, Xr, Hc - p['bd'], Hc, zm, zm + p['bw']))
    for k in ('lx1', 'lx2'):
        B.append((f'beam_{k}', 'beam', p[k] - p['lbw'] / 2, p[k] + p['lbw'] / 2, Hc - p['lbd'], Hc, Zn, Zb))
    return B


def proj(p, P):
    X, Y, Z = P
    return p['cx'] + F * X / Z, p['cy'] + F * (1 - Y) / Z


def box_arrays(B):
    lo = np.array([[b[2], b[4], b[6]] for b in B], float)
    hi = np.array([[b[3], b[5], b[7]] for b in B], float)
    return lo, hi


def occluded(Pts, lo, hi, eps=1e-4):
    """카메라(0, 1, 0)→점 선분이 점 앞(0 < s < 1)에서 어떤 상자를 지나는가(정확한 시선-상자 교차)."""
    C = np.array([0.0, 1.0, 0.0])
    D = Pts - C
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / D[:, None, :]                                     # (N,1,3)
        t1 = (lo - C)[None] * inv; t2 = (hi - C)[None] * inv          # (N,M,3)
        tmin = np.nanmax(np.minimum(t1, t2), 2); tmax = np.nanmin(np.maximum(t1, t2), 2)
    hit = (tmin < tmax - 1e-9) & (tmin < 1 - 1e-3) & (tmax > eps)
    return hit.any(1)


def occupied(Q, lo, hi):
    return ((Q[:, None, :] > lo[None]) & (Q[:, None, :] < hi[None])).all(2).any(1)


def edges3d(p, B):
    """상자 모서리마다 (P, Q, 종류, 축, n1, n2): n1·n2는 모서리에 닿은 두 면의 바깥 법선."""
    E = []
    for b in B:
        kind = b[1]
        _, _, x0, x1, y0, y1, z0, z1 = b
        lo, hi = (x0, y0, z0), (x1, y1, z1)
        for ax in range(3):
            o = [i for i in range(3) if i != ax]
            for s in (0, 1):
                for t in (0, 1):
                    P = [0, 0, 0]; Q = [0, 0, 0]
                    P[ax], Q[ax] = lo[ax], hi[ax]
                    P[o[0]] = Q[o[0]] = (lo, hi)[s][o[0]]; P[o[1]] = Q[o[1]] = (lo, hi)[t][o[1]]
                    n1 = np.zeros(3); n1[o[0]] = 1 if s else -1
                    n2 = np.zeros(3); n2[o[1]] = 1 if t else -1
                    E.append((np.array(P, float), np.array(Q, float), kind, ax, n1, n2))
    return E


def visible_segments(p, E, B, W, H, step=2.0):
    """모서리를 화면에서 촘촘히 샘플해 (1) 실제 모서리(둘레 네 칸 점유가 평면이 아님) (2) 가려지지 않음 (3) 화면 안
    인 구간만 남긴다. 반환 (a, b, 종류, Za, Zb, 축)."""
    lo, hi = box_arrays(B)
    segs, e = [], 2e-3
    for P, Q, kind, ax, n1, n2 in E:
        a, b = proj(p, P), proj(p, Q)
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))): continue
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = int(min(max(L / step, 2), 3000))
        # 화면에서 고르게: 1/Z 선형 보간으로 3D 매개변수
        s = np.linspace(0, 1, n)
        iz = 1 / P[2] + (1 / Q[2] - 1 / P[2]) * s
        t3 = (1 / iz - P[2]) / (Q[2] - P[2]) if abs(Q[2] - P[2]) > 1e-9 else s
        X = P[None] + (Q - P)[None] * t3[:, None]
        u = p['cx'] + F * X[:, 0] / X[:, 2]; v = p['cy'] + F * (1 - X[:, 1]) / X[:, 2]
        ins = (u >= -2) & (u < W + 2) & (v >= -2) & (v < H + 2)
        if not ins.any(): continue
        occ = [occupied(X + e * (sa * n1 + sb * n2), lo, hi) for sa in (1, -1) for sb in (1, -1)]
        cnt = sum(o.astype(int) for o in occ)
        flat = (cnt == 2) & ~((occ[0] & occ[3]) | (occ[1] & occ[2]))   # 이웃한 두 칸만 = 평평한 면
        crease = (cnt > 0) & (cnt < 4) & ~flat
        vis = ins & crease
        if vis.any():
            vis[vis] = ~occluded(X[vis], lo, hi)
        i = 0
        while i < n:
            if not vis[i]: i += 1; continue
            j = i
            while j + 1 < n and vis[j + 1]: j += 1
            if j > i:
                segs.append(((float(u[i]), float(v[i])), (float(u[j]), float(v[j])), kind, float(X[i, 2]), float(X[j, 2]), ax))
            i = j + 1
    return [s for s in segs if math.hypot(s[0][0] - s[1][0], s[0][1] - s[1][1]) >= 3]


def evidence(plate):
    gray = cv2.GaussianBlur(cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    ed = cv2.Canny(gray, 20, 60) > 0
    la_p = os.path.join(OUT, 'lineart.png')
    if os.path.exists(la_p):
        ed |= cv2.imread(la_p, 0) < 180
    dt = cv2.distanceTransform((~ed).astype(np.uint8), cv2.DIST_L2, 3)
    return ed, dt


def score(p, dt, W, H, step=4.0):
    B = boxes(p)
    S = visible_segments(p, edges3d(p, B), B, W, H, step=step)
    tot, n = 0.0, 0
    for a, b, *_ in S:
        L = math.hypot(b[0] - a[0], b[1] - a[1]); m = max(int(L / 4), 2)
        us = np.linspace(a[0], b[0], m); vs = np.linspace(a[1], b[1], m)
        d = np.minimum(dt[np.clip(vs.astype(int), 0, H - 1), np.clip(us.astype(int), 0, W - 1)], 12.0)
        tot += float(d.sum()); n += m
    return tot / max(n, 1), S


COLK = {'room': (0, 0, 255), 'pillar': (0, 150, 0), 'beam': (200, 0, 200), 'detail': (0, 140, 255)}


def thick(z, zref, t0=1.0, t_min=0.05, t_max=8.0):
    """거리에 따른 굵기(11-05 사용자, 스틱맨 거리 굵기와 같은 원근 규칙): 굵기 = t0 × zref / Z.
    zref = 왼쪽 맨 앞 기둥 앞면 깊이(사용자 지정), t0 = 1.0(앱 기본 굵기)."""
    return float(np.clip(t0 * zref / z, t_min, t_max))


def shapes(S, zref):
    """X·Y축 모서리 → ('line', a, b, 종류, 굵기). Z축 모서리 → ('wedge', 네 꼭짓점, 종류): 화면 폭 = APP_PX × 굵기(Z)."""
    out = []
    for a, b, k, za, zb, ax in S:
        if ax != 2 or abs(za - zb) < 1e-6:
            out.append(('line', a, b, k, thick((za + zb) / 2, zref)))
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
        if L < 1e-6: continue
        nx, ny = -dy / L, dx / L
        ha, hb = APP_PX * thick(za, zref) / 2, APP_PX * thick(zb, zref) / 2
        quad = [(a[0] + nx * ha, a[1] + ny * ha), (b[0] + nx * hb, b[1] + ny * hb), (b[0] - nx * hb, b[1] - ny * hb), (a[0] - nx * ha, a[1] - ny * ha)]
        out.append(('wedge', quad, k))
    return out


def draw(plate, SH, path, extra=''):
    ov = plate.copy(); wb = np.full_like(plate, 255)
    for sh in SH:
        if sh[0] == 'line':
            _, a, b, k, th = sh
            w = max(1, int(round(APP_PX * th)))
            cv2.line(wb, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), COLK[k], w, cv2.LINE_AA)
            cv2.line(ov, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), COLK[k], 1, cv2.LINE_AA)
        else:
            _, q, k = sh
            pts = np.array(q, np.float64).reshape(-1, 1, 2)
            cv2.fillPoly(wb, [np.round(pts * 16).astype(np.int32)], COLK[k], cv2.LINE_AA, shift=4)
            c = np.mean(q, 0)
            cv2.line(ov, tuple(map(int, ((q[0][0] + q[3][0]) / 2, (q[0][1] + q[3][1]) / 2))), tuple(map(int, ((q[1][0] + q[2][0]) / 2, (q[1][1] + q[2][1]) / 2))), COLK[k], 1, cv2.LINE_AA)
    if extra: cv2.putText(wb, extra, (8, 24), 0, 0.7, (0, 0, 0), 2)
    cv2.imwrite(path, np.vstack([ov, wb]))


def export(p, SH):
    """판 좌표 도형 → 장마다 판 위치만큼 옮긴 SFA. 배경 객체 ID는 모든 장에서 같고 점 ID는 장마다 새로.
    사다리꼴 면 = 투명 직선 4개(끝점 연결) + FR(Kind 0, 각 선 T 0–1). 스틱맨은 기존 SFA에서 복사."""
    import copy, zipfile, xml.etree.ElementTree as ET
    sys.path.insert(0, os.path.join(SP, 'scripts'))
    meta = json.load(open(os.path.join(SP, 'slice', 'plate', 'plate_meta.json')))
    off = {int(k): v for k, v in meta['offsets'].items()}
    OUTF = [int(v) for v in os.environ.get('ROOM_FRAMES', '1042,1062,1072,1102,1122').split(',')]
    import perspective_lines as PL
    W, H = 960, 540
    LAY = ((0, 'background.room'), (1, 'background.pillar'), (2, 'background.ceiling_beam'), (6, 'actor.stickman'))
    LID = {'room': 0, 'pillar': 1, 'beam': 2, 'detail': 0}
    INK = '-12566464'                       # 선·면 색(어두운 회색)
    INK_U = str(int(INK) & 0xFFFFFFFF)
    seq = ET.Element('Sequence', dict(Name='sfa_slice_room3d_v2', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount=str(len(OUTF)), BackgroundColor='-1'))
    STY = dict(ObjectScale='1.0', GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0')
    for pos, f in enumerate(OUTF):
        fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
        for lid, nm in LAY:
            ET.SubElement(fr, 'LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked='false'))
        pid = [1 + pos * 100000]
        dx, dy = off[f]
        oid = [1]

        def ap(ao, i, flag, x, y):
            el = ET.SubElement(ao, 'AP', dict(ID=str(pid[0]), Flags=flag, Index=str(i), X=f'{(x - dx) / W * 100:.3f}', Y=f'{(y - dy) / H * 100:.3f}'))
            pid[0] += 1
            return el

        frs = []
        for sh in SH:
            if sh[0] == 'line':
                _, a, b, k, th = sh
                ao = ET.SubElement(fr, 'AO', dict(ID=str(oid[0]), TypeId='1', Color=INK, LayerId=str(LID[k]), DrawOrder=str(oid[0]), ThicknessScale=f'{th:.3f}', **STY))
                oid[0] += 1
                ap(ao, 0, '9', *a); ap(ao, 1, '8', *b)
            else:
                _, q, k = sh
                objs = []
                for e in range(4):
                    p0, p1 = q[e], q[(e + 1) % 4]
                    ao = ET.SubElement(fr, 'AO', dict(ID=str(oid[0]), TypeId='1', Color='0', LayerId=str(LID[k]), DrawOrder=str(oid[0]), ThicknessScale='0.05', **STY))
                    oid[0] += 1
                    e0 = ap(ao, 0, '3' if e == 0 else '8', *p0); e1 = ap(ao, 1, '8' if e == 3 else '9', *p1)
                    objs.append((ao, e0, e1))
                for e, (ao, e0, e1) in enumerate(objs):
                    ET.SubElement(e1, 'AC', dict(ConnPtId=objs[(e + 1) % 4][1].get('ID')))
                    ET.SubElement(e0, 'AC', dict(ConnPtId=objs[(e - 1) % 4][2].get('ID')))
                frr = ET.Element('FR', dict(Color=INK_U))
                for ao, e0, e1 in objs:
                    ET.SubElement(frr, 'FS', dict(Kind='0', ObjId=ao.get('ID'), StartPtId=e0.get('ID'), EndPtId=e1.get('ID'), StartT='0.0', EndT='1.0'))
                frs.append(frr)
        m = {}
        for ao in PL.sroot.findall('Frame')[f - 432].findall('AO'):
            ao = copy.deepcopy(ao); ao.set('LayerId', '6')
            for a_ in ao.iter('AP'): m[a_.get('ID')] = str(pid[0]); a_.set('ID', str(pid[0])); pid[0] += 1
            fr.append(ao)
        for ac in fr.iter('AC'): ac.set('ConnPtId', m.get(ac.get('ConnPtId'), ac.get('ConnPtId')))
        for frr in frs: fr.append(frr)
    path = os.path.join(OUT, 'sfa_slice_room3d_v2.sfa')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('sfa_slice_room3d_v2.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
    import sfa_render as R
    R.PARAMS.update(pad=0.0, thick_mul=W / 1920)    # 앱 1920 폭 굵기를 960 그림에 맞춰(실제 보이는 비율 그대로)
    rows = []
    for pos, f in enumerate(OUTF):
        fr = seq.findall('Frame')[pos]
        rend = cv2.cvtColor(R.render_frame(seq, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
        PL.B.set(1, f + 7); ok, im = PL.B.read(); im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
        dx, dy = off[f]; ov = im.copy()
        for sh in SH:
            a, b = (sh[1], sh[2]) if sh[0] == 'line' else (((sh[1][0][0] + sh[1][3][0]) / 2, (sh[1][0][1] + sh[1][3][1]) / 2), ((sh[1][1][0] + sh[1][2][0]) / 2, (sh[1][1][1] + sh[1][2][1]) / 2))
            cv2.line(ov, (int(a[0] - dx), int(a[1] - dy)), (int(b[0] - dx), int(b[1] - dy)), (0, 0, 255), 1, cv2.LINE_AA)
        cv2.putText(rend, f'orig {f}', (6, 28), 0, 0.8, (0, 0, 255), 2)
        rows.append(np.hstack([ov, rend]))
    cv2.imwrite(os.path.join(OUT, 'room3d_frames.png'), cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5))
    n_line = sum(s[0] == 'line' for s in SH); n_w = len(SH) - n_line
    print('SFA', path, '직선', n_line, '사다리꼴 면', n_w, '(AO', n_line + 4 * n_w, ') 장', OUTF)


BND = dict(cx=(724 - 30, 724 + 30), cy=(301 - 20, 301 + 20), Xr=(3.5, 5.0), Xl=(-6.0, -4.5), Hc=(3.0, 3.8),
           pz0=(10.0, 12.5), ps=(12.0, 17.0), pw=(0.3, 1.2), pd=(0.4, 1.2), pin=(-0.1, 0.4), rp=(0.2, 0.8), rw=(0.3, 1.0),
           bd=(0.1, 0.5), bw=(0.3, 1.0), lx1=(-2.5, -1.0), lx2=(0.3, 1.8), lbw=(0.3, 0.9), lbd=(0.15, 0.5),
           dz0=(17.0, 21.0), dz1=(21.0, 24.0), dy=(1.8, 2.8), Zb=(60.0, 120.0),
           rd1a=(18.5, 21.5), rd1b=(21.6, 24.5), rd2a=(29.0, 33.5), rd2b=(33.6, 38.0), tw=(0.1, 0.6))


def main():
    os.makedirs(OUT, exist_ok=True)
    plate = cv2.imread(os.path.join(SP, 'slice', 'plate', 'plate.png'))
    H, W = plate.shape[:2]
    ed, dt = evidence(plate)
    pp = os.path.join(OUT, 'params.json')
    p = dict(P0)
    if os.path.exists(pp) and sys.argv[1:2] != ['reset']: p.update(json.load(open(pp)))
    s0, S = score(p, dt, W, H)
    print('시작 평균 거리', round(s0, 2), '선', len(S), flush=True)
    if sys.argv[1:2] in (['fit'], ['reset']):
        # 범위 제한(11-05): 범위가 없으면 맞추기 어려운 구조물을 숨겨(보 깊이 음수 등) 평균 거리를 낮추는 퇴화가 생겼다.
        from scipy.optimize import minimize
        groups = [g.split(',') for g in os.environ.get('ROOM_GROUPS', 'rd1a,rd1b,rd2a,rd2b,dy;tw;dz0,dz1').split(';')]
        for g in groups:
            x0 = np.array([p[k] for k in g])
            def f(x):
                q = dict(p); q.update(zip(g, x))
                return score(q, dt, W, H)[0]
            r = minimize(f, x0, method='Powell', bounds=[BND[k] for k in g], options=dict(maxiter=80, xtol=1e-3, ftol=1e-3))
            p.update(zip(g, map(float, r.x)))
            print(g, round(r.fun, 3), flush=True)
        json.dump(p, open(pp, 'w'), indent=1)
    s1, _ = score(p, dt, W, H)
    B = boxes(p)
    S = visible_segments(p, edges3d(p, B), B, W, H, step=1.0)
    SH = shapes(S, zref=p['pz0'])
    print('평균 거리', round(s1, 2), '보이는 모서리', len(S), 'Z축(면)', sum(s[5] == 2 for s in S), flush=True)
    json.dump(dict(zref=p['pz0'], params=p, shapes=SH), open(os.path.join(OUT, 'shapes.json'), 'w'))
    draw(plate, SH, os.path.join(OUT, 'room3d_fit.png'), f'mean edge dist {s1:.2f}px  edges {len(S)}')
    if sys.argv[1:2] in (['export'], ['fit'], ['reset']):
        export(p, SH)


if __name__ == '__main__':
    main()
