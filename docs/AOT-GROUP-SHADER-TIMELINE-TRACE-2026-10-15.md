# 그룹 글로우·셰이더 수학·내보내기 타임라인 연결 — 2026-10-15

- 기존 AOT/ELF/PP, 셰이더 자산, APK 캐시만 사용한 정적 분석이다.
- 설치·페어링·휴대폰 시작 시험·00–05/기존 영상 분석은 반복하지 않았다.
- 직접 작성한 해석과 집계만 공개한다.
- 앱 실행이나 GPU 픽셀 일치 검증을 완료한 결과가 아니다.

## 1. 그룹 글로우는 객체별 누적 그리기다

- FrameDrawPlan.drawUnit(0x414ee8)은 unit.field_b가 null인 글로우 전용 unit이면 unit.field_7의 그룹과 plan의 Paint를 Frame._DrawCompositeObjectGlow(0x420c30)에 전달하고 반환한다(0x414f28–0x414f54).
- BuildDrawPlan의 그룹 unit 공급은 0x42bc34–0x42bc54다.
- 일반 객체 unit은 채우기와 본체 경로로 이어진다.

- _DrawCompositeObjectGlow는 그룹의 iterator를 만들고 반복하면서 각 AnimationObject의 색을 전달 Paint에 설정한 뒤 DrawGlowEffect를 호출한다(0x420d8c/0x420da0/0x420da8).
- **읽은 그룹 helper에는 그룹 전체를 이미지로 합치거나 saveLayer·단일 블러·그룹 전용 셰이더를 선택하는 단계가 없다.** Composite라는 이름을 그룹 실루엣의 합집합 블러로 해석하면 틀린다.

따라서 기존 원본 객체 규칙을 이 호출자까지 연결할 수 있다.

| 단위 | 실제 선택 |
|---|---|
| 그룹 | 입력 그룹 순서대로 객체별 DrawGlowEffect |
| 각 객체 | shader → raster plan/이미지 캐시 → 직접 MaskFilter fallback |
| 셰이더 성공/화면 밖 처리 | 해당 객체에서 반환. 다음 객체는 별도로 처리 |
| 그룹 순서 | 기존 보고서의 비연속 A(g),B(h),C(g) → A,C,B 유지 |

- 그룹에서 한 객체가 셰이더로 처리됐다고 다른 객체의 backend까지 정해지는 것이 아니다.
- blendMode는 전달 Paint의 상속 규칙을 유지하며 plus로 고정하지 않는다.
- 여러 객체의 커버리지 합산과 겹침은 개별 draw의 합성 결과이고, 그룹 union 마스크를 한 번 블러한 결과와 같다고 보장할 수 없다.

- InterpolatedFrame에는 별도 _drawCompositeObjectGlow가 있다.
- 이것도 iterator 반복에서 InterpolatedAnimationObject.DrawGlowEffect를 호출하고 다음 항목으로 돌아간다(0x7968fc/0x796904). 해당 DrawGlowEffect는 같은 shader(0x796f68), raster plan(0x797114), cached raster(0x7971d4), MaskFilter(0x7972a0) helper에 연결된다.
- 원본과 보간 helper가 같은 함수라는 뜻은 아니며, 각각 읽은 객체별 선택 구조의 연결이다.

## 2. 자산의 실제 형식과 uniform 연결

- 기존 private/glow.frag는 GLSL 원본 텍스트 파일이 아니라 105,992 bytes의 컴파일된 바이너리 자산이다.
- IPLR 식별자와 SPIR-V magic, GLSL ES300/ES100 및 자동 생성 SkSL 텍스트 본문을 확인했다.
- 기존 base.apk의 해당 자산과 bytes 대조가 일치했다.
- 새 APK 추출·셰이더 컴파일·도구 설치는 하지 않았다.

SHA256: `12260c19f930c779a853e8f919b1b6ffd823da7bcd1f75163ff3910d998aabad`.

