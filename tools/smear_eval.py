"""스미어 후보 탐지기를 같은 정답/비정답 라벨로 비교 평가한다.

입력 라벨은 비공개 `smear-eval-labels/1`(장·인물색·부위·점·확신도 S/L/U),
탐지 결과는 `smear-candidate-scan/1` 형식(rows[].candidates[].actor/box/score)이다.
U(불확실) 라벨에 닿은 탐지는 정답도 오탐도 아닌 '보류'로 뺀다.
오탐은 RTMW 관절(선택)로 머리/손/발/기타로 나눠 어떤 일반 부위와 헷갈렸는지 센다.
점수는 확률이 아니며, 이 평가는 한 영상·한 라벨러 기준이라 일반화 정확도가 아니다.
"""
import argparse, gzip, json
from pathlib import Path
import numpy as np

HEAD = list(range(0, 5)) + list(range(23, 91))
HAND = [9, 10] + list(range(91, 133))
FOOT = [15, 16] + list(range(17, 23))


def load_rtmw(path, y_offset=63):
    """RTMW jsonl.gz → {장: [133×3 관절, ...]} (y는 자른 화면 기준으로 옮김)."""
    out = {}
    if not path:
        return out
    for line in gzip.open(path, 'rt'):
        d = json.loads(line)
        ks = []
        for p in d['p']:
            k = np.array(p['k'], float)
            k[:, 1] -= y_offset
            ks.append(k)
        out[int(d['f'])] = ks
    return out


def hit(label, cand, margin):
    """같은 인물색이고, 라벨 점이 후보 상자(+여유) 안이거나 라벨 영역 상자와 후보 상자가 겹치면 적중."""
    if cand['actor'] != label['actor']:
        return False
    x0, y0, x1, y1 = cand['box']
    if x0 - margin <= label['x'] <= x1 + margin and y0 - margin <= label['y'] <= y1 + margin:
        return True
    if 'box' not in label:
        return False
    a0, b0, a1, b1 = label['box']
    iw, ih = min(x1, a1) - max(x0, a0), min(y1, b1) - max(y0, b0)
    if iw <= 0 or ih <= 0:
        return False
    inter = iw * ih
    small = min((x1 - x0) * (y1 - y0), (a1 - a0) * (b1 - b0))
    return inter >= 0.3 * max(1, small)


def confuser_kind(cand, kps, min_score=2.0):
    """오탐 상자 중심과 가장 가까운 관절 무리. 관절 없으면 unknown."""
    x0, y0, x1, y1 = cand['box']
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    best, kind = 1e9, 'unknown'
    for k in kps:
        for name, idx in (('head_hair', HEAD), ('hand', HAND), ('foot_shoe', FOOT)):
            pts = k[idx]
            pts = pts[pts[:, 2] >= min_score][:, :2]
            if len(pts):
                d = float(np.min(np.linalg.norm(pts - c, axis=1)))
                if d < best:
                    best, kind = d, name
    reach = max(60.0, 0.5 * max(x1 - x0, y1 - y0))
    return kind if best <= reach else ('body_cloth_other' if kind != 'unknown' else 'unknown')


def evaluate(labels, scan, rtmw=None, margin=40, top=(20, 40, 100)):
    rtmw = rtmw or {}
    pos = [l for l in labels if l['conf'] in ('S', 'L')]
    unsure = [l for l in labels if l['conf'] == 'U']
    by_frame = {}
    for l in labels:
        by_frame.setdefault(l['frame'], []).append(l)
    dets = []
    for row in scan['rows']:
        f = row['source_index']
        for c in row['candidates']:
            dets.append((float(c['score']), f, c))
    dets.sort(key=lambda t: -t[0])
    found = set()
    ranked = []
    kinds = {}
    for score, f, c in dets:
        ls = by_frame.get(f, [])
        p = [i for i, l in enumerate(pos) if l['frame'] == f and hit(l, c, margin)]
        if p:
            ranked.append(1)
            found.update(p)
        elif any(hit(l, c, margin) for l in ls if l['conf'] == 'U'):
            ranked.append(None)
        else:
            ranked.append(0)
            k = confuser_kind(c, rtmw.get(f, []))
            kinds[k] = kinds.get(k, 0) + 1
    # 순위 평균 정밀도(새로 찾은 정답만 이득으로 침)
    seen, tp_cum, ap, judged = set(), 0, 0.0, 0
    first_hit = []
    for (score, f, c), r in zip(dets, ranked):
        if r is None:
            continue
        judged += 1
        if r == 1:
            new = [i for i, l in enumerate(pos) if l['frame'] == f and hit(l, c, margin) and i not in seen]
            if new:
                seen.update(new)
                tp_cum += len(new)
                ap += len(new) * (sum(1 for x in ranked[:judged] if x == 1) / judged)
    ap = ap / len(pos) if pos else 0.0
    judged_list = [r for r in ranked if r is not None]
    res = dict(positives=len(pos), positives_sure=sum(l['conf'] == 'S' for l in pos), uncertain=len(unsure),
               detections=len(dets), detections_hit_positive=judged_list.count(1),
               detections_false=judged_list.count(0), detections_on_uncertain=ranked.count(None),
               recall_all=round(len(found) / len(pos), 4) if pos else None,
               recall_sure=round(sum(1 for i in found if pos[i]['conf'] == 'S') / max(1, sum(l['conf'] == 'S' for l in pos)), 4),
               average_precision=round(ap, 4), false_positive_kinds=dict(sorted(kinds.items())))
    for n in top:
        js = judged_list[:n]
        res[f'top{n}_hits'] = js.count(1)
    res['missed'] = [dict(frame=l['frame'], actor=l['actor'], part=l['part'], conf=l['conf'])
                     for i, l in enumerate(pos) if i not in found]
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--labels', type=Path, required=True)
    ap.add_argument('--scan', type=Path, required=True, nargs='+')
    ap.add_argument('--rtmw', type=Path)
    ap.add_argument('--margin', type=int, default=40)
    ap.add_argument('--show-missed', action='store_true')
    a = ap.parse_args()
    labels = json.loads(a.labels.read_text())['labels']
    rtmw = load_rtmw(a.rtmw) if a.rtmw else {}
    for s in a.scan:
        r = evaluate(labels, json.loads(s.read_text()), rtmw, a.margin)
        if not a.show_missed:
            r['missed'] = len(r['missed'])
        print(s.parent.name, json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
