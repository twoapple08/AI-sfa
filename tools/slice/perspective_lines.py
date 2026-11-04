"""투시도 선 정리(2026-11-05): 선화 → 선분(LSD) → 소실점 추정 → 수평/수직/소실점 방향으로 스냅 → 같은 직선 잇기.
사용: python perspective_lines.py SP 장번호,장번호,... 태그
비공개 scratch(원본에서 딴 그림). 결과: 비교 시트, SFA(직선 객체, 라벨 레이어), 통계."""
import math, os, sys, zipfile, copy, xml.etree.ElementTree as ET
import cv2, numpy as np, torch
sys.path.insert(0, '/home/user/AI-sfa/tools'); sys.path.insert(0, sys.argv[1] + '/scripts')
from controlnet_aux.lineart import Generator
import sfa_render as R
from slice_mask import person_mask

SP = sys.argv[1]
FRAMES = [int(v) for v in sys.argv[2].split(',')]
TAG = sys.argv[3] if len(sys.argv) > 3 else ''
W, H = 960, 540
AX_DEG, VP_DEG = 4.0, 2.5          # 수평·수직 판정 / 소실점 방향 판정 허용 각
MIN_SEG, MIN_OUT = 12, int(os.environ.get('PL_MIN', 30))           # LSD 선분 최소 길이 / 최종 선 최소 길이(px)
GAP = float(os.environ.get('PL_GAP', 22))   # 같은 직선 위 조각 잇는 최대 빈칸(px)

g = Generator(3, 1, 3); g.load_state_dict(torch.load('/root/sfa-models/sk_model.pth', map_location='cpu')); g.eval()
A = cv2.VideoCapture('/home/user/AI-sfa/.claude/skills/stickman-extraction/private-data/sources/video.mp4')
B = cv2.VideoCapture(SP + '/final/final.mp4')
zs = zipfile.ZipFile(SP + '/fix869/stickman_60s_display_motion_fix_432-1871.sfa'); sroot = ET.fromstring(zs.read(zs.namelist()[0]))
lsd = cv2.createLineSegmentDetector(0)


def band(f, shape, r=45):
    m = np.zeros(shape, np.uint8)
    for ao in sroot.findall('Frame')[f - 432].findall('AO'):
        if not (int(ao.get('Color')) & 0xff000000): continue
        pts = [(float(p.get('X')) * 11.52, float(p.get('Y')) * 6.48) for p in ao.findall('AP')]
        for a, b in zip(pts, pts[1:]): cv2.line(m, tuple(map(int, a)), tuple(map(int, b)), 1, 2 * r)
    return m


def person_for(f):
    A.set(1, f); _, raw = A.read(); raw = raw[63:711]
    pm = person_mask(raw); n, lab = cv2.connectedComponents(pm); bd = band(f, pm.shape)
    hit = np.unique(lab[(bd > 0) & (pm > 0)])
    person = np.isin(lab, hit[hit > 0]).astype(np.uint8)
    person = cv2.dilate(person, np.ones((7, 7), np.uint8))
    return raw, cv2.resize(person, (W, H), interpolation=cv2.INTER_NEAREST)


def angle(s):
    return math.degrees(math.atan2(s[3] - s[1], s[2] - s[0])) % 180


def seglen(s):
    return math.hypot(s[2] - s[0], s[3] - s[1])


def dir_to_vp(s, vp):
    mx, my = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
    a = math.degrees(math.atan2(vp[1] - my, vp[0] - mx)) % 180
    d = abs(a - angle(s)); return min(d, 180 - d)


def is_axis(s):
    a = angle(s)
    return min(a, 180 - a) < AX_DEG or abs(a - 90) < AX_DEG


