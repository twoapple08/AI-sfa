#!/usr/bin/env python3
"""SFA 한 장 ↔ 정답 문장(토큰열) 변환(2026-10-30 재설계, docs/VIDEO-TO-SFA-REDESIGN-2026-10-30.md).

정답 문장 = 그 장의 SFA 오브젝트를 **그리는 순서대로**(레이어 → 연결 묶음 → 오브젝트, sfa_render와 같은 순서) 적은 것.
보이는 픽셀이 아니라 오브젝트 전체 모양을 적으므로 가려진 부분도 이어진 한 오브젝트로 남는다.
  BG c c c c                                배경색(ARGB 4수)
  LAYER                                     새 레이어(숨긴 레이어는 뺀다)
  LINE|CIRC|CURVE [스타일] x y PT [LINK d]…   오브젝트. 스타일 = SAME(앞 오브젝트와 같음) 또는 COLOR a r g b THICK t [GLOW r w a c c c c]
                                            LINK d = d개 앞의 점과 연결(AC, 상대 거리 — 스틱맨은 대개 1·2). 위치가 달라도 된다(실측 5%)
  FILL a r g b {CONTOUR | SEG o s e t0 t1 | WHOLE o}…   면(FR). o = 끝에서 몇 번째 오브젝트(1 = 마지막), s·e = 그 오브젝트의 점 번호
  EOS
수 토큰은 0..NUM-1 하나로 공유한다(좌표 0.025 단위, 굵기 로그 칸, T 0.001 단위, 글로우 0.1 단위).
범위를 넘는 수(화면 밖으로 뻗은 선 끝·곡선 조절점, 4096개 넘는 오브젝트·점 번호)는 BIG + 세 자리로 정확히 적는다.
직선은 상자(-1000..1100)로 정확히 자른다. 곡선은 자르지 않는다(먼 조절점 곡선은 렌더러 근사까지 그대로 따라야 같은 그림).
버리는 것: 보이지 않고(색·글로우 알파 0) 면에도 안 쓰인 오브젝트, 숨긴 레이어, 화면에서 아주 먼 오브젝트,
Flags(파란점 — 규칙으로 다시 만든다), ID(새로 매긴다), ObjectScale(렌더에 영향 없음).
"""
import math
import xml.etree.ElementTree as ET

SPECIAL = ['PAD', 'BOS', 'EOS', 'BG', 'LAYER', 'LINE', 'CIRC', 'CURVE', 'SAME', 'COLOR', 'THICK', 'GLOW', 'PT', 'LINK',
           'FILL', 'CONTOUR', 'SEG', 'WHOLE', 'BIG']
TOK = {s: i for i, s in enumerate(SPECIAL)}
NUM = 8192
OFF = len(SPECIAL)
VOCAB = OFF + NUM
TYPES = {'1': 'LINE', '2': 'CIRC', '3': 'CURVE'}
RTYPES = {'LINE': '1', 'CIRC': '2', 'CURVE': '3'}
XMIN, XSTEP = -50.0, 0.025         # 좌표 -50..154.8 (0.05는 렌더 차 1%, 2026-10-30 측정)
TMIN, TSTEP = -1.0, 0.001          # FS T -1..3.095
GSTEP = 0.1                        # 글로우 반경·두께 0..409.5
TH0, THR = 0.01, 1.005             # 굵기 로그 칸(상대 오차 0.25%), 0번 = 0
FAR_SAFE = 5.0                     # 화면 밖 판정 여유(%) — 선 굵기·글로우 번짐 위에 더하는 안전 몫


BIGOFF = 2 ** 38                   # BIG 수의 0점(음수 좌표용). BIG 뒤 세 자리


def n(v):
    return OFF + max(0, min(NUM - 1, int(v)))


