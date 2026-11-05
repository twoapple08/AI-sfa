"""단계 2(움직임 자료): 새 nian41 영상에서 액션 구간을 자동으로 골라 스틱맨 중간 표현(motion-ir/1)으로 만든다.

개발 사례(60초 클립 1913231262086463573, held_out=false/training_ready=false)는 쓰지 않는다. 수동 보정 없이 공통 자동 처리만:
 1) 컷: 저용량 영상의 이웃 장 HSV 히스토그램 차(바타차리야 > CUT_THR)
 2) 인물 추적: 장마다 RTMW 사람 상자를 앞 장 트랙과 IoU·중심 거리로 이음
 3) 구간 후보: 컷 안에서 트랙이 MIN_COVER 이상 이어지고 몸통·골반·무릎·발목 점수가 충분한(전신) 사람 1–2명, 키가 화면 높이의
    MIN_HEIGHT 이상, 원래 관절 흔들림 MAX_JITTER 이하, 길이 MIN_LEN–MAX_LEN장(긴 컷은 나눔)
 4) 액션 점수: 손목·발목 속도 / 몸통 길이의 평균(움직임 많은 구간 우선), 영상당 최대 PER_VIDEO개, 전체 상위 N개
 5) 변환: rtmw_to_stickman_2d_v2.run_core(키포즈) → stickman_variants.basic_joints, 머리 = run_core head_t/head_base,
    굵기 = 거리 굵기(몸통 배율), 몸 방향 = facing_from_pose(어깨·골반·코) 연속 각도
 6) 품질 수치: 관측 비율, 몸통 점수 중앙값, 흔들림(관절 2차 차분 / 몸통), run_core 잔차
사용: python tools/stage2_extract.py <작업 폴더> [N]   (작업 폴더에 video/·rtmw/ 내려받음, 결과 out/)
원본 영상·포즈 자료·결과 좌표는 비공개(작업 폴더). 저장소에는 도구와 요약 수치만.
"""
import gzip, json, math, os, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIDEOS = {   # post_id: (원본 폭, 높이) — docs/COORDINATION-2026-10-17.md 의 원본 주소 해상도
    '1613887197383622656': (1280, 720), '1613887377965211649': (1280, 720), '1943223713455051062': (1280, 720),
    '2029588466376511962': (1280, 720), '1913589758644908348': (1280, 718), '1534075160545878017': (1280, 520),
    '1534078885696000000': (1280, 520), '1913481070839742689': (872, 480)}
DEV_CLIP = '1913231262086463573'
CUT_THR, MIN_LEN, MAX_LEN, MIN_COVER, PER_VIDEO = 0.35, 24, 120, 0.8, 5
SCORE = 1.5
TORSO = (5, 6, 11, 12)
LEGS = (11, 12, 13, 14, 15, 16)   # 골반·무릎·발목: 전신 조건(첫 시도에서 얼굴 클로즈업·상반신 컷이 뽑혀 엉뚱한 몸이 나오거나 다리가 통째로 없었다)
MIN_HEIGHT, MAX_JITTER = 0.25, 0.15   # 사람 상자 높이 / 화면 높이 중앙값 하한, 원래 관절 흔들림(2차 차분 / 몸통) 중앙값 상한
LIMBS = (9, 10, 15, 16)          # 손목·발목(RTMW 몸 17점)


def fetch(work, vid):
    os.makedirs(f'{work}/video', exist_ok=True); os.makedirs(f'{work}/rtmw', exist_ok=True)
    v, r = f'{work}/video/{vid}.mp4', f'{work}/rtmw/{vid}.jsonl.gz'
    if not os.path.exists(v):
        subprocess.run(['rclone', 'copyto', f'gdrive:AI-sfa/01_원본영상/_Gemini용_저용량/nian41/{vid}.mp4', v], check=True, capture_output=True)
    if not os.path.exists(r):
        subprocess.run(['rclone', 'copyto', f'gdrive:AI-sfa/02_분석자료/포즈_RTMW/nian41/{vid}.jsonl.gz', r], check=True, capture_output=True)
    return v, r


def load_rtmw(path):
    R = {}
    for line in gzip.open(path, 'rt'):
        d = json.loads(line)
        R[int(d['f'])] = [(np.array(p['b'], float), np.array(p['k'], float)[:23]) for p in d['p']]
    return R


