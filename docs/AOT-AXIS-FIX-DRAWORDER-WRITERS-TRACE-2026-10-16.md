# 축 고정 UI 연결과 DrawOrder·잠금 쓰기 경로 전수 조사 — 2026-10-16

Claude Code 환경에서 비공개 백업(SHA256 `d6d5f1ff…cff676`)을 복구해 같은 ELF/AOT를 사용했다. 이전에 반복하지 말라고 한 이름·문자열 검색 대신, **값을 쓰는 쪽(SQL 쓰기·필드 store·비트 연산)을 전수 조사**했다. 새 앱·영상 시험은 없다. [감사](AOT-AXIS-FIX-DRAWORDER-WRITERS-AUDIT-2026-10-16.json)는 선택 명령 49곳의 Capstone/AOT 대조다.

## 1. 일반 AO 앞뒤 순서: DrawOrder를 쓰는 경로 전수

**DB 쓰기.** PP에서 `draw_order`를 쓰는 SQL 6개를 참조하는 함수는 다섯 개뿐이다.

| SQL | 참조 함수 |
|---|---|
| 0 이하 값을 `_id`로 채우는 마이그레이션 | `ApplyMigrations` |
| `UPDATE … SET draw_order = ? WHERE _id = ?` | `UpdateAnimationObjectDrawOrder`(0x50ce88). 유일한 호출자는 객체 생성 경로(0x50ce1c)이며 이미 생성 DrawOrder 보고서에서 확인한 경로 |
| AO 행 UPDATE/INSERT | `_upsertAnimationObjectRow`(0x361da4) |
| 변경 AO만 UPDATE | `_saveFiguresChangedOnly`(0x35abc4) |
| 다른 sequence로 INSERT | `CopyAnimationObjectToSequence`(0x36c5d8) |

열 이름 문자열 `draw_order`를 직접 참조하는 나머지 함수는 행 읽기(`_createAnimationObjectFromRowWithAnchors`, `_readObjectLayers`)와 마이그레이션이다. 따라서 저장되는 순서 변경은 **메모리 AO의 DrawOrder(field_2f)를 바꾼 뒤 일반 저장으로 쓰는 방식**일 수밖에 없다.

**메모리 쓰기.** `->field_2f =` store 367곳 가운데 237곳은 `layout/`의 위젯 build로, 위젯 필드다. 나머지 가운데 정수 DrawOrder로 읽히는 곳은 이미 근거가 있는 경로뿐이었다: 생성자, DB 행 적재, import, 복사 세 helper(`_copyAnimationObjectUnstored`·`CopyAnimationObject`·`CopyAnimationObjectToSequence`), `_cloneFrameDeep`, history `_copyFigure`, `AdoptLiveLayerState`(live LayerId/DrawOrder 보존, 0x604764–0x604770), `_mergeLayerDown`(0x5b9524, 병합 슬롯 재배정). 편집 화면 State 안의 이름 없는 closure 여섯 곳(0x5b23e4, 0x5b2e40, 0x5b4358, 0x5b4508, 0x5b47a8, 0x5f4d6c)은 true/false 또는 좌표 객체를 State 필드에 쓰며, AO DrawOrder가 아니다. `DataAccess` 안의 field_2f store는 SQL 인수 배열·Context 슬롯이다.

**결론(정적):** 51.0.0 AOT에서 DrawOrder를 바꾸는 경로는 생성·복사·import·병합·undo 복원뿐이며, 일반 AO의 앞뒤 순서를 바꾸는 별도 UI handler는 이 조사에서 나오지 않았다. 다음은 확인하지 않았다.

- 위젯 build 237곳의 receiver를 하나씩 확정하지 않았다.
- Blutter 주석 없이 쓰는 경우(예: 동적 SQL 조립)를 완전히 배제하지 않았다.

따라서 **앱 전체에 그런 기능이 없다는 증명은 아니다.** 다만 이전의 "이름 검색으로 미식별"보다 강한 근거다. 화면에서 순서를 바꾸는 사용자 수단은 생성 순서·레이어 병합·레이어 위/아래 이동(레이어 단위, 기존 LAYER-MEMORY·ROOT-FLAGS-LAYER-SWAP 보고서)으로 정리된다.

## 2. 별도 잠금: 스키마와 비트 쓰기

- **잠금 열은 레이어에만 있다.** 스키마의 잠금 열은 `layer_def.is_locked` 하나다. `animation_object`의 열은 `_id, sequence_id, animation_object_type_id, layer_id, thickness_scale, draw_order`뿐이다. 객체 단위 잠금 열은 없다.
- **점 단위 `selectable`은 잠금 토글로 쓰이지 않는다.** `anchor_point.selectable`은 AP Flags bit0이다. 이미 보고된 대로 hit-test closure(0x5d4e4c)가 이 bit0를 읽는다. 그러나 sfa 코드 전체에서 bit0를 켜거나 뒤집는 `orr/eor` 즉시값 연산은 없다.
  - `eor #0x10`은 Dart의 bool 부정이다.
  - `orr #0x10`은 이미 분석한 그룹 비트(`_handleFrameGroupTap`, `_handleCustomGroupTap`, `RemapGroupChildFlags`, `RepairGroupFlags`, `ReassignGroupChildren`)다.
  - 계산값을 저장하는 방식으로 bit0를 바꾸는 경로까지 모두 배제하지는 않았다.
