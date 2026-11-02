# 프레임 편집 화면 옵션 팝업(줌·축 고정·어니언 스킨·빈공간 색) — 2026-11-02

HANDOFF 후보 중 `PopupFrameOptionsLayout`을 골라 실제 UI callback→저장 필드→사용처를 연결했다. 기존 기능 문서에는 “올가미·축 고정·앵커·양파 스킨·확대: UI/문자열 근거 일부”만 있었다([FEATURE-COVERAGE](FEATURE-COVERAGE.md)). 이 보고서는 **정적 AOT/ELF 분석**이며 실제 앱 조작이나 pixel 검증이 아니다. 주소는 libapp 상대주소다.

## 팝업 생성과 입력값

`_EditFramePortScreenState._buildCurrentFrameDialog`(0x5b5d78)는 state.field_73이 true일 때 `PopupFrameOptionsLayout`을 만든다(0x5b6598). field_8f가 true면 같은 함수의 앞부분이 `DialogPremiumGuideLayout`을 만든다. state.field_17은 late `_activity`(EditFrameActivity)다.

| layout 필드 | 값의 출처 | UI 위치(빌드 0x66a3d0의 라벨) |
|---|---|---|
| b | static 0xc08(=`RewardPlus.isPlusOn()` 결과, 아래) | 구역별 스타일 인수 |
| f | `_isZoomPanEnabled`=activity.field_2b | “ZOOM & PAN/확대 축소”의 ClassicOptionToggle |
| 13 | `_isRotationSnapEnabled`=activity.field_37 | 같은 구역 회전 아이콘(IcMenuRotate)의 강조색 |
| 17 | state.field_af | “ONION SKIN GLOW/양파 스킨 글로우” |
| 1b | 현재 frame 배경색(없으면 activity 값 또는 0xFFFFFFFF) | “CANVAS COLORS/캔버스 색상” 행 |
| 1f/23 | activity.field_2f / field_33 | “AXIS FIX/축 고정”의 VERTICAL/HORIZONTAL |
| 27/2f | state.field_9b / field_a3(정수) | “ONION SKIN”의 PREVIOUS(이전 컷)/NEXT(다음 컷) 슬라이더 |
| 37 | state.field_ab | “COLOR MODE (BLUE / RED)” |
| 3b/3f | state.field_b3 / field_b7 | “BLANK SPACE COLOR/빈공간 색상”의 GRAY/BLACK |

callback 12개(layout field_43..6f)는 모두 setState로 감싼 closure다.

| callback | 실제 동작 |
|---|---|
| 43 → 0x5be6b0 | `_resetCanvasView`: 보기 Matrix4를 identity로 바꾸고 state.field_23·3f=null, 2f·37=0 |
| 47 → 0x5be5d4 | `EditFrameActivity.ToggleRotationSnap`: field_37 = !field_37 |
| 4b → 0x5be4f8 | activity.field_2b(줌/팬 사용) = 토글 값 |
| 4f → 0x5be400 | state.field_af(어니언 글로우) = 값, canvas dirty, 설정 저장 |
| 53 → 0x5be0c0 | 팝업 닫기(field_73=false), 배경 미리보기 시작/해제, 현재 frame 색으로 `BackgroundPickerDialog` 생성(state.field_93). picker 내부는 이번 범위 밖 |
| 57/5b → 0x5bdfac/0x5bde98 | `ToggleVerticalAxisFix`/`ToggleHorizontalAxisFix` |
| 5f/63 → 0x5bdcb4/0x5bdad0 | 이전/다음 장수 설정(Plus gate) |
| 67 → 0x5bd8a4 | 컬러 모드 설정(Plus gate) |
| 6b/6f → 0x5bd7c4/0x5bd6e4 | GRAY: b3=true,b7=false / BLACK: b7=true,b3=false. canvas dirty, 설정 저장 |

## Plus gate

