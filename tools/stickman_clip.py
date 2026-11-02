"""여러 인물·여러 컷 구간 → 기본 스틱맨(직선 몸통) SFA 하나(2026-11-03, 사용자: "빨간 인물까지 포함시켜 10초 정도").

- 컷마다 따로 푼다(키포즈 보간이 컷을 넘지 않게). 컷 번호는 사용자가 확인한 값으로 준다(--cuts).
  히스토그램 자동 검출은 잔상 이펙트(1137–1138)도 컷으로 잡았다 → 자동값을 그대로 쓰지 않는다.
- 인물은 색으로 고른다(rtmw_to_stickman_2d.pick_target strict). 관측이 있는 첫 장~마지막 장 사이가 그 컷에서 '있음'이다.
  - 그 사이 놓친 장은 가중 0으로 두어 이웃 키로 잇는다.
  - 그 밖에서 화면에 그 인물 색이 충분한 장(잔상 등)은 '있음·관절 관측 없음'으로 보고서에 표시하고 그리지 않는다
    (사용자: 잔상도 뼈대는 있다. 포즈는 데이터로 정할 수 없어 키포즈 지정 후보로 남긴다).
- 인물마다 rtmw_to_stickman_2d_v2.run_core(키포즈 + 흔들림 깎기 + 무릎 검사) → stickman_variants.basic_joints(10조각).
- SFA: 인물마다 오브젝트 ID 묶음이 다르고(장끼리 유지), 점 ID는 장마다 새로, 인물마다 파란점 하나. 선 색은 인물 색.

사용:
  python tools/stickman_clip.py RTMW.jsonl.gz 영상.mp4 출력.sfa --start 1032 --end 1271 --cuts 1136 1234 \
      --colors blue red --crop-y 63 [--report 보고.json] [--joints 관절.json]
"""
import argparse
import json
import os
import sys
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rtmw_to_stickman_2d import load_rtmw, pick_target  # noqa: E402
from rtmw_to_stickman_2d_v2 import run_core, calib  # noqa: E402
from stickman_variants import basic_joints  # noqa: E402
from pose_to_stickman import BODY  # noqa: E402

LINE_COLOR = {'blue': -16776961, 'red': -65536}   # ARGB 0xFF0000FF, 0xFFFF0000
FR0, AO0, PT0 = 5000, 4560000, 5680000
STYLE = ('Color="{c}" LayerId="0" ThicknessScale="{th}" ObjectScale="1.0" '
         'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0"')


def color_area(video, frames, color):
    import cv2
    from rtmw_validate import color_masks
    cap = cv2.VideoCapture(video)
    out = []
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, im = cap.read()
        _, b, r = color_masks(im)
        out.append(float((b if color == 'blue' else r).mean()))
    return np.array(out)


CHAIN_DOWN = {11: (13, 15), 12: (14, 16), 13: (15,), 14: (16,), 5: (7, 9), 6: (8, 10), 7: (9,), 8: (10,),
              15: (17, 18, 19), 16: (20, 21, 22)}


def border_info(K, img_w, img_h, top, frac=0.06, min_px=8.0):
    """화면 가장자리 관절 판정(11-03).
    가까운 화면에서 RTMW는 화면 밖 무릎·발목을 화면 끝에 몰아 찍는다(1136–1233: 무릎 y 707–723, 점수 3.9).
    몰린 축(아래·위 끝이면 y, 좌·우 끝이면 x)만 버리고 나머지 축은 관측으로 남긴다 — x는 다리 움직임을 따라 바뀐다
    (1186–1194 왼무릎 x 485 → 665). 그 관절은 그 끝 바깥에 있어야 한다는 조건(side)을 단다.
    반환: bm(가장자리 또는 사슬로 뺀 관절: 완전 관측 아님), Wax 축별 가중(0/1, 점수 조건은 호출 쪽에서 곱함), side(1 아래 2 위 3 왼 4 오른).
    사슬 규칙: 부모가 가장자리이고 자식이 가장자리가 아니면(화면 안에 찍힘) 자식은 관측에서 완전히 뺀다(발 점 포함)."""
    T, Jn = K.shape[:2]
    tor = np.linalg.norm((K[:, 5, :2] + K[:, 6, :2]) / 2 - (K[:, 11, :2] + K[:, 12, :2]) / 2, axis=1)
    m = np.maximum(min_px, frac * tor)[:, None]
    x, y = K[:, :, 0], K[:, :, 1]
    d = np.stack([(img_h - 1) - y, y - top, x, (img_w - 1) - x], -1)      # 아래·위·왼·오른 끝까지 거리
    near = d <= m[..., None]
    at = near.any(-1)
    side = np.where(at, np.argmin(np.where(near, d, np.inf), -1) + 1, 0)
    Wax = np.ones((T, Jn, 2))
    Wax[side == 1, 1] = Wax[side == 2, 1] = 0                # 아래·위 끝: y 버림
    Wax[side == 3, 0] = Wax[side == 4, 0] = 0                # 좌·우 끝: x 버림
    bm = at.copy()
    for j, kids in CHAIN_DOWN.items():
        for k in kids:
            if k >= Jn:
                continue
            chain_only = bm[:, j] & ~at[:, k]
            bm[:, k] |= bm[:, j]
            Wax[chain_only, k, :] = 0
    return bm, Wax, side


