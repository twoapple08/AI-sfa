"""스틱맨 시제품 관절(px) → 변형 SFA(2026-11-03 사용자 지시 3개).

1. basic: 목·어깨·골반 조각을 지운 앱 기본 스틱맨 10조각(data/app_templates/stickman_default.sfa 구조, tools/pose_to_stickman.BODY).
   - 팔은 목(어깨 중점)에, 다리는 골반(엉덩이 중점)에 붙는다.
   - 위팔 = 목 → 피팅 팔꿈치 방향, 허벅지 = 골반 → 피팅 무릎 방향. 길이는 인물 크기(장별 몸통 배율 S) × 고정 비율(전 장 중앙값, 좌우 평균).
     아래팔·정강이는 피팅 벡터를 그대로 옮긴다(방향·길이 유지). 그래서 손·발 위치는 어깨·엉덩이 반폭만큼 옮겨질 수 있다.
   - 머리 원: 앱 기본 틀 비율(지름 = 몸통 × 8.4/11.2), 몸통 방향, 목 점에 붙는다.
2. curve: 1에서 몸통 직선을 2차 베지어 곡선(TypeId 3)으로 바꿔 허리를 표현한다(--bend로 휘는 양 지정, 장별 배열).
3. silhouette: 뼈마다 사람 몸 두께를 입힌 실루엣 외곽선(별도 함수).

사용:
  python tools/stickman_variants.py basic 관절.json 보고.json 출력.sfa --width 1152 --crop-y 63 [--name 이름] [--joints-out 관절.json]
"""
import argparse
import json
import os
import sys
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pose_to_stickman import frame_xml as basic_frame_xml  # noqa: E402

HEAD_TEMPLATE = 8.4 / 11.2


def load(joints_path, report_path):
    J = json.load(open(joints_path, encoding='utf-8'))
    rep = json.load(open(report_path, encoding='utf-8'))
    Jd = {k: np.array([j[k] for j in J], float) for k in J[0]}
    S = np.array(rep['scale_smoothed'], float)
    return Jd, S, rep


def unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def basic_joints(J, S, head_d=HEAD_TEMPLATE, facing=None):
    """시제품 관절 → 기본 스틱맨 관절(이름은 pose_to_stickman.BODY와 같음)."""
    neck, pel = J['neck'], J['pel']
    out = {'neck': neck, 'pelvis': pel}
    ratios = {}
    for part, base, src in (('elb', neck, 'elb'), ('kne', pel, 'kne')):
        r = [np.median(np.linalg.norm(J[f'{src}_{s}'] - base, axis=1) / S) for s in ('l', 'r')]
        ratios[part] = float(np.mean(r))
    for s in ('l', 'r'):
        out[f'elb_{s}'] = neck + unit(J[f'elb_{s}'] - neck) * (S * ratios['elb'])[:, None]
        out[f'wri_{s}'] = out[f'elb_{s}'] + (J[f'wri_{s}'] - J[f'elb_{s}'])
        out[f'kne_{s}'] = pel + unit(J[f'kne_{s}'] - pel) * (S * ratios['kne'])[:, None]
        out[f'ank_{s}'] = out[f'kne_{s}'] + (J[f'ank_{s}'] - J[f'kne_{s}'])
    knee_fixed = []
    if facing is not None:   # 허벅지 뿌리를 골반 가운데로 옮기면 거의 곧은 다리가 반대로 꺾일 수 있다(B 326–334, 11-03) → 다시 검사
        from rtmw_to_stickman_2d_v2 import fix_knees
        knee_fixed = fix_knees(out, np.asarray(facing), (('pelvis', 'kne_l', 'ank_l'), ('pelvis', 'kne_r', 'ank_r')))
    u = unit(neck - pel)
    tor = np.linalg.norm(neck - pel, axis=1)
    out['head_t'] = neck + u * (tor * head_d)[:, None]
    shift = {f'{p}_{s}': float(np.median(np.linalg.norm(out[f'{p}_{s}'] - J[f'{p}_{s}'], axis=1) / S))
             for p in ('wri', 'ank') for s in ('l', 'r')}
    return out, {'ratios_torso_units': ratios, 'head_d': head_d, 'median_end_shift_torso': shift, 'knee_fixed_frames': knee_fixed}


