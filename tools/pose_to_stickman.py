"""2D 포즈(COCO 17점) → 앱 기본 스틱맨 SFA(24/24). 2단계 '인물 → 스틱맨' 갈래(docs/STAGE2-GENERATOR-DESIGN-2026-11-02.md §1).

구조: 앱 기본 스틱맨 틀(BODY 주석)을 그대로 쓰고 점 위치만 포즈 방향 × 틀 길이로 옮긴다(팔다리 비율 고정,
화면 쪽으로 향한 팔다리만 원근 단축으로 짧아짐 — 늘어나지 않음).
머리는 몸통 방향을 따른다(얼굴 점은 애니에서 떨려 머리가 흔들렸다, 11-02 사용자). 무리 하나·파란점 하나, ID·연결은 모든 장에서 같다.

사용: python tools/pose_to_stickman.py pose.json 출력.sfa --start 298 --end 390 [--crop-y 27 --h 480] [--name 이름]
pose.json = {W, H, res: [장마다 None 또는 {kp: 17×[x,y,score]}]} (YOLO11-pose 추론 결과, 큰 사람 하나)
"""
import argparse
import json
import zipfile

import numpy as np

NOSE, LEYE, REYE, LEAR, REAR, LSHO, RSHO, LELB, RELB, LWRI, RWRI, LHIP, RHIP, LKNE, RKNE, LANK, RANK = range(17)


def clean(kps, min_score=0.3):
    """장 × 17 × 3 → 낮은 신뢰 점은 앞뒤 장에서 선형 보간, 5장 중앙값(튀는 장 제거) → 5장 가중 평균(1·2·3·2·1, 떨림 줄이기).
    (11-02: 3장 평균만으로는 팔 방향이 장마다 27–29°씩 튀는 장이 10%였다.)"""
    a = np.array(kps, float)
    n = len(a)
    for j in range(17):
        good = a[:, j, 2] >= min_score
        if good.sum() == 0:
            continue
        idx = np.arange(n)
        for c in (0, 1):
            a[:, j, c] = np.interp(idx, idx[good], a[good, j, c])
    med = a.copy()
    for t in range(n):
        med[t, :, :2] = np.median(a[max(0, t - 2):t + 3, :, :2], 0)
    sm = med.copy()
    w = np.array([1, 2, 3, 2, 1], float)
    for t in range(n):
        lo, hi = max(0, t - 2), min(n, t + 3)
        ww = w[lo - t + 2:hi - t + 2]
        sm[t, :, :2] = (med[lo:hi, :, :2] * ww[:, None, None]).sum(0) / ww.sum()
    return sm


# 앱 기본 스틱맨 틀(11-02 사용자가 준 앱 기본 스틱맨 data/app_templates/stickman_default.sfa를 그대로 옮김 — 10조각, 관절점 없음).
# Flags: 3 = 골반(파란점, 뿌리), 4 = 부모 점에 붙는 끝, 2 = 뿌리(골반)에 붙는 끝, 5 = 그 밖의 끝. 머리 원의 아래 끝(5)은 목에 붙음.
# 화면 왼쪽 팔다리(틀 X 45.8)를 인물의 오른쪽(r)으로 둔다(정면 기준).
# (AO ID, TypeId, [(점 ID, 이름, Flags, [연결 점 ID]) Index0, Index1])
BODY = [
    (1, '2', [(1, 'head_t', 5, []), (2, 'neck', 5, [3])]),           # 머리(원, 지름 = 목 → 정수리)
    (2, '1', [(3, 'neck', 4, [2, 6, 10]), (4, 'pelvis', 3, [13, 17])]),  # 몸통(뿌리)
    (3, '1', [(5, 'elb_r', 5, [8]), (6, 'neck', 4, [3])]),           # 오른 위팔
    (4, '1', [(7, 'wri_r', 5, []), (8, 'elb_r', 4, [5])]),           # 오른 아래팔
    (5, '1', [(9, 'elb_l', 5, [12]), (10, 'neck', 4, [3])]),         # 왼 위팔
    (6, '1', [(11, 'wri_l', 5, []), (12, 'elb_l', 4, [9])]),         # 왼 아래팔
    (7, '1', [(13, 'pelvis', 2, [4]), (14, 'kne_r', 5, [15])]),      # 오른 허벅지
    (8, '1', [(15, 'kne_r', 4, [14]), (16, 'ank_r', 5, [])]),        # 오른 정강이
    (9, '1', [(17, 'pelvis', 2, [4]), (18, 'kne_l', 5, [19])]),      # 왼 허벅지
    (10, '1', [(19, 'kne_l', 4, [18]), (20, 'ank_l', 5, [])]),       # 왼 정강이
]
# 틀 길이(가로 % 단위, 세로는 × 0.5625로 환산해 잼): 머리 지름 8.4, 몸통 11.2, 위팔·아래팔 7.0, 허벅지 8.0, 정강이 5.6
LEN = dict(head_t=8.4, spine=11.2, elb=7.0, wri=7.0, kne=8.0, ank=5.6)
# ID 범위: 앱 파일처럼 장·오브젝트·점 ID가 서로 겹치지 않게(11-02 v2 편집에서 연결 대상 점 ID가 오브젝트 ID와 같은
# 이음(목·팔꿈치)만 떨어졌다 — 원인 가설, 앱 확인 전).
FR0, AO0, PT0 = 5000, 1560000, 9680000
AO_STYLE = ('Color="-16777216" LayerId="0" ThicknessScale="{th}" ObjectScale="1.0" '
            'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0"')


