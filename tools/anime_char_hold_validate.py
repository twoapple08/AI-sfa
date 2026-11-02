"""M1 검증 표본: 문턱 보정 구간(1913: 300–311, 1500–1511) 밖에서 장 쌍을 무작위로 뽑아 시트로 만든다.
범주: 정지 후보(c<0.1), 경계(0.1<=c<0.3), 변화(c>=0.3), 긴 정지(문턱 0.2로 4장 이상 유지: 첫 장 vs 끝 장).
시트에는 범주를 쓰지 않는다(눈 판정 블라인드). 정답표는 key.json에 따로 둔다.
"""
import sys, os, json, random
import numpy as np, cv2
sys.path.insert(0, sys.argv[1])  # tools 경로
import anime_char_hold as A

vids = sys.argv[2:-1]
out = sys.argv[-1]
os.makedirs(out, exist_ok=True)
rng = random.Random(20261102)
EXCL = {'1913231262086463573.mp4': [(295, 316), (1495, 1516)]}
cands = {'hold': [], 'border': [], 'change': [], 'long': []}
chs = {}
for v in vids:
    masks, _ = A.read_masks(v)
    ch = A.changes(masks)
    name = os.path.basename(v)
    chs[name] = ch
    ex = EXCL.get(name, [])
    ok = lambda i: not any(a <= i <= b for a, b in ex)
    for i, c in enumerate(ch):
        if c is None or not ok(i):
            continue
        cat = 'hold' if c < 0.1 else ('border' if c < 0.3 else 'change')
        cands[cat].append((v, i, i + 1, round(c, 3)))
    # 긴 정지(문턱 0.2): 연속 4장 이상 유지된 구간의 첫 장과 끝 장
    i = 0
    while i < len(ch):
        j = i
        while j < len(ch) and ch[j] is not None and ch[j] < 0.2:
            j += 1
        if j - i >= 3 and ok(i):
            cands['long'].append((v, i, j, round(max(ch[i:j]), 3)))
        i = j + 1
pick = []
for cat, n in (('hold', 8), ('border', 8), ('change', 6), ('long', 6)):
    pool = cands[cat]
    sel = rng.sample(pool, min(n, len(pool)))
    pick += [(cat,) + s for s in sel]
rng.shuffle(pick)

def grab(v, idx):
    cap = cv2.VideoCapture(v)
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    return fr

tiles, key = [], []
for k, (cat, v, a, b, c) in enumerate(pick):
    f1, f2 = grab(v, a), grab(v, b)
    m = (A.char_mask(f1) + A.char_mask(f2)) > 0
    ys, xs = np.nonzero(m)
    sc = f1.shape[1] / A.W
    if len(xs) == 0:
        x0, y0, x1, y1 = 0, 0, f1.shape[1], f1.shape[0]
    else:
        x0, x1 = int(xs.min() * sc), int((xs.max() + 1) * sc)
        y0, y1 = int(ys.min() * sc), int((ys.max() + 1) * sc)
        pad = int(0.08 * max(x1 - x0, y1 - y0)) + 8
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(f1.shape[1], x1 + pad), min(f1.shape[0], y1 + pad)
    crops = [cv2.resize(f[y0:y1, x0:x1], (200, int(200 * (y1 - y0) / max(1, x1 - x0)))) for f in (f1, f2)]
    hh = 260
    crops = [cv2.resize(cr, (int(cr.shape[1] * hh / cr.shape[0]), hh)) if cr.shape[0] > hh else cr for cr in crops]
    H = max(cr.shape[0] for cr in crops) + 30
    Wt = sum(cr.shape[1] for cr in crops) + 30
    tile = np.full((H, Wt, 3), 255, np.uint8)
    x = 10
    for cr in crops:
        tile[25:25 + cr.shape[0], x:x + cr.shape[1]] = cr
        x += cr.shape[1] + 10
    cv2.putText(tile, f'#{k + 1}', (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    tiles.append(tile)
    key.append({'no': k + 1, 'cat': cat, 'video': os.path.basename(v), 'a': a, 'b': b, 'xor_max': c})
# 시트 4장(각 7쌍)
for s in range(0, len(tiles), 7):
    grp = tiles[s:s + 7]
    Wm = max(t.shape[1] for t in grp)
    sheet = np.vstack([np.pad(t, ((0, 0), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in grp])
    cv2.imwrite(os.path.join(out, f'sheet{s // 7 + 1}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
json.dump({'seed': 20261102, 'pairs': key, 'pool_sizes': {k: len(v) for k, v in cands.items()}},
          open(os.path.join(out, 'key.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print({k: len(v) for k, v in cands.items()}, len(pick))
