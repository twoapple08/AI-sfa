#!/usr/bin/env python3
"""그림 한 장 → 평면 색 면 SFA, 테두리를 '시작점 + 끝점 + 텐션' 곡선으로, 텐션이 0이면 직선 오브젝트로 (2026-10-28).

동기(사용자): 그림 강좌의 '선 = 시작점 + 끝점 + 텐션'(벡터론)이 SFA 2차 곡선(TypeId 3: 양 끝점 + 가운데 제어점)과 같다.
나카무라 '유타퐁 큐브'처럼 모서리가 곧은 조각은 텐션이 0인 선이 대부분 → 직선 오브젝트(TypeId 1)로 바꿔 적은 수의 선으로 덮는다.
방법:
1. Lab k-평균 팔레트로 평면 색 면(palette_sfa와 같은 라벨링), 넓은 색부터 아래에 깔고 2px 넓혀 틈을 막는다.
2. 윤곽마다 꼭짓점(꺾임 각 --corner 이상)으로 나눈다.
3. 꼭짓점 사이 구간: 직선에서 가장 먼 점이 --line-tol px 이하이면 직선(텐션 0),
   아니면 양 끝을 고정한 2차 곡선을 맞춰 최대 오차가 --quad-tol px 이하이면 곡선 하나(텐션 = 제어점의 현 중점에서 떨어진 거리 / 현 길이),
   넘으면 가장 먼 점에서 나눠 다시.
4. 채우기(FR/FS)는 직선·곡선 오브젝트를 그대로 잇는다(앱 규칙: 직선은 T를 자르지 않음, 렌더러 contour_path와 같음).
원본 프레임·결과 SFA는 저장소에 넣지 않는다(다른 작가 그림). 도구와 통계만 둔다.
사용: python tools/cube_vector_sfa.py <영상> <프레임> <out.sfa> [--k 10] [--check 비교.jpg]
"""
import argparse
import math
import os
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_clip_sfa import argb  # noqa: E402
from palette_sfa import label, palette  # noqa: E402

TS = 0.1  # 테두리 굵기(채우기 경계만, 거의 안 보이게)


def cross2(a, b):
    """2차원 외적(numpy 2는 2차원 np.cross를 막음)."""
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def dp_idx(P, i0, i1, eps, out):
    """닫힌 윤곽 P의 i0..i1(포함) 구간을 더글러스-포이커로 줄여 꼭짓점 번호를 out에."""
    if i1 - i0 < 2:
        return
    a, b = P[i0], P[i1]
    seg = P[i0 + 1:i1]
    d = np.abs(cross2(b - a, seg - a)) / max(np.linalg.norm(b - a), 1e-9)
    k = int(d.argmax())
    if d[k] > eps:
        m = i0 + 1 + k
        dp_idx(P, i0, m, eps, out)
        out.append(m)
        dp_idx(P, m, i1, eps, out)


def corners(P, eps, ang):
    """꼭짓점 번호(정렬). 더글러스-포이커 점 가운데 꺾임 각이 ang도 이상인 것만 꼭짓점으로."""
    n = len(P)
    far = int(np.linalg.norm(P - P[0], axis=1).argmax())
    idx = [0]
    dp_idx(P, 0, far, eps, idx)
    idx.append(far)
    Q = np.vstack([P, P[:1]])
    tmp = []
    dp_idx(Q, far, n, eps, tmp)
    idx += [i % n for i in tmp]
    idx = sorted(set(idx))
    keep = []
    for j, i in enumerate(idx):
        a, b, c = P[idx[j - 1]], P[i], P[idx[(j + 1) % len(idx)]]
        u, v = b - a, c - b
        cosv = float(np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-9))
        if math.degrees(math.acos(max(-1.0, min(1.0, cosv)))) >= ang:
            keep.append(i)
    return keep or idx[:: max(1, len(idx) // 4)]


def fit_quad(S):
    """양 끝 고정 2차 곡선: 현 길이 매개변수로 제어점 최소제곱. 반환 (제어점, 최대 오차)."""
    p0, p2 = S[0], S[-1]
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(S, axis=0), axis=1))]
    t = L / max(L[-1], 1e-9)
    u = 1 - t
    w = 2 * u * t
    r = S - (u * u)[:, None] * p0 - (t * t)[:, None] * p2
    c = (w[:, None] * r).sum(0) / max((w * w).sum(), 1e-9)
    B = (u * u)[:, None] * p0 + w[:, None] * c + (t * t)[:, None] * p2
    return c, float(np.linalg.norm(B - S, axis=1).max())


