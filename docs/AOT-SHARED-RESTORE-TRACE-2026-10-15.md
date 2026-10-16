# 공유 프레임의 상세값·그룹·채우기 복원 — 2026-10-15

- 기존 AOT/ELF 캐시에서 저장 표현과 읽기 경로를 연결했다.
- 실제 앱 기능 테스트나 왕복 파일 비교는 새로 실행하지 않았다.
- SAVED-VALUES 보고서의 로컬 저장 근거를 이어받으며, 다음 규칙을 모든 가져오기/내보내기 형식으로 확대하지 않는다.

## 색·glow 상세값의 우선순위

GetAnimationObjectsForFrame의 공유 기반 분기에서 사용하는 조회( data_access.dart 0x34f23c–0x34f244)는 객체별로 다음 우선순위를 적용한다.

1. 현재 프레임에 해당 AO의 상세 행이 있으면 현재 행을 사용한다.
2. 현재 상세 행이 없고 `frame_base_removed_detail`에 현재 프레임/AO 삭제 표시가 있으면 기반 행을 연결하지 않는다.
3. 둘 다 없으면 기반 프레임의 상세 행을 사용한다.

- 상세 행은 ARGB·thickness·object scale·glow radius/color/alpha/thickness를 함께 선택한다.
- 각 필드별로 기반 값과 개별 혼합하는 규칙이 아니라 행을 먼저 선택한다.
- 선택된 행의 nullable 값에는 조회의 COALESCE 기본값이 적용된다.
- 삭제 표시는 AO 전체 삭제와 구분해야 하며, 이 경로에서 상세값 상속을 차단한다.

- 저장 비교용 `storedDetailRows` closure(0x363a30)의 기반 분기(0x363b60)는 현재 행들과, 현재 override 또는 removed 표시가 없는 기반 행들을 합친다.
- 선택적 `only`/chunk 경로도 존재한다.
- 따라서 지난 보고서의 `_holdsDetail`은 공유 기반으로부터 유효한 상세 행을 공급받아 비교할 수 있다.
- 저장과 읽기의 현재 우선/상속 제외 조건이 이어지지만 모든 분기에서 쿼리 실행 횟수가 같다는 뜻은 아니다.

- 객체 표시 후보도 현재 점과, override·삭제 표시로 제외되지 않은 기반 점의 AO ID에서 공급된다.
- 최종 AO 순서는 기존 확인대로 DrawOrder(없으면 AO ID), AO ID 순이다.
- 상세 삭제 표시 하나를 모든 점의 삭제로 해석하지 않는다.

## 그룹 Flags: 로컬 읽기와 기반 점 읽기가 다르다

`_preloadAnchorPointsWithRoot`(0x350030)의 현재 프레임 로컬 점은 raw_flags가 있으면 정수 전체를 AP.fieldf에 넣는다(0x3503d0–0x350468). null일 때는 selectable 및 anchor_point_type으로 조합하는 이전 표현의 fallback이 있다. 이 fallback이 그룹 상위 참조까지 복원한다고 가정하지 않는다.

기반 점 경로는 raw_flags를 읽은 뒤 다음 변환을 수행한다(0x350bdc–0x350cac). F는 읽은 flags, B는 `_FrameBase.field17`에서 가져온 현재 점 범위의 시작값이다(0x3505f0–0x3505f4).

| 조건 | 만들어지는 Flags |
|---|---|
| F의 bit4가 켜짐 | `((B + (F >> 6)) << 6) OR (F & 0x3f)` |
| bit4가 꺼짐 | `F & 0x2f` |

- 실제 명령은 signed arithmetic shift와 하위 32비트 마스크를 쓴다.
- 이 결과를 새 AP.fieldf에 저장한다(0x350e74). 즉 기반 저장의 그룹 참조 부분은 현재 점 ID 범위에 맞춰 변환된다.
- 하위 6비트와 상위 참조를 통째로 같은 절대 숫자로 복사하는 방식이 아니다.
- 비그룹 분기는 group bit와 상위 참조를 유지하지 않는다.

- 이 식은 확인한 기반 점 공급 경로의 규칙이다.
- 그룹 참조를 상대값으로 만드는 저장 쪽 역변환, 모든 점 링크·moved point의 재배치, `repairGroupFlags` 후처리 전체 계약은 추가 추적 대상이다.
- DB raw_flags와 앱 내 flags를 무조건 동일한 숫자로 비교하면 오판할 수 있다.

