"""캐릭터 시트(양식 v2) 읽기 → 스틱맨 컴파일에 입히기(재계획 단계 1-②).

시트 규칙(data/templates/character_sheet_v2_guide.png): 레이어 '캐릭터 디자인'(ID 0)에 칸마다 그림.
칸 안에서 머리 원(TypeId 2)과 연결(AC)로 이어진 묶음 = 몸 뼈대, 나머지 묶음 = 액세서리.
액세서리는 가장 가까운 부위(머리·몸통·팔·다리 마디)에 붙여 그 부위의 국소 좌표로 저장하고, 장마다 그 부위를 따라 옮긴다.
v1 범위: 정면 칸만 사용, 액세서리는 단단한 부품(흔들림·방향별 칸 선택은 다음 단계).
"""
import math, sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import character_sheet_template as T  # noqa: E402

ASPECT = 0.5625
BONES = [('torso', 'neck', 'pelvis'), ('uarm_r', 'neck', 'elb_r'), ('farm_r', 'elb_r', 'wri_r'), ('uarm_l', 'neck', 'elb_l'),
         ('farm_l', 'elb_l', 'wri_l'), ('thigh_r', 'pelvis', 'kne_r'), ('shin_r', 'kne_r', 'ank_r'), ('thigh_l', 'pelvis', 'kne_l'),
         ('shin_l', 'kne_l', 'ank_l')]


def iso(p):            # 화면 % → 가로세로 같은 단위
    return (p[0], p[1] * ASPECT)


def pct(q):
    return (q[0], q[1] / ASPECT)


def load(path):
    z = zipfile.ZipFile(path)
    return ET.fromstring(z.read([n for n in z.namelist() if n.endswith('.xml')][0]))


def slot_boxes():
    b = {n: s for n, s in zip(T.TOP, T.top_slots())}
    b.update({n: s for n, s in zip(T.BOT, T.bot_slots())})
    return b


def components(aos):
    pid2ao = {p.get('ID'): a.get('ID') for a in aos for p in a.findall('AP')}
    adj = {a.get('ID'): set() for a in aos}
    for a in aos:
        for p in a.findall('AP'):
            for c in p.findall('AC'):
                o = pid2ao.get(c.get('ConnPtId'))
                if o and o != a.get('ID'):
                    adj[a.get('ID')].add(o); adj[o].add(a.get('ID'))
    seen, out = set(), []
    for a in aos:
        if a.get('ID') in seen: continue
        st, comp = [a.get('ID')], []
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); st.extend(adj[x])
        out.append(comp)
    return out


