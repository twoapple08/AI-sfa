# 올그룹 변형 상자·레이어 필터·회전 보조·저장 — 2026-10-15

- 기존 캐시의 AllGroupTarget/Drag 및 TransformBox를 추적했다.
- 이 보고서는 영구 그룹 생성/해제와 올그룹 상자 조작을 구분한다.
- 실제 앱 기능 시험은 추가하지 않았다.

## 대상 수집과 레이어 상태

AllGroupTarget.resolve(0x5f2d08)는 collectAllGroupFigures(0x5f3330)로 Frame의 AO를 필터링하고 각 AO의 점들을 모은다. 다음을 확인했다.

| 조건 | 처리 |
|---|---|
| 범위 boolean이 true | 현재 레이어 번호 검사 생략 |
| 범위 boolean이 false이고 레이어 목록이 비어 있지 않음 | AO LayerId가 Frame 활성 레이어 번호와 같은 것만 유지 |
| 대응 Layer가 is_visible=false | 제외 |
| 대응 Layer가 is_locked=true | 제외 |
| 대응 Layer가 없음 | visible/locked 검사는 nullable 기본 허용 쪽으로 진행 |

- Layer.field13/17이 visible/locked라는 것은 DB 행 공급의 is_visible/is_locked 읽기와 저장(0x33c574–0x33c5ac)으로 연결했다.
- 범위 boolean의 사용자 설정 UI 이름 전체는 확정하지 않았다.
- ‘올그룹은 무조건 프로젝트 전체/전체 레이어/숨김·잠금까지 포함’이라는 해석은 틀리다.
- 대상은 현재 Frame의 공급된 AO 목록에서 온다.

- 화면 점 위치를 만들고 이전 상자 메모리가 현재 대상/위치와 맞는지 검사하여 재사용하거나 aroundPoints로 상자를 만든다.
- 이 캐시는 완성된 렌더 이미지 캐시가 아니다.
- 모든 상자 일치 조건·장기간 수명은 이번 보고서에서 완료로 세지 않는다.

## 드래그 시작 상태

- pan start(0x5f2260)는 Frame/sequence가 있고 대상과 grip을 찾은 경우에만 AllGroupDrag를 만든다.
- drag 객체는 시작 위치·grip·대상 상자와 AO별 시작 ThicknessScale/ObjectScale/GlowRadius를 보관한다(0x5f3858). 점 좌표 계산도 대상에 저장된 시작 화면 위치를 사용한다.
- 이벤트마다 이전 이벤트 결과에 배율을 계속 곱하는 방식이 아니다.

## 공통 좌표 변환

원래 상자 중심 C, 반폭 a, 반높이 b, 각도 θ에 대해 각 시작 점을 원래 상자의 local 좌표로 바꾼다. local의 x/y에 새 반폭/원래 반폭과 새 반높이/원래 반높이를 각각 곱한 뒤 새 상자의 toScreen으로 되돌린다(0x5ea414–0x5ea468). 최종 화면 좌표에서 DrawInformation의 offset/usable size를 역으로 적용하여 AP의 백분율 좌표를 저장한다(0x5ea4a0–0x5ea530).

따라서 수치의 8 최소 크기는 변형 상자의 화면 좌표 단위이며 출력 MP4의 물리 픽셀 8이나 SFA 좌표 8과 같다고 볼 수 없다. 음수·화면 밖 AP 좌표를 지우는 clamp는 이 저장 구간에 없다.

## grip별 상자 계산

| 조작 | 확인한 수학/행동 |
|---|---|
| 상자 이동 | 시작 중심 + (현재 pointer − 시작 pointer) |
| 변 중간 늘이기 | 해당 축의 전체 길이를 max(8, 원래 전체 길이 + 축방향 pointer 변화)로 만들고, 반대 변을 고정하여 중심 이동 |
| 모서리 확대 | 반대 모서리 O 고정. V=O에서 시작 모서리까지의 벡터, d=pointer 변화일 때 k=max(dot(V+d,V)/dot(V,V),8/(2a),8/(2b)); 새 중심 O+k(C−O), 새 반폭/반높이 ak/bk |
| 회전 | 시작 각도 + atan2(현재 pointer−C) − atan2(시작 pointer−C); 길이가 1e−6보다 작은 벡터는 원래 상자 유지 |

- 근거는 TransformBox.dragged(0x5eafc4), _stretched(0x5eb5c4), _scaledFromCorner(0x5eb744)다.
- grip enum의 네 모서리와 rotate는 기존 객체 메타데이터의 이름·index로 대조했다.
- 회전 보조가 켜져 있으면 다음 snap 처리도 적용된다.
- 이 조작을 원근의 자유 사각형 사영변환이나 ‘굽힘’으로 부르지 않는다.

## 속성 변경은 모서리 grip에 한정

AllGroupDrag.dragTo의 네 모서리 분기에서 k=새 반폭/시작 반폭을 사용한다. 시작 snapshot t0/o0/R0에 대해:

- ThicknessScale = t0×k
- ObjectScale = o0×k
- GlowRadius = min(round(R0×k), max(300,R0))

