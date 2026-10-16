# 프레임 압축의 단계·후보·삭제 재검사 — 2026-10-15

- 기존 AOT/ELF에서 프레임 compaction의 작업 선택·단계 전환·root 복사·최종 삭제, `_compactionPlainRanks`의 정상 판정과 moved 병합을 연결했다.
- 원본 파일에 압축을 실행하지 않았다.
- helper 이름만으로 모든 점이 완전히 같다고 간주하지 않는다.

## 작업 선택과 재개

- `_compactionStep`(0x4f9b8c)은 진행 job이 있으면 `_advanceCompaction`을 한 번 호출한다.
- 없으면 compacted_sequence에 없는 sequence 중 최소 ID를 선택하고 그 sequence의 frame을 position 오름차순·ID 오름차순으로 적재한다.
- 한 sequence의 목록을 다 소비하면 compacted_sequence에 기록하고 sequence 선택 상태를 해제한다.
- 후보가 더 없을 때 false를 반환한다.

- 현재 frame ID가 반복되면 시도수를 증가시키며 3회를 넘으면 다음 frame으로 넘어가는 guard가 있다.
- 기존 frame_base가 없으면 measure job, 있으면 기존 root 정보를 가져온다.
- 기존 base point_count0은 먼저 `_dropFrameBases`로 정리한다.
- 기존 base 범위 안의 실제 override 점이 없으면 다음 frame으로 넘어가고, 있으면 점 ID−first_point_id의 rank 목록으로 check job을 만든다.
- 이 override 목록 적재를 ‘모든 점을 DB에서 재복제한다’고 확대하지 않는다.

- buildPoints 이후 job을 진행하기 전에는 현재 frame_base가 여전히 job의 root와 first_point_id를 가리키는지 재확인한다.
- 새로 만든 base의 공개 이전 단계에는 point_count0 guard도 있다.
- 조건이 깨지면 진행 job을 해제한다.
- 전체 외부 수정·동시 실패의 원자성을 증명한 것은 아니다.

## 실제 enum과 단계

enum 이름과 ordinal은 객체 메타데이터, 분기는 실제 비교/branch와 대조했다. 화면 렌더의 `show` 동작과 혼동하지 않는다.

| ordinal·단계 | 확인한 역할 |
|---|---|
| 0 measure | frame의 점수와 최소 ID 측정. 최소 2점·정수 최소 ID 조건에 실패하면 skip. 이전 root가 있으면 alignPrevious, 없으면 contiguity. |
| 1 alignPrevious | 이전 root와 AO ID·Index가 연속 대응하는 prefix를 최대 1024 rank씩 검사. prefix가 전체 점수의 절반 이상이고 가상 범위가 비어 있으면 기존 root를 재사용할 후보로 만든다. 실패하면 contiguity로 전환. |
| 2 contiguity | 최소 ID에서 실제 점 ID가 이어지는 prefix를 COUNT 쿼리로 검사. 최대 1024씩 전진하며 중간 구멍이 있으면 이분 탐색으로 길이를 줄인다. 다음 frame이 있고 현재 prefix가 점수의 절반 이상이며 다음 frame에 기존 base가 없고 범위가 사용 가능할 때 alignNext 후보로 연결. |
| 3 alignNext | 다음 frame과 증가 ID 방향 AO·Index prefix 대응을 검사. 대응 0 또는 다음 frame 점수의 절반 미만이면 skip. 통과하면 새 root 행과 point_count0 base를 만들고 buildPoints로 전환. |
| 4 tombstones | 기존 root 재사용 전에 frame에 해당 AO의 점은 있지만 자체 상세가 없는 경우 root 상세 상속을 막을 removed_detail 표시를 기록. base를 point_count0으로 만든 뒤 check 후보 rank 목록을 구성. |
| 5 buildPoints | 원본 prefix를 뒤쪽에서 최대 1024씩 root의 감소 ID 공간으로 복사. prefix 내부 그룹 parent는 상대 rank로 바꾸고 그 밖의 그룹 참조는 기본 mask로 해제. |
| 6 buildLinks | source와 target이 prefix 안인 연결만 감소 ID로 매핑해 DISTINCT 복사. 완료 후 해당 prefix의 AO ID 목록 구성. |
| 7 buildDetails | prefix에 점이 있는 AO의 색·두 scale·glow 상세를 복사. AO별 상세 count=1인 경우만, MIN(row ID) 순서. 완료 후 check로 전환. |
| 8 check | 최대 1024 candidate rank를 `_compactionPlainRanks`에 전달. 통과 callback이 rank 목록을 수집하고 좌표가 다르면 target/base 좌표 map에도 기록. 끝나면 show. |
| 9 show | 통과 rank가 없으면 새 base인 경우 drop 후 skip. 있으면 새 base의 point_count를 설정하고 필요하면 moved 병합 저장을 호출. 이후 remove로 전환. |
| 10 remove | 통과했던 rank를 최대 1024씩 **다시** `_compactionPlainRanks`로 검사한 callback의 점 ID만 모아 outgoing 연결·실제 점 행을 삭제. 완료 후 root 상세 AO 목록을 구성. |
| 11 details | root와 동등한 자체 상세만 삭제. 양쪽 각각 단일 상세 행이고 removed_detail 표시가 없어야 한다. 완료하면 현재 root를 다음 후보로 보관하고 frame cursor 전진. |

