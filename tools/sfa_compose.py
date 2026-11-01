#!/usr/bin/env python3
"""조합 문제 만들기(2026-11-01, 사용자: "자료에서 일부를 떼 와 같은 오브젝트라도 위치를 랜덤하게, 처음에는 적은 양에서 점차 많게").
목적: 400여 작품을 외우는 것이 아니라 '보이는 것을 스파로 옮겨 그리는 실력'. 문제마다 자리·크기·조합이 달라 외울 정답이 없다.

- 묶음(unit): 한 장에서 관절 연결(AC) 또는 같은 면(FR)으로 이어진 오브젝트들. 스틱맨 한 명·칼 하나·면과 테두리가 통째로 움직인다
  (관절 하나씩 흩으면 스틱맨 모양을 못 배운다). 숨긴 레이어·안 보이는 오브젝트만의 묶음은 뺀다.
- 조합 장: 목표 오브젝트 수(1 ~ 수백, 로그 고르게)까지 여러 파일의 묶음을 무작위 크기·자리·좌우 반전으로 놓는다. 기하 점(원은 지름 원) 기준 화면 안 — 굵기·글로우·면 바깥 T까지는 보장하지 않음.
  좌표는 화면 화소 비율로 옮겨(세로 × 원래 비율 ÷ 새 비율) 원은 원, 모양은 그대로. 묶음마다 레이어를 새로 만들어 앞뒤 순서를 무작위로.
- 실제 장(약 30%): 실제 한 장 전체를 무작위 이동·확대·반전·굵기 배율(seq_data.augment) — 실제 애니의 겹침·가림 배치를 배우게.
정답은 바뀐 SFA를 sfa_tokens.encode로 다시 적으므로 그림과 정답이 같이 바뀐다.
"""
import copy
import json
import math
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_tokens as K  # noqa: E402

MAX_UNIT_OBJS = 300
BG_AREA = 0.4        # 원래 화면의 이 비율 이상을 덮는 묶음은 배경 — 맨 아래에 원래 크기·자리 그대로(앞에 놓이면 모두 가린다)
BG_PROB = 0.3        # 조합 장에 배경 묶음을 하나 깔 확률
REAL_FRAC = 0.3
LOPAC_AUG = 0.1      # 조합 장에서 묶음 레이어마다 이 확률로 레이어 투명도(15–90)를 붙인다 — 수집 자료에 없는 새 앱 기능의 학습 예시(11-02 사용자)
WHITE = str(-1)


def load(rel, root_dir):
    with zipfile.ZipFile(os.path.join(root_dir, rel)) as z:
        return ET.fromstring(z.read(z.namelist()[0]))


def units_of(fr, hwr, max_objs=MAX_UNIT_OBJS):
    """한 장 → 묶음 목록. 묶음 = dict(aos=[AO], frs=[FR], n=오브젝트 수, hwr=원래 비율). 원본 요소를 복사해 둔다."""
    defs = fr.findall('LayerDef')   # GPT 1라운드 ②: '정의 없음'과 '모두 숨김'을 구분(예전 `or None`은 모두 숨긴 장을 되살렸다)
    vis_layers = {d.get('ID') for d in defs if d.get('Visible') != 'false'} if defs else None
    aos = [a for a in fr.findall('AO') if vis_layers is None or a.get('LayerId', '0') in vis_layers]
    by_id = {a.get('ID'): a for a in aos}
    owner = {p.get('ID'): a.get('ID') for a in aos for p in a.findall('AP')}
    par = {k: k for k in by_id}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def join(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            par[rx] = ry
    for a in aos:
        for p in a.findall('AP'):
            for ac in p.findall('AC'):
                o = owner.get(ac.get('ConnPtId'))
                if o in by_id:
                    join(a.get('ID'), o)
    frs = []
    for r in fr.findall('FR'):
        ids = [s.get('ObjId') for s in r.findall('FS')]
        if not ids or any(i not in by_id for i in ids):
            continue   # 숨긴 레이어 등 빠진 오브젝트를 참조하는 면은 버린다
        for i in ids[1:]:
            join(ids[0], i)
        frs.append(r)
    filled = {s.get('ObjId') for r in frs if K._alpha(r.get('Color')) > 0 for s in r.findall('FS')}
    groups = {}
    for a in aos:
        groups.setdefault(find(a.get('ID')), []).append(a)
    rank = {a.get('ID'): k for k, (_, a) in enumerate(K.order_objects(None, fr))}   # 원래 그리는 순서(실제 장 일부 자르기에서 앞뒤 유지)
    out = []
    for g in groups.values():
        ids = {a.get('ID') for a in g}
        vis = any(K._alpha(a.get('Color')) > 0 or K.style_of(a)[2] is not None or a.get('ID') in filled for a in g)
        if not vis or (max_objs and len(g) > max_objs) or any(not a.findall('AP') for a in g):
            continue
        ufr = [r for r in frs if r.findall('FS')[0].get('ObjId') in ids]
        used = {a.get('LayerId', '0') for a in g}
        out.append(dict(aos=[copy.deepcopy(a) for a in g], frs=[copy.deepcopy(r) for r in ufr], n=len(g), hwr=hwr,
                        z=min(rank.get(i, 1 << 30) for i in ids),
                        layers=[d.get('ID') for d in defs if d.get('ID') in used],   # 원래 레이어 그리는 순서(GPT 코드 검토 I-09)
                        lop={d.get('ID'): d.get('Opacity') for d in defs if d.get('ID') in used and d.get('Opacity') is not None}))
    return out


def _pts(u):
    return [p for a in u['aos'] for p in a.findall('AP')]


def bbox_px(u):
    """화면 화소 비율 좌표(가로 %, 세로 % × 비율)의 경계 상자. 원은 지름 두 점의 원."""
    xs, ys = [], []
    h = u['hwr']
    for a in u['aos']:
        xy = [(float(p.get('X')), float(p.get('Y')) * h) for p in a.findall('AP')]
        if a.get('TypeId') == '2' and len(xy) >= 2:
            (x0, y0), (x1, y1) = xy[:2]
            cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0) / 2
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        else:
            xs += [x for x, _ in xy]
            ys += [y for _, y in xy]
    return min(xs), min(ys), max(xs), max(ys)


