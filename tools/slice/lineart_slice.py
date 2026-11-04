"""완성본 선화(학습된 추출기) → SFA 곡선 획. 인물 영역(원화 마스크+스틱맨 띠) 제외, 굵기 고르게. 비공개 scratch."""
import sys, cv2, numpy as np, torch, zipfile, xml.etree.ElementTree as ET, importlib.util
sys.path.insert(0, '/home/user/AI-sfa/tools'); sys.path.insert(0, sys.argv[1] + '/scripts')
from controlnet_aux.lineart import Generator
from effect_layers import decompose
import effect_clip_sfa as EC, sfa_render as R
from slice_mask import person_mask
spec = importlib.util.spec_from_file_location('sv', sys.argv[1] + '/scripts/slice_v0.py')
SP = sys.argv[1]; STICK = SP + '/fix869/stickman_60s_display_motion_fix_432-1871.sfa'
TH = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
g = Generator(3, 1, 3); g.load_state_dict(torch.load('/root/sfa-models/sk_model.pth', map_location='cpu')); g.eval()
A = cv2.VideoCapture('/home/user/AI-sfa/.claude/skills/stickman-extraction/private-data/sources/video.mp4')
B = cv2.VideoCapture(SP + '/final/final.mp4')
z = zipfile.ZipFile(STICK); sroot = ET.fromstring(z.read(z.namelist()[0]))

def band(f, shape, r=45):
    m = np.zeros(shape, np.uint8)
    for ao in sroot.findall('Frame')[f - 432].findall('AO'):
        if not (int(ao.get('Color')) & 0xff000000): continue
        pts = [(float(p.get('X')) * 11.52, float(p.get('Y')) * 6.48) for p in ao.findall('AP')]
        for a, b in zip(pts, pts[1:]): cv2.line(m, tuple(map(int, a)), tuple(map(int, b)), 1, 2 * r)
    return m

import math
STRAIGHT_PX = 1.2      # 조절점이 두 끝 잇는 선에서 이만큼(px) 안이면 직선
MERGE_DEG, MERGE_GAP = 4.0, 18.0   # 같은 방향(±도)·끝점 간격(px) 안이고 같은 직선 위(2.5px)면 한 직선으로

def dev(sg):
    x0, y0, cx, cy, x1, y1 = sg[:6]
    # 2차 베지어의 현에서 최대 벗어남 = 조절점-현 중점 거리의 1/2
    return math.hypot(cx - (x0 + x1) / 2, cy - (y0 + y1) / 2) / 2

def ang(a, b): return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180

def line_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]; L = math.hypot(vx, vy) or 1e-9
    return abs((p[0] - a[0]) * vy - (p[1] - a[1]) * vx) / L

def merge_lines(lines):
    """직선 조각들을 방향·간격이 맞으면 하나로(끝점이 서로 가깝고 같은 방향, 새 끝점도 같은 직선 위)."""
    changed = True
    while changed:
        changed = False
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                a, b = lines[i], lines[j]
                d = abs(ang(*a) - ang(*b)); d = min(d, 180 - d)
                if d > MERGE_DEG: continue
                ends = [(p, q) for p in a for q in b]
                gap = min(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in ends)
                if gap > MERGE_GAP: continue
                pts = list(a) + list(b)
                far = max(((p, q) for p in pts for q in pts), key=lambda t: math.hypot(t[0][0] - t[1][0], t[0][1] - t[1][1]))
                if max(line_dist(p, *far) for p in pts) > 2.5: continue
                lines[i] = far; lines.pop(j); changed = True; break
            if changed: break
    return lines

def line_ao(out, wr, a, b, color, ts):
    oid, p = wr.oid, wr.pid; wr.oid += 1; wr.pid += 2
    out.append(f'<AO ID="{oid}" TypeId="1" Color="{color}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">')
    for k, (x, y) in enumerate((a, b)):
        out.append(f'<AP ID="{p + k}" Flags="{(9, 8)[k]}" Index="{k}" X="{x / 960 * 100:.3f}" Y="{y / 540 * 100:.3f}" />')
    out.append('</AO>')

LAYERS = [(0, 'background'), (1, 'object.debris'), (2, 'actor.stickman'), (3, 'effect.impact')]
COLORS = {0: -12566464, 1: -16744448, 3: -23296}        # 배경 진회색, 파편 초록, 섬광 주황(확인용 색)
IMPACT_BOX = {1082: (930, 100, 1152, 360)}               # 원화 크롭 좌표, 수동

def label_masks(raw, f):
    hsv = cv2.cvtColor(raw, cv2.COLOR_BGR2HSV)
    green = ((hsv[..., 0] >= 35) & (hsv[..., 0] <= 85) & (hsv[..., 1] > 40)).astype(np.uint8)
    debris = cv2.dilate(cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), np.ones((11, 11), np.uint8))
    impact = np.zeros_like(debris)
    if f in IMPACT_BOX:
        x0, y0, x1, y1 = IMPACT_BOX[f]; impact[y0:y1, x0:x1] = 1
    return debris, impact

def label_of(ao, debris, impact):
    pts = [(float(p.get('X')) * 11.52, float(p.get('Y')) * 6.48) for p in ao.findall('AP')]
    x, y = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])
    xi, yi = int(np.clip(x, 0, 1151)), int(np.clip(y, 0, 647))
    return 3 if impact[yi, xi] else 1 if debris[yi, xi] else 0

