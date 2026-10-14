#!/usr/bin/env python3
"""Create controlled SFA attribute probes, NOT a claim of complete app emulation."""
import copy
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import sfa

N = 48
ROOT = Path(__file__).resolve().parent
CASES = [
    ('01_move', '이동', '기본 스틱맨이 좌우로 이동', 'coordinates'),
    ('02_rotate', '회전', '골반을 중심으로 몸 전체가 좌우로 기울어짐', 'coordinates'),
    ('03_stretch', '늘리기', '연결된 팔꿈치와 손목을 함께 움직여 오른팔 길이 변화', 'coordinates'),
    ('04_flip', '뒤집기', '한 팔을 든 비대칭 자세가 중간에 좌우 반전', 'coordinates'),
    ('05_scale', '크기', '발 부근 기준점에서 몸 크기가 작아졌다 커짐', 'coordinates'),
    ('06_color', '선 색상', '몸의 색이 빨강에서 파랑으로 변화', 'Color'),
    ('07_opacity', '불투명도', '파란 몸의 알파가 낮아졌다 높아짐', 'Color'),
    ('08_thickness', '개별 굵기', '오른팔 두 선만 굵어졌다 가늘어짐', 'ThicknessScale'),
    ('09_glow', '글로우', '어두운 배경에서 주황 선 주변의 푸른 글로우 변화', 'GlowRadius/Color/Alpha/Thickness'),
    ('10_curve', '곡선 변형', '곡선 하나의 제어점이 위아래로 이동', 'TypeId3/coordinates'),
    ('11_fill', '채우기 색상', '연결된 삼각형 안의 채우기 색이 변화', 'FR/FS'),
    ('12_fill_alpha', '채우기 불투명도', '삼각형의 선은 유지되고 내부만 반투명해짐', 'FR.Color'),
    ('13_layers', '레이어 표시', '겹친 두 스틱맨 중 위 레이어가 절반 지점에서 숨겨짐', 'LayerDef.Visible'),
    ('14_draw_order', '겹침 순서', '교차하는 빨강·파랑 굵은 선의 앞뒤가 절반 지점에서 바뀜', 'DrawOrder'),
    ('15_background', '배경색', '몸은 고정되고 배경색만 변화', 'Frame.BackgroundColor'),
    ('16_appear_delete', '요소 생성/삭제', '스틱맨 옆의 독립 원이 중간에 생겼다 없어짐', 'AO presence'),
]


def argb(a, r, g, b):
    return str((int(a) << 24) | (int(r) << 16) | (int(g) << 8) | int(b))


def primitive(oid, kind, points, color='-16777216', layer=0):
    obj = ET.Element('AO', {'ID': str(oid), 'TypeId': str(kind), 'Color': color,
        'LayerId': str(layer), 'DrawOrder': str(oid), 'ThicknessScale': '1.0',
        'ObjectScale': '1.0', 'GlowRadius': '0', 'GlowThickness': '20',
        'GlowColor': '4294967295', 'GlowAlpha': '0'})
    for i, (x, y) in enumerate(points):
        ET.SubElement(obj, 'AP', {'ID': str(oid*10+i), 'Flags': '3' if i == 0 else '9',
            'Index': str(i), 'X': str(x), 'Y': str(y)})
    return obj


def triangle(first_id=50, dx=0, color='-16777216'):
    # Shape and bidirectional connection graph follow observed line-based polygons.
    pts = [(42+dx, 30), (34+dx, 64), (58+dx, 64)]
    objects = [primitive(first_id+i, 1, [pts[i], pts[(i+1)%3]], color) for i in range(3)]
    for i in range(3):
        end = objects[i].findall('AP')[1]
        start = objects[(i+1)%3].findall('AP')[0]
        ET.SubElement(end, 'AC', {'ConnPtId': start.get('ID')})
        ET.SubElement(start, 'AC', {'ConnPtId': end.get('ID')})
    fill = ET.Element('FR', {'Color': argb(255, 250, 150, 30)})
    for obj in objects:
        a,b = obj.findall('AP')
        ET.SubElement(fill, 'FS', {'Kind':'0', 'ObjId':obj.get('ID'),
            'StartPtId':a.get('ID'), 'EndPtId':b.get('ID'), 'StartT':'0.0','EndT':'1.0'})
    return objects, fill


