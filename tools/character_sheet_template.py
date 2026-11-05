"""캐릭터 시트 양식 v2(2026-11-05 사용자 양식 보완): 6방향(+반측면) 칸, 정수리선·발바닥선·가운데선, 레이어 이름, 장 나누기.
사용자 v1 예시(90° 돌려 그린 캐릭터 6방향)를 바로 세워 v2 1장(스틱맨) 칸에 옮겨 넣고, 작성 안내 그림을 만든다.

사용: python tools/character_sheet_template.py <v1.sfa> <출력 폴더>
→ character_sheet_v2.sfa(빈 양식), character_sheet_v2_example.sfa(사용자 캐릭터를 옮긴 예시), character_sheet_v2_guide.png,
   character_sheet_v2_설명양식.txt
"""
import copy, math, os, sys, zipfile, xml.etree.ElementTree as ET
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
KR = 1                       # ttc 안 한국어 글꼴 번호(Noto Sans CJK KR)
PW, PH = 1600.0, 900.0       # % ↔ 화소(16:9)
INK, GUIDE, GUIDE2 = '-16777216', '-3355444', '-5592406'   # 검정, 연회색, 회색

# 칸 배치(%, x0, x1, y0, y1) — 위 줄 5칸(정면·반측면·우측·좌측·후면), 아래 줄 2칸(위·아래)
TOP = ['정면', '반측면', '우측', '좌측', '후면']
BOT = ['위', '아래']
TOP_Y0, TOP_Y1, HEAD_Y, FOOT_Y = 4.0, 57.0, 15.0, 52.5
BOT_Y0, BOT_Y1 = 60.0, 97.5


def top_slots():
    w = 96.0 / len(TOP)
    return [(2 + i * w, 2 + (i + 1) * w, TOP_Y0, TOP_Y1) for i in range(len(TOP))]


def bot_slots():
    return [(14.0, 49.0, BOT_Y0, BOT_Y1), (51.0, 86.0, BOT_Y0, BOT_Y1)]


class Ids:
    def __init__(self, o0, p0):
        self.o, self.p = o0, p0

    def obj(self):
        self.o += 1
        return self.o

    def pt(self):
        self.p += 1
        return self.p


STY = dict(ObjectScale='1.0', GlowRadius='0', GlowThickness='0', GlowColor='4294967295', GlowAlpha='0')


def line(fr, ids, a, b, color, th, layer):
    o = ids.obj()
    ao = ET.SubElement(fr, 'AO', dict(ID=str(o), TypeId='1', Color=color, LayerId=str(layer), DrawOrder=str(o), ThicknessScale=f'{th:.3f}', **STY))
    for i, (x, y) in enumerate((a, b)):
        ET.SubElement(ao, 'AP', dict(ID=str(ids.pt()), Flags=('9', '8')[i], Index=str(i), X=f'{x:.4f}', Y=f'{y:.4f}'))


