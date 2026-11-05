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


V2_NAME = {'우측': '우측면', '좌측': '좌측면'}   # v2 칸 이름 → v3 이름(같은 방향). v2 반측면은 좌우가 정해지지 않아 읽지 않는다


def slot_boxes(version='v3'):
    """{v3 칸 이름: (x0, x1, y0, y1)}. v2 시트는 이름을 v3로 바꿔 돌려준다."""
    if version == 'v3':
        return {n: v[:4] for n, v in T.slots_v3().items()}
    b = {V2_NAME.get(n, n): s for n, s in zip(T.TOP, T.top_slots()) if n != '반측면'}
    b.update({n: s for n, s in zip(T.BOT, T.bot_slots())})
    return b


def sheet_version(root):
    return 'v2' if 'v2' in (root.get('Name') or '') else 'v3'


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
    order = {a.get('ID'): i for i, a in enumerate(aos)}
    for a in aos:
        if a.get('ID') in seen: continue
        st, comp = [a.get('ID')], []
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); st.extend(sorted(adj[x], key=order.get))
        out.append(sorted(comp, key=order.get))   # 파일 순서로 고정(집합 순서는 실행마다 달라 객체 번호가 바뀌었다)
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
    """직선(점 2개)·곡선(점 3개) 묶음이 끝점끼리 닫힌 고리면 [(객체 번호, 시작 끝점 번호, 끝 끝점 번호)]를 고리 순서로, 아니면 None.
    (11-05: 망토는 곡선 3개 고리 — 직선만 찾던 처음 판에서 빠져 흰 채우기가 안 됐다)"""
    if not objs or any(not ((o['type'] == '1' and len(o['pts']) == 2) or (o['type'] == '3' and len(o['pts']) == 3)) for o in objs):
        return None
    last = lambda oi: len(objs[oi]['pts']) - 1
    nxt = {}
    for oi, o in enumerate(objs):
        for pj in (0, last(oi)):
            for c in o['pts'][pj]['conn']:
                nxt.setdefault((oi, pj), set()).add(tuple(c))
    order, cur, used = [], (0, 0), set()
    for _ in range(len(objs)):
        oi, pj = cur
        if oi in used: return None
        other = last(oi) if pj == 0 else 0
        used.add(oi); order.append((oi, pj, other))
        nx = nxt.get((oi, other), ())
        if len(used) == len(objs):
            return order if any(c[0] == 0 for c in nx) else None
        ends = [c for c in nx if c[0] not in used and c[1] in (0, last(c[0]))]
        if not ends: return None
        cur = ends[0]
    return None


def read(path, view='정면'):
    root = load(path)
    f = root.findall('Frame')[0]
    view = V2_NAME.get(view, view)
    x0, x1, y0, y1 = slot_boxes(sheet_version(root))[view]
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
        # 채우기 색: 시트에서 이 묶음 객체를 가리키는 FR이 있으면 그 색, 없으면 흰색(11-05 기본)
        ids_c = set(c)
        fcol = next((x.get('Color') for x in f.findall('FR') if any(fs.get('ObjId') in ids_c for fs in x.findall('FS'))), '-1')
        # 흰 채우기(사용자 11-05 "가면이랑 머리에 하얀색 칠 — 중요"): 머리에 붙은 닫힌 모양(가면)은 안을 흰색으로
        acc.append(dict(bone=bone, objects=objs, fill_loop=loop, fill_color=fcol))   # 닫힌 모양(가면·망토)은 채우기(기본 흰색, 사용자 11-05)
    body = lines[0]
    return dict(view=view, joints=J, body_color=body.get('Color'), body_th=float(body.get('ThicknessScale')),
                head_fill=any(fs.get('ObjId') == head.get('ID') for x in f.findall('FR') for fs in x.findall('FS')),
                accessories=acc)


