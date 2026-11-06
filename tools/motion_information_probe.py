"""현행 동작 토큰의 정보 보존 범위를 CPU에서 재현한다. 모델/원본 영상 실행 없음.

python tools/motion_information_probe.py --output data/research/motion_information_probe_2026-11-06.json
합성 반례와 공개 수집 SFA의 기존 IR 통계를 구분한다. 좌표/원본 그림은 출력하지 않는다.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

import motion_tokens as MT

ROOT = Path(__file__).resolve().parents[1]


def synthetic():
    # 3장씩 유지하는 네 자세. 애니 원본에서 측정한 값이 아닌 합성 입력이다.
    pose = dict(head_t=[50, 22], head_b=[50, 30], neck=[50, 30], pelvis=[50, 50],
                elb_r=[60, 36], wri_r=[67, 42], elb_l=[40, 36], wri_l=[33, 42],
                kne_r=[55, 65], ank_r=[58, 78], kne_l=[45, 65], ank_l=[42, 78])
    n = 12
    a = dict(slot=0, color='blue', joints={k: [[x + (i // 3) * 4, y] for i in range(n)] for k, (x, y) in pose.items()},
             thickness=[{} for _ in range(n)], hidden=[[] for _ in range(n)], smear=[[] for _ in range(n)],
             head_fill=[True] * n, facing=[0] * n, drawings=[[i, i + 2] for i in range(0, n, 3)],
             smear_mark=[[] for _ in range(n)], inferred=[[] for _ in range(n)])
    return dict(schema='motion-ir/1', fps=[24, 24], aspect=.5625, frames=n, actors=[a],
                camera=[[0, 0, 1] for _ in range(n)], timeline=[])


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    ir = synthetic()
    tokens = MT.encode(ir)
    decoded = MT.decode(tokens, aspect=ir['aspect'])
    assert decoded and decoded['actors'][0]['joints']['pelvis']
    a = ir['actors'][0]
    alternatives = dict(facing=[90] * 12, hidden=[[3]] * 12, smear=[[4]] * 12,
                        smear_mark=[[4]] * 12, inferred=[[5]] * 12,
                        thickness=[{'3': 2.5}] * 12, head_fill=[False] * 12, color='red')
    collisions = {}
    for field, value in alternatives.items():
        other = copy.deepcopy(ir)
        other['actors'][0][field] = value
        collisions[field] = MT.encode(other) == tokens
    for field, value in dict(camera=[[3, 0, 1.2]] * 12, timeline=[dict(start=3, end=5, text='타격')]).items():
        other = copy.deepcopy(ir)
        other[field] = value
        collisions[field] = MT.encode(other) == tokens
    other = copy.deepcopy(ir)
    second = copy.deepcopy(a)
    second['slot'] = 1
    other['actors'].append(second)
    collisions['second_actor_default_slot'] = MT.encode(other) == tokens
    assert all(collisions.values()), '현행 어휘가 바뀌었으므로 결론을 재검토해야 한다'
    p = decoded['actors'][0]['joints']['pelvis']
    checks = dict(input_frames=12, selected_keys=MT.keyframes(a, 12), output_frames=decoded['frames'],
                  input_drawings=a['drawings'], output_drawings=decoded['actors'][0]['drawings'],
                  input_first_pair_identical=a['joints']['pelvis'][0] == a['joints']['pelvis'][1],
                  output_first_pair_identical=p[0] == p[1])
    assert checks['output_frames'] == 11 and not checks['output_first_pair_identical']
    path = ROOT / 'data/stage2/user_sfa_ir_2026-11-05.jsonl.gz'
    counts = dict(rows=0, decodable=0, shortened=0, equal_length=0, lengthened=0, frames_lost_total=0)
    if path.exists():
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                counts['rows'] += 1
                out = MT.decode(MT.encode(row), aspect=row.get('aspect', .5625))
                if out is None:
                    continue
                counts['decodable'] += 1
                delta = row['frames'] - out['frames']
                counts['shortened' if delta > 0 else 'lengthened' if delta < 0 else 'equal_length'] += 1
                counts['frames_lost_total'] += max(0, delta)
    sources = ['tools/motion_tokens.py', 'tools/compose.py', 'tools/motion_ir.py', 'tools/stage2_extract.py',
               'tools/stage5_pack.py', 'tools/tokens_to_sfa.py', 'tools/motion_information_probe.py']
    if path.exists():
        sources.append(str(path.relative_to(ROOT)))
    return dict(scope='CPU synthetic counterexamples and existing public IR; no anime inspection or model run',
                metadata_token_collisions=collisions, synthetic_timing=checks,
                existing_public_ir=counts, existing_public_ir_present=path.exists(),
                source_sha256={s: fingerprint(ROOT / s) for s in sources},
                limits=['Collisions prove absent channels, not the cause of every visual defect.',
                        'Aggregate duration checks do not judge motion quality or anime fidelity.',
                        'No changes to production vocabulary, compiler, training data or approved output.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_sha256', 'limits')}, ensure_ascii=False))
