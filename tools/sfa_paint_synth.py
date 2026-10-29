#!/usr/bin/env python3
"""페인트 합성(2026-10-29): 흰 바탕 스틱맨 파일 복사본에 부족한 페인트 요소를 덧붙여 학습 자료를 늘린다.
원본 그림(선)은 그대로 두고 아래·위에 면만 더한다. 정답은 렌더 → 정답 지도 과정에서 자동으로 따라온다.

덧붙이는 것(장면 하나에 같은 설정, 장마다 같은 배경):
1) 배경: 장 배경색 + 화면 전체 불투명 면(바탕색) + 위아래 그라데이션(반투명 띠 여러 겹) + 땅(아래쪽 다각형).
2) 머리 채우기: 원(TypeId 2)마다 통째 채우기(FS Kind=1) — 실제 파일과 같은 방식.
3) 반투명 명암: 위에서 내려오는 빛 원뿔, 인물(연결 묶음)마다 발밑 그림자 타원.
4) 어두운 바탕이면 검은 선을 밝게(어두운 장면에서 작가들이 쓰는 방식, 바탕과 선이 같은 색이 되지 않게).
값 범위: 반투명 면 알파는 실제 파일 5개(922·포이즌 파트2·연출ㆍ이펙트ㆍ연기ㆍ능력·오버드라이브·dncncn) 분위 10–90% = 90–215.
면 테두리 선은 투명(Color 0), 파란점 규칙(고리마다 Flags 3 하나, 꼭짓점마다 표시 하나).
레이어(사용자 10-29 앱 확인: 같은 레이어에 그리는 순서 번호만 낮춰 깐 배경이 앱에서는 인물 선을 덮었다): 맨 아래 '배경'(바탕·띠·땅·그림자),
원래 레이어들(번호 +1), 맨 위 '빛'(빛 원뿔). 레이어 안 그리는 순서는 기존보다 큰 번호로 차례대로.
사용: python sfa_paint_synth.py 원본.sfa 출력.sfa [--seed 0]
"""
import argparse
import colorsys
import math
import random
import xml.etree.ElementTree as ET
import zipfile

SCENES = {  # (위 색, 아래 색, 땅 색) HSV 범위 — 밤·노을·실내·낮·동굴
    'night': ((0.60, 0.68), (0.45, 0.75), (0.10, 0.25)),
    'dusk': ((0.02, 0.10), (0.55, 0.85), (0.45, 0.75)),
    'indoor': ((0.05, 0.15), (0.15, 0.40), (0.25, 0.55)),
    'day': ((0.52, 0.60), (0.30, 0.55), (0.80, 0.95)),
    'cave': ((0.70, 0.85), (0.20, 0.45), (0.08, 0.20)),
}


def argb(r, g, b, a=255):
    return str((a << 24) | (r << 16) | (g << 8) | b)


def hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1, min(max(s, 0), 1), min(max(v, 0), 1))
    return int(r * 255), int(g * 255), int(b * 255)


class Ids:
    """앱은 AO ID 하나를 파일 전체의 '공통 오브젝트'로 만들고 레이어도 ID마다 하나로 저장한다(docs/AOT-PATH-TRACE-2026-10-15.md: 불러올 때 DrawOrder는 읽지 않고
    처음 나온 순서로 새 순서값). 그래서 역할마다 ID 구간을 고정한다 — 장마다 '최대+1'로 매기면 그림자 개수가 다른 장에서 같은 ID가 빛·배경을 오가
    빛이 배경 레이어로 묶였다(사용자 10-29 앱 확인). 점 ID는 파일 전체에서 겹치지 않게 이어서 센다."""

    def __init__(self, root):
        aos = [a for f in root.findall('Frame') for a in f.findall('AO')]
        self.base = max([int(a.get('ID')) for a in aos] + [0]) + 1
        self.ap = max([int(p.get('ID')) for a in aos for p in a.findall('AP')] + [0]) + 1
        self.ao = self.base

    def at(self, slot):
        """역할 구간 시작: 0 배경 고정 면, 1000 + 20·k 그림자 k, 5000 빛."""
        self.ao = self.base + slot


