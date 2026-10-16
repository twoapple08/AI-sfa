# 레이어 이동의 메모리 갱신과 객체 순서 UI 탐색 범위 — 2026-10-15

- 15:59 KST 세션에서 실행 환경·기존 AOT 캐시 접근이 복구됐다.
- GitHub main 0189517을 가져와 깨끗한 작업 트리에 동기화한 뒤 기존 목록과 ELF/Capstone 환경을 재사용했다.
- 새 설치·추출·폰 시험·영상 분석은 하지 않았다.
- 이번 근거는 기존 ROOT-FLAGS-LAYER-SWAP의 DB 교환과 FRAME-CACHE-SAVE의 저장/캐시 경로 사이에 남아 있던 메모리 변경이다.

## 선택 대상과 범위 검사

`_moveSelectedLayer`(main.dart 0x5bc818)는 현재 Frame과 레이어 목록을 얻고 현재 활성 번호와 일치하는 레이어를 탐색한다. 대상 인덱스는 Up의 true에서 +1, Down의 false에서 -1로 계산하며 범위를 벗어나면 반환한다(0x5bc8e8–0x5bc984). 이 부호를 실제 화면의 위/아래 좌표와 혼동하지 않는다.

선택 번호 A와 이웃 번호 B를 context에 넣고 swapLayers closure(0x5bd210)를 만든다. 활동이 보유한 프레임 목록을 순회해 이 closure를 호출한 뒤, 현재 Frame이 그 목록에 포함되지 않았으면 현재 Frame에도 한 번 호출한다(0x5bca48–0x5bcb84). 목록에 있다는 조건은 이 구간의 ListBase.contains 결과이며 모든 곳의 identity 계약으로 확대하지 않는다.

## swapLayers가 하는 일

| 단계 | 확인한 변경·조건 | 주소 |
|---|---|---|
| 두 레이어 탐색 | Frame.field27에서 A/B 번호와 일치하는 항목을 탐색, 어느 결과든 음수면 변경 없이 반환 | 0x5bd238–0x5bd2f8 |
| 레이어 번호 | A 항목의 Layer.field7에 B, B 항목에 A 대입 | 0x5bd3a8, 0x5bd3c4 |
| 객체 소속 | GetAnimationObjects로 받은 목록을 순회하며 AO.field7 LayerId가 A면 B, B면 A로 변경 | 0x5bd3cc–0x5bd434 |
| 활성 레이어 | Frame.field2b가 A/B 중 하나면 반대 번호로 변경 | 0x5bd43c–0x5bd458 |
| 목록 정렬 호출 | Layer.field7의 정수 compareTo를 수행하는 comparator를 동적 호출에 전달 | 0x5bd468–0x5bd49c, comparator 0x36ef90 |

- 두 레이어가 모두 있어야 메모리 변경을 수행한다.
- 따라서 목록에 있는 모든 프레임을 무조건 변경했다고 쓰지 않는다.
- 이 closure는 현재 메모리에 공급된 AO 목록을 사용하며 전체 시퀀스의 미로드 객체를 여기서 새로 조회하는 코드는 보이지 않는다.

- 레이어 항목은 객체 참조를 유지한 채 번호를 바꾼다.
- AO를 다른 새 객체로 재생성하거나 DrawOrder를 바꾸는 동작과 구분한다.
- 마지막 동적 호출에는 번호 비교 함수가 연결되지만, 이번 표본에서는 GDT 슬롯의 구체 클래스별 대상 전부를 독립 해석하지 않았다.
- 슬롯 번호만으로 모든 목록 클래스의 메서드를 일반화하지 않는다.

## 활동의 선택 상태

