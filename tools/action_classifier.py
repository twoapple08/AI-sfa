"""3D 포즈 동작 분류기: 태그 붙은 모캡으로 학습하고, 애니 3D(tools/lift_apply.py 출력)에 적용해 GPT T02 판정과 비교한다.

사용: python tools/action_classifier.py <mocap_unified 폴더> <mocap 목록 csv> <애니 3D 폴더> <T02 목록 csv> <T02 GPT csv> <출력 json>
- 특징(방향과 무관): 창(24프레임, 30fps 기준)마다 관절 쌍 거리(키로 정규화) 153개의 평균·표준편차,
  손목·발목·골반 속도(키/프레임)의 평균·최대, 몸 펼침(전체 관절의 골반 거리 평균) 변화량.
  애니 3D는 카메라 좌표라 위아래를 믿을 수 없어 높이·중력 방향 특징은 쓰지 않는다.
- 모캡 라벨: 목록 csv의 키워드 태그 → 공격 / 이동(걷기·달리기) / 점프·공중 / 쓰러짐·누움(피격·넘어짐, 구르기·바닥) / 기타(춤·던지기·감정 표현).
  태그는 클립 단위(대략값)라 창 라벨은 약하다(약지도).
- 모캡 창의 70%에 2·3프레임 유지를 넣고 전체에 1cm 떨림을 더한다(애니의 정지·한 번에 건너뛰기와 3D 올리기 떨림 맞추기, HOLD_AUG=0으로 끔).
- 분류기: 로지스틱 회귀(표준화). 클래스별 표본을 맞춘다.
- 평가: T02 시트(GPT 판정)와 같은 구간의 애니 3D 창을 찾아 예측과 비교. GPT '대기'는 움직임 총량 기준(분류기 밖)으로 따로 본다.
"""
import csv
import glob
import json
import os
import sys
from collections import Counter

import numpy as np

WIN = 24
PAIRS = [(i, j) for i in range(18) for j in range(i + 1, 18)]
PI, PJ = np.array([p[0] for p in PAIRS]), np.array([p[1] for p in PAIRS])
HOLD_AUG = os.environ.get("HOLD_AUG", "1") == "1"  # 모캡 창에 정지(2·3프레임 유지)·떨림을 넣는다


def label_of(tags):
    t = set(tags.split(";")) if tags else set()
    if "공격" in t:
        return "공격"
    if "피격·넘어짐" in t or "구르기·바닥" in t:
        return "쓰러짐·누움"
    if "점프·공중" in t:
        return "점프·공중"
    if t & {"걷기", "달리기"}:
        return "이동"
    if t & {"춤", "던지기·잡기"}:
        return "기타"
    return None


def feats(P, fps):
    """P [T,18,3] 미터 → 특징 벡터. 30fps 기준으로 속도를 맞춘다."""
    h = np.nanmedian(np.linalg.norm(P[:, 3] - (P[:, 14] + P[:, 15]) / 2, axis=1))
    if not np.isfinite(h) or h < 0.3:
        return None
    D = np.linalg.norm(P[:, PI] - P[:, PJ], axis=2) / h
    v = np.linalg.norm(np.diff(P[:, [0, 8, 9, 14, 15]], axis=0), axis=2) / h * (fps / 30)
    spread = np.linalg.norm(P - P[:, :1], axis=2).mean(1) / h
    return np.concatenate([D.mean(0), D.std(0), v.mean(0), v.max(0), [spread.max() - spread.min(), v.mean()]])


