# 객체·점 보간 대응과 그룹 식별자 — 2026-10-15

- 기존 FrameInterpolationPlan 및 tween_link AOT의 객체 쌍·점 대응 본문을 확인했다.
- 채우기 보간은 FILL-TWEEN, timeline은 GROUP-SHADER-TIMELINE, 실제 03/05 표본은 기존 결과를 재사용한다.
- 새 영상/앱 시험은 없다.

## 객체 쌍은 앞 프레임을 기준으로 구성

- FrameInterpolationPlan(0x62f408)은 뒤 Frame AO ID→AO map을 만들고 앞 Frame AO 목록을 순회한다.
- 앞 Frame에 layer 목록이 있으면 visible Layer 순서로 해당 LayerId의 앞 AO를 순회하고, 없으면 앞 AO 전체를 순회하는 분기가 있다.
- 해당 앞 AO에 유효한 수동 대응이 있으면 그 뒤 AO를, 없으면 같은 AO ID의 뒤 객체를 찾는다(0x62faf4/0x62fb34,0x62fd0c/4c).

- 뒤 대응이 없으면 쌍을 추가하지 않는다.
- 뒤에만 생긴 객체를 별도 unmatched loop로 중간 Frame에 넣거나 앞 객체를 임의로 fade-out하는 명령이 이 생성 구간에 없다.
- 모든 t에서 원본과 동일한 생성·삭제 상태를 보장한다는 뜻도 아니다.
- 원본 frame을 직접 출력하는 경로와 중간 InterpolatedFrame은 구분해야 한다.

- 쌍의 순서는 이 생성 순서다.
- 렌더러·DB의 다른 DrawOrder 정렬을 이 단계에도 자동 적용했다고 가정하지 않는다.
- 같은 ID의 자동 대응은 이 lookup 경로에서 수동 링크와 같은 유형/점 수 검사를 수행하지 않는다.
- 앞뒤 자료가 깨졌거나 같은 ID의 유형이 바뀐 경우를 수동 링크의 거절 규칙으로 대신 설명하면 안 된다.

## 수동 링크의 방향·충돌·우선순위

- resolveTweenLinks(0x632d74)의 입력 link map은 **뒤 대상 AO ID→앞 원천 AO ID**다.
- key들을 오름차순으로 정렬해 처리하고, 반환값은 앞 ID→뒤 AO다.
- 다음이면 해당 링크를 제외한다.

- 어느 쪽 AO를 찾지 못함.
- 앞 원천 ID가 이미 반환 map에 있음: 작은 뒤 key에서 먼저 승인된 대응 유지.
- 뒤 대상 ID가 앞 AO map에도 존재함.
- 앞 원천 ID가 뒤 AO map에도 존재함.
- TypeId가 다름.
- _samePoints 검사 실패.

- 마지막 두 ID 충돌 조건은 동일 ID의 원래 대응과 교차하는 수동 링크를 무조건 덮어쓰지 않게 한다.
- ‘마지막 입력 승리’나 임의 many-to-one 병합으로 구현하면 다르다.
- 이 helper는 역방향 링크를 자동 추가하지 않는다.
- 앞단 TweenLinkChoices UI가 허용하는 전체 선택과 별개로 실제 plan에서 다시 검사하는 경로다.

- _samePoints(0x633088)는 두 점 목록 길이가 같고, 같은 목록 위치마다 AP.Index(field23)가 같은지 확인한다.
- 좌표·점 ID·Flags 동등성 비교가 아니다.
- 목록을 이 helper가 정렬하지도 않는다.
- 따라서 ‘같은 수의 점이면 링크 가능’으로 줄이면 안 된다.

## 점 대응은 AP.Index 기준

_InterpolateAnimationObject(0x62ecbc)는 앞 AO 점 목록을 순서대로 돌며 그 점의 Index에 맞는 뒤 점을 찾는다.

1. 같은 목록 위치의 뒤 점이 존재하고 Index도 같으면 그 점 사용.
2. 아니면 뒤 점 목록 처음부터 같은 Index를 찾아 첫 일치점 사용.
3. 끝까지 없으면 해당 앞 점의 x/y를 뒤 좌표로도 사용한다.

