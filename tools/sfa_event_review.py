"""수동 판독한 부분 중심선의 SFA 비교와 사건 문맥 결합. 자동 관절 추출기가 아니다."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import event_context as C

ROOT = Path(__file__).resolve().parents[1]
OBJECT_IDS = ['4560007', '4560008']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(annotations, mode):
    if mode not in ('observed', 'fixed_length_counterexample'):
        raise ValueError('알 수 없는 비교 모드')
    width, height = annotations['image_size']
    if width <= 0 or height <= 0 or not annotations['frames']:
        raise ValueError('크기와 판독 장이 필요하다')
    rows = [np.asarray(r['points_px'], dtype=float) for r in annotations['frames']]
    if any(r.shape != (3, 2) or not np.isfinite(r).all() for r in rows):
        raise ValueError('장마다 유한한 중심점3개가 필요하다')
    lengths = np.linalg.norm(np.diff(rows[-1], axis=0), axis=1)
    if (lengths <= 0).any():
        raise ValueError('길이가0인 기준 사슬')
    seq = ET.Element('Sequence', Name='partial_axis_review', HeightWidthRatio=str(height / width),
                     RatioX='16', RatioY='9', FrameCount=str(len(rows)), BackgroundColor='-1')
    output = []
    for i, points in enumerate(rows):
        points = points.copy()
        delta = np.diff(points, axis=0)
        if (np.linalg.norm(delta, axis=1) <= 0).any():
            raise ValueError('길이가0인 사슬')
        if mode == 'fixed_length_counterexample':
            directions = delta / np.linalg.norm(delta, axis=1)[:, None]
            points[1] = points[0] + directions[0] * lengths[0]
            points[2] = points[1] + directions[1] * lengths[1]
        output.append(points.tolist())
        frame = ET.SubElement(seq, 'Frame', BackgroundColor='-1', ID=str(5000 + i), Position=str(i))
        ET.SubElement(frame, 'LayerDef', ID='0', Name='partial_review', Visible='true', Locked='false')
        base = 5680000 + i * 1000
        for j, oid in enumerate(OBJECT_IDS):
            ao = ET.SubElement(frame, 'AO', ID=oid, TypeId='1', Color='-16776961', LayerId='0',
                               DrawOrder=oid, ThicknessScale='0.7', ObjectScale='1', GlowRadius='0',
                               GlowThickness='0', GlowColor='-1', GlowAlpha='0')
            for k in range(2):
                pid = base + j * 2 + k
                point = points[j + k]
                flags = ((3, 5), (33, 9))[j][k]
                ap = ET.SubElement(ao, 'AP', ID=str(pid), Index=str(k), Flags=str(flags),
                                   X=f'{point[0] / width * 100:.6f}', Y=f'{point[1] / height * 100:.6f}')
                if (j, k) == (0, 1): ET.SubElement(ap, 'AC', ConnPtId=str(base + 2))
                if (j, k) == (1, 0): ET.SubElement(ap, 'AC', ConnPtId=str(base + 1))
    return seq, output


def extend_to_tips(root, tips, image_size):
    """기존 두 선의 좌표/역할을 보존하고 마지막 끝에 발끝 선 하나를 연결한다."""
    result = copy.deepcopy(root)
    frames = result.findall('Frame')
    xy = np.asarray(tips, dtype=float)
    if xy.shape != (len(frames), 2) or not np.isfinite(xy).all():
        raise ValueError('장마다 유한한 발끝 좌표가 필요하다')
    width, height = image_size
    if width <= 0 or height <= 0:
        raise ValueError('영상 크기 오류')
    for frame, tip in zip(frames, xy):
        aos = frame.findall('AO')
        if [a.get('ID') for a in aos] != OBJECT_IDS:
            raise ValueError('기존 두 선 검토판만 확장할 수 있다')
        old_end = aos[1].findall('AP')[1]
        pid = max(int(p.get('ID')) for a in aos for p in a.findall('AP')) + 1
        new = ET.SubElement(frame, 'AO', **dict(aos[1].attrib, ID='4560009', DrawOrder='4560009'))
        start = ET.SubElement(new, 'AP', ID=str(pid), Index='0', Flags='4', X=old_end.get('X'), Y=old_end.get('Y'))
        ET.SubElement(start, 'AC', ConnPtId=old_end.get('ID'))
        ET.SubElement(old_end, 'AC', ConnPtId=str(pid))
        ET.SubElement(new, 'AP', ID=str(pid + 1), Index='1', Flags='9',
                      X=f'{tip[0] / width * 100:.6f}', Y=f'{tip[1] / height * 100:.6f}')
    return result


def inspect(root, context, object_ids=None):
    object_ids = list(OBJECT_IDS if object_ids is None else object_ids)
    if object_ids not in (OBJECT_IDS, OBJECT_IDS + ['4560009']):
        raise ValueError('지원하지 않는 부분 사슬')
    C.validate(context)
    frames = root.findall('Frame')
    if len(frames) != len(context['source_indices']) or int(root.get('FrameCount')) != len(frames):
        raise ValueError('문맥과 SFA 장 수가 다르다')
    seen, signature = set(), None
    for index, frame in enumerate(frames):
        if int(frame.get('Position')) != index:
            raise ValueError('SFA Position 순서 오류')
        aos = frame.findall('AO')
        if [a.get('ID') for a in aos] != object_ids:
            raise ValueError('부분 사슬 대상 객체 불일치')
        current = [(a.get('ID'), a.get('TypeId'), a.get('LayerId')) for a in aos]
        if signature is not None and signature != current:
            raise ValueError('장 사이 객체 타입/레이어 변경')
        signature = current
        points = [p for a in aos for p in a.findall('AP')]
        ids = {p.get('ID') for p in points}
        if len(points) != 2 * len(object_ids) or len(ids) != len(points) or seen & ids:
            raise ValueError('점 ID 중복 또는 장간 재사용')
        if sum(p.get('Flags') == '3' for p in points) != 1 or sum((int(p.get('Flags')) & 0x2f) == 0x21 for p in points) != 1:
            raise ValueError('뿌리/주황 관절 역할 오류')
        graph = {pid: set() for pid in ids}
        for ao in aos:
            pp = ao.findall('AP')
            graph[pp[0].get('ID')].add(pp[1].get('ID'))
            graph[pp[1].get('ID')].add(pp[0].get('ID'))
        by_id = {p.get('ID'): p for p in points}
        for p in points:
            for conn in p.findall('AC'):
                other = conn.get('ConnPtId')
                if other not in ids:
                    raise ValueError('끊어진 연결 참조')
                if any(p.get(k) != by_id[other].get(k) for k in ('X', 'Y')):
                    raise ValueError('부분 사슬 연결 좌표 분리')
                graph[p.get('ID')].add(other)
        visited, todo = set(), [points[0].get('ID')]
        while todo:
            pid = todo.pop()
            if pid not in visited:
                visited.add(pid); todo.extend(graph[pid] - visited)
        if visited != ids:
            raise ValueError('부분 사슬 연결망 분리')
        if any(by_id[points[1].get('ID')].get(k) != points[2].get(k) for k in ('X', 'Y')):
            raise ValueError('가운데 연결 좌표 분리')
        seen |= ids
    return dict(frames=len(frames), objects_per_frame=len(object_ids), unique_point_ids=len(seen),
                one_root_and_one_orange_joint_per_frame=True, all_connections_resolve=True,
                app_editing_verified=False)


def bind(path, context, role, object_ids=None):
    object_ids = list(OBJECT_IDS if object_ids is None else object_ids)
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('review.xml'))
    structure = inspect(root, context, object_ids)
    return dict(schema='sfa-event-review-binding/1', asset_sha256=digest(path),
                context=copy.deepcopy(context), context_sha256=hashlib.sha256(C.dumps(context).encode()).hexdigest(),
                object_binding=dict(actor_slot=context['actor_slot'], object_ids=object_ids),
                role=role, structure=structure, training_ready=False, fps_for_review=[24, 24])


def verify(path, manifest):
    if manifest.get('training_ready') is not False or manifest.get('fps_for_review') != [24, 24]:
        raise ValueError('검토/학습 상태 또는 재생 조건이 변경됐다')
    if manifest.get('schema') != 'sfa-event-review-binding/1' or digest(path) != manifest['asset_sha256']:
        raise ValueError('SFA가 변경됐다. 기존 사건 바인딩을 재사용할 수 없다')
    context = manifest['context']
    if hashlib.sha256(C.dumps(context).encode()).hexdigest() != manifest['context_sha256']:
        raise ValueError('문맥이 변경됐다. 재결합 검토가 필요하다')
    ids = manifest['object_binding']['object_ids']
    if manifest['object_binding'] != dict(actor_slot=context['actor_slot'], object_ids=ids) or ids not in (OBJECT_IDS, OBJECT_IDS + ['4560009']):
        raise ValueError('대상 객체 연결이 변경됐다')
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('review.xml'))
    return inspect(root, context, ids)


def comparison(annotations, output, evidence_dir):
    from PIL import Image, ImageDraw, ImageOps
    import sfa_render as R
    roots = {}
    for mode in ('fixed_length_counterexample', 'observed'):
        with zipfile.ZipFile(output / (mode + '.sfa')) as z:
            roots[mode] = ET.fromstring(z.read('review.xml'))
    width = 424
    height = round(width * annotations['image_size'][1] / annotations['image_size'][0])
    sheet = Image.new('RGB', (width * 3, (height + 30) * len(annotations['frames'])), 'white')
    draw = ImageDraw.Draw(sheet)
    previous = copy.deepcopy(R.PARAMS)
    try:
        R.PARAMS.update(thick_mul=width / 1920, pad=0)
        for i, row in enumerate(annotations['frames']):
            path = evidence_dir / f'f{row["source_index"]}.png'
            if digest(path) != row['image_sha256']:
                raise ValueError('검토 이미지의 지문이 판독 입력과 다르다')
            src = Image.open(path).convert('RGB').resize((width, height))
            y = i * (height + 30)
            sheet.paste(src, (0, y))
            draw.text((5, y + height + 4), f'Source index {row["source_index"]}', fill='black')
            for j, mode in enumerate(('fixed_length_counterexample', 'observed'), 1):
                root = roots[mode]
                axes = Image.fromarray(R.render_frame(root, root.findall('Frame')[i], width, height)).convert('RGB')
                back = Image.blend(src, Image.new('RGB', src.size, 'white'), .65)
                back.paste(Image.new('RGB', back.size, 'blue'), (0, 0), ImageOps.invert(axes.getchannel('R')))
                sheet.paste(back, (j * width, y))
                draw.text((j * width + 5, y + height + 4), 'A: fixed length counterexample' if j == 1 else 'B: manual projected axes', fill='black')
        sheet.save(output / 'comparison.png')
    finally:
        R.PARAMS.clear(); R.PARAMS.update(previous)


def create_review(annotations, event, output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('원본 유래 좌표/SFA는 저장소 밖 비공개 폴더에 생성한다')
    if annotations['source_sha256'] != event['source']['sha256']:
        raise ValueError('사건과 판독 자료의 원본이 다르다')
    context = C.create(event, 0, [r['source_index'] for r in annotations['frames']])
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for mode in ('observed', 'fixed_length_counterexample'):
        path = output / (mode + '.sfa')
        root, _ = build(annotations, mode)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('review.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
        manifest = bind(path, context, mode)
        verify(path, manifest)
        (output / (mode + '.binding.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        records[mode] = manifest
    (output / 'annotations.private.json').write_text(json.dumps(annotations, ensure_ascii=False, indent=2) + '\n')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('event', type=Path)
    parser.add_argument('--private-dir', required=True, type=Path)
    parser.add_argument('--evidence-dir', type=Path)
    args = parser.parse_args()
    records = create_review(json.loads(args.annotations.read_text()), json.loads(args.event.read_text()), args.private_dir.resolve())
    if args.evidence_dir:
        comparison(json.loads(args.annotations.read_text()), args.private_dir.resolve(), args.evidence_dir)
    print(json.dumps({k: v['structure'] for k, v in records.items()}, ensure_ascii=False))
