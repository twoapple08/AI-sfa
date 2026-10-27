# 태그 토론 4차 — GPT 표본 20 검토 반영, 생성기 3차, 사실표·GPT 조각 캡션 제안 (2026-10-27 밤)

## GPT 표본 검토 요지
- 숫자 범위는 통과, 의미 오류: 색 적용 범위(대상 전체 색표가 조각에 붙음), 급팽창 번역(bursts out), 카메라 배열을 순서로 씀, 이동 묘사 누락(s0380 원경 후퇴), 컷 양쪽 병합, 주기 숫자를 장 번호로 봄, 경우 A 검증 부족, 색 낱말 중복 판정.
- 답: 길이는 중복 제거 우선(60단어 목표), rhythm 4번째 값 반대(구간 속성 메타데이터 권고), 경우 B는 GPT 리듬 요약 제거. 60단어 예시 20개를 gpt_review_report.md에 둠.
- 태그 보완: s0149 흑백 구간 빨강·노랑 제거, s0177 빔·잔상·삽입을 색별 target으로 분리, s0194 [3,28] camera ['줌아웃','팬'] 복원(사용자 추가 판정).

## Claude 대조·작업 [서버]
- b06 02e5f5fb…, b08 bbc5ae1f…, pilot30 e2c15c5a… = GPT 제시값, files 18/18, 구조 오류 0. s0177·s0149 대상 종류별 존재 장 집합·컷·리듬 이전과 동일(Claude 확인).
- 생성기 3차(`tools/caption_window.py`): 위 지적 반영, `whole_ok` 분리, 시험 `tests/test_caption_window.py` 10개(회귀 5개 추가), 전체 33개 통과. 482조각 조각 밖 번호 0, 60단어 이내 287/482.
- 색 범위 확인 필요 대상: 색 3+ 또는 '색 단계 변화'이면서 조각 경계에 걸침 141개(94컷, 175조각).
- 새 도구 `tools/window_factsheet.py`: sheet(경우 B 443조각 사실표, 조각 기준 번호·교집합·연장 여부·color_scope_check·원문 안 문장·Claude 초안), check(GPT 조각 캡션 기계 검사). GPT 예시 20개로 검사기 시험: 필수 검사 통과, 참고 경고 3(시작 장 미언급, 경우 A 원문).
- `tools/wan_lora_dataset.py --window-captions`: GPT 조각 캡션 우선, 없으면 window_caption.
- 사실표 파일(scratch, 저장소 미포함 — 재생성: `python tools/window_factsheet.py sheet data/style_kb/ai_results/gpt_SHOT_MOTION_30_2026-10-27.jsonl data/style_kb/ai_results/gpt_SHOT_MOTION_ALL_2026-10-27.jsonl -o window_facts.jsonl`, 4분할은 shot·w0 순 111/111/111/110).

## GPT에게 보낸 답장 (복붙용, 사실표 4개 첨부)

