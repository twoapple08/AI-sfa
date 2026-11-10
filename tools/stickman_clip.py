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
    next_frame = None
    for f in frames:
        if f != next_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, im = cap.read()
        if not ok:
            cap.release()
            raise ValueError(f'원영상 {f}장을 읽을 수 없다')
        next_frame = f + 1
        _, b, r = color_masks(im)
        out.append(float((b if color == 'blue' else r).mean()))
    cap.release()
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


SELECT = {'mode': 'density', 'side_rule': 'any', 'log': None, 'q': 50, 'scale_smooth': (9, 5), 'resym': False, 'key_sigma': (0.06, 0.05), 'key_starts': {}, 'projection': False, 'image_keys': False}


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
    from stickman_fit_cache import cached_fit
    core_args = dict(q=SELECT['q'], symmetric=True, keys=True, L_fallback=L_fallback,
                     side_rule=SELECT['side_rule'], scale_smooth=SELECT['scale_smooth'], resym=SELECT['resym'],
                     key_sigma=SELECT['key_sigma'], key_starts=[f for f in SELECT['key_starts'].get(color, []) if f in sub])
    arrays = dict(K=Kf, W=W)
    if half is not None:
        arrays.update(wax=half[0], side=half[1])
    J, S, r, fit_cache = cached_fit(SELECT.get('fit_cache'), arrays,
        dict(core_args, frames=sub, bounds=half[2] if half is not None else None),
        lambda: run_core(Kf, W, sub, half=half, **core_args))
    rep['fit_cache'] = fit_cache
    rep['border_joints_dropped'] = n_border
    rep['L_from_fallback'] = r['L_from_fallback']
    B, info = basic_joints(J, S, facing=r['facing_leg'])
    output_segments = r['keypose_segments']
    if SELECT['projection']:
        from stickman_projection import projected_joints
        if SELECT['image_keys']:
            from stickman_image_keys import video_segments
            output_segments, matches = video_segments(video, sub, Kf, W, color, r['keypose_segments'],
                                                      [f for f in SELECT['key_starts'].get(color, []) if f in sub])
            rep['image_keys'] = {'decisions': matches, 'fit_segments_unchanged': r['keypose_segments'],
                                 'method': '원본 템플릿 정합·미확정은 기존 경계, 완전 관측 사슬2D대응·키 좌표 직접 보간'}
            if SELECT.get('key_motion_v2'):
                from stickman_key_motion import keyed_medians
                spans = [(sub.index(a), sub.index(b)) for a,b in output_segments]
                S = keyed_medians(S, spans)
                rep['image_keys']['scale_method'] = '같은 그림 키의 척도 중간값→좌표와 같은 키 시각으로 보간'
        B, rep['projection'] = projected_joints(Kf, W, half, sub, output_segments, J, S,
            direct_keys=SELECT['image_keys'], key_motion_v2=SELECT.get('key_motion_v2', False),
            rebase_arms=SELECT.get('projected_arm_lengths', False))
    visibility = None
    body_views = [view for view in SELECT.get('body_views', [])
                  if view['actor'] == color and view['start'] <= sub[-1] and view['end'] >= sub[0]]
    if SELECT.get('face_evidence') is not None or body_views:
        from stickman_view_recovery import recover_views
        B, S, visibility, rep['view_recovery'] = recover_views(
            video, sub, Kf, B, S, output_segments, color, half[2], SELECT.get('face_evidence'),
            obs[i0:i1+1], body_views)
    present = np.zeros(len(frames), bool)
    present[i0:i1 + 1] = True
    outside = [frames[t] for t in range(len(frames)) if not present[t] and area[t] >= area_min]
    rep.update(range=[frames[i0], frames[i1]], filled_gaps=[frames[t] for t in range(i0, i1 + 1) if not obs[t]],
               present_unobserved=outside, keypose_segments=output_segments, key_thr=r['key_thr'],
               key_starts_added=r['key_starts_added'],
               rms_resid_torso_median=float(np.median([v for v in r['rms_resid_torso'] if v is not None])),
               knee_fixed=r['knee_fixed'] + [(sub[t], k) for t, k in info['knee_fixed_frames']],
               L_torso_units=r['L_torso_units'])
    if SELECT['projection']:
        # 기존 고정 길이 풀이의 잔차를 새 출력의 잔차로 보고하지 않는다.
        rep['fixed_fit_rms_resid_torso_median'] = rep.pop('rms_resid_torso_median')
        from rtmw_to_stickman_2d import OBS
        names = [name for name in B if name in OBS]
        weights = half[0][:, [OBS[name] for name in names]] if half is not None else np.repeat(W[:, [OBS[name] for name in names], None], 2, axis=2)
        delta = (np.stack([B[name] for name in names], 1) - Kf[:, [OBS[name] for name in names], :2]) / np.asarray(S)[:, None, None]
        count = weights.sum((1, 2))
        error = np.sqrt((delta ** 2 * weights).sum((1, 2)) / np.maximum(count, 1))
        rep['projection_endpoint_axis_rms_torso_median'] = float(np.median(error[count > 0])) if (count > 0).any() else None
    full = {k: np.full((len(frames), 2), np.nan) for k in B}
    for k, v in B.items():
        full[k][i0:i1 + 1] = v
    full['_S'] = np.full((len(frames), 2), np.nan)       # 장별 몸통 배율(px, 두 열 같음) — 거리 굵기용
    full['_S'][i0:i1 + 1] = np.repeat(np.asarray(S, float)[:, None], 2, 1)
    if visibility is not None:
        full['_visibility'] = np.zeros((len(frames), 10), bool)
        full['_visibility'][i0:i1 + 1] = visibility
    return full, present, rep


