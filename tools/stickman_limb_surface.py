"""가까운 직선 팔다리를 연속 면으로 표시한다. 기존 뼈대는 편집망으로 보존한다."""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from stickman_clip import AO0, LINE_COLOR, STYLE
from stickman_quality import audit, digest, read_sfa
from stickman_scene import load_scene

CHAINS = [(3, 4), (5, 6), (7, 8), (9, 10)]


def contour(points, radii):
    """거의 직선인 세 중심점의 연속 폭 곡선과 둥근 양끝, 총10개2차 곡선."""
    a, mid, b = np.asarray(points, float)
    radii = np.asarray(radii, float)
    if radii.shape != (3,) or not np.isfinite(radii).all() or (radii <= 0).any():
        raise ValueError('면의 세 반지름은 유한한 양수여야 한다')
    delta = b - a
    length = np.linalg.norm(delta)
    if length < 1:
        raise ValueError('면을 만들 사슬이 너무 짧다')
    u = delta / length
    n = np.array([-u[1], u[0]])
    t = float(np.dot(mid - a, u) / length)
    if not .05 < t < .95 or abs(np.dot(mid-a, n)) > max(1., length * .002):
        raise ValueError('이번 면 표현은 직선에 가까운 팔·다리에만 적용한다')
    control = (mid - (1-t)**2*a - t*t*b) / (2*t*(1-t))
    rc = (radii[1] - (1-t)**2*radii[0] - t*t*radii[2]) / (2*t*(1-t))
    if rc <= 0:
        raise ValueError('중간 폭 보간에서 음의 반지름이 생긴다')
    r0, _, r2 = radii
    curves = [[a+n*r0, control+n*rc, b+n*r2]]
    def cap(center, radius, begin):
        for k in range(4):
            p, q = begin-k*np.pi/4, begin-(k+1)*np.pi/4
            direction = lambda v: u*np.cos(v)+n*np.sin(v)
            curves.append([center+radius*direction(p),
                           center+radius/np.cos(np.pi/8)*direction((p+q)/2),
                           center+radius*direction(q)])
    cap(b, r2, np.pi/2)
    curves.append([b-n*r2, control-n*rc, a-n*r0])
    cap(a, r0, -np.pi/2)
    # 같은 경계점의 부동소수 오차도 제거해 연결 좌표를 일치시킨다.
    for i in range(1, 10):
        curves[i][0] = curves[i-1][2].copy()
    curves[-1][2] = curves[0][0].copy()
    return np.asarray(curves)


def events(style, scene):
    if style.get('schema') != 1 or style.get('representation') != 'filled-limb-v1' or style.get('rig') != scene['rig']:
        raise ValueError('면 설정의 버전이 다르다')
    if any(style.get(k) != scene.get(k) for k in ('start', 'end', 'source_sha256')):
        raise ValueError('면 설정의 장 범위·원본이 다르다')
    seen = set()
    for event in style.get('tracks', []):
        chain = tuple(event['segments'])
        if chain not in CHAINS or not scene['start'] <= event['start'] <= event['end'] <= scene['end']:
            raise ValueError('면 사슬·구간이 잘못됐다')
        if any(event['start'] < c <= event['end'] for c in scene.get('cuts', [])):
            raise ValueError('면 구간은 컷을 넘을 수 없다')
        times = sorted(int(t) for t in event['keys'])
        if not times or any(not event['start'] <= t <= event['end'] for t in times):
            raise ValueError('면 반지름 키가 구간 밖이다')
        values = np.asarray([event['keys'][str(t)] for t in times], float)
        if values.shape != (len(times), 3) or not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError('면 키는 세 양수 반지름이어야 한다')
        for f in range(event['start'], event['end']+1):
            key = f, event['actor'], chain
            if key in seen:
                raise ValueError('같은 인물·장·사슬의 면 설정이 겹친다')
            seen.add(key)
            yield f, event['actor'], CHAINS.index(chain), np.array([np.interp(f, times, values[:, i]) for i in range(3)])


def extension_ids(slot, chain_index):
    first = AO0 + slot*100 + 12 + chain_index*20
    return list(range(first, first+13))


