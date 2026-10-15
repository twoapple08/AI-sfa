# 편집 값의 저장 경계 — 2026-10-15

기존 정적 캐시에서 DataAccess의 저장 경로를 추적했다. 실제 앱 왕복 저장·픽셀 검증은 추가하지 않았다. 캐시 분석을 반복하지 않고 편집 값이 DB에 기록되는 조건으로 범위를 이동했다.

## 객체 기본값과 프레임별 상세값

`_saveFiguresChangedOnly`(data_access.dart 0x35abc4)는 기존 행을 수집한 뒤 객체별 비교를 수행한다. 이름만 보고 모든 저장 동작이 단순 diff라고 단정하지 않는다. 공유 기반 프레임과 moved point 처리가 함께 있다.

| 저장 층 | 확인한 값·처리 | 근거 |
|---|---|---|
| 객체 기본 행 | sequence, type, layer, thickness_scale, draw_order를 비교하고 차이가 있으면 해당 기본 행을 갱신 | 0x35bb8c, 0x35c1d0–0x35c424 |
| DrawOrder 보정 | AO.field2f > 0이면 그대로, 아니면 객체 ID(field57)를 저장용 후보로 사용 | 0x35c114–0x35c130 |
| 양의 배율 보정 | thickness(field37), object scale(field3f)가 0 이하이면 AO 값 자체를 1로 바꾼 뒤 비교·저장 | 0x35c0e4–0x35c110 |
| 프레임 상세 행 | ARGB, thickness, object scale, glow radius/color/alpha/thickness | 0x35c4b8–0x35c500, 0x361534 |
| 상세 비교 | `_holdsDetail`은 위 7개 값의 일반 동등성 비교를 차례로 수행; 첫 불일치 false | 0x362c80–0x362f88 |

배율 보정의 float 비교는 NaN 처리 규칙 전체를 뜻하지 않는다. DrawOrder의 대체값은 이 저장용 값 선택이며, 이 구간에서 AO.field2f에 값을 다시 쓰는 것은 확인하지 않았다.

기본 행이 없으면 `_upsertAnimationObjectRow`로 간다(0x35c1a0). 기존 기본 행에는 `_noteSharedFigureValues`도 호출한다(0x35c1cc). 상세 비교용 closure(0x362c34)는 `_holdsDetail`의 결과를 반전하며, 바깥 집계 결과에 따라 UpdateAnimationObjectDetail 호출을 생략하거나 실행한다. 이 결과를 단일 현재 프레임의 행 하나만 보는 규칙으로 축소하지 않는다. 공유 기반·복수 상세 행의 전체 선택 규칙은 남아 있다.

UpdateAnimationObjectDetail(0x361534)은 객체 ID와 프레임 ID로 상세 행의 존재를 검사하고 insert 또는 update로 위 7개 값을 기록한다. DrawOrder는 이 상세 행 필드가 아니다. `_holdsDetail`에서 근사 오차 epsilon 비교는 보이지 않는다. 이는 렌더용 양자화 키와 다른 비교다.

## 그룹 Flags와 점 저장

AP.fieldf는 단순 선택 가능 여부만이 아니다. 기존 행 비교 준비에서 bit0로 selectable을 만들고, 하위32비트의 0x2e 마스크로 anchor point type을 만든다(0x35cd10–0x35cd38). 실제 point UPDATE에는 별도의 raw_flags 슬롯도 있으며, 그 인수는 AP.fieldf 전체를 읽는다(0x35d410). 따라서 type 마스크에 그룹 ID 상위 비트가 없다는 이유로 그룹 정보가 저장에서 잘린다고 해석하면 안 된다.

점 갱신에는 x/y, index, selectable, point type, raw flags, frame/object ID가 연결되고(0x35d500–0x35d508), 연결 목록은 `_sameLinks` 비교 후 필요 시 `_writeAnchorConnections`로 저장된다(0x35d55c–0x35d56c). 그룹 Flags 전체의 비교·공유 기반 프레임 override 분기, moved point 병합은 아직 모두 닫지 않았다. 기존 group UI→Flags→새 record/plan 연결 근거는 DIRTY-PROPAGATION 보고서를 유지한다.

## 채우기 영역과 구멍 정보

`_replaceFrameFillRegions`(0x359044)에는 `_frameBaseOf` 및 `_storeSharedFills`로 조기 반환하는 공유 저장 분기가 있다(0x3590a4–0x3590cc). 모든 저장이 항상 로컬 fill 행 전체 삭제·재생성이라고 단정하면 안 된다. 해당 분기의 전체 적격 조건·공유 표현은 다음 추적 대상이다.

로컬 재기록 분기는 `_deleteFillRegionsForFrame` 호출 후 각 fill의 프레임/ARGB 행을 만들고 segment를 순서대로 기록한다. segment 저장 필드는 region 참조, segment index/kind, 객체 참조, 시작/끝 점 참조, start/end t, contour index다. contour index는 segment.field33에서 직접 읽어 아홉 번째 인수로 전달된다(0x3594c8–0x359534). 따라서 구멍을 구분하는 contour 정보가 이 로컬 저장 경로에도 이어진다. kind에 따른 nullable 점/t 인수 분기가 있어 모든 kind에 모든 값이 들어간다고 확대하지 않는다.

이것은 저장 쪽 연결이며 DB 재공급 시 공유 fill/segment 복원·순서 결정과 실제 앱 왕복 결과는 별도로 남긴다. MP4 내보내기와도 구분한다.

## 검증·반복 점검·다음

새로 선택한 44개 명령은 ELF PT_LOAD 직접 읽기와 Capstone/AOT 목록 대조에서 모두 일치했다. 공개 audit는 주소와 boolean만 담는다. 이 수치는 전체 함수 의미나 런타임 검증 범위가 아니고 기존 표본과 중복 합산하지 않는다. 문서만 수정하여 기존 unit/probe/영상/설치·페어링·시작 시험을 재실행하지 않았다.

이번 작업에서 첫 검색의 의미 주석 필터가 너무 넓어 출력이 잘렸다. 이후 필요한 주소창과 호출·필드로 좁혔고 전체 결과를 재출력하지 않았다. 중복 앱 실험은 없었으며, 이후 큰 함수는 출력 전 선택 결과 개수와 상한을 확인한다.

다음은 공유 frame base의 상세 행 선택·그룹 Flags 비교 및 `_storeSharedFills` → fill/segment 재공급이다. 그 뒤 SwapLayersAndContentGlobal 내부와 일반 AO 앞/뒤 순서 UI를 연결한다. 재생 전용 캐시 경계는 미완으로 유지한다. 현재 사용자 추가 작업은 없다.