def cuts(video):
    import cv2
    cap = cv2.VideoCapture(video); prev, out, i = None, [0], 0
    while True:
        ok, im = cap.read()
        if not ok: break
        h = cv2.calcHist([cv2.cvtColor(cv2.resize(im, (160, 90)), cv2.COLOR_BGR2HSV)], [0, 1], None, [24, 16], [0, 180, 0, 256])
        cv2.normalize(h, h)
        if prev is not None and cv2.compareHist(prev, h, cv2.HISTCMP_BHATTACHARYYA) > CUT_THR:
            out.append(i)
        prev, i = h, i + 1
    out.append(i)
    return out, i


def iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def track(R, s, e):
    """[s, e) 장의 사람 트랙들: [{frame: (box, k)}]."""
    tracks = []
    for f in range(s, e):
        used = set()
        for box, k in sorted(R.get(f, []), key=lambda p: -(p[0][2] - p[0][0]) * (p[0][3] - p[0][1])):
            best, bv = None, 0.25
            for ti, t in enumerate(tracks):
                if ti in used or (f - 1) not in t: continue
                v = iou(box, t[f - 1][0])
                if v > bv: best, bv = ti, v
            if best is None:
                tracks.append({f: (box, k)}); used.add(len(tracks) - 1)
            else:
                tracks[best][f] = (box, k); used.add(best)
    return tracks


def raw_jitter(t, frames):
    X = [t[f][1][:17, :2] / (np.linalg.norm((t[f][1][5, :2] + t[f][1][6, :2]) / 2 - (t[f][1][11, :2] + t[f][1][12, :2]) / 2) or 1)
         for f in frames if f in t]
    if len(X) < 3: return 9.9
    X = np.stack(X)
    return float(np.median(np.linalg.norm(X[2:] - 2 * X[1:-1] + X[:-2], axis=2)))


def action_score(t, frames):
    pts = []
    for f in frames:
        if f in t and t[f][1][list(TORSO), 2].min() >= SCORE: pts.append((f, t[f][1]))
    if len(pts) < 4: return 0.0
    v = []
    for (f0, a), (f1, b) in zip(pts, pts[1:]):
        if f1 != f0 + 1: continue
        tor = np.linalg.norm((a[5, :2] + a[6, :2]) / 2 - (a[11, :2] + a[12, :2]) / 2) or 1
        v.append(np.mean([np.linalg.norm(b[i, :2] - a[i, :2]) for i in LIMBS]) / tor)
    return float(np.median(v)) if v else 0.0   # 중앙값: 튀는 장에 덜 끌림


def candidates(vid, R, cut_list, H=720):
    out = []
    for s, e in zip(cut_list, cut_list[1:]):
        for ws in range(s, e, MAX_LEN):
            we = min(e, ws + MAX_LEN)
            if we - ws < MIN_LEN: continue
            frames = list(range(ws, we))
            T = []
            for t in track(R, ws, we):
                good = [f for f in frames if f in t and t[f][1][list(TORSO) + list(LEGS), 2].min() >= SCORE]
                if len(good) < MIN_COVER * len(frames): continue
                if np.median([t[f][0][3] - t[f][0][1] for f in t]) < MIN_HEIGHT * H: continue
                if raw_jitter(t, frames) > MAX_JITTER: continue
                T.append(t)
            if not T: continue
            T = sorted(T, key=lambda t: -np.median([(t[f][0][2] - t[f][0][0]) * (t[f][0][3] - t[f][0][1]) for f in t]))[:2]
            sc = max(action_score(t, frames) for t in T)
            out.append(dict(video=vid, start=ws, end=we, tracks=T, score=sc))
    return out


def to_pct(p, W, H):
    vis_h = W * 0.5625                      # SFA 16:9 화면(가운데 기준으로 위아래를 자르거나 여백)
    return [float(p[0]) / W * 100, float(p[1] - (H - vis_h) / 2) / vis_h * 100]