def estimate_vp(segs, rng):
    cand = [s for s in segs if not is_axis(s) and seglen(s) > 25]
    if len(cand) < 4: return None, 0
    best, score = None, 0
    w = np.array([seglen(s) for s in cand]); w = w / w.sum()
    for _ in range(3000):
        i, j = rng.choice(len(cand), 2, replace=False, p=w)
        a, b = cand[i], cand[j]
        x1, y1, x2, y2 = a; x3, y3, x4, y4 = b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-6: continue
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
        if not (-3 * W < px < 4 * W and -3 * H < py < 4 * H): continue
        sc = sum(seglen(s) for s in cand if dir_to_vp(s, (px, py)) < VP_DEG)
        if sc > score: best, score = (px, py), sc
    total = sum(seglen(s) for s in cand)
    return best, score / max(total, 1e-6)


def merge_intervals(items, gap):
    """items: (key, t0, t1) 같은 직선 위 구간 → 빈칸 gap 안이면 합침."""
    items.sort(key=lambda t: t[1]); out = []
    for k, a, b in items:
        if out and a - out[-1][2] <= gap:
            out[-1][2] = max(out[-1][2], b)
        else:
            out.append([k, a, b])
    return out


def snap(segs, vp):
    hor, ver, rad, other = [], [], [], []
    for s in segs:
        a = angle(s)
        if min(a, 180 - a) < AX_DEG:
            hor.append(s)
        elif abs(a - 90) < AX_DEG:
            ver.append(s)
        elif vp is not None and min(dir_to_vp(s, v) for v in vp) < VP_DEG:
            rad.append((s, min(range(len(vp)), key=lambda i: dir_to_vp(s, vp[i]))))
        else:
            other.append(s)
    lines = []
    # 수평: y로 묶고(2.5px) 구간 합치기
    def group(vals, tol):
        vals = sorted(vals, key=lambda t: t[0]); groups = []
        for v in vals:
            if groups and abs(v[0] - np.mean([g[0] for g in groups[-1]])) <= tol: groups[-1].append(v)
            else: groups.append([v])
        return groups
    for grp in group([((s[1] + s[3]) / 2, min(s[0], s[2]), max(s[0], s[2])) for s in hor], 2.5):
        y = float(np.average([g[0] for g in grp], weights=[g[2] - g[1] + 1 for g in grp]))
        for _, a, b in merge_intervals([(y, g[1], g[2]) for g in grp], GAP):
            lines.append(((a, y), (b, y), 'h'))
    for grp in group([((s[0] + s[2]) / 2, min(s[1], s[3]), max(s[1], s[3])) for s in ver], 2.5):
        x = float(np.average([g[0] for g in grp], weights=[g[2] - g[1] + 1 for g in grp]))
        for _, a, b in merge_intervals([(x, g[1], g[2]) for g in grp], GAP):
            lines.append(((x, a), (x, b), 'v'))
    if vp is not None:
        for vi, v in enumerate(vp):
            items = []
            for s_, k in rad:
                if k != vi: continue
                mx, my = (s_[0] + s_[2]) / 2, (s_[1] + s_[3]) / 2
                phi = math.atan2(my - v[1], mx - v[0])
                r0 = math.hypot(s_[0] - v[0], s_[1] - v[1]); r1 = math.hypot(s_[2] - v[0], s_[3] - v[1])
                items.append((phi, min(r0, r1), max(r0, r1)))
            items.sort()
            groups = []
            for it in items:
                if groups:
                    last = groups[-1]; phi0 = np.mean([g[0] for g in last]); rmid = np.mean([(g[1] + g[2]) / 2 for g in last])
                    if abs(it[0] - phi0) * max(rmid, 1) <= 3.0: last.append(it); continue
                groups.append([it])
            for grp in groups:
                phi = float(np.average([g[0] for g in grp], weights=[g[2] - g[1] + 1 for g in grp]))
                for _, a, b in merge_intervals([(phi, g[1], g[2]) for g in grp], GAP):
                    lines.append(((v[0] + a * math.cos(phi), v[1] + a * math.sin(phi)), (v[0] + b * math.cos(phi), v[1] + b * math.sin(phi)), 'r'))
    lines = [l for l in lines if math.hypot(l[0][0] - l[1][0], l[0][1] - l[1][1]) >= MIN_OUT]
    other = [((s[0], s[1]), (s[2], s[3]), 'o') for s in other if seglen(s) >= int(os.environ.get('PL_OTHER_MIN', MIN_OUT + 10))]
    return lines, other, dict(h=len(hor), v=len(ver), r=len(rad), o=len(other))


