# 프레임 복사의 기반 재사용과 DB 복사 분기 — 2026-10-16

[TIMELINE-FRAME-COMMANDS](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)의 실제 caller 뒤에 남아 있던 `_baseCopyOnRoot`, ID 예약, 같은/다른 sequence DB 복사의 정상 분기를 이어 읽었다. 기존 `_storeRoot` 상대 Flags, `_rebaseOnRoot` 완전 비교·실제/가상 점 공급·moved 저장은 재사용한다. 사용자 작품이나 DB에 복사/압축을 실제 실행하지 않았다.

## 기반 재사용은 전체 좌표 동일성 검사가 아니다

`_baseCopyOnRoot`(0x369908)의 입력은 source Frame, target Frame, 새 점 시작 B, 새 점 수 N, 새 점→원 점 map이다. N=0이면 반환한다. 정상 N>0에서 B..B+N−1을 예약한 뒤 target AO 목록 순서/각 점 목록 순서로 점 목록 P와 그 점 소유 AO ID 목록 A를 만든다(0x36994c/0x369970,0x369978–0x369bd0). 내부에서 임의 ID 정렬을 추가하는 함수는 아니다.

source.ID>0이면 기존 base를 찾는다. base가 있을 때 그 count와 N 중 작은 m을 택하고, 기존 root의 첫 m rank에서 AO ID를 조회해 rank→AO ID 배열을 만든다. 다음이 연속으로 맞는 가장 긴 prefix 길이 p를 센다.

- map[P[i]]로 얻는 원 점의 ID가 source base 시작 ID+i다.
- root의 i번째 rank AO ID가 A[i]와 같다.

원 점 map 항목이나 root rank/AO 대응이 다르면 해당 위치부터 prefix를 중단한다(0x369f10–0x36a064). 이 prefix 검사 자체는 x/y·Flags·outgoing 연결·glow·fill 전체의 동일성 검사가 아니다. 따라서 ‘base를 재사용했으니 모든 점 값이 root와 같다’고 축약하면 안 된다.

재사용 적격 조건은 **2×(N−p)≤N**, 즉 적어도 절반 이상에 해당하는 prefix다(0x36a068–0x36a084). p>0이면 source의 기존 root를 재사용하고 target의 base.point_count를 **p**로 넣는다. N 전부를 기반 범위라고 쓰는 것이 아니다. 나머지 및 차이 값의 기록은 뒤 SaveFrame 경로와 연결된다. 이 검사와 compaction의 후보 prefix는 별도 함수이며 같은 의미라고 이름만으로 대체하지 않는다.

## 새 root 생성과 source 재기반 시도

적격 prefix가 없으면 `_storeRoot(target.sequence ID,target AO 목록,P,B)`를 호출해 새 root를 만든다(0x36a0bc–0x36a0d8). 저장하는 상대 Flags·연결 표현은 기존 ROOT-FLAGS-LAYER-SWAP 근거를 유지한다.

새 root 생성 뒤 source에도 base를 붙이려는 선택 경로가 있다. source에 기존 base가 없고, source.ID>0이고, 첫 target 점에 대응하는 원 점 ID가 양수이며 나머지 원 점 ID가 그 시작값+i로 연속일 때 `_rebaseOnRoot`를 호출한다(0x36a138–0x36a2b8). 이 호출만으로 재기반 성공은 확정되지 않는다. helper 내부에는 [ROOT-REBASE-IDLE](AOT-ROOT-REBASE-IDLE-TRACE-2026-10-15.md)의 범위 충돌·AO/Index·점/Flags/연결/상세 완전 일치 guard가 있다. 이 기존 내부 검사를 다시 분석하지 않았다.

target은 재사용이면 p, 새 root면 N으로 frame_base(frame ID,root ID,B,count)를 insert한다(0x36a2bc–0x36a370). caller는 그 뒤 SaveFrame을 실행한다. root prefix 적격과 실제 point/상세 override 저장, source rebase 성공 여부를 각각 구분한다.

## 점 ID 예약은 schema에 따라 두 경로다

