"""스틱맨 중간 표현(motion-ir/1)에서 잴 수 있는 스타일 특징(재계획 조건 29 ③, 단계 2 '스타일 특징 측정').

화면 픽셀이 아니라 관절과 원본 그림 구간(actor['drawings'], stage2_extract가 run_core 키포즈 구간을 저장)으로 잰다.
픽셀 방식(sakuga_timing·rhythm_check)은 카메라 이동·이펙트 깜빡임에서 같은 그림을 새 그림으로 잡는 한계가 기록돼 있다.

특징(몸통 길이 = 목–골반 거리, 장 = 1/24초):
- 유지 리듬: 그림 하나가 몇 장 보이는지(1s·2s·3s·4+) 분포. 구간 양 끝 그림은 잘렸을 수 있어 뺀다.
- 키 속도: 이웃 그림(키) 사이 손목·발목의 골반 기준 이동 / 몸통 / 장 수. 키 위치 = 그림 구간 가운데 장의 관절.
- 타격 멈춤: 키 속도가 이 인물 상위 PEAK_Q 분위 이상인 '빠른 키 전환' 바로 뒤 그림의 유지 장 수.
  뒤 그림이 앞 그림들의 유지 장 중앙값보다 길면 '멈춤 있음'으로 센다.
- 예비 동작: 빠른 키 전환의 주 끝점(가장 많이 움직인 손목·발목)이 전환 직전 ANTIC_WIN장 안에서
  전환 방향과 반대(코사인 < -0.3)로 몸통 ANTIC_MIN 이상 움직였으면 '예비 동작 있음', 그 장 수.
- 속도 곡선: 연속으로 움직이는 키 묶음(획)마다 가장 빠른 전환의 상대 위치(0 = 시작에서 바로 빠름, 1 = 끝에서 빠름) 분포.
- 카메라 흔들림: motion-ir의 camera가 아직 고정값(자동 추출은 카메라를 따로 풀지 않음)이라 '미측정'으로 둔다.
사용: python tools/motion_style.py <ir.json …> [--json 출력]
측정은 자동 추출 자료의 경향을 보는 보조 지표다. 원본 그림 구간은 포즈 변화 문턱으로 나눈 추정이며 정답이 아니다.
"""
import json, sys
import numpy as np

ENDS = ('wri_r', 'wri_l', 'ank_r', 'ank_l')
PEAK_Q, ANTIC_WIN, ANTIC_MIN, MOVE_MIN = 75, 6, 0.08, 0.02


def _arr(js):
    return np.array([[np.nan, np.nan] if p is None else p for p in js], float)


