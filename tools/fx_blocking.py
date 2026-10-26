#!/usr/bin/env python3
"""움직임 시험용 폭발 블로킹(움직임만 잡은 거친 밑그림) 애니메이션 — 나카무라 실측 타이밍 (2026-10-26).

목적: AI가 정한 움직임(덩어리 크기·위치·타이밍)을 LoRA 그림→그림으로 장마다 나카무라 화풍으로 다시 그릴 수 있는지 본다.
나카무라 영상을 넣으면 이미 화풍이 있어 시험이 안 되므로, 화풍 없는 단순한 그림(울퉁불퉁한 원 겹)을 만든다.

실측값(파일에서 읽음):
- data/p3/fx_timing_2026-10-22.json 'explosion'(나카무라 폭발 80개): 길이 중앙 15장(사분위 7–25), 정점까지 중앙 6장(2–16),
  정점 면적 화면의 22.5%(12.4–32.8%), 갈라짐(덩어리 증가) 중앙 4번, 그림 유지 1장 57%·2장 31%·3장 5%(4장 이상은 뺌).
  밝기 곡선이 수명 내내 거의 평평(V 165–175) → 서서히 어두워지지 않고 끝 몇 장에서 사라짐.
- data/p4/nakamura_debris_rhythm_2026-10-21.json '폭발 파편'(31구간): 정점 속도 화면 높이의 1.43%/장, 정점 뒤 속도 반감 3장,
  그림 유지 비율 0(매 장 움직임), 최대 덩어리 수 중앙 44.
--sample을 주면 길이·정점·면적을 사분위 범위 안에서 시드로 뽑는다(없으면 중앙값).
가정(실측 아님): 면적 곡선 모양(빠르게 커져 정점, 이후 거의 유지하며 갈라짐 — 실측 평균 곡선은 여러 폭발이 섞여 평평해서 못 씀),
  무게중심 이동(실측 중앙 4.8%/장은 모양 변화가 섞인 값이라 그대로 안 쓰고, 갈라진 조각이 흩어지는 움직임으로만 냄).
출력: <폴더>/f000.png …(장마다 한 장, 걸이 장은 같은 그림 복사) + timing.json(장별 그림 번호·실측 출처).
사용: python tools/fx_blocking.py <출력 폴더> [--seed 3] [--sample]
"""
import argparse
import json
import os

import cv2
import numpy as np

W, H = 1344, 768
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "data/p3/fx_timing_2026-10-22.json")
DEBRIS = os.path.join(ROOT, "data/p4/nakamura_debris_rhythm_2026-10-21.json")


def lumpy(cx, cy, r, phase, harm, n=360):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rr = r * (1 + sum(a * np.sin(k * t + p + phase * (0.3 + 0.1 * k)) for k, a, p in harm))
    return np.stack([cx + rr * np.cos(t), cy + rr * np.sin(t) * 0.85], 1).astype(np.int32)


