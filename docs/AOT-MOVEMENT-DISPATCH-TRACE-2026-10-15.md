# 이동·포즈/늘이기 dispatch와 연결 점의 차이 — 2026-10-15

기존 AnchorPoint AOT에서 DoMovementAction(0x5efdbc), DragConcurrentPointsTo(0x5f0108), 관련 평행이동·회전 함수를 확인했다. 이 문서는 전체 관절 동작·모든 hit-test를 완료했다는 뜻이 아니며 실제 앱 시험을 추가하지 않았다.

## 도구·점 유형 분기

- 점 유형값 T는 Flags & 0x2e다.
- DoMovementAction은 전역 도구값 0의 pose 경로, 값 1의 늘이기 경로를 구분한다.
- 도구값은 내부 정수이며 다른 UI 메뉴/설정 번호에 일반화하지 않는다.

| 조건 | 확인한 동작 |
|---|---|
| 값 0, 조상 중 (Flags&0x2f)==0x21인 점을 만나고 현재 T!=2 | 그 조상을 중심으로 각도 변화 계산 후 RotateBranch, 즉시 반환 |
| 값 0, 일반 T==2 | 이전/현재 화면 포인터를 백분율로 역변환한 차이만큼 TranslateEntireFigure |
| 값 0, 일반 T==8 | RotateEntireFigure |
| 값 0, 일반 T==4 또는 32 | PivotTo |
| 값 1, T==4/8/32 | DragConcurrentPointsTo |

- 상세 패널·뒤집기·올그룹 상자는 별도 호출 경로다.
- 0x21 조상의 의미를 단순히 ‘잠긴 레이어’나 임의의 색 점 이름으로 명명하지 않는다.
- parent 필드는 아래 트리 구성에 의존한다.
- 손상된 그래프의 모든 예외 처리는 미완이다.

## 연결 점을 포인터로 옮기는 늘이기

GetConcurrentAnchorPoints(0x5f0330)는 identity HashSet으로 방문을 막고 _addConcurrentAnchorPoints를 재귀 호출한다. 이 helper는 AC 참조 ID를 map에서 찾으며 IsGroupConnection이 true인 연결은 건너뛴다(0x5f0558–0x5f0570).

- 즉 concurrent는 좌표가 가까운 모든 점을 전역 검색한다는 뜻이 아니다.
- 일반 AC를 따라가고 그룹 연결을 제외하는 집합이다.
- 그룹 연결의 서로 다른 위치를 같은 관절점으로 합치면 안 된다는 기존 04 결과와 이어진다.
- 일반 AC의 두 점이 원래 같은 좌표라는 전제를 이 helper가 좌표 비교로 강제하는 것은 아니다.

DragConcurrentPointsTo는 화면 pointer를 백분율 x/y로 변환하고 수집한 점 모두에 같은 최종 x/y를 저장한다(0x5f0234–0x5f02f8). 길이 보존 회전과 다른 동작이다. 이 helper의 집합 cache는 입력 map과 연결되지만 무효화 전체 계약을 새로 검증한 것은 아니다.

## 전체 평행이동·회전

- TranslateEntireFigure(0x5f0e74)는 parent를 따라 위로 올라간 뒤 _dragClosure를 구하고, 그 점들에 동일한 백분율 dx/dy를 더한다.
- _dragClosure는 이번에 확인한 CollectGroupClosure로 연결된다.
- 따라서 구조 연결과 그룹 closure가 반영될 수 있다.
- 좌표를 화면 안으로 clamp하는 코드는 이 가산 구간에 없다.

- CalculateAngleOfChange(0x5f18c4)는 pivot을 화면 좌표로 변환하여 각 pointer와 pivot 차이의 atan2를 구하고 현재각−이전각을 반환한다.
- _RotationAbout.apply(0x5f0b50)는 점을 화면 좌표로 옮겨 pivot을 뺀 뒤 일반 회전 행렬을 적용하고 백분율 좌표로 역변환한다.
- 퍼센트 x/y에 화면 종횡비를 무시한 회전 행렬을 바로 적용하면 같은 동작이 아니다.