ACC_AO0, ACC_PT0 = 4570000, 900000000
VIEW_ANGLE = dict(T.RING_ANGLE)   # v3 수평 8방향(45° 간격). 0 정면 · 90 우측면(얼굴이 화면 왼쪽, v2 '우측') · 180 후면 · 270 좌측면
VIEW_INDEX = {n: i for i, n in enumerate(T.RING)}   # 칸마다 액세서리 객체 ID 구간(0–7)


def read_all(path):
    """그려진 방향 칸을 모두 읽는다 → {칸 이름: read() 결과}. 머리 원이 없는(빈) 칸은 건너뛴다."""
    out = {}
    boxes = slot_boxes(sheet_version(load(path)))
    for v in VIEW_ANGLE:
        if v not in boxes: continue
        try:
            out[v] = read(path, v)
        except StopIteration:
            pass
    return out


def pick_view(views, facing):
    """몸 방향(도)에 가장 가까운 칸. 모르면 정면(없으면 아무 칸)."""
    views = {V2_NAME.get(k, k): x for k, x in views.items()}
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
                         f'StartT="{0.0 if a_ == 0 else 1.0:.1f}" EndT="{0.0 if b_ == 0 else 1.0:.1f}" />' for oi, a_, b_ in acc['fill_loop'])
            out.append(f'<FR ID="{7900000 + n * 100 + slot * 10 + ai}" Color="-1">{fs}</FR>')
    return ''.join(out)


# ---------- 연속 방향(11-05 사용자: "도는 모션 없이 갑자기 사라짐", "시트에서 준 그 사이가 없음", 레이어 버그) ----------
def _shape_key(acc):
    return (acc['bone'], tuple((o['type'], len(o['pts'])) for o in acc['objects']))


def rig(views):
    """칸별 액세서리를 하나의 대응 묶음으로. 기준 = 정면 칸(없으면 첫 칸). 다른 칸에서 같은 부위·같은 구조인 것을 짝으로.
    짝이 없는 칸(예: 후면의 가면)은 None → 그 방향 쪽으로 갈수록 투명해진다."""
    base_name = '정면' if '정면' in views else next(iter(views))
    base = views[base_name]
    out = []
    for acc in base['accessories']:
        per = {}
        for v, sh in views.items():
            cand = [a for a in sh['accessories'] if _shape_key(a) == _shape_key(acc)]
            per[v] = cand[0] if cand else None
        out.append(dict(per=per, ref=acc))
    return dict(views=views, base=base, accs=out)


def _neighbors(yaw, have):
    """yaw(도)를 사이에 둔 두 칸과 비율 t(0 = 앞 칸, 1 = 뒤 칸)."""
    angs = sorted(VIEW_ANGLE[v] for v in have)
    y = yaw % 360
    for i, a in enumerate(angs):
        b = angs[(i + 1) % len(angs)] + (360 if i + 1 == len(angs) else 0)
        yy = y if y >= a else y + 360
        if a <= yy <= b:
            t = 0.0 if b == a else (yy - a) / (b - a)
            name = {VIEW_ANGLE[v]: v for v in have}
            return name[a], name[b % 360], t
    return have[0], have[0], 0.0


def _with_alpha(color, alpha):
    c = int(color) & 0xFFFFFFFF
    a = int(round(((c >> 24) & 255) * max(0.0, min(1.0, alpha))))
    v = (a << 24) | (c & 0xFFFFFF)
    return v - (1 << 32) if v >= (1 << 31) else v