`_reserveAnchorPointIds`(0x36c0f4)는 `_anchorPointsCountUp`(0x36c340)의 bool을 사용한다. 이 getter는 이름과 달리 개수를 반환하지 않는다. sqlite_master의 anchor_point 테이블 선언에 AUTOINCREMENT가 있는지 확인하여 DataAccess.field17에 cache하는 **schema 검사**다(0x36c378–0x36c3a4).

| schema | 예약 처리 |
|---|---|
| AUTOINCREMENT 있음 | sqlite_sequence의 anchor_point 항목이 없으면 마지막 예약 ID로 insert. 있으면 현재 seq가 그 값보다 작을 때만 update |
| 없음 | 새 시작 B 뒤까지 이어지는 frame_base 범위를 count=max(0,B−first_point_id)로 줄이고, point_id≥B인 removed point 표시를 삭제 |

인수는 시작 B와 끝 B+N−1이다. AUTOINCREMENT 경로는 seq를 낮추는 것으로 구현하지 않는다. 비AUTOINCREMENT 경로의 쿼리를 현재 frame 하나에만 적용하거나 ‘아무 DB 상태도 바꾸지 않는 예약’이라고 설명하면 다르다. 범위 자체는 확인했지만 malformed DB·임의 B/N·동시 외부 쓰기에서의 무손실/원자성 전체를 보장하는 결과는 아니다.

## DB를 쓰는 AO 복사

상위 `_copyFrameContents`의 같은 sequence/유일 AO ID 빠른 경로는 기존 보고서의 unstored 점 복제를 쓴다. 여기서는 나머지 두 DB 복사 함수의 차이를 추가 연결했다.

| 항목 | CopyAnimationObject 0x36d0e0 | CopyAnimationObjectToSequence 0x36c5d8 |
|---|---|---|
| AO ID | source AO의 ID를 factory에 넘겨 유지 | `_allocateAnimationObjectId`로 새 ID를 얻음 |
| 객체 기본 행 | target frame의 sequence를 조회해 upsert | 대상 sequence/new ID/기존 TypeId·LayerId·배율·순서로 insert 후 새 AO 추적 |
| DrawOrder | 메모리 복사값을 유지하고 저장 helper로 연결 | source DrawOrder>0이면 유지, 아니면 source AO ID를 사용. 새 AO ID로 대체하는 식이 아님 |
| 점/상세 | 새 점을 frame scope의 생성 경로로 기록하고 maps·새 목록을 만듦; AO detail 기록 | 같은 종류의 새 점/map 구성 및 AO detail 기록 |

새 점 생성에는 원 x/y, Index, Flags가 공급된다. 새 점→원 점/원 ID→새 ID map을 작성한다(0x36c880–0x36c9c8). 상위 함수가 이 map으로 outgoing 연결과 group Flags·fill 참조를 새 ID로 연결하는 것은 TIMELINE-FRAME-COMMANDS를 재사용한다. DB helper 각각이 혼자 모든 외부 연결·group/fill 재작성까지 끝낸다고 해석하지 않는다.

새 AO는 TypeId/ARGB/LayerId, 배율, glow 값과 detail 저장을 연결한다. 정상 유한 배율에서 0 이하 값은1을 선택하는 분기가 있으며 NaN/무한대의 전체 규칙은 여기서 확정하지 않는다. 같은 sequence의 duplicate-ID 등 비정상 입력을 무조건 안전하게 복구한다는 주장도 하지 않는다.

## 검증과 남은 범위

[감사](AOT-ROOT-COPY-DB-BRANCHES-AUDIT-2026-10-16.json)는49개 선택 명령을 같은 ELF/Capstone과 AOT에 대조했고 모두 일치했다. 보고서는 정상 구조·분기·인수/저장 연결의 확인이며 실제 복사·앱 렌더·DB 실패 시험이 아니다. 기존 root/codec/probe/영상 시험은 반복하지 않았다.

이 보고서로 base copy의 정상 prefix/새root/source rebase 시도/ID 예약 schema 분기와 같은·다른 sequence AO DB복사 상위 단계를 미수행 목록에서 뺀다. 모든 원시 DB helper의 수명·실패 원자성·비정상 입력·전체 UI/pixel 검증은 별도로 남긴다.