- RotateEntireFigure는 계산한 각도로 closure 점들을 회전한다.
- RotateBranch는 _branchOf가 고른 점들에 회전을 적용한다.
- PivotTo는 GetClusterHead 및 일반 연결 점의 parent를 통해 pivot/branch 정보를 구한 뒤 RotateBranch로 간다.
- 분기 선택·트리 구성의 확인 범위는 아래와 같다.
- 여러 연결 충돌의 모든 UI 결과는 미완이다.
- 현재 코드가 보인다는 이유로 ‘모든 관절 역운동학 해석 완료’라고 쓰지 않는다.

## 분기 선택과 트리 구성

- _branchOf(0x5f11f8)는 먼저 pivot의 일반 연결 점 집합(GetConcurrentAnchorPoints)의 ID를 방문 집합에 넣어 경계로 만든다.
- branch seed를 결과/작업 목록에 넣고 순서대로 확장한다.
- 확장 원천은 그룹이 아닌 AC의 대상과 현재 점이 속한 AO의 다른 점이다.
- 이미 방문한 ID는 다시 넣지 않는다.
- CollectGroupClosure의 그룹 parent/children 확장과 같은 함수가 아니다.
- seed helper에는 pivot·입력 map을 키로 결과 목록을 보관한다.

- RotateBranch는 이 결과를 순서대로 회전한다.
- 중요한 예외가 있다.
- 결과의 현재 점이 pivot과 동일하면 회전 적용 직후 pivot의 현재 좌표로 회전 중심을 다시 만든다(0x5f1114–0x5f118c). 정상 호출에서 항상 그 조건이 생긴다는 뜻은 아니지만, 모든 경로가 최초 중심을 끝까지 고정한다고 일반화할 수 없다.

GetClusterHead(0x5f0830)는 현재 점의 parent가 일반 연결 점 목록 안에 있으면 parent로 올라가 같은 검사를 반복하고, 없거나 목록 밖이면 현재 점을 반환한다. 모든 연결점 중 최소 ID를 직접 선택하는 함수가 아니다.

- BuildTreeHierarchyWithPreferredNode(0x5223f8)의 입력은 점 map과 선택적 선호 점이다.
- 먼저 map의 모든 점 parent(field7)와 children(fieldb)을 비운다.
- 0x5114b0의 annotation은 Flutter dispose지만 실제 공유 몸체는 수신 객체 fieldb=null 쓰기다.
- Flutter 위젯 해제로 해석하면 틀린다.

- 첫 root 후보 목록은 선호 점(있을 때)과 나머지 T==2 점이다.
- **이 목록 전체를 점 ID 오름차순으로 정렬**한다(비교 closure0x522380, 정렬 0x522748). 선호 점을 먼저 추가했다는 사실만으로 무조건 첫 root라고 해석하지 않는다.
- 방문하지 않은 후보에서 작업 목록 순서로 탐색하며 그룹이 아닌 AC 대상, 이어서 소유 AO의 다른 점에 parent를 현재 점으로 지정하고 children/작업 목록에 추가한다.
- ID 방문 집합으로 이미 도달한 점의 부모를 다시 덮어쓰지 않는다.

- 후보 처리 후에도 방문하지 않은 점은 입력 map 값 순회 순서로 새 탐색을 시작한다(0x522e80–0x522f7c). 이 후반에 별도 ID 정렬은 없다.
- 따라서 root 결과를 좌표·레이어·화면 중심만으로 재구성하거나 모든 점에서 최소 ID 하나를 전체 root로 정하면 안 된다.
- 선호 점의 map 외 입력, 중복 ID 등 비정상 입력의 모든 동작은 별도 검증 대상이다.

## 검증·재개 기준

- 175개 CONNECTED-ALLGROUP 명령 대조 중 이 함수들의 선택 표본도 포함되며 Capstone/기존 AOT 목록과 일치했다.
- 전체 함수·실제 앱 검증이나 독립 표본 누적 합계가 아니다.
- 기존 시험을 반복하지 않았다.

- 다음 우선순위는 원근 도구의 대상 선택과 핸들 변형 수학이다.
- 분기·트리의 여기서 확인한 범위는 재사용한다.
- 동일 dispatch/행렬/이미 확인한 cache를 재분석하지 않는다.
- 실제 앱에서만 결정할 수 있는 경계는 기능표에 따로 남기며 지금 사용자 시험 요청은 없다.