- 수학 해석은 읽기 쉬운 SkSL 본문을 사용했다.
- ES300/ES100에도 48개 piece 배열과 최종 커버리지 clamp가 있다.
- 세 backend의 전체 산술 동등성, 실제 기기가 고른 backend, mediump/Float32/GPU 오차는 이번에 검증하지 않았다.
- 원본/자동 생성 셰이더 코드는 공개하지 않는다.

| Dart float index | 자산 값 | 연결 의미 |
|---|---|---|
| 0–3 | uColor | 기존 RGB 사전알파·글로우 알파 공급 |
| 4–5 | uA.xy | stroke 시작점 또는 ring 중심 |
| 6 | uA.z | ring 반경 |
| 10 | uB.z | 반폭 h=W/2 |
| 11 | uB.w | 보정 sigma. 자산 진입에서 최소 0.001 |
| 12 | uKind | >0.5이면 ring, 나머지 stroke |
| 13–16 | uCaps | 양 끝 inward 방향 |
| 17 | uCounts.x | cap strips 선택 |
| 18 | uCounts.y | stroke piece 수 |
| 19 | uCounts.z | ring 적분 node 수 |
| 21+4i부터 | uPieces[i] | 끝점 xy·곡률 z. 이 본문은 w를 읽지 않음 |

- 10/11/12의 기존 정정은 유지한다.
- Curve 공급자는 triples 목록 길이/3을 index18에 넣고, i번째 triple을 index21+4i의 x/y/z로 Float32 저장한다(0x425c5c–0x425c7c,0x425cbc–0x425d08 이후). 단순 직선의 piece 수는 1(0x427780–0x427788). 자산은 최대 48개를 방문한다.
- 실제 곡선 분할점/곡률을 만드는 _curvePieces의 전체 규칙은 다음 범위다.

## 3. 셰이더 커버리지의 수학적 해석

- 아래는 자산 수식을 직접 작성한 수학 표기로 요약한 것이다.
- 유한한 정상 입력 기준이며 모든 계수·부동소수 연산 순서를 보존한 복제 구현은 아니다.
- 기존 sigma=sqrt(R²+(0.29/DPR)²)는 Dart 공급 단계, 여기서는 그 sigma를 받은 이후다.

### 공통 Gaussian band

k=1/(sqrt(2)×sigma), Gaussian 밀도 g(x)=exp(−x²/(2sigma²))/(sqrt(2π)×sigma).

- 구간 커버리지 B(l,h)=0.5×[E(hk)−E(lk)]. E는 erf의 유한 다항식 근사이고 정확한 특수함수 호출이 아니다.
- |x|에 대한 t=1/(1+0.32759109|x|), 5차 다항식과 exp(−x²), 부호 복원으로 계산한다.
- 실제 자산은 Float32 반올림 계수를 사용한다.

### 직선/곡선 몸통

- 각 piece의 시작 a, 끝 b, 길이 L, 단위 접선 e를 두고 u=(p−a)·e, v=cross(e,p−a)+L²c/12다.
- c는 piece 곡률이다.
- L<약 1e−5이면 0. u가[−4sigma,L+4sigma] 밖이거나 |v|>h+4sigma면 0.

- c=0: Cbody=B(−u,L−u)×B(−h−v,h−v).
- c≠0: lo=−h(단 c<0이면 max(−h,1/c)), hi=h(단 c>0이면 min(h,1/c)). A=B(lo−v,hi−v), M=vA+sigma²[g(lo−v)−g(hi−v)]. Cbody=B(−u,L−u)×max(A−cM,0).

곡선은 최단거리 하나에 Gaussian을 씌우는 방식이 아니다. piece별 방향·곡률·양 옆 band·곡률 보정 항이 쓰인다.

### 반원 cap