def border_mask(K, img_w, img_h, top, frac=0.06, min_px=8.0):
    return border_info(K, img_w, img_h, top, frac, min_px)[0]


SELECT = {'mode': 'density', 'side_rule': 'any', 'log': None, 'q': 50, 'scale_smooth': (9, 5), 'resym': False, 'key_sigma': (0.06, 0.05)}


def pick_shot(R, video, frames, color):
    log = SELECT['log'].setdefault(color, []) if SELECT['log'] is not None else None
    return pick_target(R, frames, video, color, strict=True, select=SELECT['mode'], log=log)


def person_in_shot(R, video, frames, color, min_obs=4, area_min=0.01, min_score=1.5, img=None, L_fallback=None, K=None):
    """한 컷·한 인물. 반환: (관절 dict 또는 None, 있음 마스크, 보고). img = (폭, 높이, 화면 위 끝 y)."""
    if K is None:
        K = pick_shot(R, video, frames, color)
    obs = np.array([k is not None for k in K])
    rep = {'observed_frames': int(obs.sum())}
    area = color_area(video, frames, color)
    if obs.sum() < min_obs:
        rep['skipped'] = f'관측 {int(obs.sum())}장 < {min_obs}'
        rep['present_unobserved'] = [frames[t] for t in np.flatnonzero(area >= area_min)]
        return None, np.zeros(len(frames), bool), rep
    i0, i1 = int(np.flatnonzero(obs)[0]), int(np.flatnonzero(obs)[-1])
    idx = np.flatnonzero(obs)
    Kf = []
    for t in range(i0, i1 + 1):
        Kf.append(K[t] if obs[t] else K[idx[np.argmin(np.abs(idx - t))]])
    Kf = np.array(Kf)
    W = (Kf[:, :, 2] >= min_score).astype(float)
    W[~obs[i0:i1 + 1]] = 0
    n_border = 0
    if img is not None:
        bm, Wax, side = border_info(Kf, *img)
        n_border = int((bm[:, 5:17] & (W[:, 5:17] > 0)).sum())
        Wax = Wax * W[..., None]          # 점수·못 잡은 장 조건
        W[bm] = 0                         # 완전 관측(방향·길이 보정·앞쪽 판단)에서는 뺀다
        half = (Wax, side, (0.0, img[0] - 1, img[2], img[1] - 1))
    else:
        half = None
    sub = frames[i0:i1 + 1]
    J, S, r, _, _ = run_core(Kf, W, sub, q=SELECT['q'], symmetric=True, keys=True, L_fallback=L_fallback, half=half,
                             side_rule=SELECT['side_rule'], scale_smooth=SELECT['scale_smooth'], resym=SELECT['resym'],
                             key_sigma=SELECT['key_sigma'])
    rep['border_joints_dropped'] = n_border
    rep['L_from_fallback'] = r['L_from_fallback']
    B, info = basic_joints(J, S, facing=r['facing_leg'])
    present = np.zeros(len(frames), bool)
    present[i0:i1 + 1] = True
    outside = [frames[t] for t in range(len(frames)) if not present[t] and area[t] >= area_min]
    rep.update(range=[frames[i0], frames[i1]], filled_gaps=[frames[t] for t in range(i0, i1 + 1) if not obs[t]],
               present_unobserved=outside, keypose_segments=r['keypose_segments'], key_thr=r['key_thr'],
               rms_resid_torso_median=float(np.median([v for v in r['rms_resid_torso'] if v is not None])),
               knee_fixed=r['knee_fixed'] + [(sub[t], k) for t, k in info['knee_fixed_frames']],
               L_torso_units=r['L_torso_units'])
    full = {k: np.full((len(frames), 2), np.nan) for k in B}
    for k, v in B.items():
        full[k][i0:i1 + 1] = v
    full['_S'] = np.full((len(frames), 2), np.nan)       # 장별 몸통 배율(px, 두 열 같음) — 거리 굵기용
    full['_S'][i0:i1 + 1] = np.repeat(np.asarray(S, float)[:, None], 2, 1)
    return full, present, rep