def mocap_windows(src, index, per_class=4000, seed=0):
    rng = np.random.default_rng(seed)
    tags = {(r["자료"], r["클립"]): r["태그"] for r in csv.DictReader(open(index, encoding="utf-8"))}
    pool = {}
    for p in sorted(glob.glob(os.path.join(src, "*.npz"))):
        s = os.path.basename(p)[:-4]
        z = np.load(p)
        for st, ln, nm in zip(z["start"], z["length"], z["clip"]):
            lab = label_of(tags.get((s, str(nm)), ""))
            if lab and ln >= WIN:
                pool.setdefault(lab, []).append((p, int(st), int(ln)))
    X, Y = [], []
    cache = {}
    for lab, clips in pool.items():
        for _ in range(per_class):
            p, st, ln = clips[rng.integers(len(clips))]
            if p not in cache:
                cache[p] = np.load(p)["pos"]
            o = st + rng.integers(0, ln - WIN + 1)
            P = cache[p][o:o + WIN].astype(np.float32)
            if HOLD_AUG and rng.random() < 0.7:  # 애니처럼 2·3프레임씩 같은 그림 유지(한 번에 건너뛰는 속도 모양을 맞춘다)
                k = rng.choice([2, 3])
                P = P[(np.arange(WIN) // k) * k]
            if HOLD_AUG:
                P = P + rng.normal(0, 0.01, P.shape).astype(np.float32)  # 3D 올리기 떨림 흉내(1cm)
            f = feats(P, 30)
            if f is not None and np.isfinite(f).all():
                X.append(f)
                Y.append(lab)
    return np.array(X), np.array(Y), {k: len(v) for k, v in pool.items()}


def train(X, Y):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced"))
    m.fit(X, Y)
    return m


def anime_window(ani_dir, an, pid, start, length):
    """T02 구간(원 영상 프레임 start, 길이)과 겹치는 애니 3D 추적 구간을 찾아 WIN 프레임 창을 만든다."""
    p = os.path.join(ani_dir, an, pid + ".npz")
    if not os.path.exists(p):
        return None
    z = np.load(p)
    fps = float(z["fps"]) or 24
    for Y, st, L in zip(z["y3d"], z["start"], z["length"]):
        if st <= start and start + length <= st + L:
            c = start - st + length // 2
            n = int(round(WIN * fps / 30))
            a = max(0, c - n // 2)
            seg = Y[a:a + n]
            seg = seg[np.isfinite(seg).all((1, 2))]
            if len(seg) >= n // 2:
                return feats(seg, fps)
    return None


def main():
    src, index, ani, t02_list, t02_gpt, out = sys.argv[1:7]
    X, Y, pool = mocap_windows(src, index)
    print("모캡 클립 수", pool, "창", Counter(Y))
    # 모캡 안에서 클립 분리 없이 간단 검증(약지도라 참고값)
    idx = np.random.default_rng(1).permutation(len(X))
    cut = int(len(X) * 0.8)
    m = train(X[idx[:cut]], Y[idx[:cut]])
    acc = float((m.predict(X[idx[cut:]]) == Y[idx[cut:]]).mean())
    m = train(X, Y)
    lst = {r["시트"]: r for r in csv.DictReader(open(t02_list, encoding="utf-8-sig"))}
    gpt = {r["시트"]: r["동작"] for r in csv.DictReader(open(t02_gpt, encoding="utf-8-sig"))}
    rows = []
    for k, r in lst.items():
        f = anime_window(ani, r["애니메이터"], r["post_id"], int(r["시작프레임"]), int(r["길이"]))
        if f is None or not np.isfinite(f).all() or k not in gpt:
            continue
        rows.append((k, gpt[k], m.predict([f])[0], float(f[-1])))
    comp = [r for r in rows if r[1] in ("공격", "이동", "점프·공중", "쓰러짐·누움", "기타")]
    hit = sum(1 for r in comp if r[1] == r[2])
    conf = Counter((r[1], r[2]) for r in rows)
    res = {"mocap_windows": dict(Counter(Y)), "mocap_holdout_acc_weak": round(acc, 3),
           "t02_matched": len(rows), "t02_comparable": len(comp), "t02_agree": hit,
           "confusion_gpt_to_pred": {f"{a}→{b}": v for (a, b), v in conf.most_common()},
           "idle_motion_by_gpt": {g: round(float(np.median([r[3] for r in rows if r[1] == g])), 4)
                                  for g in sorted({r[1] for r in rows})}}
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
