# 채우기 구조 정리와 canvas history 복원 — 2026-10-15

기존 AOT/ELF에서 채우기 정리와 사용자 정의 도형의 undo/redo 정상 경로, history 비교와 일반 프레임 undo/redo의 stack·async·DB·live layer 경로를 추적했다. 실제 앱 시험·기존 영상 재분석은 하지 않았다. 모든 UI 진입·실패 복구를 완료했다는 문서는 아니다.

## 채우기를 제거하는 조건

`Frame.PruneInvalidFillRegions`(0x367384)는 현재 AO를 ID map으로 만든 뒤 fill 목록을 **뒤에서 앞으로** 순회한다. 각 `FrameFillRegion.pruneInvalidContoursForObjectsById`(0x3675ec)가 null이면 해당 region을 제거하고, 반환 region이 있으면 그 항목을 대체한다.

region 안의 segment를 음수가 아닌 contourIndex별로 모은다. 외곽 contour0이 없거나 구조 검사에 실패하면 region 전체가 null이다. 양수 contour 중 실패한 ID는 제거 대상으로 모은다. 원래 segment 순서를 유지하면서 음수 contour segment와 제거 대상 contour의 segment를 제외한다. 남은 수가 같으면 원래 region을 반환하고, 달라졌으면 ID·색을 유지한 새 region과 변경 불가 segment 목록을 만든다. 유효한 구멍 번호를 연속 번호로 다시 매기는 루프는 없다.

`_isFrameFillContourStructurallyValid`(0x36789c)의 조건은 다음과 같다.

- 빈 contour는 실패한다. 각 segment가 참조하는 AO가 존재하고 `_matchesSegment`를 모두 통과해야 한다.
- segment 하나인 contour는 위 검사 후 통과한다. 여러 segment이면 circle kind가 하나라도 있으면 실패한다. circle enum은 객체 메타데이터의 이름·ordinal1과 대조했다.
- edge kind는 시작/끝 t가 유한하고 `abs(startT-endT) > 1e-6`이어야 한다. `[0,1]` clamp 조건은 없다. 시작/끝 점 ID가 음수가 아니면 그 ID를 가진 점이 AO 점 목록에 있어야 한다.
- edge의 AO TypeId1·2는 최소2점, TypeId3은 최소3점이 필요하며 다른 유형은 실패한다. circle kind는 TypeId2와 최소2점이 필요하다.

이는 참조·유형·점수·t의 **구조 검사**다. 선분 끝점의 기하학적 일치, 폐곡선 면적, 자기 교차나 구멍이 외곽 안에 있는지까지 검사하는 것으로 확대하지 않는다. 실제 Path 구성의 실패/생략은 기존 [FILL-PATH](AOT-FILL-PATH-TRACE-2026-10-15.md)와 별개다.

## 사용자 정의 도형 undo/redo

`_createCanvasHistorySnapshot`(0x527810)은 sequence의 프레임 목록을 deep clone하고 활성 frame ID도 snapshot에 넣는다. `_sameCustomCanvasHistory`(0x5cf0a0)는 활성 ID, 프레임 수, 같은 위치의 `sameFrameForHistory`를 비교한다. 프레임 ID 비교 helper 0x5cff84는 ID 목록의 수와 위치를 비교한다. 공유 몸체의 Flutter 이름 annotation만 보고 IconData를 비교한다고 해석하지 않는다.

undo(0x6086e0)와 redo(0x6080a8)는 진행 중 상태 플래그·드래그 상태·대상 stack·현재 frame 존재 등의 진입 guard가 있다. guard 각 필드의 모든 UI 의미는 이 문서에서 확정하지 않는다. 저장한 프레임 ID 목록과 현재 목록이 맞지 않으면 history를 reset하고 적용하지 않는다.

