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
from rtmw_to_stickman_2d_v2 import run_core  # noqa: E402
from stickman_variants import basic_joints  # noqa: E402
from pose_to_stickman import BODY  # noqa: E402

LINE_COLOR = {'blue': -16776961, 'red': -65536}   # ARGB 0xFF0000FF, 0xFFFF0000
FR0, AO0, PT0 = 5000, 4560000, 5680000
STYLE = ('Color="{c}" LayerId="0" ThicknessScale="1.0" ObjectScale="1.0" '
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


def person_in_shot(R, video, frames, color, min_obs=4, area_min=0.01, min_score=1.5):
    """한 컷·한 인물. 반환: (관절 dict 또는 None, 있음 마스크, 표시할 장 목록, 보고)."""
    K = pick_target(R, frames, video, color, strict=True)
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
    sub = frames[i0:i1 + 1]
    J, S, r, _, _ = run_core(Kf, W, sub, q=50, symmetric=True, keys=True)
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
    return full, present, rep


def person_aos(n, slot, Jn, to_pct, color):
    base = PT0 + n * 1000 + slot * 100
    out = []
    for oid, typ, pts in BODY:
        out.append(f'<AO ID="{AO0 + slot * 100 + oid}" TypeId="{typ}" DrawOrder="{AO0 + slot * 100 + oid}" '
                   + STYLE.format(c=LINE_COLOR.get(color, -16777216)) + '>')
        for i, (pid, name, fl, acs) in enumerate(pts):
            x, y = to_pct(Jn[name])
            out.append(f'<AP ID="{base + pid}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{base + c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    return ''.join(out)


def build(R, video, start, end, cuts, colors):
    frames = list(range(start, end + 1))
    bounds = [start] + [c for c in sorted(cuts) if start < c <= end] + [end + 1]
    shots = [(bounds[i], bounds[i + 1] - 1) for i in range(len(bounds) - 1)]
    people = {c: {'J': None, 'present': np.zeros(len(frames), bool)} for c in colors}
    rep = {'shots': shots, 'people': {c: [] for c in colors}}
    for c in colors:
        Jall = None
        for s, e in shots:
            sub = list(range(s, e + 1))
            J, pres, r = person_in_shot(R, video, sub, c)
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
    a = ap.parse_args()
    import cv2
    Wv = cv2.VideoCapture(a.video).get(cv2.CAP_PROP_FRAME_WIDTH)
    H = Wv * 9 / 16
    to_pct = lambda p: (100 * p[0] / Wv, 100 * (p[1] - a.crop_y) / H)  # noqa: E731
    R = load_rtmw(a.rtmw)
    frames, people, rep = build(R, a.video, a.start, a.end, a.cuts, a.colors)
    xml_frames, jout = [], []
    for n in range(len(frames)):
        parts = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
        jn = {}
        for slot, c in enumerate(a.colors):
            P = people[c]
            if P['J'] is None or not P['present'][n]:
                jn[c] = None
                continue
            Jn = {k: v[n] for k, v in P['J'].items()}
            parts.append(person_aos(n, slot, Jn, to_pct, c))
            jn[c] = {k: [round(float(v[0]), 2), round(float(v[1]), 2)] for k, v in Jn.items()}
        parts.append('</Frame>')
        xml_frames.append(''.join(parts))
        jout.append(jn)
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{a.name}" HeightWidthRatio="{H / Wv:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">'
           + ''.join(xml_frames) + '</Sequence>')
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    rep.update(frames=[a.start, a.end], cuts=a.cuts, colors=a.colors,
               present_frames={c: int(people[c]['present'].sum()) for c in a.colors})
    if a.report:
        json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
    if a.joints:
        json.dump(jout, open(a.joints, 'w'), ensure_ascii=False)
    print('SFA', os.path.basename(a.out), '장', len(frames), '컷', rep['shots'], '있음', rep['present_frames'])


if __name__ == '__main__':
    main()
