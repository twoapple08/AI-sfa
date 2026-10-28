"""person_scan.py 결과로 확인 시트(군별 30칸 JPG)와 bins.json을 만든다 (2026-10-28). 시트는 학습 원본 장면이라 저장소에 넣지 않는다.
사용: python -I tools/person_sheets.py scan.json <조각 폴더> <출력 폴더>
"""
import sys, json, os, cv2, numpy as np
scan = json.load(open(sys.argv[1])); vdir, odir = sys.argv[2], sys.argv[3]; os.makedirs(odir, exist_ok=True)
bins = [('1군_크고지속_면적10%이상_5장중3장이상', lambda r: r.get('conf', 0) >= 0.5 and r['area'] >= 0.10 and r['hits'] >= 3),
        ('2군_크지만잠깐_면적10%이상_1-2장', lambda r: r.get('conf', 0) >= 0.5 and r['area'] >= 0.10 and r['hits'] < 3),
        ('3군_작은인물_10%미만', lambda r: r.get('conf', 0) >= 0.5 and r['area'] < 0.10),
        ('4군_의심_확신낮음', lambda r: 0 < r.get('conf', 0) < 0.5)]
summary = {}
for name, f in bins:
    rows = sorted([r for r in scan if 'conf' in r and f(r)], key=lambda r: -r['area'])
    summary[name] = [r['clip'] for r in rows]
    tiles = []
    for r in rows:
        c = cv2.VideoCapture(os.path.join(vdir, r['clip'] + '.mp4')); c.set(1, r['frame']); ok, im = c.read()
        if not ok: continue
        b = np.array(r['box']).astype(int); cv2.rectangle(im, (b[0], b[1]), (b[2], b[3]), (0, 255, 0), 2)
        im = cv2.resize(im, (320, 180)); cv2.rectangle(im, (0, 0), (320, 20), (0, 0, 0), -1)
        cv2.putText(im, f"{r['clip']} {r['area']*100:.0f}% c{r['conf']:.2f} {r['hits']}/{r['sampled']}", (3, 15), 0, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(im)
    for pg in range(0, len(tiles), 30):
        t = tiles[pg:pg + 30]
        while len(t) % 5: t.append(np.zeros((180, 320, 3), np.uint8))
        cv2.imwrite(os.path.join(odir, f"{name}_{pg // 30 + 1}.jpg"), np.vstack([np.hstack(t[i:i + 5]) for i in range(0, len(t), 5)]), [cv2.IMWRITE_JPEG_QUALITY, 85])
summary['none'] = [r['clip'] for r in scan if 'conf' not in r]
json.dump(summary, open(os.path.join(odir, 'bins.json'), 'w'), ensure_ascii=False, indent=0)
print({k: len(v) for k, v in summary.items()}, '전체', len(scan))