def holds(n, dist, rng):
    """그림 유지 길이(1·2·3장)를 실측 비율로 뽑아 장별 그림 번호를 만든다."""
    ks = [1, 2, 3]
    p = np.array([dist["1s"], dist["2s"], dist["3s"]]); p /= p.sum()
    ids, d = [], 0
    while len(ids) < n:
        ids += [d] * int(rng.choice(ks, p=p)); d += 1
    return ids[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--orbit", type=float, default=0.0,
                    help="폭발 중심을 도는 카메라(2D 시차): 전체 길이 동안 가까운 빌딩이 옮겨 가는 거리(화면폭 비). 0이면 고정. 음수면 반대 방향")
    ap.add_argument("--sample", action="store_true", help="길이·정점·면적을 실측 사분위 안에서 뽑기(없으면 중앙값)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    ex = json.load(open(FX, encoding="utf-8"))["types"]["explosion"]
    db = json.load(open(DEBRIS, encoding="utf-8"))["summary"]["폭발 파편"]
    pick = (lambda s: rng.uniform(*s["사분위"])) if a.sample else (lambda s: s["중앙"])
    n = max(5, int(round(pick(ex["길이(프레임)"]))))
    tp = int(np.clip(round(pick(ex["정점까지(프레임)"])), 1, n - 2))
    area = pick(ex["정점면적(화면비)"])
    splits = int(round(ex["갈라짐(덩어리 증가 횟수)"]["중앙"]))
    Rp = np.sqrt(area * W * H / (0.85 * np.pi))  # 정점 바깥 덩어리 반지름(면적 = 화면비)
    v0, half = db["peak_speed_h_median"] * H, db["half_after_peak_frames_p10_50_90"][1]
    ndeb = int(db["blob_count_max_median"])
    draw_of = holds(n, ex["그림유지"], rng)

    harm = [(k, rng.uniform(0.04, 0.12) / (1 + 0.15 * k), rng.uniform(0, 6.3)) for k in (3, 5, 7, 9, 13)]
    # 빌딩 실루엣: 깊이 3층(먼 0.35·중간 1.0·가까운 1.8 — 폭발은 중간층 깊이). 고정 카메라면 중간층만 그린다
    # 도는 카메라(2026-10-26 사용자 제안): 3D 없이 층마다 다른 속도로 옆으로 밀어 시차를 낸다. 폭발과 같은 깊이(중간층)는 화면에서 거의 안 움직이고,
    # 먼 층은 반대로 조금, 가까운 층은 크게 움직인다 → 폭발 둘레를 도는 것처럼 보임. 층마다 화면 2배 폭을 만들어 밀어도 비지 않게.
    depths = [(0.35, (40, 22, 14), (60, 180)), (1.0, (25, 15, 10), (120, 360)), (1.8, (12, 8, 6), (90, 230))] if a.orbit else \
             [(1.0, (25, 15, 10), (120, 360))]
    city = []
    for dep, colb, (hmin, hmax) in depths:
        x = -W if a.orbit else 0  # 고정 카메라는 이전과 같은 난수 순서(같은 블로킹)
        while x < (2 * W if a.orbit else W):
            w = int(rng.integers(60, 160) * dep ** 0.5); h = int(rng.integers(hmin, hmax))
            gap = int(rng.integers(0, 20) * dep) if dep <= 1.0 else int(rng.integers(120, 420))  # 가까운 층은 드문드문(높고 빽빽하면 폭발을 다 가렸다)
            city.append((dep, colb, x, H - h, x + w, H)); x += w + gap
    cx, cy = W * 0.52, H * 0.55
    # 갈라진 조각: 정점 뒤 splits번에 걸쳐 하나씩 떨어져 나와 흩어짐
    pieces = [(rng.uniform(0, 2 * np.pi), rng.uniform(0.35, 0.55), [(k, a_ * 1.3, p) for k, a_, p in harm]) for _ in range(splits)]
    deb = [(rng.uniform(0, 2 * np.pi), rng.uniform(0.6, 1.4), rng.uniform(3, 7)) for _ in range(ndeb)]
    layers = [(1.0, (30, 25, 150)), (0.82, (20, 90, 235)), (0.62, (60, 200, 255)), (0.4, (225, 250, 255))]  # BGR 바깥 → 심

    imgs = {}
    if a.orbit:  # 카메라가 움직이는 동안 같은 그림을 두 장 쓰면 배경이 멈춘다 → 폭발 모양만 유지하고 장마다 그린다
        shape_of = draw_of
        draw_of = list(range(n))
    else:
        shape_of = draw_of
    for d in sorted(set(draw_of)):
        f = draw_of.index(d)  # 그림이 처음 나오는 장 시각
        fc = f  # 카메라 시각(도는 카메라면 장마다), 폭발 모양은 그림 유지 규칙의 시각
        f = shape_of.index(shape_of[fc])
        g = (f + 1) / (tp + 1)
        R = Rp * (g ** 0.7 if f < tp else 1.0 + 0.04 * (f - tp))  # 가정: 빠르게 커져 정점, 뒤로 거의 유지
        post = max(0, f - tp) / max(1, n - 1 - tp)  # 정점 뒤 진행 0→1
        alpha = 1.0 if f < n - 3 else (n - f) / 4  # 밝기 평평 → 끝 3장에서만 사라짐
        img = np.zeros((H, W, 3), np.uint8); img[:] = (70, 30, 15)
        cam = a.orbit * W * (fc / max(1, n - 1) - 0.5)  # 카메라 옆 이동(중간층 기준 0)
        near = [c for c in city if c[0] > 1.0]
        for dep, colb, x0, y0, x1, y1 in city:
            if dep > 1.0:
                continue  # 가까운 층은 폭발 위에 나중에 그린다
            dx = int(round(-cam * (dep - 1.0) / 0.8))
            cv2.rectangle(img, (x0 + dx, y0), (x1 + dx, y1), colb, -1)
        # 갈라짐: 조각 j는 정점 뒤 j/splits 시점에 큰 덩어리 안에서 작게 나와 커지며 멀어진다. 큰 덩어리는 이어서 조금씩 줄어든다
        # (조각이 나올 때마다 한 번에 12%씩 줄이고 전체는 4%씩 키웠더니 크기가 줄고-커지고를 반복해 바운스처럼 보였다, 2026-10-26 사용자)
        main_r = R * (1 - 0.12 * splits * post)
        blobs = [(cx, cy, main_r, harm)]
        for j in range(splits):
            age = post * splits - j  # 0에서 나옴, 1 = 다음 조각 나올 때
            if f <= tp or age <= 0:
                continue
            ang, sz, hh = pieces[j]
            k = min(1.0, age)
            dist = R * (0.3 + 0.35 * k + 0.3 * post)
            blobs.append((cx + dist * np.cos(ang), cy + dist * np.sin(ang) * 0.85, R * sz * k * (1 - 0.3 * post), hh))
        for s, col in layers:
            core = s < 0.5
            ss = s * (1.0 if f <= tp else max(0.3, 1 - post))  if core else s  # 심은 정점 뒤 줄어듦
            ov = img.copy()
            for bx, by, br, hh in blobs:
                cv2.fillPoly(ov, [lumpy(bx, by, br * ss, f * 0.4, hh)], col, cv2.LINE_AA)
            img = cv2.addWeighted(ov, alpha, img, 1 - alpha, 0)
        if f >= tp - 1:  # 파편: 정점 무렵 가장자리에서 튀어나가 속도 반감(실측)
            t = f - (tp - 1)
            for ang, sp, size in deb:
                dist = R * 0.85 + v0 * sp * half / np.log(2) * (1 - 0.5 ** (t / half)) * 3
                p = (int(cx + dist * np.cos(ang)), int(cy + dist * np.sin(ang) * 0.85))
                cv2.circle(img, p, int(size), (60, 160, 255), -1, cv2.LINE_AA)
        for dep, colb, x0, y0, x1, y1 in near:  # 가까운 빌딩이 폭발 앞을 지나가며 가림
            dx = int(round(-cam * (dep - 1.0) / 0.8))
            cv2.rectangle(img, (x0 + dx, y0), (x1 + dx, y1), colb, -1)
        imgs[d] = img
    for f, d in enumerate(draw_of):
        cv2.imwrite(os.path.join(a.out, f"f{f:03d}.png"), imgs[d])
    info = {"장수": n, "정점(장)": tp, "정점면적": round(float(area), 3), "갈라짐": splits, "그림번호": shape_of, "카메라_돌기": a.orbit,
            "그림수": len(set(draw_of)), "파편": {"수": ndeb, "정점속도_화면높이": db["peak_speed_h_median"], "반감(장)": half},
            "출처": ["data/p3/fx_timing_2026-10-22.json explosion", "data/p4/nakamura_debris_rhythm_2026-10-21.json 폭발 파편"],
            "가정": ["면적 곡선 모양(빠르게 커져 정점 뒤 유지)", "갈라진 조각 흩어짐으로 무게중심 이동 대신"]}
    json.dump(info, open(os.path.join(a.out, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: info[k] for k in ("장수", "정점(장)", "정점면적", "그림수", "그림번호")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
