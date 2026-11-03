"""장면 데이터로 부위별 선 굵기를 적용한다. 좌표·구조·가시성은 바꾸지 않는다."""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

from stickman_clip import AO0
from stickman_quality import audit, digest, read_sfa
from stickman_scene import load_scene, weight


def apply_thickness(root, scene, style, colors=('blue', 'red')):
    """기존 인물 굵기 × 부위별 배율. 하나의 선 조각 안에서는 굵기가 일정하다."""
    if style.get('schema') != 1 or style.get('rig') != scene['rig']:
        raise ValueError('부위 굵기 설정과 뼈대 버전이 다르다')
    if style.get('start') != scene['start'] or style.get('end') != scene['end']:
        raise ValueError('부위 굵기와 장면 범위가 다르다')
    if style.get('source_sha256') != scene.get('source_sha256'):
        raise ValueError('부위 굵기와 원본 영상 해시가 다르다')
    result = copy.deepcopy(root)
    frames = result.findall('Frame')
    if len(frames) != scene['end'] - scene['start'] + 1:
        raise ValueError('입력 SFA와 장면의 장 수가 다르다')
    owners, changes = set(), []
    for event in style.get('tracks', []):
        actor = event['actor']
        start, end = event['start'], event['end']
        feather = event.get('feather', 2)
        if actor not in colors or not scene['start'] <= start <= end <= scene['end']:
            raise ValueError('부위 굵기의 인물·구간이 처리 대상 밖이다')
        if not isinstance(feather, int) or feather < 0 or any(start < c <= end for c in scene.get('cuts', [])):
            raise ValueError('부위 굵기의 완화 길이·컷 범위가 잘못됐다')
        keys = event['keys']
        times = sorted(int(t) for t in keys)
        if not times or any(not start <= t <= end for t in times):
            raise ValueError('부위 굵기 키가 없거나 구간 밖이다')
        segments = set(keys[str(times[0])])
        if not segments or not segments <= {str(i) for i in range(1, 11)}:
            raise ValueError('굵기를 바꿀 조각은1–10이어야 한다')
        if any(set(v) != segments for v in keys.values()):
            raise ValueError('모든 굵기 키의 조각 목록이 같아야 한다')
        values = {s: np.asarray([keys[str(t)][s] for t in times], float) for s in segments}
        if any(not np.isfinite(v).all() or (v <= 0).any() for v in values.values()):
            raise ValueError('부위 굵기 배율은 유한한 양수여야 한다')
        for i, frame in enumerate(frames):
            f = scene['start'] + i
            w = weight(f, start, end, feather, scene.get('cuts', []))
            if not w:
                continue
            for segment in sorted(segments, key=int):
                owner = f, actor, segment
                if owner in owners:
                    raise ValueError('같은 장·인물·부위의 굵기 설정이 겹친다')
                owners.add(owner)
                oid = AO0 + colors.index(actor) * 100 + int(segment)
                obj = next((a for a in frame.findall('AO') if int(a.get('ID')) == oid), None)
                if obj is None:
                    if start <= f <= end:
                        raise ValueError('굵기를 바꿀 인물이 해당 장에 없다')
                    continue
                old = float(obj.get('ThicknessScale'))
                ratio = float(np.interp(f, times, values[segment]))
                factor = 1 + w * (ratio - 1)
                new = round(old * factor, 3)
                if not np.isfinite(new) or new <= 0:
                    raise ValueError('저장 정밀도에서 굵기가0 이하 또는 비유한 값이다')
                if new != old:
                    obj.set('ThicknessScale', f'{new:.3f}')
                    changes.append(dict(frame=f, player_frame=i+1, actor=actor, segment=int(segment),
                                        weight=w, factor=factor, before=old, after=new))
    return result, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('out')
    parser.add_argument('--style', required=True)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--crop-y', type=float, default=0)
    parser.add_argument('--colors', nargs='+', default=['blue', 'red'])
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    if Path(args.input).resolve() == Path(args.out).resolve():
        parser.error('비교 기준인 입력 파일을 덮어쓸 수 없다')
    scene, rig = load_scene(args.scene)
    style = json.loads(Path(args.style).read_text(encoding='utf-8'))
    actual_sha = digest(args.input)
    if style.get('input_sfa_sha256') and style['input_sfa_sha256'] != actual_sha:
        parser.error('부위 굵기 설정의 입력 SFA 해시가 다르다')
    root, changes = apply_thickness(read_sfa(args.input), scene, style, args.colors)
    report, _, _ = audit(root, scene, args.colors, args.width, args.crop_y)
    if report['errors']:
        parser.error('부위 굵기 적용 뒤 구조·접촉 검사 실패')
    with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('part_thickness.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    report.update(input_sha256=actual_sha, style_sha256=digest(args.style), output_sha256=digest(args.out),
                  settings=rig, thickness_changes=changes)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"부위 굵기 적용 {len(changes)}개 선·장, 구조·접촉 위반0건")


if __name__ == '__main__':
    main()