- 모든 job이 표의 모든 단계를 순서대로 통과하는 것은 아니다.
- 기존 base check, 이전 root 재사용, 새 root 생성 경로가 갈라진다.
- `_skipCompactionFrame`(0x4ff1bc)은 진행 job 해제와 cursor+1이며 frame 삭제 함수가 아니다.

## 대응 검사와 저장 표현

- `_alignedRanks`(0x4fee84)는 SQL LEFT JOIN으로 `otherID = otherFirst + direction*(frameID−frameFirst)`를 구성한다.
- 원본 ID가 예상 연속 ID인지, 대응 row가 존재하는지, AO ID·index_number가 같은지를 순서대로 검사해 처음 실패할 때까지의 count를 반환한다.
- 좌표·glow·연결까지 이 helper에서 완전히 비교하는 것은 아니다.
- 이전 root 방향은−1, 다음 일반 frame 방향은+1이다.

- `_compactionRangeFree`(0x4fed7c)는 자기 frame을 제외한 다른 frame_base의 가상 범위와 겹치는지 검사한다.
- 실제 anchor_point 전체의 충돌 보장이 이 helper 하나에 들어 있는 것은 아니다.
- contiguity와 이후 판정 범위를 따로 유지한다.

- 새 root의 점 ID는 `rootFirst−(sourceID−frameFirst)`다.
- 그룹 참조가 prefix 내부면 `parentID−frameFirst`를 상위 비트에 저장하고 low6을 유지한다.
- 그 밖의 Flags는 `&0x2f`다.
- 기존 [ROOT-FLAGS](AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md)의 상대화/복원과 연결된다.

- check callback 0x4ff2d4는 x/y가 수치상 다를 때 좌표 map을 기록한다.
- 여기의 `fcmp`는 history 비교의 ±0 구분과 같은 규칙이 아니다.
- 실제 moved 형식은 기존 [FILL-MOVED-CODEC](AOT-FILL-MOVED-CODEC-TRACE-2026-10-15.md)를 사용한다.

## 실제 점 삭제를 허용하는 판정

- `_compactionPlainRanks`(0x4fd140)는 비어 있지 않은 candidate rank 목록의 첫 값과 마지막 값+1로 조회 범위를 구성한다.
- caller가 정렬 rank 목록을 공급하는 경로이며 임의 순서 입력까지 자동 정렬하는 helper가 아니다.
- frame의 실제 점 row, root 점 row, 각 outgoing 목록, 범위의 removed_point를 읽는다.
- root 점은 rootFirst−ID의 rank로 map에 넣고, Flags는 frame의 B 기준으로 부모를 복원한 값으로 조회한다.

- 각 rank는 frame 실제 row와 root row가 모두 있어야 하며 removed_point에 없어야 하고 job의 채택 길이 안이어야 한다.
- AO ID·Index·selectable·anchor type가 같아야 하고 양쪽 raw_flags는 정수이며 같아야 한다.
- 양쪽 x/y는 num이어야 하며 double 변환 값을 callback에 전달한다.
- **처음 후보 검사에서 좌표가 root와 다르다는 이유만으로 탈락시키지는 않는다.** 그 차이를 moved로 보관할 수 있기 때문이다.

