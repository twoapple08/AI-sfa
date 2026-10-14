# AOT 렌더 문맥: 좌표·DPR·굵기 공급 — 2026-10-15

기존 DrawInformation/AnimationObject/frame_fill_region/sequence_action_activity 캐시를 제한적으로 연결했다. 아래는 정적 코드 경로의 해석이다. 실제 화면/영상의 실행 경로 확정·동일 픽셀 렌더 검증이 아니다. 기존자료/시험/설치/전체추출은 반복하지 않았다.

## 1. 좌표는 사용 가능 사각형의 백분율이다

DrawInformation.TranslateToScreenX(0x347554),TranslateToScreenY(0x3474e8)의 실제 계산:

- x_screen = OffsetX + UsableCanvasWidth × x / 100
- y_screen = OffsetY + UsableCanvasHeight × y / 100

원본 _screenOffsets(0x41fd88)와 보간 _interpolatedScreenOffsets(0x795e50)에도 같은 계산이 인라인된다(0x41fe74–0x41fec8/0x795f1c–0x795f6c). 입력 점 표현만 다르고 백분율→Path 좌표 변환식은 같다. 이 함수들에 좌표0–100 clamp나 직접 DPR 나눗셈은 없다. 화면밖/음수좌표를 임의 중앙 이동하거나 삭제하면 안 된다.

DrawInformation 자체의 계산과 외부 Canvas 변환은 별도다. 편집 줌/이동이 이 기본식의 필드에 직접 포함되어 있다고 해석하지 않는다. 최종 device pixel에는 호출자가 적용한 Canvas scale/translate/clip도 관여하며 모든 호출자 연결은 미완이다.

## 2. DrawInformation의 비율 맞춤·여백

생성자(0x4d0558)는 Size.width/height가 양수이면 이를 사용하고 아니면1을 사용한다. SetDrawableValues(0x4d0994)는 height/width ratio가0이면0.5625(9/16)로 바꾼다(0x4d09b8–0x4d09c4). 이하 식은 정상적인 유한 W/H≥1,양수ratio R 조건에 한정한다.

P = ResolveStrokeOverflowPadding()의 반환값.
Aw = clamp(W−2P,1,W), Ah = clamp(H−2P,1,H).
Ah/Aw > R이면 Uw=Aw,Uh=Aw×R; 그렇지 않으면 Uh=Ah,Uw=Ah/R.
OffsetX=(W−Uw)/2,OffsetY=(H−Uh)/2.

필드 UsableCanvasWidth/Height와OffsetX/Y에 위 결과가 저장된다(0x4d0b14–0x4d0d60). 따라서 '그림을 항상캔버스전체폭높이에직접맞춘다'는모델은여백과비율맞춤을놓친다. W/H가분수1미만이거나R이음수/NaN인극단입력의전체예외정책은검증하지않았다.

CurrentDrawableArea는Offset와Usable크기의Rect이며 CurrentCanvasArea는별도 _resolveAspectFittedArea(0x4d08f8) 경로다. 화면전체영역/출력사각형/사용가능영역을하나로합치지않는다. 후기 RecordPicture의 intersect/clipRect 경로도있다.

## 3. DPR은 override→현재view→1

AnimationObject.ResolveDevicePixelRatio(0x4153b8)는static0xd34 override가있으면반환하고,없으면PlatformDispatcher.implicitView의view configuration에서DPR을얻는다. implicitView도없으면1이다. getter 자체는 override를새로저장하거나입력값을clamp하지않는다.

ExportVideoAsyncTask._withExportRenderDevicePixelRatio(0x633254):
1. 기존override를저장.
2. override=1 설정(0x633280).
3. 전달된동기closure 실행.
4. 기존override 복원(0x6332a4),예외경로도복원후rethrow(0x6332c0).

확인한호출:
- ExportToVideoOptimized의0x6299f8은 DrawInformation 반환closure0x633da8을감싼다.
- _recordExportPicture(0x62dbac)의0x62dc70은 Picture 기록closure0x62dc88을감싼다. 그closure는Canvas생성/배경drawRect/대상객체의동적Draw/endRecording을수행한다.
- 이후async경로의_recordExportPicture→toImage→toByteData 연결도있다(0x62e0fc/0x62e140/0x62e160).

**확인범위:** 이wrapper의동기범위는DPR1. 모든exportbackend/전체async기간/이전사용자영상이전부같은범위라는확정은아니다. 일반화면DPR과같게맞춰야한다는가정도사용하지않는다. 글로우R/W/sigma와여백계산에DPR이관여하므로경로차이가최종픽셀에영향줄수있다.

## 4. 여백의 기본8과 실제 Paint 굵기는 별도