- 끝점마다 inward 방향으로 u/v를 계산하여 반원 cap 커버리지를 더한다.
- strips≥0.5이면 근사 사각형 band를 사용한다.
- strips<1.5일 때 길이≈0.84882635h, 반높이≈0.92527539h의 한 사각형이다.
- 그 이상이면 h/strips 폭으로 나누고 반원 면적 원시함수의 차분으로 strip 반높이를 계산하여 최대 8개의 band 곱을 합한다.

- strips<0.5이면 x=−h sin(phi) 치환을 이용한 반원 적분으로 넘어간다.
- integrand는 h cos(phi)×g(u+h sin(phi))×B(−h cos(phi)−v,h cos(phi)−v). 4sigma 범위로 적분 구간을 제한하고 횡방향 경계 각도에서 최대 두 구간으로 나누어, 각 구간을 8-node Gauss-Legendre로 적분한다.

읽은 line/curve Dart 공급자는 z=h/sigma에 대해 z≤1이면 strips1, 1<z≤4이면 min(ceil(3z),8), z>4이면 0을 전달한다(직선 0x4276d4–0x427778,곡선 0x425bb0–0x425c54). 같은 radius에서도 두께/sigma에 따라 cap 계산 방식이 바뀐다.

### ring

p에서 중심까지 거리 r, ring 중심선 반경 a일 때 rho 적분 범위는 lo=max(a−h,0,r−4sigma), hi=min(a+h,r+4sigma). hi≤lo면 0이다.

- Cring은 이 범위에서 (rho/sigma²)×exp[−(r−rho)²/(2sigma²)]×I0e(r rho/sigma²)를 적분한 값이다.
- I0e(x)는 exp(−x)I0(x)의 다항식 근사이며 x=3.75를 경계로 식이 갈린다.
- 이것은 Gaussian을 원환에 적분한 구조라는 수학적 해석이다.
- radius와 거리의 차이만으로 평가하는 단순 1차원 Gaussian과 구분한다.

- nodes 값에 따라 2/4/8-node Gauss-Legendre를 사용한다.
- 공급값이 항상 8이라고 고정하지 않는다.
- drawRing은 더 내부적인 반폭/노드 조정 경로를 갖고 있으므로 UI W를 모든 ring 진입의 h에 무조건 그대로 대입하지 않는다.

### 한 객체의 최종 출력

- stroke는 최대 48개 몸통과 양 끝 cap 커버리지를 더한 뒤, ring은 위 적분값을 사용한다.
- 둘 다 마지막에 C를[0,1]로 clamp하여 공급 uColor×C를 반환한다.
- 따라서 몸통끼리 겹치는 값은 한 객체 내부에서 제한된다.
- **이 clamp는 그룹 전체의 객체 간 합성을 clamp한다는 뜻이 아니다.**

셰이더·축소 raster·양자화 MaskFilter가 동일한 pixel을 만든다는 결론은 내리지 않는다. 기존 raster q/여백/캐시/MaskFilter sigma 규칙은 별도 보고서를 유지한다.

## 4. 내보내기 FPS와 endpoint 산식

기호: F=원본 프레임 수, P=max(재생 FPS,1), T=요청 트위닝 FPS. 저장 FPS 순서는 계속 (트위닝,재생)이다.

- VideoSettingsDialog 재생 seekbar는 field_13(0x6346ec), tween seekbar는 field_1f(0x6348d0)에 저장한다.
- onClick은 재생값을 최소 1로, tween값을 재생값 이상으로 만든 뒤 VideoSettingsReady에 전달한다(0x628700–0x62875c).
- VideoSettingsReady는 task.field_1b에 재생, field_23에 tween을 저장한다(0x628838/0x628840).
- 내보내기는 이 task의 값으로 PlaybackEnumeration을 생성한다(0x6295c0–0x629610).
- 일반 factory의 tweeningEnabled 기본값은 true다.

