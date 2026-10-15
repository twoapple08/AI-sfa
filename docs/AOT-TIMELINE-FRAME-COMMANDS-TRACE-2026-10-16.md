# 시간축 프레임 명령의 실제 연결과 복사 단계 — 2026-10-16

복구된 AOT/동일 ELF에서 `_SequenceActionPortScreenState`의 실제 UI callback과 DB/목록/미리보기 갱신을 연결했다. FrameDialog의 이름으로 추정한 경로를 재사용하지 않았다. 새 앱·영상 시험은 없다.

## 실제 UI 입구

build의 Orientation callback(0x5abc34)은 두 분기 모두 SequenceActionLandLayout을 만들면서 아래 callback을 전달한다(0x5abea4–0x5abf58,0x5ac090–0x5ac144). callback 역할은 이름 나열 순서가 아니라 closure의 실제 인수·호출과 바깥 조건으로 확인했다.

| 명령 | 실제 연결 |
|---|---|
| 앞에 빈 frame | closure0x5aca70→`_insertEmptyFrame(true)` |
| 뒤에 빈 frame | closure0x5aca24→`_insertEmptyFrame(false)` |
| 앞에 붙여넣기 | closure0x5ac9d8→`_pasteFrame(true)` |
| 뒤에 붙여넣기 | closure0x5ac46c→`_pasteFrame(false)` |
| 현재 frame 복사 | closure0x5b16e4→`_copyCurrentFrame`0x5b171c |
| 현재 frame 삭제 요청 | closure0x5accd0→`_requestDeleteCurrentFrame`0x5acd08→확인 상태의 callback→`_deleteCurrentFrame`0x5a9f5c |

true는 현재 index, false는 index+1을 사용하고, insert/paste 모두 [0, frame 수]로 clamp한다. ‘앞/뒤’는 시간축 위치이며 AO DrawOrder UI가 아니다. 삭제 요청은 ‘경고/정말 삭제 하시겠습니까?’ 확인 상태에 삭제 callback을 보관한다. 모든 UI enable/disable·toast·접근성 동작을 분석한 것은 아니다.

## 빈 프레임 삽입

`_insertEmptyFrame`(0x5105ac)은 sequence ID가 음수면 반환한다. 현재 frame이 있으면 기억하고, 계산한 삽입 위치와 별개로 `CreateNewFrame(sequence,9999)`를 호출한다. CreateNewFrame(0x36f778)은 frame(position,sequence_id)를 insert하고 새 ID로 Frame을 만들며 기본 Layer1 visible=true/locked=false를 설정한다. 이 helper 본문은 AO를 복사하지 않는다.

삽입 caller는 새 Frame의 resources를 release한 뒤 현재 frame이 있으면 CopyLayerStructure→GetLayersForFrame→Layer 복제 목록을 적용하고 활성 layer 번호도 복사한다(0x510708–0x5107b0). 복사된 객체가 있는 frame을 ‘빈 frame’ 대신 끼워 넣는 경로와 구분한다. 새 Frame을 목록에 넣고 재정렬 helper를 호출한다. 그 후 배경 map을 설정하고 DB를 닫은 뒤 새 위치를 선택하고 sync로 연결된다. 배경의 전역 기본값/실제 출력 색 전체는 이 호출만으로 새로 확정하지 않는다.

## 복사는 clipboard snapshot, 붙여넣기는 새 DB frame

`_copyCurrentFrame`은 frame 목록이 비면 반환한다. 현재 AO가 이미 비어 있지 않게 메모리에 있었는지를 기억하고, DataAccess로 PopulateFrameAnimationObjects 후 close한다. `_cloneFrameDeep`으로 **별도 frame snapshot을 clipboard static 슬롯에 보관**한다(0x5b1840/0x5b184c). 필요 때문에 로드했던 원본 AO는 다시 release하며, 배경색은 별도의 clipboard 슬롯에 보관한다(0x5b185c/0x5b1878/0x5b189c). 여기서 새 시간축 frame을 insert하는 것은 아니다. deep clone 세부는 기존 snapshot 보고서를 재사용한다.

`_pasteFrame`(0x5ac4b8)은 sequence ID가 음수거나 clipboard가 없으면 반환한다. clipboard AO 목록이 비고 저장된 frame ID가 양수이면 populate 경로가 있다. 계산한 위치로 `MakeCopyForSequenceAtPosition`을 실행한다. 복사 결과의 AO를 release하고, clipboard 배경색이 있으면 그것을, 없으면 data-aware background 조회값을 새 frame ID에 저장한다. 배경 map도 갱신하고 목록 insert/append→재정렬→DB close→새 위치 선택→sync로 이어진다.