def _u(a, b):
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-9
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L), L


def _ldist(p, a, b):
    (ux, uy), _ = _u(a, b)
    return abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux)


def _ang(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def bridge(lines, pm, max_gap=300, cover=0.6):
    """인물에 가려 끊긴 같은 직선 위 두 조각 잇기(추론): 빈칸의 cover 이상이 인물 영역이면."""
    n_b, changed = 0, True
    while changed:
        changed = False
        for i in range(len(lines)):
            a = lines[i]
            for j in range(i + 1, len(lines)):
                b = lines[j]
                if a[2] != b[2]: continue
                d = abs(_ang(a[0], a[1]) - _ang(b[0], b[1])); d = min(d, 180 - d)
                if d > 1.5 or max(_ldist(b[0], a[0], a[1]), _ldist(b[1], a[0], a[1])) > 3: continue
                p, q = min(((p, q) for p in a[:2] for q in b[:2]), key=lambda t: math.hypot(t[0][0] - t[1][0], t[0][1] - t[1][1]))
                gap = math.hypot(p[0] - q[0], p[1] - q[1])
                if gap > max_gap: continue
                n = max(2, int(gap))
                xs = np.linspace(p[0], q[0], n).astype(int).clip(0, W - 1); ys = np.linspace(p[1], q[1], n).astype(int).clip(0, H - 1)
                if gap > GAP and pm[ys, xs].mean() < cover: continue
                pts = [a[0], a[1], b[0], b[1]]
                far = max(((u, v) for u in pts for v in pts), key=lambda t: math.hypot(t[0][0] - t[1][0], t[0][1] - t[1][1]))
                lines[i] = (far[0], far[1], a[2]); lines.pop(j); changed = True; n_b += gap > GAP; break
            if changed: break
    return lines, n_b


def extend(lines, ev, miss_max=8):
    """근거(완성본 경계·선화)가 이어지는 곳까지 양 끝을 늘린다. 근거 없는 칸이 miss_max 넘게 이어지면 멈추고 그 앞에서 자른다."""
    out, grown = [], 0
    for a, b, k in lines:
        (ux, uy), L = _u(a, b)
        ends = []
        for p, sx, sy in ((b, ux, uy), (a, -ux, -uy)):
            x, y, last, miss, t = p[0], p[1], p, 0, 0
            while miss <= miss_max:
                t += 1; x, y = p[0] + sx * t, p[1] + sy * t
                if not (0 <= x < W and 0 <= y < H): break
                if ev[int(y), int(x)]: last, miss = (x, y), 0
                else: miss += 1
            ends.append(last)
        grown += math.hypot(ends[0][0] - b[0], ends[0][1] - b[1]) + math.hypot(ends[1][0] - a[0], ends[1][1] - a[1])
        out.append((ends[1], ends[0], k))
    return out, grown


def corners(lines, tol=10):
    """선 끝이 다른(평행 아닌) 선과 tol 안에서 거의 만나면 정확히 교점으로."""
    lines = [list(l) for l in lines]; n_c = 0
    for i, L1 in enumerate(lines):
        for e in (0, 1):
            p = L1[e]; best = None
            for j, L2 in enumerate(lines):
                if i == j: continue
                d = abs(_ang(L1[0], L1[1]) - _ang(L2[0], L2[1])); d = min(d, 180 - d)
                if d < 10: continue
                x1, y1 = L1[0]; x2, y2 = L1[1]; x3, y3 = L2[0]; x4, y4 = L2[1]
                den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
                if abs(den) < 1e-9: continue
                X = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
                Y = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
                dp = math.hypot(X - p[0], Y - p[1])
                if dp > tol: continue
                (ux, uy), L = _u(L2[0], L2[1]); tt = (X - L2[0][0]) * ux + (Y - L2[0][1]) * uy
                if not (-tol <= tt <= L + tol): continue
                if best is None or dp < best[0]: best = (dp, (X, Y))
            if best: L1[e] = best[1]; n_c += 1
    return [tuple(l) for l in lines], n_c


def lineart_segs(img, person):
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).float().permute(2, 0, 1)[None] / 255
    with torch.no_grad(): zz = g(x)[0, 0].clamp(0, 1).numpy()
    la = (zz * 255).astype(np.uint8); la[person > 0] = 255
    det = lsd.detect(la)[0]
    segs = [tuple(map(float, s)) for s in (np.asarray(det).reshape(-1, 4) if det is not None else [])]
    return la, [s for s in segs if seglen(s) >= MIN_SEG]