| 항목 | PlaybackEnumeration 규칙 |
|---|---|
| 실제 tween 활성 | tweeningEnabled && T>P |
| 출력 FPS Q | 활성일 때 T, 아니면 P |
| 보간 단계 K | 활성일 때 max(round(Q/P),1), 아니면 1 |
| 출력 개수 N | ceil(max(F,0)×Q/P) |
| 원본 시작 a(j) | min(floor(max(j,0)×P/Q),F−1) |
| 다음 프레임 b(j) | min(a+1,F−1) |
| 해당 구간 첫 출력 j0 | ceil(a×Q/P) |
| 보간 step m | 비활성 또는 a=b 또는 j=j0면 0. 나머지는 floor(((max(j,0)×P) mod Q)×K/Q) |
| 보간 t | m/K. export는 m≤0 또는 K≤0이면 0 |

factory:0x519bac–0x519ce4, round helper:0x519d1c–0x519dd4, outputAt:0x62bb8c–0x62bc9c. F≤0의 outputAt은 상수 빈출력 반환 경로다. 모든 비정상 정수/오버플로/NaN 동작을 확정한 식이 아니다.

- 최적화 export는 outputAt 이름을 직접 호출하지 않고 같은 산술을 루프에 인라인한다(0x629ca0–0x629d8c).
- loop j는 0부터 N−1(0x629c58–0x629c5c).
- m/K는 0x629dd4–0x629ddc, t>0이고 서로 다른 frame이면 FrameInterpolationPlan.apply(0x62a150).
- t0 또는 같은 frame이면 원본을 사용한다(0x62a034–0x62a074).

- **마지막 프레임 뒤의 F→새 endpoint는 생성하지 않는다.** 마지막 구간은 a=b=F−1이므로 마지막 원본을 반복한다.
- (F−1)K+1이라는 프레임 수 공식은 이 경로에 맞지 않는다.
- 일반 duration의 산술상 표본 구간은 N/Q이며, 비정수 비율에서 F/P보다 최대 한 출력 간격 미만 길어질 수 있다.
- 실제 muxer가 보고한 영상 duration을 새로 측정한 것은 아니다.

예시는 새 앱 시험이 아니라 정적 산식의 계산이다.

| F | (트위닝,재생) | Q/N | 0-based 원본 index: t 순서 |
|---:|---|---|---|
| 3 | (24,12) | 24/6 | 0:0, 0:.5, 1:0, 1:.5, 2:0, 2:0 |
| 3 | (25,12) | 25/7 | 0:0, 0:0, 0:.5, 1:0, 1:.5, 2:0, 2:0 |
| 1 | (60,12) | 60/5 | 전부 0:0 |

- factory 자체에 (12,24)를 넣으면 tween 비활성, Q24/N3(F3)이다.
- VideoSettingsDialog onClick은 이런 요청의 tween을 24로 올려 보낸다.
- UI 정규화와 factory의 독립 입력 처리를 구분한다.

- N은 기존 raw 공간 예측 W×H×4×N에 쓰이고, Q는 context.field_2b에 저장되어 raw/PNG 양쪽 인코더에 전달된다(0x629630/0x629658,0x633b84,PNG0x633c1c).
- 이전 Android 인코더 보고서의 presentation timestamp j×1e9/max(Q,1) ns와 연결된다.
- 정수배가 아닌 경우 정확한 연속시간 t가 아니라 K 단계로 양자화한 t를 쓴다.

## 5. 검증과 다음 범위

- 새 명령 45곳 ELF PT_LOAD/Capstone 대조 통과. 기존 shader asset와 APK 내 한 자산의 bytes 대조 통과. 해석한 타임라인 산식 96개 입력 조합에서 개수·인덱스 범위·step 범위·마지막 프레임 유지의 수학적 일관성을 확인했다.
- 이 산식 검사는 실제 앱의 96개 시험이 아니다.
- 감사 집계: AOT-GROUP-SHADER-TIMELINE-AUDIT-2026-10-15.json.

- 문서만 변경했다.
- 기존 unit/probe/영상/폰 시험을 반복하지 않았다.
- 라이선스 응답 4로 지속 렌더 계측이 막힌 상태를 유지하고 우회·검사 변경은 없다.

