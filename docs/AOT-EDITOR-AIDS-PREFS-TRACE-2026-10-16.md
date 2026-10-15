# 편집 보조(양파 스킨·앵커 크기·점 표시·어두운 배경) 저장 위치와 출력 영향 — 2026-10-16

같은 복구 ELF/AOT에서 확인했다. 새 앱 시험은 없다. [감사](AOT-EDITOR-AIDS-PREFS-AUDIT-2026-10-16.json)는 선택 명령 10곳의 Capstone/AOT 대조다.

## 결론

양파 스킨, 앵커 크기, 점 표시, 어두운 배경은 **편집기 환경설정**이다. 프로젝트 DB·SFA·영상 출력의 입력이 아니다. AI가 생성할 SFA에 이 값들을 넣을 필요는 없고, 학습 자료의 SFA에도 이 정보는 들어 있지 않다.

## 근거

**환경설정 키.** 편집기 키는 7개다.

| 키 | 기본값 | 비고 |
|---|---|---|
| `OnionPrevCount` | **1** | `mov x16,#2`를 태그 변환 없이 객체 배열에 저장(0x5254b4)했으므로 Smi 표현 2 = 정수 1 |
| `OnionNextCount` | 0 | |
| `OnionColorMode` | false | |
| `OnionGlowEnabled` | false | |
| `AnchorSize` | 14.0 | PP double, 0x525500 |
| `IsDarkBackgroundEnabled` | false | |
| `AreObjectPointsVisible` | true | 0x52552c |

이 키 문자열을 참조하는 함수는 다음뿐이다.

- `_defaultEditorPreferences`(0x525484): 기본값 Map
- `_persistEditorPreferences`(0x552d88), `_restoreEditorPreferences`(0x524dc4)
- 사용자 정의 도형 편집기의 persist/restore

SFA 내보내기·DB 함수는 이 키를 참조하지 않는다.

**저장 위치.** `_saveEditorPreferences`(0x552f14)는 `{"values": Map}`을 MethodChannel의 `saveEditorPreferences`로 넘긴다(0x552f74, 0x552f84). 즉 Android 쪽 환경설정에 저장되며, 프로젝트 DB 테이블이 아니다. Android 쪽 저장 구현의 Java 본문은 이번에 읽지 않았다.

**그리기 경로.** `DrawOnionSkin`은 `_paintEditorUnderlay`(0x42f598) 안에서만 호출된다(0x42f970, 0x42fabc). `_paintEditorUnderlay`의 호출자는 `_EditFrameUnderlayPainter.paint`(0x430d2c)와 `_EditFramePainter`의 closure 두 곳(0x40fd30, 0x430cbc)이다. 모두 편집 화면 painter다.

반면 시퀀스·미리보기 프레임 그림을 만드는 `renderSequenceActionFramePicture`의 호출자는 메인 메뉴 미리보기, 프레임 개요, 프레임 목록, 시퀀스 미니 미리보기다. 이들은 편집기 underlay를 호출하지 않는다. 따라서 양파 스킨은 영상 출력 경로에 섞이지 않는다는 정적 근거가 된다.

## 남은 것

- 앵커 크기와 점 표시가 편집 hit-test 반경에 영향을 주는지(편집 조작감)는 추적하지 않았다. 출력 데이터와는 무관하다.
- `OnionColorMode`·`OnionGlowEnabled`의 그리기 의미, 영상 출력에 양파 스킨이 없다는 실물 확인은 남아 있다. 실물 확인은 렌더 대조 시험에 함께 넣을 수 있다.
- 축 고정·회전 스냅은 [AXIS-FIX](AOT-AXIS-FIX-DRAWORDER-WRITERS-TRACE-2026-10-16.md)를 따른다. 축 고정은 이 7개 키에 없고 앱 실행 중에만 유지된다.