def text_polys(text, size_pct):
    """글자 외곽선 → 닫힌 다각형 목록(글자 상자 좌상단 기준 %, 높이 size_pct)."""
    px = 160
    f = ImageFont.truetype(FONT, px, index=KR)
    l, t, r, b = f.getbbox(text)
    im = Image.new('L', (r - l + 20, b - t + 20), 0)
    ImageDraw.Draw(im).text((10 - l, 10 - t), text, 255, font=f)
    m = np.array(im)
    cs, _ = cv2.findContours((m > 127).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    k = size_pct / (b - t)          # 화소 → % (세로 기준)
    out = []
    for c in cs:
        if cv2.contourArea(c) < 30: continue
        a = cv2.approxPolyDP(c, 1.6, True)[:, 0, :].astype(float)
        out.append([((x - 10) * k * PH / PW, (y - 10) * k) for x, y in a])
    w = (r - l) * k * PH / PW
    return out, w


def label(fr, ids, text, cx, y, size, layer, th=0.18):
    polys, w = text_polys(text, size)
    for poly in polys:
        n = len(poly)
        for i in range(n):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            line(fr, ids, (cx - w / 2 + x0, y + y0), (cx - w / 2 + x1, y + y1), INK, th, layer)


def guide_frame(seq, pos, title, ids, names, with_slots=True):
    fr = ET.SubElement(seq, 'Frame', dict(BackgroundColor='4294967295', ID=str(pos + 1), Position=str(pos)))
    for lid, nm, lock in ((0, 'sheet.guide', 'true'), (1, 'char.back', 'false'), (2, 'char.mid', 'false'), (3, 'char.front', 'false')):
        ET.SubElement(fr, 'LayerDef', dict(ID=str(lid), Name=nm, Visible='true', Locked=lock))
    label(fr, ids, title, 50.0, 0.3, 2.8, 0, th=0.15)
    if not with_slots:
        return fr
    for (x0, x1, y0, y1), nm in zip(top_slots(), names[0]):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(fr, ids, a, b, GUIDE, 0.25, 0)
        line(fr, ids, ((x0 + x1) / 2, HEAD_Y - 1.5), ((x0 + x1) / 2, FOOT_Y + 1.5), GUIDE, 0.2, 0)      # 가운데선
        label(fr, ids, nm, (x0 + x1) / 2, y0 + 1.6, 4.2, 0)
    xs = [s[0] for s in top_slots()] + [s[1] for s in top_slots()]
    line(fr, ids, (min(xs), HEAD_Y), (max(xs), HEAD_Y), GUIDE2, 0.3, 0)    # 정수리선
    line(fr, ids, (min(xs), FOOT_Y), (max(xs), FOOT_Y), GUIDE2, 0.3, 0)    # 발바닥선
    for (x0, x1, y0, y1), nm in zip(bot_slots(), names[1]):
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(fr, ids, a, b, GUIDE, 0.25, 0)
        line(fr, ids, ((x0 + x1) / 2, y0 + 6), ((x0 + x1) / 2, y1 - 1), GUIDE, 0.2, 0)
        label(fr, ids, nm, (x0 + x1) / 2, y0 + 1.6, 4.2, 0)
    return fr


def build_template(with_example=None):
    seq = ET.Element('Sequence', dict(Name='character_sheet_v2', HeightWidthRatio='0.5625', RatioX='16', RatioY='9', FrameCount='3', BackgroundColor='-1'))
    ids = Ids(0, 0)
    f1 = guide_frame(seq, 0, '1 스틱맨', ids, (TOP, BOT))
    guide_frame(seq, 1, '2 실제 몸 (얼굴 · 머리카락 · 옷)', ids, (TOP, BOT))
    f3 = guide_frame(seq, 2, '3 근접 묘사 (손 · 표정 · 세부)', ids, None, with_slots=False)
    for (x0, x1), nm in (((3.0, 49.0), '손'), ((51.0, 97.0), '표정 · 세부')):
        for a, b in (((x0, 8), (x1, 8)), ((x1, 8), (x1, 97)), ((x1, 97), (x0, 97)), ((x0, 97), (x0, 8))):
            line(f3, ids, a, b, GUIDE, 0.25, 0)
        label(f3, ids, nm, (x0 + x1) / 2, 9.5, 4.2, 0)
    if with_example is not None:
        place_example(f1, with_example, ids)
    return seq


def load_v1(path):
    z = zipfile.ZipFile(path)
    return ET.fromstring(z.read(z.namelist()[0]))


def place_example(fr, v1, ids):
    """v1(시계 반대 90° 돌려 그린 6방향)을 시계 방향 90° 돌려 바로 세우고 칸에 맞춰 옮긴다.
    v1 배치: 왼쪽 세로줄 아래→위 = 정면·우측·좌측·후면, 오른쪽 세로줄 아래→위 = 위·아래(글자 양식을 돌린 것과 일치).
    레이어는 사용자 원본 앞뒤 순서 그대로(원본 ID 0·1·2 → char.back·char.mid·char.front): 후면에서 보석이 머리 뒤에 숨는 것처럼
    사용자가 레이어로 앞뒤를 나눴기 때문(액세서리 레이어로 옮기면 보석이 앞으로 나온다 — 11-05 첫 시험). 객체·점 ID는 그대로(면 FS 참조 유지), 양식 ID와 겹치지 않게 양식은 큰 번호 뒤에 둔다."""
    f = v1.find('Frame')
    aos = f.findall('AO')

    def rot(x, y):           # % → 화소 → 시계 방향 90°(새 x = −y, 새 y = x)
        return -y * PH / 100, x * PW / 100
    cen = []
    for a in aos:
        P = [rot(float(p.get('X')), float(p.get('Y'))) for p in a.findall('AP')]
        cen.append(np.mean(P, 0))
    cen = np.array(cen)
    # 묶음: 원래 x 기준 왼쪽/오른쪽 세로줄 → 새 y 기준 위/아래 줄, 그 안에서 새 x 순서
    ox = np.array([np.mean([float(p.get('X')) for p in a.findall('AP')]) for a in aos])
    oy = np.array([np.mean([float(p.get('Y')) for p in a.findall('AP')]) for a in aos])
    left = ox < 42.5   # 왼쪽 세로줄 x 13–41%, 오른쪽 42%~ (보석 선이 경계에 걸려 45로는 섞임)
    groups = {}
    for side, names, k in ((left, ['정면', '우측', '좌측', '후면'], 4), (~left, ['위', '아래'], 2)):
        idx = np.nonzero(side)[0]
        ys = np.sort(oy[idx])
        gaps = np.argsort(np.diff(ys))[::-1][:k - 1]
        cuts = sorted(ys[g] / 2 + ys[g + 1] / 2 for g in gaps)
        bins = np.searchsorted(cuts, oy[idx])
        for b_ in range(k):
            groups[names[k - 1 - b_]] = idx[bins == b_]        # 원래 아래(큰 y)가 첫 이름
    # 크기: 위 줄 네 방향은 같은 배율(가장 큰 키 = 정수리선~발바닥선), 아래 줄은 칸에 맞춘 같은 배율
    def bbox(ix):
        P = np.array([rot(float(p.get('X')), float(p.get('Y'))) for i in ix for p in aos[i].findall('AP')])
        return P.min(0), P.max(0)
    hmax = max(bbox(groups[n])[1][1] - bbox(groups[n])[0][1] for n in ['정면', '우측', '좌측', '후면'])
    s_top = (FOOT_Y - HEAD_Y) / 100 * PH / hmax
    bsz = [bbox(groups[n])[1] - bbox(groups[n])[0] for n in BOT]
    s_bot = min(min((bot_slots()[0][1] - bot_slots()[0][0] - 3) / 100 * PW / b[0], (BOT_Y1 - BOT_Y0 - 9) / 100 * PH / b[1]) for b in bsz)
    slot_of = {n: s for n, s in zip(TOP, top_slots())}
    slot_of.update({n: s for n, s in zip(BOT, bot_slots())})
    keep = []
    for n, ix in groups.items():
        lo, hi = bbox(ix)
        s = s_top if n in TOP else s_bot
        x0, x1, y0, y1 = slot_of[n]
        cxp = (x0 + x1) / 2 / 100 * PW
        if n in TOP:
            ty = FOOT_Y / 100 * PH - hi[1] * s            # 발끝을 발바닥선에
        else:
            ty = (y0 + 7 + (y1 - y0 - 8) / 2) / 100 * PH - (lo[1] + hi[1]) / 2 * s
        tx = cxp - (lo[0] + hi[0]) / 2 * s
        for i in ix:
            a = copy.deepcopy(aos[i])
            a.set('LayerId', str(int(a.get('LayerId')) + 1))
            for k_ in ('ThicknessScale', 'ObjectScale'):
                a.set(k_, f"{float(a.get(k_) or 1) * s:.4f}")
            for p in a.findall('AP'):
                X, Y = rot(float(p.get('X')), float(p.get('Y')))
                p.set('X', f'{(X * s + tx) / PW * 100:.4f}'); p.set('Y', f'{(Y * s + ty) / PH * 100:.4f}')
            keep.append(a)
    for a in keep:
        fr.append(a)
    for x in f.findall('FR'):
        fr.append(copy.deepcopy(x))
    return {n: len(ix) for n, ix in groups.items()}, s_top, s_bot


def renumber_template(seq, base_o, base_p):
    """양식 객체·점 ID를 예시(사용자 원래 ID)와 겹치지 않게 큰 번호로."""
    for fr in seq.findall('Frame'):
        for a in fr.findall('AO'):
            if a.get('LayerId') == '0' and int(a.get('ID')) < 100000:
                a.set('ID', str(base_o + int(a.get('ID')))); a.set('DrawOrder', a.get('ID'))
                for p in a.findall('AP'):
                    p.set('ID', str(base_p + int(p.get('ID'))))


def save(seq, path, name):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + '.xml', ET.tostring(seq, encoding='utf-8', xml_declaration=True))


