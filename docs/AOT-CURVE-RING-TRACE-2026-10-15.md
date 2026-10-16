# 곡선 글로우 분할·곡률·링 node 선택 — 2026-10-15

- 기존 AOT/PP/원본 ELF 캐시만 읽은 정적 추적이다.
- 설치·페어링·휴대폰 시작 시험·기존 영상 분석을 반복하지 않았다.
- 직접 작성한 수학적 해석·집계만 공개한다.
- 원래 Dart/셰이더 코드 또는 assembly를 공개하지 않는다.

## 1. curve 입력과 길이·회전각

- GlowShader.drawCurve(0x425948)는 start/control/end를 _curvePieces(0x426020)에 전달한다(0x425af8–0x425b08). 여기서 전달 double은 sigma다.
- 폭 W가 sigma로 잘못 들어가는 것으로 읽지 않도록 drawCurve 진입 d0→fp−0x48, d1→fp−0x50, _shaderFor 호출의 반대 재배치까지 연결했다.
- 기존 uniform10=W/2,11=sigma 정정을 유지한다.

P0=start,P1=control,P2=end, v0=P1−P0,v1=P2−P1,delta=v1−v0로 둔다. 곡선은 B(t)=(1−t)²P0+2(1−t)tP1+t²P2다.

- theta=atan2(cross(v0,v1),dot(v0,v1)). 둘 중 제곱길이가 1e−10 이하이면 theta0.
- L16=Σ(i=1..16)|B(i/16)−B((i−1)/16)|. 16개의 chord 길이 합이며 정확한 곡선 길이 적분이 아니다.
- theta는 라디안. 이 숫자를 UI 각도나 degree로 직접 쓰지 않는다.

근거: theta0/atan2 경로 0x426078–0x426134,16개 샘플 0x426164–0x426230. 곡선 점을 이 16개로 그대로 shader에 보내는 것이 아니라 분할 개수 판단을 위한 길이 추정이다.

## 2. 가장 큰 곡률과 1–48개 제한

_sharpestCurvature(0x426a90)는 v(t)=v0+t delta의 크기가 최소인 지점을 찾는다. |delta|²<1e−10이면 t*=0, 아니면 t*=clamp(−dot(v0,delta)/|delta|²,0,1). s=|v(t*)|라 두면:

- s<1e−6이면 kmax=1e6을 반환.
- 나머지 kmax=|cross(v0,v1)|/(2s³).

이는 quadratic B의 미분 B'=2v(t),B''=2delta와 연결한 곡률의 절댓값이다. 퇴화할 때 반환하는 1e6은 무한대 대신 쓰는 이 경로의 유한 값이며 모든 퇴화 곡선의 정확한 곡률이라고 부르지 않는다.

_curvePieces는 다음 수를 계산한다:

- n1=ceil(L16×sqrt(kmax/(0.16×max(sigma,0.001))))
- n2=ceil(|theta|/0.6)
- n=max(1,min(48,max(n1,n2)))

- 근거 0x426250–0x426328. 더 날카롭거나 길고 sigma가 작으면 n1이 커질 수 있다.
- 이 식을 **0.16sigma의 최종 픽셀 오차 보장**으로 해석하지 않는다.
- 길이 추정·샘플 배치·곡률 근사·48 상한이 있고 실행 오차를 측정하지 않았다.

- 48개 상한은 n을 48로 제한하는 방식이다.
- 먼저 무제한 조각을 만든 뒤 뒤쪽을 버리지 않는다.
- loop는 i=1..n을 방문하고 각 끝점의 x/y와 곡률의 triple을 저장한다(0x4263f8–0x426790). 기존 shader의 최대 48 body·Dart triples→uniform21+4i 저장과 연결된다.
- SFA의 객체/점을 삭제하는 최적화 기능이 아니다.

## 3. 등간격 t와 방향 회전 기반 t를 혼합

- f=i/n이다.
- |theta|≤0.01이면 t_i=f를 사용한다.
- |theta|>0.01이면 _turnedParameter(v0,v1,f,theta)를 호출하고 t_i=(f+tturn)/2다(0x42640c–0x426450).