def apply_surface(root, scene, style, width, crop_y, colors=('blue', 'red')):
    result = copy.deepcopy(root)
    frames = result.findall('Frame')
    if len(frames) != scene['end'] - scene['start'] + 1:
        raise ValueError('면 입력의 장 수가 다르다')
    sx, sy = width/100, width*float(root.get('HeightWidthRatio'))/100
    if not np.isfinite([sx, sy]).all() or min(sx, sy) <= 0:
        raise ValueError('면의 좌표계가 잘못됐다')
    to_px = lambda p: np.array([float(p.get('X'))*sx, float(p.get('Y'))*sy+crop_y])
    records = []
    for f, actor, chain_index, radii in events(style, scene):
        if actor not in colors:
            raise ValueError('면 인물이 설정에 없다')
        i, slot = f-scene['start'], colors.index(actor)
        frame = frames[i]
        aa = {int(a.get('ID')): a for a in frame.findall('AO')}
        ids = extension_ids(slot, chain_index)
        if any(oid in aa for oid in ids):
            raise ValueError('면 객체 ID가 기존 파일과 충돌한다')
        chain = CHAINS[chain_index]
        bones = [aa.get(AO0+slot*100+oid) for oid in chain]
        if any(a is None or a.get('Color') != str(LINE_COLOR[actor]) for a in bones):
            raise ValueError('면을 만들 기존 사슬이 없거나 숨겨져 있다')
        ps = [a.findall('AP') for a in bones]
        centers = [ps[0][0], ps[0][1], ps[1][1]]
        if chain_index < 2:
            centers = [ps[0][1], ps[0][0], ps[1][0]]
        curves = contour([to_px(p) for p in centers], radii)
        point_base = 20_000_000 + i*10000 + slot*1000 + chain_index*100
        nodes = []
        def make(oid, typ, xy, pids, order):
            a = ET.fromstring(f'<AO ID="{oid}" TypeId="{typ}" DrawOrder="{order}" '+STYLE.format(c=0, th='0.100')+'/>')
            for k, (v, pid) in enumerate(zip(xy, pids)):
                ET.SubElement(a, 'AP', ID=str(pid), Index=str(k), Flags='4' if k != 1 or typ == '1' else '5',
                              X=f'{v[0]/sx:.4f}', Y=f'{(v[1]-crop_y)/sy:.4f}')
            return a
        for k, curve in enumerate(curves):
            nodes.append(make(ids[k], '3', curve, range(point_base+k*3, point_base+k*3+3), AO0+slot*100+chain[0]))
        def link(a, b):
            ET.SubElement(a, 'AC', ConnPtId=b.get('ID'))
            ET.SubElement(b, 'AC', ConnPtId=a.get('ID'))
        for k in range(10):
            link(nodes[k].findall('AP')[-1], nodes[(k+1)%10].findall('AP')[0])
        # 세 중심점과 면을 투명한 가지로 잇는다. 기존AC는 유지하고 링크만 추가한다.
        boundary = [nodes[0].findall('AP')[0], nodes[0].findall('AP')[1], nodes[0].findall('AP')[2]]
        for k, (center, endpoint) in enumerate(zip(centers, boundary)):
            spoke = make(ids[10+k], '1', [to_px(center), to_px(endpoint)],
                         [point_base+30+k*2, point_base+31+k*2], AO0+slot*100+chain[0])
            link(center, spoke.findall('AP')[0])
            link(endpoint, spoke.findall('AP')[1])
            nodes.append(spoke)
        for a in bones:
            a.set('Color', '0')
        head = aa[AO0+slot*100+1]
        position = list(frame).index(head)
        for k, node in enumerate(nodes):
            frame.insert(position+k, node)
        fill = ET.Element('FR', ID=str(28_000_000+i*100+slot*10+chain_index), Color=str(LINE_COLOR[actor]))
        for node in nodes[:10]:
            pp = node.findall('AP')
            ET.SubElement(fill, 'FS', Kind='0', ObjId=node.get('ID'), StartPtId=pp[0].get('ID'), EndPtId=pp[-1].get('ID'),
                          StartT='0', EndT='1', Contour='0')
        frame.append(fill)
        records.append(dict(frame=f, player_frame=i+1, actor=actor, segments=list(chain), radii_px=radii.tolist(),
                            added_objects=13, added_points=36, added_fills=1))
    return result, records


