# 원근 tap 선택과 사용자 정의 도형 편집 — 2026-10-15

기존 캐시에서 앞단 선택·정상 편집 차이를 확인했다. 실제 앱 시험·기존 영상 분석은 추가하지 않았다. 변형 수학은 PERSPECTIVE-WARP 보고서를 재사용한다.

## 경계 상자 후보 선택

프레임 tap0x5d83ac는 현재 Frame 활성 LayerID를 _resolvePerspectiveSelectionAnchorInContext(0x5d8d98)에 전달한다. 활성 ID가 있으면 context의 layer별 entry 목록, 없으면 전체 entry 목록을 사용한다. 해당 layer에 목록이 없으면 빈 목록이다. context 후보의 앞단 필터는 아래와 같다.

후보 AP ID는 Set으로 중복을 막는다. 각 후보의 연결 집합에 대해 _computePerspectiveBounds(0x5d9264)를 구한다. 이 경계는 연결 점들의 화면 좌표 min/max이며, stroke 두께·곡선의 실제 극값·글로우 경계가 아니다. finite 경계가 없으면 null이다. 먼저18씩 inflate하고, 폭·높이 각각48에 못 미치면 그 축의 양쪽을 똑같이 늘려 최소48로 만든다.

선택은 이 bounds B를 다시26 inflate한 사각형까지의 거리 제곱 d²를 구한다. d²>676이면 후보에서 제외한다. 남은 후보의 점수는 다음과 같다.

score=8 d² +0.0015 width(B) height(B)+0.015 ||pointer−center(B)||².

최저 점수 후보를 선택하며 동점이면 기존 후보를 유지한다. 단순히 가장 가까운 AP·가장 위 DrawOrder·도형 실루엣 내부만 검사하는 규칙이 아니다. bounds를 두 번 확장하고 사각형 바깥 거리 허용도 별도로 두므로 ‘손가락에서26 이내’ 한 숫자로 축약하지 않는다.

## 후보 목록의 표시·점 유형 필터

_buildAnchorPointsMapForFrame(0x527da4)는 Frame AO의 점들을 ID로 모으고 helper 값을 비운다. 이 map 자체가 숨긴 layer 점을 전부 제거하는 함수는 아니다.

_buildEditorCanvasContext는 Layer.field13(visible)이 false인 layer 번호 Set을 만들고(closure0x5d5014), _HitTestAnchorEntry.layer 번호가 이 Set에 없는 점만 남긴다(0x5d4fbc). entry에는 화면 x/y, 소유 AO의 LayerId, Flags bit0(selectable), T2 여부를 기록한다(0x5d4e4c). 일반 entry에서 selectable bit0 true 목록과 T2 목록을 각각 만든다. 원근 bounds 후보는 context.field17의 **visible T2 목록**, 활성 layer 지정 시 field1b의 같은 목록 bucket이다. 모든 AP를 같은 후보로 평가하는 것은 아니다.

공유 getter annotation이 Array._nestedDimensions/MaterialDynamicColors로 보이지만 실제 ELF 몸체는 각각 수신 entry.field1f와 field23 읽기다. 이를 Flutter/색상 연산으로 해석하지 않았다. field1f=selectable, field23=T2는 생성자 쓰기와 연결했다. 이 필터 경로는 Layer.locked(field17)를 읽지 않는다. 모든 앱 UI가 잠금과 무관하다는 뜻은 아니며 다른 도구의 collectAllGroupFigures는 별도 잠금 필터가 있다.

후보 seed가 visible T2라는 사실과, 그 seed에서 계산하는 연결 closure의 map 범위는 별개다. 숨긴 layer와 연결된 점이 closure에 포함되는 모든 상황을 표시 필터 하나로 지웠다고 가정하지 않는다.

## 선택 anchor의 정규화와 fallback

_resolvePerspectiveSelectionAnchor(0x5d85b0)는 연결 점의 map 순서를 따라 T=Flags&0x2e가2인 점을 찾는다. 그중 group bit4가 꺼진 첫 점을 즉시 반환한다. group bit가 켜진 T2 점은 첫 후보를 임시로 보관한다. 끝까지 비그룹 T2가 없으면 보관한 그룹 T2, 그것도 없으면 입력 점으로 돌아간다. 점 ID 최솟값이나 화면 중심을 직접 선택하는 함수가 아니다.