T_LO, T_HI = K.TMIN, 3.09   # 정답 문장이 담는 면 T 범위


def _mirror_t(t0, t1):
    """좌우 반전된 원에서 같은 경로의 T: 렌더러 θ(t)=θ0+2πt(시계 방향, circ_off=0)를 거울에 비추면 t → −t.
    두 끝점에 같은 정수 k를 더해도 같은 경로이므로 k − t로 범위 안에 둔다. 못 넣으면 None."""
    k = math.ceil(max(t0, t1) - 1e-9)
    a, b = k - t0, k - t1
    return (a, b) if T_LO <= min(a, b) and max(a, b) <= T_HI else None


def _circle_fs(r, circ):
    """FR 하나의 원 조각들: (FS, WHOLE인가, 같은 윤곽 조각 수)."""
    cnt = {}
    for f in r.findall('FS'):
        cnt[f.get('Contour', '0')] = cnt.get(f.get('Contour', '0'), 0) + 1
    out = []
    for f in r.findall('FS'):
        if f.get('ObjId') in circ:
            out.append((f, f.get('Kind') == '1' or f.get('StartT') is None, cnt[f.get('Contour', '0')]))
    return out


def mirror_ok(frs, circ):
    for r in frs:
        for f, whole, n in _circle_fs(r, circ):
            if not whole and _mirror_t(float(f.get('StartT')), float(f.get('EndT'))) is None:
                return False
    return True


def mirror_fs(r, circ):
    """좌우 반전에 맞춰 원 면 조각 T를 바꾼다. 독립 WHOLE 원(윤곽에 조각 하나)은 그대로(방향 무관),
    복합 윤곽 안 WHOLE 원은 0→1 대신 1→0 구간으로(이어 붙이는 방향 유지). 직선·곡선은 점을 옮기면 같은 T로 거울상."""
    for f, whole, n in _circle_fs(r, circ):
        if whole:
            if n > 1:
                f.set('Kind', '0')
                f.set('StartT', '1.0')
                f.set('EndT', '0.0')
            continue
        a, b = _mirror_t(float(f.get('StartT')), float(f.get('EndT')))
        f.set('StartT', repr(a))
        f.set('EndT', repr(b))


def strip_hidden(fr):
    """숨긴 레이어의 오브젝트·레이어 정의를 지우고, 없는 오브젝트를 참조하는 면과 없는 점으로의 연결을 지운다
    (GPT 1라운드 ①: 렌더러는 면 첫 참조가 숨김이면 면을 숨기고, 정답 변환은 남은 참조로 면을 다시 적어 그림과 정답이 달라졌다)."""
    hid = {d.get('ID') for d in fr.findall('LayerDef') if d.get('Visible') == 'false'}
    for d in list(fr.findall('LayerDef')):
        if d.get('ID') in hid:
            fr.remove(d)
    for a in list(fr.findall('AO')):
        if a.get('LayerId', '0') in hid:
            fr.remove(a)
    keep_frame_refs(fr)
    return fr


