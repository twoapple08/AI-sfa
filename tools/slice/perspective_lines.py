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
    other = [((s[0], s[1]), (s[2], s[3]), 'o') for s in other if seglen(s) >= MIN_OUT + 10]
    return lines, other, dict(h=len(hor), v=len(ver), r=len(rad), o=len(other))


COL = {'h': (40, 40, 200), 'v': (40, 160, 40), 'r': (200, 60, 40), 'o': (150, 150, 150)}
rows, stats = [], []
seq = ET.Element('Sequence', dict(Name='sfa_slice_perspective_v1', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount=str(len(FRAMES)), BackgroundColor='-1'))
rng = np.random.default_rng(0)
for pos, f in enumerate(FRAMES):
    raw, person = person_for(f)
    B.set(1, f + 7); _, im = B.read(); img = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).float().permute(2, 0, 1)[None] / 255
    with torch.no_grad(): zz = g(x)[0, 0].clamp(0, 1).numpy()
    la = (zz * 255).astype(np.uint8); la[person > 0] = 255
    det = lsd.detect(la)[0]
    segs = [tuple(map(float, s)) for s in (np.asarray(det).reshape(-1, 4) if det is not None else [])]
    segs = [s for s in segs if seglen(s) >= MIN_SEG]
    vp1, sc1 = estimate_vp(segs, rng)
    vp, vp_score = ([vp1], sc1) if vp1 is not None else (None, 0)
    if vp1 is not None:   # 둘째 소실점: 첫 소실점을 따르지 않는 선분으로 다시
        rest = [s_ for s_ in segs if is_axis(s_) or dir_to_vp(s_, vp1) >= VP_DEG]
        vp2, sc2 = estimate_vp(rest, rng)
        if vp2 is not None and sc2 > 0.25 and math.hypot(vp2[0] - vp1[0], vp2[1] - vp1[1]) > 80:
            vp.append(vp2)
    lines, other, st = snap(segs, vp)
    stats.append(dict(frame=f, segs=len(segs), vp=None if vp is None else [[round(v[0]), round(v[1])] for v in vp], vp_share=round(vp_score, 2), **st, out=len(lines), other=len(other)))
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
    cv2.putText(c2, f'h{st["h"]} v{st["v"]} vp{st["r"]} other{st["o"]} -> {len(lines)} lines', (6, 28), 0, 0.8, (0, 0, 255), 2)
    rows.append(np.hstack([img, c1, c2, rend]))
with zipfile.ZipFile(SP + f'/slice/lineart/sfa_slice_perspective{TAG}.sfa', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('sfa_slice_perspective.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
cv2.imwrite(SP + f'/slice/lineart/perspective{TAG}.png', cv2.resize(np.vstack(rows), None, fx=0.4, fy=0.4))
for s in stats: print(s)