bounds 후보가 없으면 프레임은 _resolveAnchorHitInContext(0x5d3844)를 사용한다. 결과 AP가 있고 결과 거리 제곱이 threshold 이하여야 위 anchor 정규화를 적용한다. 마지막 setState closure0x5d9648에서 후보를 다시 정규화하고 선택 상태를 만든다. null이면 기존 원근 선택을 지우며, 성공하면 기존 선택을 비우고 anchor Select와 새 quad 상태로 간다. tap 자체를 도형 좌표 저장으로 세지 않는다.

일반 점 fallback은 거리만 쓰지 않는다. raw Flags==0x21 또는 T32는 우선도3, T2/4/8은1, 나머지는0이다. 현재 거리 제곱 D와 후보 d에 대해:

- 후보 우선도가 높으면 d≤D+9에서 교체한다.
- 후보 우선도가 낮으면 d+9<D에서 교체한다.
- 우선도가 같으면 d<D에서 교체한다.

9는 제곱거리 비교의 여유값이다. ‘화면거리9’로 해석하지 않는다. 프레임 fallback은 공간 bucket을 조회하고 custom fallback은 자체 entry 목록을 순회한다. bucket 전체 탐색 순서·비정상 좌표는 미완이다.

hit threshold는 _computeMaximumVisibleAnchorRadius→_computeAnchorInnerRadius(41)의 제곱이다. 후자는 DPR override, 없으면 implicitView DPR, 그것도 없으면1을 사용하여 max(5/DPR,(41−9)/DPR)를 구한다. 유효한 양수 DPR에서32/DPR이며, 앞 보고서의 원근 핸들 hit radius18과 다른 경로다. 화면·출력 단위 경계는 RENDER-CONTEXT 보고서를 따른다.

## 일반 프레임과 custom 편집

| 구간 | 프레임 편집 | 사용자 정의 도형 편집 |
|---|---|---|
| bounds 후보 | 동일 helper, 활성 LayerID 전달 | 동일 helper, 활성 LayerID 인수 없음(0x5f7ad0) |
| 점 fallback | 공간 bucket 기반 _resolveAnchorHitInContext | _resolveCustomMoveHitInContext(0x5f7524)의 entry 순회 |
| anchor/quad | 공유 정규화·생성 helper | 공유 정규화·생성 helper |
| 일반 핸들 update | handle→valid→warp→copyWith | 같은 공유 함수 호출(0x5fc788/794/7d8/80c) |
| 올가미 설정 | AllGroupDrag | resolveLassoTarget→gripAt/AllGroupDrag 경로 존재 |
| 드래그 끝 저장 | moved→_saveAfterMove; 조건에 따라 좌표 변경 AO만 저장 | moved→_markFrameDataDirty→_saveCurrentFrame |

custom 저장0x5ced24는 Frame/dirty guard 뒤 PruneInvalidFillRegions를 실행하고 저장 closure를 measureSync한 뒤 dirty fieldab=false/history로 간다. 0x555e0c는 공유 짧은 몸체의 수신 객체 fieldab=true 쓰기이며, 여기서는 실제 custom screen 객체를 전달한다. 상세 dialog에서 같은 주소를 사용한 사실과 혼동하지 않는다. custom 정상 종료0x5fbc0c/14 및0x5fbc7c/84는 전체 현재 프레임 저장 경로다. 프레임의 movedFigures 최적화와 같다고 일반화하지 않는다.

## 검증과 범위

선택 명령의 ELF/Capstone 대조는 AOT-SELECTION-CUSTOM-AUDIT-2026-10-15.json에 기록한다. 전체 함수·실제 앱 동등성의 증명이 아니다. 문서만 변경하여 기존 unit/probe/폰/영상 시험을 반복하지 않았다.

경계 상자·fallback·일반/custom 정상 변형·저장 분기까지 확인했다. 다른 도구의 lock 계약·bucket 충돌·전체 custom undo와 fill prune 계약은 별도 미완이다. 이를 ‘실물 없어서 알 수 없음’으로 분류하지 않으며, 남은 정적 후보로 유지한다.
