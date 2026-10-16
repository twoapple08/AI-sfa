# 공유 기반 해제·잔여 점 구체화 — 2026-10-15

- 대상: 기존 data_access.dart의 `_releaseLittleUsedRoot`(0x3580c8), `_dropFrameBases`(0x358a2c).
- 실제 DB를 변경하거나 File-2를 최적화하지 않았다.

## 해제 조건

1. 대상 frame의 FrameBase가 없으면 반환한다.
2. 그 base의 root_frame_id를 참조하는 frame_base 행 수가 **정확히 1**이어야 다음으로 간다(0x3581e4의 Smi 2 = 정수 1).
   - 같은 root를 여러 frame이 공유할 때 이 helper가 그중 하나만 즉시 해제하는 경로가 아니다.
3. 두 수를 센다.
   - N: root 점 중 대상에 로컬 override가 없고 removed_point로 제외되지 않은, 아직 root에서 공급해야 하는 점 수
   - R: root frame의 전체 anchor_point 행 수
4. **2N < R**일 때만 구체화를 진행하고, 같으면 반환한다(0x358244/0x3582d0).
   - root 사용 프레임 수가 작다는 이유만으로 해제하지 않는다.
   - 이 수는 화면의 점·도형 비율이나 파일 바이트 크기 비율이 아니다.

## 대상 프레임 구체화 순서

1. 남은 root 공급 점의 대상 ID를 Set에 모은다.
2. root 내부 연결의 양 끝을 대상 ID 범위로 변환해 복사한다.
   - 시작점의 로컬 override·removed, 끝점의 removed를 제외한다.
   - 기존 연결 ID 순서를 따른다(0x358450).
3. 남은 점을 target frame의 로컬 anchor_point 행으로 넣는다(0x35846c).
   - ID는 FrameBase의 기준식, group Flags는 기존 상대 참조 복원식을 적용한다.
4. 대상의 새로 구체화된 점 좌표 map을 만들어 `_readMovedPoints`의 base callback에 공급한다. 복원한 moved 좌표는 anchor_point x/y UPDATE로 반영한다(0x358810→0x358f5c).
5. 대상 AO에 필요한 root 상세 행을 복사한다. 이미 로컬 상세가 있거나 removed_detail이면 제외한다(0x358864).
6. 대상 frame ID 하나를 `_dropFrameBases`에 전달한다(0x3588a8).

해석:
- 이 순서는 root의 기준 좌표만 복사하고 이동량을 버리는 해제가 아님을 보여 준다.
- 공유 fill은 별도 frame_fill_ref 체계다. 여기서 모든 fill row를 복사한다는 근거로 삼지 않는다.

## 참조 없는 root 정리

- `_dropFrameBases`는 지정 frame ID chunk에 대해 removed_point, removed_detail, moved_points, frame_base 행을 삭제한다.
- 그 뒤 frame_root 중 어떤 frame_base도 root_frame_id로 참조하지 않는 root frame을 찾는다(0x358c70).
- 그 root의 점이 소유한 outgoing anchor_connection, root anchor_point, animation_object_detail, frame_root 행을 차례로 삭제한다(0x358d80/dcc/e18/e64).
- 한계:
  - 이것은 root 공유 자료의 정리다. 현재 작품의 모든 일반 frame/AO를 지우는 쿼리로 확대하지 않는다.
  - 모든 incoming 연결·공유 fill의 전역 GC나 동시 DB 실패 rollback까지 확인한 결과는 아니다.

## 다른 프레임 의존성 표시

- `_noteAnchorRowsLeaving`(0x360aec)이 확인하는 것:
  - 대상 점 ID chunk의 다른 frame 로컬 행
  - 다른 frame 점에서 그 ID로 향하는 연결
  - 이어서 `_anyInOtherFrameRange`와 `_rowlessLinkOwners`를 통한 검사도 호출한다.
  - 조건이 맞으면 공통 상태 bool을 true로 쓴다(0x360e74/7c). 단순 로컬 DELETE 하나만 보는 구조가 아니다.
- 추가 소비자 `_recordScope`(0x33056c)는 bool이 true면 scope 대상값을 −1, false면 현재 scope frame ID로 기록한다.
- 해석의 한계:
  - 이 flag를 즉시 복사·연결 복구를 실행하는 메커니즘으로 해석하지 않는다.
  - 모든 소비자·트랜잭션 재배치까지 추적하지 않았으므로 "어떤 편집에서도 다른 frame 참조가 완전히 보호된다"고 주장하지 않는다.
  - 이미 확인한 삭제 표시 ↔ 기반 재공급 제외는 ROOT-FLAGS-LAYER-SWAP 보고서를 재사용한다.

## 검증

- AOT-CODEC-ROOT-AUDIT-2026-10-15.json의 선택 명령은 ELF/Capstone과 대조했다.
- SQL 의미는 캐시의 해당 실행 위치에서 읽은 정적 해석이며, 실제 DB 결과 검증은 아니다.
- 코드·원본 변경이 없어서 기존 시험을 반복하지 않았다.
