"""고정 뼈대에 장면별 접촉·보완 관측·부분 인물 설정을 적용한다."""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

RIG_PATH = Path(__file__).resolve().parents[1] / 'profiles' / 'stickman_2d_v1.json'
JOINTS = {'neck', 'pelvis', 'elb_l', 'elb_r', 'wri_l', 'wri_r', 'kne_l', 'kne_r', 'ank_l', 'ank_r', 'head_t', 'head_b'}
ENDPOINTS = {'wri_l', 'wri_r', 'ank_l', 'ank_r'}


def rig_layout_fingerprint():
    """실제 직렬화기의 조각·Flags·AC·그림 순서도 고정 프로필과 대조한다."""
    from stickman_clip import person_aos, AO0, PT0
    pose = {name: np.array([20., 20.]) for name in JOINTS}
    pose.update(head_t=np.array([20., 10.]), pelvis=np.array([20., 40.]))
    frame = ET.fromstring('<Frame>' + person_aos(0, 0, pose, lambda p: p, 'blue') + '</Frame>')
    layout = [dict(id=int(a.get('ID'))-AO0, type=a.get('TypeId'), order=int(a.get('DrawOrder'))-AO0,
                   visible=a.get('Color') != '0',
                   points=[dict(id=int(p.get('ID'))-PT0, flags=p.get('Flags'), index=p.get('Index'),
                                links=sorted(int(c.get('ConnPtId'))-PT0 for c in p.findall('AC'))) for p in a.findall('AP')])
              for a in frame.findall('AO')]
    fills = [dict(color=f.get('Color'), segments=[dict(kind=s.get('Kind'), object=int(s.get('ObjId'))-AO0,
                  contour=s.get('Contour', '0'), edge_fields=sorted(k for k in ('StartPtId', 'EndPtId', 'StartT', 'EndT') if k in s.attrib))
                  for s in f.findall('FS')]) for f in frame.findall('FR')]
    return hashlib.sha256(json.dumps(dict(objects=layout, fills=fills),
                                     sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_scene(path):
    from pose_to_stickman import BODY
    scene = json.loads(Path(path).read_text(encoding='utf-8'))
    rig = json.loads(RIG_PATH.read_text(encoding='utf-8'))
    digest = hashlib.sha256(json.dumps(BODY, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    if (digest != rig['base_layout_sha256'] or rig_layout_fingerprint() != rig['layout_sha256']
            or scene.get('rig') != rig['id'] or scene.get('schema') != 1):
        raise ValueError('장면 설정과 고정 뼈대 버전이 다르다')
    unknown = set(scene) - {'schema', 'rig', 'source_sha256', 'start', 'end', 'cuts', 'tracks', 'partials', 'contacts', 'occlusions', 'description'}
    if unknown:
        raise ValueError(f'알 수 없는 장면 항목: {sorted(unknown)}')
    return scene, dict(id=rig['id'], profile_sha256=hashlib.sha256(RIG_PATH.read_bytes()).hexdigest(),
                       scene_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())


def weight(frame, start, end, feather, cuts):
    if sum(c <= frame for c in cuts) != sum(c <= start for c in cuts):
        return 0.
    d = max(start - frame, frame - end, 0)
    if d == 0:
        return 1.
    if feather <= 0 or d >= feather:
        return 0.
    return float((1 + np.cos(np.pi * d / feather)) / 2)


def keyed_value(keys, frame):
    times = sorted(int(t) for t in keys)
    values = np.asarray([keys[str(t)] for t in times], float)
    if not times or values.shape != (len(times), 2) or not np.isfinite(values).all():
        raise ValueError('키 좌표는 유한한2D 화소 좌표여야 한다')
    return np.array([np.interp(frame, times, values[:, axis]) for axis in (0, 1)])


def apply_scene(poses, frames, scene):
    """입력 불변. 좌표만 바꾸며 인물 사이 AC 연결이나 새 마디를 만들지 않는다."""
    if not frames or scene['start'] != frames[0] or scene['end'] != frames[-1]:
        raise ValueError('장면 설정과 처리 장 범위가 다르다')
    cuts = scene.get('cuts', [])
    result = copy.deepcopy(poses)
    report = {'partials': [], 'tracks': [], 'contacts': []}
    from stickman_occlusion import bridge_occlusions
    result, report['occlusions'] = bridge_occlusions(result, frames, scene.get('occlusions', []), cuts)
    for spec in [*scene.get('partials', []), *scene.get('tracks', []), *scene.get('contacts', [])]:
        if not frames[0] <= spec['start'] <= spec['end'] <= frames[-1] or any(spec['start'] < c <= spec['end'] for c in cuts):
            raise ValueError('이벤트는 처리 범위·한 컷 안에 있어야 한다')
    # 부분 인물도 같은11객체 틀을 쓰고 보이는 조각만 표시한다.
    for part in scene.get('partials', []):
        actor = part['actor']
        valid = [i for i, row in enumerate(poses) if row.get(actor) is not None]
        if not valid or not set(part['visible_segments']).issubset(range(1, 11)):
            raise ValueError('부분 인물의 기존 틀 또는 가시 조각이 잘못됐다')
        for i, frame in enumerate(frames):
            if not part['start'] <= frame <= part['end']:
                continue
            if result[i].get(actor) is not None:
                raise ValueError('부분 인물이 기존 인물을 덮어쓰려고 한다')
            nearest = min(valid, key=lambda n: abs(n - i))
            template = copy.deepcopy(poses[nearest][actor])
            pelvis = keyed_value({t: v['pelvis'] for t, v in part['keys'].items()}, frame)
            delta = pelvis - template['pelvis']
            j = {k: np.asarray(v, float) + delta for k, v in template.items() if k in JOINTS}
            for name in next(iter(part['keys'].values())):
                if name not in JOINTS:
                    raise ValueError(f'알 수 없는 관절: {name}')
                j[name] = keyed_value({t: v[name] for t, v in part['keys'].items()}, frame)
            j['_visible_segments'] = list(part['visible_segments'])
            result[i][actor] = j
            report['partials'].append(dict(frame=frame, actor=actor, visible_segments=part['visible_segments']))
    for track in scene.get('tracks', []):
        actor = track['actor']
        for i, frame in enumerate(frames):
            w = weight(frame, track['start'], track['end'], track.get('feather', 2), cuts)
            j = result[i].get(actor)
            if not w or j is None:
                continue
            for name in next(iter(track['keys'].values())):
                if name not in JOINTS:
                    raise ValueError(f'알 수 없는 관절: {name}')
                target = keyed_value({t: v[name] for t, v in track['keys'].items()}, frame)
                j[name] = np.asarray(j[name]) * (1 - w) + target * w
            report['tracks'].append(dict(frame=frame, actor=actor, weight=w))
    # 모든 접촉은 같은 입력 좌표를 기준으로 풀어 이벤트 나열 순서에 의존하지 않게 한다.
    reference = copy.deepcopy(result)
    owners = set()
    for event in scene.get('contacts', []):
        for actor, joint in event['members']:
            if joint not in ENDPOINTS:
                raise ValueError('접촉 이동점은 손목·발목 끝점이어야 한다')
        for i, frame in enumerate(frames):
            w = weight(frame, event['start'], event['end'], event.get('feather', 2), cuts)
            if not w:
                continue
            members = event['members']
            owned = {(frame, actor, joint) for actor, joint in members}
            if owners & owned:
                raise ValueError('같은 장·끝점에 접촉 이벤트가 겹친다')
            owners.update(owned)
            if any(result[i].get(a) is None for a, _ in members):
                if event['start'] <= frame <= event['end']:
                    raise ValueError(f'접촉 인물이 없는 장: {frame}')
                continue
            if 'anchor_keys' in event:
                target = keyed_value(event['anchor_keys'], frame)
            else:
                src = event['target']
                if isinstance(src, list):
                    target = np.asarray(reference[i][src[0]][src[1]], float)
                else:
                    j = reference[i][src['actor']]
                    target = np.asarray(j[src['start']]) * (1 - src['t']) + np.asarray(j[src['end']]) * src['t']
            before = [float(np.linalg.norm(np.asarray(result[i][a][n]) - target)) for a, n in members]
            for actor, name in members:
                result[i][actor][name] = np.asarray(result[i][actor][name]) * (1 - w) + target * w
            for chain in event.get('straighten', []):
                j = result[i][chain['actor']]
                a, mid, b = chain['root'], chain['mid'], chain['end']
                fraction = chain.get('fraction', .5)
                goal = np.asarray(j[a]) * (1 - fraction) + np.asarray(j[b]) * fraction
                j[mid] = np.asarray(j[mid]) * (1 - w) + goal * w
            after = [float(np.linalg.norm(np.asarray(result[i][a][n]) - target)) for a, n in members]
            report['contacts'].append(dict(id=event['id'], frame=frame, weight=w,
                                            before_max_px=max(before), after_max_px=max(after)))
    return result, report
