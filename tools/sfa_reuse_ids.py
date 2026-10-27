#!/usr/bin/env python3
"""장마다 새 AO ID를 쓰는 플립북 SFA를 '장 사이 AO ID 재사용'으로 바꿔 앱 가져오기를 가볍게 만든다 (2026-10-27).

근거(정적 분석, docs/AOT-PATH-TRACE-2026-10-15.md 1절): 가져오기(_ImportSequenceXmlHandler.startElement)는 XML AO ID에
대응하는 객체가 없을 때만 DataAccess.CreateNewAnimationObject로 DB 객체를 새로 만들고(상세값·순서값 저장 포함) 대응 맵에 둔다.
XML DrawOrder는 읽지 않고 처음 만든 순서가 그리기 순서가 된다.
관찰(2026-10-27): 사람이 앱에서 만든 114장 파일(곡선 449,537개, 서로 다른 AO ID 47,677개)이 1:34에 열렸고,
장마다 새 ID인 변환본(곡선 104,657개 = 서로 다른 ID 104,657개)이 1:50 — 곡선 수보다 '새 객체 수'가 로딩 시간을 좌우한다는 가설.
사람 파일에서 같은 ID의 색·굵기·글로우는 장마다 바뀌지만 TypeId·점 개수는 한 번도 바뀌지 않았다 → 여기서도 지킨다.

방법: 각 장의 AO를 그리는 순서(DrawOrder, 없으면 ID)대로 줄 세워 j번째에 ID base+j를 준다(모든 장에서 j 순서 = 처음 만든 순서라
칠하는 순서 유지). 직선(TypeId 1)은 가운데 제어점의 2차 곡선(TypeId 3)으로 바꿔 같은 ID의 종류·점 수를 고정한다(모양 동일).
AP ID·연결·FR은 ID만 바꿔 그대로 둔다. 원(TypeId 2)이 있으면 거절(이 도구 범위 밖).
주의: 앱 트위닝을 켜면(tween_fps > playback_fps) 같은 ID끼리 장 사이를 보간해 엉뚱하게 변형된다 — (12,12)처럼 같게 둘 것.
사용: python tools/sfa_reuse_ids.py <in.sfa> <out.sfa> [--name 이름]
"""
import argparse
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

BASE = 100001


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--name', default='')
    a = ap.parse_args()
    name = a.name or os.path.splitext(os.path.basename(a.dst))[0]
    zin = zipfile.ZipFile(a.src)
    seq, frames, max_ap = None, [], 0
    for ev, el in ET.iterparse(zin.open(zin.namelist()[0]), events=('start', 'end')):
        if ev == 'start':
            if el.tag == 'Sequence' and seq is None:
                seq = dict(el.attrib)
            continue
        if el.tag != 'Frame':
            continue
        aos = sorted(el.findall('AO'), key=lambda x: (int(x.get('DrawOrder') or x.get('ID')), int(x.get('ID'))))
        for x in aos:
            if x.get('TypeId') == '2':
                sys.exit('원(TypeId 2)은 범위 밖')
            for p in x.findall('AP'):
                max_ap = max(max_ap, int(p.get('ID')))
        frames.append((dict(el.attrib), el.findall('LayerDef'), aos, el.findall('FR')))
    nxt = max_ap + 1
    seq['Name'] = name
    xs = ['<?xml version="1.0" encoding="UTF-8" ?><Sequence ' + ' '.join(f'{k}="{v}"' for k, v in seq.items()) + '>']
    n_entries = slots = 0
    for fattr, layers, aos, frs in frames:
        remap = {x.get('ID'): str(BASE + j) for j, x in enumerate(aos)}
        slots = max(slots, len(aos))
        n_entries += len(aos)
        xs.append('<Frame ' + ' '.join(f'{k}="{v}"' for k, v in fattr.items()) + '>')
        xs += [ET.tostring(l, encoding='unicode') for l in layers]
        for x in aos:
            if x.get('TypeId') == '1':  # 직선 → 가운데 제어점 2차 곡선(끝점은 Index 2로)
                p0, p1 = sorted(x.findall('AP'), key=lambda p: int(p.get('Index')))
                mid = ET.Element('AP', {'ID': str(nxt), 'Flags': '9', 'Index': '1',
                                        'X': f"{(float(p0.get('X')) + float(p1.get('X'))) / 2:.3f}",
                                        'Y': f"{(float(p0.get('Y')) + float(p1.get('Y'))) / 2:.3f}"})
                nxt += 1
                p1.set('Index', '2')
                x.remove(p1)
                x.append(mid)
                x.append(p1)
                x.set('TypeId', '3')
            x.set('ID', remap[x.get('ID')])
            x.set('DrawOrder', x.get('ID'))
            xs.append(ET.tostring(x, encoding='unicode'))
        for f in frs:
            for fs in f.findall('FS'):
                fs.set('ObjId', remap[fs.get('ObjId')])
            xs.append(ET.tostring(f, encoding='unicode'))
        xs.append('</Frame>')
    xs.append('</Sequence>')
    with zipfile.ZipFile(a.dst, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(name + '.xml', ''.join(xs).encode('utf-8'))
    print(f'곡선 {n_entries}개 | 서로 다른 AO ID {n_entries} → {slots} | 압축 {os.path.getsize(a.dst) / 1e6:.1f}MB')


if __name__ == '__main__':
    main()