static 0xc08은 `_applyMainMenuPremiumState`(0x50078c)와 `_applyRewardPlus`(0x504fe8)가 `RewardPlus.isPlusOn()`(0x5027c0)의 반환값을 저장하는 슬롯이다. 이전 장수·다음 장수·컬러 모드 wrapper는 이 값을 먼저 본다(예 0x5bdd00). **true가 아니면** 값을 바꾸지 않고 setState(0x5bda9c)로 팝업을 닫고 field_8f=true로 Premium 안내 layout을 띄운다. 글로우·빈공간 색·줌/팬·축 고정·회전 스냅·보기 초기화·캔버스 색 callback에는 이 검사가 없다. 이 문서는 gate의 존재만 기록하며 우회하지 않는다. 안내 dialog의 내용과 Plus 판정 서버 의미는 확인하지 않았다.

## 어니언 스킨

- **장수:** ClassicOptionSlider `_emitValue`(0x65bbd4)는 t=clamp(dx/width,0,1)을 계산해 t×max를 넘긴다. 이 팝업의 max는 5다(0x66b1d4, 0x66c07c). setter(0x5bdd8c/0x5bdba8)는 `LibcRound` 후 정수화(NaN·범위초과는 DoubleToInteger stub)해 field_9b/a3와 static(0x1850/0x1858)에 쓰고 `_refreshOnionFrameCache`를 호출한다. 따라서 이전·다음 장수는 각각 0..5다.
- **목록 생성:** `_buildFrameOnionFrames`(0x523a94)는 장수가 0 이하이거나 frame 목록이 비면 빈 목록이다. k=장수부터 1까지 내려가며 index=현재+방향×k(이전 −1, 다음 +1)를 계산한다. 범위 밖이면 그 k만 건너뛴다. 결과는 **먼 frame부터 가까운 frame 순서**다. 이전 목록은 state+0x11b, 다음 목록은 +0x11f에 둔다. tween-link 편집 모드(static 0x1c20의 Smi 7)에서는 이전 목록 대신 `_tweenLinkOnionFrames`를 쓰고 다음 목록은 비운다(0x5d1f24–0x5d1f8c).
- **그리기:** `_EditFrameUnderlayPainter`→`_paintEditorUnderlay`(0x42f598)가 이전 목록, 다음 목록 순서로 `Frame.DrawOnionSkin`(0x42fcd8)을 호출한다. 목록 위치 i의 거리 d=길이−i다.

| 컬러 모드 | 이전 색 | 다음 색 | 알파(0..255) |
|---|---|---|---|
| 끔 | 0xFFD3D3D3 | 0xFFD3D3D3 | max(200−50d, 30) |
| 켬(BLUE/RED) | 0xFF0000FF | 0xFFFF0000 | max(60−20d, 20) |

`DrawOnionSkin`은 이 알파를 `withAlpha`로 넣은 paint로 `saveLayer`한 뒤 frame을 그린다. 색이 0이 아니면 그 ARGB로 별도 Paint를 준비한다. 이 색이 객체 획을 어떤 방식으로 덮는지는 따라가지 않았다. 글로우 플래그가 false면 객체 그룹별 `_DrawCompositeObjectGlow`(0x420c30) 호출을 건너뛴다(0x430178). 즉 **어니언 글로우 토글은 어니언 frame에서 그룹 글로우를 그릴지 여부**다.

## 축 고정과 회전 스냅·줌/팬

