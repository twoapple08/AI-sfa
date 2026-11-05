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

VIDEOS = {   # post_id: (원본 폭, 높이) — X 영상은 docs/COORDINATION-2026-10-17.md 원본 주소, Sakugabooru는 data/sakuga/posts_nian41.jsonl
    # 세로 영상 2개(1569962812805644289 444×722, 1937399147772137658 666×1082)는 16:9 화면에 다 들어가지 않아 뺐다
    '1534075160545878017': (1280, 520), '1534078885696000000': (1280, 520), '1567691748968906752': (444, 248), '1613887197383622656': (1280, 720),
    '1613887377965211649': (1280, 720), '1913481070839742689': (872, 480), '1913589758644908348': (1280, 718), '1943223713455051062': (1280, 720),
    '2029588466376511962': (1280, 720), '216073': (852, 480), '216075': (852, 480), '216076': (852, 480),
    '216077': (852, 480), '216079': (852, 480), '216081': (852, 480), '216084': (852, 480),
    '216085': (852, 480), '216089': (852, 480), '280521': (854, 480), '280523': (854, 480),
    '280525': (854, 480), '280526': (854, 480), '280527': (854, 480), '280528': (854, 480),
    '280530': (854, 480), '280534': (854, 480), '280535': (854, 480), '280536': (854, 480),
    '280544': (848, 480), '280556': (854, 480), '280597': (872, 480), '280598': (872, 480),
    '280830': (854, 480), '280831': (854, 480), '280832': (854, 480), '280833': (854, 480),
    '280834': (854, 480), '280835': (854, 480), '287139': (854, 480), '287140': (854, 480),
    '287263': (854, 480), '287264': (854, 480), '287268': (854, 480), '301142': (854, 480),
    '301158': (854, 480),
}
DEV_CLIP = '1913231262086463573'
PREFIX = {'nian41': 'n41', 'yutaka_nakamura': 'nkm'}
LOW_PRIORITY = {'302394'}   # 나카무라 비질란테: 기본 중요도 낮음(AGENTS.md) — 채우기에서 뺀다
MIN_ACT = 0.05             # 액션 점수 하한: 서 있기만 하는 구간 제외(11-05 4차 시트 12·14·20, 0.007–0.02)


def videos_of(work, animator):
    """애니메이터별 (영상 → 원본 해상도). nian41은 VIDEOS, 그 밖은 data/sakuga/posts_<animator>.jsonl ∩ Drive RTMW 목록(가로 영상만)."""
    if animator == 'nian41':
        return VIDEOS
    lst = f'{work}/rtmw_{animator}.txt'
    if not os.path.exists(lst):
        out = subprocess.run(['rclone', 'lsf', f'gdrive:AI-sfa/02_분석자료/포즈_RTMW/{animator}/'], check=True, capture_output=True, text=True).stdout
        open(lst, 'w').write(out)
    ids = {x.replace('.jsonl.gz', '') for x in open(lst).read().split()}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = {}
    for l in open(f'{root}/data/sakuga/posts_{animator}.jsonl', encoding='utf-8'):
        r = json.loads(l); i = str(r['id'])
        if i in ids and i not in LOW_PRIORITY and r['width'] > r['height']:
            res[i] = (int(r['width']), int(r['height']))
    return dict(sorted(res.items()))


def cached_cuts(work, vid, v):
    p = f'{work}/cuts/{vid}.json'
    if os.path.exists(p):
        return tuple(json.load(open(p)))
    os.makedirs(f'{work}/cuts', exist_ok=True)
    cl, n = cuts(v)
    json.dump([list(map(int, cl)), int(n)], open(p, 'w'))
    return cl, n