- 기존 frame_base 인수를 전달한 재검사에서는 root 좌표 map을 B 기준 실제 ID에 연결하고 기존 moved를 적용한 유효 좌표 map을 만든다.
- 해당 ID가 map에 있고 frame 실제 row의 x/y와 double 수치 equality로 같아야 통과한다.
- 이는 history helper의 NaN쌍·±0 판정과 다르다.

- 연결은 해당 frame 점의 outgoing 원본 목록과, root 점 outgoing을 job 범위 안·removed 대상 제외로 필터하여 B 기준 ID로 변환한 set을 비교한다.
- frame 목록 길이=set 크기, frame 목록의 자체 중복 제거 크기=원래 길이, frame 각 대상이 root 변환 set에 모두 포함되어야 한다.
- 따라서 frame의 중복·외부·불일치 연결은 통과시키지 않는다.
- root의 필터 전 목록 전체가 그대로 frame과 같아야 한다는 비교로 확대하지 않는다.
- 특히 이 helper는 root outgoing 중복을 set으로 모으며, 앞서 `_holdsRootExactly`의 전체 count 비교와 조건이 다르다.

- 모든 조건을 통과한 rank에만 `(rank, frameX, frameY, rootX, rootY)` callback을 호출한다.
- check 단계에서는 통과 목록/좌표 차이를 모으고, remove 단계에서는 이 재검사 callback이 실제 삭제 ID를 모은다.
- 이 구조가 현재 미확인 외부 실패·malformed SQL 값의 전체 안전성을 증명하는 것은 아니다.

## 기존 moved와 새 override의 병합

`_writeCompactionMovedPoints`(0x4fc728)는 현재 frame_base와 job root가 있어야 한다. target map을 새로 만들고 base 좌표 map은 check에서 기록한 root 좌표 map의 복사로 시작한다.

- 새 base면 기존 moved 해독을 건너뛴다. 새 target 좌표를 넣고 base map을 공급해 기존 `_writeMovedPoints`로 저장한다.
- 기존 base면 먼저 dummy base `(0,0)`를 공급해 기존 moved의 **점 ID 목록**을 수집한다. dummy에서 계산한 좌표를 최종 좌표로 사용하는 것이 아니다.
- 그 ID를 root 감소 ID로 바꿔 chunk별로 root의 실제 x/y를 조회한다. num인 좌표를 double로 바꾸고 B 기준 실제 ID key로 base map을 보충한다.
- 보충한 base map으로 기존 moved를 다시 해독하여 유효 target 좌표 map을 만든다. 그 위에 이번 check의 새 target map을 `addAll`하여 같은 ID에서는 새 override가 우선하게 한다.
- 최종 `_writeMovedPoints`의 base callback은 map에서 찾은 값의 nonnull cast를 요구한다. helper가 어떤 값이든 자동으로 0으로 치환하는 계약은 아니다. 앞선 decode에서 base lookup이 null이면 기존 codec 규칙대로 그 점의 callback을 생략한다.

따라서 저장된 잔차 바이트를 단순 이어 붙이거나 dummy 해독 좌표로 전체 blob을 덮는 처리가 아니다. 조회 누락·비정상 수치·DB 실패까지 모든 기존 데이터를 항상 보존한다는 보장은 따로 검증해야 한다.

## 남은 범위·검증

- 남은 범위는 비정상/오류 입력·외부수정·DB 및 파일 실패·전체 수명 결과다.
- 위 caller·SQL·단계·정상 판정·병합을 곧 완전한 무손실 압축 증명으로 바꾸지 않는다.
- [DB-REWRITE](AOT-DB-REWRITE-TRACE-2026-10-15.md)의 파일 교체는 별도 절차다.

- [감사 파일](AOT-COMPACTION-PHASES-AUDIT-2026-10-15.json)은 선택 명령의 원본 ELF/Capstone 일치만 기록한다.
- 다른 보고서 표본과 독립 누적 합산하지 않는다.
- 문서만 변경했고 새 폰/영상/SFA 시험·unit/probe 재실행은 하지 않았다.
