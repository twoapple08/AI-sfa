# AOT Paint 굵기 정정·변경·복원·호출 경로 — 2026-10-15

- 기존 AOT/PP/ELF 캐시만 재사용했다.
- 실제 UI·픽셀 실행 검증이 아니라, 읽은 경로의 정적 분석이다.
- 새 명령 표본 14개와 PP Float32 해석을 검증했다.
- 기존 시험·추출·도구 설치·휴대폰 작업은 반복하지 않았다.

## 1. 중요 정정: 초기 strokeWidth는 0이 아니다

- 앞선 AOT-RENDER-CONTEXT 보고서에서 OBJECT/PREVIEW Paint의 초기 strokeWidth를 0으로 읽고 "공급 미해결"로 기록한 것은 잘못이었다.
- Blutter의 요약 주석 `d0=0.000000`만 읽고, 바로 아래 명령·리터럴의 실제 폭을 연결하지 못했다.

원본 명령과 PP 리터럴:

| Paint | scalar load/store | PP 원시 32비트 | IEEE754 Float32 값 |
|---|---|---|---|
| OBJECT_PAINT | 0x42d6c8 ldr s0 → 0x42d6cc str s0 | pp+0x11d28: 0x41000000 | 8.0 |
| PREVIEW_OBJECT_PAINT | 0x42d778 ldr s0 → 0x42d77c str s0 | pp+0x11d30: 0x400ccccd | 2.200000047683716 |

- scalar s0는 Float32다. d0 요약을 Double 수치로 오독하면 안 된다.
- 일반 B = 8, preview B ≈ 2.2가 실제 초기화 식이다.
- PP 원시 메타데이터 → struct Float32 해석과 ELF의 load/store 명령 폭을 연결했다. runtime Paint 값을 직접 로그로 읽은 것은 아니다.
- padding helper 기본 인수 8과 일반 Paint 초기 8은 숫자가 같지만 다른 공급 근거다.
  - 앞선 "여백 8을 실제 B로 임의 대입하지 말자"는 방법 지침은 유지한다.
  - "초기 0 / 비영 값 공급 경로 미해결"은 이 체크포인트로 정정한다.
- 원본 역컴파일·메타데이터를 고치지 않고 직접 작성한 보고서만 정정했다.

## 2. FrameDrawPlan의 선택과 실제 호출자 범위

- BuildDrawPlan(0x42b910)은 isPreview=false면 OBJECT_PAINT, true면 PREVIEW_OBJECT_PAINT를 plan.field_f에 보관하고 drawUnit에서 사용한다.
- 기존 Frame 자료의 값을 실행 중 바꿔 버리는 영구 UI 설정과는 별도다.

확인한 공급자:
- EditorFrameCache._FrameRecord(0x4291b4)의 0x42926c는 named isPreview 없이 Frame.BuildDrawPlan을 호출한다. 기본 false이므로 일반 B 8이다.
- FrameDrawPlanCache.planFor(0x51743c)의 0x5174cc도 기본 false. ViewSequence.RecordPicture(0x516dc0)는 0x5172b4에서 이 캐시를 얻어 Frame.Draw에 넘긴다.
- renderSequenceActionFramePicture(0x4cf91c)는 usePreviewPaint가 생략되면 false(0x4cf9f4)이고, 그 값을 Frame.Draw의 isPreview로 전달한다(0x4d0064–0x4d0098). true인 호출은 preview B ≈ 2.2 선택이 가능하다.
- Frame.Draw(0x791c9c)는 plan이 없으면 옵션으로 BuildDrawPlan, 있으면 그 plan을 사용한 뒤 drawUnit을 순회한다.

해석:
- "편집 화면은 전부 preview 2.2 / 출력은 전부 8"이라는 결론은 틀릴 수 있다. isPreview의 구체 호출값·캐시 상태를 따라야 한다.
- 보간 객체의 `_drawLayerObjects` / `_drawCompositeObjectGlow`에는 OBJECT_PAINT를 직접 읽는 경로도 있다(0x793374/0x7967f8).
- 모든 preview 옵션의 보간 투과 여부와 사용자 영상 dispatch를 이번에 실물 검증한 것은 아니다.

## 3. 일반 객체: 폭과 cap/join을 변경 후 정상 반환에서 복원

- AnimationObject.DrawBaseObject(0x4150b8)는 SetPaintThickness(0x4152bc)를 호출해, 입력 Paint B에 현재 sequence 비율 S, 객체 ThicknessScale T, DPR D를 적용한다.

  w = B × max(S×T, 0) / D

- SetPaintThickness는 이전 B를 double로 반환한다.
- 새 폭이 양수가 아니면 원래 B를 복원하고 return한다(0x415154–0x41516c).
- 양수면 기존 StrokeCap/Join을 저장하고 임시 값 1을 설정한 뒤 AO 종류의 DrawObject로 동적 dispatch한다. 끝에서 B/cap/join을 복원한다(0x415248–0x41528c).
- 이는 객체 간 배율이 순차 누적되지 않도록 하는 정상 경로다. 이 함수에 전체 예외 finally가 있다고 주장하지 않는다.
- 가상 dispatch의 GDT 슬롯 번호만으로 다른 클래스의 같은 슬롯 함수 이름을 붙이지 않는다.

## 4. primitive는 기본 w에 화면 반올림 보정을 더한다

- Line.DrawObject(0x791a44)와 Curve.DrawObject(0x791660)는 StabilizeCurvedStrokeWidth(0x43f6a0)를 호출한다. 함수 이름의 "Curved"만 보고 곡선 전용이라 판정하면 안 된다.
- Circle.DrawObject(0x7912f8)는 StabilizeCircleStrokeWidth(0x43f730)에 배율 1.14를 전달한다.
- 이 읽은 보정 경로에서 실제 stroke 폭은 `round(1.14×w×D)/D`다.
- 각 primitive는 그 폭을 임시로 쓰고 이전 폭을 다시 저장하는 경로가 있다.
- filled/stroke/type별 전체 분기와 모든 pixel AA 동작은 별도 확인 범위다.