def fit_run(S, line_tol, quad_tol, out, depth=0):
    """구간 S(점 배열) → [(kind, pts)] kind 1 = 직선 (p0,p2), 3 = 곡선 (p0,c,p2)."""
    p0, p2 = S[0], S[-1]
    ch = p2 - p0
    cl = max(np.linalg.norm(ch), 1e-9)
    dev = np.abs(cross2(ch, S - p0)) / cl
    if dev.max() <= line_tol or len(S) < 4:
        out.append((1, (p0, p2), 0.0))
        return
    c, err = fit_quad(S)
    if err <= quad_tol or depth > 12:
        out.append((3, (p0, c, p2), float(np.linalg.norm(c - (p0 + p2) / 2) / cl)))
        return
    k = int(dev.argmax())
    k = min(max(k, 2), len(S) - 3)
    fit_run(S[:k + 1], line_tol, quad_tol, out, depth + 1)
    fit_run(S[k:], line_tol, quad_tol, out, depth + 1)


def contour_segs(P, eps, ang, line_tol, quad_tol):
    cs = corners(P, eps, ang)
    segs = []
    for j, i in enumerate(cs):
        k = cs[(j + 1) % len(cs)]
        S = P[i:k + 1] if k > i else np.vstack([P[i:], P[:k + 1]])
        fit_run(S, line_tol, quad_tol, segs)
    return segs


def corners_open(P, eps, ang):
    """열린 선의 꼭짓점(양 끝 포함)."""
    idx = [0]
    dp_idx(P, 0, len(P) - 1, eps, idx)
    idx.append(len(P) - 1)
    keep = [0]
    for j in range(1, len(idx) - 1):
        a, b, c = P[idx[j - 1]], P[idx[j]], P[idx[j + 1]]
        u, v = b - a, c - b
        cosv = float(np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-9))
        if math.degrees(math.acos(max(-1.0, min(1.0, cosv)))) >= ang:
            keep.append(idx[j])
    return keep + [len(P) - 1]


def ink_strokes(img, eps, ang, line_tol, quad_tol, bh_kernel=9, bh_thr=None, min_len=12):
    """먹선(주변보다 어두운 가는 선) → 가운데선 → 꼭짓점마다 직선/곡선 조각 + 굵기(px)·색.
    블랙햇(닫기 - 원본)으로 가는 어두운 선만 남기고 뼈대로 줄여 끝점·갈림점 사이 선으로 나눈다(effect_vectorize.trace)."""
    from effect_vectorize import trace
    from skimage.morphology import skeletonize
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (bh_kernel, bh_kernel)))
    if bh_thr is None:  # 장면 밝기마다 다르다(어두운 장면은 선 대비가 작다) → 상위 4% 기준, 최소 5
        bh_thr = max(5.0, float(np.percentile(bh, 96)))
    m = (bh > bh_thr).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))  # 압축으로 끊긴 먹선 잇기
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    sk = skeletonize(m > 0)
    out = []
    for path in trace(sk):
        if len(path) < min_len:
            continue
        P = np.array([(x, y) for y, x in path], np.float64)
        w = float(np.median([dist[y, x] for y, x in path])) * 2
        col = np.median(np.array([img[y, x] for y, x in path]), axis=0)
        cs = corners_open(P, eps, ang)
        segs = []
        for i, k in zip(cs[:-1], cs[1:]):
            if k - i >= 1:
                fit_run(P[i:k + 1], line_tol, quad_tol, segs)
        out.append((segs, max(w, 1.0), col))
    return join_lines(out)


