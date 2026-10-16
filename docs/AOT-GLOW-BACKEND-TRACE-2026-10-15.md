# AOT 글로우 셰이더·래스터·MaskFilter 선택 추적 — 2026-10-15

- 기존 AOT/PP/ELF 캐시를 재사용한 정적 분석이다.
- 실제 UI/픽셀 검증은 아니다.
- 신규 명령어 20곳을 ELF PT_LOAD/Capstone과 대조했다.
- 휴대폰 설치·페어링·기존 시작 시험은 반복하지 않았다.

## 셰이더 준비와 선택 순서

- main의 초기화 경로에서 DataAccess.bootstrap을 기다린 다음 GlowShader.load(0x3205c4)를 호출하고 그 Future를 기다린다(0x3205d0). load(0x33c5c4)는 프로그램 static 0xdf0가 이미 있으면 즉시 반환한다.
- 없으면 shaders/glow.frag의 FragmentProgram.fromAsset을 기다리고 결과를 static에 저장한다(0x33c604–0x33c61c). 예외 처리 경로는 static을 null로 만든 뒤 반환한다(0x33c624–0x33c638). 따라서 셰이더 로드 실패가 반드시 앱 전체 초기화 실패라는 뜻은 아니다.
- 실행에서 성공했는지는 미계측이다.

원본 AnimationObject.DrawGlowEffect(0x420dcc)의 확인한 순서:

| 단계 | 선택/반환 |
|---|---|
| 셰이더 | TryDrawGlowWithShader(0x421298). true이면 반환한다. 화면 밖 생략도 true가 될 수 있다. |
| 래스터 계획 | BuildGlowRasterPlanForObject(0x42131c). 계획이 있으면 destination bounds로 화면 밖을 검사한다. |
| 이미지 캐시 | TryDrawCachedGlowRaster(0x421398). 성공하면 반환한다. miss에서도 이미지를 새로 만들 수 있다. |
| 직접 블러 | 계획이 없을 때 별도 화면 밖 검사. 앞 경로가 처리하지 못하면 ResolveGlowMaskFilter(0x4213f4)와 DrawGlowGeometry(0x421450). |

TryDrawGlowWithShader(0x425458)는 프로그램 null 또는 전달된 style gate가 false이면 false를 반환한다(0x425498–0x4254a8). 원본 호출자는 Paint style code == 1 여부를 전달한다(0x421254–0x421278). TypeId 1/2/3과 필요한 점 개수 검사를 통과해야 대응 line/circle/curve 경로로 간다. sigma=sqrt(R²+(0.29/DPR)²)와 화면 밖 true의 뜻은 이전 AOT-DRAW-GLOW 보고서를 유지한다.

보간 DrawGlowEffect에도 shader→plan→cached raster→직접 fallback 호출이 있고, 입력 Paint 복원은 AOT-PAINT-DISPATCH 보고서를 따른다. 전체 그룹 합성·최종 영상 backend가 이 원본 객체 분기와 동일하다고 일반화하지 않는다.

## 래스터 축소와 좌표 단위

- GlowRasterPlan의 line/curve/circle builder가 _resolveRasterScale(0x4249fc)를 사용한다.
- R은 DrawGlowEffect에서 계산해 전달한 블러 입력이며, 크기는 글로우 여백을 포함한 bounds의 Canvas 좌표 크기다.
- 별도 물리픽셀/DPR 단위를 임의로 덧붙이지 않는다.

면적 A=width×height, 긴 변 L=max(width,height)일 때 위에서부터 처음 성립하는 배율 q:

| 조건 | q |
|---|---:|
| A≥1,600,000 또는 L≥1,800 | 0.35 |
| A≥700,000 또는 L≥1,200 | 0.5 |
| A≥250,000 또는 L≥700 또는 R≥18 | 0.67 |
| 나머지 | 1 |

- line builder(0x424f0c)에서 여백은 W/2+3×max(R,0.001)+2이다.
- 이를 셰이더의 W/2+4×sigma+1과 동일한 식으로 합치지 않는다.
- 래스터 너비/높이는 각각 ceil(boundsDimension×q)를 최소 1로 만든 뒤 4의 배수로 올린다.
- destination의 오른쪽/아래 끝은 left+imageWidth/q, top+imageHeight/q로 다시 구성된다(0x425018–0x425114).

- 점 좌표는 (screenPoint−boundsOrigin)×q, stroke 폭은 W×q, 블러 입력은 R×q로 래스터 공간에 옮긴다.
- line(0x425118–0x425334), curve(0x424274–0x424548), circle(0x424c64–0x424e0c)의 공급/저장을 연결했다.
- _rasterize는 이 plan 폭/블러/geometry로 Picture를 기록하고 toImageSync(imageWidth,imageHeight)를 호출한다(0x423564). 배율 축소는 원본 SFA 좌표나 객체를 영구 변경하는 기능이 아니다.

- TryDrawCachedGlowRaster(0x4221d4)는 전체 이미지 Rect를 plan destination Rect로 drawImageRect한다(0x422514). q<0.999이면 FilterQuality.low, 아니면 none이다.
- PP enum 이름을 직접 대조했다.
- 최종 pixel sampling/AA까지 실행 검증한 것은 아니다.

