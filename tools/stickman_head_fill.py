"""기존 스틱맨 SFA의 머리 채움 저장 형식만 고친다. 포즈·뼈대·근경 면은 보존한다."""
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from stickman_clip import AO0
from stickman_quality import audit, digest, read_sfa
from stickman_scene import load_scene


def repair(root, colors=('blue', 'red')):
    """명시한 고정 리그의 흰 머리만 수정한다. 다른 채움을 추측해서 바꾸지 않는다."""
    result = copy.deepcopy(root)
    changes = []
    for i, frame in enumerate(result.findall('Frame')):
        objects = {a.get('ID'): a for a in frame.findall('AO')}
        for slot, actor in enumerate(colors):
            head_id = str(AO0 + slot*100 + 1)
            head = objects.get(head_id)
            if head is None:
                continue
            if head.get('TypeId') != '2' or len(head.findall('AP')) != 2:
                raise ValueError('고정 리그의 머리 원이 아니다')
            fills = [f for f in frame.findall('FR') if any(s.get('ObjId') == head_id for s in f.findall('FS'))]
            if not (int(head.get('Color')) & 0xff000000) and not fills:
                continue
            if len(fills) != 1 or fills[0].get('Color') != '-1' or len(fills[0].findall('FS')) != 1:
                raise ValueError('흰 머리 단일 채움이 아니므로 자동 수정을 거부한다')
            seg = fills[0].find('FS')
            if seg.get('Contour', '0') != '0':
                raise ValueError('머리 채움 외곽 번호가 다르다')
            desired = dict(Kind='1', ObjId=head_id, Contour='0')
            if seg.attrib != desired:
                before = dict(seg.attrib)
                seg.attrib.clear()
                seg.attrib.update(desired)
                changes.append(dict(index=i, actor=actor, before=before, after=desired))
    return result, changes


def convert(source, out, scene_path, width, crop_y, expected_sha, surface_path=None):
    if Path(source).resolve() == Path(out).resolve():
        raise ValueError('입력 SFA를 덮어쓸 수 없다')
    if digest(source) != expected_sha:
        raise ValueError('입력 SFA 해시가 다르다')
    scene, rig = load_scene(scene_path)
    root, changes = repair(read_sfa(source))
    root = ET.fromstring(ET.tostring(root, encoding='utf-8'))
    if surface_path:
        from stickman_limb_surface import audit_surface
        style = json.loads(Path(surface_path).read_text(encoding='utf-8'))
        report, _ = audit_surface(root, scene, style, width, crop_y)
    else:
        report, _, _ = audit(root, scene, width=width, crop_y=crop_y)
    if report['errors']:
        raise ValueError('저장 검사 실패: '+ '; '.join(report['errors'][:5]))
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('head_fill_fixed.xml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    report.update(input_sha256=expected_sha, output_sha256=digest(out), settings=rig, head_fill_changes=changes)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('out')
    parser.add_argument('--scene', required=True)
    parser.add_argument('--width', required=True, type=int)
    parser.add_argument('--crop-y', type=float, default=0)
    parser.add_argument('--expect-input-sha256', required=True)
    parser.add_argument('--surface')
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = convert(args.input, args.out, args.scene, args.width, args.crop_y, args.expect_input_sha256, args.surface)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"머리 채움 형식 {len(report['head_fill_changes'])}건 수정, 저장 검사 오류0건")


if __name__ == '__main__':
    main()