def audit_surface(root, scene, style, width, crop_y, colors=('blue', 'red')):
    """면을 벗긴 기존 뼈대 검사 + 실제 면 포함 전체 연결망 + 면 재생성 일치 검사."""
    base = copy.deepcopy(root)
    frames = base.findall('Frame')
    for f, actor, chain_index, _ in events(style, scene):
        slot, i = colors.index(actor), f-scene['start']
        frame = frames[i]
        ids = set(extension_ids(slot, chain_index))
        nodes = [a for a in frame.findall('AO') if int(a.get('ID')) in ids]
        extension_points = {p.get('ID') for a in nodes for p in a.findall('AP')}
        for point in frame.iter('AP'):
            for conn in list(point):
                if conn.get('ConnPtId') in extension_points:
                    point.remove(conn)
        for node in nodes:
            frame.remove(node)
        for fill in list(frame.findall('FR')):
            if any(int(s.get('ObjId')) in ids for s in fill.findall('FS')):
                frame.remove(fill)
        for a in frame.findall('AO'):
            if int(a.get('ID')) in {AO0+slot*100+v for v in CHAINS[chain_index]}:
                a.set('Color', str(LINE_COLOR[actor]))
    report, _, _ = audit(base, scene, colors, width, crop_y)
    rebuilt, records = apply_surface(base, scene, style, width, crop_y, colors)
    errors = report['errors']
    if ET.tostring(rebuilt) != ET.tostring(root):
        errors.append('면의 윤곽·채움·연결이 재생성 결과와 다르다')
    seen = set()
    for i, frame in enumerate(root.findall('Frame')):
        for slot, color in enumerate(colors):
            nodes = [a for a in frame.findall('AO') if (int(a.get('ID'))-AO0)//100 == slot]
            if not nodes:
                continue
            points = {p.get('ID'): p for a in nodes for p in a.findall('AP')}
            if seen.intersection(points) or len(points) != sum(len(a.findall('AP')) for a in nodes):
                errors.append(f'{i+scene["start"]} {color} 면 포함 점ID 중복')
            seen.update(points)
            if sum(p.get('Flags') == '3' for p in points.values()) != 1:
                errors.append('면 포함 인물의 파란점 수 오류')
            graph = {p: set() for p in points}
            for node in nodes:
                pp = node.findall('AP')
                for a, b in zip(pp, pp[1:]):
                    graph[a.get('ID')].add(b.get('ID'))
                    graph[b.get('ID')].add(a.get('ID'))
            for pid, point in points.items():
                for conn in point.findall('AC'):
                    target = conn.get('ConnPtId')
                    if target not in points or any(point.get(k) != points[target].get(k) for k in ('X', 'Y')):
                        errors.append('면 연결의 인물 혼입 또는 좌표 분리')
                    else:
                        graph[pid].add(target)
            visited, todo = set(), [next(iter(points))]
            while todo:
                pid = todo.pop()
                if pid not in visited:
                    visited.add(pid)
                    todo.extend(graph[pid]-visited)
            if visited != set(points):
                errors.append('면 포함 연결망이 분리됐다')
    report.update(surface_records=records, full_unique_points=len(seen),
                  full_objects=sum(len(f.findall('AO')) for f in root.findall('Frame')),
                  full_fills=sum(len(f.findall('FR')) for f in root.findall('Frame')))
    return report, base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('out')
    parser.add_argument('--style', required=True)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--crop-y', type=float, default=0)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    if Path(args.input).resolve() == Path(args.out).resolve():
        parser.error('입력 기준판을 덮어쓸 수 없다')
    scene, rig = load_scene(args.scene)
    style = json.loads(Path(args.style).read_text(encoding='utf-8'))
    if style.get('input_sfa_sha256') != digest(args.input):
        parser.error('면 설정의 기준 SFA 해시가 다르다')
    root, _ = apply_surface(read_sfa(args.input), scene, style, args.width, args.crop_y)
    report, _ = audit_surface(root, scene, style, args.width, args.crop_y)
    if report['errors']:
        parser.error('; '.join(report['errors'][:5]))
    with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('limb_surface.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    report.update(settings=rig, input_sha256=digest(args.input), style_sha256=digest(args.style), output_sha256=digest(args.out))
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"연속 면 {len(report['surface_records'])}개 인물·장, 연결·접촉 검사 위반0건")


if __name__ == '__main__':
    main()
