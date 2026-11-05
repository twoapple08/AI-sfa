"""포즈 검출기 비교 보고(2026-11-05): 같은 30구간을 RTMW / ViTPose / Sapiens 관절로 각각 스틱맨 변환한 결과를 오류 지표와 나란히 영상으로.

사용: python tools/pose_cmp_report.py <기준 작업 폴더(RTMW)> <출력 폴더> <모델 작업 폴더 ...>
  각 작업 폴더는 stage2_extract.py를 STAGE2_SEGMENTS(기준 summary.json 구간 고정)로 돌린 결과(out/)를 가진다.
지표(구간 장 수 대비, 수정 파일 미적용 결과로 잰다 — 검출기 자체 비교):
  튐: 끝점(골반 기준)이 한 장에 몸통 0.8 넘게 이동 / 접힘: 뼈 길이 < 0.4 × 구간 중앙값 / 예상 다리: inferred 장
  원본 대조 눈 판정이 정답이다. 지표는 차이를 찾는 보조다.
"""
import json, os, sys
import cv2, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stage2_tag_sheets import crop169  # noqa: E402

SEG = {2: ('neck', 'pelvis'), 3: ('neck', 'elb_r'), 4: ('elb_r', 'wri_r'), 5: ('neck', 'elb_l'), 6: ('elb_l', 'wri_l'),
       7: ('pelvis', 'kne_r'), 8: ('kne_r', 'ank_r'), 9: ('pelvis', 'kne_l'), 10: ('kne_l', 'ank_l')}
END = ('wri_r', 'wri_l', 'ank_r', 'ank_l', 'elb_r', 'elb_l', 'kne_r', 'kne_l')


def metrics(ir):
    a = ir['actors'][0]; N = ir['frames']
    J = {k: np.array([[np.nan, np.nan] if p is None else p for p in v], float) * [1, 0.5625] for k, v in a['joints'].items()}
    T = np.nanmedian(np.linalg.norm(J['neck'] - J['pelvis'], axis=1))
    jump = set()
    for k in END:
        d = np.linalg.norm(np.diff(J[k] - J['pelvis'], axis=0), axis=1) / T
        jump |= set((np.flatnonzero(d > 0.8) + 1).tolist())
    fold = set()
    for o, (p, q) in SEG.items():
        L = np.linalg.norm(J[p] - J[q], axis=1)
        fold |= set(np.flatnonzero(L < 0.4 * np.nanmedian(L)).tolist())
    inf = sum(bool(x) for x in a.get('inferred', []))
    return dict(frames=N, jump=len(jump), fold=len(fold), inferred=inf)


def draw(ir, n, im, tw, th, pad):
    c = np.full((th + pad, tw, 3), 235, np.uint8); c[:th] = (im * 0.35 + 255 * 0.65).astype(np.uint8)
    cv2.line(c, (0, th), (tw, th), (120, 120, 120), 1)
    for a in ir['actors']:
        J = a['joints']
        P = lambda k: (int(J[k][n][0] / 100 * tw), int(J[k][n][1] / 100 * th)) if J[k][n] else None
        if P('neck') is None: continue
        hid = set(a['hidden'][n]); inf = set((a.get('inferred') or [[]] * ir['frames'])[n])
        base = (200, 40, 20) if a['slot'] == 0 else (30, 30, 210)
        for o, (p, q) in SEG.items():
            if o in hid or P(p) is None or P(q) is None: continue
            cv2.line(c, P(p), P(q), (0, 140, 255) if o in inf else base, 2, cv2.LINE_AA)
        if P('head_t') and P('head_b'):
            cc = ((P('head_t')[0] + P('head_b')[0]) // 2, (P('head_t')[1] + P('head_b')[1]) // 2)
            r = int(np.hypot(P('head_t')[0] - P('head_b')[0], P('head_t')[1] - P('head_b')[1]) / 2)
            cv2.circle(c, cc, r, (255, 255, 255), -1, cv2.LINE_AA); cv2.circle(c, cc, r, base, 2, cv2.LINE_AA)
    return c


def main():
    base, outd, others = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(outd, exist_ok=True)
    works = [base] + others
    names = ['rtmw'] + [w.rsplit('_', 1)[-1] for w in others]
    S = {s['video'] + '_' + str(s['start']): s for s in json.load(open(f'{base}/out/summary.json'))['segments']}
    table, irs = {}, {}
    for nm, w in zip(names, works):
        for s in json.load(open(f'{w}/out/summary.json'))['segments']:
            key = s['video'] + '_' + str(s['start'])
            if key not in S: continue
            ir = json.load(open(f"{w}/out/{s['name']}.json"))
            irs[(nm, key)] = ir; table.setdefault(key, {})[nm] = metrics(ir)
    tot = {nm: {m: sum(table[k][nm][m] for k in table if nm in table[k]) for m in ('frames', 'jump', 'fold', 'inferred')} for nm in names}
    json.dump(dict(total=tot, per_segment=table), open(f'{outd}/pose_cmp_metrics.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(tot, ensure_ascii=False))
    tw, th, pad = 400, 225, 90
    vw = cv2.VideoWriter(f'{outd}/f.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 24, (tw * (len(names) + 1), th + pad + 26))
    for key in sorted(table):
        s = S[key]; cap = cv2.VideoCapture(f"{base}/video/{s['video']}.mp4")
        for n in range(s['frames']):
            cap.set(cv2.CAP_PROP_POS_FRAMES, s['start'] + n); ok, im = cap.read()
            if not ok: break
            im = cv2.resize(crop169(im), (tw, th))
            left = np.full((th + pad, tw, 3), 60, np.uint8); left[:th] = im
            cols = [left] + [draw(irs[(nm, key)], n, im, tw, th, pad) if (nm, key) in irs and n < irs[(nm, key)]['frames']
                             else np.zeros((th + pad, tw, 3), np.uint8) for nm in names]
            h = np.zeros((26, tw * len(cols), 3), np.uint8)
            cv2.putText(h, f"{s['name']} k{n}", (6, 18), 0, 0.5, (255, 255, 255), 1)
            for i, nm in enumerate(names):
                cv2.putText(h, nm, (tw * (i + 1) + 6, 18), 0, 0.55, (0, 255, 255), 1)
            vw.write(np.vstack([h, np.hstack(cols)]))
    vw.release()
    os.system(f"ffmpeg -y -loglevel error -i {outd}/f.mp4 -c:v libx264 -pix_fmt yuv420p -crf 24 {outd}/pose_cmp.mp4 && rm {outd}/f.mp4")


if __name__ == '__main__':
    main()
