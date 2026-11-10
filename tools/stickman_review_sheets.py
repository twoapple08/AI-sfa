"""원본 대조 시트(사람 눈 판정용). 출력 그림은 원본 장면을 담으므로 비공개 경로에만 저장한다.
렌더는 sfa_overlay_video의 앱 순서 흉내(서버 미리보기)이며 앱 표시 확인이 아니다.

  ab      두 SFA를 원본 위에 나란히 [A | B]                      (판 비교)
  diff    두 SFA 렌더가 다른 곳 확대: 원본 | A | B              (바뀐 곳만)
  cross   두 인물 선·머리 교차점 120px 확대: 원본 | SFA          (앞뒤 대조)
  heads   한 인물 머리 확대 띠(장 범위)                          (정면/뒷모습 판독)
  dets    RTMW 검출 전부(노랑) + 고른 검출(빨강/파랑)            (인물 고르기 점검)
  keys    장면 판독 키 점을 SFA 위에                            (키와 자동 결과 대조)

장 목록은 '1103,1105' 또는 '1101-1118'.
예: python tools/stickman_review_sheets.py ab 이전.sfa 새.sfa --frames-dir 프레임 --base 1032 --list 1101-1118 --out 비교.jpg
"""
import argparse
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as E

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfa_render as R  # noqa: E402
from sfa_overlay_video import render_alpha  # noqa: E402

W, H = 1152, 648
FONT = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'


def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except OSError:
        return ImageFont.load_default()


def load(p):
    z = zipfile.ZipFile(p)
    return E.fromstring(z.read(z.namelist()[0]))


def frames_of(s):
    if '-' in s and ',' not in s:
        a, b = map(int, s.split('-'))
        return list(range(a, b + 1))
    return [int(x) for x in s.split(',')]


def orig(fd, n):
    return np.asarray(Image.open(f'{fd}/{n}.png').convert('RGB')).astype(np.float32)


def solo(root, n, base):
    b, a = render_alpha(root, root.findall('Frame')[n - base], W, H)
    return b + 255 * (1 - a[:, :, None]), b, a


