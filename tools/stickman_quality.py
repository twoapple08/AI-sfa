"""고정 2D 스틱맨의 저장 파일 검사. 움직임 후보는 판독용이며 자동 수정하지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

import stickman_clip as sc
from stickman_scene import JOINTS, keyed_value, load_scene


def digest(path):
    with open(path, 'rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def read_sfa(path):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith('.xml')]
        if len(names) != 1:
            raise ValueError('XML 하나가 있는 SFA가 필요하다')
        return ET.fromstring(archive.read(names[0]))


def decode(root, colors, width, crop_y):
    """직렬화된 점을 원본 영상 화소로 읽는다. 틀 밖 좌표도 보존한다."""
    if width <= 0 or not colors or len(set(colors)) != len(colors):
        raise ValueError('양수 가로폭과 중복 없는 인물 목록이 필요하다')
    height = width * float(root.get('HeightWidthRatio'))
    if not np.isfinite(height) or height <= 0:
        raise ValueError('양수 화면비가 필요하다')
    sx, sy = width / 100, height / 100
    poses, styles = [], {}
    names = {o: [p[1] for p in pts] for o, _, pts in sc.BODY}
    names[1] = ['head_t', 'head_b']
    for i, frame in enumerate(root.findall('Frame')):
        row = {}
        for slot, color in enumerate(colors):
            objects = {int(a.get('ID')) - sc.AO0 - slot * 100: a for a in frame.findall('AO')
                       if (int(a.get('ID')) - sc.AO0) // 100 == slot}
            if not objects:
                row[color] = None
                continue
            if set(objects) != set(range(1, 12)):
                raise ValueError(f'{i + 1}장 {color}: 고정11객체가 아니다')
            pose = {}
            for oid, joint_names in names.items():
                points = objects[oid].findall('AP')
                if len(points) != 2:
                    raise ValueError(f'{i + 1}장 {color}: 객체 점 수 오류')
                for name, point in zip(joint_names, points):
                    pose[name] = np.array([float(point.get('X')) * sx,
                                           float(point.get('Y')) * sy + crop_y])
            visible = [oid for oid in range(1, 11) if int(objects[oid].get('Color')) & 0xff000000]
            if visible != list(range(1, 11)):
                pose['_visible_segments'] = visible
            row[color] = pose
            styles[color, i] = float(objects[1].get('ThicknessScale'))
        poses.append(row)
    return poses, styles


def audit(root, scene, colors=('blue', 'red'), width=1152, crop_y=63, top=24, visibility_plan=None):
    """위반은 errors, 수치로 선별한 미확정 움직임은 review_candidates로 분리한다."""
    errors, seen, object_types = [], set(), {}
    poses, styles = decode(root, colors, width, crop_y)
    frames = root.findall('Frame')
    planned = {}
    for event in visibility_plan or []:
        actor, start, end = event['actor'], event['start'], event['end']
        visible = event['visible_segments']
        if (actor not in colors or not scene['start'] <= start <= end <= scene['end']
                or len(set(visible)) != len(visible) or not set(visible).issubset(range(1, 11))):
            errors.append('자동 표시 계획의 인물/범위/조각 오류')
            continue
        for frame in range(start, end+1):
            if (frame, actor) in planned:
                errors.append(f'{frame}: {actor} 자동 표시 계획 중복')
            planned[frame, actor] = sorted(visible)
    expected_count = scene['end'] - scene['start'] + 1
    if len(frames) != expected_count or int(root.get('FrameCount')) != len(frames):
        errors.append('장 수가 장면/Sequence와 다르다')
    appearances = fills = links = 0
    counts = {c: 0 for c in colors}
    expected = ET.fromstring('<Frame>' + sc.person_aos(0, 0, {n: np.array([20., 20.]) for n in JOINTS},
                                                     lambda p: p, colors[0]) + '</Frame>')
    expected_points = {int(p.get('ID')) - sc.PT0: p for p in expected.iter('AP')}
    for i, frame in enumerate(frames):
        f = scene['start'] + i
        def fail(message):
            errors.append(f'{f}: {message}')
        if int(frame.get('Position')) != i:
            fail('재생 위치 오류')
        all_objects = frame.findall('AO')
        if len({a.get('ID') for a in all_objects}) != len(all_objects):
            fail('객체 ID 중복')
        if any(not 0 <= (int(a.get('ID')) - sc.AO0) // 100 < len(colors) for a in all_objects):
            fail('설정에 없는 인물 객체')
        for slot, color in enumerate(colors):
            pose = poses[i][color]
            if pose is None:
                if ((f, color) in planned or any(part['actor'] == color and part['start'] <= f <= part['end']
                                               for part in scene.get('partials', []))):
                    fail(f'{color} 표시하기로 한 부분 인물 누락')
                continue
            counts[color] += 1
            expected_visible = list(range(1, 11))
            for partial in scene.get('partials', []):
                if partial['actor'] == color and partial['start'] <= f <= partial['end']:
                    expected_visible = sorted(partial['visible_segments'])
            expected_visible = planned.get((f, color), expected_visible)
            if sorted(pose.get('_visible_segments', range(1, 11))) != expected_visible:
                fail(f'{color} 장면에 없는 조각 숨김/표시')
            appearances += 1
            objects = [a for a in all_objects if (int(a.get('ID')) - sc.AO0) // 100 == slot]
            points = [p for a in objects for p in a.findall('AP')]
            pmap = {p.get('ID'): p for p in points}
            if len(pmap) != 22 or len(points) != 22 or seen.intersection(pmap):
                fail(f'{color} 점 ID 중복/재사용/개수 오류')
            seen.update(pmap)
            if sum(p.get('Flags') == '3' for p in points) != 1:
                fail(f'{color} 파란점 수 오류')
            base = sc.PT0 + i * 1000 + slot * 100
            adjacency = {k: set() for k in pmap}
            for a in objects:
                oid = int(a.get('ID')) - sc.AO0 - slot * 100
                signature = a.get('TypeId')
                if oid in object_types and object_types[oid] != signature:
                    fail(f'{color} 객체 형식 변화')
                object_types[oid] = signature
                if signature != ('2' if oid == 1 else '1'):
                    fail(f'{color} 객체 형식 오류')
                if int(a.get('DrawOrder')) != sc.AO0 + slot * 100 + (50 if oid == 1 else oid):
                    fail(f'{color} 그리기 순서 오류')
                if oid == 11 and a.get('Color') != '0':
                    fail(f'{color} 내부 연결선 노출')
                if not np.isfinite(float(a.get('ThicknessScale'))) or float(a.get('ThicknessScale')) <= 0:
                    fail(f'{color} 선 굵기 오류')
                ids = [p.get('ID') for p in a.findall('AP')]
                adjacency[ids[0]].add(ids[1])
                adjacency[ids[1]].add(ids[0])
            for pid, point in pmap.items():
                local = int(pid) - base
                template = expected_points.get(local)
                actual_links = sorted(int(c.get('ConnPtId')) - base for c in point.findall('AC'))
                if template is None or point.get('Flags') != template.get('Flags') or point.get('Index') != template.get('Index') or actual_links != sorted(int(c.get('ConnPtId')) - sc.PT0 for c in template.findall('AC')):
                    fail(f'{color} 점 Flags/연결/ID 틀 변화')
                xy = [float(point.get(k)) for k in ('X', 'Y')]
                if not np.isfinite(xy).all():
                    fail(f'{color} 비유한 좌표')
                for conn in point.findall('AC'):
                    links += 1
                    target = conn.get('ConnPtId')
                    if target not in pmap:
                        fail(f'{color} 인물 밖 연결')
                    else:
                        if any(abs(float(point.get(k)) - float(pmap[target].get(k))) > 1e-6 for k in ('X', 'Y')):
                            fail(f'{color} 연결점 좌표 분리')
                        adjacency[pid].add(target)
            visited, todo = set(), [next(iter(pmap))]
            while todo:
                pid = todo.pop()
                if pid not in visited:
                    visited.add(pid)
                    todo.extend(adjacency[pid] - visited)
            if len(visited) != 22:
                fail(f'{color} 연결망 분리')
            head_visible = 1 in pose.get('_visible_segments', range(1, 11))
            own_fills = [fill for fill in frame.findall('FR') if any(int(s.get('ObjId')) == sc.AO0 + slot * 100 + 1 for s in fill.findall('FS'))]
            fills += len(own_fills)
            if len(own_fills) != int(head_visible) or any(fill.get('Color') != '-1' for fill in own_fills):
                fail(f'{color} 흰 머리 채움 오류')
            for fill in own_fills:
                segs = fill.findall('FS')
                if (len(segs) != 1 or segs[0].get('Kind') != '1'
                        or segs[0].get('ObjId') != str(sc.AO0 + slot * 100 + 1)
                        or segs[0].get('Contour', '0') != '0'
                        or any(k in segs[0].attrib for k in ('StartPtId', 'EndPtId', 'StartT', 'EndT'))):
                    fail(f'{color} 머리 원 전체 채움 저장 형식 오류')
            if head_visible:
                center = (pose['head_t'] + pose['head_b']) / 2
                radius = np.linalg.norm(pose['head_t'] - pose['head_b']) / 2
                if np.linalg.norm(center - pose['neck']) - radius > .002:
                    fail(f'{color} 머리 접합 분리')
        if len(frame.findall('FR')) != sum(1 for c in colors if poses[i][c] is not None and 1 in poses[i][c].get('_visible_segments', range(1, 11))):
            fail('예상하지 않은 채움 영역')
    contact_results = []
    for event in scene.get('contacts', []):
        gaps = []
        for f in range(event['start'], event['end'] + 1):
            row = poses[f - scene['start']]
            if 'anchor_keys' in event:
                target = keyed_value(event['anchor_keys'], f)
            else:
                spec = event['target']
                target = row[spec[0]][spec[1]] if isinstance(spec, list) else (row[spec['actor']][spec['start']] * (1-spec['t']) + row[spec['actor']][spec['end']] * spec['t'])
            gaps.extend(float(np.linalg.norm(row[c][j] - target)) for c, j in event['members'])
        gap = max(gaps)
        contact_results.append(dict(id=event['id'], max_gap_px=gap))
        if gap > .002:
            errors.append(f"접촉 잔차: {event['id']}")
    candidates, overlap_candidates = [], []
    height = width * float(root.get('HeightWidthRatio'))
    for i, row in enumerate(poses):
        for actor, pose in row.items():
            if pose is None or '_visible_segments' in pose:
                continue
            scale = max(float(np.linalg.norm(pose['neck'] - pose['pelvis'])), 1.)
            for part, mid, end, hub in [('leg', 'kne', 'ank', 'pelvis'), ('arm', 'elb', 'wri', 'neck')]:
                points = [pose[f'{name}_{side}'] for name in (mid, end) for side in ('l', 'r')]
                # 틀 밖의 추정 사슬이나 접힌 짧은 사슬을 화면 안 중복 검출로 오해하지 않는다.
                if not all(0 <= p[0] <= width and crop_y <= p[1] <= crop_y + height for p in points):
                    continue
                gap = max(float(np.linalg.norm(points[k] - points[k+1])) for k in (0, 2)) / scale
                length = sum(float(np.linalg.norm(pose[f'{end}_{s}'] - pose[hub])) for s in ('l', 'r')) / (2 * scale)
                if gap < .05 and length > .25:
                    overlap_candidates.append(dict(frame=scene['start']+i, player_frame=i+1, actor=actor,
                                                   part=part, paired_gap_torso=gap, review_only=True))
    cuts = set(scene.get('cuts', []))
    for color in colors:
        for i in range(1, len(poses) - 1):
            f = scene['start'] + i
            if f in cuts or f + 1 in cuts:
                continue
            rows = [poses[k][color] for k in (i-1, i, i+1)]
            if any(row is None or '_visible_segments' in row for row in rows):
                continue
            scale = max(float(np.median([np.linalg.norm(r['neck'] - r['pelvis']) for r in rows])), 1.)
            ranked = []
            for joint in sorted(JOINTS):
                x, y, z = [r[joint] - r['pelvis'] for r in rows]
                ranked.append((float(np.linalg.norm(x-2*y+z) / scale), joint))
            value, joint = max(ranked)
            candidates.append(dict(frame=f, player_frame=i+1, actor=color, joint=joint,
                                   relative_acceleration_torso=value, review_only=True))
    candidates.sort(key=lambda r: (-r['relative_acceleration_torso'], r['frame'], r['actor']))
    return dict(schema=1, rig=scene['rig'], frames=len(frames), appearances=appearances,
                appearances_by_actor=counts, unique_points=len(seen), connections=links, white_heads=fills,
                errors=errors, contacts=contact_results, review_candidates=candidates[:top],
                visibility_plan_frames=len(planned),
                overlap_candidates=overlap_candidates,
                candidate_policy='컷·부분 인물 제외, 몸통 대비 상대 가속도 순위. 실제 빠른 동작과 오류를 구별하지 않으며 자동 보정/합격선이 아니다.'), poses, styles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sfa')
    parser.add_argument('--scene', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--crop-y', type=float, default=0)
    parser.add_argument('--colors', nargs='+', default=['blue', 'red'])
    parser.add_argument('--top', type=int, default=24)
    parser.add_argument('--surface', help='선택 면 표시층 설정. 면을 포함한 전체 연결망과 기존 뼈대를 함께 검사한다')
    parser.add_argument('--visibility-plan', help='자동 부분 구도 표시 계획 JSON. 표시 선택만 대조하며 포즈 정답/눈 합격은 검사하지 않는다')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    scene, rig = load_scene(args.scene)
    plan = None
    if args.visibility_plan:
        data = json.loads(Path(args.visibility_plan).read_text())
        if (data.get('schema') != 1 or data.get('start') != scene['start'] or data.get('end') != scene['end']
                or data.get('source_sha256') != scene.get('source_sha256')):
            parser.error('자동 표시 계획과 장면의 원본/범위가 다르다')
        plan = data['events']
    if args.surface:
        from stickman_limb_surface import audit_surface
        style = json.loads(Path(args.surface).read_text(encoding='utf-8'))
        report, _ = audit_surface(read_sfa(args.sfa), scene, style, args.width, args.crop_y, args.colors, visibility_plan=plan)
        report['surface_style_sha256'] = digest(args.surface)
    else:
        report, _, _ = audit(read_sfa(args.sfa), scene, args.colors, args.width, args.crop_y, args.top, visibility_plan=plan)
    report.update(sfa_sha256=digest(args.sfa), settings=rig)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{report['frames']}장 검사: 구조·접촉 위반 {len(report['errors'])}건, 눈 판독 후보 {len(report['review_candidates'])}건")
    raise SystemExit(int(bool(report['errors'])))


if __name__ == '__main__':
    main()
