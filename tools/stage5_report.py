"""단계 5 결과 채점·시트·영상: Kaggle stage5_gen.jsonl(표본마다 chunks = [처음 32장, 이어 만들기 24장 ×2]) →
- 되돌림: 조각마다 동작으로 되돌릴 수 있는 비율, 조각 장 수(요청 32·24장과 비교)
- 이음매: 조각 경계(앞 조각 마지막 키 → 다음 조각 첫 키)의 자세 변화 ÷ 조각 안 이웃 키 자세 변화 중앙값(1 근처면 자연스럽게 이어짐, 크면 튐)
- 리듬: stage5_score.style_score(nian41 유지 리듬 L1·예비 동작) — 층별(스타일 글 / 참고 글). 기준선: nian41 되돌림 0.064, 수집 SFA 0.622
- 그럴듯함: 이어 붙인 동작의 장마다 stage4_pack.plausible 통과 비율
출력: stage5_score.json, stage5_sheet_*.jpg(표본마다 4장 간격 줄), stage5_*.mp4·.sfa(캐릭터 시트 입힘, 앞 6개)
사용: python tools/stage5_report.py <stage5_gen.jsonl> <출력 폴더> [캐릭터 시트.sfa]
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motion_tokens as MT, stage4_pack as P, stage5_score as SS, tokens_to_sfa as T  # noqa: E402

K = 23
REQ = [32, 24, 24]


def keys(tokens):
    """토큰 → 키프레임 자세 벡터 목록(골반 기준·몸통 단위)."""
    body = [t for t in tokens if t not in ('<motion>', '</motion>')]
    out = []
    for i in range(0, len(body) - K + 1, K):
        ir = MT.decode(['<motion>'] + body[i:i + K] + ['</motion>'])
        if ir is not None: out.append(P.pose_vec(ir))
    return out


def seam_ratio(chunks):
    """조각 경계 자세 변화 ÷ 조각 안 이웃 키 자세 변화 중앙값. 경계가 없으면 None."""
    ks = [keys(c) for c in chunks]
    inner = [float(np.linalg.norm(a - b)) / math.sqrt(len(a) / 2) for k in ks for a, b in zip(k, k[1:])]
    seams = [float(np.linalg.norm(ks[i][-1] - ks[i + 1][0])) / math.sqrt(len(ks[i][-1]) / 2)
             for i in range(len(ks) - 1) if ks[i] and ks[i + 1]]
    if not seams or not inner: return None
    m = float(np.median(inner)) or 1e-6
    return [round(s / m, 2) for s in seams]


def frame_plausible(ir):
    """이어 붙인 동작의 장마다 plausible(한 장짜리로 잘라 검사) 통과 비율."""
    a = ir['actors'][0]; ok = 0
    for n in range(ir['frames']):
        one = dict(ir, frames=1, actors=[dict(a, joints={k: [v[n]] for k, v in a['joints'].items()})])
        ok += bool(P.plausible(one))
    return ok / max(ir['frames'], 1)


def evaluate(gen):
    rows, joined = [], {'style': [], 'ref': []}
    for g in gen:
        ch = g['chunks']
        dec = [MT.decode(c) for c in ch]
        lens = [d['frames'] if d else 0 for d in dec]
        full = T.join(ch) if all(dec) else None
        ir = MT.decode(full) if full else None
        rows.append(dict(src=g['src'], layer=g['layer'], chunks=len(ch), decoded=[d is not None for d in dec], frames=lens,
                         total=ir['frames'] if ir else 0, seam=seam_ratio(ch) if all(dec) else None,
                         plausible=round(frame_plausible(ir), 3) if ir else None))
        if full: joined[g['layer']].append(full)
    def agg(rs):
        sm = [s for r in rs if r['seam'] for s in r['seam']]
        return dict(n=len(rs),
                    decoded_chunks=round(float(np.mean([x for r in rs for x in r['decoded']])), 3) if rs else None,
                    full_3_chunks=sum(r['chunks'] == 3 and all(r['decoded']) for r in rs),
                    frames_vs_request=[round(float(np.median([r['frames'][i] for r in rs if len(r['frames']) > i])), 1) if any(len(r['frames']) > i for r in rs) else None for i in range(3)],
                    seam_ratio_median=round(float(np.median(sm)), 2) if sm else None, seam_over_3=sum(s > 3 for s in sm), seams=len(sm),
                    plausible_median=round(float(np.median([r['plausible'] for r in rs if r['plausible'] is not None])), 3) if any(r['plausible'] is not None for r in rs) else None)
    sc = dict(all=agg(rows), style=agg([r for r in rows if r['layer'] == 'style']), ref=agg([r for r in rows if r['layer'] == 'ref']),
              requested=REQ, rhythm={k: SS.style_score(v) for k, v in joined.items() if v},
              rhythm_baseline=dict(nian41_roundtrip=0.064, user_sfa=0.622))
    return sc, rows


def sheet(gen, outd, per=10, step=4, tw=160, th=90):
    import cv2, motion_ir as M, sfa_render as R
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 14)
    R.PARAMS.update(pad=0.0, thick_mul=tw / 1920)
    for p0 in range(0, len(gen), per):
        lines = []
        for g in gen[p0:p0 + per]:
            try: ir, root = T.build(g['chunks'], center=True)
            except ValueError: continue
            F = root.findall('Frame'); seams = np.cumsum([MT.decode(c)['frames'] if MT.decode(c) else 0 for c in g['chunks']])[:-1]
            tiles = []
            for k in range(0, len(F), step):
                im = cv2.cvtColor(R.render_frame(root, F[k], tw, th)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR)
                cv2.putText(im, str(k), (3, 12), 0, 0.35, (0, 0, 200) if any(abs(k - s) < step for s in seams) else (90, 90, 90), 1)
                tiles.append(im)
            row = np.hstack(tiles[:20] + [np.full((th, tw, 3), 255, np.uint8)] * max(0, 20 - len(tiles)))
            cap = Image.new('RGB', (row.shape[1], 20), 'white'); ImageDraw.Draw(cap).text((4, 1), (g['layer'] + ' | ' + g['prompt'].replace('<ref> ', ''))[:110], fill=(0, 0, 0), font=f)
            lines.append(np.vstack([np.array(cap)[:, :, ::-1], row]))
        if lines: cv2.imwrite(f'{outd}/stage5_sheet_{p0 // per + 1}.jpg', np.vstack(lines), [cv2.IMWRITE_JPEG_QUALITY, 82])


def videos(gen, outd, sheet_path, n=6, W=640, H=360):
    import cv2, motion_ir as M, sfa_render as R
    R.PARAMS.update(pad=0.0, thick_mul=W / 1920)
    for i, g in enumerate(gen[:n]):
        try: ir, root = T.build(g['chunks'], sheet_path, center=True, name=f'stage5_{i}')
        except ValueError: continue
        M.save_sfa(root, f'{outd}/stage5_{i}.sfa', f'stage5_{i}')
        vw = cv2.VideoWriter(f'{outd}/stage5_{i}.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 24, (W, H))
        for fr in root.findall('Frame'):
            vw.write(cv2.cvtColor(R.render_frame(root, fr, W, H)[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR))
        vw.release()


def main(genp, outd, sheet_path=None):
    os.makedirs(outd, exist_ok=True)
    gen = [json.loads(l) for l in open(genp, encoding='utf-8')]
    sc, rows = evaluate(gen)
    json.dump(dict(score=sc, rows=rows), open(f'{outd}/stage5_score.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(sc, ensure_ascii=False))
    sheet(gen, outd)
    if sheet_path: videos(gen, outd, sheet_path)


if __name__ == '__main__':
    main(*sys.argv[1:4])
