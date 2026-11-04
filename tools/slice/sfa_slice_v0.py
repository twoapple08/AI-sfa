"""SFA화 시험판 v0(원본1032–1271 중 표본 장): 라벨 레이어별 분해 + 스틱맨 합치기 + 중간 표현 JSON.
비공개 scratch 전용(원본에서 딴 그림). 사용: python slice_v0.py 출력폴더 장번호...
라벨 마스크는 이 클립 전용 규칙(색)·수동 영역이며 자동 분류기가 아니다."""
import json, sys, xml.etree.ElementTree as ET, zipfile, copy
from pathlib import Path
import cv2, numpy as np
sys.path.insert(0, '/home/user/AI-sfa/tools'); sys.path.insert(0, str(Path(__file__).parent))
import effect_clip_sfa as EC
from effect_layers import decompose
from slice_mask import person_mask

VIDEO = '/home/user/AI-sfa/.claude/skills/stickman-extraction/private-data/sources/video.mp4'
STICK = sys.argv[1]
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
FRAMES = [int(x) for x in sys.argv[3:]]
LAYERS = [(0, 'background'), (1, 'object.debris'), (2, 'actor.stickman'), (3, 'effect.impact')]
# 수동 영역(원본 크롭 1152×648 좌표): 타격 섬광. 사람 눈으로 정한 상자 → source=manual
IMPACT_BOX = {1082: (930, 100, 1152, 360)}
H, W = 540, 960
import os
K_ = int(os.environ.get('SLICE_K', 8)); TOL_ = float(os.environ.get('SLICE_TOL', 1.0)); MIN_AREA = int(os.environ.get('SLICE_MIN_AREA', 20))
LEVELS = [float(x) for x in os.environ['SLICE_LEVELS'].split(',')] if os.environ.get('SLICE_LEVELS') else None


def skeleton_band(root, f, shape, r=45):
    """스틱맨 관절 선을 넓힌 띠(원본 크롭 좌표). 색 마스크 중 이 띠에 닿는 덩어리만 인물로 본다."""
    band = np.zeros(shape, np.uint8)
    for ao in root.findall('Frame')[f - 432].findall('AO'):
        if not (int(ao.get('Color')) & 0xff000000): continue
        pts = [(float(p.get('X')) * 11.52, float(p.get('Y')) * 6.48) for p in ao.findall('AP')]
        for a, b in zip(pts, pts[1:]):
            cv2.line(band, tuple(map(int, a)), tuple(map(int, b)), 1, 2 * r)
    return band


def masks_for(img, f, sroot):
    raw = person_mask(img)
    band = skeleton_band(sroot, f, raw.shape)
    n, lab = cv2.connectedComponents(raw)
    hit = np.unique(lab[(band > 0) & (raw > 0)])
    person = np.isin(lab, hit[hit > 0]).astype(np.uint8)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = ((hsv[..., 0] >= 35) & (hsv[..., 0] <= 85) & (hsv[..., 1] > 40)).astype(np.uint8)
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    debris = cv2.dilate(green, np.ones((7, 7), np.uint8)) & (1 - person)
    impact = np.zeros_like(person)
    if f in IMPACT_BOX:
        x0, y0, x1, y1 = IMPACT_BOX[f]
        bright = ((hsv[..., 2] > 200) & (hsv[..., 1] < 50)).astype(np.uint8)
        impact[y0:y1, x0:x1] = bright[y0:y1, x0:x1]
        impact = cv2.dilate(impact, np.ones((5, 5), np.uint8)) & (1 - person) & (1 - debris)
    bg = (1 - person) & (1 - debris) & (1 - impact)
    return dict(person=person, background=bg, **{'object.debris': debris, 'effect.impact': impact})


def stickman_frame(root, f):
    fr = root.findall('Frame')[f - 432]
    return [copy.deepcopy(n) for n in fr if n.tag in ('AO', 'FR')]


def renumber(frame_el, start):
    """프레임 안 AP ID를 새로 매기고 AC/FS 참조를 맞춘다(장마다 새 점 ID)."""
    m = {}
    for ap in frame_el.iter('AP'):
        m[ap.get('ID')] = str(start); ap.set('ID', str(start)); start += 1
    for ac in frame_el.iter('AC'):
        ac.set('ConnPtId', m[ac.get('ConnPtId')])
    for fs in frame_el.iter('FS'):
        for k in ('StartPtId', 'EndPtId'):
            if fs.get(k) in m: fs.set(k, m[fs.get(k)])
    return start


