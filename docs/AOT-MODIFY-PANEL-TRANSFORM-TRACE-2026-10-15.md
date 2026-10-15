# 객체 상세 패널 명령과 크기·굵기 적용식 — 2026-10-15

기존 캐시에서 상세 패널의 실제 버튼 연결을 확인했다. 이번 단계는 새 실제 앱 시험이나 영상 재분석이 아니다. 개별 AO 앞뒤 순서 UI는 여전히 미식별이며 그 존재를 전제로 분석 범위를 늘리지 않는다.

## 확인한 상세 패널과 버튼

ModifyFigureDialogLayout build(0x555354)는 색상·변형·글로우 탭을 구성한다. 컨트롤러의 `_initializeTab`(0x4e28a4)은 index1→SetupTransformTab, index2→SetupGlowTab, 그 외→SetupColorTab으로 연결된다. 변형 탭 build(0x63b294)에는 크기(%)·굵기(%) 입력과 ‘변형 적용’ 버튼이 있다.

이 버튼의 closure(0x63b930)는 ApplyOnlyTransform을 직접 호출하지 않는다. ApplyAllPendingChangesAndDismiss closure(0x6350fc)를 만들어 `_afterAction`으로 넘긴다(0x63b978–0x63b98c). `_afterAction`의 setState closure는 전달된 동작을 실행한 뒤 입력 컨트롤러를 동기화한다(0x63bac0).

ApplyAllPendingChangesAndDismiss(0x635134)는 실행 직전 color/transform/glow 표시 fieldc3/c7/cb를 읽어 각각 true인 경우에 색상→변형→glow 순서로 적용한다(0x635194/0x6351a4/0x6351b4). 따라서 변형 탭의 버튼이라도 다른 탭의 pending 변경을 함께 적용할 수 있다. 이를 무조건 모든 속성을 재설정하는 동작으로 해석하지 않는다. 변형 입력 setter는 fieldc7를 true로 만들고 입력 문자열을 갱신한다(0x63bdd4).

마지막에 dialog.fieldab=true가 된다. AOT annotation은 호출 주소0x555e0c를 다른 클래스의 `_markFrameDataDirty`로 표시하지만 실제 함수 몸체는 수신 객체의 fieldab에 true를 쓰는 짧은 코드다. 이름만 보고 화면 상태의 dirty 필드를 쓴 것으로 해석하면 안 된다. 이 호출의 수신 객체는 dialog다.

`_afterAction`은 dialog.fieldaf가 true이면 widget.field13 callback을 호출하고, fieldab가 true이면 widget.fieldf callback을 호출한다. 프레임 화면의 widget.field13은 `_commitModifyFigureMutation`으로 연결된다(0x5b5e34–0x5b5e48). 기존 보고서에서 확인한 cache evict→dirty→SaveFrame 경로로 이어지는 지점이다. fieldaf(변경 여부)와 fieldab(이 경로의 닫기 신호)를 구분한다. 닫기 신호 자체를 mutation 또는 저장 완료로 세지 않는다.

## 입력 배율

ApplyOnlyTransform(0x63562c)은 크기 문자열 field47, 굵기 문자열 field4b를 각각 정수로 parse한다. 각 정수의 하한은1이고100으로 나누어 배율을 만든다. parse 예외 경로의 배율은1이다. SetupTransformTab은 처음 초기화할 때 입력들을 ‘100’으로 만든다.

- 크기 배율 m = max(1, parseInt(sizePercent)) / 100
- 굵기 배율 k = max(1, parseInt(thicknessPercent)) / 100
- 각 parse 실패는 해당 배율1로 처리

입력 문자열과 UI 증감 버튼의 제한 전체를 같은 규칙으로 단정하지 않는다. 이 Apply 함수에서 별도 상한 clamp는 보이지 않으며 앱의 모든 입력 경로가 무제한이라는 뜻도 아니다. 1% 하한과 parse 실패의 100% 대체는 다르다.

## 기준점 선택

dialog.field7의 대상 AO 목록 순서와 각 AO의 점 목록 순서로 탐색하여 `(Flags & 0x2e) == 2`인 첫 점을 찾는다. 이는 bit1이 켜지고 bit2·3·5가 꺼진 조건이며 group bit4 등 마스크 밖 비트는 이 검사에 포함하지 않는다(0x635804–0x635868).