### 복사 helper의 분기와 ID map

MakeCopyForSequenceAtPosition(0x34ea78)은 `_inOneTransaction` closure에서 새 frame을 만들고 새 frame scope의 `_copyFrameContents`를 호출한다. source.Frame.sequence ID와 대상 sequence가 같은지를 bool로 전달한다(0x36f930–0x36f96c). ‘같은 sequence 붙여넣기’와 ‘다른 sequence 붙여넣기’를 같은 ID 정책으로 단정하지 않는다.

`_copyFrameContents`(0x3686b0)는 저장된 source.ID>0이고 필요한 목록이 비었으면 AO/layer/fill을 보충한다. 대상 sequence의 기존 layer 구조가 있으면 그것을, 없으면 source layer를 사용해 새 Layer 목록을 만든다. source 활성 번호가 유효하면 유지하고, 없으면 빈 목록은0/그 외 목록 getter fallback이다. 이 getter의 실제 first 해석은 [DISPATCH-TARGETS](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md)를 따른다.

AO 복사에는 다음 세 갈래가 있다.

- **같은 sequence이며 source AO ID가 모두 중복 없이 유일:** `_nextAnchorPointId`로 시작 ID를 얻고 `_copyAnimationObjectUnstored`를 사용한다. 유일성 검사는 empty Set에 ID를 add하는 closure를 every로 실행한 결과다(0x368bc0–0x368bf0,0x36f0cc–0x36f0f0). ‘모든 ID가 양수’ 검사로 바꾸면 틀린다.
- 같은 sequence의 나머지 경우: `CopyAnimationObject`.
- 다른 sequence: `CopyAnimationObjectToSequence`; 이 helper에는 새 AO ID 할당 경로가 있다.

빠른 unstored helper는 새 점 ID를 순차 공급받고 Index/x/y/Flags를 복사하며, 새 점→원래 점과 원래 점 ID→새 ID map을 만든다. AO ID/TypeId/ARGB/LayerId/DrawOrder를 복사하고, 정상 유한 배율에서 thickness/object scale은 양수일 때 유지하고 그 외1을 사용하며 glow 값도 복사한다(0x36d6d8–0x36d7e4,0x36d870–0x36d8dc). NaN/비정상 값의 전체 정책으로 확대하지 않는다.

상위 helper는 원 AO ID→새 AO ID map도 만들고, 원 점의 outgoing 연결 중 새 ID map에 대응이 있는 대상만 새 AnchorConnection으로 붙인다(0x368d60/0x368d64,0x368f68–0x36912c). 맵 밖 연결을 기존 점 ID로 그대로 가져오는 것으로 구현하면 다르다. 이후 각 점의 group Flags는 기존 RemapGroupChildFlags에 원점 map/새 ID map을 전달해 재작성한다(0x369778/0x36ee80/0x36ee88). 그 내부 legacy/범위 규칙은 GROUP-REPAIR 근거를 재사용한다.

같은 sequence의 DB AO LayerId/DrawOrder가 대상 layer에 유효하면 그 값을 사용한다. 그렇지 않으면 복사된 AO의 유효 layer를 유지하고, 필요 시 활성 layer로 fallback한다. 다른 sequence에서 source layer를 추가하는 경로는 번호·이름·visible/locked를 현재 새 frame에 복제하고 AddLayerToAllFrames에도 연결된다(0x3693e4–0x369608). 추가하는 모든 frame에 현재 clone의 visible/locked까지 동일하게 전파한다고 일반화하지 않는다.

fill은 `_copyFillRegion`(0x36e860)에서 객체/점 ID를 새 map으로 변환한다. AO 대응이 없는 segment의 contour ID를 모아 outer0이면 region 자체를 null로, 그 외 해당 contour의 모든 segment를 제외한다. 원 endpoint ID의 새 대응이 없으면 −1을 넣고 t/contour 번호를 유지한다. ring segment는 새 AO ID/기존 contour와 −1 endpoint·t0/1 형태로 만든다. 반환 region은 ID−1/기존 색과 변경 불가 segment 목록을 갖는다. 상위는 null region을 걸러낸다(0x369798–0x3697f4). 실제 폐곡선·malformed topology 검증과는 다르다.