def convert(c, W, H):
    from rtmw_to_stickman_2d_v2 import run_core
    from stickman_variants import basic_joints
    from stickman_clip import distance_thickness
    import facing_from_pose as FP
    frames = list(range(c['start'], c['end']))
    N = len(frames)
    actors, quality = [], []
    for slot, t in enumerate(c['tracks']):
        K = np.stack([t[f][1] if f in t else np.zeros((23, 3)) for f in frames])
        Wt = (K[:, :, 2] >= SCORE).astype(float)
        J, S, rep, _, _ = run_core(K, Wt, frames, keys=True)
        S = np.asarray(S, float)
        B = basic_joints(J, S)[0]
        B['head_t'], B['head_b'] = J['head_t'], J['head_base']
        names = ['head_t', 'head_b', 'neck', 'pelvis', 'elb_r', 'wri_r', 'elb_l', 'wri_l', 'kne_r', 'ank_r', 'kne_l', 'ank_l']
        joints = {k: [to_pct(B[k][i], W, H) if np.all(np.isfinite(B[k][i])) else None for i in range(N)] for k in names}
        th, _ = distance_thickness(S * 1152.0 / W, ((73.3, 1.0), (376.4, 5.0)))
        raw = [FP.yaw_of(t[f][1].tolist()) if f in t else None for f in frames]
        X = np.stack([np.asarray(B[k], float) for k in names], 1)
        jit = np.nanmedian(np.linalg.norm(X[2:] - 2 * X[1:-1] + X[:-2], axis=2) / S[1:-1, None]) if N > 2 else 0.0
        quality.append(dict(slot=slot, observed=float(np.mean([f in t and t[f][1][list(TORSO), 2].min() >= SCORE for f in frames])),
                            torso_score_median=float(np.median([t[f][1][list(TORSO), 2].min() for f in frames if f in t])),
                            jitter_torso_median=round(float(jit), 4),
                            rms_resid_torso_median=float(np.median([v for v in rep['rms_resid_torso'] if v is not None])) if rep.get('rms_resid_torso') else None,
                            knee_fixed=len(rep.get('knee_fixed', []))))
        actors.append(dict(slot=slot, color=('blue', 'red')[slot], joints=joints,
                           thickness=[{str(o): round(float(th[i]), 3) for o in range(1, 12)} for i in range(N)],
                           hidden=[[] for _ in range(N)], smear=[[] for _ in range(N)], head_fill=[True] * N,
                           facing=FP.smooth_yaw(raw)))
    ir = dict(schema='motion-ir/1', fps=[24, 24], aspect=0.5625, frames=N, actors=actors,
              camera=[[0.0, 0.0, 1.0] for _ in range(N)], timeline=[],
              source=dict(animator='nian41', video=c['video'], start=c['start'], end=c['end'], auto=True,
                          held_out=False, training_ready=False, note='공통 자동 처리만, 사용자 판정 전'))
    return ir, quality


def main():
    work = sys.argv[1]; NSEL = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    os.makedirs(f'{work}/out', exist_ok=True)
    allc = []
    for vid in VIDEOS:
        assert vid != DEV_CLIP
        v, r = fetch(work, vid)
        R = load_rtmw(r)
        cl, n = cuts(v)
        cs = sorted(candidates(vid, R, cl, VIDEOS[vid][1]), key=lambda c: -c['score'])[:PER_VIDEO]
        print(vid, '장', n, '컷', len(cl) - 1, '후보', len(cs), [round(c['score'], 3) for c in cs], flush=True)
        allc += cs
    sel = sorted(allc, key=lambda c: -c['score'])[:NSEL]
    import motion_ir as M
    summary = []
    for i, c in enumerate(sorted(sel, key=lambda c: (c['video'], c['start']))):
        W, H = VIDEOS[c['video']]
        ir, q = convert(c, W, H)
        name = f'n41_{i + 1:02d}_{c["video"][-6:]}_{c["start"]}-{c["end"] - 1}'
        json.dump(ir, open(f'{work}/out/{name}.json', 'w'))
        M.save_sfa(M.compile_ir(ir, name=name), f'{work}/out/{name}.sfa', name)
        summary.append(dict(name=name, video=c['video'], start=c['start'], end=c['end'] - 1, frames=c['end'] - c['start'],
                            actors=len(ir['actors']), action_score=round(c['score'], 4), quality=q))
        print(name, len(ir['actors']), round(c['score'], 3), [(x['observed'], x['jitter_torso_median']) for x in q], flush=True)
    json.dump(summary, open(f'{work}/out/summary.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