def join_lines(strokes, gap=24.0, ang=8.0, off=3.0):
    """끊긴 직선 잇기: 끝점이 gap px 안이고 방향 차가 ang도 안, 서로의 연장선에서 off px 안이면 한 직선으로(양 끝 = 가장 먼 두 끝점).
    곡선은 그대로. 이은 직선은 따로 한 획이 된다(굵기·색 = 이어진 것들의 평균)."""
    L = []  # [p0, p1, w, col]
    rest = []
    for segs, w, col in strokes:
        keep = []
        for sg in segs:
            if sg[0] == 1:
                L.append([np.array(sg[1][0]), np.array(sg[1][1]), w, np.array(col, float), 1])
            else:
                keep.append(sg)
        if keep:
            rest.append((keep, w, col))
    changed = True
    while changed:
        changed = False
        for i in range(len(L)):
            if L[i] is None:
                continue
            a0, a1 = L[i][0], L[i][1]
            da = (a1 - a0) / max(np.linalg.norm(a1 - a0), 1e-9)
            for j in range(i + 1, len(L)):
                if L[j] is None:
                    continue
                b0, b1 = L[j][0], L[j][1]
                db = (b1 - b0) / max(np.linalg.norm(b1 - b0), 1e-9)
                if abs(float(np.dot(da, db))) < math.cos(math.radians(ang)):
                    continue
                if min(np.linalg.norm(x - y) for x in (a0, a1) for y in (b0, b1)) > gap:
                    continue
                if max(abs(float(cross2(da, b0 - a0))), abs(float(cross2(da, b1 - a0)))) > off:
                    continue
                P = [a0, a1, b0, b1]
                k, m = max(((k, m) for k in range(4) for m in range(k + 1, 4)), key=lambda km: np.linalg.norm(P[km[0]] - P[km[1]]))
                n = L[i][4] + L[j][4]
                L[i] = [P[k], P[m], (L[i][2] * L[i][4] + L[j][2] * L[j][4]) / n, (L[i][3] * L[i][4] + L[j][3] * L[j][4]) / n, n]
                L[j] = None
                a0, a1 = L[i][0], L[i][1]
                da = (a1 - a0) / max(np.linalg.norm(a1 - a0), 1e-9)
                changed = True
    return rest + [([(1, (l[0], l[1]), 0.0)], l[2], l[3]) for l in L if l is not None]


class Writer:
    def __init__(self, W, H):
        self.W, self.H, self.oid, self.pid, self.out = W, H, 1, 1, []

    def ao(self, kind, pts, color, links, ts=TS):
        oid, p = self.oid, self.pid
        self.oid += 1
        self.pid += len(pts)
        o = [f'<AO ID="{oid}" TypeId="{kind}" Color="{color}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
             f'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">']
        for i, (x, y) in enumerate(pts):
            link = links[0] if i == 0 else links[1] if i == len(pts) - 1 else None
            ac = f'<AC ConnPtId="{link}"/>' if link else ""
            o.append(f'<AP ID="{p + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / self.W * 100:.3f}" Y="{y / self.H * 100:.3f}">{ac}</AP>')
        self.out.append("".join(o) + "</AO>")
        return oid, p, p + len(pts) - 1

    def region(self, contours, color):
        """contours: [(hole, segs)] 바깥 하나 + 구멍들. 조각끼리 끝점을 AC로 잇고 FS로 채우기."""
        fs = []
        for ci, (_, segs) in enumerate(contours):
            ends = []
            start_pid = self.pid
            for j, (kind, pts, _) in enumerate(segs):
                prev_end = ends[-1] if ends else None
                nxt = None  # 다음 조각의 시작점 번호는 아직 모름 → 앞 조각 끝에서 거꾸로 잇는 것으로 충분(한쪽 연결)
                oid, ps, pe = self.ao(kind, pts, color, (prev_end, nxt))
                ends.append(pe)
                fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{ps}" EndPtId="{pe}" StartT="0.0" EndT="1.0" Contour="{ci}"/>')
            del start_pid
        self.out.append(f'<FR Color="{color}">' + "".join(fs) + "</FR>")

    def stroke(self, segs, color, ts):
        """보이는 선: 조각마다 오브젝트, 이어지는 끝점은 AC로(관절처럼 한 획)."""
        prev = None
        for kind, pts, _ in segs:
            oid, ps, pe = self.ao(kind, pts, color, (prev, None), ts)
            prev = pe


def vectorize(img, k, grow, min_area, eps, ang, line_tol, quad_tol):
    cent, bgr = palette([img], k)
    idx = label(img, cent)
    order = sorted(range(k), key=lambda c: -(idx == c).sum())
    regions, stats = [], {"line": 0, "quad": 0, "tension": []}
    for ci in order:
        m = (idx == ci).astype(np.uint8)
        if m.sum() < min_area:
            continue
        if ci != order[0]:
            m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
        cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        hier = hier[0]
        for i, c in enumerate(cnts):
            if hier[i][3] != -1 or cv2.contourArea(c) < min_area:
                continue
            group = []
            j = i
            chain = [i]
            ch = hier[i][2]
            while ch != -1:
                if cv2.contourArea(cnts[ch]) >= min_area:
                    chain.append(ch)
                ch = hier[ch][0]
            for jj in chain:
                P = cnts[jj][:, 0, :].astype(np.float64)
                if len(P) < 4:
                    continue
                segs = contour_segs(P, eps, ang, line_tol, quad_tol)
                for kind, _, tn in segs:
                    stats["line" if kind == 1 else "quad"] += 1
                    if kind == 3:
                        stats["tension"].append(tn)
                group.append((jj != i, segs))
            del j
            if group and not group[0][0]:
                regions.append((argb(bgr[ci]), group))
    return regions, stats, idx, bgr


