# 상세 패널 색상·글로우 탭의 입력→적용 경로 — 2026-10-27

기능표의 색상/글로우 항목은 렌더링(DrawGlowEffect·shader)과 저장 필드까지만 직접 연결돼 있었고, 상세 패널(ModifyFigureDialog)의 **색상 탭과 글로우 탭 UI callback이 AO 필드를 바꾸는 경로**는 연결되지 않았다. [MODIFY-PANEL-TRANSFORM](AOT-MODIFY-PANEL-TRANSFORM-TRACE-2026-10-15.md)은 ApplyAll의 색상→변형→글로우 순서와 commit/닫기 신호를, 크기·굵기 변형식만 다뤘다. 이 보고서는 그 빈칸만 보충한다. 정적 AOT/ELF 분석이며 실제 앱 조작·pixel 검증이 아니다.

## AO 필드 대응

`AnimationObject.GetXml`의 문자열 순서로 다시 대조했다(0x5af274–0x5af45c): Color=field4f, ThicknessScale=field37(double), ObjectScale=field3f(double), GlowRadius=fieldf, GlowThickness=field27, GlowColor=field17, GlowAlpha=field1f. 기존 [PATH-TRACE](AOT-PATH-TRACE-2026-10-15.md)의 glow 필드 대응과 같다.

## 패널 초기화

- `SetupColorTab`(0x4e294c)은 fieldb7로 한 번만 실행된다. 대상 목록(dialog.field7)이 비어 있지 않으면 `_GrowableList.first`(0x4d5ff4)의 Color를 **원래 색** dialog.field17에 보관하고, 비었으면0xFF000000을 쓴다. 이 값의 알파 바이트를 dialog.fieldf에, `_ColorToHsv` 결과를 dialog.fieldb에 넣고 SyncUI/프리셋/최근색을 불러온다.
- `InitDataFromObject`(0x4e4034)도 첫 AO에서 값을 읽는다. 색 알파·HSV 외에 ThicknessScale·ObjectScale(≤0이면1.0)을 복사한다. glow는 반경=GlowRadius, 알파=GlowAlpha, 색=((GlowAlpha&0xff)<<24)|(GlowColor&0xffffff), 두께=GlowThickness이며 **두께가 0 이하이면 20**으로 바꾼다. 반경에는 이런 기본값이 없다. 대상이 비면 HSV만 0xFF000000에서 만든다.

따라서 여러 AO를 열면 패널의 시작값은 모두 **대상 목록의 첫 AO** 값이다. 평균값이나 공통값을 찾지 않는다. 목록 구성은 기존 CONNECTED-TARGET/MODIFY-PANEL 근거를 따르고 여기서 다시 추적하지 않았다.

## 입력 callback과 pending 표시

색상 쪽 setter는 모두 dialog.fieldc3(색상 pending)와 field1f를 true로 만든다. 글로우 쪽 setter는 fieldcb(글로우 pending)를 true로 만든다.

| UI 입력 | 함수 | 저장되는 dialog 값 |
|---|---|---|
| 색상 휠 | onColorWheelChanged 0x52e1f0 | 휠 closure가 넘긴 double 3개를 HSV 목록[0..2]에 그대로 저장. 범위 보정은 변환 시점에 함 |
| 색상 알파 슬라이더 | closure 0x637c34→onAlphaSeekBarChanged 0x637d34 | 슬라이더 double을 round해 넘김. 퍼센트를0..100으로 clamp한 뒤 alpha=clamp(round(p/100×255),0,255) |
| 색상 hex | onHexTextChanged 0x637960 | 아래 hex 규칙 |
| 색 견본 칸 탭(색상 layout의 caller 0x6373bc/0x637838 두 곳) | ApplyColorFromView 0x6373dc | 견본 값이 null이 아닐 때만 그 ARGB의 알파·HSV를 설정. 두 caller가 각각 프리셋/최근색 칸이라는 배치는 이번에 확인하지 않음 |
| 색 되돌리기 | ResetColorToOriginal 0x63840c | 보관한 원래 색 field17로 복원. 복원도 pending=true로 표시 |
| 글로우 색 휠 | onGlowColorChanged 0x52eff0 | glow HSV 목록(field97)[0..2] |
| 글로우 hex | onGlowHexTextChanged 0x639c30 | 파싱한 ARGB의 알파를 glow 알파(field8f)로, RGB를 glow HSV로. 퍼센트 문구 갱신 |
| 강도(SOLID)/범위(RANGE)/알파 슬라이더 | 0x63a41c/0x63a1e8/0x639ef8 closure | round한 정수를 각각 반경 field7f/두께 field9b/알파 퍼센트로 전달 |
| 글로우 되돌리기 | ResetGlowToOriginal 0x63ab30 | 첫 AO의 GlowAlpha·GlowColor로 **색과 알파만** 복원. 반경·두께는 되돌리지 않음 |