def rig_xml(R_, yaw, n, slot, J, body_th_frame):
    """연속 방향 액세서리: 두 이웃 칸의 국소 좌표를 비율로 섞는다. 한쪽에만 있으면 그쪽에서 멀어질수록 투명(t 0.6에서 0).
    객체 ID는 칸과 상관없이 하나(첫 장부터 항상 내보내 앱의 '처음 나온 순서'가 인물 바로 뒤로 고정 — 레이어 버그 수정)."""
    views = R_['views']
    have = [v for v in VIEW_ANGLE if v in views]
    va, vb, t = _neighbors(0.0 if yaw is None else yaw, have)
    ratio = body_th_frame / (R_['base']['body_th'] or 1)
    out, k, npt = [], 0, 0
    for ai, item in enumerate(R_['accs']):
        A, B = item['per'].get(va), item['per'].get(vb)
        ref = item['ref']
        if A is not None and B is not None:
            mix, alpha = [(A, 1 - t), (B, t)], 1.0
        elif A is not None:
            mix, alpha = [(A, 1.0)], max(0.0, 1 - t / 0.6)
        elif B is not None:
            mix, alpha = [(B, 1.0)], max(0.0, (t - 0.4) / 0.6)
        else:
            mix, alpha = [(ref, 1.0)], 0.0
        frames = [(acc, w, frame_of(J, acc['bone'])) for acc, w in mix]
        ids = {}
        for oi, o in enumerate(ref['objects']):
            for pj, _ in enumerate(o['pts']):
                ids[(oi, pj)] = ACC_PT0 + n * 10000 + slot * 1000 + npt; npt += 1
        k0 = k
        for oi, o in enumerate(ref['objects']):
            oid = ACC_AO0 + slot * 1000 + k; k += 1
            col = _with_alpha(o['color'], alpha)
            s = [f'<AO ID="{oid}" TypeId="{o["type"]}" DrawOrder="{oid}" Color="{col}" LayerId="0" ThicknessScale="{o["th"] * ratio:.3f}" '
                 'ObjectScale="1.0" GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
            for pj, p in enumerate(o['pts']):
                x = y = 0.0
                for acc, w, fr_ in frames:
                    px, py = from_local(acc['objects'][oi]['pts'][pj]['uv'], fr_)
                    x += w * px; y += w * py
                s.append(f'<AP ID="{ids[(oi, pj)]}" Flags="{p["flags"]}" Index="{pj}" X="{x:.4f}" Y="{y:.4f}">'
                         + ''.join(f'<AC ConnPtId="{ids[tuple(c)]}"/>' for c in p['conn']) + '</AP>')
            s.append('</AO>')
            out.append(''.join(s))
        if ref.get('fill_loop'):
            fs = ''.join(f'<FS Kind="0" ObjId="{ACC_AO0 + slot * 1000 + k0 + oi}" StartPtId="{ids[(oi, a_)]}" EndPtId="{ids[(oi, b_)]}" '
                         f'StartT="{0.0 if a_ == 0 else 1.0:.1f}" EndT="{0.0 if b_ == 0 else 1.0:.1f}" />' for oi, a_, b_ in ref['fill_loop'])
            out.append(f'<FR ID="{7900000 + n * 100 + slot * 10 + ai}" Color="{_with_alpha(-1, alpha)}">{fs}</FR>')
    return ''.join(out)


# ---------- 흔들리는 액세서리(망토) — 11-05 사용자: "몸을 뚫고 펄럭임이 없음" ----------
# 망토(흔들리는 액세서리) 기본 세팅 — 사용자 11-05 확정("망토라는 캐디가 들어왔을 때 지금 세팅이 기본"): 아래 값 + 밑단 2배.
SIM = dict(n=9, gravity=0.008, damping=0.04, shape=0.008, iters=12, wind=(0.0, 0.0), reset_jump=1.2, drag=0.35)
# 밑단 최소 너비(몸통 길이 대비, 칸별) — 사용자 11-05: "2배가 아니라 지금과 같은 크기. 시트에서 더 크게 들어오면 그 크기, 작으면 지금 크기".
# 값 = 예시 시트(character_sheet_v2_example) 칸별 밑단 너비 × 2(사용자가 '좋다'고 한 v5 결과). 칸 사이는 섞어 쓴다.
HEM_MIN = {'정면': 0.858, '우측면': 0.318, '후면': 0.896, '좌측면': 0.506}   # 반측면·후반측면 칸은 시트 밑단 길이만(없으면 0)
# 11-05 사용자 "형태에 너무 얽매임, 훨씬 넓게 퍼지고 펄럭여도 됨": 모양 복원 0.06→0.008, 감쇠 0.08→0.04, 중력 0.012→0.008,
# 공기 저항 drag(고정점 속도의 반대 방향, 끝으로 갈수록 크게) 추가


def flex_info(ref):
    """몸통에 붙은 곡선 3개 고리 중 두 곡선이 한 끝점(위)을 나눠 가지면 망토로 본다 → 두 가장자리와 밑단.
    v1은 이 모양만 흔든다(나머지는 단단한 부품)."""
    objs = ref['objects']
    if ref['bone'] != 'torso' or not ref.get('fill_loop') or len(objs) != 3 or any(o['type'] != '3' for o in objs):
        return None
    pairs = []
    for a in range(3):
        for b in range(a + 1, 3):
            for ea in (0, 2):
                for eb in (0, 2):
                    if (b, eb) in [tuple(c) for c in objs[a]['pts'][ea]['conn']]:
                        u = (objs[a]['pts'][ea]['uv'][0] + objs[b]['pts'][eb]['uv'][0]) / 2   # 몸통 축 위치(0 = 목)
                        pairs.append((u, a, ea, b, eb))
    if not pairs: return None
    u, a, ea, b, eb = min(pairs)   # 목에 가장 가까운 공유 끝점 = 고정점(위)
    h = 3 - a - b
    hem_conn = {}
    for e in (0, 2):
        c = [tuple(x) for x in objs[h]['pts'][e]['conn'] if tuple(x) in ((a, 2 - ea), (b, 2 - eb))]
        if not c: return None
        hem_conn[e] = c[0]
    if hem_conn[0] == hem_conn[2]: return None
    return dict(edges=[(a, ea, 2 - ea), (b, eb, 2 - eb)], hem=h, hem_conn=hem_conn)


def _quad(p0, c, p2, t):
    return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p2[1])