def main():
    z = zipfile.ZipFile(STICK); sroot = ET.fromstring(z.read(z.namelist()[0]))
    cap = cv2.VideoCapture(VIDEO)
    seq = ET.Element('Sequence', dict(Name='sfa_slice_v0', HeightWidthRatio='0.5625', RatioX='16', RatioY='9',
                                      FrameCount=str(len(FRAMES)), BackgroundColor='-1'))
    wr = EC.Writer(); wr.oid = 20_000_000; wr.pid = 1
    inter = dict(schema='sfa-intermediate-v0', clip=dict(source='nian41 비공개 원본', frames=FRAMES, crop_y=[63, 711], fps=[24, 24]),
                 layers=[dict(id=i, label=n) for i, n in LAYERS], frames=[])
    sheets, next_pid = [], 1
    for pos, f in enumerate(FRAMES):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); _, raw = cap.read(); raw = raw[63:711]
        img = cv2.resize(raw, (W, H), interpolation=cv2.INTER_AREA)
        ms = {k: cv2.resize(v, (W, H), interpolation=cv2.INTER_NEAREST) for k, v in masks_for(raw, f, sroot).items()}
        # 인물 자리 배경 메우기(가려진 배경은 추론): 인물을 뺀 그림으로 배경을 분해해 스틱맨 뒤에 흰 구멍이 남지 않게
        filled = cv2.inpaint(img, ms['person'], 7, cv2.INPAINT_TELEA)
        ms['background'] = ms['background'] | ms['person']
        fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
        for i, n in LAYERS:
            ET.SubElement(fr, 'LayerDef', dict(ID=str(i), Name=n, Visible='true', Locked='false'))
        rec_f = dict(frame=f, elements=[])
        for lid, name in LAYERS:
            if name == 'actor.stickman':
                nodes = stickman_frame(sroot, f)
                for nd in nodes:
                    if nd.tag == 'AO': nd.set('LayerId', str(lid))
                    fr.append(nd)
                rec_f['elements'].append(dict(label=name, source='스틱맨 수정판(1Ba4WVy8…, fix869)', objects=sum(n.tag == 'AO' for n in nodes)))
                continue
            valid = ms[name]
            if valid.sum() < 40:
                continue
            src = filled if name == 'background' else img
            doc, _ = decompose(src, K_, TOL_, min_area=MIN_AREA, valid=valid, levels=LEVELS)
            xml = EC.frame_xml(doc, pos, wr, W, 0)
            part = ET.fromstring(xml)
            n_ao = 0
            for nd in part:
                if nd.tag == 'AO': nd.set('LayerId', str(lid)); n_ao += 1
                if nd.tag in ('AO', 'FR'): fr.append(nd)
            rec_f['elements'].append(dict(label=name, source='색 규칙' if name != 'effect.impact' else '수동 영역+밝기',
                                          objects=n_ao, stats=doc['stats'], area_px=int(valid.sum())))
        next_pid = renumber(fr, next_pid)
        inter['frames'].append(rec_f)
        # 확인용 그림: 원본 / 라벨 색칠 / SFA 렌더
        import sfa_render as R
        R.PARAMS.update(pad=0.0, thick_mul=1.0)
        rend = cv2.cvtColor(R.render_frame(seq, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
        lab = img.copy()
        for name, col in (('background', (200, 200, 200)), ('object.debris', (0, 200, 0)), ('effect.impact', (0, 200, 255)), ('person', (255, 0, 255))):
            m = ms[name] > 0; lab[m] = (lab[m] * 0.4 + np.array(col) * 0.6).astype(np.uint8)
        sheets.append(np.hstack([img, lab, rend]))
    with zipfile.ZipFile(OUT / 'sfa_slice_v0.sfa', 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('sfa_slice_v0.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))
    (OUT / 'intermediate_v0.json').write_text(json.dumps(inter, ensure_ascii=False, indent=1), encoding='utf-8')
    cv2.imwrite(str(OUT / 'slice_v0_sheet.png'), cv2.resize(np.vstack(sheets), None, fx=0.5, fy=0.5))
    print(json.dumps([{e['label']: e['objects'] for e in r['elements']} for r in inter['frames']], ensure_ascii=False))


if __name__ == '__main__':
    main()