def write(path, W, H, regions, bg, strokes=()):
    wr = Writer(W, H)
    for col, group in regions:
        wr.region(group, col)
    for segs, w, col in strokes:  # 선은 면 위에. 굵기: 화면 폭 1920 기준 선 폭 = 1.14·8·TS
        wr.stroke(segs, argb(col), max(0.02, w * (1920 / W) / (1.14 * 8)))
    name = os.path.splitext(os.path.basename(path))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"{bg}\">\n<Frame BackgroundColor=\"{bg}\" ID=\"1\" Position=\"0\">"
           '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>\n' + "\n".join(wr.out) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    return wr.oid - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("frame", type=int)
    ap.add_argument("out")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--scale", type=float, default=1.0, help="원본을 키워 딴다(가는 모서리 보존)")
    ap.add_argument("--grow", type=int, default=2)
    ap.add_argument("--min-area", type=int, default=40)
    ap.add_argument("--eps", type=float, default=1.5, help="꼭짓점 찾기 더글러스-포이커 허용(px)")
    ap.add_argument("--corner", type=float, default=30.0, help="이 각도(도) 이상 꺾이면 꼭짓점")
    ap.add_argument("--line-tol", type=float, default=1.2, help="직선에서 이만큼(px) 안이면 텐션 0 → 직선 오브젝트")
    ap.add_argument("--quad-tol", type=float, default=1.5, help="곡선 하나로 덮을 최대 오차(px)")
    ap.add_argument("--ink", action="store_true", help="먹선(가는 어두운 선)을 따로 가운데선 획으로 뽑아 면 위에 그린다")
    ap.add_argument("--check", help="원본 | 결과 렌더 비교 그림")
    a = ap.parse_args()
    c = cv2.VideoCapture(a.video)
    c.set(cv2.CAP_PROP_POS_FRAMES, a.frame)
    ok, img = c.read()
    if not ok:
        raise SystemExit("프레임을 못 읽음")
    if a.scale != 1.0:
        img = cv2.resize(img, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_CUBIC)
    H, W = img.shape[:2]
    regions, st, idx, bgr = vectorize(img, a.k, a.grow, a.min_area, a.eps, a.corner, a.line_tol, a.quad_tol)
    strokes = ink_strokes(img, a.eps, a.corner, a.line_tol, a.quad_tol) if a.ink else []
    for segs, _, _ in strokes:
        for kind, _, tn in segs:
            st["line" if kind == 1 else "quad"] += 1
            if kind == 3:
                st["tension"].append(tn)
    n = write(a.out, W, H, regions, argb(bgr[np.bincount(idx.ravel()).argmax()]), strokes)
    if strokes:
        ns = sum(len(x[0]) for x in strokes)
        print(f"먹선 획 {len(strokes)}개, 오브젝트 {ns} (직선 {sum(k == 1 for x in strokes for k, _, _ in x[0])})")
    tn = np.array(st["tension"]) if st["tension"] else np.zeros(1)
    print(f"면 {len(regions)}, 오브젝트 {n} = 직선 {st['line']} + 곡선 {st['quad']} (직선 비율 {st['line'] / max(n, 1):.0%}), "
          f"곡선 텐션 중앙값 {np.median(tn):.3f}")
    if a.check:
        import subprocess
        tmp = a.out + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), a.out, tmp,
                        "--frames", "0", "--size", f"{W}x{H}"], check=True, capture_output=True)
        r = cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0]))
        diff = float(np.abs(r.astype(np.float32) - img.astype(np.float32)).mean())
        cv2.imwrite(a.check, np.hstack([img, r]))
        print(f"렌더 평균 화소차 {diff:.1f} (0–255) → {a.check}")


if __name__ == "__main__":
    main()