## 이미지 캐시 키와 예산

- _buildKey(0x4246b8)는 종류, 양자화한 두 double 값, 정수 이미지 크기 두 값, geometry double 목록을 구분자로 연결한다.
- double 양자화와 목록 값은 round(value×2)이다.
- line 호출에서 두 double은 W×q와 R×q, 목록은 래스터 local 좌표다(0x425274–0x42528c). 키에는 line의 ARGB나 화면 절대 원점이 직접 들어가지 않는다.
- curve/circle도 같은 key helper를 호출하지만 모든 geometry 목록 원소의 의미를 이번에 풀어 쓴 것은 아니다.

- _rasterize는 공용 Paint를 흰색으로 설정한다(0x422f64–0x422f70). 이미지 재사용 후 plan ARGB를 ColorFilter의 BlendMode.srcIn으로 입히고, 이미지 Paint blendMode는 입력 Paint에서 상속한다.
- 따라서 색을 cache key에서 제외하는 것이 곧 색 무시라는 뜻은 아니다.
- PP srcIn/low/none/BlurStyle.normal 이름을 확인했다.

GlowRasterImageCache.resolve(0x422998):
- 이미지 너비×높이 > 2,000,000이면 캐시 조회보다 먼저 null. 여기서 단위는 이미지 픽셀 수이며 bytes가 아니다.
- hit는 key를 remove 후 재삽입하여 최근 사용 항목을 뒤로 보내고 기존 Image를 반환한다.
- miss는 _rasterize를 호출하고 null이면 실패. 성공한 entry를 삽입하고 픽셀 수를 총량에 더한 뒤 _evictIfNeeded를 실행한다.
- entry는 Image와 width×height를 저장한다(0x423580–0x42358c).

- _evictIfNeeded(0x422af4)는 entry 수>128 또는 합계 픽셀 수>8,000,000이면 앞쪽 key를 제거하고 Image.dispose 후 반복한다.
- 이는 읽은 LinkedHashMap 순서와 hit 재삽입을 연결한 LRU 방식이다.
- 실제 GPU 메모리 8MB 제한으로 해석하면 틀린다.

## 직접 fallback와 MaskFilter 캐시

ResolveGlowMaskFilter(0x421c48)는 유한한 정상 입력에 대해:
- k=clamp(round(max(input,0.001)×20),2,40000)
- BlurStyle.normal, sigma=k/20

- 따라서 필터 sigma의 최소값은 0.1, 최대값은 2000이고, 내부 값은 0.05 간격이다.
- 표시된 GlowRadius를 그대로 사용하는 공식과 구분한다.
- 래스터 생성에서는 축소한 R×q가 이 helper에 들어가며, 직접 fallback는 해당 호출의 블러 입력을 사용한다.
- 셰이더 sigma와 이 양자화 sigma는 같다고 보장할 수 없다.

- 정수 k를 key로 filter를 조회해 재사용한다.
- 새 key를 만들 때 기존 개수가 96 이상이면 앞 key 하나를 제거한 뒤 삽입한다(0x421dd8–0x421e18). hit에서는 remove/reinsert가 없어 이미지 캐시와 같은 LRU라고 부르면 안 된다.
- 여기서는 삽입 순서 기반이다.
- NaN/무한대의 일반 렌더 규칙은 확정하지 않았다.

## 검증과 남은 범위

- AOT-GLOW-BACKEND-AUDIT-2026-10-15.json의 새 20명령 표본 모두 ELF/Capstone 대조 통과. PP enum과 실제 scalar 명령·인수 이동을 함께 읽었다.
- 기존 단위/probe/시작 시험 반복 없음.
- 명령 대조는 전체 함수 의미나 셰이더·래스터 픽셀 일치 검증이 아니다.

- 현재 정적 사실은 '셰이더 준비/선택 + 원본 객체 fallback 순서 + 래스터 배율/단위 + 이미지/MaskFilter 캐시 제한'이다.
- 화면 밖 생략은 객체 삭제가 아니다.
- 정밀 복제 시 셰이더와 축소 래스터·양자화 블러를 하나의 이상적 Gaussian으로 합치면 차이를 놓칠 수 있다.

- 다음은 export optimized/native encoder dispatch를 추적한다.
- 그룹 합성의 별도 선택, 실제 사용 영상의 backend, shader asset 내부 함수/엔진 pixel 결과는 미확인 상태를 유지한다.
- 실기기 지속 렌더 계측은 기존 라이선스 응답 4 차단 상태이며 추가 사용자 작업/검사 변경은 없다.

캐시: e23c9fd610d3/private/blutter_out/asm/sfa/{main.dart,original_port/sequences/{glow_shader,animation_object,interpolated_animation_object}.dart},pp.txt,원본 ELF. 새 검증기 25b8ca176661/private-trace/{validate_glow_backend.py,glow-backend-validation.json}. 공개는 직접 작성 해석과 집계만.