def person_aos(n, slot, Jn, to_pct, color, thick=1.0, visible_segments=None):
    base = PT0 + n * 1000 + slot * 100
    out = []
    moving_head = 'head_b' in Jn
    if moving_head:
        from stickman_projection import constrain_head_contact
        # 캐시 좌표를 쓰는 호출에도 A안을 적용하되 입력·몸통·팔다리는 바꾸지 않는다.
        Jn = dict(Jn)
        Jn['head_t'], Jn['head_b'], _ = constrain_head_contact(Jn['neck'], Jn['head_t'], Jn['head_b'])
    body = sorted(BODY, key=lambda v: v[0] == 1)  # 머리는 앞에 그린다. 앱은 물리 순서, 렌더러는 DrawOrder를 사용한다.
    if moving_head:
        body = body[:-1] + [(11, '1', [(21, 'neck', 4, [3]), (22, 'head_b', 4, [2])])] + body[-1:]
    for oid, typ, pts in body:
        order = 50 if oid == 1 else oid
        # 내부 연결은 편집망에만 남긴다. 흰 원 가장자리의 안티앨리어싱에도 비치지 않게 한다.
        line_color = 0 if moving_head and oid == 11 else LINE_COLOR.get(color, -16777216)
        if visible_segments is not None and oid not in visible_segments:
            line_color = 0
        out.append(f'<AO ID="{AO0 + slot * 100 + oid}" TypeId="{typ}" DrawOrder="{AO0 + slot * 100 + order}" '
                   + STYLE.format(c=line_color, th=f'{thick:.3f}') + '>')
        # 원 내부의 편집용 연결선. A안의 접촉 제약으로 긴 목 가지가 밖에 드러나지 않는다.
        # 원의 두 지름 끝점과 몸통 허브가 다른 겹침 자세에서도 단일 연결망을 유지한다.
        for i, (pid, name, fl, acs) in enumerate(pts):
            if moving_head:
                if oid == 1 and pid == 2:
                    name, acs = 'head_b', [22]
                elif pid == 3:
                    acs = [v for v in acs if v != 2] + [21]
            x, y = to_pct(Jn[name])
            out.append(f'<AP ID="{base + pid}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{base + c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    if visible_segments is None or 1 in visible_segments:
        # 원 전체 채움은 Kind=1이다. 종류 없는 edge를 뷰어가 원으로 보완해도 앱 호환 근거가 되지 않는다.
        out.append(f'<FR ID="{7800000 + n * 10 + slot}" Color="-1"><FS Kind="1" ObjId="{AO0 + slot * 100 + 1}" Contour="0"/></FR>')
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
                Jall = {}
            o = s - start
            for k in J:
                if k not in Jall:
                    Jall[k] = np.full((len(frames), *J[k].shape[1:]), np.nan)
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
    ap.add_argument('--select', choices=['density', 'coverage'], default='coverage', help='인물 검출 고르기: coverage((a) 재선택, 기준판 11-03 합의) / density(옛 방식)')
    ap.add_argument('--side-rule', choices=['any', 'valid'], default='valid', help='키 끝 조건: valid((b) 유효 축 관측이 있으면 끔, 기준판) / any(옛 방식)')
    ap.add_argument('--quantile', type=float, default=50, help='(c) 뼈 길이 분위(기본 L50)')
    ap.add_argument('--scale-smooth', type=int, nargs=2, default=[9, 5], help='(c) 몸통 배율 평활: 중앙값 창, 평균 창')
    ap.add_argument('--resym', action='store_true', help='(c) 리그 빌린 뒤 좌우 대칭 다시 맞춤')
    ap.add_argument('--key-sigma', type=float, nargs=2, default=[0.06, 0.05], help='키 흔들림 깎기(0 0이면 끔)')
    ap.add_argument('--key-start', nargs='*', default=[], metavar='색:장', help='원본 대조용 키 시작 장 추가. 예: blue:1038 blue:1088. 자동 경계는 유지하며 기본값은 추가 없음')
    ap.add_argument('--projection', action='store_true', help='관측 가능한 키별 2D 길이와 머리 위치 보존(사용자 비교판)')
    ap.add_argument('--image-keys', action='store_true', help='--projection에서 원본 무늬로 키 분리·완전 관측 가지 대응·키 좌표 직접 보간(비교용)')
    ap.add_argument('--fit-cache', help='CPU 보정 전 피팅 캐시 폴더. 입력/코드 해시가 같을 때만 재사용')
    ap.add_argument('--key-motion-v2', action='store_true', help='미승인 공통 처리 시험: 같은 키 척도/지역적 가림/짧은 가림 뒤 가지 대응')
    ap.add_argument('--projected-arm-lengths', action='store_true', help='미승인 시험: 원본 키마다 잰2D 팔 길이로 팔꿈치 재배치,손목/몸통 유지')
    ap.add_argument('--body-views', help='위몸이 틀 밖인 구도 태그 JSON. 좌표가 아닌 관측 범위 데이터,미승인 시험')
    ap.add_argument('--face-evidence', help='CPU 독립 얼굴 관측 JSON. 확대/부분 인물 복구 선택 시험,원영상 지문 대조')
    ap.add_argument('--scene', help='고정 뼈대용 장면 JSON: 접촉·보완 관측·부분 인물. --projection 필요')
    ap.add_argument('--thick-ref', nargs=2, metavar='장:색:굵기', help='거리 굵기 기준 두 점(클립 장 번호 0부터), 예: 40:blue:1.0 120:red:5.0')
    a = ap.parse_args()
    key_starts = {}
    for item in a.key_start:
        try:
            c, f = item.split(':')
            f = int(f)
        except ValueError:
            ap.error('--key-start는 색:장 형식이어야 한다')
        if c not in a.colors or not a.start <= f <= a.end:
            ap.error('--key-start의 색·장이 처리 대상 밖이다')
        key_starts.setdefault(c, []).append(f)
    import cv2
    Wv = cv2.VideoCapture(a.video).get(cv2.CAP_PROP_FRAME_WIDTH)
    H = Wv * 9 / 16
    to_pct = lambda p: (100 * p[0] / Wv, 100 * (p[1] - a.crop_y) / H)  # noqa: E731
    R = load_rtmw(a.rtmw)
    SELECT.update(mode=a.select, side_rule=a.side_rule, log={}, q=a.quantile, scale_smooth=tuple(a.scale_smooth), resym=a.resym, key_sigma=tuple(a.key_sigma) if any(a.key_sigma) else None, key_starts=key_starts)
    SELECT['projection'] = a.projection
    if a.image_keys and not a.projection:
        ap.error('--image-keys는 --projection과 함께 사용한다')
    SELECT['image_keys'] = a.image_keys
    SELECT['fit_cache'] = a.fit_cache
    if a.key_motion_v2 and not a.image_keys:
        ap.error('--key-motion-v2는 --projection --image-keys와 함께 사용한다')
    SELECT['key_motion_v2'] = a.key_motion_v2
    if (a.projected_arm_lengths or a.body_views) and not a.key_motion_v2:
        ap.error('팔 길이/부분 구도 시험은 --key-motion-v2와 함께 사용한다')
    SELECT['projected_arm_lengths'] = a.projected_arm_lengths
    SELECT['body_views'] = []
    if a.body_views:
        from stickman_face_evidence import digest
        with open(a.body_views) as source:
            config = json.load(source)
        if (config.get('schema') != 1 or config.get('source_sha256') != digest(a.video)
                or config.get('crop_y') != a.crop_y or not config['start'] <= a.start <= a.end <= config['end']):
            ap.error('부분 구도 태그와 원본/범위/화면 위 끝이 다르다')
        owned = set()
        for view in config['views']:
            if (view['kind'] != 'lower_body_top' or view['actor'] not in a.colors
                    or not config['start'] <= view['start'] <= view['end'] <= config['end']
                    or any(view['start'] < cut <= view['end'] for cut in a.cuts)):
                ap.error('부분 구도 태그의 종류/인물/범위/컷 오류')
            for f in range(view['start'], view['end']+1):
                if (f, view['actor']) in owned:
                    ap.error('부분 구도 태그가 중복된다')
                owned.add((f, view['actor']))
        SELECT['body_views'] = config['views']
    SELECT['face_evidence'] = None
    if a.face_evidence:
        if not a.key_motion_v2:
            ap.error('--face-evidence는 --key-motion-v2와 함께 쓰는 미승인 시험이다')
        from stickman_face_evidence import load_evidence
        source = cv2.VideoCapture(a.video)
        SELECT['face_evidence'] = load_evidence(a.face_evidence, a.video, range(a.start, a.end+1),
            int(source.get(cv2.CAP_PROP_FRAME_WIDTH)), int(source.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        source.release()
    if a.scene and not a.projection:
        ap.error('--scene은 --projection과 함께 사용한다')
    cap = cv2.VideoCapture(a.video)
    img = (cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT), a.crop_y)
    frames, people, rep = build(R, a.video, a.start, a.end, a.cuts, a.colors, img)
    rep['processing'] = dict(revision='2-experimental' if a.key_motion_v2 else '1', fixed_rig='stickman-2d-11-v1',
        image_key_coordinates=bool(a.image_keys), image_key_scale=bool(a.key_motion_v2),
        local_axis_censoring=bool(a.key_motion_v2), view_recovery=bool(a.face_evidence),
        projected_arm_lengths=bool(a.projected_arm_lengths), body_view_tags=len(SELECT['body_views']),
        automatic_quality_approval=False)
    poses = [{c: ({k: v[n].copy() for k, v in people[c]['J'].items() if not k.startswith('_')}
                  if people[c]['J'] is not None and people[c]['present'][n] else None)
              for c in a.colors} for n in range(len(frames))]
    if a.face_evidence or a.body_views:
        for n, pose in enumerate(poses):
            for c, j in pose.items():
                visibility = people[c]['J'].get('_visibility') if people[c]['J'] is not None else None
                if j is not None and visibility is not None and np.isfinite(visibility[n]).all():
                    j['_visible_segments'] = (np.flatnonzero(visibility[n]) + 1).tolist()
    if a.body_views:
        rep['body_views'] = dict(config_sha256=digest(a.body_views), tags=SELECT['body_views'], manual_coordinates=0)
    if a.face_evidence:
        rep['face_evidence'] = {k: SELECT['face_evidence'][k] for k in
            ('schema', 'source_sha256', 'model_sha256', 'threshold', 'backend')}
    if a.scene:
        from stickman_scene import load_scene, apply_scene
        scene, rig = load_scene(a.scene)
        if sorted(scene.get('cuts', [])) != sorted(a.cuts):
            ap.error('장면 JSON과 --cuts가 다르다')
        if scene.get('source_sha256'):
            import hashlib
            with open(a.video, 'rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != scene['source_sha256']:
                    ap.error('장면 JSON의 원본 영상 해시가 다르다')
        poses, scene_report = apply_scene(poses, frames, scene)
        rep['scene'] = dict(rig=rig, **scene_report)
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
            Jn = poses[n][c]
            if Jn is None:
                jn[c] = None
                continue
            th = thick[c][n]
            if not np.isfinite(th):
                same_shot = np.array([sum(f >= cut for cut in a.cuts) == sum(frames[n] >= cut for cut in a.cuts) for f in frames])
                valid = np.flatnonzero(np.isfinite(thick[c]) & same_shot)
                th = thick[c][min(valid, key=lambda t: abs(t - n))] if len(valid) else 1.
            th = Jn.get('_thick', th)
            parts.append(person_aos(n, slot, Jn, to_pct, c, float(th), Jn.get('_visible_segments')))
            jn[c] = {k: [round(float(v[0]), 2), round(float(v[1]), 2)] for k, v in Jn.items() if not k.startswith('_')}
            if '_visible_segments' in Jn:
                jn[c]['_visible_segments'] = list(Jn['_visible_segments'])
        parts.append('</Frame>')
        xml_frames.append(''.join(parts))
        jout.append(jn)
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{a.name}" HeightWidthRatio="{H / Wv:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">'
           + ''.join(xml_frames) + '</Sequence>')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    rep.update(frames=[a.start, a.end], cuts=a.cuts, colors=a.colors, select=a.select, side_rule=a.side_rule,
               key_starts_requested=key_starts, projection=a.projection, image_keys=a.image_keys,
               select_log={c: [x for x in v if x[1] != 'same'] for c, v in SELECT['log'].items()},
               present_frames={c: sum(row[c] is not None for row in poses) for c in a.colors})
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if a.joints:
        json.dump(jout, open(a.joints, 'w'), ensure_ascii=False)
    print('SFA', os.path.basename(a.out), '장', len(frames), '컷', rep['shots'], '있음', rep['present_frames'])


if __name__ == '__main__':
    main()