주의:
- 이전 여백 계산의 circle 배율 1.24는 여백 helper용이다. 실제 Circle.DrawObject의 1.14와 구분한다.
- 일반 B 8도 최종 stroke가 항상 8이라는 뜻은 아니다.
  - 예: 정상 양수 S=T=D=1이고 이 보정 분기를 쓰면, 기본 w 8 → round 9.12 = 9, preview는 w 약 2.2 → round 2.508… = 3.
  - 이는 코드식의 계산 예시이며 새 실물 측정이 아니다.
- 글로우 W는 입력 Paint B와 GlowThickness로 계산하는 별도 경로다. "최종 기본 선 반올림 폭 × GlowThickness/10"으로 글로우 W를 대체하면 안 된다.

## 5. 보간 객체의 변경·복원

- InterpolatedAnimationObject.DrawBaseObject(0x7935a4)
  - 원래 Float32 폭 비트·색을 저장하고, 보간 ThicknessScale에 대해 같은 B×max(S×T,0)/D를 계산한다.
  - 양수인 경우 보간 Color·새 폭을 Paint에 넣고 DrawGeometry를 호출한다.
  - 정상 끝에서 폭의 원래 Float32 비트를 그대로 복원하고 색도 복원한다(0x7937e0/0x7937ec).
- DrawGeometry의 원/곡선/선 보정 호출을 확인했다(0x793af4/0x793e04/0x7940ac). 원은 1.14를 전달한다. branch별 임시 폭 저장·복원도 있다.
- raw Float32 비트 저장과 fcvt로 계산한 double 저장을 같은 값 표현으로 취급하지 않는다.
- 보간 DrawGlowEffect
  - 입력 Paint의 상태를 임시로 바꾸며, shader/cull/raster/fallback의 여러 종료 경로에서 `_restorePaint`(0x797bd8)를 호출한다.
  - 이 helper는 mask 관련 바이트 슬롯을 0으로 만들고 width/color/style/cap/join/blend 및 보존된 object/filter 참조를 복원하는 경로다.
  - 임의 기존 maskFilter와 모든 예외까지 원상 복구를 보장한다는 주장은 하지 않는다.
  - 원본 AO의 공용 GLOW_PAINT 사용과 보간 AO의 입력 Paint 임시 변경을 같은 구현으로 합치지 않는다.

## 6. 현재 출력 dispatch 연결과 한계

직접 읽은 연결:
- Frame.Draw → FrameDrawPlan.drawUnit → 그룹 Glow 또는 FR / DrawBaseObject.
- EditorFrameCache._record(0x414ba4)는 NativePictureRecorder/Canvas를 만들고 각 unit.drawUnit(0x414d64)을 기록한다. 이후 `_drawWithRecordings`로 재사용하는 경로가 있다.
- ViewSequence.RecordPicture는 clipRect / 배경 / planFor / Draw / endRecording으로 연결된다.
- export `_recordExportPicture`의 동기 closure는 DPR 1 범위에서 NativePictureRecorder / Canvas / 배경 / 동적 Draw / endRecording. 이후 toImage / toByteData로 연결된다.

한계:
- 이들은 Dart 측 Picture 기록 경로다.
- Android 쪽 영상 인코더와의 연결, optimized/native 대체 경로의 최종 선택, 사용자 영상이 어느 경로를 썼는지는 아직 미확인이다.
- NativeCanvas FFI라는 이름만으로 앱의 Java 네이티브 renderer와 같다고 판정하면 안 된다.

## 검증·다음 작업

**검증**
- 신규 명령 표본 14개를 ELF PT_LOAD/Capstone과 대조해 통과했고, 초기 폭 PP 리터럴 2개의 IEEE754 Float32 값을 검증했다.
- audit: AOT-PAINT-DISPATCH-AUDIT-2026-10-15.json
- 기존 다른 14개·원본·unit/probe 시험을 재실행하지 않았다.
- 명령·메타데이터 검증은 전체 함수 의미나 실물 픽셀 확정이 아니다.

**다음 작업 (작성 당시)**
- shader load lifecycle → 프로그램 준비/Style gate → raster cache 생성/hit/단위 조건 → MaskFilter fallback의 구체 선택을 연결한다.
- 그다음 export optimized/native encoder dispatch를 필요한 부분만 연결한다.
- 요청된 전체 기능 분석은 계속 진행 중이며, 실기기 렌더 계측은 기존 라이선스 차단 상태다.
- 휴대폰 추가 명령·설치·Play 설정 요청 없음.

**근거 캐시**
- **근거 캐시(현재 환경):** `/root/sfa-cache/extracted`의 `blutter_out/asm/sfa/original_port/sequences/{animation_object,interpolated_animation_object,line,circle,curve}.dart`, `blutter_out/asm/sfa/original_port/editor/editor_frame_cache.dart`, `blutter_out/pp.txt`, `evidence/libapp.so`, `python/`(Capstone·pyelftools). Setup script가 복구한다.
- 현재 환경에 없는 것: 작성 당시 새 검사(`validate_paint.py`, `paint-validation.json`). 작성 당시 이전 환경 경로는 [원문](history/before-current-facts-2026-10-16/AOT-PAINT-DISPATCH-TRACE-2026-10-15.md)에 보존했다.
- 공개는 직접 작성한 해석·집계만.
- 앞선 Float32 오독은 AGENTS와 기존 보고서에 정정했다.
