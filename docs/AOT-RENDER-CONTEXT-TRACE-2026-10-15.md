# AOT 렌더 문맥: 좌표·DPR·굵기 공급 — 2026-10-15

- 기존 DrawInformation / AnimationObject / frame_fill_region / sequence_action_activity 캐시를 제한적으로 연결했다.
- 아래는 정적 코드 경로의 해석이다. 실제 화면·영상의 실행 경로 확정이나 동일 픽셀 렌더 검증이 아니다.
- 기존 자료·시험·설치·전체 추출은 반복하지 않았다.

## 1. 좌표는 사용 가능 사각형의 백분율이다

DrawInformation.TranslateToScreenX(0x347554), TranslateToScreenY(0x3474e8)의 실제 계산:

- x_screen = OffsetX + UsableCanvasWidth × x / 100
- y_screen = OffsetY + UsableCanvasHeight × y / 100

- 원본 `_screenOffsets`(0x41fd88)와 보간 `_interpolatedScreenOffsets`(0x795e50)에도 같은 계산이 인라인된다(0x41fe74–0x41fec8 / 0x795f1c–0x795f6c).
- 입력 점 표현만 다르고, 백분율 → Path 좌표 변환식은 같다.
- 이 함수들에 좌표 0–100 clamp나 직접 DPR 나눗셈은 없다. 화면 밖·음수 좌표를 임의로 중앙 이동하거나 삭제하면 안 된다.
- DrawInformation 자체의 계산과 외부 Canvas 변환은 별도다.
  - 편집 줌·이동이 이 기본식의 필드에 직접 포함돼 있다고 해석하지 않는다.
  - 최종 device pixel에는 호출자가 적용한 Canvas scale/translate/clip도 관여하며, 모든 호출자 연결은 미완이다.

## 2. DrawInformation의 비율 맞춤·여백

- 생성자(0x4d0558)는 Size.width/height가 양수이면 이를 사용하고, 아니면 1을 사용한다.
- SetDrawableValues(0x4d0994)는 height/width ratio가 0이면 0.5625(9/16)로 바꾼다(0x4d09b8–0x4d09c4).
- 아래 식은 정상적인 유한 W/H ≥ 1, 양수 ratio R 조건에 한정한다.

```
P  = ResolveStrokeOverflowPadding()의 반환값
Aw = clamp(W−2P, 1, W),  Ah = clamp(H−2P, 1, H)
Ah/Aw > R 이면  Uw = Aw, Uh = Aw×R
그렇지 않으면    Uh = Ah, Uw = Ah/R
OffsetX = (W−Uw)/2,  OffsetY = (H−Uh)/2
```

- 필드 UsableCanvasWidth/Height와 OffsetX/Y에 위 결과가 저장된다(0x4d0b14–0x4d0d60).
- 따라서 "그림을 항상 캔버스 전체 폭·높이에 직접 맞춘다"는 모델은 여백과 비율 맞춤을 놓친다.
- W/H가 분수 1 미만이거나 R이 음수/NaN인 극단 입력의 전체 예외 정책은 검증하지 않았다.
- CurrentDrawableArea는 Offset와 Usable 크기의 Rect이고, CurrentCanvasArea는 별도 `_resolveAspectFittedArea`(0x4d08f8) 경로다.
- 화면 전체 영역 / 출력 사각형 / 사용 가능 영역을 하나로 합치지 않는다. 후기 RecordPicture의 intersect/clipRect 경로도 있다.

## 3. DPR은 override → 현재 view → 1

- AnimationObject.ResolveDevicePixelRatio(0x4153b8)
  - static 0xd34 override가 있으면 반환한다.
  - 없으면 PlatformDispatcher.implicitView의 view configuration에서 DPR을 얻는다.
  - implicitView도 없으면 1이다.
  - getter 자체는 override를 새로 저장하거나 입력값을 clamp하지 않는다.