ResolveStrokeOverflowPadding(0x43f580)의생략인수 baseStrokeWidth 기본값은8이다. current sequence가있으면S=thickness/100,없으면1; q=baseStrokeWidth×max(S,0)/DPR.

StabilizeCurvedStrokeWidth(0x43f6a0)는 round(1.14×q×DPR)/DPR를계산한다. StabilizeCircleStrokeWidth(0x43f730)는전달받은배율f에대해 round(f×q×DPR)/DPR를계산하며여백함수는1.24를전달한다. 여백함수는원/곡선보정결과를비교해최댓값의절반+1,최소1을사용한다(0x43f63c–0x43f688). 동일곡선보정호출이2번보이며임의로다른세번째종류가있다고해석하지않는다.

이8은 **여백helper의기본인수**이며모든렌더Paint.strokeWidth를8로확정하는근거가아니다. 일부레이아웃은실제OBJECT_PAINT strokeWidth를읽어helper에명시적으로전달한다(예:item_frame_view_layout0x43f370/0x43f3a8/0x43f3b0). DrawInformation.SetDrawableValues는생략인수경로다.

SetPaintThickness(0x4152bc)는전달Paint의현재strokeWidth를기본값B로읽고 B×max(S×ThicknessScale,0)/DPR로바꾸며이전B를반환한다(0x415318/0x415374/0x415398/0x41539c). 앞서glow도같은실제B를참조하는경로를확인했다.

**2026-10-15 정정:** 초기strokeWidth0이라는해석은Blutter Float32로드를double요약주석으로오독한것이었다. 실제ldr s0와PP원시32비트에따라OBJECT_PAINT=8,PREVIEW_OBJECT_PAINT≈2.2다. 공급/변경·복원/primitive보정은AOT-PAINT-DISPATCH-TRACE-2026-10-15.md에서연결했다. 따라서'초기0→비영값미해결'과아래해당찾기를요구하는옛다음행동은폐기한다. 여백helper8과실제Paint8의공급근거를구분해야한다는지침은유지한다.

## 5. 글로우 경로의 현재 연결

읽은 DrawGlowEffect는 shader TryDrawGlowWithShader 성공이면반환한다. 실패하면BuildGlowRasterPlanForObject→drawable area검사→TryDrawCachedGlowRaster. 여기서도완료되지않으면_isGlowOutsideDrawableArea→ResolveGlowMaskFilter→DrawGlowGeometry로진행한다(0x421298/0x42131c/0x421398/0x4213bc/0x4213f4/0x421450).

이는선택경로의존재/호출순서다. shader프로그램load완료시점,캐시hit/miss의전체조건과픽셀동등성,사용자영상실제backend는미확인이다. 프로그램/Style/점수/cull로Try가달라지고화면밖true도있다는이전정정을유지한다. '항상shader' 또는'shader가실패하면항상MaskFilter'로단순화하지않는다.

## 검증·체크포인트

새명령표본14개를캐시ELF와Capstone으로대조해모두통과했다. 이전새14개Path/보간검사를재실행한것이아니다. audit는AOT-RENDER-CONTEXT-AUDIT-2026-10-15.json. 문서작업으로unit/probe시험반복없음. 일시exec-server접속실패후재연결과캐시/새검증성공;사용자ADB실패또는캐시손실로판정하지않았다.

다음정확한작업: 실제Paint B의plan/caller/primitive 변경·복원과출력dispatch를먼저닫는다. 필요하면Frame.DrawBaseObject 및보간객체_restorePaint를추적하고Frame/Picture/native백엔드경계를확인한다. 다음shader load lifecycle/raster hit 조건·hole캐시키. 현재좌표/여백식과B의미해결을구분한다. 휴대폰추가설치/명령/Play설정/시작시험요청없음.

HANDOFF.md가많은과거체크포인트를반복수록하여길어져이번에현행입구를압축했다. 삭제전전체는docs/history/HANDOFF-2026-10-15-before-render-context.md에보존한다. 고정예측/File-2최적화/학습/AI연결보류·원본/역컴파일/assembly공개금지유지.

캐시e23c9fd610d3/private/blutter_out/asm/sfa/original_port/sequences/{draw_information,animation_object,frame_fill_region}.dart와activities/sequence_action_activity.dart,ELF/venv. 새표본검사25b8ca176661/private-trace/{validate_render_context.py,render-context-validation.json}. 직접작성해석/집계/인수인계만공개한다.

현재다음은AOT-PAINT-DISPATCH-TRACE-2026-10-15.md의shader/raster선택과optimized/encoderdispatch다. 기존기본폭재추적요청은완료로대체한다.