글로우 슬라이더 build(0x6390d4–0x639350)는 `AppText.choose`로 만든 라벨 다음에 슬라이더를 배치한다. 라벨 순서는 “SOLID/강도”→GlowRadius, “RANGE/범위”→GlowThickness, “ALPHA/알파”→GlowAlpha 퍼센트다. 반경·두께 슬라이더 표시값은 0..300으로 clamp되고 범위도 0..300.0이다. 알파 슬라이더는 field8f/255×100이며 범위는 0..100.0이다. 반경·두께 setter(0x63a51c/0x63a2e8) 자체에는 clamp가 없다. 글로우 알파 setter(0x639ff8)는 round(p/100×255)를 0..255로 clamp한다. 따라서 저장 필드 GlowRadius를 UI의 ‘반경’이라는 이름으로 설명하지 않는다. 이 앱 UI에서는 ‘강도’ 라벨이 붙는다.

### hex 규칙

입력은 trim 후 ‘#’이 없으면 붙인다. 길이가 7 또는 9일 때만 처리한다. `_ParseColor`(0x637ae0)는 ‘#’ 뒤 6자리를 radix16으로 parse해 0xFF000000을 OR하고(불투명), 8자리는 그대로 ARGB로 쓴다. 그 밖의 길이는 FormatException을 throw한다. catch는 class id0xfe9만 삼키고 나머지는 rethrow한다. 0xfe9가 FormatException이라는 것은 할당 stub(0x2f1838)의 header tag 0xfe921c(cid bit12부터)로 확인했다.

- 색상 hex는 field23 guard가 true이면 즉시 반환한다. SyncUI(0x4e2fac)와 UpdateColorPreview가 프로그램적으로 문구를 갱신하는 동안 이 guard를 true→false로 둔다. 글로우 hex의 확인한 몸체에는 이 guard 검사가 없다.
- 길이 조건을 통과하면 **parse 전에** pending 표시를 먼저 켠다(색상 0x637a34/0x637a38, 글로우 0x639ce8). 같은 길이의 잘못된 hex는 색 값을 바꾸지 않지만 pending은 남긴다. 그 상태로 적용하면 바뀌지 않은 현재 패널 값을 모든 대상에 쓰게 된다. 이것은 정적 경로상의 결론이며 실제 UI에서 재현하지는 않았다.

## HSV↔ARGB 변환

`_ColorToHsv`(BackgroundPickerDialog 0x4e31f8, 상세 패널도 이 함수를 호출)는 입력의 알파를 무시하고 RGB/255로 일반 HSV를 계산한다. delta=0이면 h=0이다. max가 R이면 60×((G−B)/delta mod 6), G이면 60×((B−R)/delta+2), 그 밖은 60×((R−G)/delta+4)를 쓰고 음수면 360을 더한다. s=max가0이면0, 아니면 delta/max이고 v=max다. 결과는 길이3 목록 [h,s,v]다.

`_HsvToColor`(0x4e37e0)는 h=((h mod 360)+360) mod 360, s·v를 각각 [0,1]로 clamp한다. c=v×s, x=c×(1−|(h/60 mod 2)−1|), m=v−c로 계산하고 60° 구간별 (c,x,0)/(x,c,0)/(0,c,x)/(0,x,c)/(x,0,c)/(c,0,x)를 고른다. 각 채널은 round((채널+m)×255)를 0..255로 clamp한다. 알파는 전달된 정수의 **하위 8비트**만 `<<24`로 쓴다. 비정상 double의 정수 변환은 DoubleToInteger stub 경로로 간다.

