# 기반 그룹 참조의 저장·점 override·레이어 전체 교환 — 2026-10-15

- 기존 AOT/ELF의 미확인 주소만 추적했다.
- SHARED-RESTORE 보고서의 복원식과 FRAME-CACHE-SAVE 보고서의 레이어 이동 UI 연결을 이어받는다.
- 실제 앱 기능 테스트는 추가하지 않았다.

## 기반 그룹 참조: 저장과 복원

그룹 참조를 상대화하는 실제 코드는 일반 point UPDATE가 아니라 기반 데이터 생성 `_storeRoot`(data_access.dart 0x36ac6c)에 있다. 이 함수는 입력 점 목록을 순회하며 AP.fieldf를 읽고, 입력 기준 점 ID P와 점 수 n으로 상대 참조 r을 만든다(0x36ad54–0x36ada4).

- r = (F >> 6) - P
- group bit4가 켜져 있고 0 ≤ r < n이면 저장 Flags S = (r << 6) OR (F & 0x3f)
- 그 외에는 S = F & 0x2f

실제 명령은 signed arithmetic shift와 하위 32비트 마스크다. 결과 S는 point 행 묶음의 raw_flags 슬롯으로 전달된다(0x36b0e0–0x36b120). `_baseCopyOnRoot`도 기준 ID를 `_storeRoot`의 해당 인수로 전달한다(0x36a0d4–0x36a0d8). 모든 root 생성 호출의 목록 구성·연속 ID 전제까지 확인한 결과는 아니다.

- 복원은 앞서 확인한 `_preloadAnchorPointsWithRoot`의 S bit4 검사와 `((B + (S >> 6)) << 6) OR (S & 0x3f)`이다.
- 유효한 r에 대해 복원 그룹 참조는 B+r이 된다.
- B=P인 경우 원래 참조로 돌아가고, B가 바뀌면 새 점 범위에 맞춰 이동한다.
- 숫자 동일성보다 참조 위치의 대응이 핵심이다.

- 범위 밖 참조와 비그룹 입력은 저장에서 상위 참조와 group bit를 유지하지 않는다.
- 이 조건을 모든 일반 편집의 group 해제 규칙으로 확대하지 않는다.
- 이 보고서가 닫은 것은 기반 생성의 상대화와 기반 읽기의 복원 대응이다.

## 저장 비교에도 복원된 참조를 공급

- `storedPointRows` closure(0x364418)의 기반 조회(0x364530–0x364538)는 현재 프레임 로컬 점 행과 기반에서 공급하는 점 행을 합친다.
- 기반 행의 점 ID는 현재 범위로 변환하고, raw_flags의 그룹 참조에도 위 복원식과 같은 변환을 적용한다.
- 현재 ID에 로컬 override가 있거나 removed point 표시가 있으면 그 기반 행을 제외한다.
- from_root 태그도 별도로 공급한다.

- 따라서 `_saveFiguresChangedOnly`가 DB의 상대 Flags를 앱 내 절대 Flags와 그대로 비교하는 구조로 해석하면 안 된다.
- 유효한 기반 점 행은 비교 전에 현재 프레임의 ID·Flags 표현으로 변환된다.
- 다만 모든 point 비교·moved point·연결 분기를 완료로 세지는 않는다.

- 기반 점을 로컬 행으로 구체화하는 `_storeRootPoint`(0x35f810)의 insert-select(0x35fa24–0x35fa2c)에도 같은 Flags 복원식이 있다.
- 연결 복사는 기반 범위 안의 연결 대상 ID를 현재 범위로 바꾸고 removed point 대상은 제외한다(0x35fb34–0x35fb3c). 일반 point 저장 closure(0x364b38)는 기존 로컬 행 갱신 또는 `_insertAnchorPointRow`와 `_writeAnchorConnections`로 연결된다.
- 이 호출 확인만으로 모든 편집 UI가 이 경로를 호출한다고 단정하지 않는다.

## 점 삭제가 다시 나타나는 것을 막는 표시

`_deleteAnchorPoint`(0x3608b0)는 `_noteAnchorRowsLeaving` 호출 뒤 연결 행과 점 행을 삭제하고 `_listRemovedPoint`를 호출한다(0x360934, 0x360994, 0x3609e0, 0x3609ec).

- `_listRemovedPoint`(0x360a08)의 기록(0x360ac8–0x360ad0)은 해당 점 ID를 포함하는 frame_base 범위에 대해 frame_base_removed_point의 point/frame 쌍을 INSERT OR IGNORE한다.
- 기준 first_point_id는 점 ID 이하의 유효한 최대 시작값을 고르고 상한 point_count 검사도 한다.
- 모든 프레임이나 모든 시퀀스에 무조건 삭제 표시를 만드는 규칙은 아니다.

복원·저장 비교의 기반 조회가 이 표시를 제외하는 조건과 이어지므로, 로컬 행만 지워졌다고 기반 점을 다시 공급하는 방식은 아니다. 앞단의 다른 프레임 보호·root 수명 관리 전체, 삭제 UI별 호출 계약은 별도 미완이다.

## 레이어 위·아래 이동은 시퀀스 범위 교환

UI의 `_moveSelectedLayer`가 호출하는 `SwapLayersAndContentGlobal`(0x5bccf8)은 두 번호 A/B를 임시 번호 T를 거쳐 세 단계로 교환한다.

| 대상 | 교환 범위 | 처리 |
|---|---|---|
| animation_object.layer_id | 해당 sequence ID의 객체 | A→T, B→A, T→B |
| layer_def.layer_index | 해당 sequence의 프레임 중 현재 FrameID 제외 | A→T, B→A, T→B |

- 근거는 객체 변경 실행 0x5bcdc4/0x5bce3c/0x5bce9c와 레이어 정의 변경 실행 0x5bcf1c/0x5bcf84/0x5bcfec다.
- 같은 숫자 교환을 다른 시퀀스까지 전파하지 않는다.
- 이 helper 자체는 DrawOrder·좌표·색 값을 갱신하는 쿼리를 포함하지 않는다.

- 현재 프레임 제외 조건은 레이어 정의 쪽에 있다.
- 바깥 UI 경로가 이 helper 뒤 SaveFrame을 수행하고, 정상 반환 뒤 renderable Frame 캐시 전체 제거·화면 갱신·onion/adjacent 예약으로 이어진다는 이전 근거와 연결된다.
- 따라서 레이어 이동은 현재 프레임 하나의 화면 순서만 바꾸는 것으로 해석하면 안 된다.
- 현재 프레임 메모리의 layer/객체 목록 변화 전체와 개별 AO 앞/뒤 보내기 UI는 다음에 확인한다.

## 검증·남은 범위

- 48개 선택 명령을 비공개 ELF PT_LOAD 직접 읽기/Capstone 결과와 AOT 목록으로 대조하여 일치했다.
- 공개 audit는 주소·일치 여부만 포함한다.
- SQL 문자열의 독립 검증·전체 함수 의미·런타임 결과의 증명은 아니다.
- 기존 표본과 중복 합산하지 않는다.
- 문서만 변경하여 기존 unit/probe/영상 분석·설치·페어링·시작 시험을 반복하지 않았다.

- 다음은 일반 AO 앞뒤 순서 UI와 레이어 이동의 현재 프레임 메모리 갱신을 연결하고, 그 결과를 기능별 정적 확인/실제 앱 검증 필요 항목으로 묶는다.
- root 수명·moved point/연결 전체 분기, codec 전체 재현, 재생 전용 캐시 경계는 미완이다.
- 현재 사용자 추가 작업은 없다.
