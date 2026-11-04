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
    wr = EC.Writer(); fr = ET.fromstring(EC.frame_xml(doc, 0, wr, 960, 0xFFFFFFFF))
    for a in fr.findall('AO'): a.set('Color', str(-12566464))           # 진회색 선
    for ao in sroot.findall('Frame')[f - 432].findall('AO'): fr.append(ao)  # 스틱맨
    seq = ET.Element('Sequence', dict(HeightWidthRatio='0.5625')); R.PARAMS.update(pad=0.0, thick_mul=1.0)
    r = cv2.cvtColor(R.render_frame(seq, fr, 960, 540)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
    nl = sum(len(l['segs']) for l in doc['lines']); counts.append(nl)
    cv2.putText(r, f'{nl} strokes', (6, 30), 0, 1, (0, 0, 255), 2)
    rows.append(np.hstack([img, cv2.cvtColor(lmap, cv2.COLOR_GRAY2BGR), r]))
cv2.imwrite(SP + f'/slice/lineart/lineart_sfa_th{TH}.png', cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5))
print(TH, counts)
