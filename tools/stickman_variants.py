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


def basic_joints(J, S, head_d=HEAD_TEMPLATE):
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
    u = unit(neck - pel)
    tor = np.linalg.norm(neck - pel, axis=1)
    out['head_t'] = neck + u * (tor * head_d)[:, None]
    shift = {f'{p}_{s}': float(np.median(np.linalg.norm(out[f'{p}_{s}'] - J[f'{p}_{s}'], axis=1) / S))
             for p in ('wri', 'ank') for s in ('l', 'r')}
    return out, {'ratios_torso_units': ratios, 'head_d': head_d, 'median_end_shift_torso': shift}


def write_sfa(path, name, frames_xml, W, H):
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames_xml)}" BackgroundColor="-1">'
           + ''.join(frames_xml) + '</Sequence>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + '.xml', xml)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['basic'])
    ap.add_argument('joints')
    ap.add_argument('report')
    ap.add_argument('out')
    ap.add_argument('--width', type=float, required=True)
    ap.add_argument('--crop-y', type=float, default=0.0)
    ap.add_argument('--name', default='stickman_basic')
    ap.add_argument('--head', type=float, default=HEAD_TEMPLATE)
    ap.add_argument('--joints-out')
    a = ap.parse_args()
    J, S, rep = load(a.joints, a.report)
    W, H = a.width, a.width * 9 / 16
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - a.crop_y) / H)  # noqa: E731
    B, info = basic_joints(J, S, a.head)
    T = len(S)
    frames = [basic_frame_xml(n, {k: v[n] for k, v in B.items()}, to_pct) for n in range(T)]
    write_sfa(a.out, a.name, frames, W, H)
    if a.joints_out:
        json.dump([{k: [round(float(v[n, 0]), 2), round(float(v[n, 1]), 2)] for k, v in B.items()} for n in range(T)],
                  open(a.joints_out, 'w'), ensure_ascii=False)
    print('SFA', os.path.basename(a.out), '장', T, json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
