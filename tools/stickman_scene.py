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
    unknown = set(scene) - {'schema', 'rig', 'source_sha256', 'start', 'end', 'cuts', 'tracks', 'partials', 'contacts', 'occlusions', 'description', 'visible_views', 'despike'}
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


PARENT = {'pelvis': 'neck', 'elb_l': 'neck', 'elb_r': 'neck', 'wri_l': 'elb_l', 'wri_r': 'elb_r',
          'kne_l': 'pelvis', 'kne_r': 'pelvis', 'ank_l': 'kne_l', 'ank_r': 'kne_r', 'head_t': 'neck', 'head_b': 'neck'}


def keyed_pose(keys, frame, names):
    """키 사이를 부모 관절 기준 각도·길이로 보간한다(11-09). 좌표 직선 보간은 자세가 크게 바뀌는 두 키 사이에서
    팔다리를 접어 짧게 만들었다(예: 3153 다리 0.1배). 키 밖은 가장 가까운 키, 부모가 키에 없으면 좌표 보간."""
    out = {}
    for name in names:
        out[name] = keyed_value({t: v[name] for t, v in keys.items() if name in v}, frame)
    times = sorted(int(t) for t in keys)
    lo = [t for t in times if t <= frame]
    hi = [t for t in times if t >= frame]
    if not lo or not hi or lo[-1] == hi[0]:
        return out
    t0, t1 = lo[-1], hi[0]
    k0, k1 = keys[str(t0)], keys[str(t1)]
    w = (frame - t0) / (t1 - t0)
    order = ['pelvis', 'elb_l', 'elb_r', 'head_t', 'head_b', 'kne_l', 'kne_r', 'wri_l', 'wri_r', 'ank_l', 'ank_r']
    for name in order:
        par = PARENT[name]
        if name not in names or par not in out or not all(n in k for k in (k0, k1) for n in (name, par)):
            continue
        v0 = np.subtract(k0[name], k0[par]); v1 = np.subtract(k1[name], k1[par])
        a0, a1 = np.arctan2(v0[1], v0[0]), np.arctan2(v1[1], v1[0])
        da = (a1 - a0 + np.pi) % (2 * np.pi) - np.pi
        ang = a0 + w * da; length = (1 - w) * np.linalg.norm(v0) + w * np.linalg.norm(v1)
        out[name] = np.asarray(out[par], float) + length * np.array([np.cos(ang), np.sin(ang)])
    return out


def despike(poses, frames, cuts, protected, agree=0.25, jump=0.35, length_ratio=(0.6, 1.5), min_px=30):
    """자동 검출의 한 장 흔들림 제거(11-09). 같은 컷에서 앞뒤 장의 관절이 서로 가까운데(몸통의 agree 이내)
    그 장만 몸통의 jump 넘게 벗어나면 앞뒤 중간값으로 바꾼다. 앞뒤가 서로 먼 빠른 움직임은 건드리지 않는다.
    protected={(장, 인물)}: 수동 지정 구간은 제외."""
    shot = lambda f: sum(f >= c for c in cuts)
    out = copy.deepcopy(poses); log = []
    def window(src, i, w, actor):
        if i < 1 or i + w >= len(frames):
            return None
        if len({shot(frames[k]) for k in range(i - 1, i + w + 1)}) != 1:
            return None
        rows = [src[k].get(actor) for k in range(i - 1, i + w + 1)]
        if any(r is None for r in rows) or any((frames[k], actor) in protected for k in range(i, i + w)):
            return None
        return rows[0], rows[1:-1], rows[-1]
    for w in (1, 2):  # 그림이 2장 단위로 바뀌므로 2장짜리 튐도 본다
        for i in range(1, len(frames) - 1):
            for actor in list(poses[i]):
                win = window(out, i, w, actor)
                if win is None:
                    continue
                a, mids, b = win
                torso = np.median([np.linalg.norm(np.subtract(p['neck'], p['pelvis'])) for p in (a, *mids, b)])
                for name in JOINTS:
                    if any(name not in p for p in (a, b, *mids)):
                        continue
                    pa, pb = np.asarray(a[name], float), np.asarray(b[name], float)
                    if np.linalg.norm(pa - pb) >= agree * torso:
                        continue
                    for k, j in enumerate(mids):
                        target = pa + (pb - pa) * (k + 1) / (w + 1)
                        if np.linalg.norm(np.asarray(j[name], float) - target) > jump * torso:
                            log.append(dict(frame=frames[i + k], actor=actor, joint=name, moved_px=round(float(np.linalg.norm(np.asarray(j[name], float) - target)), 1)))
                            j[name] = target
    # 2단계: 길이 튐. 앞뒤 장의 마디 길이가 서로 비슷한데 그 장만 크게 다르면 방향은 두고 길이만 앞뒤 평균으로(아래 관절 함께 이동).
    child = {'elb_l': ['wri_l'], 'elb_r': ['wri_r'], 'kne_l': ['ank_l'], 'kne_r': ['ank_r'], 'wri_l': [], 'wri_r': [], 'ank_l': [], 'ank_r': []}
    for w, i in [(w, i) for w in (1, 2) for i in range(1, len(frames) - 1)]:
        for actor in list(out[i]):
            win = window(out, i, w, actor)
            if win is None:
                continue
            a, mids, b = win
            for name in ('elb_l', 'elb_r', 'kne_l', 'kne_r', 'wri_l', 'wri_r', 'ank_l', 'ank_r'):
                par = PARENT[name]
                la, lb = (float(np.linalg.norm(np.subtract(p[name], p[par]))) for p in (a, b))
                if abs(la - lb) > agree * max(la, lb):
                    continue
                for k, j in enumerate(mids):
                    m = la + (lb - la) * (k + 1) / (w + 1)
                    lj = float(np.linalg.norm(np.subtract(j[name], j[par])))
                    if not (lj < length_ratio[0] * m or lj > length_ratio[1] * m) or abs(lj - m) < min_px:
                        continue
                    d = np.subtract(j[name], j[par]); d = d / max(np.linalg.norm(d), 1e-9)
                    delta = np.asarray(j[par], float) + d * m - np.asarray(j[name], float)
                    for n in [name, *child[name]]:
                        j[n] = np.asarray(j[n], float) + delta
                    log.append(dict(frame=frames[i + k], actor=actor, joint=name, length=[round(lj), round(m)]))
    return out, log


