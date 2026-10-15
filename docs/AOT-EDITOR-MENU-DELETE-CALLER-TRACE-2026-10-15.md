# 편집 메뉴의 실제 연결과 선택 객체 삭제 — 2026-10-15

`_EditFramePortScreenState`의 실제 callback 연결을 좁혀 확인했다. 이름만으로 미확인 명령을 추측하지 않고 기존 연결·저장·이동 보고서를 재사용했다. 새로운 실제 앱·영상 시험은 없다.

## 메뉴에서 canvas까지

`_buildCurrentFrameDialog`(0x5b5d78)는 모드0–7을 `_setFrameActionMode`로 넘기는 closure들과 도형 추가·변형 적용·배경색·축·zoom/pan·회전 snap·레이어 목록/추가/삭제/이동 관련 callback을 구성한다. 읽은 범위의 이 함수를 ‘프레임 복사·삽입 버튼이 있을 것’이라는 추측의 근거로 쓰지 않는다. 시간축 frame 추가·복사·삭제의 실제 입구는 별도 추적 대상이다.

`_setFrameActionMode`는 인수 정수를 boxed Smi로 보관해 setState closure에 전달한다. callback literal만으로 도구 이름을 붙이지 않고 실제 canvas 분기를 대조했다.

| 실제 mode 값 | 확인한 canvas 연결 |
|---|---|
| 4 | tap→`_handleFramePerspectiveTap`, pan start→`_handleFramePerspectivePanStart` |
| 5 | tap→`_handleFrameFillTap`; `_isFrameFillMode`의 비교 raw10은 Smi 정수5 |
| 6 | pan start→`_handleFrameAllGroupPanStart`; 여기서 전체 올가미 세부 모드를 새로 단정하지 않음 |
| 7 | tap→`_handleFrameTweenLinkTap`, pan start→`_handleFrameTweenLinkPanStart` |

모드0/1의 pose/stretch는 기존 MOVEMENT-DISPATCH 근거를 유지한다. 나머지 mode 이름을 표의 빈칸을 채우려는 추측으로 확정하지 않는다. 기존 전체이동/올가미 보고서가 확인한 실제 분기는 그대로 재사용한다. 특히 4와6, 5와7을 callback 나열 순서만으로 바꿔 적으면 안 된다.

## 선택 객체 삭제의 범위

`_deleteSelectedFrameObject`(0x6022ec)는 현재 frame과 활성 anchor ID가 있어야 한다. frame의 점 map에서 ID가 없으면 상태 갱신 callback으로 종료한다. 점이 있으면 `Deselect` 후 `_deleteConnectedObjects`를 호출하고 상태를 갱신한다.

`_deleteConnectedObjects`(0x5e7748)는 helper 값을 비우고 `GetAllConnectedAnimationObjects`의 AO ID를 set으로 모은다. 선택 점의 소유 AO가 있으면 그 ID도 추가한다. 현재 frame AO 중 이 ID set에 포함된 목록만 대상으로 한다. 연결 수집의 상세 확장은 기존 CONNECTED-TARGET-REFLECTION 보고서 범위를 재사용하며 이 caller만으로 임의 잠금/레이어 정책을 덧붙이지 않는다.

대상 목록이 비면 반환한다. 있으면 transaction 안에서 `DeleteAnchorPointsOfFigures`→현재 AO 목록 removeWhere→fill prune→SaveFrame→commit을 수행한다. 정상 finish/close 뒤 helper 초기화·dirty 관련 bool 초기화·현재 history entry 기록으로 연결된다. 레이어 전역 삭제의 history 전체 clear를 이 명령에도 그대로 적용한다고 해석하지 않는다.

`DeleteAnchorPointsOfFigures`(0x5e798c)는 해당 frame scope에서 closure 0x5e7a20을 실행한다. closure는 대상 AO의 점 ID를 중복 제거해 `_deleteAnchorPoint`를 호출하고, 현재 frame AO/점 정리 뒤 `_cleanupUnusedAnimationObjects`, 필요 경로의 `_releaseLittleUsedRoot`로 이어진다. 레이어 전역 삭제처럼 sequence의 해당 LayerId AO 행을 처음부터 일괄 삭제하는 caller는 아니다. `_deleteAnchorPoint`와 unused AO 정리의 전체 내부 조건·영향 frame 수명은 아직 추가 확인 대상이다.

## 검증·미완

[감사 파일](AOT-EDITOR-MENU-DELETE-CALLER-AUDIT-2026-10-15.json)은 선택 명령의 ELF/Capstone 대조이며 메뉴 전체 UI·실제 삭제·실패 원자성 검증은 아니다. 다른 보고서 표본과 독립 누적 합산하지 않는다. 코드 변경이 없으므로 unit/probe 재실행은 하지 않았다.

남은 구체 범위는 time-axis frame 명령의 실제 caller, `_deleteAnchorPoint`(0x3608b0)·`_cleanupUnusedAnimationObjects`(0x3662a4), `Frame.GetFastHash`(0x51cb64)의 포함 필드와 무효화다. 기존 보고서에 이미 완료한 세부가 있는지 먼저 확인하고 새 분기만 추적한다. 일반 AO 앞뒤/별도 lock toggle UI 미식별과 GDT concrete target 미확정도 유지한다.