def poly(frame, ids, pts, color, order, layer):
    """닫힌 다각형 면 하나: 투명 테두리 선 + FR. order = 첫 테두리 선의 DrawOrder(면은 주인 선 자리에 그려짐)."""
    objs = []
    n = len(pts)
    for k in range(n):
        o = ET.Element('AO', dict(ID=str(ids.ao), TypeId='1', Color='0', LayerId=layer, DrawOrder=str(order + k), ThicknessScale='1.0', ObjectScale='1.0',
                                  GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0'))
        ids.ao += 1
        pp = []
        for j, (x, y) in enumerate((pts[k], pts[(k + 1) % n])):
            fl = ('3' if k == 0 else '8') if j == 0 else ('8' if k == n - 1 else '9')
            ET.SubElement(o, 'AP', dict(ID=str(ids.ap), Flags=fl, Index=str(j), X=f'{x:.4f}', Y=f'{y:.4f}'))
            pp.append(ids.ap)
            ids.ap += 1
        objs.append((o, pp))
    for k, (o, pp) in enumerate(objs):
        ET.SubElement(o.findall('AP')[1], 'AC', dict(ConnPtId=str(objs[(k + 1) % n][1][0])))
        ET.SubElement(o.findall('AP')[0], 'AC', dict(ConnPtId=str(objs[(k - 1) % n][1][1])))
        frame.append(o)
    fr = ET.Element('FR', dict(Color=color))
    for o, pp in objs:
        ET.SubElement(fr, 'FS', dict(Kind='0', ObjId=o.get('ID'), StartPtId=str(pp[0]), EndPtId=str(pp[1]), StartT='0.0', EndT='1.0'))
    frame.append(fr)
    return order + n


def figures(frame):
    """AC로 이어진 오브젝트 묶음(인물) → 묶음마다 (가로 중심, 발 높이, 폭)."""
    aos = [a for a in frame.findall('AO') if a.get('Color') != '0']
    par = {a.get('ID'): a.get('ID') for a in aos}
    owner = {p.get('ID'): a.get('ID') for a in aos for p in a.findall('AP')}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a in aos:
        for p in a.findall('AP'):
            for c in p.findall('AC'):
                o = owner.get(c.get('ConnPtId'))
                if o and o in par:
                    par[find(a.get('ID'))] = find(o)
    g = {}
    for a in aos:
        g.setdefault(find(a.get('ID')), []).extend((float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP'))
    out = []
    for pts in g.values():
        if len(pts) < 8:  # 작은 조각(소품·파편)은 그림자 없음
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        if not all(map(math.isfinite, xs + ys)):
            continue
        out.append(((min(xs) + max(xs)) / 2, max(ys), max(xs) - min(xs)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--scene', default='', help='night·dusk·indoor·day·cave (비우면 무작위)')
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    z = zipfile.ZipFile(a.src)
    name = z.namelist()[0]
    root = ET.fromstring(z.read(name))
    scene = a.scene or rnd.choice(list(SCENES))
    (h0, h1), (s0, s1), (v0, v1) = SCENES[scene]
    hue = rnd.uniform(h0, h1)
    sat = rnd.uniform(s0, s1)
    top = hsv(hue, sat, rnd.uniform(v0, v1))
    bot = hsv(hue + rnd.uniform(-0.05, 0.05), sat * rnd.uniform(0.6, 1.0), min(1, rnd.uniform(v0, v1) * rnd.uniform(0.9, 1.4)))
    ground = hsv(hue + rnd.uniform(-0.1, 0.1), sat * rnd.uniform(0.5, 1.0), rnd.uniform(v0, v1) * rnd.uniform(0.5, 0.8))
    dark = sum(top) / 3 < 110
    horizon = rnd.uniform(62, 82)  # 땅 시작(위에서 %)
    head = hsv(rnd.random(), rnd.uniform(0.0, 0.5), rnd.uniform(0.85, 1.0)) if dark else hsv(rnd.random(), rnd.uniform(0.2, 0.7), rnd.uniform(0.7, 1.0))
    light = hsv(rnd.uniform(0.08, 0.18), rnd.uniform(0.1, 0.5), 1.0)
    la = rnd.randint(40, 110)          # 빛 원뿔 알파(옅게)
    sa = rnd.randint(90, 180)          # 그림자 알파(실제 분위 안)
    lx = rnd.uniform(20, 80)
    # 장면 모양은 한 번만 정한다(장마다 바꾸면 배경이 깜빡이고, 면 수가 달라져 ID 구간이 어긋난다)
    nb = rnd.randint(3, 5)
    bands = [(100 * (i + 1) / (nb + 1) - 10, int(rnd.uniform(0.25, 0.45) * 255)) for i in range(nb)]
    wob = [horizon + rnd.uniform(-2, 2) for _ in range(5)]
    cone = (rnd.uniform(18, 30), rnd.uniform(18, 30))
    ids = Ids(root)
    print('장면', scene, '위', top, '아래', bot, '땅', ground, '어두움', dark)
    root.set('BackgroundColor', str(int(argb(*top)) - (1 << 32)))
    for fr in root.findall('Frame'):
        fr.set('BackgroundColor', argb(*top))
        aos = fr.findall('AO')
        if not aos:
            continue
        # 레이어: 배경 0 / 원래 레이어 +1 / 빛 맨 위
        defs = fr.findall('LayerDef')
        if not defs:  # 옛 형식: 원래 그림을 레이어 하나로
            d = ET.Element('LayerDef', dict(ID='0', Name='Layer 1', Visible='true', Locked='false'))
            fr.insert(0, d)
            defs = [d]
            for o in aos:
                o.set('LayerId', '0')
        for d in defs:
            d.set('ID', str(int(d.get('ID')) + 1))
        for o in aos:
            o.set('LayerId', str(int(o.get('LayerId') or 0) + 1))
        pos = list(fr).index(defs[0])
        fr.insert(pos, ET.Element('LayerDef', dict(ID='0', Name='배경', Visible='true', Locked='false')))
        top_id = str(max(int(d.get('ID')) for d in defs) + 1)
        fr.insert(list(fr).index(defs[-1]) + 1, ET.Element('LayerDef', dict(ID=top_id, Name='빛', Visible='true', Locked='false')))
        bottom_layer, top_layer = '0', top_id
        hi = max(int(o.get('DrawOrder') or o.get('ID')) for o in aos)
        figs = figures(fr)
        # 4) 어두운 바탕: 검은 선을 밝게
        if dark:
            for o in aos:
                if o.get('Color') in ('-16777216', '4278190080'):
                    o.set('Color', argb(235, 235, 235))
        # 2) 머리 채우기
        for o in aos:
            if o.get('TypeId') == '2' and o.get('Color') != '0':
                r = ET.Element('FR', dict(Color=argb(*head)))
                ET.SubElement(r, 'FS', dict(Kind='1', ObjId=o.get('ID')))
                fr.append(r)
        # 1) 배경(맨 아래): 바탕 면 → 그라데이션 띠 → 땅
        order = hi + 1000
        ids.at(0)
        order = poly(fr, ids, [(-2, -2), (102, -2), (102, 102), (-2, 102)], argb(*top), order, bottom_layer)
        for y0, ba in bands:
            order = poly(fr, ids, [(-2, y0), (102, y0), (102, 102), (-2, 102)], argb(*bot, ba), order, bottom_layer)
        gp = [(-2, wob[0])] + [(25 * i, wob[i]) for i in range(1, 4)] + [(102, wob[4]), (102, 102), (-2, 102)]
        order = poly(fr, ids, gp, argb(*ground), order, bottom_layer)
        # 3) 그림자(땅 위, 인물 아래)
        for k, (cx, fy, w) in enumerate(figs[:40]):
            ids.at(1000 + 20 * k)
            rw, rh = max(w * 0.6, 4), max(w * 0.12, 1.2)
            pts = [(cx + rw * math.cos(t), fy + rh * math.sin(t)) for t in [2 * math.pi * k / 16 for k in range(16)]]
            order = poly(fr, ids, pts, argb(0, 0, 0, sa), order, bottom_layer)
        # 3) 빛 원뿔(맨 위, 반투명)
        order += 100
        ids.at(5000)
        poly(fr, ids, [(lx - 4, -2), (lx + 4, -2), (lx + cone[0], 102), (lx - cone[1], 102)], argb(*light, la), order, top_layer)
    xml = ET.tostring(root, encoding='unicode')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as zz:
        zz.writestr(name, '<?xml version="1.0" encoding="UTF-8" ?>' + xml)


if __name__ == '__main__':
    main()