def torso_offset(mask, P, N, fr=np.linspace(0.35, 0.65, 7)):
    """원본 그림의 몸통 중심선이 직선 P(엉덩이 중점) → N(어깨 중점)에서 수직으로 얼마나 벗어났는지(몸통 단위, 부호 있음).
    몸통 35–65% 지점마다 직선에 수직으로 대상 색 영역의 연속 구간(직선 위 점을 포함하거나 가장 가까운 것)을 찾아 가운데를 잰다.
    반환: (중심 오프셋들, 폭들) 배열."""
    v = N - P
    L = np.linalg.norm(v)
    if L < 1e-6:
        return np.array([]), np.array([])
    u = v / L
    n = np.array([-u[1], u[0]])
    ts = np.arange(-0.6 * L, 0.6 * L, 1.0)
    z = len(ts) // 2
    offs, widths = [], []
    for f in fr:
        pts = (P + v * f + ts[:, None] * n).round().astype(int)
        ok = (pts[:, 0] >= 0) & (pts[:, 0] < mask.shape[1]) & (pts[:, 1] >= 0) & (pts[:, 1] < mask.shape[0])
        on = np.zeros(len(ts), bool)
        on[ok] = mask[pts[ok, 1], pts[ok, 0]] > 0
        idx = np.flatnonzero(np.diff(np.r_[0, on.astype(int), 0]))
        runs = list(zip(idx[::2], idx[1::2] - 1))
        if not runs:
            continue
        s, e = min(runs, key=lambda r: 0 if r[0] <= z <= r[1] else min(abs(r[0] - z), abs(r[1] - z)))
        offs.append((ts[s] + ts[e]) / 2 / L)
        widths.append((ts[e] - ts[s]) / L)
    return np.array(offs), np.array(widths)


