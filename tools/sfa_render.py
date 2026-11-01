#!/usr/bin/env python3
"""SFA 기준 렌더러(서버용). 앱 내보내기 영상과 픽셀을 대조해 뷰어의 정답 기준을 만든다.

사용:
  python tools/sfa_render.py <file.sfa> <out_dir> [--frames 0,10,20] [--size 1920x1080]
  python tools/sfa_render.py <file.sfa> --compare <app.mp4> [--frames ...]   # 앱 영상과 프레임별 차이

근거(정적 분석, docs/AOT-RENDER-CONTEXT·PAINT-DISPATCH·DRAW-GLOW·GROUP-SHADER-TIMELINE):
- 좌표: x = OffsetX + Uw*x/100, y = OffsetY + Uh*y/100. 여백 P(기본 8 기준 helper=6)를 뺀 영역에 비율(HeightWidthRatio) 맞춤.
- 선 폭: w = 8 * S * ThicknessScale (S = sequence thickness/100, 파일에 없으면 1), 실제 폭 round(1.14*w). 끝·이음은 둥글게.
- 글로우: W = 8*S*ThicknessScale*max(GlowThickness/10,0), R = GlowRadius*S, sigma = sqrt(R^2+0.29^2).
  셰이더는 폭 W 띠를 Gaussian(sigma)으로 적분한 커버리지 × GlowColor(GlowAlpha). 여기서는 같은 띠를 그린 뒤 Gaussian 블러로 근사한다.
- 채우기(FR): FS마다 ObjId 곡선의 [StartT, EndT] 구간을 이어 붙인 닫힌 경로. 직선은 선형, 곡선은 2차 베지어.
작은 미리보기: PARAMS['thick_mul'] = W/1920 이면 선·글로우를 그림 크기에 맞춰 줄인다(기본 1.0 = 앱 1920 기준 고정 픽셀; 400px 시트에서 선이 4.8배 두꺼워 뭉개졌다, 10-28 사용자 지적).
가정(영상 대조로 조정 중인 항목은 PARAMS에 모았다): 레이어 그리기 순서, FR이 그려지는 위치, ObjectScale의 효과.
"""
import math, sys, zipfile, os
import xml.etree.ElementTree as ET
import numpy as np
import skia

PARAMS = dict(pad=6.0, base=8.0, stab=1.14, layer_order='normal', glow=True, fill_first=True, objscale_thick=False, circ_off=0, circ_dir=1, evenodd=True, gap=1.5, split_strict=False, gsig=1.0, gw=1.0, glow_mode='cv', groups=None, hole_mode='difference', thick_mul=1.0)


def argb(v):
    v = int(v) & 0xFFFFFFFF
    return skia.Color((v >> 16) & 255, (v >> 8) & 255, v & 255, (v >> 24) & 255)


def alpha(v):
    return (int(v) & 0xFFFFFFFF) >> 24


def iter_frames(path, want=None):
    z = zipfile.ZipFile(path)
    f = z.open(z.namelist()[0])
    seq = None
    for ev, el in ET.iterparse(f, events=('start', 'end')):
        if ev == 'start':
            if el.tag == 'Sequence' and seq is None:
                seq = el
            continue
        if el.tag != 'Frame':
            continue
        pos = int(el.get('Position'))
        if want is None or pos in want:
            yield seq, el
        el.clear()


class Geo:
    def __init__(self, seq, W, H):
        R = float(seq.get('HeightWidthRatio') or 0.5625) or 0.5625
        P = PARAMS['pad'] * W / 1920  # 여백은 앱 기준 화면 1920 폭에서 6화소 — 작은 그림에서도 같은 비율(2026-10-24, 비교 영상 작은 칸에서 4배 두꺼웠음)
        aw, ah = min(max(W - 2 * P, 1), W), min(max(H - 2 * P, 1), H)
        if ah / aw > R:
            uw, uh = aw, aw * R
        else:
            uh, uw = ah, ah / R
        self.ox, self.oy, self.uw, self.uh = (W - uw) / 2, (H - uh) / 2, uw, uh
        self.S = float(seq.get('Thickness', 100)) / 100

    def pt(self, x, y):
        return self.ox + self.uw * x / 100, self.oy + self.uh * y / 100


def obj_points(ao, geo):
    return [geo.pt(float(p.get('X')), float(p.get('Y'))) for p in ao.findall('AP')]


def qb(p, t):
    (x0, y0), (x1, y1), (x2, y2) = p
    u = 1 - t
    return u * u * x0 + 2 * u * t * x1 + t * t * x2, u * u * y0 + 2 * u * t * y1 + t * t * y2