def person_aos(n, slot, Jn, to_pct, color, thick=1.0):
    base = PT0 + n * 1000 + slot * 100
    out = []
    for oid, typ, pts in BODY:
        out.append(f'<AO ID="{AO0 + slot * 100 + oid}" TypeId="{typ}" DrawOrder="{AO0 + slot * 100 + oid}" '
                   + STYLE.format(c=LINE_COLOR.get(color, -16777216), th=f'{thick:.3f}') + '>')
        for i, (pid, name, fl, acs) in enumerate(pts):
            x, y = to_pct(Jn[name])
            out.append(f'<AP ID="{base + pid}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{base + c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    return ''.join(out)


def distance_thickness(S, refs, t_min=0.2, t_max=20.0):
    """카메라(뷰어)와의 거리에 따른 선 굵기(11-03 사용자): 화면 속 인물 크기(몸통 배율 S, px)가 거리에 반비례하므로
    굵기 = t1 × (S / S1)^k. 기준 두 점 (S1, t1), (S2, t2)를 정확히 지나도록 k = ln(t2/t1) / ln(S2/S1).
    사용자 기준: 1032–1271 클립의 40장 파랑 = 1.0(지금 굵기), 120장 빨강 = 5.0(500%). 실측 S 73.3 대 376.4(비 5.14) → k ≈ 0.98
    (거의 S에 정비례 = 원근 규칙과 같다)."""
    (S1, t1), (S2, t2) = refs
    k = np.log(t2 / t1) / np.log(S2 / S1)
    return np.clip(t1 * (np.asarray(S, float) / S1) ** k, t_min, t_max), float(k)


def build(R, video, start, end, cuts, colors, img=None):
    frames = list(range(start, end + 1))
    bounds = [start] + [c for c in sorted(cuts) if start < c <= end] + [end + 1]
    shots = [(bounds[i], bounds[i + 1] - 1) for i in range(len(bounds) - 1)]
    people = {c: {'J': None, 'present': np.zeros(len(frames), bool)} for c in colors}
    rep = {'shots': shots, 'people': {c: [] for c in colors}}
    for c in colors:
        Jall = None
        # 인물 리그: 모든 컷의 관측을 모아 뼈 길이를 잰다(가장자리 점 제외). 컷 안 표본이 적은 뼈는 이 값을 쓴다.
        picks = {(s, e): pick_shot(R, video, list(range(s, e + 1)), c) for s, e in shots}
        allK = [k for v in picks.values() for k in v if k is not None]
        L_rig = None
        if len(allK) >= 4:
            AK = np.array(allK)
            AW = (AK[:, :, 2] >= 1.5).astype(float)
            if img is not None:
                AW[border_mask(AK, *img)] = 0
            L_rig, n_rig, _ = calib(AK, AW, SELECT['q'], True)
            rep.setdefault('person_rig', {})[c] = {'L': {k: round(v, 3) for k, v in L_rig.items()}, 'samples': n_rig}
        for s, e in shots:
            sub = list(range(s, e + 1))
            J, pres, r = person_in_shot(R, video, sub, c, img=img, L_fallback=L_rig, K=picks[(s, e)])
            r['shot'] = [s, e]
            rep['people'][c].append(r)
            if J is None:
                continue
            if Jall is None:
                Jall = {k: np.full((len(frames), 2), np.nan) for k in J}
            o = s - start
            for k in J:
                Jall[k][o:o + len(sub)] = J[k]
            people[c]['present'][o:o + len(sub)] |= pres
        people[c]['J'] = Jall
    return frames, people, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rtmw')
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--cuts', type=int, nargs='*', default=[])
    ap.add_argument('--colors', nargs='+', default=['blue', 'red'])
    ap.add_argument('--crop-y', type=float, default=0.0)
    ap.add_argument('--name', default='stickman_clip')
    ap.add_argument('--report')
    ap.add_argument('--joints')
    ap.add_argument('--select', choices=['density', 'coverage'], default='density', help='인물 검출 고르기: density(기존) / coverage((a) 재선택)')
    ap.add_argument('--side-rule', choices=['any', 'valid'], default='any', help='키 끝 조건: any(기존) / valid((b) 유효 축 관측이 있으면 끔)')
    ap.add_argument('--quantile', type=float, default=50, help='(c) 뼈 길이 분위(기본 L50)')
    ap.add_argument('--scale-smooth', type=int, nargs=2, default=[9, 5], help='(c) 몸통 배율 평활: 중앙값 창, 평균 창')
    ap.add_argument('--resym', action='store_true', help='(c) 리그 빌린 뒤 좌우 대칭 다시 맞춤')
    ap.add_argument('--key-sigma', type=float, nargs=2, default=[0.06, 0.05], help='키 흔들림 깎기(0 0이면 끔)')
    ap.add_argument('--thick-ref', nargs=2, metavar='장:색:굵기', help='거리 굵기 기준 두 점(클립 장 번호 0부터), 예: 40:blue:1.0 120:red:5.0')
    a = ap.parse_args()
    import cv2
    Wv = cv2.VideoCapture(a.video).get(cv2.CAP_PROP_FRAME_WIDTH)
    H = Wv * 9 / 16
    to_pct = lambda p: (100 * p[0] / Wv, 100 * (p[1] - a.crop_y) / H)  # noqa: E731
    R = load_rtmw(a.rtmw)
    SELECT.update(mode=a.select, side_rule=a.side_rule, log={}, q=a.quantile, scale_smooth=tuple(a.scale_smooth), resym=a.resym, key_sigma=tuple(a.key_sigma) if any(a.key_sigma) else None)
    cap = cv2.VideoCapture(a.video)
    img = (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT), a.crop_y)
    frames, people, rep = build(R, a.video, a.start, a.end, a.cuts, a.colors, img)
    thick = {c: np.ones(len(frames)) for c in a.colors}
    if a.thick_ref:
        pts = []
        for item in a.thick_ref:
            n_, c_, t_ = item.split(':')
            pts.append((float(people[c_]['J']['_S'][int(n_), 0]), float(t_)))
        for c in a.colors:
            if people[c]['J'] is not None:
                thick[c], k = distance_thickness(people[c]['J']['_S'][:, 0], pts)
        rep['thickness'] = {'refs': [[a.thick_ref[i], round(pts[i][0], 1)] for i in range(2)], 'k': round(k, 4),
                            'range': {c: [round(float(np.nanmin(thick[c])), 3), round(float(np.nanmax(thick[c])), 3)] for c in a.colors}}
    xml_frames, jout = [], []
    for n in range(len(frames)):
        parts = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
        jn = {}
        for slot, c in enumerate(a.colors):
            P = people[c]
            if P['J'] is None or not P['present'][n]:
                jn[c] = None
                continue
            Jn = {k: v[n] for k, v in P['J'].items() if not k.startswith('_')}
            parts.append(person_aos(n, slot, Jn, to_pct, c, float(np.nan_to_num(thick[c][n], nan=1.0))))
            jn[c] = {k: [round(float(v[0]), 2), round(float(v[1]), 2)] for k, v in Jn.items()}
        parts.append('</Frame>')
        xml_frames.append(''.join(parts))
        jout.append(jn)
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{a.name}" HeightWidthRatio="{H / Wv:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">'
           + ''.join(xml_frames) + '</Sequence>')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    rep.update(frames=[a.start, a.end], cuts=a.cuts, colors=a.colors, select=a.select, side_rule=a.side_rule,
               select_log={c: [x for x in v if x[1] != 'same'] for c, v in SELECT['log'].items()},
               present_frames={c: int(people[c]['present'].sum()) for c in a.colors})
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if a.joints:
        json.dump(jout, open(a.joints, 'w'), ensure_ascii=False)
    print('SFA', os.path.basename(a.out), '장', len(frames), '컷', rep['shots'], '있음', rep['present_frames'])


if __name__ == '__main__':
    main()
