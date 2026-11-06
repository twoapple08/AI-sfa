"""수동 원본 궤적의 곡선 표현층 비교. 스미어 자동 검출/스타일 학습기가 아니다."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import event_context as C


def quad(p, t):
    p = np.asarray(p, float)
    return (1 - t)**2 * p[0] + 2 * t * (1 - t) * p[1] + t*t*p[2]


def segment(p, lo, hi):
    p = np.asarray(p, float)
    derivative = 2 * ((1-lo)*(p[1]-p[0]) + lo*(p[2]-p[1]))
    return np.array([quad(p, lo), quad(p, lo) + (hi-lo)*derivative/2, quad(p, hi)])


def build(annotation, mode):
    if mode not in ('plain', 'variable_glow'):
        raise ValueError('알 수 없는 비교판')
    w, h = annotation['image_size']
    if min(w, h) <= 0 or not annotation['frames']:
        raise ValueError('영상 크기/장이 필요하다')
    root = ET.Element('Sequence', Name='curve_layer_review', HeightWidthRatio=str(h/w),
                      RatioX='16', RatioY='9', FrameCount=str(len(annotation['frames'])), BackgroundColor='-16777216')
    for n, row in enumerate(annotation['frames']):
        p = np.asarray(row['curve_px'], float)
        widths = np.asarray(row['widths_px'], float)
        if p.shape != (3, 2) or widths.shape != (3,) or not np.isfinite(p).all() or not np.isfinite(widths).all() or (widths <= 0).any():
            raise ValueError('유한한 곡선3점/양수 폭3개가 필요하다')
        f = ET.SubElement(root, 'Frame', ID=str(5000+n), Position=str(n), BackgroundColor='-16777216')
        ET.SubElement(f, 'LayerDef', ID='0', Name='effect_review', Visible='true', Locked='false')
        # 두 판에 같은9분할/대상ID를 사용.9는 프로브 설정이며 표현 상한/필수 문법이 아니다.
        for i in range(9):
            lo, hi = i/9, (i+1)/9
            thickness = float(np.interp((lo+hi)/2, [0,.5,1], widths)) if mode == 'variable_glow' else 12.
            # 원본화소 폭을 기존 서버/파일 선폭 단위로 대응한 검토용 근사.
            scale = thickness / (8 * 1.14 * w / 1920)
            active = row['active']
            glow = mode == 'variable_glow' and active
            a = ET.SubElement(f, 'AO', ID=str(9600000+i), TypeId='3', LayerId='0', DrawOrder=str(9600000+i),
                              Color=str(0xffffad22 if active else 0), ObjectScale='1', ThicknessScale=f'{scale:.6f}',
                              GlowRadius='6', GlowThickness='18', GlowColor=str(0xffff5400), GlowAlpha='.4' if glow else '0')
            for j, point in enumerate(segment(p, lo, hi)):
                pid = 20000000 + n*1000 + i*3 + j
                flags = 3 if (i,j)==(0,0) else 4 if j==0 else 5 if j==1 else 9
                ap = ET.SubElement(a, 'AP', ID=str(pid), Index=str(j), Flags=str(flags),
                                   X=f'{point[0]/w*100:.6f}', Y=f'{point[1]/h*100:.6f}')
                if j == 0 and i > 0: ET.SubElement(ap, 'AC', ConnPtId=str(pid-1))
                if j == 2 and i < 8: ET.SubElement(ap, 'AC', ConnPtId=str(pid+1))
    return root


def inspect(root, context, rows):
    C.validate(context)
    frames = root.findall('Frame')
    if len(frames) != len(rows) or len(frames) != len(context['source_indices']) or int(root.get('FrameCount')) != len(frames):
        raise ValueError('장 대응 불일치')
    seen = set()
    for n, (f, row) in enumerate(zip(frames, rows)):
        if int(f.get('Position')) != n: raise ValueError('장 순서 오류')
        aos = f.findall('AO')
        if [(a.get('ID'), a.get('TypeId'), a.get('LayerId')) for a in aos] != [(str(9600000+i),'3','0') for i in range(9)]:
            raise ValueError('표현층 대상/타입/레이어 불일치')
        points = [p for a in aos for p in a.findall('AP')]; by = {p.get('ID'): p for p in points}
        if len(points) != 27 or len(by) != 27 or seen & by.keys(): raise ValueError('점 ID 오류')
        if sum(p.get('Flags') == '3' for p in points) != 1: raise ValueError('뿌리 역할 오류')
        for i in range(8):
            left, right = aos[i].findall('AP')[2], aos[i+1].findall('AP')[0]
            if right.get('ID') not in [c.get('ConnPtId') for c in left.findall('AC')] or left.get('ID') not in [c.get('ConnPtId') for c in right.findall('AC')]:
                raise ValueError('곡선 사슬 연결 소실')
        for p in points:
            for c in p.findall('AC'):
                q = by.get(c.get('ConnPtId'))
                if q is None or any(p.get(k) != q.get(k) for k in ('X','Y')): raise ValueError('곡선 경계 연결 오류')
        if not row['active'] and any((int(a.get('Color'))>>24)&255 or float(a.get('GlowAlpha')) for a in aos):
            raise ValueError('소멸 장에 표현이 남음')
        seen.update(by)
    return dict(frames=len(frames), objects_per_frame=9, unique_points=len(seen), app_verified=False)


def save_review(annotation, event, directory):
    directory = directory.resolve()
    repo = Path(__file__).resolve().parents[1]
    if directory == repo or repo in directory.parents: raise ValueError('원본 유래 표현은 저장소 밖에 생성한다')
    if annotation['source_sha256'] != event['source']['sha256']: raise ValueError('원본 불일치')
    context = C.create(event, 0, [r['source_index'] for r in annotation['frames']])
    directory.mkdir(parents=True, exist_ok=True)
    records = {}
    for mode in ('plain','variable_glow'):
        root = build(annotation, mode)
        path = directory / (mode+'.sfa')
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
        with zipfile.ZipFile(path) as z: reopened=ET.fromstring(z.read('review.xml'))
        report = inspect(reopened, context, annotation['frames'])
        records[mode] = dict(asset_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), context=copy.deepcopy(context),
                             report=report,training_ready=False,fps_for_review=[24,24],kind='standalone_effect_layer_not_body_rig',
                             object_ids=[str(9600000+i) for i in range(9)],anchor_binding_status='manual_screen_position_no_rig_attachment')
        (directory/(mode+'.binding.json')).write_text(json.dumps(records[mode],ensure_ascii=False,indent=2)+'\n')
    return records