def unit(v, prev):
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else prev


def scales(kps):
    """장마다 몸 크기(화소 / 틀 단위): 몸통·위팔·아래팔·허벅지·정강이 비의 중앙값, 9장 이동 평균(원근으로 커지고 작아짐은 따라감)."""
    out = []
    for kp in kps:
        neck, pel = (kp[LSHO, :2] + kp[RSHO, :2]) / 2, (kp[LHIP, :2] + kp[RHIP, :2]) / 2
        r = [np.linalg.norm(neck - pel) / LEN['spine']]
        for a, b, L in ((LSHO, LELB, LEN['elb']), (RSHO, RELB, LEN['elb']), (LELB, LWRI, LEN['wri']), (RELB, RWRI, LEN['wri']),
                        (LHIP, LKNE, LEN['kne']), (RHIP, RKNE, LEN['kne']), (LKNE, LANK, LEN['ank']), (RKNE, RANK, LEN['ank'])):
            r.append(np.linalg.norm(kp[a, :2] - kp[b, :2]) / L)
        out.append(np.median(r))
    out = np.array(out)
    return np.array([out[max(0, t - 4):t + 5].mean() for t in range(len(out))])


def joints(kp, s, prev=None, fs=None):
    """포즈 → 틀 길이 고정 관절 위치(화소). 방향만 포즈에서 가져온다. 머리는 몸통 방향을 따른다(얼굴 점 떨림 무시)."""
    prev = prev or {}
    neck, pel = (kp[LSHO, :2] + kp[RSHO, :2]) / 2, (kp[LHIP, :2] + kp[RHIP, :2]) / 2
    d = {}
    J = {'pelvis': pel}
    u = unit(neck - pel, prev.get('spine', np.array([0.0, -1.0])))
    d['spine'] = u
    fs = fs or {}
    J['neck'] = pel + u * LEN['spine'] * s * fs.get('spine', 1.0)
    J['head_t'] = J['neck'] + u * LEN['head_t'] * s
    for side, sho, elb, wri, hip, kne, ank in (('l', LSHO, LELB, LWRI, LHIP, LKNE, LANK), ('r', RSHO, RELB, RWRI, RHIP, RKNE, RANK)):
        for part, base, a, b in (('elb', 'neck', sho, elb), ('wri', f'elb_{side}', elb, wri),
                                 ('kne', 'pelvis', hip, kne), ('ank', f'kne_{side}', kne, ank)):
            name = f'{part}_{side}'
            v = unit(kp[b, :2] - kp[a, :2], prev.get(name, np.array([0.0, 1.0])))
            d[name] = v
            J[name] = J[base] + v * LEN[part] * s * fs.get(name, 1.0)
    return J, d


SEGS = dict(spine=((LSHO, RSHO), (LHIP, RHIP)), elb_l=(LSHO, LELB), wri_l=(LELB, LWRI), kne_l=(LHIP, LKNE), ank_l=(LKNE, LANK),
            elb_r=(RSHO, RELB), wri_r=(RELB, RWRI), kne_r=(RHIP, RKNE), ank_r=(RKNE, RANK))


