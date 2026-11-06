"""사용자 지정 4.sfa의 표현 구조만 조사한다. 스미어 판별기/스타일 학습기가 아니다.

python tools/sfa_effect_reference_probe.py INPUT.sfa --output OUTPUT.json
색은 이 파일의 조사 범위 필터일 뿐 효과의 의미를 판정하는 기준이 아니다.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

FRAMES = [83, 84, 87, 88, 91, 92, 98, 99, 110, 111, 112, 113, 114, 115]
PAIRS = [(83, 84), (87, 88), (91, 92), (98, 99), (110, 111), (111, 112),
         (112, 113), (113, 114), (114, 115)]
COLOR = 0xffae0000


def frame_info(frame):
    aos = {a.get('ID'): a for a in frame.findall('AO')}
    owners = {p.get('ID'): k for k, a in aos.items() for p in a.findall('AP')}
    target = {k: a for k, a in aos.items() if int(a.get('Color', '0')) & 0xffffffff == COLOR}
    edges = defaultdict(set)
    external = dangling = 0
    for k, a in target.items():
        for p in a.findall('AP'):
            for c in p.findall('AC'):
                other = owners.get(c.get('ConnPtId'))
                if other is None:
                    dangling += 1
                elif other in target:
                    edges[k].add(other)
                    edges[other].add(k)
                else:
                    external += 1
    pending = set(target)
    groups = []
    while pending:
        first = min(pending, key=int)
        group, queue = {first}, [first]
        while queue:
            for other in edges[queue.pop()]:
                if other not in group:
                    group.add(other)
                    queue.append(other)
        pending -= group
        groups.append(sorted(group, key=int))
    return aos, target, groups, dict(outgoing_ac_to_other_colors=external, dangling_ac=dangling)


def points(aos, keys, aspect):
    return np.array([[float(p.get('X')), float(p.get('Y')) * aspect]
                     for k in keys for p in sorted(aos[k].findall('AP'), key=lambda p: int(p.get('Index', '0')))])


def motion(before, after, keys, aspect):
    x, y = points(before, keys, aspect), points(after, keys, aspect)
    if x.shape != y.shape or len(x) < 3:
        return dict(comparable=False)
    xc, yc = x - x.mean(axis=0), y - y.mean(axis=0)
    u, singular, vt = np.linalg.svd(xc.T @ yc)
    scale = float(singular.sum() / max(float((xc * xc).sum()), 1e-20))
    # 반사도 허용한 최적 상사변환. 잔차는 단순 이동/회전/등방 확대 이상의 차이를 뜻한다.
    residual = xc @ (u @ vt) * scale - yc
    extent = max(float(np.linalg.norm(np.ptp(y, axis=0))), 1e-20)
    affine = np.c_[x, np.ones(len(x))]
    fit = np.linalg.lstsq(affine, y, rcond=None)[0]
    return dict(comparable=True, points=len(x),
                moved_points_over_1e_8=int((np.linalg.norm(y - x, axis=1) > 1e-8).sum()),
                similarity_rms=float(np.sqrt((residual * residual).sum(axis=1).mean())),
                similarity_rms_over_extent=float(np.sqrt((residual * residual).sum(axis=1).mean()) / extent),
                affine_rms_over_extent=float(np.sqrt(((affine @ fit - y) ** 2).sum(axis=1).mean()) / extent))


def run(path, image_reference=None):
    with zipfile.ZipFile(path) as archive:
        entries = [n for n in archive.namelist() if n.lower().endswith('.xml')]
        if len(entries) != 1:
            raise ValueError('XML 항목이 하나인 SFA만 지원한다')
        seq = ET.fromstring(archive.read(entries[0]))
    frames = seq.findall('Frame')
    aspect = float(seq.get('HeightWidthRatio'))
    info, records = {}, []
    for number in FRAMES:
        frame = frames[number - 1]
        assert int(frame.get('Position')) == number - 1
        aos, selected, groups, refs = info[number] = frame_info(frame)
        records.append(dict(user_frame=number, position=number - 1, total_ao=len(aos),
                            color_candidate_ao=len(selected),
                            candidate_types=dict(Counter(a.get('TypeId') for a in selected.values())),
                            candidate_layer_counts=dict(Counter(a.get('LayerId') for a in selected.values())),
                            connected_component_sizes=sorted(map(len, groups)),
                            size38_component_ids=[g for g in groups if len(g) == 38],
                            candidate_fill_references=sum(s.get('ObjId') in selected for r in frame.findall('FR') for s in r.findall('FS')),
                            **refs))
    transitions = []
    for left, right in PAIRS:
        a, b = info[left][1], info[right][1]
        common = sorted(a.keys() & b.keys(), key=int)
        kept38 = [g for g in info[left][2] if len(g) == 38 and set(g) <= b.keys()]
        transitions.append(dict(frames=[left, right], common_candidate_ao=len(common),
                                removed_candidate_ao=len(a.keys() - b.keys()), added_candidate_ao=len(b.keys() - a.keys()),
                                retained38_components=[dict(ids=g, **motion(a, b, g, aspect)) for g in kept38]))
    result = dict(schema='sfa-effect-reference-probe/1', source_name='4.sfa',
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), frame_count=len(frames),
                source_role='SFA 표현 구조 참고 전용', training_ready=False, learn_placement_style=False,
                user_rule='스미어를 넣는 방식·타이밍·연출은 승인된 실제 애니메이터 원본에서 학습한다.',
                scope='사용자 지정 장의 특정 색 후보. 다른 효과/몸체 포함 가능. 스미어 자동 라벨이 아니다.',
                number_mapping='사용자 장 번호 n = XML Position n-1; 지정 장의 효과 출현과 대조',
                color_filter='0xffae0000', frames=records, transitions=transitions,
                limits=['AC 연결 성분은 의미상 효과 하나와 같다고 보장하지 않는다.',
                        '38은 이 파일에서 관찰한 크기이며 표준 단어나 필수 객체 수가 아니다.',
                        '서버 렌더 관찰은 실제 앱 편집 검증과 다르다.',
                        '원본 애니 대응 자료는 제공되지 않았다. 스타일 학습/배치 규칙 채택 없음.'])
    result['probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if image_reference:
        result['image_reference'] = dict(name='1000408331.jpg',
            sha256=hashlib.sha256(image_reference.read_bytes()).hexdigest(),
            scope='정지 이미지 외형 참고. 편집 구조/장간 변화는 미확인', training_ready=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--image-reference', type=Path)
    args = parser.parse_args()
    result = run(args.input, args.image_reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(frames=len(result['frames']), transitions=len(result['transitions']),
                         source_sha256=result['source_sha256']), ensure_ascii=False))