def actor_features(a, aspect=0.5625):
    J = {k: _arr(v) for k, v in a['joints'].items()}
    for k in J:
        J[k][:, 1] *= aspect                      # 화면 % → 가로세로 같은 단위
    tor = np.linalg.norm(J['neck'] - J['pelvis'], axis=1)
    rel = {k: J[k] - J['pelvis'] for k in ENDS}
    D = [tuple(d) for d in a.get('drawings') or []]
    out = dict(drawings=len(D))
    inner = D[1:-1]
    hold = [e - s + 1 for s, e in inner]
    out['hold'] = {str(k): sum(1 for h in hold if h == k) for k in (1, 2, 3)}
    out['hold']['4+'] = sum(1 for h in hold if h >= 4)
    if len(D) < 3:
        return out
    mid = [(s + e) // 2 for s, e in D]
    T = np.nanmedian(tor[[m for m in mid if np.isfinite(tor[m])]]) if any(np.isfinite(tor[m]) for m in mid) else np.nan
    if not np.isfinite(T) or T <= 0:
        return out
    trans = []   # (i: D[i]→D[i+1], 속도, 주 끝점, 이동 벡터)
    for i in range(len(D) - 1):
        gap = mid[i + 1] - mid[i]
        disp = {k: rel[k][mid[i + 1]] - rel[k][mid[i]] for k in ENDS}
        mag = {k: float(np.linalg.norm(v)) / T for k, v in disp.items() if np.all(np.isfinite(v))}
        if not mag or gap <= 0:
            trans.append(None); continue
        k = max(mag, key=mag.get)
        trans.append((i, float(np.mean(list(mag.values()))) / gap, k, disp[k] / T))
    sp = [t[1] for t in trans if t]
    if not sp:
        return out
    out['key_speed_median'] = round(float(np.median(sp)), 4)
    thr = float(np.percentile(sp, PEAK_Q))
    peaks = [t for t in trans if t and t[1] >= thr and t[1] > MOVE_MIN]
    stops, antic = [], []
    for i, v, k, vec in peaks:
        if i + 1 < len(D) - 1:                   # 뒤 그림이 마지막(잘렸을 수 있는) 그림이 아닐 때만
            after = D[i + 1][1] - D[i + 1][0] + 1
            before = [D[j][1] - D[j][0] + 1 for j in range(max(1, i - 3), i + 1)]
            stops.append(dict(after=after, before_median=float(np.median(before)) if before else None,
                              stop=bool(before and after > np.median(before))))
        s0 = max(0, D[i][1] - ANTIC_WIN)
        seg = rel[k][s0:D[i][1] + 1]
        seg = seg[np.all(np.isfinite(seg), axis=1)]
        if len(seg) >= 2 and np.linalg.norm(vec) > 0:
            back = (seg[-1] - seg[0]) / T
            cos = float(back @ vec / (np.linalg.norm(back) * np.linalg.norm(vec) + 1e-9))
            hit = bool(cos < -0.3 and np.linalg.norm(back) >= ANTIC_MIN)
            antic.append(dict(frames=int(D[i][1] - s0), cos=round(cos, 3), hit=hit))
    out['fast_transitions'] = len(peaks)
    out['stop_after_fast'] = dict(n=len(stops), with_stop=sum(s['stop'] for s in stops),
                                  after_hold=sorted(s['after'] for s in stops))
    out['anticipation'] = dict(n=len(antic), with_antic=sum(a_['hit'] for a_ in antic))
    strokes, cur = [], []
    for t in trans:
        if t and t[1] > MOVE_MIN: cur.append(t[1])
        else:
            if len(cur) >= 3: strokes.append(cur)
            cur = []
    if len(cur) >= 3: strokes.append(cur)
    out['stroke_peak_pos'] = [round(int(np.argmax(c)) / (len(c) - 1), 3) for c in strokes]
    return out


def measure(ir):
    return dict(frames=ir['frames'], camera_shake='미측정(camera 고정값)',
                actors=[dict(slot=a.get('slot'), **actor_features(a, ir.get('aspect', 0.5625))) for a in ir['actors']])


def aggregate(results):
    hold = {'1': 0, '2': 0, '3': 0, '4+': 0}
    stop_n = stop_w = an_n = an_w = 0
    pos, after = [], []
    for r in results:
        for a in r['actors']:
            for k in hold: hold[k] += a.get('hold', {}).get(k, 0)
            s = a.get('stop_after_fast'); an = a.get('anticipation')
            if s: stop_n += s['n']; stop_w += s['with_stop']; after += s['after_hold']
            if an: an_n += an['n']; an_w += an['with_antic']
            pos += a.get('stroke_peak_pos', [])
    tot = sum(hold.values()) or 1
    return dict(hold_counts=hold, hold_share={k: round(v / tot, 3) for k, v in hold.items()},
                stop_after_fast=dict(n=stop_n, with_stop=stop_w, after_hold_median=float(np.median(after)) if after else None),
                anticipation=dict(n=an_n, with_antic=an_w),
                stroke_peak_pos=dict(n=len(pos), quartiles=[round(float(x), 3) for x in np.percentile(pos, [25, 50, 75])] if pos else None))


if __name__ == '__main__':
    args = sys.argv[1:]
    outp = args[args.index('--json') + 1] if '--json' in args else None
    files = [a for a in args if a.endswith('.json') and a != outp]
    res = [dict(file=f, **measure(json.load(open(f)))) for f in files]
    agg = aggregate(res)
    print(json.dumps(agg, ensure_ascii=False))
    if outp:
        json.dump(dict(aggregate=agg, per_file=res), open(outp, 'w'), ensure_ascii=False, indent=1)