def apply_scene(poses, frames, scene):
    """입력 불변. 좌표만 바꾸며 인물 사이 AC 연결이나 새 마디를 만들지 않는다."""
    if not frames or scene['start'] != frames[0] or scene['end'] != frames[-1]:
        raise ValueError('장면 설정과 처리 장 범위가 다르다')
    cuts = scene.get('cuts', [])
    result = copy.deepcopy(poses)
    report = {'partials': [], 'tracks': [], 'contacts': []}
    from stickman_occlusion import bridge_occlusions
    result, report['occlusions'] = bridge_occlusions(result, frames, scene.get('occlusions', []), cuts)
    if scene.get('despike'):
        protected = {(f, sp['actor']) for sp in [*scene.get('partials', []), *scene.get('visible_views', [])]
                     for f in range(sp['start'], sp['end'] + 1)}
        cfg = scene['despike'] if isinstance(scene['despike'], dict) else {}
        result, report['despike'] = despike(result, frames, cuts, protected, **cfg)
    for spec in [*scene.get('partials', []), *scene.get('tracks', []), *scene.get('contacts', []), *scene.get('visible_views', [])]:
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
    # 보이는 부위 지정(11-09): 근접·부분 구도에서 검출이 몸을 지어내도 원본에 보이는 조각만 그린다.
    # 검출된 인물이 있으면 그 좌표를, 없으면 가장 가까운 틀을 쓰고 keys 관절만 원본 판독 좌표로 바꾼다.
    for view in scene.get('visible_views', []):
        actor = view['actor']
        if not set(view['visible_segments']).issubset(range(1, 11)):
            raise ValueError('보이는 부위 지정의 조각 번호가 잘못됐다')
        valid = [i for i, row in enumerate(poses) if row.get(actor) is not None]
        for i, frame in enumerate(frames):
            if not view['start'] <= frame <= view['end']:
                continue
            j = result[i].get(actor)
            if j is None:
                if not valid:
                    raise ValueError('보이는 부위 지정: 쓸 수 있는 인물 틀이 없다')
                j = {k: np.asarray(v, float) for k, v in poses[min(valid, key=lambda n: abs(n - i))][actor].items() if k in JOINTS}
            j = {k: (np.asarray(v, float).copy() if k in JOINTS else v) for k, v in j.items()}
            names = set().union(*(v.keys() for v in view.get('keys', {}).values())) if view.get('keys') else set()
            for name in names:
                if name not in JOINTS:
                    raise ValueError(f'알 수 없는 관절: {name}')
            j.update(keyed_pose(view.get('keys', {}), frame, names))
            if view.get('head_d'):  # 머리 지름은 장마다 읽지 않고 구간 흐름으로 고정(가림 때문에 줄이지 않는다, 11-09 사용자)
                dia = float(np.interp(frame, *zip(*sorted((int(t), float(v)) for t, v in view['head_d'].items()))))
                c = (np.asarray(j['head_t'], float) + np.asarray(j['head_b'], float)) / 2
                u = np.asarray(j['head_t'], float) - np.asarray(j['head_b'], float)
                u = u / max(np.linalg.norm(u), 1e-9)
                j['head_t'], j['head_b'] = c + u * dia / 2, c - u * dia / 2
            j['_visible_segments'] = sorted(view['visible_segments'])
            if 'thick' in view:  # 근접에서 검출 크기를 믿을 수 없을 때 같은 장면 기준으로 정한 굵기
                j['_thick'] = float(view['thick'])
            result[i][actor] = j
            report.setdefault('visible_views', []).append(dict(frame=frame, actor=actor, visible_segments=j['_visible_segments']))
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
