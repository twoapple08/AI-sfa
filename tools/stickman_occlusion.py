"""명시한 일시 가림을 같은 컷의 양끝 포즈로 잇는다. 숨은 자세는 추론이다."""
import copy
import numpy as np

PARENTS = {'neck': 'pelvis', 'head_b': 'neck', 'head_t': 'head_b',
           'elb_l': 'neck', 'wri_l': 'elb_l', 'elb_r': 'neck', 'wri_r': 'elb_r',
           'kne_l': 'pelvis', 'ank_l': 'kne_l', 'kne_r': 'pelvis', 'ank_r': 'kne_r'}


def bridge_occlusions(poses, frames, events, cuts=()):
    """양끝 사이 마디 방향/투영 길이 보간. 속도 제한·고정 길이·컷간 차용 없음."""
    result = copy.deepcopy(poses)
    index = {f: i for i, f in enumerate(frames)}
    report, occupied = [], set()
    for event in events:
        actor, start, end = event['actor'], event['start'], event['end']
        if not event.get('evidence') or start > end or any(f not in index for f in (start-1, start, end, end+1)):
            raise ValueError('가림 범위·양끝 관측·근거가 필요하다')
        if any(start-1 < c <= end+1 for c in cuts):
            raise ValueError('가림 보간은 컷 경계를 넘을 수 없다')
        nodes = set(event.get('nodes', ['pelvis', *PARENTS]))
        if not nodes or not nodes <= {'pelvis', *PARENTS}:
            raise ValueError('알 수 없는 가림 마디')
        left, right = poses[index[start-1]].get(actor), poses[index[end+1]].get(actor)
        if left is None or right is None:
            raise ValueError('양끝에 같은 인물의 확인 포즈가 필요하다')
        hidden=event.get('hidden_intervals',[])
        if any(not start<=a<=b<=end for a,b in hidden):raise ValueError('숨김 범위는 가림 구간 안이어야 한다')
        for f in range(start, end+1):
            if (f, actor) in occupied:
                raise ValueError('같은 인물의 가림 구간 중복')
            occupied.add((f, actor))
            t = (f-start+1)/(end-start+2)
            target = copy.deepcopy(left)
            target['pelvis'] = (1-t)*np.asarray(left['pelvis'])+t*np.asarray(right['pelvis'])
            for node, parent in PARENTS.items():
                a, b = np.asarray(left[node])-left[parent], np.asarray(right[node])-right[parent]
                la, lb = np.linalg.norm(a), np.linalg.norm(b)
                if min(la, lb) < 1e-8:
                    vector = (1-t)*a+t*b
                else:
                    angle = np.arctan2(a[1], a[0])
                    delta = np.arctan2(np.sin(np.arctan2(b[1], b[0])-angle),
                                       np.cos(np.arctan2(b[1], b[0])-angle))
                    angle += t*delta
                    vector = ((1-t)*la+t*lb)*np.array([np.cos(angle), np.sin(angle)])
                target[node] = target[parent]+vector
            row = result[index[f]].get(actor)
            if row is None:
                if nodes != {'pelvis', *PARENTS}:
                    raise ValueError('미검출 인물에는 전신 보간이 필요하다')
                result[index[f]][actor] = target
            else:
                for node in nodes:
                    row[node] = target[node]
            if any(a<=f<=b for a,b in hidden):result[index[f]][actor]['_visible_segments']=[]
            report.append(dict(frame=f, actor=actor, nodes=sorted(nodes),
                               reason='명시 가림,양끝2D방향/길이 보간;숨은 자세 추론'))
    return result, report