- 마지막 식은 0x5ea6c4–0x5ea6dc의 csel 방향까지 확인했다.
- 상한을 무조건 300으로 쓰거나, 모든 확대에서 원래 반경을 넘지 못한다고 읽으면 틀리다.
- 이 분기에서 glow color/alpha/thickness 변경은 보이지 않는다.
- 변 중간·이동·회전은 위 속성 배율 루프로 들어가지 않고 공통 점 좌표 변환을 수행한다.
- 상세 패널의 크기/굵기 적용과 올그룹 모서리 확대는 같은 속성 집합을 갱신하지 않는다.

## 회전 snap 보조

_BoxTurnSettling.settle(0x5eacc4)은 _applyRotationSnapAssist(0x5ead48)에 기준각 0, 현재 각도의 degree 값과 이전 snap 값을 전달한다. 확인한 정상 finite 입력에서는:

- 보조가 꺼져 있으면 각도를 그대로 사용하고 snap 결과를 유지하지 않는다.
- 새 후보는 round(angle/45)×45도이며 후보와 차이가 0.55도 이하일 때 붙는다.
- 이미 붙은 각도는 차이가 0.96도 이하이면 유지한다. 벗어나면 새 후보를 평가한다.

- 0.55=max(0.55,0.512),0.96=max(0.55+0.35,0.96)이며 모두 실제 ldr dN의 64비트 상수다.
- 진입/이탈 문턱이 달라 경계에서 계속 붙었다 떨어지는 것을 줄이는 방식이다.
- NaN/무한대 예외 경로와 설정 UI 전체를 모든 조작의 일반 규칙으로 확장하지 않는다.

## 종료와 저장

- pan update는 dragTo→EditorFrameCache.dragMoved→화면 repaint 예약으로 간다.
- pan end setState는 markCanvasDirty, drag 참조 제거, 필요 시 leftBox 메모리 보관, activity.ResetAnchorDragState로 이어진다.
- drag.field1f 변경 표시가 true일 때 _saveAfterMove를 호출한다(0x5e8b98).

- _saveAfterMove는 좌표 snapshot과 현재 dirty 상태가 허용하면 movedFigures로 변경 AO를 구해 _saveMovedFigures/SaveFiguresOfFrame을 호출한다.
- 그 조건을 충족하지 못하면 markFrameDataDirty→SaveCurrentFrame이다(0x5d2ef4–0x5d2f28). ‘항상 전체 프레임 저장’도 ‘항상 부분 저장’도 아니다.
- 추가로 movedFigures(0x5d343c)의 비교 범위를 확인했다.
- 같은 Frame 객체, AO 목록 길이/위치별 AO identity, 점 수와 점 ID 순서를 확인하고 불일치하면 null을 반환하여 전체 저장 경로로 넘긴다.
- 구조가 맞으면 각 점 x/y의 정확한 double 비교로 이동 여부를 판단하여 해당 AO만 결과에 넣는다.
- 색·배율·glow 값 자체를 비교하는 함수는 아니다.
- _saveMovedFigures는 결과 목록이 비어 있으면 DB 호출을 생략하고, 정상 경로에서 dirty=false와 history 기록을 수행한다(0x5d2f8c–0x5d2fbc). 이를 모든 속성 편집의 범용 diff로 사용하면 안 된다.
- SaveFiguresOfFrame 내부의 전체 분기는 이번 추가 확인 범위가 아니다.

## 레이어 표시 UI의 별도 연결

레이어 항목 callback(0x5b6ec4)은 is_visible을 반전하여 setState에서 현재 상태를 바꾸고 _syncLayerStateToAllFrames를 호출한다. 활성 레이어를 숨기면 _activateNearestVisibleLayer로 간다(0x5b6fac). DB UpdateLayerAttributesGlobal은 같은 sequence의 해당 layer_index에 visible과 locked를 함께 기록한다(0x5b8020–0x5b802c).

- 이는 표시 토글의 실제 호출과 잠금 값의 전달/올그룹 제외 규칙을 확인한 것이다.
- 별도의 잠금 토글 UI를 찾았다고 쓰지 않는다.
- 새 객체 추가 시 현재 레이어가 숨김이면 visible=true로 바꾼 뒤 같은 동기화 helper를 호출하는 경로도 있다(0x5befb8–0x5befcc).

## 검증과 미완

- CONNECTED-ALLGROUP audit의 175개 선택 명령은 비공개 ELF PT_LOAD/Capstone/AOT 목록과 일치했다.
- 전체 함수/GDT/SQL 의미나 실제 앱 픽셀 시험은 아니다.
- 기존 표본과 중복 합산하지 않는다.
- 문서만 변경하여 기존 unit/probe/영상/설치·페어링·폰 시작 시험을 반복하지 않았다.

- 남은 것은 선택 hit-test 옵션·상자 grip 판정의 전체 경계, 회전 보조 설정 UI, 잠금 토글 UI 존재/dispatch, 좌표 diff만으로 선택 저장하는 경로의 모든 경계 사례, 상세 변형 fallback getter 등이다.
- 이 중 코드에서 확인할 수 있는 부분은 후속 정적 작업이며 실제 앱 검증이 필요한 부분과 구분한다.
- 사용자 추가 작업은 없다.