def keep_frame_refs(fr):
    ids = {a.get('ID') for a in fr.findall('AO')}
    pts = {p.get('ID') for a in fr.findall('AO') for p in a.findall('AP')}
    for r in list(fr.findall('FR')):
        if any(f.get('ObjId') not in ids for f in r.findall('FS')) or not r.findall('FS'):
            fr.remove(r)
    for a in fr.findall('AO'):
        for p in a.findall('AP'):
            for ac in list(p.findall('AC')):
                if ac.get('ConnPtId') not in pts:
                    p.remove(ac)


def snap_th(v):
    """굵기를 정답 문장의 굵기 칸 값으로(그림과 정답이 정확히 같은 굵기 — 0.01 미만은 칸 최솟값으로 잘리던 것)."""
    return K.dq_th(K.q_th(v)) if v > 0 else v


class Ids:
    def __init__(self):
        self.ao = self.ap = 1000
        self.layer = 0


def is_bg(u):
    x0, y0, x1, y1 = bbox_px(u)
    return (min(x1, 100) - max(x0, 0)) * (min(y1, 100 * u['hwr']) - max(y0, 0)) >= BG_AREA * 100 * 100 * u['hwr']


def place(u, fr, hwr, rng, ids, z, keep=False):
    """묶음 하나를 장에 놓는다: 무작위 크기·자리·좌우 반전(화면 안), ID 새로. z = 이 묶음의 레이어 순서 시작."""
    x0, y0, x1, y1 = bbox_px(u)
    W, Hh = 100.0, 100.0 * hwr
    w, h = max(x1 - x0, 1e-3), max(y1 - y0, 1e-3)
    fit = min(W / w, Hh / h) * 0.98
    if keep:   # 배경: 원래 크기·자리(화면 화소 비율 그대로). keep='exact'면 반전도 없음
        s, flip, tx, ty, th = 1.0, keep != 'exact' and rng.random() < 0.5, x0, y0, 1.0
    else:
        s = math.exp(rng.uniform(math.log(0.35), math.log(1.6)))   # 원래 크기 기준
        s = min(s, fit)
        flip = rng.random() < 0.5
        tx = rng.uniform(0, W - w * s)
        ty = rng.uniform(0, Hh - h * s)
        th = s ** 0.5 * math.exp(rng.uniform(math.log(0.7), math.log(1.4)))   # 굵기: 크기를 조금 따르고 무작위
    circ = {a.get('ID') for a in u['aos'] if a.get('TypeId') == '2'}
    if flip and not mirror_ok(u['frs'], circ):
        flip = False   # 원 면 T를 범위 안으로 옮길 수 없으면 반전하지 않는다
    hs = u['hwr']
    old_layers = list(u.get('layers') or [])   # 원래 LayerDef 순서(그리는 순서) — AO가 XML에 나온 순서가 아니다(GPT 코드 검토 I-09: 묶음 안 가림이 바뀌었다)
    for a in u['aos']:
        if a.get('LayerId', '0') not in old_layers:
            old_layers.append(a.get('LayerId', '0'))
    lmap = {}
    for k, lid in enumerate(old_layers):
        ids.layer += 1
        lmap[lid] = str(ids.layer)
        ld = ET.Element('LayerDef', dict(ID=lmap[lid], Name=f'L{ids.layer}', Visible='true', Locked='false'))
        op = (u.get('lop') or {}).get(lid)
        if op is None and not keep and rng.random() < LOPAC_AUG:
            op = str(rng.randint(15, 90))
        if op is not None:
            ld.set('Opacity', op)
        z.append(ld)
    aomap, apmap = {}, {}
    new_aos = []
    for a in sorted(u['aos'], key=lambda a: int(a.get('DrawOrder') or a.get('ID') or 0)):
        b = copy.deepcopy(a)
        ids.ao += 1
        aomap[a.get('ID')] = str(ids.ao)
        b.set('ID', str(ids.ao))
        b.set('LayerId', lmap[a.get('LayerId', '0')])
        b.set('DrawOrder', str(ids.ao))
        b.set('ThicknessScale', repr(snap_th(float(a.get('ThicknessScale') or 1) * th)))
        for p in b.findall('AP'):
            ids.ap += 1
            apmap[p.get('ID')] = str(ids.ap)
            p.set('ID', str(ids.ap))
            x, y = float(p.get('X')), float(p.get('Y')) * hs
            x = x1 - (x - x0) if flip else x
            p.set('X', repr((x - x0) * s + tx))
            p.set('Y', repr(((y - y0) * s + ty) / hwr))
        new_aos.append(b)
    for b in new_aos:
        for p in b.findall('AP'):
            for ac in list(p.findall('AC')):
                if ac.get('ConnPtId') in apmap:
                    ac.set('ConnPtId', apmap[ac.get('ConnPtId')])
                else:
                    p.remove(ac)
    for b in new_aos:
        fr.append(b)
    for r in u['frs']:
        r2 = copy.deepcopy(r)
        if flip:
            mirror_fs(r2, circ)   # 원 면 T도 좌우 반전에 맞춘다(GPT 1라운드 ④)
        for fs in r2.findall('FS'):
            fs.set('ObjId', aomap[fs.get('ObjId')])
            for k in ('StartPtId', 'EndPtId'):
                if fs.get(k) in apmap:
                    fs.set(k, apmap[fs.get(k)])
        fr.append(r2)
    return s, flip