- setState closure가 호출하는 EditFrameActivity.UpdateLayerSelectionAfterMove(0x5bd12c)는 목표 인덱스가 0 이상이고 Frame.field27 길이보다 작은 경우만 처리한다.
- 해당 위치의 Layer.field7 번호를 Frame.field2b와 activity.field23에 넣고 목표 인덱스를 activity.field1b에 기록한다(0x5bd1dc–0x5bd1f4). 이 함수 자체가 전체 레이어/객체를 교환하는 것은 아니다.
- 실제 교환은 앞선 swapLayers closure에서 한다.

## DB 저장·화면 기록 갱신과의 연결

정상 경로는 메모리 프레임 순회/현재 Frame 보충 처리 → 기존 확인된 DB BeginTransaction/SwapLayersAndContentGlobal/SaveFrame → commit/close → setState의 renderable Frame 캐시 전체 evict·주변 목록 비움·markCanvasDirty → 선택 상태 갱신 → onion/adjacent 예약으로 이어진다.

- DB helper는 동일 sequence 객체들의 LayerId와 현재 FrameID를 제외한 다른 프레임 layer_def 번호를 교환하며, 현재 Frame은 SaveFrame으로 기록한다.
- 이번 분석은 왜 현재 Frame의 layer 정의가 DB helper에서 제외되어도 정상 경로의 메모리 변경과 별도 저장이 연결되는지 보충한다.
- DB 실패 시 메모리 rollback 전체나 실제 화면 결과는 확인하지 않았다.
- native Picture/image 캐시와 renderable Frame 데이터 객체 캐시도 구분한다.

## 일반 AO 앞뒤 순서 UI: 아직 미식별

이번에는 다음의 제한된 후보 탐색을 수행했다.

- main/관련 activities·dialogs·layout·menu·animation_object 목록의 front/backward/forward/bring/send/draworder/zorder 관련 이름.
- sfa AOT에서 명명된 DrawOrder 호출과 pp 문자열의 앞/뒤·front/backward·DrawOrder 관련 후보.
- main의 raw64 field2f 저장 후보는 객체 타입 확인이 필요하므로 그 개수 자체를 AO 기능 개수로 세지 않는다.

- 일반 AO 순서 UI의 메뉴·dispatch·mutation 연결은 식별하지 못했다.
- pp의 ‘뒤로’(0x24f40)는 flutter_localizations의 generated_material_localizations.dart가 참조하는 탐색용 문구였다.
- 객체 생성 경로의 UpdateAnimationObjectDrawOrder(0x50ce1c)나 레이어 merge의 DrawOrder 비교 함수를 일반 순서 변경 UI로 대체하지 않는다.

- 이는 기능 부재 증명이 아니다.
- 이름 검색에 안 잡히는 anonymous closure, 공통 command dispatch나 동적 호출이 있을 수 있다.
- 같은 이름·문자열 검색을 다시 돌리는 대신 다음에는 객체 상세 패널/command dispatch의 조작 목록을 확인해야 한다.
- 앞뒤 UI가 존재한다고 먼저 가정하고 끝없이 호출을 찾지 않는다.

## 검증과 다음

- 37개 선택 명령을 기존 ELF PT_LOAD와 Capstone/AOT 목록으로 대조하여 일치했다.
- 공개 audit에는 주소·일치 여부만 담았다.
- 전체 GDT/SQL 문자열/함수 의미나 런타임 픽셀 검증이 아니며 과거 표본과 중복 합산하지 않는다.
- 코드 변경 없이 문서와 기능표/인수인계만 변경하므로 기존 unit/probe 시험은 재실행하지 않았다.

- 다음은 객체 상세 패널의 command dispatch에서 실제 제공하는 순서 관련 조작을 식별하는 것이다.
- 없다고 단정하지 않고 미식별 상태를 유지한다.
- 기능표의 현재 프레임 메모리 항목은 이번 정적 근거로 갱신하며 실제 앱 검증 완료로 올리지 않는다.
- root 수명·moved point/연결 전체·codec 전체·재생 전용 캐시는 미완이다.
- 사용자 추가 작업은 없다.