def pts(a):
    return [(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')]


def skeleton_joints(byid, comp):
    """뼈대 묶음 → 관절 12개(정면 기준: 화면 왼쪽 = 캐릭터 오른쪽)."""
    head = next(byid[i] for i in comp if byid[i].get('TypeId') == '2')
    h = pts(head)
    lines = [byid[i] for i in comp if byid[i].get('TypeId') == '1']
    ends = [tuple(pts(a)) for a in lines]
    # 목 = 머리 원에서 가까운 점, 정수리 = 반대쪽
    c0, c1 = h
    neck_guess = min((p for e in ends for p in e), key=lambda p: min(math.dist(iso(p), iso(c0)), math.dist(iso(p), iso(c1))))
    head_b = min(h, key=lambda p: math.dist(iso(p), iso(neck_guess))); head_t = h[1] if head_b == h[0] else h[0]
    def near(p, q): return math.dist(iso(p), iso(q)) < 0.8
    from_neck = [e for e in ends if near(e[0], neck_guess) or near(e[1], neck_guess)]
    other = lambda e, p: e[1] if near(e[0], p) else e[0]
    # 몸통 = 목에서 나가는 선 중 가장 긴 것(아래로)
    torso = max(from_neck, key=lambda e: math.dist(iso(e[0]), iso(e[1])))
    pelvis = other(torso, neck_guess)
    arms = [e for e in from_neck if e is not torso]
    legs = [e for e in ends if (near(e[0], pelvis) or near(e[1], pelvis)) and e is not torso]
    J = dict(head_t=head_t, head_b=head_b, neck=neck_guess, pelvis=pelvis)
    for side_list, (a1, a2) in ((arms, ('elb', 'wri')), (legs, ('kne', 'ank'))):
        root = neck_guess if a1 == 'elb' else pelvis
        mids = sorted((other(e, root) for e in side_list), key=lambda p: p[0])[:2]
        for nm, m in zip(('r', 'l'), mids):   # 정면: 화면 왼쪽 = 캐릭터 오른쪽
            J[f'{a1}_{nm}'] = m
            tip = [e for e in ends if (near(e[0], m) or near(e[1], m)) and not (near(e[0], root) or near(e[1], root))]
            J[f'{a2}_{nm}'] = other(tip[0], m) if tip else m
    return J, head, lines


def frame_of(J, bone):
    """부위의 국소 좌표계: 원점, 축(길이 포함)."""
    if bone == 'head':
        a, b = iso(J['head_b']), iso(J['head_t'])
    else:
        _, s, e = next(x for x in BONES if x[0] == bone)
        a, b = iso(J[s]), iso(J[e])
    return a, (b[0] - a[0], b[1] - a[1])


def to_local(p, frame):
    (ax, ay), (dx, dy) = frame
    L2 = dx * dx + dy * dy or 1e-9
    x, y = iso(p)
    rx, ry = x - ax, y - ay
    return ((rx * dx + ry * dy) / L2, (-rx * dy + ry * dx) / L2)


def from_local(u, frame):
    (ax, ay), (dx, dy) = frame
    return pct((ax + u[0] * dx - u[1] * dy, ay + u[0] * dy + u[1] * dx))


def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1e-9)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def closed_loop(objs):
    """직선 묶음이 닫힌 고리면 [(객체 번호, 시작 점 번호, 끝 점 번호)]를 고리 순서로, 아니면 None."""
    if not objs or any(o['type'] != '1' or len(o['pts']) != 2 for o in objs): return None
    nxt = {}
    for oi, o in enumerate(objs):
        for pj, p in enumerate(o['pts']):
            for c in p['conn']:
                nxt.setdefault((oi, pj), set()).add(tuple(c))
    order, cur, used = [], (0, 0), set()
    for _ in range(len(objs)):
        oi, pj = cur
        if oi in used: return None
        used.add(oi); order.append((oi, pj, 1 - pj))
        ends = [c for c in nxt.get((oi, 1 - pj), ()) if c[0] not in used or (len(used) == len(objs) and c[0] == 0)]
        if len(used) == len(objs):
            return order if any(c[0] == 0 for c in nxt.get((oi, 1 - pj), ())) else None
        if not ends: return None
        cur = ends[0]
    return None


def read(path, view='정면'):
    root = load(path)
    f = root.findall('Frame')[0]
    x0, x1, y0, y1 = slot_boxes()[view]
    aos = [a for a in f.findall('AO') if a.get('LayerId') == '0' and all(x0 < X < x1 and y0 < Y < y1 for X, Y in pts(a))]
    byid = {a.get('ID'): a for a in aos}
    comps = components(aos)
    sk = next(c for c in comps if any(byid[i].get('TypeId') == '2' for i in c))
    J, head, lines = skeleton_joints(byid, sk)
    hc = ((J['head_t'][0] + J['head_b'][0]) / 2, (J['head_t'][1] + J['head_b'][1]) / 2)
    hr = math.dist(iso(J['head_t']), iso(J['head_b'])) / 2
    acc = []
    for c in comps:
        if c is sk: continue
        P = [p for i in c for p in pts(byid[i])]
        cen = (sum(p[0] for p in P) / len(P), sum(p[1] for p in P) / len(P))
        if math.dist(iso(cen), iso(hc)) <= hr * 1.1:
            bone = 'head'
        else:
            # 붙는 자리 = 뼈대에 가장 가까운 액세서리 점(망토는 목에 닿은 점). 같은 거리면 BONES 순서(몸통 먼저).
            def d(b): return min(seg_dist(iso(p), iso(J[b[1]]), iso(J[b[2]])) for p in P)
            best = min(d(b) for b in BONES)
            bone = next(b for b in BONES if d(b) <= best + 0.15)[0]
        fr_ = frame_of(J, bone)
        objs = []
        pid_index = {p.get('ID'): (k, j) for k, i in enumerate(c) for j, p in enumerate(byid[i].findall('AP'))}
        for i in c:
            a = byid[i]
            objs.append(dict(type=a.get('TypeId'), color=a.get('Color'), th=float(a.get('ThicknessScale')),
                             pts=[dict(flags=p.get('Flags'), uv=to_local((float(p.get('X')), float(p.get('Y'))), fr_),
                                       conn=[pid_index[x.get('ConnPtId')] for x in p.findall('AC') if x.get('ConnPtId') in pid_index])
                                  for p in a.findall('AP')]))
        loop = closed_loop(objs)
        # 흰 채우기(사용자 11-05 "가면이랑 머리에 하얀색 칠 — 중요"): 머리에 붙은 닫힌 모양(가면)은 안을 흰색으로
        acc.append(dict(bone=bone, objects=objs, fill_loop=loop if (loop and bone == 'head') else None))
    body = lines[0]
    return dict(view=view, joints=J, body_color=body.get('Color'), body_th=float(body.get('ThicknessScale')),
                head_fill=any(fs.get('ObjId') == head.get('ID') for x in f.findall('FR') for fs in x.findall('FS')),
                accessories=acc)


ACC_AO0, ACC_PT0 = 4570000, 900000000
VIEW_ANGLE = {'정면': 0.0, '우측': 90.0, '후면': 180.0, '좌측': 270.0}   # 반측면은 좌우가 정해지지 않아 v1은 고르지 않음
VIEW_INDEX = {'정면': 0, '우측': 1, '후면': 2, '좌측': 3}


def read_all(path):
    """그려진 방향 칸을 모두 읽는다 → {칸 이름: read() 결과}. 머리 원이 없는(빈) 칸은 건너뛴다."""
    out = {}
    for v in VIEW_ANGLE:
        try:
            out[v] = read(path, v)
        except StopIteration:
            pass
    return out


def pick_view(views, facing):
    """몸 방향(도)에 가장 가까운 칸. 모르면 정면(없으면 아무 칸)."""
    if facing is None:
        return views.get('정면') or next(iter(views.values()))
    def gap(v): d = abs((facing - VIEW_ANGLE[v]) % 360); return min(d, 360 - d)
    return views[min(views, key=gap)]


def accessory_xml(sheet, n, slot, J, body_th_frame):
    """한 장·한 인물의 액세서리 AO들(객체 ID는 모든 장에서 같게, 점 ID는 장마다 새로).
    칸마다 객체 ID 구간을 따로 둔다(칸마다 액세서리 수·종류가 달라 같은 ID가 장에 따라 다른 모양이 되지 않게)."""
    vi = VIEW_INDEX.get(sheet.get('view'), 0)
    out, k, npt = [], vi * 100, 0
    ratio = body_th_frame / (sheet['body_th'] or 1)
    for ai, acc in enumerate(sheet['accessories']):
        fr_ = frame_of(J, acc['bone'])
        k0 = k
        ids = {}
        for oi, o in enumerate(acc['objects']):
            for pj, _ in enumerate(o['pts']):
                ids[(oi, pj)] = ACC_PT0 + n * 10000 + slot * 1000 + npt; npt += 1   # 액세서리 전체에서 이어 세기(겹침 방지)
        for oi, o in enumerate(acc['objects']):
            oid = ACC_AO0 + slot * 1000 + k; k += 1
            s = [f'<AO ID="{oid}" TypeId="{o["type"]}" DrawOrder="{oid}" Color="{o["color"]}" LayerId="0" ThicknessScale="{o["th"] * ratio:.3f}" '
                 'ObjectScale="1.0" GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
            for pj, p in enumerate(o['pts']):
                x, y = from_local(p['uv'], fr_)
                s.append(f'<AP ID="{ids[(oi, pj)]}" Flags="{p["flags"]}" Index="{pj}" X="{x:.4f}" Y="{y:.4f}">'
                         + ''.join(f'<AC ConnPtId="{ids[tuple(c)]}"/>' for c in p['conn']) + '</AP>')
            s.append('</AO>')
            out.append(''.join(s))
        if acc.get('fill_loop'):
            fs = ''.join(f'<FS Kind="0" ObjId="{ACC_AO0 + slot * 1000 + k0 + oi}" StartPtId="{ids[(oi, a_)]}" EndPtId="{ids[(oi, b_)]}" '
                         f'StartT="{float(a_):.1f}" EndT="{float(b_):.1f}" />' for oi, a_, b_ in acc['fill_loop'])
            out.append(f'<FR ID="{7900000 + n * 100 + slot * 10 + ai}" Color="-1">{fs}</FR>')
    return ''.join(out)