## 적용 함수

ApplyAllPendingChangesAndDismiss(0x635134)는 **실행 직전의** pending 표시를 읽는다. 색상 pending이면 field1f도 함께 보관한다(아니면 false). 순서는 ApplyOnlyColor→(변형)→ApplyOnlyGlow다. 마지막에 색상 pending과 field1f가 모두 true이면 `AddRecentColor(GetCurrentColor())`를 호출하고 닫기 신호를 설정한다. 이후 commit/저장 연결은 MODIFY-PANEL 보고서를 따른다.

- **ApplyOnlyColor(0x635bec):** GetCurrentColor(0x52e5bc)=_HsvToColor(clamp(alpha,0,255), HSV)를 한 번 계산하고, 대상 목록의 **모든 AO**에서 Color(field4f)에 같은 ARGB를 쓴다. 이후 변경 여부 fieldaf=true다. 선 굵기·glow·점은 건드리지 않는다.
- **ApplyOnlyGlow(0x635568):** 먼저 dialog의 glow 색=_HsvToColor(glowAlpha, glowHSV)를 계산한다. 이어 모든 대상 AO에 GlowRadius=반경, GlowColor=그 ARGB, GlowAlpha=glowAlpha, GlowThickness=두께의 **네 필드를 함께** 쓴다. GlowColor 알파 바이트는 GlowAlpha 하위 8비트다. 기존 렌더 경로는 GlowColor 알파 대신 GlowAlpha를 쓴다.

결과적으로 여러 AO를 대상으로 글로우 슬라이더 하나만 바꿔도, 나머지 글로우 값은 첫 AO에서 읽은 값으로 모든 대상에 통일된다. 첫 AO의 GlowThickness가 0 이하였다면 20으로 기록된다. 색상도 대상별 상대 변경이 아니라 하나의 ARGB로 덮어쓴다. glow pending이 없으면 ApplyOnlyGlow는 실행되지 않으므로 색상만 바꾼 경우 glow 필드는 보존된다.

## 최근색·프리셋 저장

- AddRecentColor(0x6351f4)는 static 저장소의 “r0”..“r6” 7칸을 읽는다(없으면0xFFE0E0E0). 같은 정수값을 removeWhere로 지우고 맨 앞에 insert한 뒤 7개로 자르고 다시 쓴다. predicate는 공유 closure 0x362bf0의 정수 동등 비교다.
- AddNewPreset(0x63756c)은 프리셋 목록 길이가 16 이상이면 추가하지 않는다. 추가/삭제(DeletePreset 0x63710c의 removeAt)는 SaveAllPresets로 “saved_count”와 “p”+index key를 다시 쓴다.
- 앱 전역 `_persistDialogColorPreferences`(0x5cd1d8)는 ExportColorStorage 결과의 “presets”/“recent”를 `_saveColorPreferences`로 넘긴다. 시작 시 `_restoreDialogColorPreferences`가 비동기로 RestoreColorStorage를 호출한다. 최종 저장 backend 형식은 이번에 확인하지 않았다.

## 검증 범위

[감사](AOT-MODIFY-COLOR-GLOW-APPLY-AUDIT-2026-10-27.json)는 위 함수의 선택 명령 234개를 같은 ELF 디코딩과 대조한 결과다. FormatException stub tag도 별도로 확인했다. 비공개 검사 스크립트는 cache `checks/validate_modify_color_glow.py`에 두었다. annotation이 `ArrayStore r[0]`으로 표시한 0x6355f0/0x4e4120/0x4e3910/0x638438/0x4e342c는 실제 명령이 offset0x17 접근이었다. 해당 필드 의미는 원시 명령을 따랐다.

남은 것: 색 휠/삼각형 위젯의 터치→HSV 좌표식, 프리셋 UI 배치, 저장 backend, 비정상 입력(음수/거대 반경·NaN), 실제 화면 색/글로우 pixel은 미확인이다. 색·글로우 apply의 정상 정적 경로는 여기서 닫았으므로 같은 함수를 다시 미수행으로 세지 않는다. 실제 앱 결과로 승격하지 않는다.
