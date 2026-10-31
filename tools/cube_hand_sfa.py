#!/usr/bin/env python3
"""'이해는 사람(또는 Claude), 정밀함은 도구': 큐브의 꼭짓점·면 구조를 대략 지정하면 먹선에 붙여 '직선 9개 + 면 3개' SFA로 (2026-10-28).

배경(사용자): 픽셀을 따라가는 변환은 선을 토막 내고 오브젝트가 수만 개가 된다. 사람은 '큐브다'를 먼저 알고 모서리 9개를 긋는다.
방법:
1. 구조 JSON: 큐브마다 꼭짓점(대략, 원본 px)·면(꼭짓점 번호 목록, 시계/반시계 무관). 모서리 = 면 테두리의 합집합(공유 모서리는 한 번).
2. 모서리마다 대략 선분 주변 띠(--band px)의 먹선 픽셀(어두운 픽셀)에 직선을 맞춘다(cv2.fitLine, 양 끝 15%는 빼서 꼭짓점 뭉침 무시).
3. 꼭짓점 = 그 꼭짓점에 닿는 모서리 직선들에 가장 가까운 점(최소제곱 교점) — 먹선 가운데에 정확히 붙는다.
4. SFA: 모서리마다 직선 오브젝트 하나(TypeId 1, 먹선 색·굵기), 면마다 채우기(FR)가 그 모서리 오브젝트를 그대로 테두리로 쓴다
   (거꾸로 지나는 모서리는 StartT 1→EndT 0, 앱 규칙: StartT>EndT면 방향 반전). 채우기는 모서리를 공유해 큐브 하나 = 오브젝트 9 + 채우기 3.
   채우기는 첫 테두리 오브젝트 차례에 그려지므로(렌더러·앱 규칙) 공유 모서리를 가장 앞 번호로 둬 면이 선을 덮지 않게 한다.
원본 프레임·결과 SFA는 저장소에 넣지 않는다. 구조 JSON(좌표 몇 개)과 도구만 둔다.
사용: python tools/cube_hand_sfa.py <그림> <구조.json> <out.sfa> [--scale 2] [--check 비교.jpg]
"""
import argparse
import json
import os
import subprocess
import sys
import zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from effect_clip_sfa import argb  # noqa: E402