- 다음 우선순위: **GlowShader._curvePieces의 분할 오차·곡률·48개 한계와 drawRing/퇴화 stroke의 내부 반폭·노드 선택을 연결**한다.
- 이번 수학 요약을 완전한 pixel 복제식으로 승격하지 않는다.
- 실제 backend·shader/raster/MaskFilter pixel 차이·기기 codec/색은 runtime 미확인으로 남긴다.

- **근거 캐시(현재 환경):** `/root/sfa-cache/extracted`의 `blutter_out/asm/sfa/{main.dart,original_port/sequences/{frame,interpolated_frame,interpolated_animation_object,glow_shader,playback_timeline}.dart,original_port/dialogs/video_settings_dialog.dart,original_port/activities/sequence_action_activity.dart}`, `evidence/libapp.so`, 셰이더 자산 `evidence/glow.frag`, `python/`(Capstone·pyelftools). Setup script가 복구한다.
- 현재 환경에 없는 것: 작성 당시 private 검사·본문 읽기 파일과 문서 checkout. 작성 당시 이전 환경 경로는 [원문](history/before-current-facts-2026-10-16/AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md)에 보존했다.
- 작성 당시 이전 dirty worktree는 보존했다.


## 6. 추가 명령 대조·타임라인 예시

- 원격 체크포인트 5042a69를 보존하고 같은 캐시에서 별도로 선택한 50명령을 ELF PT_LOAD/Capstone에 대조했다.
- 모두 통과했다.
- 이전 45명령과 중복되는 주소가 있어 95개의 서로 다른 신규 명령으로 합산하지 않는다.
- 자산 byte/hash도 일치하며, 설치/추출/영상/실물시험은 반복하지 않았다.
- 추가 집계: AOT-GROUP-SHADER-TIMELINE-SUPPLEMENT-AUDIT-2026-10-15.json.

- BuildDrawPlan은 그룹 glow unit 뒤에 구성원별 fill/본체 unit을 넣는다(0x42bc44/0x42bddc).
- drawUnit은 해당 fill 뒤 본체를 그린다(0x414f78/0x41509c).
- 보간 호출자도 그룹 helper를 먼저 호출하고 구성원을 순회한다(0x793260/0x793534).
- 객체별 backend 선택과 그룹 전체 coverage clamp를 혼동하지 않는다는 본문의 결론을 유지한다.

- 다음은 본문 산식을 추가 6개 입력에 대입한 결과다.
- 실행 영상의 프레임 수나 duration을 재측정한 것이 아니다.
- 양수 비율의 0.5 반올림은 실제 LibcRound 호출(0x519d74)에 연결된다.

| F | (트위닝,재생) | Q | K | N | 산출 결과 |
|---:|---|---:|---:|---:|---|
| 2 | (60,12) | 60 | 5 | 10 | 앞 구간 t=0,.2,.4,.6,.8; 마지막 원본 5회 유지 |
| 2 | (30,12) | 30 | 3 | 5 | 앞 구간 t=0,1/3,2/3; 마지막 원본 2회 유지 |
| 4 | (30,12) | 30 | 3 | 10 | 원본 시작 index0,3,5,8; 각 시작 step0 |
| 2 | (24,24) | 24 | 1 | 2 | 보간 비활성, 원본당 1장 |
| 1 | (60,12) | 60 | 5 | 5 | 같은 원본 5회 |
| 0 | (60,12) | 60 | 5 | 0 | 출력 없음 |

- 작성 당시 추가 private 검사(`validate_group_shader_timeline.py`, `group-shader-timeline-validation.json`, `shader-timeline-structure.json`, `window.py`)와 문서 반영용 clean worktree는 현재 환경에 없다. 현재 주소창 도구는 `/root/sfa-cache/extracted`의 `checks/window.py`다.
- 본문의 다음 우선순위와 runtime 미확인 제한은 그대로 유지한다.