def _simulate(info, P, J, state, key, n, hem_min=None):
    """PBD(위치 기반 동역학) 사슬 두 줄. P = 이 장의 단단한 배치(화면 %) — 목표 모양·고정점·길이의 기준.
    중력·관성(Verlet)·감쇠·약한 모양 복원·거리 조건. 컷 등으로 고정점이 몸통 길이의 reset_jump배 넘게 뛰면 처음부터."""
    L = math.dist(iso(J['neck']), iso(J['pelvis'])) or 1.0
    N = SIM['n']
    targets = []
    for oi, top, bot in info['edges']:
        p0, c, p2 = iso(P[(oi, top)]), iso(P[(oi, 1)]), iso(P[(oi, bot)])
        targets.append([_quad(p0, c, p2, i / (N - 1)) for i in range(N)])
    ws = math.dist(targets[0][-1], targets[1][-1]) / L if len(targets) == 2 else 0
    f = max(1.0, (hem_min or 0) / ws) if ws > 1e-9 else 1.0   # 시트가 기준보다 작을 때만 기준 너비까지(크면 시트 그대로)
    if f != 1.0 and len(targets) == 2:
        for i in range(N):
            mx, my = (targets[0][i][0] + targets[1][i][0]) / 2, (targets[0][i][1] + targets[1][i][1]) / 2
            k = 1 + (f - 1) * i / (N - 1)
            for T in targets:
                T[i] = (mx + (T[i][0] - mx) * k, my + (T[i][1] - my) * k)
    st = state.get(key)
    anchor = targets[0][0]
    if st is None or st['n'] != n - 1 or math.dist(anchor, st['anchor']) > SIM['reset_jump'] * L:
        st = dict(X=[list(map(list, t)) for t in targets], Xp=[list(map(list, t)) for t in targets])
    g = SIM['gravity'] * L
    wx, wy = SIM['wind'][0] * L, SIM['wind'][1] * L
    av = (anchor[0] - st.get('anchor', anchor)[0], anchor[1] - st.get('anchor', anchor)[1]) if st.get('n') == n - 1 else (0.0, 0.0)
    for s, T in enumerate(targets):
        X, Xp = st['X'][s], st['Xp'][s]
        for i in range(N):
            vx, vy = (X[i][0] - Xp[i][0]) * (1 - SIM['damping']), (X[i][1] - Xp[i][1]) * (1 - SIM['damping'])
            Xp[i] = list(X[i])
            f = SIM['drag'] * i / (N - 1)      # 공기 저항: 몸이 가는 반대로, 끝으로 갈수록
            X[i] = [X[i][0] + vx + wx - f * av[0], X[i][1] + vy + g + wy - f * av[1]]
        rest = [math.dist(T[i], T[i + 1]) for i in range(N - 1)]
        for _ in range(SIM['iters']):
            X[0] = list(T[0])
            for i in range(N - 1):
                dx, dy = X[i + 1][0] - X[i][0], X[i + 1][1] - X[i][1]
                d = math.hypot(dx, dy) or 1e-9
                corr = (d - rest[i]) / d
                if i == 0:
                    X[i + 1][0] -= dx * corr; X[i + 1][1] -= dy * corr
                else:
                    X[i][0] += dx * corr / 2; X[i][1] += dy * corr / 2
                    X[i + 1][0] -= dx * corr / 2; X[i + 1][1] -= dy * corr / 2
            for i in range(1, N):
                X[i][0] += SIM['shape'] * (T[i][0] - X[i][0]); X[i][1] += SIM['shape'] * (T[i][1] - X[i][1])
        X[0] = list(T[0])
    # 두 가장자리 아래 끝이 시트 밑단 폭의 절반보다 가까워지지 않게(밑단이 점으로 줄어 사라지지 않게)
    A_, B_ = st['X'][0], st['X'][1]
    w0 = math.dist(targets[0][-1], targets[1][-1]) * 0.5
    for i in range(N // 2, N):
        dx, dy = B_[i][0] - A_[i][0], B_[i][1] - A_[i][1]
        d = math.hypot(dx, dy)
        need = w0 * (i - N // 2 + 1) / (N - N // 2)
        if d < need:
            if d < 1e-9: dx, dy, d = 1.0, 0.0, 1.0
            push = (need - d) / 2 / d
            A_[i][0] -= dx * push; A_[i][1] -= dy * push; B_[i][0] += dx * push; B_[i][1] += dy * push
    st.update(n=n, anchor=anchor)
    state[key] = st
    out = dict(P)
    m = (N - 1) // 2
    for (oi, top, bot), X in zip(info['edges'], st['X']):
        p0, p2, mid = X[0], X[-1], X[m]
        c = (2 * mid[0] - (p0[0] + p2[0]) / 2, 2 * mid[1] - (p0[1] + p2[1]) / 2)
        out[(oi, top)], out[(oi, 1)], out[(oi, bot)] = pct(p0), pct(c), pct(p2)
    h = info['hem']
    # 밑단: 두 끝을 시트 연결대로 이어진 가장자리 아래 끝에(11-05: '가까운 쪽'으로 붙여 두 끝이 같은 점이 되어 밑단이 사라졌다 —
    # 480개 중 382개 길이 0), 조절점은 두 끝이 움직인 평균만큼
    hp = [P[(h, 0)], P[(h, 1)], P[(h, 2)]]
    newe = []
    for e in (0, 2):
        tgt = info['hem_conn'][e]
        newe.append(out[tgt] if tgt in out else hp[e])
    # 조절점: 시트 밑단에서 두 끝 가운데 대비 조절점 위치(휨)를 두 끝 길이 비율만큼 키워 새 두 끝 가운데에
    om = ((hp[0][0] + hp[2][0]) / 2, (hp[0][1] + hp[2][1]) / 2); nm = ((newe[0][0] + newe[1][0]) / 2, (newe[0][1] + newe[1][1]) / 2)
    sc = (math.dist(iso(newe[0]), iso(newe[1])) / (math.dist(iso(hp[0]), iso(hp[2])) or 1e-9))
    out[(h, 0)], out[(h, 2)], out[(h, 1)] = newe[0], newe[1], (nm[0] + (hp[1][0] - om[0]) * sc, nm[1] + (hp[1][1] - om[1]) * sc)
    return out


def _depth_alpha(yaw):
    """망토 앞 사본의 불투명도. 얼굴(가면)이 보이는 동안은 망토가 몸 뒤여야 한다(11-05 사용자: 몸을 뚫음 — 가면은 후면에서 36°
    떨어질 때까지 보이는데 망토가 75°부터 앞으로 나왔다). 가면이 완전히 사라진 뒤(후면에서 36° 안)에만 앞 사본: 12° 안 = 1, 36° 밖 = 0.
    뒤 사본 = 1 − 이 값."""
    if yaw is None: return 0.0
    d = abs((yaw - 180 + 180) % 360 - 180)
    return 1.0 if d <= 12 else 0.0 if d >= 36 else (36 - d) / 24


def rig_frame(R_, yaw, n, slot, J, body_th_frame, state):
    """한 장·한 인물 → (몸 뒤에 그릴 XML, 몸 앞에 그릴 XML). 흔들리는 액세서리(망토)는 사슬 계산 + 뒤/앞 두 사본(앱은 '처음 나온 순서'로
    앞뒤를 정하므로 두 사본을 첫 장부터 모두 내보내고 불투명도로 하나만 보이게). 나머지는 앞 사본만."""
    views = R_['views']
    have = [v for v in VIEW_ANGLE if v in views]
    va, vb, t = _neighbors(0.0 if yaw is None else yaw, have)
    ratio = body_th_frame / (R_['base']['body_th'] or 1)
    back_out, front_out, k, npt = [], [], 0, 0
    fa = _depth_alpha(yaw)
    for ai, item in enumerate(R_['accs']):
        A, B = item['per'].get(va), item['per'].get(vb)
        ref = item['ref']
        if A is not None and B is not None:
            mix, alpha = [(A, 1 - t), (B, t)], 1.0
        elif A is not None:
            mix, alpha = [(A, 1.0)], max(0.0, 1 - t / 0.6)
        elif B is not None:
            mix, alpha = [(B, 1.0)], max(0.0, (t - 0.4) / 0.6)
        else:
            mix, alpha = [(ref, 1.0)], 0.0
        frames = [(acc, w, frame_of(J, acc['bone'])) for acc, w in mix]
        P = {}
        for oi, o in enumerate(ref['objects']):
            for pj, _ in enumerate(o['pts']):
                x = y = 0.0
                for acc, w, fr_ in frames:
                    px, py = from_local(acc['objects'][oi]['pts'][pj]['uv'], fr_)
                    x += w * px; y += w * py
                P[(oi, pj)] = (x, y)
        info = flex_info(ref)
        if info is not None:
            hm = (1 - t) * HEM_MIN.get(va, 0) + t * HEM_MIN.get(vb, 0)
            P = _simulate(info, P, J, state, (slot, ai), n, hem_min=hm)
            copies = [(back_out, 500, alpha * (1 - fa)), (front_out, 0, alpha * fa)]
        else:
            copies = [(front_out, 0, alpha)]
        for dest, base, al in copies:
            fill_col = ref.get('fill_color', '-1')
            same = info is not None and all((int(o['color']) & 0xFFFFFFFF) == (int(fill_col) & 0xFFFFFFFF) for o in ref['objects'])
            if info is not None and ref.get('fill_loop') and not same:
                # 11-05 사용자: 변형되는 망토에서 페인트가 망토 선을 가림 → 장마다 그 모양을 따라 새로 만든 투명 테두리에 흰 채우기,
                # 망토 선보다 먼저(아래) 둔다. 객체 ID는 모든 장에서 같다(앞뒤 순서 유지).
                poly = []
                for oi, a_, b_ in ref['fill_loop']:
                    p0, c, p2 = P[(oi, a_)], P[(oi, 1)], P[(oi, b_)]
                    poly += [_quad(p0, c, p2, j / 4) for j in range(4)]
                hid = []
                for j in range(len(poly)):
                    oid = ACC_AO0 + slot * 1000 + base + 300 + ai * 20 + j
                    pa, pb = ACC_PT0 + n * 10000 + slot * 1000 + npt, ACC_PT0 + n * 10000 + slot * 1000 + npt + 1; npt += 2
                    q0, q1 = poly[j], poly[(j + 1) % len(poly)]
                    dest.append(f'<AO ID="{oid}" TypeId="1" DrawOrder="{oid}" Color="0" LayerId="0" ThicknessScale="0.05" ObjectScale="1.0" GlowRadius="0" '
                                f'GlowThickness="0" GlowColor="4294967295" GlowAlpha="0"><AP ID="{pa}" Flags="9" Index="0" X="{q0[0]:.4f}" Y="{q0[1]:.4f}" />'
                                f'<AP ID="{pb}" Flags="8" Index="1" X="{q1[0]:.4f}" Y="{q1[1]:.4f}" /></AO>')
                    hid.append((oid, pa, pb))
                fs = ''.join(f'<FS Kind="0" ObjId="{o}" StartPtId="{pa}" EndPtId="{pb}" StartT="0.0" EndT="1.0" />' for o, pa, pb in hid)
                dest.append(f'<FR ID="{7900000 + n * 100 + slot * 10 + ai + (5 if base else 0)}" Color="{_with_alpha(fill_col, al)}">{fs}</FR>')
            ids = {}
            for oi, o in enumerate(ref['objects']):
                for pj, _ in enumerate(o['pts']):
                    ids[(oi, pj)] = ACC_PT0 + n * 10000 + slot * 1000 + npt; npt += 1
            k0 = base + k
            for oi, o in enumerate(ref['objects']):
                oid = ACC_AO0 + slot * 1000 + k0 + oi
                s = [f'<AO ID="{oid}" TypeId="{o["type"]}" DrawOrder="{oid}" Color="{_with_alpha(o["color"], al)}" LayerId="0" ThicknessScale="{o["th"] * ratio:.3f}" '
                     'ObjectScale="1.0" GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
                for pj, p in enumerate(o['pts']):
                    x, y = P[(oi, pj)]
                    s.append(f'<AP ID="{ids[(oi, pj)]}" Flags="{p["flags"]}" Index="{pj}" X="{x:.4f}" Y="{y:.4f}">'
                             + ''.join(f'<AC ConnPtId="{ids[tuple(c)]}"/>' for c in p['conn']) + '</AP>')
                s.append('</AO>')
                dest.append(''.join(s))
            if ref.get('fill_loop') and (info is None or same):   # 단단한 액세서리, 또는 채우기 색 = 테두리 색인 망토는 곡선에 바로
                fs = ''.join(f'<FS Kind="0" ObjId="{ACC_AO0 + slot * 1000 + k0 + oi}" StartPtId="{ids[(oi, a_)]}" EndPtId="{ids[(oi, b_)]}" '
                             f'StartT="{0.0 if a_ == 0 else 1.0:.1f}" EndT="{0.0 if b_ == 0 else 1.0:.1f}" />' for oi, a_, b_ in ref['fill_loop'])
                dest.append(f'<FR ID="{7900000 + n * 100 + slot * 10 + ai + (5 if base else 0)}" Color="{_with_alpha(ref.get("fill_color", "-1"), al)}">{fs}</FR>')
        k += len(ref['objects'])
    return ''.join(back_out), ''.join(front_out)