seq_all = ET.Element('Sequence', dict(Name='sfa_slice_outline_v1', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount='4', BackgroundColor='-1'))
label_stats = []
rows, counts = [], []
for f in (1042, 1082, 1122, 1252):
    A.set(1, f); _, raw = A.read(); raw = raw[63:711]
    pm = person_mask(raw); n, lab = cv2.connectedComponents(pm); bd = band(f, pm.shape)
    hit = np.unique(lab[(bd > 0) & (pm > 0)]); person = np.isin(lab, hit[hit > 0]).astype(np.uint8)
    person = cv2.dilate(person, np.ones((15, 15), np.uint8))          # 완성본 인물이 원화보다 조금 큼
    B.set(1, f + 7); _, im = B.read(); img = cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA)
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).float().permute(2, 0, 1)[None] / 255
    with torch.no_grad(): zz = g(x)[0, 0].clamp(0, 1).numpy()
    lmap = (zz * 255).astype(np.uint8)                                 # 흰 바탕 검은 선
    lmap[cv2.resize(person, (960, 540), interpolation=cv2.INTER_NEAREST) > 0] = 255
    lmap[lmap > int(255 * (1 - TH))] = 255                             # 옅은 선 버림(TH 높을수록 더 많이 남김)
    doc, _ = decompose(img, 4, 1.5, lines_only=True, line_join=True, line_map=lmap)
    for ln in doc['lines']:
        for s in ln['segs']:
            if len(s) > 6: s[6] = 1.6                                  # 굵기 고르게(분해 높이 540 기준 px)
    curves, straight = [], []
    for ln in doc['lines']:
        for sg in ln['segs']:
            (straight.append(((sg[0], sg[1]), (sg[4], sg[5]))) if dev(sg) <= STRAIGHT_PX else curves.append(sg))
    n_before = len(straight) + len(curves)
    straight = merge_lines(straight)
    straight = [l for l in straight if math.hypot(l[0][0] - l[1][0], l[0][1] - l[1][1]) >= 3]
    doc['lines'] = [dict(tone='dark', color=[64, 64, 64], segs=curves)]
    wr = EC.Writer(); xml = EC.frame_xml(doc, 0, wr, 960, 0xFFFFFFFF)
    extra = []
    ts = max(EC.TS_MIN, EC.thick(1.6, 960) * EC.LINE_SCALE)
    for a_, b_ in straight: line_ao(extra, wr, a_, b_, -12566464, ts)
    fr = ET.fromstring(xml.replace('</Frame>', ''.join(extra) + '</Frame>'))
    debris, impact = label_masks(raw, f)
    lab_n = {0: 0, 1: 0, 3: 0}
    for a in fr.findall('AO'):
        lid = label_of(a, debris, impact); lab_n[lid] += 1
        a.set('LayerId', str(lid)); a.set('Color', str(COLORS[lid]))
    for ld in fr.findall('LayerDef'): fr.remove(ld)
    for i_, (lid, nm) in enumerate(LAYERS): fr.insert(i_, ET.Element('LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked='false')))
    label_stats.append({n: lab_n.get(l, 0) for l, n in LAYERS if l != 2})
    for ao in sroot.findall('Frame')[f - 432].findall('AO'):
        ao = __import__('copy').deepcopy(ao); ao.set('LayerId', '2'); fr.append(ao)  # 스틱맨(레이어2)
    pos = len(seq_all.findall('Frame')); fr.set('ID', str(pos + 1)); fr.set('Position', str(pos))
    pid = [1 + pos * 100000]
    m = {}
    for ap in fr.iter('AP'): m[ap.get('ID')] = str(pid[0]); ap.set('ID', str(pid[0])); pid[0] += 1
    for ac in fr.iter('AC'): ac.set('ConnPtId', m[ac.get('ConnPtId')])
    for fs in fr.iter('FS'):
        for k_ in ('StartPtId', 'EndPtId'):
            if fs.get(k_) in m: fs.set(k_, m[fs.get(k_)])
    seq_all.append(fr)
    seq = ET.Element('Sequence', dict(HeightWidthRatio='0.5625')); R.PARAMS.update(pad=0.0, thick_mul=1.0)
    r = cv2.cvtColor(R.render_frame(seq, fr, 960, 540)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
    nl = len(curves) + len(straight); npts = 3 * len(curves) + 2 * len(straight); counts.append((n_before, len(straight), len(curves), npts))
    cv2.putText(r, f'line {len(straight)} / curve {len(curves)} (was {n_before})', (6, 30), 0, 0.9, (0, 0, 255), 2)
    rows.append(np.hstack([img, cv2.cvtColor(lmap, cv2.COLOR_GRAY2BGR), r]))
with zipfile.ZipFile(SP + '/slice/lineart/sfa_slice_outline_v1.sfa', 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('sfa_slice_outline_v1.xml', ET.tostring(seq_all, encoding='utf-8', xml_declaration=True))
print('labels', label_stats)
cv2.imwrite(SP + f'/slice/lineart/lineart_labeled_th{TH}.png', cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5))
print(TH, counts)
