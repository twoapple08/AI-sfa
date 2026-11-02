# 프레임 배경색 picker의 미리보기·취소·저장·녹화 경로 — 2026-11-02

[FRAME-OPTIONS-POPUP](AOT-FRAME-OPTIONS-POPUP-TRACE-2026-11-02.md)의 “CANVAS COLORS/캔버스 색상” 행에서 이어지는 `BackgroundPickerDialog`를 따라갔다. 이 dialog는 현재 frame의 배경색을 바꾼다. 아래는 정적 AOT/ELF 분석이며 실제 앱 조작·pixel 검증은 아니다. 주소는 libapp 상대주소다.

## 시작 색과 미리보기 상태

- `_getBackgroundColorForFrame`(0x5bad18)은 activity.field_7 객체의 정수 field_7을 기본색으로 쓰고, 그 객체가 없으면 0xFFFFFFFF(흰색)를 쓴다. 이어 state.field_fb map에서 **frame.field_7(frame ID)** 키를 찾아 값이 있으면 그 값을 쓴다. 즉 frame별 배경색은 ID 키 map이고 없으면 기본색이다.
- 팝업 callback 0x5be220은 옵션 팝업을 닫는다(field_73=false). 현재 frame이 있으면 `_beginFrameBackgroundPreview`(0x5be370)가 state+0x113에 frame ID, +0x117에 시작 색을 기록한다. 없으면 `_clearFrameBackgroundPreview`(0x5be358)가 둘을 null로 만든다. 그다음 dialog를 생성해 `onCreate`를 호출하고 state.field_93에 둔다(0x5be310–0x5be324).
- 생성자(0x5a100c)의 이름 인수는 `initialColorOverride`, `isPointColorDialog`, `onPreviewColorChanged`다. 이 경로는 미리보기 callback으로 `_previewFrameBackgroundColor` closure를 넘긴다. 점 색 용도(`isPointColorDialog`)는 이번에 따라가지 않았다.

## 입력과 실시간 미리보기

- dialog 색 처리 구조는 상세 패널 색상 탭과 비슷하다(HSV 목록, 최근색·프리셋). 다른 점은 **알파가 없다**는 것이다. `GetCurrentColor`(0x529ed4)는 HSV 3값만 `_HsvToColor`(0x529f90)에 넘기고, 이 함수는 결과에 0xFF000000을 OR한다(0x52a34c).
- hex 입력(`onHexTextChanged` 0x60adc0)은 trim 후 ‘#’을 보충하고 길이가 7일 때만 처리한다. `_ParseRgbHex`(0x60af14)는 6자리를 radix16으로 parse해 0xFF000000을 OR한다. 따라서 8자리 ARGB 입력은 받지 않는다. FormatException(cid 0xfe9)만 무시하고 다른 예외는 rethrow한다.
- `UpdateColorPreview`(0x529dc8)는 미리보기 callback이 있으면 `_previewFrameBackgroundColor(GetCurrentColor())`를 호출한다(0x529eb8). 이 함수(0x5296a4)는 색과 현재 frame이 있고 map의 현재 값과 다를 때만 setState로 map[frame ID]=새 색을 넣고 canvas를 dirty로 만든다(0x529804). 즉 확인 전에도 편집 화면 배경은 바로 바뀐다.

## 확인·취소

dialog의 `onClick`(0x609dcc)은 눌린 view를 저장된 세 view와 비교한다.

| view 필드 | 동작 |
|---|---|
| field_53 | `AddNewPreset(GetCurrentColor())` |
| field_4b | field_2b(확정)=true, 결과 보관 객체가 있으면 색 기록, field_f가 true면 `AddRecentColor`, listener의 `onSaveColor(색)` 호출 후 dismiss |
| field_4f | dismiss만 |

listener 호출은 dispatch selector −0xc37이다. 실제 표에서 `_EditFramePortScreenState`(cid 3321)의 target은 `onSaveColor`(0x728db4)다. dismiss(0x609ee4)는 dialog.field_27=true만 쓴다.

- **확인:** `onSaveColor`는 현재 frame이 없으면 끝난다. 있으면 DataAccess를 열고 `SaveFrameBackgroundColor(frame ID, 색)`를 실행한 뒤 닫는다. 예외 시에도 close 후 rethrow한다. SQL은 `INSERT INTO frame_background (frame_id, color) VALUES (?, ?) ON CONFLICT(frame_id) DO UPDATE SET color = excluded.color`이며 frame scope 안에서 실행된다. 테이블은 `frame_background(frame_id INTEGER PRIMARY KEY, color INTEGER NOT NULL)`다. 이어 setState로 map[frame ID]=색을 넣고 미리보기 기록을 지우고 field_93=null로 만든다. 마지막으로 `_recordCanvasHistoryEntry`를 호출한다. 이 history 항목을 undo하면 배경색이 되돌아가는지는 확인하지 않았다.
- **취소/닫기:** dialog를 닫는 closure(0x5cccb8)와 `_closeFrameDialogs`(0x5d0ed8)는 dialog.field_2b가 false일 때 `_restoreFrameBackgroundPreview`를 호출한다. 확정됐거나 dialog가 없으면 미리보기 기록만 지운다. 복원 함수(0x5ccd3c)는 기록한 frame ID와 시작 색이 모두 있을 때 map[frame ID]=시작 색으로 되돌린다. 시작 색이 map이 아닌 기본색에서 왔더라도 복원 시에는 그 값이 map에 들어간다.

## 다른 화면과 출력

- frame 배경 map은 편집 화면 `_loadFrame`, frame 개요 `_loadFrameOverviewData`, 시퀀스 작업 화면 `_reloadSequenceActionFrameBackgroundColors`가 `GetFrameBackgroundColors`(`SELECT frame_id, color FROM frame_background WHERE frame_id IN (...)`)로 읽는다.
- 재생/녹화 쪽 `ViewSequencePlayerView.GetBackgroundColorForFrame`(0x518204)은 기본색(없으면 0xFFFFFFFF), 내부 cache, DB `GetFrameBackgroundColor` 순서로 찾는다. `ViewSequencePlayerThread._record`는 frame마다 이 색을 얻어 `RecordPicture`(0x516dc0)에 넘긴다. `RecordPicture`는 내용 영역을 clipRect한 뒤 그 색 Paint로 drawRect를 하고 `Frame.Draw`를 호출한다(0x517180–0x5172dc). 따라서 frame별 배경색은 **녹화 Picture 단계에도 반영되는 정적 경로**가 있다. 최종 인코더 출력 pixel은 확인하지 않았다.
- 기존 [TIMELINE-FRAME-COMMANDS](AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md)의 frame 복사 시 별도 배경 처리와 연결된다. 이번에 다시 추적하지 않았다.

## 검증 범위와 남은 것

[감사](AOT-FRAME-BACKGROUND-PICKER-AUDIT-2026-11-02.json)는 위 경로의 선택 명령 67개와 dispatch 1개를 ELF 디코딩·실제 표와 대조한 결과다. 비공개 검사 스크립트는 cache `checks/validate_frame_background.py`에 있다.

다음은 확인하지 않았다. 휠 터치→HSV 좌표식, 프리셋/최근색 UI 배치와 저장 backend, 점 색 용도, history undo 시 배경 복원, activity.field_7 객체(기본색 보유)의 정체, 실제 화면·인코더 pixel 결과. 정상 정적 경로는 여기서 닫았으므로 같은 함수를 다시 미수행으로 세지 않는다.
