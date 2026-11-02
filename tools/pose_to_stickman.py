"""2D 포즈(COCO 17점) → 관절점 있는 스틱맨 SFA(24/24). 2단계 '인물 → 스틱맨' 갈래(docs/STAGE2-GENERATOR-DESIGN-2026-11-02.md §1).

구조(실제 스틱맨 SFA의 점 값·연결 방식을 따름 — 막고라 관절 스틱맨 관찰, 11-02):
- 몸통 T: 시작점 = 목(관절점 33), 끝점 = 골반(파란점 3, 뿌리)
- 위팔: 시작 = 팔꿈치(관절점 33), 끝 = 목에 붙음(5 ↔ 몸통 33)  /  아래팔: 시작 = 손목(9), 끝 = 팔꿈치(5 ↔ 위팔 33)
- 허벅지: 시작 = 무릎(33), 끝 = 골반(8 ↔ 몸통 3)  /  정강이: 시작 = 발목(9), 끝 = 무릎(5 ↔ 허벅지 33)
- 머리: 원(TypeId 2), 지름 양끝 = 목 쪽(5 ↔ 몸통 33) · 정수리 쪽(9)
- 점·오브젝트 ID는 모든 장에서 같고 연결(AC)도 모든 장에서 같다(앱 불변 조건, AGENTS.md). 무리(스틱맨 하나)마다 파란점 하나(사용자 11-02).

사용: python tools/pose_to_stickman.py pose.json 출력.sfa --start 298 --end 390 [--crop-y 27 --h 480] [--name 이름]
pose.json = {W, H, res: [장마다 None 또는 {kp: 17×[x,y,score]}]} (YOLO11-pose 추론 결과, 큰 사람 하나)
"""
import argparse
import json
import zipfile

import numpy as np

NOSE, LEYE, REYE, LEAR, REAR, LSHO, RSHO, LELB, RELB, LWRI, RWRI, LHIP, RHIP, LKNE, RKNE, LANK, RANK = range(17)


def clean(kps, min_score=0.3):
    """장 × 17 × 3 → 낮은 신뢰 점은 앞뒤 장에서 선형 보간, 그다음 3장 이동 평균(떨림 줄이기)."""
    a = np.array(kps, float)
    n = len(a)
    for j in range(17):
        good = a[:, j, 2] >= min_score
        if good.sum() == 0:
            continue
        idx = np.arange(n)
        for c in (0, 1):
            a[:, j, c] = np.interp(idx, idx[good], a[good, j, c])
    sm = a.copy()
    for t in range(n):
        lo, hi = max(0, t - 1), min(n, t + 2)
        sm[t, :, :2] = a[lo:hi, :, :2].mean(0)
    return sm


def joints(kp):
    """COCO 17점 → 스틱맨 관절(화소 좌표)."""
    m = lambda i, k: (kp[i, :2] + kp[k, :2]) / 2  # noqa: E731
    neck, pelvis = m(LSHO, RSHO), m(LHIP, RHIP)
    face = [kp[i, :2] for i in (NOSE, LEYE, REYE, LEAR, REAR) if kp[i, 2] >= 0.3] or [kp[NOSE, :2]]
    head_c = np.mean(face, 0)
    up = head_c - neck
    L = max(np.linalg.norm(up), 1e-3)
    r = max(0.55 * L, 0.18 * np.linalg.norm(neck - pelvis))
    head_bottom = neck + up / L * max(L - r, 0.2 * L)
    head_top = head_bottom + up / L * 2 * r
    return dict(neck=neck, pelvis=pelvis, lelb=kp[LELB, :2], lwri=kp[LWRI, :2], relb=kp[RELB, :2], rwri=kp[RWRI, :2],
                lkne=kp[LKNE, :2], lank=kp[LANK, :2], rkne=kp[RKNE, :2], rank=kp[RANK, :2], hb=head_bottom, ht=head_top)


# 오브젝트: (AO ID, TypeId, [(점 ID, 관절 이름, Flags, [연결 상대 점 ID])])
BODY = [
    (1, '1', [(10, 'neck', 33, [21, 41, 101]), (11, 'pelvis', 3, [61, 81])]),            # 몸통
    (2, '1', [(20, 'lelb', 33, [31]), (21, 'neck', 5, [10])]),                             # 왼 위팔
    (3, '1', [(30, 'lwri', 9, []), (31, 'lelb', 5, [20])]),                                # 왼 아래팔
    (4, '1', [(40, 'relb', 33, [51]), (41, 'neck', 5, [10])]),                             # 오른 위팔
    (5, '1', [(50, 'rwri', 9, []), (51, 'relb', 5, [40])]),                                # 오른 아래팔
    (6, '1', [(60, 'lkne', 33, [71]), (61, 'pelvis', 8, [11])]),                           # 왼 허벅지
    (7, '1', [(70, 'lank', 9, []), (71, 'lkne', 5, [60])]),                                # 왼 정강이
    (8, '1', [(80, 'rkne', 33, [91]), (81, 'pelvis', 8, [11])]),                           # 오른 허벅지
    (9, '1', [(90, 'rank', 9, []), (91, 'rkne', 5, [80])]),                                # 오른 정강이
    (10, '2', [(101, 'hb', 5, [10]), (102, 'ht', 9, [])]),                                 # 머리(원)
]


def frame_xml(n, J, to_pct, color='-16777216', thick='2.0'):
    out = [f'<Frame BackgroundColor="-1" ID="{n + 1}" Position="{n}"><LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>']
    for oid, typ, pts in BODY:
        out.append(f'<AO ID="{oid}" TypeId="{typ}" Color="{color}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{thick}" ObjectScale="1.0" '
                   'GlowRadius="0" GlowThickness="0" GlowColor="-1" GlowAlpha="0">')
        for k, (pid, name, fl, acs) in enumerate(pts):
            x, y = to_pct(J[name])
            out.append(f'<AP ID="{pid}" Flags="{fl}" Index="{k}" X="{x:.4f}" Y="{y:.4f}">' + ''.join(f'<AC ConnPtId="{c}"/>' for c in acs) + '</AP>')
        out.append('</AO>')
    out.append('</Frame>')
    return ''.join(out)


def build(pose, start, end, crop_y=0.0, h=None, name='stickman'):
    W = pose['W']
    H = h or pose['H']
    res = pose['res'][start:end + 1]
    if any(r is None for r in res):
        raise SystemExit('구간 안에 사람이 없는 장이 있다 — 구간을 바꿀 것')
    kps = clean([r['kp'] for r in res])
    to_pct = lambda p: (100 * p[0] / W, 100 * (p[1] - crop_y) / H)  # noqa: E731  화면 % (가로 폭·세로 높이 기준)
    frames = [frame_xml(i, joints(kp), to_pct) for i, kp in enumerate(kps)]
    xml = ("<?xml version='1.0' encoding='utf-8'?>\n"
           f'<Sequence Name="{name}" HeightWidthRatio="{H / W:.4f}" RatioX="16" RatioY="9" FrameCount="{len(frames)}" BackgroundColor="-1">\n'
           + '\n'.join(frames) + '\n</Sequence>\n')
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
    a = ap.parse_args()
    pose = json.load(open(a.pose, encoding='utf-8'))
    xml, _ = build(pose, a.start, a.end, a.crop_y, a.h or None, a.name)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(a.name + '.xml', xml)
    print('SFA', a.out, '장', a.end - a.start + 1)


if __name__ == '__main__':
    main()
