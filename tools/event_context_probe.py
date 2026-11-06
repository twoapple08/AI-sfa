"""실제 사건 기록과 합성 자세를 구분한 CPU 왕복/기존 통로 소실 진단."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import event_context as C
import motion_tokens as MT
from motion_information_probe import synthetic

ROOT = Path(__file__).resolve().parents[1]


def run():
    path = ROOT / 'data/research/anime_smear_event_2026-11-06.json'
    event = json.loads(path.read_text())
    context = C.create(event, 0, range(1376, 1408))
    recovered = C.loads(C.dumps(context))
    chunks = [C.slice_context(recovered, 0, 14), C.slice_context(recovered, 14, 20),
              C.slice_context(recovered, 20, 32)]
    assert C.concatenate(chunks) == context
    view = chunks[1]
    unknown = C.remap(view, [0, None, 1, 2, 3, 4, 5])
    assert unknown['source_indices'][1] is None and unknown['event'] == event
    motion = synthetic()
    motion['timeline'] = [copy.deepcopy(event)]
    bound = C.create(event, 0, range(1390, 1402))
    C.check_motion_binding(bound, motion)
    tokens = MT.encode(motion)
    decoded = MT.decode(tokens)
    caught = False
    try:
        C.check_motion_binding(bound, decoded)
    except ValueError:
        caught = True
    assert caught and decoded['timeline'] == []
    original = synthetic()
    assert MT.encode(original) == tokens
    files = [path, Path(__file__), ROOT / 'tools/event_context.py', ROOT / 'tools/motion_tokens.py',
             ROOT / 'tools/motion_information_probe.py']
    return dict(schema='event-context-probe/1', source_case=event['case_id'],
                actual_anime_pose_used=False, synthetic_motion_only=True,
                context_roundtrip_equal=recovered == context, split_rejoin_equal=C.concatenate(chunks) == context,
                source_event_unchanged_after_remap=unknown['event'] == event,
                local_phase_runs_for_1390_1395=C.phase_runs(view),
                unmapped_interpolation_retained_as_null=unknown['source_indices'][1] is None,
                legacy_tokens_unchanged_by_event=MT.encode(original) == tokens,
                legacy_timeline_empty=decoded['timeline'] == [],
                legacy_motion_frames=[motion['frames'], decoded['frames']],
                changed_length_binding_rejected=caught,
                source_event_training_ready_after_roundtrip=recovered['event']['training_ready'],
                exact_boundaries_verified_after_roundtrip=recovered['event']['validation']['exact_smear_boundaries_verified'],
                alignment_status=recovered['alignment_status'],
                source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                limits=['문맥 보존은 생성 모델이 의미를 배웠다는 증거가 아니다.',
                        '원본 자세나 SFA 외형/편집 가능성은 이번에 비교하지 않았다.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('source_sha256', 'limits')}, ensure_ascii=False))
