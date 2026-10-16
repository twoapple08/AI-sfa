# 연결 대상 수집·객체 중복 제거·뒤집기 — 2026-10-15

기존 AOT/ELF 캐시에서 상세 변형에 전달되는 대상과 뒤집기 실행을 연결했다. 신규 앱 시험·영상 분석은 하지 않았다.

## 상세 패널의 입력 목록

- main의 캔버스 tap closure 0x5e4264에서 도구 값이 1 또는 6인 상세 분기는 시작 AnchorPoint와 점 ID map을 GetAllConnectedAnimationObjects(0x5d8a28)에 넘긴다(0x5e44ec).
- 반환 AO 목록이 ModifyFigureDialog 생성자에 전달된다(0x5e4504).
- 모드 6은 `_isAllGroupMode`의 Smi12 검사와 대응한다.
- 이 사실을 모든 도구가 같은 선택 범위를 쓴다는 뜻으로 확대하지 않는다.

- 이 수집 함수는 시작 AP의 편집 helper에 AO 목록이 이미 있으면 반환한다.
- 없으면 그룹/구조 연결 점 closure를 만든 다음 각 방문점의 소유 AO를 가져와 AO ID(field57) Set으로 중복을 제거한다.
- 최초로 발견한 AO만 목록 끝에 추가하므로 DrawOrder 정렬이 아니라 방문 중 최초 발견 순서다(0x5d8b88–0x5d8c34). 방문 AP들의 helper는 같은 결과 목록을 가리키게 된다.
- helper의 전체 수명·무효화 계약은 이번 범위가 아니다.

## 점 closure의 연결

- CollectGroupedStructuralConnectedAnchorPoints(0x5d8cf0)는 CollectGroupClosure(0x3463b4)의 결과를 고정·변경 불가 목록으로 만든다.
- 함수 이름에 structural이 들어가지만 이 wrapper가 CollectStructuralConnectedAnchorPoints를 직접 호출하는 것은 아니다.

- CollectGroupClosure는 ListQueue와 방문 AP ID Set을 사용한다.
- 시작점을 넣고 removeFirst로 꺼내 결과에 추가한다.
- 확인한 확장 경로는 다음과 같다.

- 현재 점의 AnchorConnection 목록에서 참조 ID를 입력 map으로 해석한 점.
- 현재 점 소유 AO의 점 목록에 대한 enqueue callback.
- ResolveGroupParentId로 구한 부모 점.
- 현재 점 ID에 대응하는 그룹 자식 목록에 대한 enqueue callback.

- enqueue callback은 null을 무시하고 방문 ID Set에 처음 추가되는 점만 큐에 넣는다(0x346edc). 따라서 그룹/연결 순환이 있어도 이 수집의 같은 점 ID를 계속 중복 방문하는 방식은 아니다.
- 구조 연결뿐 아니라 그룹 관계와 같은 AO 내부 점들까지 이어지는 범위다.
- 입력 map이 실제로 담고 있는 점이 해석 범위를 정하며 모든 프레임·모든 레이어를 무조건 전역 조회하는 알고리즘은 아니다.
- 잘못된 Flags를 다루는 parent resolver의 모든 복구 분기까지 완료한 것은 아니다.

- 이 AO 목록을 상세 패널이 사용하므로 크기·굵기·색·glow 적용의 대상은 단순히 클릭한 AO 하나로 제한되지 않는다.
- 목록은 AO ID 단위로 중복 제거되지만, 상세 ApplyOnlyTransform 자체의 점 identity 중복 제거는 별도 확인되지 않았다.
- 이 둘을 혼동하지 않는다.

## 뒤집기

같은 tap closure의 도구 값 2 분기(0x5e444c)는 시작점에 DoReflectionAction을 호출한다(0x5e44b0). DoReflectionAction(0x5e488c)은 시작점 x를 중심 c로 보관하고 같은 그룹/구조 closure를 수집한다.

- 시작 AP ID와 같은 점은 건너뛴다.
- 다른 방문점에는 x′ = c − (x − c) = 2c − x를 저장한다(0x5e490c–0x5e4914). y, AO 두 배율, glow 속성은 이 함수에서 바꾸지 않는다.
- 따라서 이 경로는 시작점의 x를 지나는 세로축에 대한 좌우 반사다.
- 화면 중심·그룹 bounding box 중심을 축으로 쓰거나 y도 뒤집는 것으로 해석하면 안 된다.
- 음수·화면 밖 좌표 clamp도 보이지 않는다.

- 반사 뒤 tap context의 변경 표시를 true로 만든다.
- 바깥 _handleFrameCanvasTap은 setState 반환 뒤 그 표시가 true인 경우 _saveAfterMove로 간다(0x5d2e48–0x5d2e6c). 좌표 snapshot을 이용할 수 있으면 변경 AO를 구해 선택 저장, 없으면 dirty→SaveCurrentFrame으로 연결된다.
- 실제 앱 반사 결과·다른 축/다른 도구 경로는 새로 검증하지 않았다.

## 기존 UI 근거와 구분

- 04에서 연결 스틱맨 여러 AO의 크기 변화가 함께 나타난 실제 표본과 이 대상 확장은 부합한다.
- 그러나 기존 손끝 드래그의 내부 관절/길이 제약 수학을 이번 수집/반사 함수만으로 확정하지 않는다.
- 독립된 주황선이 변형 대상에서 제외된 기존 결과도 모든 선택·레이어 옵션의 보장은 아니다.

## 검증·후속

- 선택된 명령은 동시 작성한 CONNECTED-ALLGROUP audit의 175개 대조 표본에 포함된다.
- 비공개 ELF PT_LOAD/Capstone/AOT 목록 대조이며 전체 의미·GDT·SQL·실제 앱 검증은 아니다.
- 중복 표본을 누적 합산하지 않는다.
- 원본/역컴파일 코드·assembly는 공개하지 않는다.

- 대상 AO 연결과 뒤집기 tap→저장 연결은 이번 범위에서 닫았다.
- 상세 변형 pivot fallback의 구체 GDT getter, 선택 hit-test/레이어 범위의 전체 옵션, 편집 helper 무효화의 전체 계약은 남겨 둔다.
- 다음 도구인 올그룹의 대상은 별도 ALLGROUP-BOX 보고서와 구분한다.