def compose(pool, rng, n_target, hwr, bg_pool=None):
    """조합 장 하나 → (Sequence, Frame). pool = 일반 묶음, bg_pool = 배경 묶음."""
    seq = ET.Element('Sequence', dict(Name='compose', HeightWidthRatio=repr(hwr), FrameCount='1', BackgroundColor=WHITE))
    fr = ET.SubElement(seq, 'Frame', dict(ID='1', Position='0'))
    bgs = [u.get('bg', WHITE) for u in rng.sample(pool, min(3, len(pool)))]
    fr.set('BackgroundColor', WHITE if rng.random() < 0.6 else bgs[0])
    ids = Ids()
    layers = []
    n = 0
    tries = 0
    units = []
    if bg_pool and n_target >= 5 and rng.random() < BG_PROB:
        b = rng.choice(bg_pool)
        if b['n'] <= n_target:
            place(b, fr, hwr, rng, ids, layers, keep=True)
            n += b['n']
    while n < n_target and tries < 200:
        tries += 1
        u = rng.choice(pool)
        if n + u['n'] > max(n_target * 1.3, n_target + 1):
            continue
        units.append(u)
        n += u['n']
    for u in units:
        place(u, fr, hwr, rng, ids, layers)
    seq.set('src', json.dumps(dict(kind='comp', n_target=n_target, units=[[u.get('src'), u.get('pos'), u['n']] for u in units]),
                              ensure_ascii=False))   # 출처(⑦)
    for k, d in enumerate(layers):   # 레이어 정의는 장 앞쪽에(묶음 놓은 순서 = 앞뒤 순서)
        fr.insert(k, d)
    return seq, fr


def build_pool(files, root_dir, rng, frames_per_file=6):
    """학습 파일에서 묶음 모으기(파일마다 장 몇 개). 묶음에 원래 배경색도 붙인다."""
    pool, hwrs = [], []
    for rel in files:
        try:
            root = load(rel, root_dir)
        except Exception:
            continue
        hwr = float(root.get('HeightWidthRatio') or 0.5625) or 0.5625
        hwrs.append(hwr)
        frs = root.findall('Frame')
        for fr in rng.sample(frs, min(frames_per_file, len(frs))):
            bg = fr.get('BackgroundColor', root.get('BackgroundColor', WHITE))
            for u in units_of(fr, hwr):
                u['bg'] = bg
                u['src'] = rel
                u['pos'] = fr.get('Position')
                pool.append(u)
    bgp = [u for u in pool if is_bg(u)]
    pool = [u for u in pool if not is_bg(u)]
    return pool, bgp, hwrs