점 ID 숫자가 달라도 Index 대응이 가능하고, 뒤 점만 추가됐다고 보간 점 목록이 그만큼 늘지는 않는다. 만들어지는 InterpolatedAnchorPoint는 앞 목록 길이/순서의 좌표 목록이다.

- 좌표는 p(t)=p0+(p1−p0)t의 백분율 x/y 선형 보간이다(0x62f010–28). 이동/포즈 도구의 화면좌표 회전·길이 보존 조작을 여기서 다시 실행하는 것이 아니다.
- 이 구간에 원호/관절 각도 보간이나 화면 밖 clamp는 없다.
- 이 helper 자체의 t clamp도 확인되지 않는다.
- 유효한 t 공급은 timeline의 별도 계약이다.

## 속성의 수학과 앞쪽 구조

확인한 쓰기 구간은 다음과 같다. u(t)=u0+(u1−u0)t다.

| 항목 | 계산 |
|---|---|
| 본체 ARGB | Frame.InterpolateArgbColor |
| ThicknessScale | double u(t) |
| GlowRadius | round(u(t)) |
| GlowAlpha | alpha0+trunc((alpha1−alpha0)t) |
| GlowThickness | round(u(t)) |
| GlowColor | Frame.InterpolateArgbColor |

GlowAlpha의 정수화 위치는 델타를 곱한 뒤 0방향 절삭하고 앞 값을 더하는 것이다(0x62f210/230). 최종 합을 무조건 반올림하는 식과 다르다. 큰 값/NaN의 DoubleToInteger 오류·fallback은 별도 분기이며 임의로 0을 공급하지 않는다.

- 새 InterpolatedAnimationObject의 AO ID·LayerId·TypeId는 앞 객체에서 공급한다(0x62f0e4–150). 이 본문은 ObjectScale(field3f)을 두 끝값으로 선형 보간해 저장하지 않는다.
- 모든 저장 속성을 일률적으로 lerp하는 일반 객체 변환으로 바꾸면 실제 쓰기와 다르다.
- 실제 렌더 구조가 ObjectScale을 소비하는 전체 계약은 다른 경로와 함께 봐야 하며, 이 사실만으로 원본 ObjectScale 기능이 무효라고 결론내리지 않는다.

## 그룹 glow의 식별자는 앞 연결 집합에서 공급

- plan은 앞 AO 목록에서 _ResolveConnectedObjectGlowGroupIds를 호출한다(0x62f598).
- 각 앞 AO ID에 그 map의 group ID가 있으면 쌍에 넣고, 없으면 그 AO ID를 넣는다.
- 이 값이 _InterpolateAnimationObject의 세 번째 인수로 InterpolatedAnimationObject에 전달된다(0x62e8c0/cc,0x62f16c).

- 따라서 중간 결과의 그룹 ID를 앞뒤 ID 숫자 사이에서 선형 보간하는 규칙은 아니다.
- 뒤 Frame의 그룹 Flags를 t=.5에서 이 helper가 통째로 교체한다는 근거도 없다.
- 그룹 glow의 합성/실제 픽셀 검증은 기존 static renderer 근거 및 향후 실물 검증과 구분한다.

- apply(0x62e810)는 각 호출마다 새 AO 목록·보간 점/객체 및 InterpolatedFrame을 만든다.
- 앞 Frame의 layer를 clone하고 fill step 결과를 붙인다.
- 원본 Frame의 점을 in-place 수정하는 편집 명령으로 취급하지 않는다.
- plan 재사용과 완성 Frame/Picture 재사용은 별개다.

## 검증·남은 범위

- AOT-OBJECT-TWEEN-AUDIT-2026-10-15.json에 선택 명령 대조를 기록했다.
- 정상 객체 쌍·점 Index·속성 정수화·앞 그룹 ID 공급을 연결한 정적 분석이다.
- 모든 비정상 중복 Index/ID, 다중 UI 조작, 실제 곡선/원 픽셀·blend 동등성 전체를 검증한 결과가 아니다.
- 기존 영상/앱·unit/probe 시험은 반복하지 않았다.
