# 레이어 병합·삭제·추가의 실제 caller — 2026-10-15

기존 callback inventory에서 확인한 main의 실제 명령을 이어 분석했다. 앞선 [PATH](AOT-PATH-TRACE-2026-10-15.md)의 병합 전용 comparator와 [DIRTY-PROPAGATION](AOT-DIRTY-PROPAGATION-TRACE-2026-10-15.md)의 병합 후 cache 무효화를 재사용하고, 여기서는 대상·순서 재배정·전역 DB 변경을 추가한다. 같은 문자열/PP 검색이나 기존 영상 재분석을 반복한 결과가 아니다.

## 아래 레이어로 병합

`_mergeLayerDown`(0x5b86f4)은 현재 frame이 필요하다. 해당 레이어 번호를 현재 layer 목록에서 찾고 그 위치가0보다 커야 진행한다. 목적지는 목록의 **직전 항목 번호**이며 숫자 ID에서 무조건1을 빼는 것이 아니다. 앞단 전역 설정 guard가 별도로 있으며 그 설정의 모든 UI 의미를 이 보고서에서 새로 확정하지 않는다.

sequence frame을 가져와 필요한 레이어·fill·AO를 공급하고 AO ID별로 각 frame 인스턴스를 모은다. map의 각 AO 목록에서 대표 객체를 동적 getter로 얻어 source/target layer 여부를 분류한다. 이 getter의 concrete dispatch target은 미확정이므로 첫 객체라고 단정하지 않는다. 일반적인 AO layer 메타데이터는 sequence의 AO 행에 존재한다는 기존 저장 근거와 함께 읽는다.

source와 target 대표 목록을 각각 다음 comparator로 정렬한다. 유효 순서 key는 `DrawOrder>0 ? DrawOrder : AO ID`, 같으면 AO ID다(0x5b9c54). 이를 모든 draw planner의 전역 comparator로 일반화하지 않는다. 실제 DB 로드의 COALESCE 정렬과 비양수 처리가 다르다는 기존 정정을 유지한다.

그 후 **target 목록 복사→source 목록 addAll**로 합친다. 합친 대표 목록의 기존 순서 key를 별도 목록으로 만들어 숫자 오름차순 정렬한다. 합친 목록의 k번째 AO ID에 속한 모든 frame 인스턴스에 target LayerId와 정렬된 key의 k번째 값을 배정한다(0x5b94d4/0x5b9524). 따라서 단순 LayerId 교체만도 아니고, 새 DrawOrder를1부터 재번호화하는 루프도 아니다. key 목록 생성에서 자체 중복 제거를 확인한 것은 아니므로 기존 중복 key가 모두 새 고유 값으로 바뀐다고 주장하지 않는다.

frame AO 목록을 정렬한 뒤 frame scope의 SaveFrame closure로 저장한다. 같은 transaction 안에서 `MoveLayerObjectsGlobal`(0x5b9b34)은 sequence의 source LayerId AO 행을 target으로 갱신하고, `DeleteLayerDefinitionsGlobal`(0x5b9a68)은 그 sequence 모든 frame의 source layer_def를 삭제한다. 정상 commit/finish/close 후 frame cache 무효화·onion 목록 초기화·필요한 활성 layer 변경·일시 입력 초기화·dirty·현재 frame reload·주변 prefetch로 이어진다.

마지막은 `_clearAllCanvasHistory`→`_recordCanvasHistoryEntry`다(0x5b9850/58). 병합을 기존 canvas undo stack에 평범한 한 항목으로만 더한다고 해석하면 안 된다. 이 정적 사실은 UI 확인창·실제 rollback·전체 픽셀 변화의 실측 완료를 뜻하지 않는다.

## 레이어 삭제

`_deleteSelectedLayer`(0x5bb280)는 현재 frame이 있고 layer가 둘 이상일 때 진행한다. 선택 활성 layer 번호를 sequence와 함께 `DeleteLayerGlobal`에 전달한다. 결과 뒤 선택·onion/prefetch 상태를 갱신하고 history 전체 clear→현재 entry 기록으로 연결된다.

`DeleteLayerGlobal`(0x5bb4ec)은 transaction→`_deleteLayerGlobal`→commit/finish이며 예외는 finish→rethrow다. 내부는 sequence+layer_id에 해당하는 AO ID 목록을 먼저 구하고 chunk로 처리한다. 처리 순서는 다음과 같다.

1. 해당 AO를 참조하는 fill contour/region 정리 helper 호출.
2. 전체 frame_base 정보를 공급해 `_storeRootPointsLinkedToRows`와 `_deleteLinksToRootPoints` 호출.
3. `_listRemovedRows`에 AO 조건을 전달해 기반 삭제 표시 처리.
4. 해당 AO 실제 점의 outgoing와 incoming 연결을 모두 삭제.
5. 해당 AO의 실제 점·상세·figure_definition_part·animation_object 행 삭제.
6. sequence 모든 frame의 layer_def 삭제.

현재 frame의 layer_def 한 행만 없애고 객체들을 그대로 남기는 명령이 아니다. caller 순서만으로 모든 압축 기반·외부 연결 오류 결과가 보장된다고 쓰지 않는다.