CUT_THR, MIN_LEN, MAX_LEN, MIN_COVER, PER_VIDEO = 0.35, 24, 120, 0.8, 6
SCORE = 1.5
TORSO = (5, 6, 11, 12)
LEGS = (11, 12, 13, 14, 15, 16)   # 골반·무릎·발목: 전신 조건(첫 시도에서 얼굴 클로즈업·상반신 컷이 뽑혀 엉뚱한 몸이 나오거나 다리가 통째로 없었다)
MIN_HEIGHT, MAX_JITTER = 0.25, 2.0   # 사람 상자 높이 / 화면 높이 중앙값 하한, 원래 관절 흔들림(2차 차분 / 몸통) 중앙값 상한 — 0.15는 빠른 동작까지 잘라 6구간뿐(11-05: 전신 57트랙 흔들림 중앙 0.71), 2.0 넘는 4–6은 사람 바뀜·추적 실패
LEG_MED = 3.0                     # 무릎·발목 점수 중앙값 하한: 가까운 상반신 컷은 다리를 지어내도 2.3 안팎(11-05 3차 시트 08·24·30), 전신은 3.2 이상
IN_LEG = 0.6                      # 골반→발목 / 몸통 하한(웅크림 허용, 지어낸 짧은 다리 제외)
LIMBS = (9, 10, 15, 16)          # 손목·발목(RTMW 몸 17점)


def fetch(work, vid, animator='nian41'):
    os.makedirs(f'{work}/video', exist_ok=True); os.makedirs(f'{work}/rtmw', exist_ok=True)
    v, r = f'{work}/video/{vid}.mp4', f'{work}/rtmw/{vid}.jsonl.gz'
    if not os.path.exists(v):
        subprocess.run(['rclone', 'copyto', f'gdrive:AI-sfa/01_원본영상/_Gemini용_저용량/{animator}/{vid}.mp4', v], check=True, capture_output=True)
    if not os.path.exists(r):
        subprocess.run(['rclone', 'copyto', f'gdrive:AI-sfa/02_분석자료/포즈_RTMW/{animator}/{vid}.jsonl.gz', r], check=True, capture_output=True)
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


def leg_in_frame(t, f, W, H):
    """발목이 화면 안에 있고 골반→발목 길이가 몸통의 IN_LEG배 이상(가까운 상반신 컷에서 RTMW가 화면 밖 다리를 높은 점수로 지어낸다, 11-05 2차 시트 20·24·28–30)."""
    k = t[f][1]
    tor = np.linalg.norm((k[5, :2] + k[6, :2]) / 2 - (k[11, :2] + k[12, :2]) / 2) or 1
    for hip, ank in ((11, 15), (12, 16)):
        x, y = k[ank, :2]
        if not (0 <= x < W and 0 <= y < H * 0.99): return False
        if np.linalg.norm(k[ank, :2] - k[hip, :2]) < IN_LEG * tor: return False
    return True


