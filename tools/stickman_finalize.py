"""저장한 투영 SFA에 장면 설정을 다시 적용하고 실제 파일을 검사한다. 재피팅하지 않는다."""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

import stickman_clip as sc
from stickman_projection import guard_hidden_chains
from stickman_quality import audit, decode, digest, read_sfa
from stickman_scene import apply_scene, load_scene


def finalize(base, scene_path, out, width, crop_y, colors=('blue', 'red'), hidden_path=None, expected_sha=None):
    """원본 입력·장면·가림 근거를 분리하여 기록한다. 입력 파일 덮어쓰기는 금지한다."""
    if Path(base).resolve() == Path(out).resolve():
        raise ValueError('보정 전 입력을 덮어쓸 수 없다')
    actual_sha = digest(base)
    if expected_sha and actual_sha != expected_sha:
        raise ValueError('보정 전 입력 SFA 해시가 다르다')
    scene, rig = load_scene(scene_path)
    root = read_sfa(base)
    poses, styles = decode(root, colors, width, crop_y)
    frames = list(range(scene['start'], scene['end'] + 1))
    if len(poses) != len(frames):
        raise ValueError('입력과 장면의 장 수가 다르다')
    hidden_changes = []
    if hidden_path:
        hidden = json.loads(Path(hidden_path).read_text(encoding='utf-8'))
        if hidden['source_sha256'] != scene.get('source_sha256'):
            raise ValueError('가림 관측과 장면의 원본 영상 해시가 다르다')
        seen = set()
        for row in hidden['rows']:
            f, actor = row['frame'], row['actor']
            if (f, actor) in seen or f not in frames or actor not in colors:
                raise ValueError('가림 관측의 장·인물 중복/범위 오류')
            seen.add((f, actor))
            pose = poses[f - frames[0]][actor]
            if pose is None:
                raise ValueError('가림 관측에 해당하는 인물이 없다')
            wax = np.asarray(row['axis_weights'], float)
            side = np.asarray(row['sides'], int)
            if wax.shape != (23, 2) or side.shape != (23,) or not np.isfinite(wax).all() or (wax < 0).any() or not np.isin(side, range(5)).all():
                raise ValueError('가림 관측의 축 가중치·경계 코드 오류')
            joints = {k: np.array([v]) for k, v in pose.items() if not k.startswith('_')}
            changes = guard_hidden_chains(joints, (wax[None], side[None], None))
            for change in changes:
                pose[change['joint']] = joints[change['joint']][0]
                hidden_changes.append(dict(frame=f, actor=actor, joint=change['joint'], axis=change['axis']))
    # 이전 장면의 부분 인물/접촉 결과를 입력으로 재사용하지 말고 보정 전 투영본을 쓴다.
    poses, events = apply_scene(poses, frames, scene)
    root = copy.deepcopy(root)
    height = width * float(root.get('HeightWidthRatio'))
    for i, frame in enumerate(root.findall('Frame')):
        for node in list(frame):
            if node.tag in ('AO', 'FR'):
                frame.remove(node)
        for slot, actor in enumerate(colors):
            pose = poses[i][actor]
            if pose is None:
                continue
            shot = sum(c <= frames[i] for c in scene.get('cuts', []))
            available = [k for c, k in styles if c == actor and sum(cut <= frames[k] for cut in scene.get('cuts', [])) == shot]
            if not available:
                raise ValueError('같은 컷에 부분 인물의 굵기 기준이 없다')
            thick = styles[actor, min(available, key=lambda k: abs(i-k))]
            fragment = ET.fromstring('<Frame>' + sc.person_aos(i, slot, pose,
                lambda v: (v[0] / (width / 100), (v[1] - crop_y) / (height / 100)), actor, thick,
                pose.get('_visible_segments')) + '</Frame>')
            frame.extend(fragment)
    # XML 직렬화 정밀도로 인한 오차까지 저장 전에 검사한다.
    root = ET.fromstring(ET.tostring(root, encoding='utf-8'))
    report, _, _ = audit(root, scene, colors, width, crop_y)
    if report['errors']:
        raise ValueError('저장 검사 실패: ' + '; '.join(report['errors'][:5]))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('stickman_final.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    report.update(input_sha256=actual_sha, sfa_sha256=digest(out), settings=rig, scene_events=events,
                  hidden_changes=hidden_changes, hidden_observations_sha256=digest(hidden_path) if hidden_path else None)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base')
    parser.add_argument('out')
    parser.add_argument('--scene', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--crop-y', type=float, default=0)
    parser.add_argument('--colors', nargs='+', default=['blue', 'red'])
    parser.add_argument('--hidden-observations', help='구버전 투영본용 축 가중치·경계 코드 JSON. 새 추출본은 공통 가림 보정이 이미 적용된다')
    parser.add_argument('--expect-input-sha256')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = finalize(args.base, args.scene, args.out, args.width, args.crop_y, args.colors,
                      args.hidden_observations, args.expect_input_sha256)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{report['frames']}장 저장·검사 완료: 구조·접촉 위반0, 가림 사슬 보정{len(report['hidden_changes'])}건")


if __name__ == '__main__':
    main()