undo에서 현재 상태가 undo stack 마지막과 다르면 현재 snapshot을 redo에 넣고 undo 마지막을 적용한다. 같으면 undo 항목이 둘 이상일 때 마지막을 빼 redo에 넣고 새 undo 마지막을 적용한다. redo는 redo 마지막을 꺼낸 후, 현재 상태와 undo 마지막의 중복을 확인하여 필요하면 현재 상태를 넣고, 대상도 undo 마지막과 다를 때 넣은 후 적용한다. 확인한 push 경로에서는 stack 길이가60을 넘으면 가장 오래된 항목 하나를 제거한다. 이를 모든 앱 history의 공통 상한으로 일반화하지 않는다.

`_applyCanvasHistorySnapshot`(0x6083f0)은 적용 중 플래그 설정→일시 입력 상태 초기화→snapshot 프레임 재복제→transaction→각 frame의 fill prune→frame scope를 통한 SaveFrame closure→commit/finish/close→활성 ID를 전달해 custom figure reload로 연결된다. 메모리 객체 포인터만 이전 것으로 바꾸는 undo가 아니다. 예외 경로에도 finish/close가 있지만 임의 DB 실패 후 UI의 완전한 복구까지 새 실측하지 않았다.

## 일반 프레임 복원과 레이어

일반 편집기 undo/redo는 `_applySingleCanvasHistorySnapshotAsync`(0x602dc8)로 연결된다. 확인한 저장 구간은 입력 초기화→snapshot frame deep clone→`_keepLiveLayerState`→변경 marker→transaction→fill prune다. 변경 AO 목록을 사용할 조건이면 `figuresDifferingFrom`→`SaveFiguresOfFrame`, 아니면 `SaveFrame`을 호출한다. 배경색은 별도 저장하고 tween link가 다르면 `SetFrameTweenLinks`를 호출한다. commit/finish/close 후 `FramesChangedSince` 결과를 소비한다.

`_keepLiveLayerState`(0x604198)는 DB에서 복원 대상 frame의 레이어를 읽는다. 현재 편집 frame ID가 대상과 다르면 열린 frame 목록에서 같은 ID를 찾는다. DB 레이어가 비었고 live frame이 있으면 live 레이어 목록을 대신 사용한다. 선택한 레이어를 deep clone해 `Frame.AdoptLiveLayerState`(0x60441c)에 전달한다.

Adopt는 빈 레이어 입력이면 반환한다. 아니면 대상의 레이어 목록을 교체한다. live 활성 layer가 새 목록에 있으면 유지하며, 없으면 동적 getter가 반환한 layer의 번호를 사용한다. 이 fallback getter의 concrete target은 여기서도 미확정이므로 ‘첫 레이어’라고 단정하지 않는다. live AO를 AO ID map으로 만든 후 복원 AO를 순회하여, 같은 ID의 live AO가 있고 그 LayerId가 새 목록에 있으면 **live LayerId와 DrawOrder를 복사**한다. 그렇지 않으면 snapshot AO의 LayerId가 유효할 때는 유지하고, 유효하지 않으면 활성 layer로 바꾼다. 즉 일반 undo가 레이어 배정·표시·순서까지 무조건 과거 값으로 돌리는 경로가 아니다.

## 일반 프레임의 stack과 비동기 진입

일반 undo(0x6053e4)/redo(0x6029fc)는 **frame ID별 두 history map**에서 stack을 찾는다. 적용 중 bool(field0x10f)이 참이면 진입하지 않으며 다른 진행 bool·두 transient 입력·프레임 목록·현재 frame 존재 guard도 있다. 각 transient 필드의 모든 UI 의미는 확정하지 않는다.

undo는 마지막 snapshot의 signature와 현재 signature가 다르면 현재 snapshot을 redo 쪽에 추가하고 undo 마지막을 적용한다. 같으면 undo 항목이 둘 이상일 때 stack 항목을 redo로 옮긴 후 새 마지막을 적용한다. redo는 redo에서 가져온 대상과 현재 상태가 undo 마지막과 중복되는지 signature로 확인하여 필요한 snapshot만 넣고 대상을 적용한다. 확인한 두 경로 모두 추가한 stack이60을 넘으면0번 항목을 제거하는 호출이 있다.