orb = cv2.ORB_create(2000)


def to_target(img_t, img_n, person_t, person_n):
    """이웃 장 → 대상 장 호모그래피(배경 특징점만, 인물 제외). 대응이 약하면 None(컷 바뀜·큰 움직임)."""
    gt = cv2.cvtColor(img_t, cv2.COLOR_BGR2GRAY); gn = cv2.cvtColor(img_n, cv2.COLOR_BGR2GRAY)
    k1, d1 = orb.detectAndCompute(gn, (1 - person_n) * 255); k2, d2 = orb.detectAndCompute(gt, (1 - person_t) * 255)
    if d1 is None or d2 is None or len(k1) < 30 or len(k2) < 30: return None, 0
    m = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    if len(m) < 30: return None, 0
    src = np.float32([k1[x.queryIdx].pt for x in m]); dst = np.float32([k2[x.trainIdx].pt for x in m])
    Hm, inl = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    n_in = int(inl.sum()) if inl is not None else 0
    return (Hm, n_in) if Hm is not None and n_in >= 60 else (None, n_in)


COL = {'h': (40, 40, 200), 'v': (40, 160, 40), 'r': (200, 60, 40), 'o': (150, 150, 150)}
rows, stats = [], []
seq = ET.Element('Sequence', dict(Name='sfa_slice_perspective_v1', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount=str(len(FRAMES)), BackgroundColor='-1'))
rng = np.random.default_rng(0)
for pos, f in enumerate(FRAMES):
    raw, person = person_for(f)
    B.set(1, f + 7); _, im = B.read(); img = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    la, segs = lineart_segs(img, person)
    used = []
    for dlt in [int(v) for v in os.environ.get('PL_MULTI', '').split(',') if v]:   # 같은 컷 이웃 장의 선분 모으기
        _, pn = person_for(f + dlt)
        B.set(1, f + dlt + 7); okn, imn = B.read()
        if not okn: continue
        imn = cv2.resize(imn, (W, H), interpolation=cv2.INTER_AREA)
        Hm, n_in = to_target(img, imn, person, pn)
        if Hm is None: used.append((dlt, n_in, 0)); continue
        _, sn = lineart_segs(imn, pn)
        pts = np.float32([[s[0], s[1]] for s in sn] + [[s[2], s[3]] for s in sn]).reshape(-1, 1, 2)
        tp = cv2.perspectiveTransform(pts, Hm).reshape(-1, 2); n = len(sn)
        add = [(tp[i][0], tp[i][1], tp[n + i][0], tp[n + i][1]) for i in range(n)]
        add = [s_ for s_ in add if person[int(np.clip((s_[1] + s_[3]) / 2, 0, H - 1)), int(np.clip((s_[0] + s_[2]) / 2, 0, W - 1))] == 0 or True]
        segs += add; used.append((dlt, n_in, len(add)))
    vp1, sc1 = estimate_vp(segs, rng)
    vp, vp_score = ([vp1], sc1) if vp1 is not None else (None, 0)
    if vp1 is not None:   # 둘째 소실점: 첫 소실점을 따르지 않는 선분으로 다시
        rest = [s_ for s_ in segs if is_axis(s_) or dir_to_vp(s_, vp1) >= VP_DEG]
        vp2, sc2 = estimate_vp(rest, rng)
        if vp2 is not None and sc2 > 0.25 and math.hypot(vp2[0] - vp1[0], vp2[1] - vp1[1]) > 80:
            vp.append(vp2)
    lines, other, st = snap(segs, vp)
    if os.environ.get('PL_REFINE', '1') == '1':
        gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
        ev = (cv2.Canny(gray, 25, 70) > 0) | (la < 200)
        ev = cv2.dilate(ev.astype(np.uint8), np.ones((3, 3), np.uint8)) & (1 - person)
        lines, st['bridged'] = bridge(lines, cv2.dilate(person, np.ones((9, 9), np.uint8)))
        lines, grown = extend(lines, ev); st['grown_px'] = int(grown)
        lines, st['corners'] = corners(lines)
        lines = [l for l in lines if math.hypot(l[0][0] - l[1][0], l[0][1] - l[1][1]) >= MIN_OUT]
    stats.append(dict(frame=f, neighbours=used, segs=len(segs), vp=None if vp is None else [[round(v[0]), round(v[1])] for v in vp], vp_share=round(vp_score, 2), **st, out=len(lines), other=len(other)))
    # 그림: 원본 / LSD 선분 / 스냅 결과(색=방향) + 스틱맨
    c1 = np.full_like(img, 255)
    for s in segs: cv2.line(c1, (int(s[0]), int(s[1])), (int(s[2]), int(s[3])), (60, 60, 60), 1, cv2.LINE_AA)
    c2 = np.full_like(img, 255)
    for (a, b, k) in lines + other:
        cv2.line(c2, tuple(map(int, a)), tuple(map(int, b)), COL[k], 1 if k == 'o' else 2, cv2.LINE_AA)
    for v in (vp or []):
        if 0 <= v[0] < W and 0 <= v[1] < H: cv2.circle(c2, (int(v[0]), int(v[1])), 6, (0, 0, 255), 2)
    sk = np.zeros_like(img)
    fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
    for lid, nm in ((0, 'background'), (1, 'object.other'), (2, 'actor.stickman')):
        ET.SubElement(fr, 'LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked='false'))
    oid, pid = 1, 1 + pos * 100000
    for (a, b, k) in lines + other:
        ao = ET.SubElement(fr, 'AO', dict(ID=str(oid), TypeId='1', Color=str(-12566464 if k != 'o' else -7829368), LayerId='0' if k != 'o' else '1',
                                          DrawOrder=str(oid), ThicknessScale='0.35', ObjectScale='1.0', GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0'))
        for i, (px_, py_) in enumerate((a, b)):
            ET.SubElement(ao, 'AP', dict(ID=str(pid), Flags=('9', '8')[i], Index=str(i), X=f'{px_ / W * 100:.3f}', Y=f'{py_ / H * 100:.3f}')); pid += 1
        oid += 1
    m = {}
    for ao in sroot.findall('Frame')[f - 432].findall('AO'):
        ao = copy.deepcopy(ao); ao.set('LayerId', '2')
        for ap in ao.iter('AP'): m[ap.get('ID')] = str(pid); ap.set('ID', str(pid)); pid += 1
        fr.append(ao)
    for ac in fr.iter('AC'): ac.set('ConnPtId', m.get(ac.get('ConnPtId'), ac.get('ConnPtId')))
    R.PARAMS.update(pad=0.0, thick_mul=1.0)
    rend = cv2.cvtColor(R.render_frame(seq, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
    cv2.putText(c2, f'{len(lines)} lines  bridge{st.get("bridged", 0)} corner{st.get("corners", 0)}', (6, 28), 0, 0.8, (0, 0, 255), 2)
    rows.append(np.hstack([img, c1, c2, rend]))
with zipfile.ZipFile(SP + f'/slice/lineart/sfa_slice_perspective{TAG}.sfa', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('sfa_slice_perspective.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
cv2.imwrite(SP + f'/slice/lineart/perspective{TAG}.png', cv2.resize(np.vstack(rows), None, fx=0.4, fy=0.4))
for s in stats: print(s)