def num(v):
    """정수 v → [수] 또는 [BIG, 세 자리](범위 밖이면)."""
    v = int(v)
    if 0 <= v < NUM:
        return [OFF + v]
    w = max(0, min(NUM ** 3 - 1, v + BIGOFF))
    return [TOK['BIG'], OFF + w // NUM ** 2, OFF + w // NUM % NUM, OFF + w % NUM]


def is_num(t):
    return t >= OFF or t == TOK['BIG']


def q_th(v):
    return n(0 if v <= 0 else 1 + round(math.log(max(v, TH0) / TH0) / math.log(THR)))


def dq_th(t):
    k = t - OFF
    return 0.0 if k == 0 else TH0 * THR ** (k - 1)


def u32(v):
    return int(float(v)) & 0xFFFFFFFF


def argb4(v):
    v = u32(v)
    return [n(v >> 24), n((v >> 16) & 255), n((v >> 8) & 255), n(v & 255)]


def de_argb(ts):
    a, r, g, b = (t - OFF for t in ts)
    v = (a << 24) | (r << 16) | (g << 8) | b
    return str(v - (1 << 32) if v >= 1 << 31 else v)


def _alpha(v):
    return u32(v) >> 24


def style_of(a):
    ga = float(a.get('GlowAlpha') or 0)
    ga = ga if ga <= 1 or ga > 255 else ga  # 원래 값 그대로(0..255 정수가 대부분)
    glow = None
    if ga > 0 and float(a.get('GlowRadius') or 0) > 0 and float(a.get('GlowThickness') or 0) > 0:
        glow = (round(float(a.get('GlowRadius')) / GSTEP), round(float(a.get('GlowThickness')) / GSTEP),
                round(ga if ga > 1 else ga * 255), u32(a.get('GlowColor') or 0) & 0xFFFFFF)
    return (u32(a.get('Color')), q_th(float(a.get('ThicknessScale') or 1)), glow)


CLIP = (-1000.0, 1100.0)           # 직선은 이 상자로 정확히 자른다(보이는 모양 그대로, 좌표 -20억 같은 값 처리)


def far_away(a, xy, hwr):
    """화면(0–100)에 아무 화소도 닿지 않는 오브젝트인지 — 보수적으로(GPT 검토 10-30: 원 크기·굵기·글로우를 반영).
    원은 화면 화소 기준 반지름(가로 % 단위 r, 세로 % 단위 r/비율), 선은 굵기 반 + 글로우 폭 반 + 흐림 4σ를 여유로 더한다(1920 기준 화소 → %)."""
    T = float(a.get('ThicknessScale') or 1)
    gr, gw, ga = float(a.get('GlowRadius') or 0), float(a.get('GlowThickness') or 0), float(a.get('GlowAlpha') or 0)
    m_px = 8.0 * 1.14 * abs(T) / 2 + 1
    if ga > 0 and gw > 0:
        m_px = max(m_px, 8.0 * abs(T) * gw / 10 / 2 + 4 * gr + 1)
    mx = m_px / 1900 * 100 + FAR_SAFE
    my = mx / hwr
    if a.get('TypeId') == '2' and len(xy) >= 2:
        cx, cy = (xy[0][0] + xy[1][0]) / 2, (xy[0][1] + xy[1][1]) / 2
        rx = math.hypot(xy[1][0] - xy[0][0], (xy[1][1] - xy[0][1]) * hwr) / 2
        bb = (cx - rx, cy - rx / hwr, cx + rx, cy + rx / hwr)
    else:   # 직선·곡선: 점(곡선은 조절점 포함)의 상자가 모양을 감싼다
        bb = (min(x for x, _ in xy), min(y for _, y in xy), max(x for x, _ in xy), max(y for _, y in xy))
    return bb[2] + mx < 0 or bb[0] - mx > 100 or bb[3] + my < 0 or bb[1] - my > 100


def clip_line(xy):
    """Liang–Barsky. 두 점이 모두 상자 안이면 None(그대로)."""
    (x0, y0), (x1, y1) = xy
    lo, hi = CLIP
    if all(lo <= v <= hi for v in (x0, y0, x1, y1)):
        return None
    t0, t1 = 0.0, 1.0
    dx, dy = x1 - x0, y1 - y0
    for p, q in ((-dx, x0 - lo), (dx, hi - x0), (-dy, y0 - lo), (dy, hi - y0)):
        if p == 0:
            if q < 0:
                return [(min(max(x0, lo), hi), min(max(y0, lo), hi))] * 2
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
    if t0 > t1:
        return [(min(max(x0, lo), hi), min(max(y0, lo), hi))] * 2
    return [(x0 + dx * t0, y0 + dy * t0), (x0 + dx * t1, y0 + dy * t1)]


def order_objects(seq, fr):
    """sfa_render.render_frame과 같은 그리기 순서로 (레이어 번호, AO) 목록을 돌려준다."""
    layers = fr.findall('LayerDef')
    aos = fr.findall('AO')
    if not layers:
        layers = [{'ID': v} for v in dict.fromkeys(a.get('LayerId', '0') for a in aos)]
    ap_owner = {p.get('ID'): a.get('ID') for a in aos for p in a.findall('AP')}
    parent = {a.get('ID'): a.get('ID') for a in aos}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a in aos:
        for p in a.findall('AP'):
            for ac in p.findall('AC'):
                o = ap_owner.get(ac.get('ConnPtId'))
                if o and o in parent:
                    ra, rb = find(a.get('ID')), find(o)
                    if ra != rb:
                        parent[ra] = rb
    out = []
    for li, layer in enumerate(layers):
        if layer.get('Visible') == 'false':
            continue
        objs = sorted((a for a in aos if a.get('LayerId', '0') == layer.get('ID')), key=lambda a: int(a.get('DrawOrder') or a.get('ID')))
        groups = {}
        for a in objs:
            groups.setdefault(find(a.get('ID')), []).append(a)
        for g in groups.values():
            out += [(li, a) for a in g]
    return out


def encode(seq, fr):
    """한 장 → (토큰열, 기록). 기록: 버린 오브젝트 수, 잘린 좌표 수 등."""
    st = dict(drop_invis=0, drop_far=0, clamp=0, objs=0, links=0, fills=0, link_fwd=0)
    fill_objs = {s.get('ObjId') for r in fr.findall('FR') if _alpha(r.get('Color')) > 0 for s in r.findall('FS')}
    keep = []
    hwr = float(seq.get('HeightWidthRatio') or 0.5625) or 0.5625
    for li, a in order_objects(seq, fr):
        used = a.get('ID') in fill_objs
        vis = _alpha(a.get('Color')) > 0 or style_of(a)[2] is not None
        if not vis and not used:
            st['drop_invis'] += 1
            continue
        xy = [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')]
        if not xy:
            continue
        if len(xy) < {'1': 2, '2': 2, '3': 3}.get(a.get('TypeId'), 2):
            # 점이 모자란 오브젝트: 앱의 점 삭제 기능으로 생길 수 있다(사용자 10-30). 빼지 않고 그대로 적는다
            # (실측: tlqkf.sfa 154–156장 곡선 1점 하나뿐. 앱에서 어떻게 보이는지 미확인 — 렌더러는 안 그림)
            st['short'] = st.get('short', 0) + 1
        if not used and far_away(a, xy, hwr):
            st['drop_far'] += 1
            continue
        keep.append((li, a))
    toks = [TOK['BOS'], TOK['BG']] + argb4(fr.get('BackgroundColor', seq.get('BackgroundColor', '-1')))
    pidx, oidx = {}, {}
    prev_style, prev_layer = None, None
    for li, a in keep:
        if li != prev_layer:
            toks.append(TOK['LAYER'])
            prev_layer, prev_style = li, None
        toks.append(TOK[TYPES.get(a.get('TypeId'), 'LINE')])
        sty = style_of(a)
        if sty == prev_style:
            toks.append(TOK['SAME'])
        else:
            toks += [TOK['COLOR']] + argb4(sty[0]) + [TOK['THICK'], n(sty[1] - OFF)]
            if sty[2]:
                gr, gw, ga, gc = sty[2]
                toks += [TOK['GLOW'], n(gr), n(gw), n(ga)] + argb4(gc)[1:]
            prev_style = sty
        oidx[a.get('ID')] = len(oidx)
        xy = [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')]
        # 면이 쓰는 직선은 자르지 않는다(잘라도 FS의 T는 그대로라 면 구간이 바뀐다, GPT 검토 10-30) → BIG 좌표로 보존
        cl = clip_line(xy) if a.get('TypeId') == '1' and len(xy) == 2 and a.get('ID') not in fill_objs else None
        for pi, p in enumerate(a.findall('AP')[:NPTS[TYPES.get(a.get('TypeId'), 'LINE')]]):
            for v in (cl[pi] if cl else (float(p.get('X')), float(p.get('Y')))):
                v = v if v == v else 50.0
                k = round((v - XMIN) / XSTEP)
                st['clamp'] += not (0 <= k < NUM)
                toks += num(k)
            toks.append(TOK['PT'])
            for ac in p.findall('AC'):
                j = pidx.get(ac.get('ConnPtId'))
                if j is None:
                    st['link_fwd'] += 1      # 아직 안 나온 점 → 그 점 쪽에서 거꾸로 적힌다(AC는 양방향)
                    continue
                toks += [TOK['LINK']] + num(len(pidx) - j)  # 상대 거리(1 = 바로 앞 점)
                st['links'] += 1
            pidx[p.get('ID')] = len(pidx)
        st['objs'] += 1
    ptn = {}
    for _, a in keep:
        aps = a.findall('AP')[:NPTS[TYPES.get(a.get('TypeId'), 'LINE')]]
        for j, p in enumerate(a.findall('AP')):
            ptn[p.get('ID')] = min(j, len(aps) - 1)
    # 면 칠 순서는 중요하지 않다(사용자 10-30) → 주인 오브젝트(첫 FS의 오브젝트) 순으로 정렬해 고정(안정 정렬: 같은 주인끼리는 원래 순서,
    # 렌더러는 면을 주인 오브젝트와 함께 칠하므로 그림은 그대로)
    def _owner(r):
        for s_ in r.findall('FS'):
            if s_.get('ObjId') in oidx:
                return oidx[s_.get('ObjId')]
        return len(oidx)
    for r in sorted(fr.findall('FR'), key=_owner):
        if _alpha(r.get('Color')) == 0:
            continue
        segs = [s for s in r.findall('FS') if s.get('ObjId') in oidx]
        # 윤곽 묶음(렌더러와 같은 규칙: Contour 0 = 바깥, 1 이상 = 구멍, 번호 순). 바깥이 없으면 렌더러가 안 그리므로 뺀다.
        # 같은 번호는 한 묶음으로 모은다(0,1,0이 0,1,2로 바뀌던 것, GPT 검토 10-30). 해독은 0,1,2…로 다시 번호를 매긴다.
        groups = {}
        for s_ in segs:
            groups.setdefault(int(s_.get('Contour') or 0), []).append(s_)
        if 0 not in groups:
            continue
        toks += [TOK['FILL']] + argb4(r.get('Color'))
        for gi, c in enumerate(sorted(groups)):
            if gi:
                toks.append(TOK['CONTOUR'])
            for s in groups[c]:
                toks += seg_tokens(s, oidx, ptn)
        st['fills'] += 1
    toks.append(TOK['EOS'])
    return toks, st


def seg_tokens(s, oidx, ptn):
    """면 조각 하나(FS) → 토큰. 오브젝트는 상대 거리(1 = 마지막 오브젝트)."""
    rel = num(len(oidx) - oidx[s.get('ObjId')])
    if s.get('Kind') == '1' or s.get('StartT') is None:
        return [TOK['WHOLE']] + rel
    return ([TOK['SEG']] + rel + [n(ptn.get(s.get('StartPtId'), 0)), n(ptn.get(s.get('EndPtId'), 0)),
            n(round((float(s.get('StartT')) - TMIN) / TSTEP)), n(round((float(s.get('EndT')) - TMIN) / TSTEP))])


class Ids:
    def __init__(self):
        self.k = 1

    def __call__(self):
        self.k += 1
        return str(self.k)


def decode(toks, fid=1, pos=0, ids=None):
    """토큰열 → Frame 요소. ID는 ids로 파일 전체에서 겹치지 않게 새로 매긴다(앱 규칙: ID마다 레이어 하나).
    Flags는 파란점 규칙으로 다시 만든다: 연결 묶음의 첫 점 3, 앞 점에 이어진 점 8, 나머지 9."""
    ids = ids or Ids()
    i = 0
    fr = ET.Element('Frame', dict(ID=str(fid), Position=str(pos)))
    objs, pts, owner = [], [], []
    style = None
    layer = -1
    order = 0
    bg = '-1'

    def take(k):
        nonlocal i
        v = toks[i:i + k]
        i += k
        return v

    def rnum():
        nonlocal i
        if toks[i] == TOK['BIG']:
            v = ((toks[i + 1] - OFF) * NUM + (toks[i + 2] - OFF)) * NUM + (toks[i + 3] - OFF) - BIGOFF
            i += 4
            return v
        i += 1
        return toks[i - 1] - OFF
    toks = list(toks) + [TOK['EOS']] * 8   # 잘린 문장(생성 길이 한도)도 앞부분은 살린다
    while i < len(toks):
        t = toks[i]
        i += 1
        if t in (TOK['BOS'], TOK['PAD']):
            continue
        if t == TOK['EOS']:
            break
        if t == TOK['BG']:
            bg = de_argb(take(4))
        elif t == TOK['LAYER']:
            layer += 1
            ET.SubElement(fr, 'LayerDef', dict(ID=str(layer), Name=f'Layer {layer + 1}', Visible='true', Locked='false'))
            style = None
        elif t in (TOK['LINE'], TOK['CIRC'], TOK['CURVE']):
            if layer < 0:
                layer = 0
                ET.SubElement(fr, 'LayerDef', dict(ID='0', Name='Layer 1', Visible='true', Locked='false'))
            if toks[i] == TOK['SAME'] and style is not None:
                i += 1
            else:
                if toks[i] == TOK['SAME']:
                    i += 1
                    style = dict(Color='-16777216', ThicknessScale='1.0')
                else:
                    i += 1  # COLOR
                    style = dict(Color=de_argb(take(4)))
                    i += 1  # THICK
                    style['ThicknessScale'] = repr(round(dq_th(take(1)[0]), 6))
                    if i < len(toks) and toks[i] == TOK['GLOW']:
                        i += 1
                        gr, gw, ga = (v - OFF for v in take(3))
                        gc = de_argb([OFF] + take(3))
                        style.update(GlowRadius=repr(round(gr * GSTEP, 4)), GlowThickness=repr(round(gw * GSTEP, 4)),
                                     GlowAlpha=str(ga), GlowColor=str(int(gc) & 0xFFFFFF))
            o = ET.SubElement(fr, 'AO', dict(ID=ids(), TypeId=RTYPES[SPECIAL[t]], LayerId=str(layer), DrawOrder=str(order),
                                             ObjectScale='1.0', **{k: v for k, v in style.items()}))
            o.attrib.setdefault('GlowRadius', '0'); o.attrib.setdefault('GlowThickness', '0')
            o.attrib.setdefault('GlowAlpha', '0'); o.attrib.setdefault('GlowColor', '0')
            order += 1
            objs.append(o)
            j = 0
            while i < len(toks) and is_num(toks[i]):
                x = rnum()
                if not is_num(toks[i]):   # 잘린 점(y 없음)은 버린다
                    break
                y = rnum()
                i += 1  # PT
                ap = ET.SubElement(o, 'AP', dict(ID=ids(), Flags='9', Index=str(j), X=repr(round(XMIN + x * XSTEP, 4)), Y=repr(round(XMIN + y * XSTEP, 4))))
                j += 1
                while i < len(toks) and toks[i] == TOK['LINK']:
                    i += 1
                    k = len(pts) - rnum()
                    if 0 <= k < len(pts):
                        ET.SubElement(ap, 'AC', dict(ConnPtId=pts[k].get('ID')))
                        ET.SubElement(pts[k], 'AC', dict(ConnPtId=ap.get('ID')))
                pts.append(ap)
                owner.append(len(objs) - 1)
        elif t == TOK['FILL']:
            r = ET.SubElement(fr, 'FR', dict(Color=de_argb(take(4))))
            cur = 0
            while i < len(toks) and toks[i] in (TOK['SEG'], TOK['WHOLE'], TOK['CONTOUR']):
                u = toks[i]
                i += 1
                if u == TOK['CONTOUR']:
                    cur += 1
                    continue
                oi = len(objs) - rnum()
                if not 0 <= oi < len(objs):
                    i += 4 if u == TOK['SEG'] else 0
                    continue
                o = objs[oi]
                a = dict(Kind='1' if u == TOK['WHOLE'] else '0', ObjId=o.get('ID'))
                if u == TOK['SEG']:
                    s, e, t0, t1 = (v - OFF for v in take(4))
                    aps = o.findall('AP')
                    a.update(StartPtId=aps[min(s, len(aps) - 1)].get('ID'), EndPtId=aps[min(e, len(aps) - 1)].get('ID'),
                             StartT=repr(round(TMIN + t0 * TSTEP, 4)), EndT=repr(round(TMIN + t1 * TSTEP, 4)))
                if cur:
                    a['Contour'] = str(cur)
                ET.SubElement(r, 'FS', a)
    fr.set('BackgroundColor', bg)
    # 파란점 규칙
    par = list(range(len(objs)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    pid = {p.get('ID'): k for k, p in enumerate(pts)}
    for k, p in enumerate(pts):
        for ac in p.findall('AC'):
            par[find(owner[k])] = find(owner[pid[ac.get('ConnPtId')]])
    seen = set()
    for k, p in enumerate(pts):
        g = find(owner[k])
        if g not in seen:
            seen.add(g)
            p.set('Flags', '3')
        elif any(pid[ac.get('ConnPtId')] < k for ac in p.findall('AC')):
            p.set('Flags', '8')
    # 레이어 정의를 오브젝트보다 앞으로(원래 파일 순서)
    lds = fr.findall('LayerDef')
    for ld in lds:
        fr.remove(ld)
    for k, ld in enumerate(lds):
        fr.insert(k, ld)
    return fr


def names(toks):
    return [SPECIAL[t] if t < OFF else str(t - OFF) for t in toks]



# ── 문법(2026-10-30): 생성 때 다음에 올 수 있는 토큰만 허용 + 학습 때 토큰마다 칸 종류 표시 ──
FIELDS = ['spec', 'bg', 'color', 'thick', 'glow', 'coord', 'link', 'obj', 'ptidx', 't', 'big']
FID = {f: i for i, f in enumerate(FIELDS)}
NPTS = {'LINE': 2, 'CIRC': 2, 'CURVE': 3}


def grammar(strict=False):
    """생성기. yield (허용 특수 토큰 집합, 수 하한, 수 상한(포함, 수 불가면 -1), 칸 이름), send(고른 토큰).
    수 칸에서 BIG을 허용하면 특수 집합에 BIG이 들어 있다. 참조(LINK·면 오브젝트)는 상한이 NUM 이상일 때만 BIG을 허용하고,
    strict=True(정답 검사)면 BIG으로 적은 값도 범위를 확인한다(GPT 검토 10-30: LINK BIG(-1)이 통과하던 것)."""
    T = TOK
    st = {'pend': None}

    def ask(specs, lo=0, hi=-1, field='spec'):
        if st['pend'] is not None:
            t, st['pend'] = st['pend'], None
            return t
        return (yield (frozenset(T[x] for x in specs), lo, hi, field))

    def num(lo, hi, field, big=False, ref=False):
        big = big and (not ref or hi >= NUM)
        t = yield from ask(('BIG',) if big else (), lo, min(hi, NUM - 1), field)
        if t == T['BIG']:
            v = 0
            for _ in range(3):
                d = yield from ask((), 0, NUM - 1, 'big')
                v = v * NUM + (d - OFF)
            v -= BIGOFF
            if strict and ref and not lo <= v <= hi:
                raise ValueError(f'참조 {v} 범위 밖({lo}..{hi})')
            return v
        return t - OFF

    yield from ask(('BOS',))
    yield from ask(('BG',))
    for _ in range(4):
        yield from num(0, 255, 'bg')
    npts = nobj = 0
    obj_npts = []   # 오브젝트마다 실제 점 수(면 조각의 점 번호 제한)
    style = False
    t = yield from ask(('LAYER', 'EOS'))   # 빈 장 허용
    while True:
        if t == T['EOS']:
            return
        if t == T['LAYER']:
            style = False
            t = yield from ask(('LAYER', 'LINE', 'CIRC', 'CURVE', 'EOS') + (('FILL',) if nobj else ()))
            continue
        if t == T['FILL']:
            for _ in range(4):
                yield from num(0, 255, 'color')
            u = yield from ask(('SEG', 'WHOLE'))
            while True:
                if u == T['EOS']:
                    return
                if u == T['CONTOUR']:
                    u = yield from ask(('SEG', 'WHOLE'))
                    continue
                if u == T['FILL']:
                    for _ in range(4):
                        yield from num(0, 255, 'color')
                    u = yield from ask(('SEG', 'WHOLE'))
                    continue
                o = yield from num(1, nobj, 'obj', big=True, ref=True)
                k = obj_npts[nobj - o] if 1 <= o <= nobj else 1
                if u == T['SEG']:
                    yield from num(0, max(k - 1, 0), 'ptidx')
                    yield from num(0, max(k - 1, 0), 'ptidx')
                    yield from num(0, NUM - 1, 't')
                    yield from num(0, NUM - 1, 't')
                u = yield from ask(('SEG', 'WHOLE', 'CONTOUR', 'FILL', 'EOS'))
        kind = SPECIAL[t]
        s = yield from ask(('SAME', 'COLOR') if style else ('COLOR',))
        if s == T['COLOR']:
            for _ in range(4):
                yield from num(0, 255, 'color')
            yield from ask(('THICK',))
            yield from num(0, NUM - 1, 'thick')
            style = True
            g = yield from ask(('GLOW', 'BIG'), 0, NUM - 1, 'coord')   # GLOW 또는 첫 x 좌표
            if g == T['GLOW']:
                for _ in range(3):
                    yield from num(0, NUM - 1, 'glow')
                for _ in range(3):
                    yield from num(0, 255, 'glow')
            else:
                st['pend'] = g
        n_ = NPTS[kind]
        obj_npts.append(0)
        for k in range(n_):
            yield from num(0, NUM - 1, 'coord', big=True)
            yield from num(0, NUM - 1, 'coord', big=True)
            yield from ask(('PT',))
            npts += 1
            obj_npts[-1] += 1
            last = k == n_ - 1
            link = ('LINK',) if npts > 1 else ()
            while True:
                ends = ('LAYER', 'LINE', 'CIRC', 'CURVE', 'FILL', 'EOS')
                if last:
                    a = yield from ask(link + ends)
                else:   # LINK, 다음 점 x, 또는 점이 모자란 채 끝(점 삭제 기능)
                    a = yield from ask(link + ('BIG',) + ends, 0, NUM - 1, 'coord')
                if a == T['LINK']:
                    yield from num(1, npts - 1, 'link', big=True, ref=True)
                    continue
                if not last and (a >= OFF or a == T['BIG']):
                    st['pend'] = a
                break
            if a < OFF and a != T['BIG']:
                break
        nobj += 1
        t = a


def allowed_ok(al, t):
    specs, lo, hi, _ = al
    return t in specs or (t >= OFF and lo <= t - OFF <= hi)


def fields(toks):
    """토큰열을 문법으로 읽어 토큰마다 칸 번호(FID)를 돌려준다. 문법에 어긋나면 ValueError."""
    g = grammar(strict=True)
    al = next(g)
    out = []
    for i, t in enumerate(toks):
        if not allowed_ok(al, t):
            raise ValueError(f'{i}번째 토큰 {names([t])} 불가(허용 {names(sorted(al[0]))} 수 {al[1]}..{al[2]})')
        out.append(FID[al[3]] if t >= OFF else FID['spec'])
        try:
            al = g.send(t)
        except StopIteration:
            if i != len(toks) - 1:
                raise ValueError('EOS 뒤에 토큰')
            return out
    raise ValueError('EOS 없이 끝남')