def img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def grid(cells, cols, out, bg=(20, 20, 20)):
    w = max(c.width for c in cells); h = max(c.height for c in cells)
    sh = Image.new('RGB', (cols * (w + 6), ((len(cells) + cols - 1) // cols) * (h + 6)), bg)
    for i, c in enumerate(cells):
        sh.paste(c, ((i % cols) * (w + 6), (i // cols) * (h + 6)))
    sh.save(out, quality=86)
    return out


def head_info(root, scene, n, base):
    import sfa_depth_layers as D
    sc = json.load(open(scene))
    cs = {int(v['smear_color']): v['slot'] for v in sc['actors'].values()}
    return D.classify_frame(root.findall('Frame')[n - base], cs)


def cmd_ab(a):
    A, B = load(a.sfa[0]), load(a.sfa[1]); f = font(15); cells = []
    for n in frames_of(a.list):
        o = orig(a.frames_dir, n) * .55 + 255 * .45
        c = Image.new('RGB', (2 * (W // 3) + 4, H // 3), (20, 20, 20))
        for i, (r, lab) in enumerate(((A, a.labels[0]), (B, a.labels[1]))):
            _, b, al = solo(r, n, a.base)
            im = img(b + o * (1 - al[:, :, None])).resize((W // 3, H // 3))
            ImageDraw.Draw(im).text((3, 2), f'{n} {lab}', fill=(255, 255, 0), font=f, stroke_width=2, stroke_fill=(0, 0, 0))
            c.paste(im, (i * (W // 3 + 4), 0))
        cells.append(c)
    return grid(cells, 2, a.out)


def cmd_diff(a):
    A, B = load(a.sfa[0]), load(a.sfa[1]); f = font(16); PS = 240; cells = []
    for n in frames_of(a.list):
        sa, _, _ = solo(A, n, a.base); sb, _, _ = solo(B, n, a.base)
        ys, xs = np.nonzero(np.abs(sa - sb).max(2) > 40)
        if not len(xs):
            continue
        cx, cy = np.median(xs), np.median(ys)
        h = max(60, min(200, (np.percentile(xs, 90) - np.percentile(xs, 10) + np.percentile(ys, 90) - np.percentile(ys, 10)) / 2))
        x0, y0 = int(np.clip(cx - h, 0, W - 2 * h)), int(np.clip(cy - h, 0, H - 2 * h)); x1, y1 = int(x0 + 2 * h), int(y0 + 2 * h)
        c = Image.new('RGB', (3 * PS + 8, PS + 22), (40, 40, 40))
        ImageDraw.Draw(c).text((2, 2), f'{n}  원본 | {a.labels[0]} | {a.labels[1]}', fill=(255, 255, 0), font=f)
        for i, im in enumerate((orig(a.frames_dir, n), sa, sb)):
            c.paste(img(im[y0:y1, x0:x1]).resize((PS, PS)), (i * (PS + 4), 22))
        cells.append(c)
    return grid(cells, 2, a.out) if cells else None


def cmd_cross(a):
    import sfa_depth_layers as D
    root = load(a.sfa[0]); src = load(a.source) if a.source else root; f = font(14); cells = []
    for n in frames_of(a.list):
        _, _, lines, heads = head_info(src, a.scene, n, a.base)
        pts = []
        for ka in [k for k in lines if k[0] == 0]:
            for kb in [k for k in lines if k[0] == 1]:
                for p1, p2, wa, _ in lines[ka]:
                    for q1, q2, wb, _ in lines[kb]:
                        d, c = D.seg_closest(p1, p2, q1, q2)
                        if d < (wa + wb) / 2:
                            pts.append((c, f'{ka[0]}:{ka[1]}x{kb[0]}:{kb[1]}'))
        seen = []
        for c, _ in pts:
            if not any(np.linalg.norm(c - q) < 40 for q in seen):
                seen.append(c)
        o = orig(a.frames_dir, n); s, _, _ = solo(root, n, a.base)
        for c in seen[:6]:
            lab = [l for q, l in pts if np.linalg.norm(q - c) < 40][0]
            x0, y0 = int(np.clip(c[0] - 60, 0, W - 120)), int(np.clip(c[1] - 60, 0, H - 120))
            cell = Image.new('RGB', (406, 222), (40, 40, 40)); ImageDraw.Draw(cell).text((2, 2), f'{n} {lab}', fill=(255, 255, 0), font=f)
            cell.paste(img(o[y0:y0 + 120, x0:x0 + 120]).resize((200, 200)), (0, 22)); cell.paste(img(s[y0:y0 + 120, x0:x0 + 120]).resize((200, 200)), (206, 22))
            cells.append(cell)
    return grid(cells, 3, a.out) if cells else None


def cmd_heads(a):
    root = load(a.sfa[0]); f = font(13); cells = []
    for n in frames_of(a.list):
        _, _, _, heads = head_info(root, a.scene, n, a.base)
        cc = Image.new('RGB', (130, 144), (30, 30, 30))
        if a.slot in heads:
            c, rad = heads[a.slot]; h = max(45, rad * 2.2)
            cc.paste(Image.open(f'{a.frames_dir}/{n}.png').convert('RGB').crop((int(c[0] - h), int(c[1] - h * .8), int(c[0] + h), int(c[1] + h * 1.2))).resize((130, 130)), (0, 14))
        ImageDraw.Draw(cc).text((2, 0), str(n), fill=(255, 255, 0), font=f); cells.append(cc)
    return grid(cells, 12, a.out)


def cmd_dets(a):
    from rtmw_to_stickman_2d import load_rtmw, pick_target
    Rt = load_rtmw(a.rtmw); fr = frames_of(a.list); f = font(16)
    picks = {c: pick_target(Rt, fr, a.video, c, strict=True, select='coverage') for c in ('red', 'blue')}
    EDGES = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (11, 12), (5, 11), (6, 12), (11, 13), (13, 15), (12, 14), (14, 16)]
    cells = []
    for t, n in enumerate(fr):
        im = Image.open(f'{a.frames_dir}/{n}.png').convert('RGB'); d = ImageDraw.Draw(im)
        for k, col, w in [(np.asarray(k), (255, 255, 0), 2) for _, k in Rt.get(n, [])] + \
                [(picks[c][t], col, 5) for c, col in (('red', (255, 0, 0)), ('blue', (0, 0, 255))) if picks[c][t] is not None]:
            for u, v in EDGES:
                if k[u, 2] > 1.5 and k[v, 2] > 1.5:
                    d.line([k[u, 0], k[u, 1] - a.crop_y, k[v, 0], k[v, 1] - a.crop_y], fill=col, width=w)
        d.text((4, 4), str(n), fill=(255, 255, 0), font=f); cells.append(im.resize((460, 259)))
    return grid(cells, 4, a.out)


def cmd_keys(a):
    root = load(a.sfa[0]); sc = json.load(open(a.scene)); f = font(16); cells = []
    for n in frames_of(a.list):
        o = orig(a.frames_dir, n) * .5 + 255 * .5; _, b, al = solo(root, n, a.base)
        im = img(b + o * (1 - al[:, :, None])); d = ImageDraw.Draw(im)
        for v in sc.get('visible_views', []) + sc.get('partials', []):
            k = v.get('keys', {}).get(str(n))
            if not k:
                continue
            col = (0, 160, 0) if v['actor'] == 'red' else (255, 140, 0)
            for name, (x, y) in k.items():
                y -= a.crop_y; d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col); d.text((x + 8, y - 8), name, fill=col, font=f)
        d.text((4, 4), f'{n}  초록=빨강 키, 주황=파랑 키', fill=(0, 0, 0), font=f); cells.append(im.resize((W // 2, H // 2)))
    return grid(cells, 2, a.out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['ab', 'diff', 'cross', 'heads', 'dets', 'keys'])
    ap.add_argument('sfa', nargs='*')
    ap.add_argument('--frames-dir', required=True, help='원본 프레임(장번호.png, 위 crop 뺀 1152×648)')
    ap.add_argument('--base', type=int, default=1032, help='SFA 첫 장의 원본 장 번호')
    ap.add_argument('--list', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--labels', nargs=2, default=['이전', '새'])
    ap.add_argument('--scene', help='cross/heads: 스미어 장면(actors), keys: 스틱맨 장면')
    ap.add_argument('--source', help='cross: 교차점을 찾을 원래(깊이 칸 전) SFA')
    ap.add_argument('--slot', type=int, default=0)
    ap.add_argument('--rtmw'); ap.add_argument('--video'); ap.add_argument('--crop-y', type=float, default=63)
    a = ap.parse_args()
    R.PARAMS.update(pad=0, thick_mul=W / 1920)
    print(globals()['cmd_' + a.cmd](a))


if __name__ == '__main__':
    main()