def candidates(vid, R, cut_list, H=720, W=1280):
    out = []
    for s, e in zip(cut_list, cut_list[1:]):
        for ws in range(s, e, MAX_LEN):
            we = min(e, ws + MAX_LEN)
            if we - ws < MIN_LEN: continue
            frames = list(range(ws, we))
            T = []
            for t in track(R, ws, we):
                good = [f for f in frames if f in t and t[f][1][list(TORSO) + list(LEGS), 2].min() >= SCORE and leg_in_frame(t, f, W, H)]
                if len(good) < MIN_COVER * len(frames): continue
                if np.median([t[f][1][13:17, 2] for f in t]) < LEG_MED: continue
                if np.median([t[f][0][3] - t[f][0][1] for f in t]) < MIN_HEIGHT * H: continue
                if raw_jitter(t, frames) > MAX_JITTER: continue
                T.append((t, good))
            if not T: continue
            T = sorted(T, key=lambda tg: -np.median([(tg[0][f][0][2] - tg[0][f][0][0]) * (tg[0][f][0][3] - tg[0][f][0][1]) for f in tg[0]]))[:2]
            # 구간을 주 인물이 잘 보이는 첫 장–끝 장으로 자른다(11-05: 트랙이 늦게 시작하면 앞 장 몸통 배율이 0 → 팔다리 전체가 NaN)
            a, b = T[0][1][0], T[0][1][-1] + 1
            if b - a < MIN_LEN: continue
            fr = list(range(a, b))
            T = [t for t, g in T if t is T[0][0] or sum(f in t for f in fr) == len(fr)]
            sc = max(action_score(t, fr) for t in T)
            out.append(dict(video=vid, start=a, end=b, tracks=T, score=sc))
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
                           facing=FP.smooth_yaw(raw),
                           # 원본 그림 구간(이 구간 0장 기준 [첫 장, 끝 장]): 관절은 PCHIP으로 24장 모두 움직이지만, 유지 리듬(2s·3s)·타격 멈춤은
                           # 이 경계에 남는다(11-05: 보간 때문에 스타일 측정 자료에서 유지 리듬이 지워지던 것 보존). 트랙이 없는 장은 키 구간 밖.
                           drawings=[[int(a_ - frames[0]), int(b_ - frames[0])] for a_, b_ in (rep.get('keypose_segments') or [])]))
    ir = dict(schema='motion-ir/1', fps=[24, 24], aspect=0.5625, frames=N, actors=actors,
              camera=[[0.0, 0.0, 1.0] for _ in range(N)], timeline=[],
              source=dict(animator=c.get('animator', 'nian41'), video=c['video'], start=c['start'], end=c['end'], auto=True,
                          held_out=False, training_ready=False, note='공통 자동 처리만, 사용자 판정 전'))
    return ir, quality


DUP_THR = 12.0   # 썸네일(64×36 회색) 평균 절대차 — X 영상과 Sakugabooru 클립은 같은 장면을 잘라 올린 것이 많다(10-17 프레임 대조)


def thumbs(video, frames):
    import cv2
    cap = cv2.VideoCapture(video); out = []
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f); ok, im = cap.read()
        out.append(cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32) if ok else None)
    return out


def seg_thumbs(work, c):
    fr = [c['start'] + int(q * (c['end'] - 1 - c['start'])) for q in (0.2, 0.5, 0.8)]
    return thumbs(f'{work}/video/{c["video"]}.mp4', fr)


def same_scene(A, B):
    """두 구간의 표본 장 중 하나라도 거의 같은 그림이면 같은 장면."""
    return any(a is not None and b is not None and float(np.abs(a - b).mean()) < DUP_THR for a in A for b in B)


POSE_DUP = 0.2   # 정규화 포즈 열(골반 원점·몸통 배율) 최소 정렬 차이 — 같은 그림의 다른 색·자르기 판(X↔사쿠가, 사쿠가끼리)이
                 # 0.05–0.18, 다른 장면은 0.30 이상(11-05 3차 30구간). 화면 썸네일 비교는 레터박스·색 보정 차이로 놓쳤다


def pose_seq(c):
    t = c['tracks'][0]
    K = np.stack([t[f][1][:17, :2] for f in range(c['start'], c['end']) if f in t])
    pel = (K[:, 11] + K[:, 12]) / 2
    tor = np.linalg.norm((K[:, 5] + K[:, 6]) / 2 - pel, axis=1)[:, None, None] + 1e-6
    return (K - pel[:, None]) / tor


def pose_dist(A, B, minov=12):
    best = 9.0
    for off in range(-len(B) + minov, len(A) - minov + 1):
        i0, i1 = max(0, off), min(len(A), off + len(B))
        if i1 - i0 < minov: continue
        best = min(best, float(np.median(np.linalg.norm(A[i0:i1] - B[i0 - off:i1 - off], axis=2))))
    return best