- **축 고정:** 모드는 static 0x1840에 Smi로 둔다(0 없음, 1 세로, 2 가로). 세로 토글은 모드가 1이면 0, 아니면 1로 만들고 세로 표시=모드==1, 가로=false로 둔다. 가로 토글도 같은 방식(2)이다. 따라서 둘은 상호배타다. `_handleFrameCanvasPanUpdate`(0x5e9c44)는 원근/올그룹/tween-link 모드가 아닐 때 `_applyAxisFix(모드, 현재점, activity._touchDownPoint)`를 호출한다(0x5e9dc4). 세로는 Offset(기준.dx, 현재.dy), 가로는 Offset(현재.dx, 기준.dy), 그 밖은 현재점을 그대로 쓴다. 결과가 `_lastDragPoint`와 같으면 이동 처리를 생략한다. 이 모드는 설정 파일 key에 없다. 설정 복원 setState가 `RestoreAxisFixSelection`으로 static 모드를 activity 표시값에 다시 반영한다.
- **줌/팬:** `_handleCanvasScaleUpdate`(0x5f6118)는 activity.field_2b가 false이거나 details.field_1f(포인터 수로 보이는 값)가 2 미만이면 아무것도 하지 않는다. 즉 줌/팬 토글은 두 손가락 보기 변환의 허용 여부다. 이 함수에서는 확대 비율에 유한·양수 검사만 있고 clamp는 보이지 않았다.
- **회전 스냅:** 같은 함수가 회전 변화량을 (rotation−이전 rotation)×180/π로 **도 단위**로 바꾸고, 누적 보기 회전(state.field_37)·lock(field_3f)과 함께 `_applyRotationSnapAssist`(0x5ead48)를 부른다. 스냅이 꺼져 있거나 변화량이 무한/NaN이면 그대로 쓴다. 켜져 있으면 진입 임계=max(0.55,0.512)=0.55°, 해제 임계=max(0.55+0.35,0.96)=0.96°다. lock이 있고 목표각이 lock에서 0.96° 이내면 lock 각도로 고정한다. 그 밖에는 round(목표/45)×45와 목표의 차가 0.55° 이내이면 그 45° 배수로 맞추고 lock을 설정한다. 아니면 원래 변화량을 쓰고 lock을 해제한다. |변화량|>0.001일 때만 π/180을 곱해 보기 행렬에 회전을 적용하고 누적각을 더한다. 이것은 **캔버스 보기 회전**의 스냅이다. 올가미 시작/올그룹 대상 closure에서도 같은 offset 0x37 읽기가 검색됐지만 같은 activity 필드인지 확인하지 않았다.
- **초기값:** EditFrameActivity 생성자(0x527118)는 줌/팬=true, 세로·가로=false, 회전 스냅=true다. 줌/팬과 회전 스냅은 설정 파일 key에 없다.

## 빈공간 색과 설정 저장·복원

- 편집 본문은 field_b7(BLACK)이 true면 검정 0xFF000000, 아니면 0xFFD9D9D9(“GRAY”)를 골라 본문 객체 field_1f에 넣는다(0x5d1ec4–0x5d1eec). 이 색이 underlay에서 쓰이는 세부는 따라가지 않았다.
- `_persistEditorPreferences`(0x552d88)의 key와 값: OnionPrevCount=field_9b, OnionNextCount=field_a3, OnionColorMode=field_ab, OnionGlowEnabled=field_af, AnchorSize=static 0x1848, IsDarkBackgroundEnabled=field_b7, AreObjectPointsVisible=static 0x1870. 같은 값을 static 슬롯에도 복사한다.
- `_restoreEditorPreferences`(0x524dc4)는 저장 map이 null이면 아무것도 바꾸지 않는다. Plus면 장수를 `(값 as num?)?.toInt()`로 읽고 없으면 이전 1·다음 0으로 둔다. 컬러 모드는 값==true다. **Plus가 아니면 저장 값과 무관하게 이전1·다음0·컬러모드false**다. 이 정수 변환이 toInt임은 실제 dispatch 표(cid 60/61→IntegerImplementation.toInt, 62→Double.toInt)로 확인했다. 글로우·어두운 배경은 값==true, AnchorSize는 toDouble 없으면 14.0, AreObjectPointsVisible은 !(값==false)라서 없으면 true다. setState(0x5255cc)는 field_b3=!field_b7로 둔다.
- state 생성자(0x64719c) 초기값: 이전1·다음0·컬러모드false·글로우false·GRAY=true·BLACK=false·팝업/Premium 안내 false.

## 검증 범위와 남은 것

[감사](AOT-FRAME-OPTIONS-POPUP-AUDIT-2026-11-02.json)는 위 경로의 선택 명령 165개를 같은 ELF 디코딩과 대조한 결과다. 비공개 검사 스크립트는 cache `checks/validate_frame_options_popup.py`에 두었다. annotation이 `ArrayLoad r[0]`로 표시한 state/context 접근은 실제 offset 0x17 명령으로 읽었다.

남은 것은 다음과 같다. `BackgroundPickerDialog` 내부와 배경 저장, Premium 안내 내용, AnchorSize·점 표시 UI, 어니언 색 Paint의 합성 방식, 빈공간 색의 실제 그리기 위치는 확인하지 않았다. 축 고정의 frame 외 모드별 적용, 비정상 입력, 실제 화면/pixel 결과도 확인하지 않았다. 이 정적 정상 경로를 다시 미수행으로 세지 않는다. 실제 앱 결과로 승격하지도 않는다.