빠른 경로는 이어 `_baseCopyOnRoot`를 호출하고 모든 경우 SaveFrame으로 끝난다(0x369810–0x369858). root helper 내부의 전체 최적화/실패 계약을 이번 호출 연결만으로 완료 처리하지 않는다. 기존 ROOT-FLAGS/ROOT-RELEASE/COMPACTION 근거와 구분한다.

## 삭제는 마지막 frame 하나를 남기는 UI 계약

`_deleteCurrentFrame`은 목록이 비면 반환한다. DataAccess.DeleteFrame→배경 map에서 ID 제거→현재 index의 메모리 frame 제거 순서다. 삭제 후 목록이 비면 position0의 새 frame을 만들고 index0을 선택한다(0x5aa034–0x5aa168). 나머지 frame이 있고 현재 index가 범위 밖이면 마지막 index로 옮긴다. 삭제된 ID를 invalidatedFrameIds로 전달해 sync한다. 따라서 이 caller의 정상 완료 후 frame 수0을 그대로 유지하는 것으로 모델링하면 다르다.

DataAccess.DeleteFrame(0x5aa250)은 삭제 전 실제 점과 현재 base에서 유효하게 공급하는 점의 AO ID 후보를 수집한다. transaction에서 가상 target incoming 연결→해당 frame 실제 점의 연결/점 행→fill→frame별 AO detail/layer/background/tween link→frame 행 삭제를 수행한다. 같은 sequence에서 뒤 position을1씩 당기고, 해당 frame의 base를 drop한 뒤 후보의 unused AO 정리→commit/finish로 연결된다(0x5aa3a8–0x5aa690). unused AO는 [UNUSED-AO-FAST-HASH](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md)의 A∪R 잔존 검사다.

`_deleteAnchorPointRowsForFrame`(0x5aa6d8)은 해당 frame을 exceptFrameIds set에 넣고 `_listRemovedRows`를 호출한 뒤, 해당 실제 점이 source/target인 연결과 점을 삭제한다. 기존 layer 삭제 보조의 removed 표시 근거를 재사용한다. SQL 순서 확인을 전체 실패 원자성/다른 frame의 모든 객체 수명 보장으로 확대하지 않는다.

## 재정렬과 미리보기 cache

`_reorderSequenceFrames`(0x510bdc)는 별도 transaction에서 목록 순서 i와 Frame.Position이 다르면 메모리 Position=i로 바꾸고 해당 frame ID의 DB position을 i로 갱신한다. commit/finish와 예외 finish/rethrow가 있다. frame ID나 AO DrawOrder를 i로 재번호화하는 함수가 아니다. insert/paste/delete caller 전체가 하나의 새 transaction이라는 주장도 하지 않는다.

`_syncSequenceActionAfterFrameMutation`(0x510a7c)은 공유 sequence-action frame 목록을 갱신하고 현재 index를 범위로 clamp한 뒤 preview cache에 invalidatedFrameIds를 넘긴다. 생략 시 빈 ID 목록이고 `FramePictureCache.evictFrames`는 빈 set에서 조기 반환한다(0x5103cc). 삭제는 삭제 ID를 명시한다. 모든 명령이 모든 Picture/Image/editor history를 무조건 clear한다는 해석은 틀린다.

## 검증 범위

[감사](AOT-TIMELINE-FRAME-COMMANDS-AUDIT-2026-10-16.json)는 선택 명령146곳의 Capstone/AOT 대조다. UI 실제 누르기·실제 DB 실패·동시 실행·전체 복사 helper의 모든 입력을 시험한 결과가 아니다. 같은 보고서 안의 미리보기 cache와 재생 버퍼를 혼동하지 않는다. frame 명령의 실제 입구 미식별 항목은 이 범위에서 해소하되 전체 UI coverage 완료는 주장하지 않는다.


## 추가 근거

호출 뒤 남겨 두었던 root prefix 재사용·새 root·source 재기반 시도·ID 예약 schema와 AO DB복사의 정상 분기는 [ROOT-COPY-DB-BRANCHES](AOT-ROOT-COPY-DB-BRANCHES-TRACE-2026-10-16.md)에서 이어 확인했다. 본문의 ‘이 호출 연결만으로 미완’과 실제 helper의 새 확인 범위를 구분한다.