ExportVideoAsyncTask._withExportRenderDevicePixelRatio(0x633254):
1. 기존 override를 저장.
2. override = 1 설정(0x633280).
3. 전달된 동기 closure 실행.
4. 기존 override 복원(0x6332a4). 예외 경로도 복원 후 rethrow(0x6332c0).

확인한 호출:
- ExportToVideoOptimized의 0x6299f8은 DrawInformation 반환 closure 0x633da8을 감싼다.
- `_recordExportPicture`(0x62dbac)의 0x62dc70은 Picture 기록 closure 0x62dc88을 감싼다. 그 closure는 Canvas 생성 / 배경 drawRect / 대상 객체의 동적 Draw / endRecording을 수행한다.
- 이후 async 경로의 `_recordExportPicture` → toImage → toByteData 연결도 있다(0x62e0fc/0x62e140/0x62e160).

**확인 범위**
- 이 wrapper의 동기 범위는 DPR 1이다.
- 모든 export backend, 전체 async 기간, 이전 사용자 영상이 전부 같은 범위라는 확정은 아니다.
- 일반 화면 DPR과 같게 맞춰야 한다는 가정도 사용하지 않는다.
- 글로우 R/W/sigma와 여백 계산에 DPR이 관여하므로, 경로 차이가 최종 픽셀에 영향을 줄 수 있다.

## 4. 여백의 기본 8과 실제 Paint 굵기는 별도

- ResolveStrokeOverflowPadding(0x43f580)의 생략 인수 baseStrokeWidth 기본값은 8이다.
  - current sequence가 있으면 S = thickness/100, 없으면 1.
  - q = baseStrokeWidth × max(S, 0) / DPR
- StabilizeCurvedStrokeWidth(0x43f6a0)는 round(1.14×q×DPR)/DPR를 계산한다.
- StabilizeCircleStrokeWidth(0x43f730)는 전달받은 배율 f에 대해 round(f×q×DPR)/DPR를 계산한다. 여백 함수는 1.24를 전달한다.
- 여백 함수는 원·곡선 보정 결과를 비교해 최댓값의 절반 + 1, 최소 1을 사용한다(0x43f63c–0x43f688).
- 같은 곡선 보정 호출이 2번 보이며, 임의로 다른 세 번째 종류가 있다고 해석하지 않는다.

주의:
- 이 8은 **여백 helper의 기본 인수**이며, 모든 렌더 Paint.strokeWidth를 8로 확정하는 근거가 아니다.
- 일부 레이아웃은 실제 OBJECT_PAINT strokeWidth를 읽어 helper에 명시적으로 전달한다(예: item_frame_view_layout 0x43f370/0x43f3a8/0x43f3b0).
- DrawInformation.SetDrawableValues는 생략 인수 경로다.
- SetPaintThickness(0x4152bc)는 전달 Paint의 현재 strokeWidth를 기본값 B로 읽어 B×max(S×ThicknessScale, 0)/DPR로 바꾸고, 이전 B를 반환한다(0x415318/0x415374/0x415398/0x41539c).
- 앞서 glow도 같은 실제 B를 참조하는 경로를 확인했다.

**2026-10-15 정정**
- 초기 strokeWidth 0이라는 해석은 Blutter Float32 로드를 double 요약 주석으로 오독한 것이었다.
- 실제 ldr s0와 PP 원시 32비트에 따라 OBJECT_PAINT = 8, PREVIEW_OBJECT_PAINT ≈ 2.2다.
- 공급·변경·복원·primitive 보정은 AOT-PAINT-DISPATCH-TRACE-2026-10-15.md에서 연결했다.
- 따라서 "초기 0 → 비영 값 미해결"과, 그 공급처 찾기를 요구하던 옛 다음 행동은 폐기한다.
- 여백 helper 8과 실제 Paint 8의 공급 근거를 구분해야 한다는 지침은 유지한다.