def measure_bend(video, K, frames, segments, color='blue'):
    """그림 구간마다 몸통 휨(몸통 단위)을 잰다. 기준선은 그 장 RTMW 엉덩이 중점 → 어깨 중점(원본 그림과 시간이 맞음).
    팔이 몸통을 가리면 폭이 커지므로, 폭이 전체 중앙값의 1.5배를 넘거나 0.5배 미만인 표본은 뺀다."""
    import cv2
    from rtmw_validate import color_masks
    cap = cv2.VideoCapture(video)
    per = []
    for t, f in enumerate(frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, im = cap.read()
        _, blue, red = color_masks(im)
        m = cv2.morphologyEx((blue if color == 'blue' else red).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        k = K[t]
        per.append(torso_offset(m, (k[11, :2] + k[12, :2]) / 2, (k[5, :2] + k[6, :2]) / 2))
    allw = np.concatenate([w for _, w in per if len(w)])
    wmed = float(np.median(allw)) if len(allw) else 1.0
    seg_bend = []
    for s, e in segments:
        o = np.concatenate([off[(w <= 1.5 * wmed) & (w >= 0.5 * wmed)] for off, w in per[s:e + 1]] or [np.array([])])
        seg_bend.append(float(np.median(o)) if len(o) else np.nan)
    return np.array(seg_bend), wmed


def curve_frame_xml(n, Jn, bend, to_pct, thick='1.0'):
    """기본 스틱맨 10조각에서 몸통만 2차 베지어(TypeId 3, 점 3개: 목·조절점·골반)로 바꾼 장.
    조절점 = 몸통 가운데 + 수직 × (2 × 휨 × 몸통 길이)(2차 베지어의 t=0.5 점은 조절점 오프셋의 절반)."""
    from pose_to_stickman import BODY, FR0, AO0, PT0, AO_STYLE
    P, N = np.asarray(Jn['pelvis']), np.asarray(Jn['neck'])
    v = N - P
    L = np.linalg.norm(v)
    nrm = np.array([-v[1], v[0]]) / max(L, 1e-9)
    J = dict(Jn)
    J['ctrl'] = (P + N) / 2 + nrm * (2 * bend * L)
    base = PT0 + n * 100
    out = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
    for oid, typ, pts in BODY:
        if oid == 2:   # 몸통: (목 4) – (조절점 5, 연결 없음) – (골반 3)
            typ = '3'
            pts = [pts[0], (21, 'ctrl', 5, []), pts[1]]
        out.append(f'<AO ID="{AO0 + oid}" TypeId="{typ}" DrawOrder="{AO0 + oid}" ' + AO_STYLE.format(th=thick) + '>')
        for i, (pid, name, fl, acs) in enumerate(pts):
            x, y = to_pct(J[name])
            out.append(f'<AP ID="{base + pid}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{base + c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ''.join(out)


def write_sfa(path, name, frames_xml, W, H):
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames_xml)}" BackgroundColor="-1">'
           + ''.join(frames_xml) + '</Sequence>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + '.xml', xml)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['basic', 'curve'])
    ap.add_argument('joints')
    ap.add_argument('report')
    ap.add_argument('out')
    ap.add_argument('--width', type=float, required=True)
    ap.add_argument('--crop-y', type=float, default=0.0)
    ap.add_argument('--name', default='stickman_basic')
    ap.add_argument('--head', type=float, default=HEAD_TEMPLATE)
    ap.add_argument('--joints-out')
    ap.add_argument('--video', help='curve: 원본 영상')
    ap.add_argument('--rtmw', help='curve: RTMW 결과')
    ap.add_argument('--start', type=int, help='curve: 첫 장 번호')
    ap.add_argument('--color', default='blue')
    ap.add_argument('--bend-gain', type=float, default=1.0, help='curve: 잰 휨에 곱하는 배율')
    ap.add_argument('--bend-max', type=float, default=0.2, help='curve: 휨 상한(몸통 단위)')
    ap.add_argument('--bend-sigma', type=float, default=0.03, help='curve: 그림별 휨 흔들림 허용치(몸통 단위, 0이면 그대로 잇기)')
    a = ap.parse_args()
    J, S, rep = load(a.joints, a.report)
    W, H = a.width, a.width * 9 / 16
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - a.crop_y) / H)  # noqa: E731
    B, info = basic_joints(J, S, a.head, rep.get('facing'))
    T = len(S)
    if a.mode == 'basic':
        frames = [basic_frame_xml(n, {k: v[n] for k, v in B.items()}, to_pct) for n in range(T)]
    else:
        from rtmw_to_stickman_2d import load_rtmw, pick_target
        from rtmw_to_stickman_2d_v2 import smooth_keys
        fr_ids = list(range(a.start, a.start + T))
        K = np.array(pick_target(load_rtmw(a.rtmw), fr_ids, a.video, a.color))
        segs = [(s - a.start, e - a.start) for s, e in rep['keypose_segments']]
        sb, wmed = measure_bend(a.video, K, fr_ids, segs, a.color)
        ck = np.array([(s + e) / 2 for s, e in segs])
        ok = ~np.isnan(sb)
        # 그림별 휨을 그대로 이으면 허리가 꿀렁인다(사용자 11-03, B 322–324·328–330만 부호가 튐) → 흔들림 허용치 안에서 고른 뒤 잇는다
        bend_sm = smooth_keys(ck[ok], sb[ok][:, None], a.bend_sigma, np.arange(T, dtype=float))[:, 0] if a.bend_sigma > 0 \
            else smooth_keys(ck[ok], sb[ok][:, None], 1e-9, np.arange(T, dtype=float))[:, 0]
        bend = np.clip(a.bend_gain * bend_sm, -a.bend_max, a.bend_max)
        frames = [curve_frame_xml(n, {k: v[n] for k, v in B.items()}, bend[n], to_pct) for n in range(T)]
        info.update(segment_bend=[None if np.isnan(x) else round(float(x), 3) for x in sb], torso_width_median=round(wmed, 3),
                    bend_gain=a.bend_gain, bend_max=a.bend_max, bend_sigma=a.bend_sigma,
                    frame_bend=[round(float(x), 3) for x in bend])
    write_sfa(a.out, a.name, frames, W, H)
    if a.joints_out:
        json.dump([{k: [round(float(v[n, 0]), 2), round(float(v[n, 1]), 2)] for k, v in B.items()} for n in range(T)],
                  open(a.joints_out, 'w'), ensure_ascii=False)
    print('SFA', os.path.basename(a.out), '장', T, json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
