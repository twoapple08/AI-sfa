"""단계 4 결과 채점·시트: Kaggle stage4_gen.jsonl → 점수(stage4_pack.score) + 글·정답·생성 나란히 시트.
사용: python tools/stage4_report.py <stage4_gen.jsonl> <poses.jsonl> <출력 폴더>
"""
import json, os, sys
import cv2, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT, motion_ir as M, sfa_render as R, stage4_pack as P  # noqa: E402
from PIL import Image, ImageDraw, ImageFont

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def draw(tokens, w=220, h=124):
    ir = MT.decode(tokens)
    if ir is None:
        im = np.full((h, w, 3), 230, np.uint8); cv2.putText(im, 'decode fail', (40, 64), 0, 0.5, (0, 0, 200), 1); return im
    R.PARAMS.update(pad=0.0, thick_mul=w / 1920)
    sf = M.compile_ir(ir, name='p')
    return cv2.cvtColor(R.render_frame(sf, sf.findall('Frame')[0], w, h)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)


def main(genp, posesp, outd):
    os.makedirs(outd, exist_ok=True)
    gen = [json.loads(l) for l in open(genp, encoding='utf-8')]
    rows = [json.loads(l) for l in open(posesp, encoding='utf-8')]
    held = {g['src'] for g in gen}
    train = [r for r in rows if r['src'] not in held]
    sc = dict(all=P.score([g['gen'] for g in gen], train, [dict(tokens=g['ref']) for g in gen]))
    for lay in ('style', 'ref'):
        gg = [g for g in gen if g['layer'] == lay]
        if gg: sc[lay] = P.score([g['gen'] for g in gg], train)
    json.dump(sc, open(f'{outd}/stage4_score.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(sc, ensure_ascii=False))
    f = ImageFont.truetype(FONT, 15)
    for page in range(0, min(len(gen), 48), 12):
        tiles = []
        for g in gen[page:page + 12]:
            a, b = draw(g['ref']), draw(g['gen'])
            pair = np.hstack([a, np.full((124, 4, 3), 255, np.uint8), b])
            txt = Image.new('RGB', (pair.shape[1], 46), 'white'); d = ImageDraw.Draw(txt)
            p = g['prompt'].replace('<ref> ', '')
            d.text((4, 2), p[:30], fill=(0, 0, 0), font=f); d.text((4, 22), p[30:60], fill=(0, 0, 0), font=f)
            tiles.append(np.vstack([np.array(txt)[:, :, ::-1], pair]))
        while len(tiles) % 3: tiles.append(np.full_like(tiles[0], 255))
        img = np.vstack([np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)])
        cv2.imwrite(f'{outd}/stage4_sheet_{page // 12 + 1}.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])


if __name__ == '__main__':
    main(*sys.argv[1:4])
