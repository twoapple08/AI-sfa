import sys, cv2, numpy as np, json, xml.etree.ElementTree as ET
sys.path.insert(0, '/home/user/AI-sfa/tools')
from effect_layers import decompose
import effect_clip_sfa as EC, sfa_render as R
SP = sys.argv[1]
B = cv2.VideoCapture(SP + '/final/final.mp4')
def edges_canny(img):
    s = cv2.bilateralFilter(img, 9, 40, 9); g = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(g, 30, 80)
def edges_regions(img, k=7):
    small = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA)
    s = cv2.pyrMeanShiftFiltering(small, 8, 20); Z = s.reshape(-1, 3).astype(np.float32)
    _, lab, _ = cv2.kmeans(Z, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2, cv2.KMEANS_PP_CENTERS)
    lab = cv2.medianBlur(lab.reshape(small.shape[:2]).astype(np.uint8), 5)
    lab = cv2.resize(lab, (960, 540), interpolation=cv2.INTER_NEAREST)
    e = np.zeros_like(lab); e[:, 1:] |= (lab[:, 1:] != lab[:, :-1]); e[1:, :] |= (lab[1:, :] != lab[:-1, :])
    return (e * 255).astype(np.uint8)
def to_sfa(img, edge):
    lmap = 255 - cv2.dilate(edge, np.ones((2, 2), np.uint8))
    doc, _ = decompose(img, 4, 1.5, lines_only=True, line_join=True, line_map=lmap)
    wr = EC.Writer(); fr = ET.fromstring(EC.frame_xml(doc, 0, wr, 960, 0xFFFFFFFF))
    for a in fr.findall('AO'): a.set('Color', str(-16777216))
    seq = ET.Element('Sequence', dict(HeightWidthRatio='0.5625')); R.PARAMS.update(pad=0.0, thick_mul=1.0)
    r = cv2.cvtColor(R.render_frame(seq, fr, 960, 540)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
    return r, len(fr.findall('AO'))
rows = []
for f in (1049, 1089, 1129, 1259):
    B.set(1, f); _, im = B.read(); img = cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA); cells = [img]
    for name, fn in (('A', edges_canny), ('B', edges_regions)):
        r, n = to_sfa(img, fn(img)); cv2.putText(r, f'{name} {n}', (6, 30), 0, 1, (0, 0, 255), 2); cells.append(r); print(f, name, n, flush=True)
    rows.append(np.hstack(cells))
cv2.imwrite(SP + '/slice/outline_test.png', cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5))