## 5. 글로우 경로의 현재 연결

읽은 DrawGlowEffect의 순서:
1. shader `TryDrawGlowWithShader` 성공이면 반환한다.
2. 실패하면 BuildGlowRasterPlanForObject → drawable area 검사 → TryDrawCachedGlowRaster.
3. 여기서도 완료되지 않으면 `_isGlowOutsideDrawableArea` → ResolveGlowMaskFilter → DrawGlowGeometry로 진행한다.
- 주소: 0x421298 / 0x42131c / 0x421398 / 0x4213bc / 0x4213f4 / 0x421450.

한계:
- 이는 선택 경로의 존재와 호출 순서다.
- shader 프로그램 load 완료 시점, 캐시 hit/miss의 전체 조건과 픽셀 동등성, 사용자 영상의 실제 backend는 미확인이다.
- 프로그램/Style/점수/cull로 Try가 달라지고 화면 밖 true도 있다는 이전 정정을 유지한다.
- "항상 shader" 또는 "shader가 실패하면 항상 MaskFilter"로 단순화하지 않는다.

## 검증·체크포인트

**검증**
- 새 명령 표본 14개를 캐시 ELF와 Capstone으로 대조해 모두 통과했다.
- 이전의 새 14개 Path/보간 검사를 재실행한 것은 아니다.
- audit: AOT-RENDER-CONTEXT-AUDIT-2026-10-15.json
- 문서 작업이라 unit/probe 시험 반복 없음.
- 일시적 exec-server 접속 실패 후 재연결했고, 캐시·새 검증은 성공했다. 사용자 ADB 실패나 캐시 손실로 판정하지 않았다.

**다음 정확한 작업 (작성 당시)**
- 실제 Paint B의 plan/caller/primitive 변경·복원과 출력 dispatch를 먼저 닫는다.
- 필요하면 Frame.DrawBaseObject와 보간 객체 `_restorePaint`를 추적하고, Frame/Picture/native 백엔드 경계를 확인한다.
- 그다음 shader load lifecycle / raster hit 조건 / hole 캐시 키.
- 현재 좌표·여백식과 B의 미해결을 구분한다.
- 휴대폰 추가 설치·명령·Play 설정·시작 시험 요청 없음.

**인수인계 관련**
- HANDOFF.md가 과거 체크포인트를 반복 수록해 길어져, 이번에 현행 입구를 압축했다. 삭제 전 전체는 docs/history/HANDOFF-2026-10-15-before-render-context.md에 보존한다.
- 고정 예측 변경·File-2 최적화는 보류, 원본·역컴파일·assembly 공개 금지 유지.
- 학습·AI 연결은 2026-10-16 사용자 결정으로 개인용 범위에서 진행한다(AGENTS.md "학습 단계 결정", [AI-PIPELINE-PLAN](AI-PIPELINE-PLAN-2026-10-16.md)).

**근거 캐시**
- **근거 캐시(현재 환경):** `/root/sfa-cache/extracted`의 `blutter_out/asm/sfa/original_port/sequences/{draw_information,animation_object,frame_fill_region}.dart`, `blutter_out/asm/sfa/original_port/activities/sequence_action_activity.dart`, `evidence/libapp.so`, `python/`(Capstone·pyelftools). Setup script가 복구한다.
- 현재 환경에 없는 것: 작성 당시 새 표본 검사(`validate_render_context.py`, `render-context-validation.json`). 작성 당시 이전 환경 경로는 [원문](history/before-current-facts-2026-10-16/AOT-RENDER-CONTEXT-TRACE-2026-10-15.md)에 보존했다.
- 직접 작성한 해석·집계·인수인계만 공개한다.

**후속:** 현재 다음은 AOT-PAINT-DISPATCH-TRACE-2026-10-15.md의 shader/raster 선택과 optimized/encoder dispatch다. 기존 기본 폭 재추적 요청은 완료로 대체한다.
