"""사건의 원본 근거를 보존하는 선택형 문맥 통로. 생성/렌더/학습 기능은 없다.

원본 장 대응은 명시 입력이며 자동 검증한 정답이 아니다. 보간 장의 대응은 None으로 남긴다.
"""
import copy
from fractions import Fraction
import json
import re

SCHEMA = 'anime-event-context/1'


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate(context):
    if context.get('schema') != SCHEMA or context.get('alignment_status') != 'declared_only':
        raise ValueError('지원하지 않는 문맥/대응 상태')
    event = context['event']
    if event.get('schema') != 'anime-to-sfa-event-draft/1' or not event.get('case_id'):
        raise ValueError('사건 형식/ID가 필요하다')
    source = event['source']
    if source.get('index_base') != 0 or not _integer(source['frames']) or source['frames'] <= 0:
        raise ValueError('0기준 원본 장 수가 필요하다')
    if not re.fullmatch('[0-9a-f]{64}', source.get('sha256', '')):
        raise ValueError('원본 SHA256이 필요하다')
    try:
        fps = Fraction(source['fps'])
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError('원본 FPS 형식 오류') from exc
    if fps <= 0:
        raise ValueError('양수 FPS가 필요하다')
    lo, hi = event['evidence_window']['inclusive_indices']
    if not (_integer(lo) and _integer(hi) and 0 <= lo <= hi < source['frames']):
        raise ValueError('원본 검토 구간 오류')
    if not _integer(context['actor_slot']) or context['actor_slot'] < 0:
        raise ValueError('대상 슬롯은 음수가 아닌 정수여야 한다')
    for phase in event['phases']:
        a, b = phase['indices']
        if not (_integer(a) and _integer(b) and lo <= a <= b <= hi):
            raise ValueError('관찰 단계가 검토 구간 밖에 있다')
    if not isinstance(context['source_indices'], list):
        raise ValueError('원본 장 대응 목록이 필요하다')
    for value in context['source_indices']:
        if value is not None and not (_integer(value) and lo <= value <= hi):
            raise ValueError('원본 대응 장이 검토 구간 밖이거나 잘못됐다')
    # 알 수 없는 새 필드도 버리지 않는다. NaN/Infinity 등 비표준 JSON은 금지한다.
    json.dumps(context, allow_nan=False)
    return context


def create(event, actor_slot, source_indices):
    return validate(dict(schema=SCHEMA, event=copy.deepcopy(event), actor_slot=actor_slot,
                         source_indices=list(source_indices), alignment_status='declared_only'))


def dumps(context):
    validate(context)
    return json.dumps(context, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


def loads(text):
    return validate(json.loads(text))


def remap(context, output_to_input):
    """길이 변경/반복/순서 변경은 명시 대응만 허용. None은 출처를 모르는 새 장이다."""
    validate(context)
    result = copy.deepcopy(context)
    indices = context['source_indices']
    mapped = []
    for index in output_to_input:
        if index is None:
            mapped.append(None)
        elif _integer(index) and 0 <= index < len(indices):
            mapped.append(indices[index])
        else:
            raise ValueError('출력→입력 장 대응 오류; 자동 보간으로 채우지 않는다')
    result['source_indices'] = mapped
    return validate(result)


def slice_context(context, start, end):
    validate(context)
    if not (_integer(start) and _integer(end) and 0 <= start <= end <= len(context['source_indices'])):
        raise ValueError('잘못된 구간; 끝은 포함하지 않는다')
    return remap(context, range(start, end))


def concatenate(contexts):
    """같은 사건/대상 문맥만 재결합한다. 서로 다른 사건의 통합 규칙은 아직 없다."""
    if not contexts:
        raise ValueError('재결합할 문맥이 없다')
    result = copy.deepcopy(validate(contexts[0]))
    result['source_indices'] = []
    for context in contexts:
        validate(context)
        left, right = copy.deepcopy(context), copy.deepcopy(result)
        left.pop('source_indices'); right.pop('source_indices')
        if left != right:
            raise ValueError('출처/사건/대상이 다른 문맥을 합칠 수 없다')
        result['source_indices'].extend(context['source_indices'])
    return validate(result)


def phase_runs(context):
    """출력 장에서 어떤 원본 관찰 단계에 해당하는지만 계산. 스미어 확정 라벨이 아니다."""
    validate(context)
    result = []
    for phase_index, phase in enumerate(context['event']['phases']):
        lo, hi = phase['indices']
        start = None
        for index, source in enumerate(context['source_indices'] + [None]):
            active = source is not None and lo <= source <= hi
            if active and start is None:
                start = index
            if not active and start is not None:
                result.append(dict(phase_index=phase_index, local_inclusive=[start, index - 1]))
                start = None
    return result


def check_motion_binding(context, motion):
    """소실/개수/대상 불일치를 검사한다. 대응의 시각적 정확성은 검증하지 않는다."""
    validate(context)
    if not _integer(motion.get('frames')) or motion['frames'] != len(context['source_indices']):
        raise ValueError('장 수가 달라졌다. 명시적인 출력→입력 장 대응이 필요하다')
    slots = [a.get('slot') for a in motion.get('actors', [])]
    if not all(_integer(slot) and slot >= 0 for slot in slots) or slots.count(context['actor_slot']) != 1:
        raise ValueError('연결할 인물 슬롯이 없거나 중복됐다')
    return True
