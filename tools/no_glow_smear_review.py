"""수동 원본 팔 중심선+잔상 영역의 비발광 비교. 형상은 근사이며 학습 결과가 아니다."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import event_context as C
import sfa_event_review as AX

FX_IDS = [str(9700000 + g*10 + k) for g in range(2) for k in range(7)]


def build(annotation, with_smear):
    root, _ = AX.build(annotation, 'observed')
    root.set('Name', 'no_glow_arm_review')
    if not with_smear:
        return root
    width, height = annotation['image_size']
    # 성긴 반복 획의 길이 변주. 원본 손/손가락 윤곽을 복제한 값이 아닌 표현 시험 설정.
    lengths = [.72, .92, .81, 1., .88, .96, .7]
    for n, (frame, row) in enumerate(zip(root.findall('Frame'), annotation['frames'])):
        ET.SubElement(frame, 'LayerDef', ID='1', Name='smear_review', Visible='true', Locked='false')
        if len(row['smears']) != 2:
            raise ValueError('이번 프로브는 두 잔상 영역을 사용한다')
        for g, shape in enumerate(row['smears']):
            center = np.asarray(shape['center_px'], float)
            size = np.asarray(shape['size_px'], float)
            if center.shape != (2,) or size.shape != (2,) or not np.isfinite(center).all() or not np.isfinite(size).all() or (size <= 0).any():
                raise ValueError('유한한 중심/양수 퍼짐이 필요하다')
            for k in range(7):
                x = (k/6 - .5)*size[0]
                half = size[1]*lengths[k]/2
                slant = float(shape['slant_px'])
                if not np.isfinite(slant): raise ValueError('기울기는 유한해야 한다')
                xy = center + np.array([[x-slant/2, -half], [x+slant*.2, 0], [x+slant/2, half]])
                ao = ET.SubElement(frame, 'AO', ID=FX_IDS[g*7+k], TypeId='3', LayerId='1', DrawOrder=FX_IDS[g*7+k],
                    Color=str(0x990000ff if row['smear_active'] else 0), ThicknessScale='.45', ObjectScale='1',
                    GlowRadius='0', GlowThickness='0', GlowColor='0', GlowAlpha='0')
                for j, point in enumerate(xy):
                    ET.SubElement(ao, 'AP', ID=str(30000000+n*1000+g*100+k*3+j), Index=str(j),
                        Flags=('9','5','8')[j], X=f'{point[0]/width*100:.6f}', Y=f'{point[1]/height*100:.6f}')
    return root


def inspect(plain, smear, context, annotation):
    C.validate(context)
    if len(annotation['frames']) != len(context['source_indices']):
        raise ValueError('사건 장 대응 불일치')
    AX.inspect(plain, context)
    base = copy.deepcopy(smear)
    seen = set()
    for i, (a, b, row) in enumerate(zip(plain.findall('Frame'), base.findall('Frame'), annotation['frames'])):
        if row['source_index'] != context['source_indices'][i]: raise ValueError('원본 장 불일치')
        aos = b.findall('AO')
        if [x.get('ID') for x in aos[2:]] != FX_IDS: raise ValueError('잔상 대상 불일치')
        if [ET.tostring(x) for x in a.findall('AO')] != [ET.tostring(x) for x in aos[:2]]:
            raise ValueError('잔상 판에서 기존 팔 축이 변했다')
        points = [p for x in aos for p in x.findall('AP')]; ids = {p.get('ID') for p in points}
        if len(points) != 46 or len(ids) != 46 or seen & ids: raise ValueError('점 ID 오류')
        seen |= ids
        for x in aos:
            if any(float(x.get(k,'0')) != 0 for k in ('GlowRadius','GlowThickness','GlowAlpha')):
                raise ValueError('비발광 비교에 글로우가 남았다')
        if not row['smear_active'] and any((int(x.get('Color'))>>24)&255 for x in aos[2:]):
            raise ValueError('잔상 없는 장에 흔적이 남았다')
        for x in aos[2:]: b.remove(x)
    AX.inspect(base, context)
    if len(smear.findall('Frame')) != len(plain.findall('Frame')): raise ValueError('두 판 장 수 불일치')
    return dict(frames=len(annotation['frames']),plain_objects_per_frame=2,smear_objects_per_frame=16,
                unique_smear_version_points=len(seen),axes_identical=True,all_glow_zero=True,
                fx_rig_attachment_verified=False,app_editing_verified=False)


def save_review(annotation, event, directory):
    directory = directory.resolve()
    repo = Path(__file__).resolve().parents[1]
    if directory == repo or repo in directory.parents: raise ValueError('비공개 폴더가 필요하다')
    if annotation['source_sha256'] != event['source']['sha256']: raise ValueError('원본 불일치')
    context = C.create(event, 0, [r['source_index'] for r in annotation['frames']])
    plain, smear = build(annotation,False), build(annotation,True)
    report = inspect(plain,smear,context,annotation)
    directory.mkdir(parents=True,exist_ok=True)
    records = {}
    for name, root in [('axes_only',plain),('axes_with_smear',smear)]:
        path = directory/(name+'.sfa')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
        binding = dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),context=context,report=report,
                       training_ready=False,fps_for_review=[24,24],fx_binding='manual_screen_placement_not_following_rig')
        (directory/(name+'.binding.json')).write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
        records[name]=binding
    return records