_turnedParameter(0x426884):

- q=rotate(v0,f×theta)/|v0|.
- d=cross(delta,q).
- |d|<1e−8이면 tturn=f.
- 나머지 tturn=clamp(−cross(v0,q)/d,0,1).

- 이는 변화하는 접선이 q와 평행해지는 방정식의 해를 사용하는 수학적 해석이다.
- 구간 전체를 정확한 등호길이로 나누는 알고리즘이 아니다.
- 균일 parameter와 방향 회전 기반 parameter를 반씩 혼합한다.
- 작은 각도·작은 분모의 분기까지 구분한다.

- 각 piece는 끝점 B(t_i)를 저장한다.
- 곡률은 tmid=(t_(i−1)+t_i)/2에서 계산한다.
- D=2[(1−tmid)v0+tmid v1], A=2delta라 두면 |D|≤1e−5일 때 c_i=0, 나머지 c_i=cross(D,A)/|D|³다(0x4264d8–0x426574). 여기서는 **부호 있는 곡률**을 보내며, n을 구할 때의 kmax 절댓값과 다르다.
- 기존 shader의 Lpiece²c/12·moment 보정이 이 c_i를 받는다.

## 4. 퇴화 곡선·선의 호출 경계

- 읽은 drawCurve는 endpoint tangent가 아주 작으면 다른 endpoint를 향하는 chord로 대체해 방향을 구한다(0x4259b4–0x425a3c).
- 대체한 양 끝 방향 중 길이가 1e−5 미만인 것이 있으면 start→start인 drawLine으로 넘어간다(0x425a90–0x425abc).
- 원본 모든 곡선이 단순 직선으로 바뀐다는 뜻은 아니다.

- drawLine(0x42753c)은 길이<1e−5이면 _drawRing을 직접 호출한다(0x4275c4–0x4275ec). radius0, node8, 원래 W/sigma를 전달한다.
- 따라서 거의 점인 stroke도 ring kind로 처리할 수 있다.
- 이것은 일반 drawRing의 node 선택을 거친 호출이 아니므로 ‘모든 ring은 같은 node 선택’을 적용하면 틀린다.

- 돌아오는 collinear 곡선처럼 endpoint가 같더라도 control이 다르면 tangent가 남을 수 있다.
- 이런 곡선을 전부 radius0 경로로 일반화하지 않는다.
- interior cusp/퇴화 근사에 대한 픽셀 정확도는 미검증이다.

## 5. 일반 ring의 반폭과 node 선택

AO.TryDrawGlowWithShader의 circle branch는 두 점의 중간점을 중심, 두 점 거리/2를 radius로 만든다(0x425690–0x4256fc). drawRing에 d0=radius,d1=sigma,d2=W를 전달한다(0x42578c/0x425798/0x42579c).

drawRing(0x427378)의 shuffle을 실제 mov로 따라가면, 내부에서 z=min(W,8sigma)/sigma를 계산하고:

| 조건 | 적분 node 수 |
|---|---:|
| z≤1 | 2 |
| 1<z≤3 | 4 |
| z>3 | 8 |

- 0x4273b0–0x427404. **min(W,8sigma)는 node 선택에 쓰인다.** _drawRing으로는 원래 W가 d3로 전달되고, _shaderFor에 그대로 재배치되어 uniform10=W/2를 설정한다(0x4273ec–0x427470). 따라서 읽은 일반 ring 경로의 shader 반폭을 min(W,8sigma)/2로 줄이는 식은 틀린다.
- 이전 GROUP-SHADER 보고서의 ‘내부 반폭 전체 미확인’은 이 호출 범위에서 해결했다.
- UI 원시 두께부터 W까지의 이전 환산과 shader 내부 sigma 최소 0.001은 여전히 별도 단계다.

반경은 uniform6,node수는 19에 공급된다. _drawRing은 중심의 직경 2radius 사각형을 만들고 _fill을 호출한다(0x4274c8–0x427520). radius0의 퇴화 stroke는 앞 절처럼 node8 고정이다.

## 6. 화면 밖 검사와 실제 drawRect 여백은 다른 식

