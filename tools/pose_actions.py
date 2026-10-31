"""정리된 포즈 추적(tools/pose_tracks.py)에서 짧은 구간별 동작 종류를 규칙으로 1차 추정한다(정답 없음, 추론값).

사용: python tools/pose_actions.py <tracks_all 폴더> <출력 csv> [--win 12] [--min-score 2.8]
- 대상: 몸점수_중앙 ≥ min-score(학습 선별 기준, pose_tracks.KEEP_SCORE) 인 추적, 길이 ≥ win.
- 몸 크기 = 어깨 가운데~엉덩이 가운데 거리(구간 중앙값). 속도는 몸 크기 / 프레임 단위.
- 점 위치는 3프레임 중앙값으로 다듬은 뒤 잰다(손목·발목 떨림이 속도로 잡혀 '공격'이 78%로 부풀었다).
- 구간(win 프레임, 절반씩 겹침)마다 지표:
  손발_최고속도(손목·발목 중 최대, 골반 기준 상대 속도), 골반_수평·수직 속도, 몸통_기울기(세로선과 각도),
  팔다리_뻗음(손목·발목이 골반에서 떨어진 최대 거리), 움직임_총량.
- 규칙(먼저 맞는 것): 쓰러짐(몸통 기울기 ≥ 60°) → 공격(손발 최고속도 ≥ 0.35 이고 뻗음 ≥ 1.1) →
  점프·공중(골반 수직 속도 ≥ 0.08) → 이동(골반 수평 속도 ≥ 0.06) → 대기(움직임 총량 < 0.03) → 기타 동작.
기준값은 첫 추정이다. 막기·회피·피격은 상대 정보가 있어야 해서 아직 나누지 않는다.
**검증 결과(GPT T02 89구간, 2026-10-22): 규칙과 GPT 일치 16/89(18%), '공격' 규칙 15개 중 실제 공격 3개 — 쓸 수 없다.**
대안: 3D로 올린 뒤 태그 붙은 모캡으로 학습한 동작 분류기를 쓰고, T02를 평가 정답으로 쓴다.
"""
import argparse
import csv
import glob
import os

import numpy as np

KEEP = 2.8


def windows(K, win):
    for s in range(0, len(K) - win + 1, win // 2):
        yield s, K[s:s + win]


def smooth(P):
    """3프레임 중앙값(관절 점 떨림 제거). 빈 점(NaN)은 그대로."""
    Q = P.copy()
    if len(P) >= 3:
        st = np.stack([P[:-2], P[1:-1], P[2:]])
        Q[1:-1] = np.nanmedian(st, 0)
    return Q


def feats(W):
    P = smooth(W[:, :17, :2])
    hip = (P[:, 11] + P[:, 12]) / 2
    sh = (P[:, 5] + P[:, 6]) / 2
    size = np.nanmedian(np.linalg.norm(sh - hip, axis=1))
    if not np.isfinite(size) or size < 5:
        return None
    rel = (P - hip[:, None]) / size
    ext = [9, 10, 15, 16]
    v = np.linalg.norm(np.diff(rel[:, ext], axis=0), axis=2)
    vmax = np.nanmax(np.nanmedian(np.sort(v, 0)[-3:], 0)) if np.isfinite(v).any() else np.nan
    hv = np.diff(hip, axis=0) / size
    torso = sh - hip
    ang = np.degrees(np.arctan2(np.abs(torso[:, 0]), -torso[:, 1]))  # 화면 y는 아래 → 똑바로 서면 0°
    reach = np.nanmax(np.linalg.norm(rel[:, ext], axis=2))
    tot = np.nanmean(np.linalg.norm(np.diff(rel, axis=0), axis=2))
    return {"손발_최고속도": vmax, "골반_수평": float(np.nanmedian(np.abs(hv[:, 0]))),
            "골반_수직": float(np.nanmax(np.abs(hv[:, 1]))) if np.isfinite(hv[:, 1]).any() else np.nan,
            "몸통_기울기": float(np.nanmedian(ang)), "팔다리_뻗음": float(reach), "움직임_총량": float(tot)}


def label(f):
    if f["몸통_기울기"] >= 60:
        return "쓰러짐"
    if f["손발_최고속도"] >= 0.35 and f["팔다리_뻗음"] >= 1.1:
        return "공격"
    if f["골반_수직"] >= 0.08:
        return "점프·공중"
    if f["골반_수평"] >= 0.06:
        return "이동"
    if f["움직임_총량"] < 0.03:
        return "대기"
    return "기타 동작"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks")
    ap.add_argument("out")
    ap.add_argument("--win", type=int, default=12)
    ap.add_argument("--min-score", type=float, default=KEEP)
    a = ap.parse_args()
    rows = []
    for f in sorted(glob.glob(os.path.join(a.tracks, "*", "*.npz"))):
        z = np.load(f)
        if z["quality"].ndim < 2:
            continue
        an, pid = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-4]
        for i, (L, q, st) in enumerate(zip(z["length"], z["quality"], z["start"])):
            if q[0] < a.min_score or L < a.win:
                continue
            for s, W in windows(z["kp"][i, :L], a.win):
                ft = feats(W)
                if ft is None or not all(np.isfinite(list(ft.values()))):
                    continue
                rows.append([an, pid, i, int(st) + s, a.win, label(ft)] + [round(v, 4) for v in ft.values()])
    cols = ["애니메이터", "post_id", "추적", "시작프레임", "길이", "동작"] + \
        ["손발_최고속도", "골반_수평", "골반_수직", "몸통_기울기", "팔다리_뻗음", "움직임_총량"]
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)
    from collections import Counter
    for an in sorted({r[0] for r in rows}):
        c = Counter(r[5] for r in rows if r[0] == an)
        print(an, sum(c.values()), dict(c.most_common()))


if __name__ == "__main__":
    main()