def fit_edge(ink, a, b, band):
    """선분 a-b 주변 띠의 먹선 픽셀에 직선 맞추기 → (점, 방향, 쓴 픽셀 수). 픽셀이 적으면 대략 선분 그대로."""
    ys, xs = np.nonzero(ink)
    P = np.c_[xs, ys].astype(np.float64)
    d = b - a
    L = np.linalg.norm(d)
    u = d / L
    t = (P - a) @ u
    off = np.abs((P - a)[:, 0] * u[1] - (P - a)[:, 1] * u[0])
    sel = (t > 0.15 * L) & (t < 0.85 * L) & (off < band)
    if sel.sum() < 6:
        return a, u, 0
    vx, vy, x0, y0 = cv2.fitLine(P[sel].astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
    return np.array([x0, y0]), np.array([vx, vy]), int(sel.sum())


def corner(lines):
    """여러 직선(점, 단위 방향)에 가장 가까운 점."""
    A = np.zeros((2, 2))
    r = np.zeros(2)
    for p, u in lines:
        n = np.array([-u[1], u[0]])
        A += np.outer(n, n)
        r += np.outer(n, n) @ p
    return np.linalg.solve(A + 1e-9 * np.eye(2), r)


def solve_cube(ink, cube, band):
    V = np.array(cube["v"], np.float64)
    edges = []
    for f in cube["faces"]:
        for i, j in zip(f, f[1:] + f[:1]):
            e = tuple(sorted((i, j)))
            if e not in edges:
                edges.append(e)
    fits = {e: fit_edge(ink, V[e[0]], V[e[1]], band) for e in edges}
    V2 = V.copy()
    for k in range(len(V)):
        ls = [(fits[e][0], fits[e][1]) for e in edges if k in e and fits[e][2] > 0]
        if len(ls) >= 2:
            c = corner(ls)
            if np.linalg.norm(c - V[k]) < 3 * band:  # 엇나간 맞춤(평행 직선 등)은 버림
                V2[k] = c
    return V2, edges, {e: fits[e][2] for e in edges}


def edges_of(faces):
    edges = []
    for f in faces:
        for i, j in zip(f, f[1:] + f[:1]):
            e = tuple(sorted((i, j)))
            if e not in edges:
                edges.append(e)
    return edges


def convex_fix(img, ink, V, faces, min_area=2.0):
    """볼록 블록 검사(10-28 사용자: 육면체 윤곽이 안으로 꺾이고 그 안이 비는 건 현실적으로 말이 안 된다).
    바깥 윤곽(면 하나에만 속한 모서리의 고리)에서 볼록 껍질 꼭짓점이 아닌 점 = 안으로 꺾인 점.
    껍질 꼭짓점 사이 꺾인 점 묶음마다 빈틈 다각형 [h1, r..., h2]을 만들고 원본 그림과 대조한다:
    - 틈 안이 먹선·기존 면 색이면(> 50%) 빠진 면 → 그 틈을 면으로 채운다(얇은 두께면 등).
    - 아니면(바탕) 잘못 잡힌 꼭짓점 → 꺾인 점을 h1–h2 직선 위로 편다.
    면적 < min_area(px²)인 틈은 펴기만 한다. 돌려주는 값: (V, faces, 새 면 색 {면 번호: BGR}, 기록)."""
    V = V.copy()
    faces = [list(f) for f in faces]
    own = {}
    for fi, f in enumerate(faces):
        for i, j in zip(f, f[1:] + f[:1]):
            own.setdefault(tuple(sorted((i, j))), []).append(fi)
    outer = [e for e, fs in own.items() if len(fs) == 1]
    nb = {}
    for a, b in outer:
        nb.setdefault(a, []).append(b)
        nb.setdefault(b, []).append(a)
    if not nb or any(len(v) != 2 for v in nb.values()):
        return V, faces, {}, ["바깥 윤곽이 고리 하나가 아니라 검사 생략"]
    start = next(iter(nb))
    ring, prev = [start], None
    while True:
        nxt = [x for x in nb[ring[-1]] if x != prev][0]
        if nxt == start:
            break
        prev = ring[-1]
        ring.append(nxt)
    hull = set(cv2.convexHull(V[ring].astype(np.float32), returnPoints=False).ravel().tolist())
    hull = {ring[i] for i in hull}
    if not hull or len(hull) == len(ring):
        return V, faces, {}, []
    k0 = next(i for i, v in enumerate(ring) if v in hull)
    ring = ring[k0:] + ring[:k0]
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    fmask = np.zeros(img.shape[:2], np.uint8)
    for f in faces:
        cv2.fillPoly(fmask, [np.round(V[f]).astype(np.int32)], 1)
    fcols = [np.median(lab[cv2.erode(m, np.ones((3, 3), np.uint8)) > 0], 0)
             for m in (cv2.fillPoly(np.zeros(img.shape[:2], np.uint8), [np.round(V[f]).astype(np.int32)], 1) for f in faces)
             if cv2.erode(m, np.ones((3, 3), np.uint8)).any()]
    new_cols, log = {}, []
    ring.append(ring[0])
    i = 0
    while i < len(ring) - 1:
        j = i + 1
        while ring[j] not in hull:
            j += 1
        if j > i + 1:
            gap = ring[i:j + 1]
            P = V[gap]
            area = 0.5 * abs(np.dot(P[:, 0], np.roll(P[:, 1], 1)) - np.dot(P[:, 1], np.roll(P[:, 0], 1)))
            m = cv2.fillPoly(np.zeros(img.shape[:2], np.uint8), [np.round(P).astype(np.int32)], 1)
            m[fmask > 0] = 0
            px = lab[m > 0]
            filled = False
            if area >= min_area and len(px):
                like = ink[m > 0].astype(bool)
                for c in fcols:
                    like |= np.linalg.norm(px - c, axis=1) < 20
                if like.mean() > 0.5:
                    faces.append(gap)
                    nonink = img[(m > 0) & (ink == 0)]
                    new_cols[len(faces) - 1] = np.median(nonink if len(nonink) >= 3 else img[m > 0], 0)
                    log.append(f"빈틈 채움 {gap} 면적 {area:.1f} 먹선·면색 {like.mean():.0%}")
                    filled = True
            if not filled:
                h1, h2 = V[gap[0]], V[gap[-1]]
                u = (h2 - h1) / np.linalg.norm(h2 - h1)
                for r in gap[1:-1]:
                    V[r] = h1 + u * ((V[r] - h1) @ u)
                log.append(f"꺾임 폄 {gap[1:-1]} 면적 {area:.1f}")
        i = j
    return V, faces, new_cols, log


def face_color(img, poly, shrink=0.25):
    c = poly.mean(0)
    m = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(m, [np.round(c + (poly - c) * (1 - shrink)).astype(np.int32)], 1)
    return np.median(img[m > 0], axis=0) if m.any() else np.array([128, 128, 128])


def build(img, spec, band, scale, ts_all=None, vis=9, convex=True):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ink = (g < spec.get("ink_max", 70)).astype(np.uint8)
    ink_col = np.median(img[cv2.erode(ink, np.ones((3, 3), np.uint8)) > 0], axis=0)
    if ts_all is None:  # 선 굵기는 모두 같게(10-28 사용자): 그림 전체 먹선 굵기 중앙값 하나
        d = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
        from skimage.morphology import skeletonize
        w_all = float(np.median(d[skeletonize(ink > 0)])) * 2
        ts_all = max(0.05, max(w_all, 1.0) * (1920 / img.shape[1]) / (1.14 * 8))
    H, W = img.shape[:2]
    objs, frs, report = [], [], []
    oid = pid = 1
    for cube in spec["cubes"]:
        cube = dict(cube, v=[[x * scale, y * scale] for x, y in cube["v"]])
        V, edges, npx = solve_cube(ink, cube, band * scale)
        if convex:  # 먹선 맞춤 뒤 볼록 검사: 안으로 꺾인 윤곽은 빈틈을 채우거나 편다
            V, faces, newc, log = convex_fix(img, ink, V, cube["faces"])
            if log:
                print(cube.get("name"), "볼록 검사:", "; ".join(log))
            cube = dict(cube, faces=faces, face_bgr={**cube.get("face_bgr", {}), **{str(k): v for k, v in newc.items()}})
            edges = edges_of(faces)
        # 공유 모서리(면 2개)를 앞에: 채우기가 첫 테두리 차례에 그려지므로 뒤 선을 덮지 않는다
        share = {e: sum(set(e) <= set(f) and any({f[k], f[(k + 1) % len(f)]} == set(e) for k in range(len(f))) for f in cube["faces"])
                 for e in edges}
        edges.sort(key=lambda e: -share[e])
        dist = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
        ids = {}
        objs_c = []  # (oid, pts, tsc) — 연결(AC)을 다 모은 뒤 쓴다
        for e in edges:
            a, b = V[e[0]], V[e[1]]
            ts = np.linspace(0.2, 0.8, 9)
            w = np.median([dist[int(round(y)), int(round(x))] for x, y in (a + (b - a) * t for t in ts)
                           if 0 <= int(round(y)) < H and 0 <= int(round(x)) < W]) * 2
            col = ink_col  # 선 위 표본은 가는 선 옆 바탕색(주황)이 섞여 갈색이 됐다 → 그림 전체 먹선 색 하나
            tsc = ts_all if ts_all else max(0.05, max(w, 1.0) * (1920 / W) / (1.14 * 8))
            ids[e] = (oid, pid, pid + 1)
            objs_c.append((oid, ((pid, a), (pid + 1, b)), tsc, col))
            oid += 1
            pid += 2
        # 앱에서 한 덩어리로 움직이게(10-28 사용자: 파란점이 없고 선끼리 안 이어짐): 같은 꼭짓점에 닿는 선 끝점끼리 서로 AC로 잇고,
        # 큐브마다 파란점(Flags=3) 하나. 나머지 점은 8(시작)/9 — sfa_slim.py와 같은 방식(앱에서 열림 확인된 형식)
        at_v = {}
        for e in edges:
            o, p0, p1 = ids[e]
            at_v.setdefault(e[0], []).append(p0)
            at_v.setdefault(e[1], []).append(p1)
        links = {}
        for ps in at_v.values():
            for x in ps:
                links[x] = [y for y in ps if y != x]
        # 10-28 녹화: 겹친 점 중 Flags 8만 있는 꼭짓점은 점이 안 보이고, 파란점(3) 위에 9가 덮여 주황으로 보였다.
        # 문서상 bit0(1) = 점 표시·선택, Flags & 0x2e = 점 종류(2 = 파란 기준점). → 꼭짓점마다 점 하나만 표시(bit0), 나머지는 bit0을 끈다.
        blue = ids[edges[0]][1]
        flag = {}
        for ps in at_v.values():
            shown = blue if blue in ps else ps[0]
            for x in ps:
                flag[x] = 3 if x == blue else (vis if x == shown else vis - 1)
        for o, pts, tsc, col in objs_c:
            aps = "".join(f'<AP ID="{i}" Flags="{flag[i]}" Index="{k}" X="{x[0] / W * 100:.3f}" Y="{x[1] / H * 100:.3f}">'
                          + "".join(f'<AC ConnPtId="{c}"/>' for c in links.get(i, [])) + "</AP>" for k, (i, x) in enumerate(pts))
            objs.append(f'<AO ID="{o}" TypeId="1" Color="{argb(col)}" LayerId="0" DrawOrder="{o}" ThicknessScale="{tsc:.3f}" ObjectScale="1.0" '
                        f'GlowRadius="0" GlowThickness="0" GlowColor="4294967295" GlowAlpha="0">{aps}</AO>')
        fbgr = {k: np.array(v, float) for k, v in cube.get("face_bgr", {}).items()}  # 폭 1–3px 얇은 면은 자동 찾기에서 잰 색(cube_auto_spec)
        for fi, f in enumerate(cube["faces"]):
            ring = list(zip(f, f[1:] + f[:1]))
            k0 = min(range(len(ring)), key=lambda k: ids[tuple(sorted(ring[k]))][0])  # 가장 앞 번호 모서리부터
            ring = ring[k0:] + ring[:k0]
            fs = []
            for i, j in ring:
                e = tuple(sorted((i, j)))
                o, p0, p1 = ids[e]
                fwd = (i, j) == e
                fs.append(f'<FS Kind="0" ObjId="{o}" StartPtId="{p0 if fwd else p1}" EndPtId="{p1 if fwd else p0}" '
                          f'StartT="{0.0 if fwd else 1.0}" EndT="{1.0 if fwd else 0.0}" Contour="0"/>')
            frs.append((ids[tuple(sorted(ring[0]))][0], f'<FR Color="{argb(fbgr[str(fi)] if str(fi) in fbgr else face_color(img, V[f]))}">' + "".join(fs) + "</FR>"))
        report.append({"name": cube.get("name"), "edges": len(edges), "faces": len(cube["faces"]),
                       "ink_px": [npx.get(e, 0) for e in edges], "moved_px": float(np.abs(V / scale - np.array(cube["v"]) / scale).max())})
    # 채우기는 주인 오브젝트(첫 테두리) 바로 뒤에 둬도 렌더 순서는 오브젝트 차례를 따른다
    body = objs + [x for _, x in sorted(frs)]
    return body, report, oid - 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--band", type=float, default=2.5, help="모서리 대략 선분에서 이 거리(원본 px) 안의 먹선 픽셀로 맞춤")
    ap.add_argument("--bg", default="", help="바탕 BGR(쉼표). 비우면 그림 가장자리 중앙값")
    ap.add_argument("--ts", type=float, default=None, help="모든 선 굵기(ThicknessScale). 비우면 먹선 굵기 중앙값 하나로 통일")
    ap.add_argument("--vis", type=int, default=9, choices=(5, 9), help="꼭짓점에 보이는 점의 Flags(9: 기존 출력, 5: 사람 파일의 끝점). 겹친 나머지는 vis-1로 숨김")
    ap.add_argument("--no-convex", action="store_true", help="볼록 블록 검사 끄기(오목한 물체)")
    ap.add_argument("--check")
    a = ap.parse_args()
    img0 = cv2.imread(a.image)
    img = cv2.resize(img0, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_CUBIC)
    spec = json.load(open(a.spec, encoding="utf-8"))
    body, rep, n = build(img, spec, a.band, a.scale, a.ts, a.vis, not a.no_convex)
    H, W = img.shape[:2]
    bg = np.array([int(x) for x in a.bg.split(",")]) if a.bg else np.median(np.r_[img[0], img[-1], img[:, 0], img[:, -1]], axis=0)
    name = os.path.splitext(os.path.basename(a.out))[0]
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"{H / W:.4f}\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"1\" BackgroundColor=\"{argb(bg)}\">\n<Frame BackgroundColor=\"{argb(bg)}\" ID=\"1\" Position=\"0\">"
           '<LayerDef ID="0" Name="Layer 1" Visible="true" Locked="false"/>\n' + "\n".join(body) + "\n</Frame>\n</Sequence>\n")
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    for r in rep:
        print(f"{r['name']}: 직선 {r['edges']} + 면 {r['faces']}, 모서리별 먹선 픽셀 {r['ink_px']}, 꼭짓점 최대 이동 {r['moved_px']:.1f}px")
    print(f"전체 오브젝트 {n}개 → {a.out}")
    if a.check:
        tmp = a.out + "_r"
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), a.out, tmp,
                        "--frames", "0", "--size", f"{W}x{H}"], check=True, capture_output=True)
        r = cv2.imread(os.path.join(tmp, sorted(os.listdir(tmp))[0]))
        cv2.imwrite(a.check, np.hstack([img, r]))


if __name__ == "__main__":
    main()