- **잠금처럼 쓰이는 실제 UI는 축 고정과 회전 스냅이다.** 저장되는 객체 잠금 대신, 편집 메뉴에 드래그를 제한하는 토글 두 개가 있다. 아래 3절에서 연결했다.

## 3. 축 고정(가로/세로)과 회전 스냅의 실제 연결

**UI 입구.** `_EditFramePortScreenState._buildCurrentFrameDialog`(0x5b5d78)가 만드는 closure에서 각 토글을 호출한다.

| closure | 호출 |
|---|---|
| 0x5bdef8 | `EditFrameActivity.ToggleHorizontalAxisFix`(0x5bdf5c) |
| 0x5be00c | `EditFrameActivity.ToggleVerticalAxisFix`(0x5be070) |
| 0x5be634 | `EditFrameActivity.ToggleRotationSnap`(0x5be698) |

사용자 정의 도형 편집기도 같은 이름의 메서드를 따로 가진다(closure 0x5ce1c8/0x5ce2dc/0x5ce4cc, 정적 필드 0xc14).

**상태.** 프레임 편집기의 축 고정 모드는 정적 필드 0xc20의 Smi 값이다. 0=없음, 1=세로 고정, 2=가로 고정.

- 세로 토글: 현재 값이 1이면 0, 아니면 1로 바꾼다(0x5be078–0x5be098).
- 가로 토글: 현재 값이 2이면 0, 아니면 2로 바꾼다(0x5bdf64–0x5bdf84).
- 두 모드는 서로 배타다. 한쪽을 켜면 activity의 다른 쪽 bool이 false가 된다(field_2f=세로, field_33=가로; 0x5bdf9c/0x5bdfa0, 0x5be0b0/0x5be0b4).
- `RestoreAxisFixSelection`(0x52568c)은 정적 값으로 두 bool을 다시 맞춘다. `_restoreEditorPreferences`의 closure(0x5255cc)가 다른 환경설정 값을 복원한 뒤 이 함수를 호출한다(0x525664).
- 0xc20을 쓰는 곳은 두 토글뿐이다. 따라서 **환경설정 파일에 저장되지 않고, 앱 프로세스가 살아 있는 동안 편집 화면을 다시 열어도 유지되는 값**으로 읽힌다. 정적 필드의 초기값은 직접 읽지 못했다. 다만 1/2가 아니면 두 bool 모두 false다.
- activity 생성자에서 두 bool은 false, 회전 스냅(field_37)은 true로 시작한다(0x527124/0x527128, 0x527158–0x527160). 회전 스냅 토글은 bool 반전이다(0x5be6a0). 회전 스냅이 환경설정으로 덮이는지는 추적하지 않았다.

**적용 범위.** `_handleFrameCanvasPanUpdate`(0x5e9c44)는 먼저 전역 편집 도구 값 0xe10이 4(원근)·6(올그룹)·7(트윈 링크)이면 각 전용 handler로 보내고 반환한다(0x5e9ca4/0x5e9cc4/0x5e9ce4). **따라서 축 고정은 이 세 모드에 적용되지 않는다.**

일반 점 드래그에서는 activity의 다섯 값이 모두 null이 아니어야 한다: 드래그 점 ID(field_3f), 시작점(field_43), field_f, field_7, `_lastDragPoint`. 시작점(field_43)은 `RecordFrameTapDown`(0x5e734c)과 `BeginAnchorDragSession`(0x5f4fd8)이 기록한다.

그다음 `_applyAxisFix(mode, 시작점, 현재점)`(0x5e9e50)을 호출한다.

- mode 1: `Offset(시작.dx, 현재.dy)`, 즉 x를 시작점에 고정해 세로로만 움직인다.
- mode 2: `Offset(현재.dx, 시작.dy)`, 즉 y를 고정해 가로로만 움직인다.
- 그 외: 현재점을 그대로 쓴다.

결과는 context.field_27에 저장된다(0x5e9dd0). 이 값이 직전 점과 같으면(`==`, 0x5e9df4) 갱신 없이 반환한다. 다르면 `measureSync` closure(0x5ef920)가 `DoMovementAction`에 직전 점(field_23)과 고정된 점(field_27)을 넘긴다(0x5ef9f0, 0x5efa18). 그 뒤의 pose/늘이기 분기는 [MOVEMENT-DISPATCH](AOT-MOVEMENT-DISPATCH-TRACE-2026-10-15.md)를 재사용한다. 같은 드래그의 삭제 영역 hover 판정도 이어진다.

**데이터 영향.** 축 고정은 저장 형식에 새 값을 남기지 않는다. 드래그의 목표점만 바꾸므로 결과는 일반 점 좌표 변경으로 저장된다. 예를 들어 세로 고정으로 드래그한 점은 X가 터치 시작 위치로 투영되어, 이론상 Y만 바뀐다. 다만 연결된 점·늘이기 분기의 파생 이동까지 한 축으로 제한된다는 보장은 아니다.

## 실물 검증으로 남긴 것

축 고정은 SFA로 관측할 수 있다. 한 점을 세로 고정으로 비스듬히 드래그한 전후 내보내기에서 그 점의 X 불변·Y 변화를 보면 된다. [APP-V3](APP-V3-FRAME-COMMANDS-PROTOCOL-2026-10-16.md) 절차의 선택 항목으로 추가했다.

다음은 실제 앱 결과가 아직 없다.

- 회전 스냅의 각도 단위
- 원근/올그룹/트윈 링크 모드에서 축 고정이 적용되지 않는지
- 앱 재시작 후 축 고정이 초기화되는지