def circle_arcs(cx, cy, r, box, tol=0.05, max_seg=32.0):
    """원(중심·반지름, 화소)의 상자 안 호들을 꺾은선으로(float64로 직접 계산). 상자 = (x0, y0, x1, y1).
    반지름이 아주 큰 원(수백만 %)은 skia 원 근사가 무너져 화면에 대각선 쐐기로 나오고, 좌표가 조금만 달라도 모양이 바뀌었다
    (11-01 판 6 자료 1080 정합성 표본 6,410화소·서버 재현 30,006화소). 꺾은선 마디 길이는 처짐(sagitta) tol 화소 이하."""
    x0, y0, x1, y1 = box
    angs = {0.0, 2 * math.pi}
    for v, ax in ((x0, 0), (x1, 0), (y0, 1), (y1, 1)):
        d = v - (cx if ax == 0 else cy)
        if abs(d) <= r:
            u = max(-1.0, min(1.0, d / r))
            cand = (math.acos(u), -math.acos(u)) if ax == 0 else (math.asin(u), math.pi - math.asin(u))   # x = cx + r cos θ, y = cy + r sin θ
            for t in cand:
                angs.add(t % (2 * math.pi))
    angs = sorted(angs)
    seg = min(max_seg, math.sqrt(8 * r * tol)) if r > 0 else max_seg
    out = []
    for a0, a1 in zip(angs, angs[1:]):
        m = (a0 + a1) / 2
        if not (x0 <= cx + r * math.cos(m) <= x1 and y0 <= cy + r * math.sin(m) <= y1):
            continue
        n = max(2, int(math.ceil((a1 - a0) * r / seg)) + 1)
        pts = [(cx + r * math.cos(t), cy + r * math.sin(t)) for t in np.linspace(a0, a1, n)]
        if out and abs(out[-1][1] - a0) < 1e-12:
            out[-1] = (out[-1][0], a1, out[-1][2] + pts[1:])
        else:
            out.append((a0, a1, pts))
    if len(out) > 1 and out[0][0] == 0.0 and out[-1][1] == 2 * math.pi:   # 0 각도를 지나는 호는 이어 붙인다
        out = [(out[-1][0], out[0][1], out[-1][2] + out[0][2][1:])] + out[1:-1]
    return [p for _, _, p in out]


def geom_path(kind, pts):
    path = skia.Path()
    if kind == 'P':   # 상자 안 호 꺾은선들(아주 큰 원)
        for line in pts:
            if len(line) >= 2:
                path.moveTo(*line[0])
                for q in line[1:]:
                    path.lineTo(*q)
    elif kind == '1' and len(pts) >= 2:
        path.moveTo(*pts[0]); path.lineTo(*pts[1])
    elif kind == '2' and len(pts) >= 2:
        (x1, y1), (x2, y2) = pts[:2]
        path.addCircle((x1 + x2) / 2, (y1 + y2) / 2, math.hypot(x2 - x1, y2 - y1) / 2)
    elif kind == '3' and len(pts) >= 3:
        path.moveTo(*pts[0]); path.quadTo(*pts[1], *pts[2])
    return path


def seg_points(kind, pts, t0, t1, step=2.0):
    out = []
    if kind == '2' and len(pts) >= 2:
        L = math.pi * math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    else:
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    n = max(2, int(math.ceil(abs(t1 - t0) * L / step)) + 1) if kind != '1' else 2
    for t in np.linspace(t0, t1, n):
        if kind == '3' and len(pts) >= 3:
            out.append(qb(pts[:3], t))
        elif kind == '2' and len(pts) >= 2:
            (x1, y1), (x2, y2) = pts[:2]
            cx, cy, r = (x1 + x2) / 2, (y1 + y2) / 2, math.hypot(x2 - x1, y2 - y1) / 2
            a0 = math.atan2(y1 - cy, x1 - cx) + PARAMS['circ_off'] * math.pi / 2
            ang = a0 + PARAMS['circ_dir'] * 2 * math.pi * t
            out.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
        elif len(pts) >= 2:
            out.append((pts[0][0] + (pts[1][0] - pts[0][0]) * t, pts[0][1] + (pts[1][1] - pts[0][1]) * t))
    return out


