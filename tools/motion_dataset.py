#!/usr/bin/env python3
"""글→동작 모델(MoMask, HumanML3D 형식) 추가 학습 자료 만들기: 애니 3D(nian41·나카무라) + 모캡(잊지 않게 섞는 자료).

사용: python tools/motion_dataset.py <momask 폴더> <애니 3D 폴더(lift_apply 출력)> <mocap_unified 폴더> <기준 관절 npy> <출력 폴더>
      [--mocap-max 4000] [--style "in anime style"]
출력(HumanML3D 배치): <출력>/new_joint_vecs/<id>.npy (프레임, 263), <출력>/texts/<id>.txt ("문장#토큰#0.0#0.0"),
      <출력>/train.txt·val.txt, <출력>/목록.csv(id, 출처, 문장, 프레임). 원본 유래라 저장소 밖(Drive·서버 임시)에만 둔다.

변환:
- 공통 18관절(pelvis spine neck head l/r_shoulder elbow wrist hip knee ankle toe) → SMPL 22관절 근사(척추 3·쇄골 2는 사이 보간).
  기준 관절 npy(MoMask가 만든 22관절 하나)로 뼈 길이를 맞춘다(process_file의 uniform_skeleton).
- 애니 3D: 카메라 좌표라 위 방향이 추적마다 다르다 → 추적 평균 (목 − 골반) 방향을 +y로 돌린다. 떨림(약 0.034 m/프레임²)을 줄이려고
  Savitzky–Golay(7, 2) 평활. 골반 기준(전역 이동 없음)이라 디딤발 고정으로 엉덩이 이동을 되살린다(낮은 발이 땅에 붙어 있다고 보고
  그 발의 수평 이동을 거꾸로 엉덩이에 더함). 23.976 → 20fps.
- 모캡: 30 → 20fps, y 위·전역 이동 그대로.
- 길이: 40–196프레임(20fps) 창으로 자른다(긴 추적은 절반 겹침).
- 문장(트리거): 애니 창은 동작 판정(data/tag_index.csv의 동작 행, 같은 영상·겹치는 구간)을 영어 문장으로 바꾸고 끝에 --style을 붙인다
  (예: "a person throws a kick, in anime style"). 판정이 없는 창은 "a person fights, in anime style".
  모캡은 mocap_index 설명(영어 원문)을 그대로 쓴다(트리거 없음 → 원래 사람 움직임 유지).
"""
import argparse
import csv
import glob
import os
import random
import re
import sys

import numpy as np
from scipy.signal import savgol_filter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
J18 = ["pelvis", "spine", "neck", "head", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
       "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle", "l_toe", "r_toe"]
I = {n: i for i, n in enumerate(J18)}
EN = {"대기": "stands in a fighting stance", "공격": "attacks", "공격_킥": "throws a kick", "공격_펀치": "throws a punch",
      "공격_무기": "swings a weapon", "공격_던지기": "throws the opponent", "공격_기타": "attacks", "막기·회피": "blocks and dodges",
      "이동": "dashes forward", "점프·공중": "jumps through the air", "피격": "gets hit and recoils", "쓰러짐·누움": "is knocked down to the ground"}  # "falls"는 하늘에서 떨어짐과 헷갈려 피한다


def to22(P):
    """[T,18,3] → [T,22,3] (SMPL 순서)."""
    g = lambda n: P[:, I[n]]
    lerp = lambda a, b, t: a + (b - a) * t
    pel, sp, nk = g("pelvis"), g("spine"), g("neck")
    out = [pel, g("l_hip"), g("r_hip"), lerp(pel, sp, 0.5), g("l_knee"), g("r_knee"), sp, g("l_ankle"), g("r_ankle"),
           lerp(sp, nk, 0.6), g("l_toe"), g("r_toe"), nk, lerp(nk, g("l_shoulder"), 0.45), lerp(nk, g("r_shoulder"), 0.45),
           g("head"), g("l_shoulder"), g("r_shoulder"), g("l_elbow"), g("r_elbow"), g("l_wrist"), g("r_wrist")]
    return np.stack(out, 1)


