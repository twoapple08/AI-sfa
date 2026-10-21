"""BVH → 관절 3D 좌표(미터) 변환. LaFAN1·Bandai Namco 모캡용.

사용: python tools/bvh_pos.py <BVH 폴더> <출력 폴더> [--fps 30] [--unit 0.01] [--jobs 2]
출력: <출력>/<파일이름>.npz  (pos [프레임, 관절, 3] float32, names, parents, fps) — tools/cmu_amc.py와 같은 형식
End Site는 '<부모>_end' 관절로 넣는다. 위쪽 축은 원본 그대로(두 자료 모두 Y 위)다.
"""
import argparse
import glob
import os
from multiprocessing import Pool

import numpy as np


def rmat(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    o, z = np.ones_like(a), np.zeros_like(a)
    if axis == "x":
        m = [[o, z, z], [z, c, -s], [z, s, c]]
    elif axis == "y":
        m = [[c, z, s], [z, o, z], [-s, z, c]]
    else:
        m = [[c, -s, z], [s, c, z], [z, z, o]]
    return np.moveaxis(np.array(m), [0, 1], [-2, -1])  # [..., 3, 3]


def parse(path):
    tok = open(path, encoding="latin1").read().split()
    i, names, parents, offs, chans, stack = 0, [], [], [], [], []
    while tok[i] != "MOTION":
        t = tok[i]
        if t in ("ROOT", "JOINT"):
            names.append(tok[i + 1])
            parents.append(stack[-1] if stack else -1)
            i += 2
        elif t == "End":
            names.append(names[stack[-1]] + "_end")
            parents.append(stack[-1])
            chans.append([])
            i += 2
        elif t == "{":
            stack.append(len(names) - 1)
            i += 1
        elif t == "}":
            stack.pop()
            i += 1
        elif t == "OFFSET":
            offs.append([float(x) for x in tok[i + 1:i + 4]])
            i += 4
        elif t == "CHANNELS":
            n = int(tok[i + 1])
            chans.append(tok[i + 2:i + 2 + n])
            i += 2 + n
        else:
            i += 1
    nf = int(tok[i + 2])
    ft = float(tok[i + 5])
    data = np.array(tok[i + 6:], dtype=float).reshape(nf, -1)
    return names, parents, np.array(offs), chans, data, ft


def fk(names, parents, offs, chans, data, unit):
    nf = len(data)
    R = [None] * len(names)
    P = np.zeros((nf, len(names), 3))
    col = 0
    for j in range(len(names)):
        ch = chans[j]
        vals = data[:, col:col + len(ch)]
        col += len(ch)
        local = np.broadcast_to(np.eye(3), (nf, 3, 3)).copy()
        trans = None
        for k, c in enumerate(ch):
            cl = c.lower()
            if cl.endswith("rotation"):
                local = local @ rmat(cl[0], vals[:, k])
        if any(c.lower().endswith("position") for c in ch):
            trans = np.stack([vals[:, ch.index(a)] if a in ch else np.zeros(nf)
                              for a in ("Xposition", "Yposition", "Zposition")], 1)
        p = parents[j]
        if p < 0:
            P[:, j] = (trans if trans is not None else offs[j]) * unit
            R[j] = local
        else:
            off = trans if trans is not None else np.broadcast_to(offs[j], (nf, 3))
            P[:, j] = P[:, p] + np.einsum("nij,nj->ni", R[p], off) * unit
            R[j] = R[p] @ local
    return P


def convert(args):
    src, dst, fps, unit = args
    if os.path.exists(dst):
        return dst, "skip"
    names, parents, offs, chans, data, ft = parse(src)
    step = max(1, round((1 / ft) / fps))
    P = fk(names, parents, offs, chans, data[::step], unit).astype(np.float32)
    np.savez_compressed(dst, pos=P, names=np.array(names), parents=np.array(parents), fps=1 / ft / step)
    return dst, P.shape


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--unit", type=float, default=0.01)
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    jobs = [(f, os.path.join(a.out, os.path.basename(f)[:-4] + ".npz"), a.fps, a.unit)
            for f in sorted(glob.glob(os.path.join(a.src, "**", "*.bvh"), recursive=True))]
    n = 0
    with Pool(a.jobs) as p:
        for _ in p.imap_unordered(convert, jobs):
            n += 1
            if n % 200 == 0:
                print(n, "/", len(jobs), flush=True)
    print("완료", n)


if __name__ == "__main__":
    main()
