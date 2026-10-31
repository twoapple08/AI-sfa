"""CMU 모캡(ASF/AMC) → 관절 3D 좌표(미터, Y 위쪽) 변환.

사용: python tools/cmu_amc.py <all_asfamc 폴더> <출력 폴더> [--fps 30] [--jobs 2]
출력: <출력>/<피험자>_<번호>.npz  (pos: [프레임, 31, 3] float32, names, parents, fps)
이미 있는 파일은 건너뛴다. CMU 원본은 저장소에 넣지 않는다(Drive·서버 임시 폴더만).

순운동학: 뼈마다 L = L_부모 · C · M · C⁻¹, 끝점 = 시작점 + L · (방향 × 길이).
C는 ASF axis(도, XYZ 순 오일러), M은 AMC 자유도 값(도)을 dof 순서대로 곱한 회전.
길이 단위: ASF `:units length s` → 1 / s 인치 → × 0.0254 m.
"""
import argparse
import glob
import os
from multiprocessing import Pool

import numpy as np


def rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(vals, order):
    r = np.eye(3)
    for ax, v in zip(order.lower(), vals):
        r = r @ rot(ax, v)
    return r


def parse_asf(path):
    lines = [l.split("#")[0].rstrip() for l in open(path, encoding="latin1")]
    scale, root_order, root_axis = 1.0, "XYZ", "XYZ"
    bones, parents, sec, cur = {}, {}, None, None
    for l in lines:
        t = l.split()
        if not t:
            continue
        if t[0].startswith(":"):
            sec = t[0]
            continue
        if sec == ":units" and t[0] == "length":
            scale = float(t[1])
        elif sec == ":root":
            if t[0] == "order":
                root_order = t[1:]
            elif t[0] == "axis":
                root_axis = t[1]
        elif sec == ":bonedata":
            if t[0] == "begin":
                cur = {"dof": []}
            elif t[0] == "end":
                bones[cur["name"]] = cur
            elif t[0] == "name":
                cur["name"] = t[1]
            elif t[0] == "direction":
                cur["dir"] = np.array(list(map(float, t[1:4])))
            elif t[0] == "length":
                cur["len"] = float(t[1])
            elif t[0] == "axis":
                cur["axis"] = (list(map(float, t[1:4])), t[4])
            elif t[0] == "dof":
                cur["dof"] = [d.lower() for d in t[1:]]
        elif sec == ":hierarchy":
            if t[0] in ("begin", "end"):
                continue
            for ch in t[1:]:
                parents[ch] = t[0]
    unit = 0.0254 / scale
    for b in bones.values():
        b["C"] = euler(*b["axis"])
        b["Cinv"] = b["C"].T
        b["off"] = b["dir"] * b["len"] * unit
    order = ["root"]
    i = 0
    while i < len(order):
        order += [c for c, p in parents.items() if p == order[i]]
        i += 1
    return {"bones": bones, "parents": parents, "order": order, "unit": unit,
            "root_order": [o.lower() for o in root_order], "root_axis": root_axis}


def parse_amc(path):
    frames, cur = [], None
    for l in open(path, encoding="latin1"):
        t = l.split()
        if not t or t[0].startswith("#") or t[0].startswith(":"):
            continue
        if t[0].isdigit() and len(t) == 1:
            cur = {}
            frames.append(cur)
        elif cur is not None:
            cur[t[0]] = list(map(float, t[1:]))
    return frames


def fk(asf, fr):
    pos, glob_r = {}, {}
    rv = fr["root"]
    vals = dict(zip(asf["root_order"], rv))
    pos["root"] = np.array([vals.get("tx", 0), vals.get("ty", 0), vals.get("tz", 0)]) * asf["unit"]
    rax = [a for a in asf["root_order"] if a.startswith("r")]
    glob_r["root"] = euler([vals[a] for a in rax], "".join(a[1] for a in rax))
    for name in asf["order"][1:]:
        b, p = asf["bones"][name], asf["parents"][name]
        m = np.eye(3)
        if name in fr and b["dof"]:
            for d, v in zip(b["dof"], fr[name]):
                m = m @ rot(d[1], v)
        L = glob_r[p] @ b["C"] @ m @ b["Cinv"]
        glob_r[name] = L
        pos[name] = pos[p] + L @ b["off"]
    return np.stack([pos[n] for n in asf["order"]])


def convert(args):
    amc, asf_path, out, fps, src_fps = args
    if os.path.exists(out):
        return out, "skip"
    asf = parse_asf(asf_path)
    fr = parse_amc(amc)
    step = max(1, round(src_fps / fps))
    pos = np.stack([fk(asf, f) for f in fr[::step]]).astype(np.float32)
    names = asf["order"]
    parents = [-1] + [names.index(asf["parents"][n]) for n in names[1:]]
    np.savez_compressed(out, pos=pos, names=np.array(names), parents=np.array(parents), fps=src_fps / step)
    return out, pos.shape


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--index", help="trial→fps json(index.json의 trials); 없으면 120")
    a = ap.parse_args()
    import json
    fpsmap = json.load(open(a.index))["trials"] if a.index else {}
    os.makedirs(a.out, exist_ok=True)
    jobs = []
    for amc in sorted(glob.glob(os.path.join(a.src, "**", "*.amc"), recursive=True)):
        tid = os.path.basename(amc)[:-4]
        subj = tid.split("_")[0]
        asf = glob.glob(os.path.join(os.path.dirname(amc), subj + ".asf"))
        if not asf:
            continue
        sf = fpsmap.get(tid, {}).get("fps", 120)
        jobs.append((amc, asf[0], os.path.join(a.out, tid + ".npz"), a.fps, sf))
    n = 0
    with Pool(a.jobs) as p:
        for out, r in p.imap_unordered(convert, jobs):
            n += 1
            if n % 200 == 0:
                print(n, "/", len(jobs), flush=True)
    print("완료", n)


if __name__ == "__main__":
    main()
