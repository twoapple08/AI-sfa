#!/usr/bin/env python3
"""SFA의 AO ID를 장 사이에 빈자리로 채워 넣어 '서로 다른 AO ID 수'(가져오기 때 새로 만드는 DB 객체 수)를 줄인다 (2026-10-27).

sfa_reuse_ids.py(장마다 j번째 = 같은 ID)는 장마다 새 ID인 플립북용이다. 이 도구는 이미 ID를 이어 쓰는 앱 제작 파일에도 쓴다:
원래 AO ID 하나 = 트랙(나오는 장 집합). 오래 사는 트랙은 그대로 한 ID로 두고, 겹치지 않는 트랙끼리 같은 새 ID를 나눠 쓴다.
지키는 것:
- 한 장 안에서 ID는 하나씩.
- 같은 새 ID의 (TypeId, 점 수, LayerId)는 고정(앱 제작 파일에서 이것들이 장 사이에 바뀐 적이 없음, 2026-10-27 관찰).
- 칠 순서: 가져오기는 XML DrawOrder 대신 '처음 만든 순서'를 쓴다(docs/AOT-PATH-TRACE 1절). 원래 순서 = 트랙이 파일에서 처음 나온 순서(rank).
  앱은 레이어별로 그린다(BuildDrawPlan → 레이어마다 _BuildLayerObjectGroups) → 순서는 같은 레이어 안에서만 지킨다.
  트랙을 rank 순으로 처리하며, 그 트랙이 나오는 모든 장의 같은 레이어에서 이미 배치된(=rank가 앞선) 트랙들의 최대 자리 L보다 뒤의 같은 종류 자리에만 넣는다.
  같은 종류 자리는 레이어도 같으므로 L 뒤 자리는 그 장들에서 항상 비어 있고, 모든 장·레이어에서 새 ID 순서 = 원래 rank 순서가 된다. 각 장의 AO는 새 ID 순으로 쓴다.
- AP ID·연결(AC)·그룹 Flags(위쪽 비트 = AP ID)는 그대로. FS ObjId만 새 ID로.
후보 자리 중 앞 트랙의 마지막 색·굵기·글로우가 같은 자리를 먼저 고른다(장별 상세 변경을 덜 만들기 위해, 앞 8개 후보까지).
주의: 앱 트위닝을 켜면 같은 새 ID끼리 장 사이 보간이 생긴다 — tween=playback으로 볼 것.
사용: python tools/sfa_pack_ids.py <in.sfa> <out.sfa> [--name 이름]
"""
import argparse
import bisect
import os
import zipfile
import xml.etree.ElementTree as ET

DETAIL = ('Color', 'ThicknessScale', 'GlowRadius', 'GlowThickness', 'GlowColor', 'GlowAlpha')
BASE = 100001


def frames_of(path):
    z = zipfile.ZipFile(path)
    seq = None
    for ev, el in ET.iterparse(z.open(z.namelist()[0]), events=('start', 'end')):
        if ev == 'start':
            if el.tag == 'Sequence' and seq is None:
                seq = dict(el.attrib)
            continue
        if el.tag == 'Frame':
            yield seq, el
            el.clear()


def plan(path):
    """트랙 수집 → 새 ID 배정. 반환: {원래 ID: 새 ID}, 통계."""
    tracks = {}  # id -> [rank, key, frames(list), first_detail, last_detail]
    rank = 0
    nf = 0
    for _, el in frames_of(path):
        for a in el.findall('AO'):
            i = a.get('ID')
            det = tuple(a.get(k) for k in DETAIL)
            t = tracks.get(i)
            if t is None:
                tracks[i] = [rank, (a.get('TypeId'), len(a.findall('AP')), a.get('LayerId')), [nf], det, det]
                rank += 1
            else:
                t[2].append(nf)
                t[4] = det
        nf += 1
    maxslot = {}  # (장, 레이어) -> 이미 배치한 최대 자리. 앱은 레이어별로 그리므로 순서는 같은 레이어 안에서만 지키면 된다
    by_key = {}  # key -> sorted slot list
    slot_last = []  # 자리마다 마지막 트랙의 마지막 상세
    remap = {}
    for i, (r, key, fr, d0, d1) in sorted(tracks.items(), key=lambda x: x[1][0]):
        L = max(maxslot.get((f, key[2]), -1) for f in fr)
        lst = by_key.setdefault(key, [])
        k = bisect.bisect_right(lst, L)
        s = None
        for c in lst[k:k + 8]:
            if slot_last[c] == d0:
                s = c
                break
        if s is None and k < len(lst):
            s = lst[k]
        if s is None:
            s = len(slot_last)
            slot_last.append(None)
            lst.append(s)
        slot_last[s] = d1
        for f in fr:
            maxslot[(f, key[2])] = max(maxslot.get((f, key[2]), -1), s)
        remap[i] = str(BASE + s)
    return remap, len(tracks), len(slot_last), nf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--name', default='')
    a = ap.parse_args()
    remap, n_old, n_new, nf = plan(a.src)
    name = a.name or os.path.splitext(os.path.basename(a.dst))[0]
    with zipfile.ZipFile(a.dst, 'w', zipfile.ZIP_DEFLATED) as z, z.open(name + '.xml', 'w', force_zip64=True) as out:
        head = False
        for seq, el in frames_of(a.src):
            if not head:
                att = dict(seq)
                att['Name'] = name
                out.write(('<?xml version="1.0" encoding="UTF-8" ?><Sequence ' + ' '.join(f'{k}="{v}"' for k, v in att.items()) + '>').encode('utf-8'))
                head = True
            parts = ['<Frame ' + ' '.join(f'{k}="{v}"' for k, v in el.attrib.items()) + '>']
            parts += [ET.tostring(l, encoding='unicode') for l in el.findall('LayerDef')]
            aos = el.findall('AO')
            for x in aos:
                x.set('ID', remap[x.get('ID')])
                if x.get('DrawOrder') is not None:
                    x.set('DrawOrder', x.get('ID'))
            aos.sort(key=lambda x: int(x.get('ID')))
            parts += [ET.tostring(x, encoding='unicode') for x in aos]
            for f in el.findall('FR'):
                for fs in f.findall('FS'):
                    if fs.get('ObjId') in remap:
                        fs.set('ObjId', remap[fs.get('ObjId')])
                parts.append(ET.tostring(f, encoding='unicode'))
            parts.append('</Frame>')
            out.write(''.join(parts).encode('utf-8'))
        out.write(b'</Sequence>')
    print(f'{nf}장 | 서로 다른 AO ID {n_old} → {n_new} | 압축 {os.path.getsize(a.src) / 1e6:.1f}MB → {os.path.getsize(a.dst) / 1e6:.1f}MB')


if __name__ == '__main__':
    main()
