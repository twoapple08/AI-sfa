#!/usr/bin/env python3
"""사람이 만든 SFA에서 스틱맨 뼈대(관절 궤적)를 뽑는다 (2026-10-28).

목적(사용자 10-28): 수집한 SFA의 주된 쓰임은 '스틱맨의 움직임'. SFA 스틱맨은 선·점 자체가 뼈대라 관절을 추측할 필요가 없고,
장이 바뀌어도 같은 오브젝트(ID)가 남아 관절이 그대로 이어진다(10장 이상 애니 183개 중 161개, docs/USER-SFA-INVENTORY).

구조(표준 스틱맨 StickFigureNew·달리기.sfa 확인):
- 머리 = 원(TypeId 2, 두 점 = 지름 양 끝), 한 점이 목에 AC로 붙는다.
- 몸통 = 목–엉덩이 직선. 파란점(Flags 3)은 보통 엉덩이(뿌리).
- 팔 = 목에서 나가는 사슬(위팔–아래팔[–손]), 다리 = 엉덩이에서 나가는 사슬(허벅지–정강이[–발]).
방법: AC로 이어진 점을 하나의 관절 노드로 합치고, 오브젝트를 노드 사이 변으로 본다. 원 1개 + 직선 6개 이상이 한 덩어리면 스틱맨 후보.
목 = 머리 원이 붙은 노드, 엉덩이 = 목에서 몸통을 따라간 노드(파란점이 있으면 그 노드, 없으면 목에서 가지가 3개 이상인 반대쪽 끝).
팔·다리 사슬은 목·엉덩이에서 나가는 가지를 끝까지 따라간다. 좌우 구분은 하지 않고 첫 오브젝트 ID 순(장 사이에 ID가 유지되므로 같은 팔은 같은 이름).
T/F(fps)는 파일에 없으므로 장 번호만 기록한다(시간으로 읽지 않는다).
출력: JSONL 한 줄 = 한 장의 한 스틱맨 {"file","frame","fig","head":[[목쪽 x,y],[정수리 x,y]],"neck","hip","arms":[[...],[...]],"legs":[...],"ids":[...]}.
좌표는 SFA 단위(0–100, 화면 비율은 HeightWidthRatio).
사용: python tools/sfa_stickman_extract.py <file.sfa|폴더> <out.jsonl> [--min-frames 10]
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict

MERGE_TOL = 0.3  # SFA 단위(화면 폭의 0.3%) 안에 겹친 끝점은 같은 관절


def frames_of(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read(z.namelist()[0]))
    return root, root.findall('Frame')


def figures(frame):
    """한 장에서 스틱맨 후보 덩어리들을 찾아 뼈대 dict 목록으로 돌려준다."""
    aos = []
    for ao in frame.findall('AO'):
        pts = []
        for ap in ao.findall('AP'):
            pts.append((ap.get('ID'), int(ap.get('Flags') or 0), float(ap.get('X')), float(ap.get('Y')),
                        [c.get('ConnPtId') for c in ap.findall('AC')]))
        if len(pts) >= 2:
            aos.append((ao.get('ID'), ao.get('TypeId'), pts))
    par = {}

    def find(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    pos, flag = {}, {}
    for _, _, pts in aos:
        for pid, fl, x, y, conn in pts:
            find(pid)
            pos[pid] = (x, y)
            flag[pid] = fl
            for c in conn:
                par[find(c)] = find(pid)
    # 옛 파일은 AC 없이 끝점만 같은 자리에 겹쳐 둔다(_SPECTRUM-1 등) → 거의 같은 자리(merge_tol, SFA 단위) 끝점도 합친다
    ends = sorted({p for _, _, pts in aos for p in (pts[0][0], pts[-1][0])}, key=lambda p: pos[p])
    for i, p in enumerate(ends):
        for q in ends[i + 1:]:
            if pos[q][0] - pos[p][0] > MERGE_TOL:
                break
            if abs(pos[q][1] - pos[p][1]) <= MERGE_TOL:
                par[find(q)] = find(p)
    nodes = defaultdict(list)
    for pid in pos:
        nodes[find(pid)].append(pid)
    npos = {n: (sum(pos[p][0] for p in ps) / len(ps), sum(pos[p][1] for p in ps) / len(ps)) for n, ps in nodes.items()}
    root_nodes = {find(p) for p, fl in flag.items() if fl == 3}
    edges = []  # (ao_id, type, node_a, node_b) — 2차 곡선은 양 끝(첫·마지막 점)만
    for aid, t, pts in aos:
        a, b = find(pts[0][0]), find(pts[-1][0])
        if a != b:
            edges.append((aid, t, a, b))
    adj = defaultdict(list)
    for e in edges:
        adj[e[2]].append(e)
        adj[e[3]].append(e)
    seen, out = set(), []
    for start in list(adj):
        if start in seen:
            continue
        comp, st = set(), [start]
        while st:
            n = st.pop()
            if n in comp:
                continue
            comp.add(n)
            st += [e[2] if e[3] == n else e[3] for e in adj[n]]
        seen |= comp
        ce = {e[0]: e for n in comp for e in adj[n]}.values()
        heads = [e for e in ce if e[1] == '2']
        lines = [e for e in ce if e[1] != '2']
        if len(heads) != 1 or len(lines) < 6 or len(ce) > 24:
            continue
        h = heads[0]
        # 목 = 머리 원 끝점 중 다른 선이 붙은 쪽
        neck = max((h[2], h[3]), key=lambda n: sum(1 for e in adj[n] if e[1] != '2'))
        body = [e for e in lines]

        def other(e, n):
            return e[3] if e[2] == n else e[2]
        # 엉덩이: 목에서 나가는 선 중, 끝 노드의 가지가 가장 많은(다리 2개 + 몸통) 쪽. 파란점이 있으면 우선
        cand = [e for e in adj[neck] if e[1] != '2']
        if not cand:
            continue

        def score(e):
            n = other(e, neck)
            return (n in root_nodes, len(adj[n]))
        torso = max(cand, key=score)
        hip = other(torso, neck)
        used = {torso[0], h[0]}

        def chain(n0, e0):
            seq, n, e = [n0], n0, e0
            while e is not None:
                used.add(e[0])
                n = other(e, n)
                seq.append(n)
                nxt = [x for x in adj[n] if x[0] not in used and x[1] != '2']
                e = nxt[0] if len(nxt) == 1 else None
            return [e0[0], [list(npos[k]) for k in seq]]
        arms = [chain(neck, e) for e in sorted((e for e in adj[neck] if e[0] not in used and e[1] != '2'), key=lambda e: int(e[0]))]
        legs = [chain(hip, e) for e in sorted((e for e in adj[hip] if e[0] not in used and e[1] != '2'), key=lambda e: int(e[0]))]
        if len(legs) < 2:
            continue
        far = h[3] if neck == h[2] else h[2]
        # 머리 = 원의 두 점(지름 양 끝: 목 쪽, 정수리 쪽). x·y 단위가 화면 비율(HeightWidthRatio)만큼 달라 반지름은 그릴 때 화면 좌표로 잰다
        out.append(dict(head=[[round(v, 3) for v in npos[neck]], [round(v, 3) for v in npos[far]]], neck=[round(v, 3) for v in npos[neck]],
                        hip=[round(v, 3) for v in npos[hip]], torso_id=torso[0], head_id=h[0],
                        arms=[[a[0], [[round(v, 3) for v in p] for p in a[1]]] for a in arms],
                        legs=[[a[0], [[round(v, 3) for v in p] for p in a[1]]] for a in legs],
                        extra=len(body) + 1 - len(used)))
    return out


def extract(path, rel=None):
    root, frames = frames_of(path)
    rows = []
    for k, fr in enumerate(frames):
        for f in figures(fr):
            rows.append(dict(file=rel or os.path.basename(path), frame=k, fig=f['torso_id'], hwr=float(root.get('HeightWidthRatio') or 0.5625), **f))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--min-frames', type=int, default=10)
    a = ap.parse_args()
    paths = [a.src] if a.src.endswith('.sfa') else sorted(os.path.join(d, f) for d, _, fs in os.walk(a.src) for f in fs if f.endswith('.sfa'))
    n_rows = n_files = 0
    with open(a.out, 'w', encoding='utf-8') as fh:
        for p in paths:
            try:
                root, frames = frames_of(p)
                if len(frames) < a.min_frames:
                    continue
                rows = extract(p, os.path.relpath(p, a.src) if os.path.isdir(a.src) else None)
            except Exception as e:
                print('건너뜀', p, type(e).__name__, file=sys.stderr)
                continue
            if rows:
                n_files += 1
                n_rows += len(rows)
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'파일 {n_files}, 스틱맨-장 {n_rows} → {a.out}')


if __name__ == '__main__':
    main()