## 공유 채우기의 저장·재사용

`_storeSharedFills`(0x359dd0)는 FillSetCodec.encode → FNV64 해시 → 같은 해시의 저장 후보 조회로 간다(0x359e0c–0x359e94). 후보의 길이가 다르면 건너뛰고, 길이가 같으면 각 바이트를 비교한다(0x359fc0–0x35a010). 모두 같을 때만 그 set ID를 선택하므로 해시 일치만으로 묶음을 공유하지 않는다. 맞는 후보가 없으면 hash/max_figure_id/data를 가진 set 행을 추가한다.

그 뒤 로컬 fill 행을 정리하고, region ID 범위를 예약하여 `frame_fill_ref`에 frame ID·set ID·first region ID·first point ID를 기록한다(0x35a1f0, 0x35a294, 0x35a318). 이것은 DB 내부 공유 표현이며 기존 파일을 최적화하거나 재압축한 작업이 아니다.

공유 채우기를 읽는 GetFillRegionsForFrame(0x339a14)은 `_readSharedFills` 결과 map에 현재 frame 키가 있으면 그 값을 반환한다. 키가 없는 경우에 로컬 fill/segment 조회로 간다(0x339aa4–0x339b04). 단순히 공유 결과의 목록 길이만으로 fallback을 결정한다고 해석하지 않는다.

`_readSharedFills`(0x33a498)는 frame_fill_ref를 읽고 set의 data를 조회하여 decode한 뒤, ref의 두 기준 ID를 FillSet.regions로 전달한다(0x33a79c, 0x33a81c, 0x33a95c). FillSet.regions는 첫 region ID에 항목 위치를 더해 새 FR ID를 만들고 ARGB를 공급하며, 복원한 segment 목록을 고정·변경 불가 목록으로 넣는다(0x33aad0, 0x33ac9c–0x33acd4).

## 채우기 점 참조·구멍 번호

| 항목 | 저장용 구조 만들기 | 복원용 구조 만들기 |
|---|---|---|
| 객체 참조 | segment.fieldb 보관 | FrameFillSegment.fieldb에 공급 |
| contour index | field33→StoredSegment.field17 | field17→FrameFillSegment.field33 |
| 시작·끝 점 | 음수 sentinel은 null, 나머지는 기준 first point ID를 뺀 상대값 | null은 -1, 나머지는 기준 first point ID를 더함 |
| start/end t | StoredSegment.of의 별도 값 처리 | null이면 0/1 기본값, 아니면 저장 double 공급 |

- 근거는 codec `_StoredSegment.of`(0x35a924) 및 `toSegment`(0x33add0)다.
- 시작·끝 점 변환은 0x35a9a4/0x35a9d4와 0x33ae6c/0x33ae98, contour 공급은 0x35a954/0x35a994 및 0x33ae0c/0x33af1c에서 연결된다.
- 모든 kind가 점/t를 갖는 것은 아니다.

- 따라서 공유 표현의 기반 ID가 바뀌면 FR·점 참조의 절대 숫자가 달라질 수 있다.
- 그 차이만으로 구멍 정보 손실이나 다른 geometry라고 판정하면 안 된다.
- contour 번호는 별도로 복원되는 구조다.
- codec의 전체 바이트 형식·t 정규화·오류 복구와 실제 앱 왕복 보존은 이 보고서에서 완료로 세지 않는다.

## 검증과 남은 범위

- 55개 선택 명령이 기존 ELF PT_LOAD 직접 읽기/Capstone 결과와 AOT 목록 대조에서 일치했다.
- 공개 audit는 주소·일치 여부만 포함한다.
- SQL 내용의 독립 검증이나 전체 함수 의미·픽셀 결과의 증명은 아니며 기존 표본과 중복 합산하지 않는다.
- 코드 변경이 없으므로 기존 unit/probe/영상/설치·페어링·시작 시험을 반복하지 않았다.

- 다음은 기반 저장의 그룹 Flags 상대화·점 override/삭제 표시와 복원 식의 대응을 닫고, SwapLayersAndContentGlobal 및 일반 AO 앞뒤 UI를 확인한다.
- 채우기 codec 전체 구현 재현과 재생 전용 캐시 경계는 별도 미완이다.
- 현재 사용자 추가 작업은 없다.