def transform(objects, fn):
    for obj in objects:
        for p in obj.findall('AP'):
            x,y = fn(float(p.get('X')), float(p.get('Y')))
            p.set('X', str(x)); p.set('Y', str(y))


def clone_rig(objects, offset=100):
    clone = copy.deepcopy(objects)
    remap = {p.get('ID'):str(int(p.get('ID'))+offset*10) for o in clone for p in o.findall('AP')}
    for obj in clone:
        obj.set('ID', str(int(obj.get('ID'))+offset))
        obj.set('DrawOrder', str(int(obj.get('DrawOrder'))+offset))
        for p in obj.findall('AP'):
            p.set('ID', remap[p.get('ID')])
            for c in p.findall('AC'):c.set('ConnPtId', remap[c.get('ConnPtId')])
    return clone


def frame_for(case, index, source):
    frame = copy.deepcopy(source)
    objects = frame.findall('AO')
    t = index/(N-1)
    pulse = math.sin(math.pi*t)**2
    if case == '01_move':
        transform(objects, lambda x,y:(x+15*math.sin(math.tau*t),y))
    elif case == '02_rotate':
        theta = math.radians(25*math.sin(math.tau*t))
        ratio = 9/16
        def rotate(x,y):
            px,py = (x-50)/ratio,y-40
            return 50+(px*math.cos(theta)-py*math.sin(theta))*ratio,40+px*math.sin(theta)+py*math.cos(theta)
        transform(objects, rotate)
    elif case == '03_stretch':
        # Same-location connected endpoints receive the same transform.
        for obj in objects[4:6]:
            for p in obj.findall('AP'):
                x,y=float(p.get('X')),float(p.get('Y'))
                p.set('X',str(50+(x-50)*(1+1.5*pulse)))
                p.set('Y',str(20+(y-20)*(1+0.3*pulse)))
    elif case == '04_flip':
        objects[5].findall('AP')[0].set('Y','15')
        if index >= N//2: transform(objects,lambda x,y:(100-x,y))
    elif case == '05_scale':
        scale = 0.65+0.35*pulse
        transform(objects, lambda x,y:(50+(x-50)*scale,62+(y-62)*scale))
    elif case in ('06_color','07_opacity'):
        rgb = argb(255,round(240*(1-t)),40,round(240*t)) if case=='06_color' else argb(round(255-223*pulse),30,90,230)
        for o in objects:o.set('Color',rgb)
    elif case == '08_thickness':
        for obj in objects[4:6]:obj.set('ThicknessScale',str(0.5+3.5*pulse))
    elif case == '09_glow':
        frame.set('BackgroundColor',argb(255,24,26,34))
        for obj in objects:
            obj.set('Color',argb(255,255,160,40))
            obj.set('GlowColor',argb(255,50,150,255))
            obj.set('GlowAlpha',str(round(255*pulse)))
            obj.set('GlowRadius',str(round(18*pulse)))
            obj.set('GlowThickness','30')
    elif case == '10_curve':
        for o in objects:frame.remove(o)
        frame.append(primitive(50,3,[(25,50),(50,15+65*t),(75,50)]))
    elif case in ('11_fill','12_fill_alpha'):
        for o in objects:frame.remove(o)
        group, fill = triangle()
        if case=='11_fill':fill.set('Color',argb(255,round(250*(1-t)),round(180*t),round(200*t)))
        elif case=='12_fill_alpha':fill.set('Color',argb(round(255-223*pulse),250,150,30))
        frame.extend(group);frame.append(fill)
    elif case == '13_layers':
        frame.append(ET.Element('LayerDef',{'ID':'1','Name':'Layer 2','Visible':'true' if index<N//2 else 'false','Locked':'false'}))
        clone = clone_rig(objects)
        transform(clone,lambda x,y:(x+3,y+2))
        for obj in objects:obj.set('Color',argb(255,240,50,50))
        for obj in clone:obj.set('LayerId','1');obj.set('Color',argb(255,40,90,235))
        frame.extend(clone)
    elif case == '14_draw_order':
        for o in objects:frame.remove(o)
        red=primitive(50,1,[(30,30),(70,70)],argb(255,240,40,40))
        blue=primitive(60,1,[(30,70),(70,30)],argb(255,30,90,235))
        for obj in (red,blue):obj.set('ThicknessScale','5.0')
        if index>=N//2:red.set('DrawOrder','100')
        frame.extend([red,blue])
    elif case == '15_background':
        frame.set('BackgroundColor',argb(255,round(255-90*pulse),round(255-25*pulse),255))
    elif case == '16_appear_delete' and N//3<=index<2*N//3:
        frame.append(primitive(70,2,[(72,35),(72,55)],argb(255,220,60,70)))
    return frame


def reidentify(frame, absolute_index, section):
    frame.set('ID',str(500000+absolute_index));frame.set('Position',str(absolute_index))
    # Separate section IDs prevent unintended correspondence across probe boundaries.
    object_map={o.get('ID'):str(section*1000+int(o.get('ID'))) for o in frame.findall('AO')}
    point_map={p.get('ID'):str(10000000+absolute_index*1000+j) for j,p in enumerate(frame.iter('AP'))}
    for obj in frame.findall('AO'):
        obj.set('ID',object_map[obj.get('ID')])
        obj.set('DrawOrder',str(section*1000+int(obj.get('DrawOrder'))))
    for point in frame.iter('AP'):point.set('ID',point_map[point.get('ID')])
    for c in frame.iter('AC'):c.set('ConnPtId',point_map[c.get('ConnPtId')])
    for fs in frame.iter('FS'):
        fs.set('ObjId',object_map[fs.get('ObjId')])
        for key in ('StartPtId','EndPtId'):fs.set(key,point_map[fs.get(key)])


def build_suite(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    template=ET.parse(ROOT/'examples/default_stickman.xml').getroot()
    combined=ET.Element('Sequence',dict(template.attrib))
    combined.set('Name','AI_sfa_feature_probes_v1')
    manifest={'status':'generated; current app verification pending',
        'recommended_fps':{'tween_fps':24,'playback_fps':24},
        'frames_per_case':N,'cases':[],
        'not_covered':['exact editor operations','ObjectScale-only semantics','perspective/bend UI equivalence','groups/ungroup','TweenLink','complex fills and holes','layer locking','editor-only settings','global thickness/FPS import initialization']}
    for section,(name,label,expected,attribute) in enumerate(CASES,1):
        sequence=ET.Element('Sequence',dict(template.attrib));sequence.set('Name',name)
        for i in range(N):
            frame=frame_for(name,i,template.find('Frame'))
            reidentify(frame,i,section);sequence.append(frame)
            cf=copy.deepcopy(frame);cf.set('ID',str(500000+len(combined)));cf.set('Position',str(len(combined)))
            # AP IDs must also be unique across the combined sequence.
            reidentify(cf,len(combined),0)
            combined.append(cf)
        sequence.set('FrameCount',str(N));sfa.write_sfa(sequence,destination/(name+'.sfa'))
        manifest['cases'].append({'id':name,'label_ko':label,'expected':expected,'attribute':attribute,
            'app_verified':False,'frame_start_1based':(section-1)*N+1,'frame_end_1based':section*N,
            'seconds_at_24fps':[(section-1)*2,section*2]})
    combined.set('FrameCount',str(len(combined)))
    sfa.write_sfa(combined,destination/'feature_probes_v1.sfa')
    manifest['total_frames']=len(combined)
    manifest['max_objects_per_frame']=max(len(f.findall('AO')) for f in combined.findall('Frame'))
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with ZipFile(destination/'feature_probes_v1.zip','w',ZIP_DEFLATED) as archive:
        for path in sorted(destination.glob('*.sfa')):archive.write(path,path.name)
        archive.write(destination/'manifest.json','manifest.json')
    return manifest


if __name__=='__main__':
    result=build_suite(ROOT/'examples/probes_v1')
    print(f"Built {len(result['cases'])} probes, {result['total_frames']} frames; app verification pending")