def upright(P):
    """추적 평균 (목 − 골반)을 +y로 돌린다."""
    up = np.nanmean(P[:, I["neck"]] - P[:, I["pelvis"]], 0)
    up /= np.linalg.norm(up) + 1e-9
    y = np.array([0.0, 1.0, 0.0])
    v, c = np.cross(up, y), float(up @ y)
    if np.linalg.norm(v) < 1e-8:
        R = np.eye(3) if c > 0 else np.diag([1, -1, -1])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx / (1 + c)
    return P @ R.T


def foot_lock_root(P):
    """골반 기준 움직임에 엉덩이 이동을 되살린다: 더 낮은 발목을 디딤발로 보고 그 발의 수평 이동을 거꾸로 더하고, 높이는 그 발을 바닥에 붙인다."""
    out = P.copy()
    off = np.zeros(3)
    for t in range(1, len(P)):
        a = I["l_ankle"] if P[t, I["l_ankle"], 1] < P[t, I["r_ankle"], 1] else I["r_ankle"]
        d = P[t, a] - P[t - 1, a]
        off -= np.array([d[0], 0.0, d[2]])
        out[t] += off
    # 위아래도 되살린다: 골반 기준이라 엉덩이 높이가 늘 같아서(3차 자료 117개 모두 높이 변화 0) 쪼그림·일어서기·착지가
    # '다리만 접힘'으로 배워졌다(2026-10-23 확인). 다리에서 가장 낮은 점(발목·발끝·무릎 — 무릎 꿇기는 무릎이 닿음)을 늘 바닥
    # (첫 프레임 높이)에 붙인다 — 두 발이 다 뜬 점프는 잃는다.
    low = P[:, [I[n] for n in ("l_ankle", "r_ankle", "l_toe", "r_toe", "l_knee", "r_knee")], 1].min(1)
    out[:, :, 1] -= (low - low[0])[:, None]
    return out


def quality(P):
    """망가진 2D→3D 창 거르기용: (가속 95%, 어깨-골반 비틀림 90%) — 미터/프레임², 도."""
    acc = np.linalg.norm(np.diff(P, 2, axis=0), axis=-1)
    sh = P[:, I["l_shoulder"]] - P[:, I["r_shoulder"]]
    hp = P[:, I["l_hip"]] - P[:, I["r_hip"]]
    sh[:, 1] = 0
    hp[:, 1] = 0
    c = (sh * hp).sum(-1) / (np.linalg.norm(sh, axis=-1) * np.linalg.norm(hp, axis=-1) + 1e-9)
    return float(np.percentile(acc, 95)), float(np.percentile(np.degrees(np.arccos(np.clip(c, -1, 1))), 90))


def resample(P, src, dst):
    n = int((len(P) - 1) * dst / src) + 1
    t = np.arange(n) * src / dst
    i0 = np.floor(t).astype(int).clip(0, len(P) - 1)
    i1 = (i0 + 1).clip(0, len(P) - 1)
    f = (t - i0)[:, None, None]
    return P[i0] * (1 - f) + P[i1] * f


def windows(n, lo=40, hi=196):
    if n < lo:
        return []
    if n <= hi:
        return [(0, n)]
    out, s = [], 0
    while s + lo <= n:
        out.append((s, min(n, s + hi)))
        if s + hi >= n:
            break
        s += hi // 2
    return out


def anime_labels():
    lab = {}
    p = os.path.join(ROOT, "data", "tag_index.csv")
    for r in csv.DictReader(open(p, encoding="utf-8")):
        if r["분류"] == "동작" and r["태그"] in EN:
            lab.setdefault(r["post_id"], []).append((int(r["시작"]), int(r["끝"]), r["태그"]))
    return lab