그 점이 없고 대상 첫 AO의 점 목록이 비어 있지 않으면, 그 목록에 동적 getter를 호출해 fallback 점을 얻는다(0x635898–0x635924). 이 getter의 GDT 구체 대상은 아직 독립 해석하지 않았으므로 ‘첫 점’으로 확정하지 않는다. 기준점이 끝내 없으면 좌표/배율 변경 루프 전에 반환한다. 선택한 점의 x/y가 중심 c가 된다. 화면 중심·bounding box 중심·모든 점 평균으로 대체하면 안 된다. 이 조건의 점을 모든 작품에서 ‘허리’라고 부르지 않는다.

기준점 탐색은 전달된 AO 목록 안에서 수행한다. 이번 단계는 그 목록을 어떤 선택/연결/그룹 확장 규칙으로 만드는지까지 확정하지 않았다.

## 실제 변경식

대상 AO별로 기존 ThicknessScale t와 ObjectScale o를 읽는다. 0 이하인 값은 계산에1을 사용한다. 이후 다음을 저장한다(0x635a1c–0x635a48).

| 항목 | 저장값 |
|---|---|
| ThicknessScale | positiveOrOne(t) × k |
| ObjectScale | positiveOrOne(o) × m |
| 각 방문 점의 x/y | c + m × (p − c) |

좌표식은 0x635aec–0x635b20의 subtract/multiply/add 및 double 저장으로 확인했다. 점의 raw x/y 모두 같은 m을 적용하고 좌표 부호를 clamp하지 않는다. 따라서 화면 밖·음수 좌표가 생길 수 있다는 기존 UI 결과와 연결된다. NaN·모든 비정상 값의 정규화 전체는 이번 범위가 아니다.

크기200%·굵기100%를 t=o=1에 적용하면 좌표는 c중심2배, ObjectScale2, ThicknessScale1이다. [기존 04 UI 표본](UI-04-05-RESULTS-2026-10-15.md)의 확대 결과와 부합한다. 기존 표본을 재출력·재계산한 결과는 아니다. 그 표본에는 손끝 드래그가 앞서 누적되어 있었으므로 이번 크기식을 손끝 드래그 공식으로 사용하지 않는다.

루프는 전달된 AO와 그 점들을 방문한다. 방문점 identity 중복 제거 set은 이 함수에서 보이지 않는다. 이 사실만으로 실제 앱에서 중복 확대 버그가 발생한다고 주장하지 않는다. 대상 목록 생성과 점 공유/연결 모델이 별도 확인 대상이다. 함수 끝에서 dialog.fieldaf=true를 설정한다(0x635b70).

## 순서 UI 탐색의 현재 한계

확인한 상세 탭과 크기/굵기 적용 경로에는 AO DrawOrder를 바꾸는 동작이 연결되지 않았다. 상세 패널 밖의 메뉴·도구·공통 dispatch에 일반 순서 조작이 없는지까지 증명한 것은 아니다. 같은 front/back 이름·PP 문자열 검색은 반복하지 않는다. 순서 UI는 기능표에 미식별로 남긴다.

다음은 dialog 생성 지점(main 0x5e4504)에 전달하는 대상 AO 목록의 선택·연결 확장 범위와 순서, fallback getter의 실제 대상과 적용 조건을 확인한다. 이어 이미 알려진 올그룹·뒤집기 등 도구의 명령 연결로 범위를 넓힌다. 미확인 앞뒤 UI 하나 때문에 전체 기능 분석을 정체시키지 않는다.

## 검증

새로 선택한54개 명령을 비공개 ELF PT_LOAD의 Capstone 결과와 AOT 목록으로 대조하여 모두 일치했다. audit는 주소·boolean만 공개한다. 과거 표본과 중복 합산하지 않는다. 이 검사는 전체 함수 의미·실제 앱 결과·픽셀 일치의 증명이 아니다. 기존 unit/probe/영상 분석·설치·페어링·휴대폰 시작 시험은 반복하지 않았다. 코드 변경 없이 문서·기능표·인계만 변경했다. 현재 사용자 추가 작업은 없다.


## 2026-10-16 추가 근거

본문 당시 미확정이던 목록 getter는 [DISPATCH-TARGETS](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md)의 실제 표/수신 cid/본문으로 정상 목록 계열의 first로 확인했다. 이 한정 미확정 항목을 다시 탐색하지 않는다. history hash 포함 필드는 [UNUSED-AO-FAST-HASH](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md), 실제 시간축 명령은 [TIMELINE-FRAME-COMMANDS](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)를 따른다. 기존 검증을 실제 앱/pixel 완료로 승격하지 않는다.