def glow_cv(surf, path, Wg, sig, gc, ga, W, H):
    """띠(폭 Wg)를 Gaussian(sig)으로 흐린 커버리지 x GlowColor x GlowAlpha 를 현재 화면 위에 합성(srcOver).
    큰 sigma도 정확하도록 OpenCV로 블러한다(축소 래스터에서 계산 후 확대)."""
    import cv2
    b = path.computeTightBounds()
    m = Wg / 2 + 4 * sig + 2
    x0, y0 = max(int(b.left() - m), 0), max(int(b.top() - m), 0)
    x1, y1 = min(int(b.right() + m) + 1, W), min(int(b.bottom() + m) + 1, H)
    if x1 <= x0 or y1 <= y0:
        return
    q = 1.0 if sig < 6 else max(0.1, 3.0 / sig)
    w, h = max(1, int((x1 - x0) * q)), max(1, int((y1 - y0) * q))
    ms = skia.Surface(w, h)
    mc = ms.getCanvas()
    mc.clear(skia.ColorTRANSPARENT)
    mc.scale(w / (x1 - x0), h / (y1 - y0))
    mc.translate(-x0, -y0)
    mc.drawPath(path, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(Wg, 0.01),
                                 StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))
    a = ms.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
    a = cv2.GaussianBlur(a, (0, 0), sig * q) if sig * q > 0.05 else a
    a = cv2.resize(a, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
    a = np.clip(a, 0, 1) * ga
    img = surf.makeImageSnapshot().toarray()
    reg = img[y0:y1, x0:x1].astype(np.float32)
    col = np.array([gc & 255, (gc >> 8) & 255, (gc >> 16) & 255], np.float32)  # BGRA 순서
    reg[..., :3] = reg[..., :3] * (1 - a[..., None]) + col * a[..., None]
    img[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    surf.getCanvas().drawImage(skia.Image.fromarray(img, colorType=skia.kBGRA_8888_ColorType), 0, 0)


def render_frame(seq, fr, W=1920, H=1080):
    geo = Geo(seq, W, H)
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(argb(fr.get('BackgroundColor', seq.get('BackgroundColor', '-1'))))
    layers = [l for l in fr.findall('LayerDef')]
    if PARAMS['layer_order'] == 'reverse':
        layers = layers[::-1]
    aos = fr.findall('AO')
    if not layers:
        # 옛 형식(LayerDef 없음): 원래 앱은 오브젝트 전체를 그린다. 오브젝트의 LayerId 값마다 보이는 레이어를 만든다.
        layers = [{'ID': v} for v in dict.fromkeys(a.get('LayerId', '0') for a in aos)]
    by_id = {a.get('ID'): (a.get('TypeId'), obj_points(a, geo), a) for a in aos}
    # 조절점이 아주 먼 곡선은 상자 안 구간만 그린다(sfa_tokens.clip_quad, 정답 문장과 같은 자르기 — 11-01 그림·정답 어긋남).
    # 면이 쓰는 곡선은 그대로(면 T가 원래 곡선 기준).
    import sfa_tokens as K
    used = {s.get('ObjId') for r in fr.findall('FR') if K._alpha(r.get('Color')) > 0 for s in r.findall('FS')}
    for a in aos:
        if a.get('TypeId') == '3' and a.get('ID') not in used and len(a.findall('AP')) >= 3:
            cq = K.clip_quad([(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')[:3]])
            if cq is not None:
                by_id[a.get('ID')] = ('3', [geo.pt(x, y) for x, y in cq], a)
        elif a.get('TypeId') == '2' and a.get('ID') not in used and len(a.findall('AP')) >= 2:
            # 아주 큰 원(점이 상자 밖): 상자 안 호만 꺾은선으로 정확히(circle_arcs). 정답 문장은 원 그대로(좌표가 조금 달라도 같은 모양으로 그려진다)
            xy = [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')[:2]]
            if not all(K.CLIP[0] <= v <= K.CLIP[1] for q in xy for v in q):
                # 반지름이 상한보다 크면 정답 문장과 같은 원으로 바꾼 뒤(K.canon_circle — 큰 수끼리 빼는 정밀도 손실도 막는다) 호를 계산
                cc = K.canon_circle(xy, float(seq.get('HeightWidthRatio') or 0.5625) or 0.5625)
                if cc == []:   # 화면 상자에 닿지 않는 원(정답 문장에서도 뺀다)
                    by_id[a.get('ID')] = ('P', [], a)
                    continue
                xy = cc or xy
                (px1, py1), (px2, py2) = [geo.pt(x, y) for x, y in xy]
                bx0, by0 = geo.pt(K.CLIP[0], K.CLIP[0])
                bx1, by1 = geo.pt(K.CLIP[1], K.CLIP[1])
                by_id[a.get('ID')] = ('P', circle_arcs((px1 + px2) / 2, (py1 + py2) / 2, math.hypot(px2 - px1, py2 - py1) / 2,
                                                       (bx0, by0, bx1, by1)), a)
    frs = fr.findall('FR')
    fr_owner = {}
    for i, r in enumerate(frs):
        first = next((s.get('ObjId') for s in r.findall('FS') if s.get('ObjId') in by_id), None)
        fr_owner.setdefault(first, []).append(r)
    drawn = set()

    def contour_path(segs):
        # 앱 규칙(AOT-FILL-PATH 4·5절): 첫 시작점 moveTo, 조각 사이 간격이 0.1보다 크면 lineTo로 잇고 마지막에 닫는다.
        # 곡선 T는 0–1로 자르고, 직선·원 T는 자르지 않는다. 각 윤곽은 짝홀 규칙.
        pts = []
        for s in segs:
            o = by_id.get(s.get('ObjId'))
            if not o:
                continue
            t0 = float(s.get('StartT') or 0)
            t1 = float(s.get('EndT') if s.get('EndT') is not None else 1)
            if o[0] == '3':
                t0, t1 = min(max(t0, 0), 1), min(max(t1, 0), 1)
                if abs(t1 - t0) <= 1e-6:
                    continue
            pts += seg_points(o[0], o[1], t0, t1)
        if len(pts) < 3:
            return None
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close()
        p.setFillType(skia.PathFillType.kEvenOdd)
        return p

    def draw_fill(r):
        if alpha(r.get('Color')) == 0:
            return
        groups = {}
        for s in r.findall('FS'):
            groups.setdefault(int(s.get('Contour') or 0), []).append(s)
        outer = contour_path(groups.get(0, []))
        if outer is None:
            return
        for k in sorted(g for g in groups if g > 0):
            hole = contour_path(groups[k])
            if hole is not None and PARAMS['hole_mode'] == 'evenodd':
                outer.addPath(hole)
                continue
            if hole is not None:
                try:
                    res = skia.Op(outer, hole, skia.PathOp.kDifference_PathOp)
                except RuntimeError:
                    res = None
                if res is not None:
                    outer = res
        c.drawPath(outer, skia.Paint(Color=argb(r.get('Color')), AntiAlias=True, Style=skia.Paint.kFill_Style))

    S = geo.S
    # 연결 그룹(그리기 단위): 규칙은 sfa_tokens.link_groups 하나(정답 문장 순서와 같게). PARAMS['groups']가 None이면 sfa_tokens.GROUP_MODE.
    import sfa_tokens as K
    find = K.link_groups(aos, PARAMS['groups'], fr.findall('FR'))

    def draw_glow(a, path):
        T = float(a.get('ThicknessScale') or 1)
        gr, gt, ga = float(a.get('GlowRadius') or 0), float(a.get('GlowThickness') or 0), float(a.get('GlowAlpha') or 0)
        if not (PARAMS['glow'] and gr > 0 and gt > 0 and ga > 0):
            return
        Wg = PARAMS['base'] * max(S * T, 0) * max(gt / 10, 0) * PARAMS['gw'] * PARAMS['thick_mul']
        sig = math.sqrt((gr * S * PARAMS['gsig'] * PARAMS['thick_mul']) ** 2 + 0.29 ** 2)
        gc = int(a.get('GlowColor')) & 0xFFFFFFFF
        ga_ = min(max(ga if ga <= 1 else ga / 255, 0), 1)
        if PARAMS['glow_mode'] == 'cv':
            glow_cv(surf, path, Wg, sig, gc, ga_, W, H)
        else:
            col = skia.Color((gc >> 16) & 255, (gc >> 8) & 255, gc & 255, int(round(255 * ga_)))
            c.drawPath(path, skia.Paint(Color=col, AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=Wg,
                                        StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join,
                                        MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, sig)))

    def draw_base(a, path):
        T = float(a.get('ThicknessScale') or 1)
        if PARAMS['objscale_thick']:
            T *= float(a.get('ObjectScale') or 1)
        if alpha(a.get('Color')) > 0:
            w = PARAMS['base'] * max(S * T, 0) * PARAMS['thick_mul']
            if w > 0:
                sw = round(PARAMS['stab'] * w)
                c.drawPath(path, skia.Paint(Color=argb(a.get('Color')), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                            StrokeWidth=max(sw, 0.5), StrokeCap=skia.Paint.kRound_Cap,
                                            StrokeJoin=skia.Paint.kRound_Join))

    def fills_of(a):
        for r in fr_owner.get(a.get('ID'), []):
            if id(r) not in drawn:
                drawn.add(id(r)); draw_fill(r)

    for layer in layers:
        if layer.get('Visible') == 'false':
            continue
        objs = sorted((a for a in aos if a.get('LayerId', '0') == layer.get('ID')), key=lambda a: int(a.get('DrawOrder') or a.get('ID')))
        if True:
            groups = {}
            for a in objs:
                groups.setdefault(find(a.get('ID')), []).append(a)
            units = list(groups.values())
        else:
            units = [[a] for a in objs]
        # 레이어 투명도(LayerDef Opacity 0–100, 새 앱 기능 — 11-02 사용자 '막고라' 파일에서 처음 봄, 예전 수집 441파일에는 없음):
        # 레이어를 그대로 그린 뒤 그리기 전 화면과 op 비율로 섞는다 = 레이어 묶음을 불투명도 op로 덮어 그리기(srcOver 그룹 불투명도와 같은 식)
        op = min(max(float(layer.get('Opacity') or 100) / 100, 0.0), 1.0)
        before = surf.makeImageSnapshot().toarray().astype(np.float32) if op < 1 else None
        for g in units:
            paths = [(a, geom_path(by_id[a.get('ID')][0], by_id[a.get('ID')][1])) for a in g]
            for a, path in paths:
                draw_glow(a, path)
            for a, path in paths:
                if PARAMS['fill_first']:
                    fills_of(a)
                draw_base(a, path)
                if not PARAMS['fill_first']:
                    fills_of(a)
        if before is not None:
            after = surf.makeImageSnapshot().toarray().astype(np.float32)
            mix = np.clip(before + (after - before) * op, 0, 255).astype(np.uint8)
            surf.getCanvas().drawImage(skia.Image.fromarray(mix, colorType=skia.kBGRA_8888_ColorType), 0, 0)
    # 남은 채우기(주인 곡선이 어느 레이어에도 안 그려진 것)만 마지막에. 주인 곡선이 숨긴 레이어에 있으면 그리지 않는다
    # (2026-10-26 사용자 색칠공부 SFA: 숨긴 '중간 레이어'의 채색 면이 그려져 앱 화면과 달랐다)
    hidden = {l.get('ID') for l in layers if l.get('Visible') == 'false'}
    for owner, rs in fr_owner.items():
        if owner in by_id and by_id[owner][2].get('LayerId', '0') in hidden:
            for r in rs:
                drawn.add(id(r))
    for r in frs:
        if id(r) not in drawn:
            draw_fill(r)
    img = surf.makeImageSnapshot().toarray()  # BGRA
    return img[..., [2, 1, 0]].copy()


def video_frame(mp4, n, W=1920, H=1080):
    import subprocess
    p = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', mp4, '-vf', f'select=eq(n\\,{n}),scale={W}:{H}',
                        '-vsync', '0', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                       capture_output=True, stdin=subprocess.DEVNULL)
    a = np.frombuffer(p.stdout, np.uint8)
    return a[:W * H * 3].reshape(H, W, 3) if a.size >= W * H * 3 else None


def main():
    src = sys.argv[1]
    want = None
    if '--frames' in sys.argv:
        want = {int(x) for x in sys.argv[sys.argv.index('--frames') + 1].split(',')}
    W, H = 1920, 1080
    if '--size' in sys.argv:
        W, H = (int(x) for x in sys.argv[sys.argv.index('--size') + 1].split('x'))
    import cv2
    if '--compare' in sys.argv:
        mp4 = sys.argv[sys.argv.index('--compare') + 1]
        errs = []
        for seq, fr in iter_frames(src, want):
            pos = int(fr.get('Position'))
            mine = render_frame(seq, fr, W, H)
            ref = video_frame(mp4, pos, W, H)
            if ref is None:
                continue
            d = np.abs(mine.astype(np.int16) - ref.astype(np.int16)).mean()
            errs.append(d)
            print(f'frame {pos} mean_abs_diff {d:.2f}', flush=True)
        print('MEAN', round(float(np.mean(errs)), 3) if errs else None)
        return
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for seq, fr in iter_frames(src, want):
        img = render_frame(seq, fr, W, H)
        cv2.imwrite(os.path.join(out, f"f{int(fr.get('Position')):04d}.png"), img[..., ::-1])


if __name__ == '__main__':
    main()