def dev_thumbs(work):
    """개발 사례 영상 전체(4장 간격) 썸네일: 다른 출처에 같은 장면이 있으면 개발 사례로 보고 뺀다."""
    v = f'{work}/video/{DEV_CLIP}.mp4'
    if not os.path.exists(v):
        subprocess.run(['rclone', 'copyto', f'gdrive:AI-sfa/01_원본영상/_Gemini용_저용량/nian41/{DEV_CLIP}.mp4', v], check=True, capture_output=True)
    import cv2
    n = int(cv2.VideoCapture(v).get(cv2.CAP_PROP_FRAME_COUNT))
    return [t for t in thumbs(v, range(0, n, 4)) if t is not None]


def main():
    """사용: stage2_extract.py <작업 폴더> [N] [--fill 애니메이터 ...]
    nian41에서 먼저 고르고, N에 못 미치면 --fill 애니메이터(예: yutaka_nakamura, 사용자 11-05 "부족하면 나카무라쪽도") 후보로 채운다."""
    args = sys.argv[1:]
    fill = args[args.index('--fill') + 1:] if '--fill' in args else []
    pos = args[:args.index('--fill')] if '--fill' in args else args
    work = pos[0]; NSEL = int(pos[1]) if len(pos) > 1 else 30
    os.makedirs(f'{work}/out', exist_ok=True)
    dev = dev_thumbs(work)
    sel, dropped, RES = [], [], {}
    for animator in ['nian41'] + fill:
        vids = videos_of(work, animator)
        allc = []
        for vid in vids:
            assert vid != DEV_CLIP
            RES[vid] = vids[vid]
            try:
                v, r = fetch(work, vid, animator)
            except subprocess.CalledProcessError:
                print(vid, '내려받기 실패(저용량 영상 없음)', flush=True); continue
            R = load_rtmw(r)
            cl, n = cached_cuts(work, vid, v)
            cs = sorted([c for c in candidates(vid, R, cl, vids[vid][1], vids[vid][0]) if c['score'] >= MIN_ACT],
                        key=lambda c: -c['score'])[:PER_VIDEO]
            for c in cs: c['animator'] = animator
            print(animator, vid, '장', n, '컷', len(cl) - 1, '후보', len(cs), [round(c['score'], 3) for c in cs], flush=True)
            allc += cs
        for c in sorted(allc, key=lambda c: (-c['score'], -RES[c['video']][0])):   # 같은 점수면 해상도 높은 쪽 먼저
            if len(sel) == NSEL: break
            th = seg_thumbs(work, c)
            if same_scene(th, dev):
                dropped.append((c['video'], c['start'], '개발 사례와 같은 장면')); continue
            ps = pose_seq(c)
            hit = next((k for k in sel if same_scene(th, k['th']) or pose_dist(ps, k['ps']) < POSE_DUP), None)
            if hit:
                dropped.append((c['video'], c['start'], f'중복 {hit["video"]}:{hit["start"]}')); continue
            c['th'], c['ps'] = th, ps; sel.append(c)
        print(animator, '까지 고름', len(sel), flush=True)
        if len(sel) >= NSEL: break
    print('뺀 후보', len(dropped), dropped, flush=True)
    import motion_ir as M
    summary = []
    for i, c in enumerate(sorted(sel, key=lambda c: (list(PREFIX).index(c['animator']), c['video'], c['start']))):
        W, H = RES[c['video']]
        ir, q = convert(c, W, H)
        name = f'{PREFIX[c["animator"]]}_{i + 1:02d}_{c["video"][-6:]}_{c["start"]}-{c["end"] - 1}'
        json.dump(ir, open(f'{work}/out/{name}.json', 'w'))
        M.save_sfa(M.compile_ir(ir, name=name), f'{work}/out/{name}.sfa', name)
        summary.append(dict(name=name, animator=c['animator'], video=c['video'], start=c['start'], end=c['end'] - 1,
                            frames=c['end'] - c['start'], actors=len(ir['actors']), action_score=round(c['score'], 4), quality=q))
        print(name, len(ir['actors']), round(c['score'], 3), [(x['observed'], x['jitter_torso_median']) for x in q], flush=True)
    json.dump(dict(segments=summary, dropped=dropped), open(f'{work}/out/summary.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