위 stack 역할은 같은 typed-list receiver의 동적 호출 위치·인수·반환값·후속 signature 비교를 종합한 해석이다. GDT selector만으로 전역 메서드명을 확정한 것이 아니다. 예를 들어 항목을 꺼내는 0xbc49와 마지막을 읽는 0x9780의 concrete dispatch table은 기존 cache에 따로 없다. 이 한계를 ‘모든 동적 호출 대상 복원 완료’로 바꾸지 않는다.

`_historySignatureOf`(0x51c704)는 `Frame.GetFastHash`를 얻고 tween link가 있으면 `tweenLinksSignature`와 Object.hash로 합친다. 이 caller의 중복 판정은 custom의 `sameFrameForHistory`를 매번 전체 호출하는 비교와 다르다. hash가 같다는 것이 모든 상태의 충돌 없는 동일성 증명은 아니다. 개별 GetFastHash 필드·충돌 계약 전체는 이 문서 범위 밖이다. single snapshot에는 frame 복사 외 배경색·tween link의 별도 값도 보관하며 link map은 복사 후 변경 불가 view로 만든다.

비동기 적용 함수는 sequence가 없으면 반환한다. 적용 중 bool을 true로 설정한 뒤 **16ms Duration의 Future.delayed를 await**하고 mounted 상태를 다시 검사한다. 그러고 나서 앞 절의 clone/live layer/DB 복원을 진행한다. 이 16ms는 실제 렌더 완료를 기다렸다는 보장이 아니다. 정상 종료에서 mounted면 bool을 false로 바꾸고, 예외 종료에서도 mounted면 false로 바꾼 후 rethrow하는 별도 경로가 있다. 이 함수 하나의 guard로 모든 외부 DB 수정·navigation 경쟁·실패 직전 stack 변경까지 원자적으로 복구된다고 주장하지 않는다.

## history 비교의 민감도

`sameFrameForHistory`(0x5cf1f4)는 frame ID·GetPosition·활성 layer ID와 layer 수/순서를 비교한다. 각 layer의 번호·이름·visible·locked, AO 수/순서와 AO ID·TypeId·ARGB·LayerId·DrawOrder·두 scale·glow4값, 점 수/순서와 ID·Flags·Index·x/y, 각 점의 연결 수/순서와 대상 ID를 비교한다. fill도 수/순서와 색·signature를 비교한다. 순서가 달라도 집합만 같으면 통과하는 helper가 아니다. 별도 배경색·tween link 저장은 이 helper의 비교 전체와 혼동하지 않는다.

`sameDoubleText`(0x5cfef0)는 실제 문자열 변환 호출 없이 double을 비교한다. 둘 다 NaN이면 같고, 그 외에는 수치가 같아야 하며 0에서는 부호도 같아야 한다. 따라서 `+0.0`과 `−0.0`은 다르다. AO 두 scale에서 이 helper를 쓰며 점 x/y에도 같은 판정이 inline된다. bit pattern이 다른 모든 NaN을 서로 다른 수정으로 보는 비교는 아니다. codec의 t에서 −0을 +0으로 정규화하는 규칙과도 구분한다.

## 검증 범위

선택 명령의 원본 ELF/Capstone 대조 결과는 [감사 파일](AOT-FILL-HISTORY-AUDIT-2026-10-15.json)에 기록했다. 전체 함수 의미·완전한 UI coverage·실제 malformed 데이터 결과·pixel 동등성 검증은 아니다. 다른 보고서와 중복 표본을 독립 누적 합산하지 않는다. 문서만 변경했으므로 unit/probe·휴대폰 시작 시험은 반복하지 않았다.


## 2026-10-16 추가 근거

본문 당시 미확정이던 목록 getter는 [DISPATCH-TARGETS](AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md)의 실제 표/수신 cid/본문으로 정상 목록 계열의 first로 확인했다. 이 한정 미확정 항목을 다시 탐색하지 않는다. history hash 포함 필드는 [UNUSED-AO-FAST-HASH](AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md), 실제 시간축 명령은 [TIMELINE-FRAME-COMMANDS](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)를 따른다. 기존 검증을 실제 앱/pixel 완료로 승격하지 않는다.
