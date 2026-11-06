"""스타일 층 자료 늘리기 1단계(11-06 사용자 '추천대로' — 자료 늘리기): nian41·나카무라 영상에서 걷기·달리기처럼 '이동'하는 구간 후보 찾기.
(배경: 스타일 층 학습 글에 걷기 0회·달리기 9회 → 모델이 걷기 주기를 못 만듦.)

stage2_extract.candidates(같은 컷 나누기·인물 추적·몸통 점수 조건)로 구간을 만든 뒤, 주 인물마다
- 다리 보임: 두 발목 점수 ≥ 2.5 비율(LEG_SEEN 이상)
- 걸음 번갈이: (왼발목 x − 오른발목 x)/몸통 의 부호가 바뀌는 횟수(진폭 STEP_AMP 몸통 이상인 것만) → 초당 걸음 수
- 이동: 골반 x 이동 총량 / 몸통(카메라가 따라가면 작을 수 있어 참고만)
걸음 수 ≥ MIN_STEPS인 구간을 점수 순으로. 이미 고른 구간(stage2 선택)·제외 목록·개발 영상은 뺀다.
사용: python tools/find_locomotion.py <stage2 작업 폴더> [--top 40] [--json 출력]
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage2_extract as X  # noqa: E402

LEG_SEEN, STEP_AMP, MIN_STEPS = 0.6, 0.25, 2


def gait(t, frames):
    K = [t[f][1] for f in frames if f in t]
    if len(K) < 8: return None
    K = np.stack(K)
    tor = np.linalg.norm((K[:, 5, :2] + K[:, 6, :2]) / 2 - (K[:, 11, :2] + K[:, 12, :2]) / 2, axis=1) + 1e-6
    seen = float(np.mean((K[:, 15, 2] >= 2.5) & (K[:, 16, 2] >= 2.5)))
    d = (K[:, 15, 0] - K[:, 16, 0]) / tor
    steps, sign = 0, 0
    for x in d:
        if abs(x) < STEP_AMP: continue
        s = 1 if x > 0 else -1
        if sign and s != sign: steps += 1
        sign = s
    pel = (K[:, 11, 0] + K[:, 12, 0]) / 2
    travel = float(np.sum(np.abs(np.diff(pel))) / np.median(tor))
    return dict(leg_seen=round(seen, 2), steps=steps, steps_per_s=round(steps / (len(K) / 24), 2), travel=round(travel, 1),
                torso_px=round(float(np.median(tor)), 1))


def main(work, top=40, outp=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    have = {(s['video'], s['start']) for s in json.load(open(f'{work}/out/summary.json'))['segments']}
    excl = set()
    for p in __import__('glob').glob(f'{root}/data/stage2/exclude_*.json'):
        for e in json.load(open(p, encoding='utf-8'))['segments']: excl.add((e['video'], int(e['start'])))
    vids = dict(X.VIDEOS); vids.update({v: wh for v, wh in X.videos_of(work, 'yutaka_nakamura').items()})
    out, kept = [], []
    for vid, (W, H) in vids.items():
        if vid == X.DEV_CLIP: continue
        r = f'{work}/rtmw/{vid}.jsonl.gz'; v = f'{work}/video/{vid}.mp4'
        if not os.path.exists(r) or not os.path.exists(f'{work}/cuts/{vid}.json'): continue
        R = X.load_rtmw(r); cl, n = X.cached_cuts(work, vid, v)
        for c in X.candidates(vid, R, cl, H, W):
            if (c['video'], c['start']) in excl: continue
            if (c['video'], c['start']) in have:
                kept.append(X.pose_seq(c)); continue
            fr = list(range(c['start'], c['end']))
            g = gait(c['tracks'][0], fr)
            if not g or g['leg_seen'] < LEG_SEEN or g['steps'] < MIN_STEPS: continue
            out.append(dict(video=vid, start=c['start'], end=c['end'] - 1, frames=c['end'] - c['start'],
                            animator='yutaka_nakamura' if vid not in X.VIDEOS else 'nian41', action=round(c['score'], 3), _ps=X.pose_seq(c), **g))
    out.sort(key=lambda x: (-x['steps_per_s'] * min(1.0, x['leg_seen']), -x['frames']))
    # 중복 빼기(X·사쿠가 같은 장면 다른 판, 11-05 POSE_DUP): 이미 고른 구간·앞선 후보와 정규화 자세 열이 가까우면 뺀다
    uniq = []
    for x in out:
        if any(X.pose_dist(x['_ps'], k) < X.POSE_DUP for k in kept + [u['_ps'] for u in uniq]): continue
        uniq.append(x)
    print('중복 빼기 전', len(out), '후', len(uniq))
    out = [{k: v for k, v in x.items() if k != '_ps'} for x in uniq]
    print('후보', len(out))
    for x in out[:top]: print(x)
    if outp: json.dump(out, open(outp, 'w'), ensure_ascii=False, indent=1)
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], int(a[a.index('--top') + 1]) if '--top' in a else 40, a[a.index('--json') + 1] if '--json' in a else None)