def foreshorten(kps, S, lo=0.3):
    """조각마다 실측 길이 / (몸 크기 × 틀 길이)를 0.3–1로 자르고 5장 평균. 화면 쪽으로 향한 팔다리는 짧게(원근 단축), 늘이지는 않는다.
    (11-02 측정: 팔은 장의 20–31%가 틀 길이의 0.6 미만 — 고정 길이로 그리면 팔이 튀어나와 어색했다.)"""
    pt = lambda kp, i: kp[i, :2] if np.isscalar(i) else (kp[i[0], :2] + kp[i[1], :2]) / 2  # noqa: E731
    out = {}
    for name, (a, b) in SEGS.items():
        L = LEN[name.split('_')[0]]
        r = np.array([np.linalg.norm(pt(kp, b) - pt(kp, a)) / (S[t] * L) for t, kp in enumerate(kps)])
        r = np.clip(r, lo, 1.0)
        out[name] = np.array([r[max(0, t - 2):t + 3].mean() for t in range(len(r))])
    return [{k: v[t] for k, v in out.items()} for t in range(len(kps))]


def frame_xml(n, J, to_pct, thick='1.0'):
    out = [f'<Frame BackgroundColor="-1" ID="{FR0 + n}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
    for oid, typ, pts in BODY:
        out.append(f'<AO ID="{AO0 + oid}" TypeId="{typ}" DrawOrder="{AO0 + oid}" ' + AO_STYLE.format(th=thick) + '>')
        for i, (pid, name, fl, acs) in enumerate(pts):
            x, y = to_pct(J[name])
            out.append(f'<AP ID="{PT0 + pid}" Flags="{fl}" Index="{i}" X="{x:.4f}" Y="{y:.4f}">'
                       + ''.join(f'<AC ConnPtId="{PT0 + c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ''.join(out)


def build(pose, start, end, crop_y=0.0, h=None, name='stickman', thick='1.0', fore=False, const=True):
    W = pose['W']
    H = h or pose['H']
    res = pose['res'][start:end + 1]
    if any(r is None for r in res):
        raise SystemExit('구간 안에 사람이 없는 장이 있다 — 구간을 바꿀 것')
    kps = clean([r['kp'] for r in res])
    S = scales(kps)
    if const:   # 11-02: 앱 스틱맨 파일은 조각 길이가 장마다 같다(실제 4개 중앙 변화 0%). 우리 v2·v3는 75–90% 변해 여러 장에서 편집 연결이 깨졌다(추정).
        S = np.full(len(S), float(np.median(S)))
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - crop_y) / H)  # noqa: E731  화면 % (가로 폭·세로 높이 기준)
    F = foreshorten(kps, S) if fore else [None] * len(kps)
    frames, prev = [], None
    for i, kp in enumerate(kps):
        J, prev = joints(kp, S[i], prev, F[i])
        frames.append(frame_xml(i, J, to_pct, thick))
    # 앱이 내보내는 형식 그대로(머리글·한 줄). 11-02 사용자 앱 시험: v3 첫 장만(T2)은 편집 연결 정상, 같은 형식의 93장(T3)은
    # 조각이 떨어짐 → 형식이 아니라 여러 장일 때의 문제(원인 시험 중). 형식은 앱과 맞춰 둔다.
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>'
           f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">'
           + ''.join(frames) + '</Sequence>')
    return xml, kps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pose')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, required=True)
    ap.add_argument('--end', type=int, required=True)
    ap.add_argument('--crop-y', type=float, default=0.0, help='위 검은 띠 화소(16:9 화면 시작 행)')
    ap.add_argument('--h', type=float, default=0, help='16:9 화면 높이 화소(0이면 영상 높이)')
    ap.add_argument('--name', default='stickman')
    ap.add_argument('--fore', action='store_true', help='원근 단축 켜기(조각 길이가 장마다 바뀜 — 앱 편집 연결이 깨질 수 있음)')
    ap.add_argument('--var-scale', action='store_true', help='몸 크기를 장마다 바꿈(같은 이유로 기본 끔)')
    ap.add_argument('--thick', default='1.0', help='선 굵기 배율(앱 기본 스틱맨 1.0)')
    a = ap.parse_args()
    pose = json.load(open(a.pose, encoding='utf-8'))
    xml, _ = build(pose, a.start, a.end, a.crop_y, a.h or None, a.name, a.thick, a.fore, not a.var_scale)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    print('SFA', a.out, '장', a.end - a.start + 1)


if __name__ == '__main__':
    main()