def real_frame(root, fr, rng, hwr, src=None):
    """실제 한 장 전체를 장마다 따로 무작위 변환(좌우 반전·0.7–1.25배·±12% 이동·굵기 0.5–2배). 화면 밖은 정답 변환이 뺀다.
    파일 하나의 장들이 모두 다른 자리·크기로 나와 외울 자리가 없다(seq_data.augment는 파일 전체에 같은 변환 하나).
    숨긴 레이어는 지운다(①). 반전하면 원 면 T도 맞춘다(④). 출처·변환은 Sequence의 src 속성(JSON)에 남긴다(⑦)."""
    seq = ET.Element('Sequence', dict(Name='real', HeightWidthRatio=repr(hwr), FrameCount='1',
                                      BackgroundColor=root.get('BackgroundColor', WHITE)))
    f2 = strip_hidden(copy.deepcopy(fr))
    f2.set('Position', '0')
    seq.append(f2)
    flip = rng.random() < 0.5
    sc = rng.uniform(0.7, 1.25)
    tx, ty = rng.uniform(-12, 12), rng.uniform(-12, 12)
    th = math.exp(rng.uniform(math.log(0.5), math.log(2.0)))
    circ = {a.get('ID') for a in f2.findall('AO') if a.get('TypeId') == '2'}
    if flip and not mirror_ok(f2.findall('FR'), circ):
        flip = False
    for p in f2.iter('AP'):
        x, y = float(p.get('X')), float(p.get('Y'))
        x = 100 - x if flip else x
        p.set('X', repr((x - 50) * sc + 50 + tx))
        p.set('Y', repr((y - 50) * sc + 50 + ty))
    if flip:
        for r in f2.findall('FR'):
            mirror_fs(r, circ)
    for o in f2.iter('AO'):
        o.set('ThicknessScale', repr(snap_th(float(o.get('ThicknessScale') or 1) * th)))
    info = dict(src or {}, flip=flip, scale=round(sc, 4), tx=round(tx, 3), ty=round(ty, 3), thick=round(th, 4))
    seq.set('src', json.dumps(info, ensure_ascii=False))
    return seq, f2


def n_target(rng, lo=1, hi=250):
    """목표 오브젝트 수: 로그 고르게(작은 문제부터 큰 문제까지 고루 — 학습기가 쉬운 것부터 순서를 정한다)."""
    return int(round(math.exp(rng.uniform(math.log(lo), math.log(hi)))))


def subset(fr, keep_ids, bg, hwr):
    """원본 장 복사본에서 keep_ids 밖 오브젝트를 지운 장(GPT 1라운드 ③: 원래 레이어·그리기 순서·배경을 그대로 보존)."""
    seq = ET.Element('Sequence', dict(Name='crop', HeightWidthRatio=repr(hwr), FrameCount='1', BackgroundColor=bg))
    f2 = strip_hidden(copy.deepcopy(fr))
    for a in list(f2.findall('AO')):
        if a.get('ID') not in keep_ids:
            f2.remove(a)
    keep_frame_refs(f2)
    f2.set('Position', '0')
    seq.append(f2)
    return seq, f2


def _fit(order_ids, fr, bg, hwr, maxlen):
    """앞에서부터 몇 개를 담아야 정답 길이 한도 안에서 가장 많은가(이분 탐색). order_ids = [오브젝트 ID 묶음, ...]."""
    def build(k):
        return subset(fr, {i for g in order_ids[:k] for i in g}, bg, hwr)
    if len(K.encode(*build(1))[0]) > maxlen:
        return None
    lo, hi = 1, len(order_ids)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(K.encode(*build(mid))[0]) <= maxlen:
            lo = mid
        else:
            hi = mid - 1
    return build(lo)


def real_crop(fr, rng, hwr, maxlen, bg=WHITE):
    """2,048단어를 넘는 실제 장(사용자 11-01: 넘는 원본도 일부를 떼어 오면 된다): 무작위 지점에서 가까운 묶음부터 담고,
    원본 장에서 나머지를 지워 원래 자리·레이어·그리기 순서·배경을 그대로 둔다. 가장 가까운 묶음 하나도 넘치면 그 안에서 오브젝트 단위로.
    반환 (Sequence, Frame) 또는 None."""
    us = units_of(fr, hwr, max_objs=None)
    if not us:
        return None
    ax, ay = rng.uniform(0, 100), rng.uniform(0, 100 * hwr)

    def dist(u):
        x0, y0, x1, y1 = bbox_px(u)
        return math.hypot((x0 + x1) / 2 - ax, (y0 + y1) / 2 - ay)
    us.sort(key=dist)
    got = _fit([{a.get('ID') for a in u['aos']} for u in us], fr, bg, hwr, maxlen)
    if got is not None:
        return got
    u = us[0]   # 묶음 하나가 혼자 넘침: 그 묶음 안에서 가까운 오브젝트부터(빠진 오브젝트의 연결·면은 지운다)
    pts = [(a.get('ID'), [(float(p.get('X')), float(p.get('Y')) * hwr) for p in a.findall('AP')]) for a in u['aos']]
    bx, by = rng.choice([xy[0] for _, xy in pts if xy])
    pts.sort(key=lambda it: min(math.hypot(x - bx, y - by) for x, y in it[1]) if it[1] else 1e9)
    return _fit([{i} for i, _ in pts], fr, bg, hwr, maxlen)