### 기반 점과 incoming 정리

`_storeRootPointsLinkedToRows`(0x5bbae4)는 각 base에서 아직 실제 override도 removed 표시도 없는 가상 점 중, 삭제 대상 AO가 아닌 root 점을 찾는다. 그 점의 root outgoing이 삭제 대상 AO 점을 가리키며 **그 target의 가상 ID에는 실제 override 행이 있는 경우**를 선택해 B+rootFirst−rootID의 가상 ID로 반환한다. 선택한 source를 `_storeRootPoint`의 기본 인수로 먼저 구체화한다. 모든 root 점을 일괄 복제하는 helper가 아니다.

`_deleteLinksToRootPoints`(0x5a456c)는 연결 target이 base의 가상 ID 범위에 있고 실제 override·removed 표시는 없으며 대응 root 점이 존재하는 경우에 incoming 행을 삭제한다. 레이어 삭제 caller는 삭제 대상 AO ID 조건도 공급한다. 실제 점에 대한 incoming/outgoing 대량 삭제와 가상 점에 대한 이 쿼리를 구분한다. `_listRemovedRows`는 제외 frame 목록을 건너뛰고 해당 base의 실제 ID 범위에서 삭제 조건에 맞는 점 ID를 removed_point에 INSERT OR IGNORE한다.

### 공유 fill과 기존 행 표현의 차이

`_deleteFillRegionsReferencingAnimationObjects`(0x3309bc)는 공유 frame_fill_set와 기존 개별 region/segment 행을 모두 처리한다. 공유 set은 max_figure_id 후보 필터 뒤 `FillSetCodec.withoutFigures`(0x332598)를 호출하고, 바뀐 경우 같은 set의 hash/data를 갱신한다.

withoutFigures는 각 stored region에서 삭제 AO를 참조한 segment들의 contourIndex를 모은다. 아무것도 맞지 않으면 원래 region을 유지한다. 영향 contour에0이 있으면 **빈 segment 목록을 가진 stored region을 남긴다**. 0이 없으면 영향 구멍 contour의 모든 segment를 제외하고 색을 유지한 region을 만든다. 하나도 바뀌지 않았을 때는 null을 반환하고, 바뀌었으면 전체 결과를 다시 encode한다. 공유 표현에서 외곽 삭제를 무조건 region 개수 감소로 세면 틀린다.

기존 SQL 행 표현은 삭제 AO를 참조하는 `(region ID, contourIndex)`를 모아 contour0이 맞으면 그 region의 segment와 region 행을 삭제하고, 구멍만 맞으면 해당 contour segment를 삭제한다. 공유 표현과 최종 저장 행 모양까지 동일하다고 단정하지 않는다. 렌더/다음 prune에서 빈 외곽을 처리하는 계약은 기존 FILL-PATH·FILL-PRUNE 보고서와 이어 읽는다.

## 레이어 추가

`GetNextLayerIdForSequence`(0x5ba2bc)는 sequence 모든 frame의 layer_def 중 최대 layer_index+1이며 행이 없으면0이다. main `_addLayer`는 메모리에 열린 frame 레이어도 순회해 이미 쓰는 번호 이상인 후보를 만나면 그 번호+1로 올린다. DB 목록만 보고 열린 상태와 번호가 충돌해도 강행하는 경로가 아니다.

새 Layer는 visible=true, locked=false로 구성한다. `AddLayerToAllFrames`(0x36c3c8)는 sequence 모든 frame에 같은 번호·이름·기본 visible/locked 값을 삽입하되 같은 번호가 이미 있으면 건너뛴다. 이후 onion 갱신·주변 prefetch·현재 history entry 기록이 있다. 병합·삭제의 history 전체 clear와 추가를 같은 동작으로 일반화하지 않는다.

## 검증과 남은 범위

[선택 명령 감사](AOT-LAYER-MERGE-DELETE-ADD-AUDIT-2026-10-15.json)는 기존 ELF/Capstone 대조이며 전체 UI·실제 DB 삭제·실패 rollback·픽셀 동등성 검증은 아니다. 기존 comparator/cache 보고서와 중복 표본을 독립 누적 합산하지 않는다. 일반 AO 앞뒤 변경/별도 lock toggle UI는 여전히 미식별이며 레이어 병합을 그 UI의 발견으로 세지 않는다.

이 범위는 코드·원본 파일을 변경하지 않은 정적 분석이다. 새 설치·페어링·폰 시작 시험·기존 영상/SFA 분석·unit/probe 재실행은 하지 않았다. 남은 것은 전체 UI coverage·비정상/동시 실패·공유 set 변경의 전체 변경범위 기록과 오류 복구 결과다.


## 2026-10-16 추가 근거

본문 당시 미확정이던 목록 getter는 [DISPATCH-TARGETS](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md)의 실제 표/수신 cid/본문으로 정상 목록 계열의 first로 확인했다. 이 한정 미확정 항목을 다시 탐색하지 않는다. history hash 포함 필드는 [UNUSED-AO-FAST-HASH](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md), 실제 시간축 명령은 [TIMELINE-FRAME-COMMANDS](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)를 따른다. 기존 검증을 실제 앱/pixel 완료로 승격하지 않는다.