def render(seq, k, W=1600, H=900):
    import sfa_render as R
    R.PARAMS.update(pad=0.0, thick_mul=W / 1920)
    return cv2.cvtColor(R.render_frame(seq, seq.findall('Frame')[k], W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)


def guide_png(seq_ex, path):
    """작성 안내 그림: 1장 예시 렌더 + 설명 화살표 + 규칙 목록."""
    base = Image.fromarray(cv2.cvtColor(render(seq_ex, 0), cv2.COLOR_BGR2RGB))
    W, H = base.size
    canvas = Image.new('RGB', (W, H + 760), 'white')
    canvas.paste(base, (0, 0))
    d = ImageDraw.Draw(canvas)
    f = lambda s: ImageFont.truetype(FONT, s, index=KR)
    red = (220, 30, 30)
    xs = [s[0] for s in top_slots()]
    hy, fy = HEAD_Y / 100 * H, FOOT_Y / 100 * H
    d.text((W * 0.005, hy - 30), '정수리선', fill=red, font=f(22))
    d.text((W * 0.005, fy + 4), '발바닥선', fill=red, font=f(22))
    x2 = (top_slots()[1][0] + top_slots()[1][1]) / 2 / 100 * W
    d.line([(x2 + 60, (HEAD_Y + 20) / 100 * H), (x2 + 4, (HEAD_Y + 24) / 100 * H)], fill=red, width=3)
    d.text((x2 + 64, (HEAD_Y + 17) / 100 * H), '가운데선(몸 중심축)', fill=red, font=f(20))
    d.text((x2 - 95, (HEAD_Y + 33) / 100 * H), '(비워 둔 칸 — 새로 그려 주세요)', fill=red, font=f(17))
    y = H + 20
    d.text((30, y), '캐릭터 시트 양식 v2 — 작성 안내', fill=(0, 0, 0), font=f(40)); y += 64
    rules = [
        '① 장 나누기:  1장 = 스틱맨 버전,  2장 = 실제 몸(얼굴·머리카락·옷),  3장 = 근접 묘사(손 모양·표정·세부).',
        '② 위 줄 다섯 칸(정면·반측면·우측·좌측·후면)은 똑바로 그립니다. 발은 발바닥선, 정수리는 정수리선에 맞춥니다.',
        '     → 다섯 칸 모두 같은 크기(같은 키). 몸 중심은 칸의 세로 가운데선에.',
        '③ 반측면 = 정면과 측면 사이(약 45°로 돌아선 모습). 액션 장면에서 가장 많이 나오는 각도입니다.',
        '④ 아래 줄(위·아래)은 비스듬하게(부감·앙각) 그려도 됩니다. 대략의 방향·각도는 설명 글에 적어 주세요.',
        '⑤ 레이어(앞뒤 순서):  sheet.guide = 양식(잠김)  ·  char.back = 몸 뒤에 오는 것  ·  char.mid = 몸  ·  char.front = 몸 앞에 오는 것.',
        '     → 예: 후면에서 이마 보석은 머리 뒤(char.back), 정면에서는 앞(char.front). 레이어 이름은 바꾸지 마세요.',
        '⑥ 액세서리가 무엇인지(이름·붙는 곳·흔들림)는 설명 글에 적어 주세요.',
        '⑦ 설명 글(따로 보내는 글 파일): 이름 · 색 · 비율 메모 · 액세서리마다 붙는 곳과 흔들림 여부 · 위/아래 칸 각도 · 그 밖의 특징.',
        '⑧ 무기는 이 시트가 아니라 무기 파일 + 무기를 든 정지 컷으로 따로 보냅니다.',
    ]
    for r_ in rules:
        d.text((40, y), r_, fill=(20, 20, 20), font=f(26)); y += 70
    canvas.save(path)


DESC = """# 캐릭터 설명 글 양식 (캐릭터 시트 v2와 함께 보내 주세요)

이름:
한 줄 소개:

## 색
- 스틱맨 선 색:
- 머리(원) 안 색:
- 그 밖의 색:

## 비율·체형 메모
- (예: 다리가 긴 편, 머리가 작은 편, 어깨가 넓음)

## 액세서리 (하나마다)
- 이름:
  - 붙는 곳: (예: 머리 위 / 목 / 오른손목 / 허리)
  - 흔들림: 없음(단단함) / 있음(망토·끈처럼 늘어지고 펄럭임)
  - 특징:

## 위·아래 칸 각도
- 위: (예: 앞쪽 위에서 약 45도로 내려다봄)
- 아래: (예: 앞쪽 아래에서 약 30도로 올려다봄)

## 실제 몸(2장) 메모
- 얼굴·머리카락·옷의 특징:

## 그 밖의 특징
-
"""


def main():
    v1p, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    empty = build_template()
    save(empty, os.path.join(out, 'character_sheet_v2.sfa'), 'character_sheet_v2')
    v1 = load_v1(v1p)
    ex = build_template()
    renumber_template(ex, 10_000_000, 90_000_000)
    info = place_example(ex.findall('Frame')[0], v1, Ids(0, 0))
    ex.set('Name', 'character_sheet_v2_example')
    save(ex, os.path.join(out, 'character_sheet_v2_example.sfa'), 'character_sheet_v2_example')
    guide_png(ex, os.path.join(out, 'character_sheet_v2_guide.png'))
    for k in range(3):
        cv2.imwrite(os.path.join(out, f'render_empty_{k + 1}.png'), render(empty, k, 1280, 720))
    open(os.path.join(out, 'character_sheet_v2_설명양식.txt'), 'w', encoding='utf-8').write(DESC)
    print('예시 칸별 객체', info[0], '배율 위/아래', round(info[1], 3), round(info[2], 3))
    print('빈 양식 객체', sum(len(f.findall('AO')) for f in empty.findall('Frame')))


if __name__ == '__main__':
    main()