def ext_captions(path):
    """Codex 등이 만든 동작 문장 csv(출처,애니메이터,post_id,시작,끝,…,caption_en,caption_en_2,확신) → {post_id: [(시작, 끝, [문장], 확신)]}."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        caps = [c.strip().rstrip(".") for c in (r.get("caption_en"), r.get("caption_en_2")) if c and c.strip()]
        if caps and r.get("확신") != "낮음":
            out.setdefault(r["post_id"], []).append((int(r["시작"]), int(r["끝"]), caps))
    return out


def caption(labels, pid, a, b, style):
    hit = [t for s, e, t in labels.get(pid, []) if s <= b and e >= a]
    sub = [t for t in hit if t.startswith("공격_")]
    seq = []
    for t in (sub + [t for t in hit if not t.startswith("공격")] + [t for t in hit if t == "공격"]):
        if EN[t] not in seq:
            seq.append(EN[t])
    body = " and then ".join(seq[:3]) if seq else "fights"
    return f"a person {body}, {style}", bool(seq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("momask")
    ap.add_argument("anim")
    ap.add_argument("mocap")
    ap.add_argument("ref")
    ap.add_argument("out")
    ap.add_argument("--mocap-max", type=int, default=4000)
    ap.add_argument("--style", default="in anime style")
    ap.add_argument("--captions", help="동작 설명 문장 csv(예: data/style_kb/ai_results/codex_action_captions_*.csv). 겹치는 창은 이 문장을 쓴다")
    ap.add_argument("--max-acc", type=float, default=0.17, help="가속 95%가 이보다 크면 버림(측정: 중앙 0.086, 상위 25% 0.171)")
    ap.add_argument("--max-twist", type=float, default=45.0, help="어깨-골반 비틀림 90%가 이보다 크면 버림(상위 10%)")
    ap.add_argument("--extra-mocap", help="꼭 넣을 모캡 클립 csv(자료,클립,문장(|로 여럿),반복) — 예: data/mocap/extra_landing_2026-10-23.csv. "
                    "짧은 클립은 마지막 자세를 이어 붙여 2.2초로 채운다")
    ap.add_argument("--min-stand-hip", type=float, default=0.7,
                    help="애니: 서기·걷기·타격 문장인데 엉덩이 높이 중앙값이 이보다 낮으면(m) 문장-자세 불일치로 버림(2026-10-23: 'stands upright'인데 0.15–0.6m인 창이 모델에 '서기=낮음'을 가르침). 0이면 끔")
    ap.add_argument("--keep-generic", action="store_true", help="판정 문장이 없는 애니 창('fights')도 쓴다(기본: 뺀다)")
    a = ap.parse_args()
    sys.path.insert(0, a.momask)
    import utils.motion_process as mp
    from common.skeleton import Skeleton
    from utils.paramUtil import t2m_kinematic_chain, t2m_raw_offsets
    import torch
    ref = np.load(a.ref)
    sk = Skeleton(torch.from_numpy(t2m_raw_offsets), t2m_kinematic_chain, "cpu")
    mp.tgt_offsets = sk.get_offsets_joints(torch.from_numpy(ref[0]).float())
    mp.n_raw_offsets, mp.kinematic_chain = torch.from_numpy(t2m_raw_offsets), t2m_kinematic_chain
    mp.face_joint_indx, mp.fid_r, mp.fid_l = [2, 1, 17, 16], [8, 11], [7, 10]
    mp.l_idx1, mp.l_idx2 = 5, 8
    for d in ("new_joint_vecs", "texts"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    rows, n = [], 0

    nbad = [0]

    def save(J22, cap, src):
        nonlocal n
        try:
            feat = mp.process_file(J22.astype(np.float64), 0.002)[0]
        except Exception as e:  # 이상한 창(뒤집힘 등)은 버린다
            print("버림", src, e)
            return
        if not np.isfinite(feat).all() or not (40 <= len(feat) < 200):
            return
        c0 = (cap if isinstance(cap, list) else [cap])[0]
        low_word = re.search(r"kneel|crouch|squat|on the ground|lies|lying|sits|sitting|stands? up\b|gets? up|rises|falls?|knocked", c0)
        stand_word = re.search(r"stand|walk|run|step|punch|kick|strike|swing", c0)
        hip = float(np.median(feat[:, 3]))
        # 낮은 자세 단어가 없으면 서 있는 몸으로 본다: 서기·걷기·타격 문장은 min-stand-hip, 팔 동작만 적힌 문장은 0.6m 미만이면 불일치
        if (a.min_stand_hip and "anime style" in c0 and not low_word
                and hip < (a.min_stand_hip if stand_word else min(a.min_stand_hip, 0.6))):
            nbad[0] += 1
            return
        i = f"{n:06d}"
        n += 1
        np.save(os.path.join(a.out, "new_joint_vecs", i + ".npy"), feat.astype(np.float32))
        caps = cap if isinstance(cap, list) else [cap]
        with open(os.path.join(a.out, "texts", i + ".txt"), "w", encoding="utf-8") as fh:
            for c in caps:  # 문장이 여럿이면 줄마다(학습 때 하나를 무작위로 고른다)
                fh.write(f"{c}#{' '.join(w + '/OTHER' for w in c.replace(',', '').split())}#0.0#0.0\n")
        cap = caps[0]
        rows.append((i, src, cap, len(feat)))

    labels = anime_labels()
    ext = ext_captions(a.captions)
    na = nl = nq = ne = 0
    used = set()
    for an in ("nian41", "yutaka_nakamura"):  # 보충 애니메이터 몸동작은 쓰지 않는다(AGENTS)
        for f in sorted(glob.glob(os.path.join(a.anim, an, "*.npz"))):
            d = np.load(f)
            pid, fps = os.path.basename(f)[:-4], float(d["fps"])
            for k in range(len(d["length"])):
                Y = d["y3d"][k, : int(d["length"][k])]
                ok = np.isfinite(Y).all((1, 2))
                # 이어진 유효 구간마다
                idx = np.flatnonzero(np.diff(np.r_[0, ok.astype(int), 0]))
                for s, e in zip(idx[::2], idx[1::2]):
                    P = Y[s:e]
                    if len(P) < (40 if ext else 48):
                        continue
                    P = upright(P)
                    P = savgol_filter(P, 7, 2, axis=0) if len(P) >= 7 else P
                    if not ext:  # 문장 창 방식은 창마다 품질을 따로 잰다(구간 전체로 버리면 문장 붙은 좋은 부분도 버려진다)
                        acc95, tw90 = quality(P)
                        if acc95 > a.max_acc or tw90 > a.max_twist:
                            nq += 1
                            continue
                    P = foot_lock_root(P)
                    P = resample(P, fps, 20)
                    f0 = int(d["start"][k]) + s
                    if ext:  # 문장이 붙은 판정 구간(12프레임)을 가운데 둔 짧은 창 — 문장과 동작이 정확히 맞게
                        for s0, e0, cs in ext.get(pid, []):
                            c0 = (s0 + e0) / 2 - f0                     # 애니 프레임 → 이 구간 안 위치
                            n20 = len(P)
                            if n20 < 44 or not (0 <= c0 * 20 / fps < n20):
                                continue
                            w0 = int(round(c0 * 20 / fps)) - 22          # 판정 구간 가운데 앞뒤 1.1초(20fps 44프레임)
                            w0 = min(max(w0, 0), n20 - 44)                # 구간 끝에 걸리면 안쪽으로 민다
                            w1 = w0 + 44
                            acc95, tw90 = quality(P[w0:w1])
                            if acc95 > a.max_acc or tw90 > a.max_twist:
                                nq += 1
                                continue
                            key = (pid, s0)
                            if key in used:  # 같은 판정 구간을 여러 추적이 덮으면 처음 것만(같은 장면 다른 인물 섞임 방지)
                                continue
                            used.add(key)
                            save(to22(P[w0:w1]), [f"{c}, {a.style}" for c in cs], f"{an}:{pid}:{s0}-{e0}")
                            na += 1
                            ne += 1
                            nl += 1
                        continue
                    for w0, w1 in windows(len(P)):
                        a0, a1 = f0 + int(w0 * fps / 20), f0 + int(w1 * fps / 20)
                        hit = [c for s0, e0, c in ext.get(pid, []) if s0 <= a1 and e0 >= a0]
                        if hit:  # 구체적 동작 문장(겹치는 판정 묶음 중 첫 것) + 트리거
                            cap, has = [f"{c}, {a.style}" for c in hit[0]], True
                            ne += 1
                        else:
                            cap, has = caption(labels, pid, a0, a1, a.style)
                        if not has and not a.keep_generic:
                            continue
                        save(to22(P[w0:w1]), cap, f"{an}:{pid}:{a0}-{a1}")
                        na += 1
                        nl += has
    print("문장-자세 불일치로 버린 애니 창", nbad[0])
    print("애니 창", na, "판정 문장", nl, "외부 문장", ne, "품질로 버린 구간", nq)
    # 모캡(잊지 않게 섞기): 공격·피격·점프·방어·구르기·달리기 위주, 걷기·감정 표현은 적게
    desc = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "mocap", "mocap_index_2026-10-21.csv"), encoding="utf-8-sig")):
        desc[(r["자료"], r["클립"])] = (r["설명"], r["태그"])
    pri = ("공격", "피격·넘어짐", "점프·공중", "방어·회피", "구르기·바닥", "달리기", "던지기·잡기")
    cand = []
    for src in ("cmu", "amass", "mixamo", "lafan1", "bandai"):
        p = os.path.join(a.mocap, src + ".npz")
        if not os.path.exists(p):
            continue
        d = np.load(p, allow_pickle=True)
        for k, c in enumerate(d["clip"]):
            ds, tg = desc.get((src, str(c)), ("", ""))
            if not ds:
                continue
            w = 3 if any(t in tg for t in pri) else 1
            cand.append((w, src, k, ds))
    random.Random(0).shuffle(cand)
    cand.sort(key=lambda x: -x[0])
    cache, nm = {}, 0
    for w, src, k, ds in cand:
        if nm >= a.mocap_max:
            break
        if src not in cache:  # npz 항목은 읽을 때마다 압축을 푼다 → 한 번만 풀어 배열로 들고 있는다
            z = np.load(os.path.join(a.mocap, src + ".npz"), allow_pickle=True)
            cache[src] = {k: z[k] for k in ("pos", "start", "length", "clip", "fps")}
        d = cache[src]
        P = d["pos"][int(d["start"][k]): int(d["start"][k]) + int(d["length"][k])].astype(np.float64)
        P = resample(P, float(d["fps"]), 20)
        for w0, w1 in windows(len(P))[:2]:
            save(to22(P[w0:w1]), "a person " + ds.strip().rstrip("."), f"{src}:{d['clip'][k]}")
            nm += 1
    print("모캡 창", nm)
    if a.extra_mocap:  # 무작위 뽑기에서 빠진 동작(착지 등)을 손으로 쓴 문장과 함께 넣는다(2026-10-23: 착지 클립 19개가 3차 자료에 0개)
        ne2 = 0
        for r in csv.DictReader(open(a.extra_mocap, encoding="utf-8-sig")):
            src = r["자료"]
            if src not in cache:
                z = np.load(os.path.join(a.mocap, src + ".npz"), allow_pickle=True)
                cache[src] = {k: z[k] for k in ("pos", "start", "length", "clip", "fps")}
            d = cache[src]
            ks = [k for k, c in enumerate(d["clip"]) if str(c) == r["클립"]]
            if not ks:
                print("없는 클립", src, r["클립"])
                continue
            k = ks[0]
            P = d["pos"][int(d["start"][k]): int(d["start"][k]) + int(d["length"][k])].astype(np.float64)
            P = resample(P, float(d["fps"]), 20)
            if len(P) < 44:
                P = np.concatenate([P, np.repeat(P[-1:], 44 - len(P), 0)])
            caps = [c.strip() for c in r["문장"].split("|") if c.strip()]
            for _ in range(int(r.get("반복") or 1)):
                for w0, w1 in windows(len(P)):
                    save(to22(P[w0:w1]), caps, f"{src}:{r['클립']}")
                    ne2 += 1
        print("지정 모캡 창", ne2)
    ids = [r[0] for r in rows]
    random.Random(1).shuffle(ids)
    nv = max(1, len(ids) // 20)
    open(os.path.join(a.out, "val.txt"), "w").write("\n".join(ids[:nv]) + "\n")
    open(os.path.join(a.out, "train.txt"), "w").write("\n".join(ids[nv:]) + "\n")
    with open(os.path.join(a.out, "목록.csv"), "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows([("id", "출처", "문장", "프레임")] + rows)
    print("합계", len(rows), "학습", len(ids) - nv, "검증", nv)


if __name__ == "__main__":
    main()