```text
표본 검토 감사합니다. 공통 규칙 지적은 모두 맞아서 생성기에 반영했습니다. 다만 결과를 보니 생성기만으로는 GPT의 60단어 예시 품질에 못 미칩니다. 그래서 역할을 바꾸자고 제안합니다(아래 [3]).

[0] 5차 파일 대조
- b06·b08·pilot30의 SHA-256이 말씀하신 값과 일치합니다. 검증 파일 files는 18/18, 서버 구조 검사 오류는 0개입니다.
- s0177·s0149: 대상 종류별 존재 장 집합, 컷, 리듬이 이전 판과 정확히 같은 것을 Claude도 확인했습니다. 대상 분리로 색이 발생 구간에 붙었습니다.
- s0194: 구간 [3,28]의 camera가 ['줌아웃','팬']이고, 캡션이 후퇴와 추적으로 바뀐 것을 확인했습니다.
- 저장소의 태그 사본도 이 판으로 바꿨습니다.

[1] 세 가지 답 — 모두 받아들입니다
1) 길이는 강제로 자르지 않고 중복부터 없앱니다.
2) rhythm 4번째 값은 넣지 않습니다. 구간 속성은 생성기 쪽 메타데이터로 둡니다.
3) 경우 B에서는 GPT의 리듬·카메라·컷 요약 문장을 빼고, 구조에서 한 번만 계산합니다.

[2] 생성기 수정 (tools/caption_window.py, 시험 33개 통과)
- 'shifting colors'를 없앴습니다. 공존하는 색은 그대로 나열합니다(orange-yellow fire). change에 '색 단계 변화'가 있는데 조각이 대상 일부만 보면 색을 붙이지 않습니다.
- 급팽창은 'rapidly expands'로 씁니다. 소멸은 change에 '화면 밖으로 나감'이 있으면 'leaves the frame', 아니면 'disappears'로 씁니다. 'fades'는 밝기 근거가 있을 때만 씁니다.
- change 낱말(rotating, spreading apart, bending, breaking into chunks, moving out of frame, lengthening)을 대상 묘사에 넣었습니다.
- '둥근 덩어리'는 연기·먼지·폭발·물보라만 billows로, 빛·불은 rounded masses로 씁니다.
- 카메라 배열은 동시(병행)로 씁니다: 'tracking with pullback', 'shaky push-in', 'shaky tracking'. 구간이 다르면 'camera unclear before 7, then shaky push-in from 7'처럼 순서로 씁니다. 조각에 1–2장만 걸친 구간의 카메라는 말하지 않습니다. 원문에 slight가 있으면 'slight camera shake'로 씁니다.
- 컷을 넘어 같은 대상을 합치지 않습니다. 새 컷 쪽 대상에는 'in the new shot'을 붙입니다.
- 'every/offset/cycle/period' 뒤의 숫자는 장 번호로 보지 않습니다.
- 경우 A는 빠진 끝 1–3장에 컷이나 새 phase 시작이 있으면 쓰지 않습니다.
- 중복 판정은 대상 이름 낱말로만 합니다(색 낱말은 쓰지 않음).
- 대상이 없으면 'No visible effects.'를 씁니다. 홀드가 앞뒤로 모두 이어지면 'a 29-frame portion of an ongoing drawing hold …, continuing beyond the window'로 씁니다.
- 일부 가림은 'Partly occluded'로 한 번 씁니다. 대상은 첫 장 순서로 씁니다.
회귀 표본(같은 20개 중):
- (7) s0149 22–42: '… camera unclear before 7, then shaky push-in from 7, two cuts, new shot at 7.' 빨강이 빠졌고 순서 오류도 없습니다.
- (8) s0157 33–65: 'Gray-brown and dark gray dust … rapidly expands at 23-26 …; shaky tracking, one cut.'
- (10) s0177 22–42: 'pink beam … at 0-2; yellow beam … at 5. … purple afterimage … at 0; pink … at 4; yellow … at 7.' 조각 밖 색이 0개입니다.
남은 한계(생성기로는 풀 수 없음):
- 482조각 중 60단어 이내는 287개뿐입니다(중앙값 53.5, 최대 194).
- (19) s0380의 '원경으로 멀어지며 작아짐'은 구조 태그에 없습니다(불 phase는 잔류 12–28). 그래서 생성기로는 되살릴 수 없습니다.
- 색표·change·shape는 대상 전체 속성입니다. 색이 셋 이상이거나 '색 단계 변화'가 있으면서 조각 경계에 걸친 대상이 141개(94컷, 175조각)입니다. 이 조각들은 시트를 봐야 실제 색을 알 수 있습니다.

[3] 제안 — 경우 B 조각 캡션은 GPT가 쓰고, Claude가 사실을 계산하고 검사합니다
GPT의 60단어 예시 20개는 같은 사실에서 생성기보다 정확하고 짧습니다. 그래서 각자 잘하는 일로 나누자고 제안합니다.
- Claude: 조각마다 '사실표'를 정확히 계산했습니다. 첨부 4개 파일(조각사실표_1of4–4of4.jsonl), 443조각입니다.
  · 조각 범위는 학습 자료 생성과 같은 계산이고, 모든 장 번호는 조각 기준(0부터)입니다.
  · segments: 구간 범위, new_shot, camera, rhythm(앞뒤 연장 여부 포함)
  · events: 대상·색·형태·change·가림, phase 교집합, starts_before / continues_after, color_scope_check(true면 시트에서 이 조각의 실제 색을 확인)
  · cuts_in_window, window_ends_at_shot_end
  · original_sentences_inside: 원 캡션 중 조각 안에 다 들어가는 문장
  · claude_draft: 생성기 출력(참고용)
- GPT: 각 조각의 캡션을 60단어 이내로 써 주세요. 형식은 JSONL 한 줄에 {"shot","w0","w1","caption"}이고, w0·w1은 사실표의 값(시트 장 번호) 그대로입니다.
  · 장 번호는 조각 기준으로 씁니다. 앞뒤 연장은 'already …', 'beyond the window', 'through the last visible frame'으로 씁니다.
  · 컷 수 낱말을 쓰고, 새 컷 장 번호를 언급합니다. 판정 과정 낱말은 쓰지 않습니다.
  · color_scope_check가 true인 대상은 시트에서 색을 확인해 주세요. 태그에 없는 이동 묘사(원경 후퇴 등)도 시트에서 확인되면 넣어 주세요.
- Claude: tools/window_factsheet.py check로 전부 기계 검사합니다.
  · 필수 검사: 조각 범위 일치, 조각 밖 번호, 컷 수, 새 컷 언급, 60단어, 한글·붙은 숫자·판정 낱말.
  · 참고 경고: 시작 장 번호가 안 보이는 대상.
  · 검사기를 GPT 예시 20개로 시험했고, 필수 검사는 모두 통과했습니다.
  · 그다음 묶음마다 몇 조각씩 원본 영상과 대조하겠습니다. 학습 자료 생성기는 GPT 캡션을 우선 쓰고, 없는 조각만 생성기 출력을 씁니다.
- 경우 A(39조각)는 지금처럼 원 캡션을 그대로 씁니다.
- 반대하신다면 대안을 알려 주세요. 그 경우 생성기 수정을 계속하고, 같은 20개를 다시 보내겠습니다.

```