- GlowShader._fill(0x425e9c)은 전달된 bounds를 W/2+3sigma+1만큼 inflate하고 shader/blendMode Paint로 drawRect한다(0x425ee0–0x425f40).
- 이것은 shader body/ring의 4sigma 조기 종료 조건이나 AO.TryDrawGlowWithShader의 화면 밖 검사용 W/2+4sigma+1과 다른 단계다.

- 같은 숫자 R을 쓰는 raster plan의 여백과도 합치지 않는다.
- culling bounds, 실제 그리는 rectangle, shader coverage 지원영역, raster 생성 bounds를 분리해야 한다.
- 이 차이에서 최종 tail 픽셀 오차나 잘림량까지 수치 확정하지 않는다.
- 실제 엔진의 샘플/AA 결과는 미계측이다.

## 7. 신규 검증·예시·다음

새 54명령 ELF PT_LOAD/Capstone 대조 모두 통과. 검사기는 private-trace/validate_curve_ring.py. 감사 집계는 AOT-CURVE-RING-AUDIT-2026-10-15.json. 이전 주제의 명령 대조나 셰이더 자산 byte 비교를 반복하지 않았다.

다음은 해석한 정적 식의 산출 예시다. 앱 시험이나 픽셀 오차 시험이 아니다.

| (P0,P1,P2) | sigma | L16 | 계산 요구수 | 실제 n |
|---|---:|---:|---:|---:|
| ((0,0),(50,0),(100,0)) | 2 | 100 | 0 | 1 |
| ((0,0),(50,50),(100,0)) | 2 | 약 114.7333 | 29 | 29 |
| 같은 곡선 | 10 | 약 114.7333 | 13 | 13 |
| ((0,0),(100,0),(0,0)) | 2 | 100 | 176777 | 48 |

- 4개 예시에서 triple 개수≤48/끝 parameter1을 확인했다.
- 내부 cusp 예시의 큰 요구수와 48상한은 정확도 한계 검토가 필요한 조건이며 불량픽셀을 실측했다는 뜻은 아니다.
- 일반 ring sigma2일 때 W2→2node,W6→4node,W6.01→8node,W100→8node이고 반폭은 각각 1,3,3.005,50이다.

정적 연결 완료: quadratic 길이·곡률·각도→분할수상한→parameter혼합→끝점/부호곡률 triple→기존 uniform/body수학; circle/퇴화 stroke→ring node/원래반폭→_fill bounds. 완전 렌더러·GPU pixel 동등성 검증을 완료한 결과는 아니다.

- **다음:** fill path/holed-path와 draw-plan·glow 이미지 캐시의 key·수정 무효화 경계를 확인한다.
- 객체 색/좌표/두께/구멍 변경 후 어떤 캐시를 재사용·재생성하는지, edit와 export 호출자를 구분한다.
- 휴대폰 작업을 추가하지 않고 기존 정적 캐시를 먼저 사용한다.

사용자환경정정:2026-10-15 08:49 KST,휴대폰 Wi-Fi는학교망에연결가능하나제약있음(정확한제약미확인). PC i7-8700/GTX1050Ti/RAM16GB확보. 현재무선 ADB/USB연결가능여부·PC OS는미확인. 지금사용자추가작업없음. 라이선스응답 4차단해결로세지않는다.

- **근거 캐시(현재 환경):** `/root/sfa-cache/extracted`의 `blutter_out/asm/sfa/original_port/sequences/{glow_shader,animation_object}.dart`, `blutter_out/pp.txt`, `evidence/libapp.so`, `python/`(Capstone·pyelftools). Setup script가 복구한다.
- 현재 환경에 없는 것: 작성 당시 신규 검사(`validate_curve_ring.py`, `curve-ring-validation.json`, `check_curve_formulas.py`, `curve-formula-examples.json`)와 문서 worktree. 작성 당시 이전 환경 경로는 [원문](history/before-current-facts-2026-10-16/AOT-CURVE-RING-TRACE-2026-10-15.md)에 보존했다.
- 작성 당시 이전 worktree와 보호 원본은 변경하지 않았다.
