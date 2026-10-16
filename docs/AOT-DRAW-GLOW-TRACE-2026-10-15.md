# AOT 추가 추적: 객체 공급·비연속 그룹·글로우 인수 — 2026-10-15

- 기존 Blutter/ELF/PP/IDA 이름 캐시만 재사용했다.
- 이 보고서는 정적 경로 해석이다.
- 원본 앱의 영상 출력 경로 확정·픽셀 재현·편집 기능 실행 완료가 아니다.
- Android 테스트에서는 Gadget/Flutter 모듈 로드는 성공했고 라이선스 오류로 지속 실행이 차단됐다.
- 그 사실은 ANDROID-INSTRUMENTATION-BUILD-2026-10-15.md에 별도로 기록했다.
- 설치/페어링/기존 00–05 시험/전체 JADX/Blutter 추출을 반복하지 않았다.

## 1. GetAnimationObjects는 DB 지연 로더가 아니다

- Frame.GetAnimationObjects(0x34eb9c)는 field_1f의 목록을 반환하며 null이면 새 빈 목록을 만들어 저장한다.
- DB 호출이나 정렬은 없다.
- 이름만으로 프레임 조회 시 DB가 자동으로 채워진다고 가정하면 안 된다.

- DataAccess.PopulateFrameAnimationObjects(0x34ec1c)는 목록이 **null 또는 비었을 때** GetAnimationObjectsForFrame을 호출하고 결과를 field_1f에 저장한다(0x34ec90/0x34ec98).
- 이미 비어 있지 않으면 DB를 재조회하지 않고 CreateAnimationObjectMap만 수행한다(0x34ec78).
- 따라서 이미 편집 중인 목록의 순서를 매번 DB 순서로 강제 교정하는 함수가 아니다.
- BulkLoadFrames(0x5280c8)에서도 같은 null/빈 목록 검사와 DB 목록 공급 경로가 보인다.

- GetAnimationObjectsForFrame(0x34eff0)은 measureSync closure(0x34f0d4)에서 기존에 확인한 SQL을 실행하고, 결과를 map→GrowableList.of로 구체화한다(0x34f244/0x34f26c/0x34f27c).
- 해당 SQL의 두 분기는 모두 ORDER BY COALESCE(a.draw_order,a._id) ASC,a._id ASC다.
- 여기서 null DrawOrder는 ID fallback이며 비양수값을 모두 fallback시키는 다른 comparator와 구분한다.

**확인 범위:** 이 DB 공급 경로의 순서는 정렬되어 있다. 모든 in-memory 편집/보간/캐시 공급자의 최종 순서가 동일하다는 보장은 아직 없다.

## 2. 비연속 연결 그룹은 처음 등장한 위치에 묶인다

- Frame._BuildLayerObjectGroups(0x42c2c8)는 레이어에 속한 AO를 입력 순서로 순회한다.
- AO ID→연결 그룹 ID 매핑이 있으면 그룹 키, 없으면 AO ID를 사용한다.
- 삽입 순서를 갖는 Map.fromLiteral/LinkedHashMap 경로에서 키를 처음 만났을 때 목록을 만들고 이후 같은 키에는 AO를 추가한다(0x42c304/0x42c3a0/0x42c46c/0x42c490). 마지막에 map.values를 List.of로 반환한다(0x42c4e4–0x42c4fc). 별도 sort는 없다.

같은 레이어에서 A와 C가 같은 연결 그룹이고 B가 독립이면 다음과 같다.

| 입력 AO 순서 | 그룹 목록 | object unit 방문 순서 |
|---|---|---|
| A, B, C | [A,C], [B] | A, C, B |

- 이는 코드 경로를 설명하는 예시이며 새로운 실물 시험 결과가 아니다.
- 그룹 키는 먼저 등장한 AO 위치에 따라 순서가 정해지고 그룹 내부는 입력 순서를 유지한다.
- 즉 전체 AO DrawOrder 정렬을 그대로 선형 draw 호출 순서로 사용하는 모델은 이 경우 틀릴 수 있다.

- 기존 BuildDrawPlan의 그룹 glow-only unit→각 AO의 FR/base unit 배치와 연결하면, FR take가 가장 먼저 만나는 outerSegments 참조 AO도 이 그룹 방문 순서에 영향을 받는다.
- 모든 FR이 독립적인 최상단/최하단 패스로 그려진다고 가정하지 않는다.
- 연결 그룹 ID를 만드는 union/대표키의 전체 정책 및 레이어 밖 참조는 이번 범위에서 재해석하지 않았다.

## 3. 글로우 두께·반경의 확인된 계산

DrawGlowEffect(0x420dcc)의 shader 호출까지 실제 레지스터/스택 전달을 연결했다. 아래는 유한한 정상 입력의 해당 경로이며 전체 화면/영상 dispatch 또는 UI 좌표 변환의 완성식은 아니다.

- S = 현재 sequence thickness/100, current sequence가 null이면 1 (0x4210d8–0x421108).
- B = 전달된 입력 Paint의 strokeWidth.
- D = ResolveDevicePixelRatio의 반환값.
- T = max(S × ThicknessScale,0).
- W = (B × T / D) × max(GlowThickness/10,0) (0x421114–0x421194).
- R = max(GlowRadius × S / D,0.001) (0x4211bc–0x421200).
- W 또는 T가 양수가 아니면 그리기를 종료한다. 앞쪽에는 GlowRadius/GlowAlpha 양수 검사도 있다.

- TryDrawGlowWithShader(0x425458)는 입력 R에 대해 `sigma = sqrt(R² + (0.29/D)²)` 를 계산한다(0x4254b4–0x4254d0).
- 화면 밖 판정용 확장 폭은 `W/2 + 4×sigma + 1`이다(0x4254dc–0x4254f4).
- 화면 밖이면 true를 반환할 수 있으므로 **true를 반드시 실제 픽셀이 그려졌다는 증거로 세면 안 된다.**

- 프로그램 미준비 또는 전달된 Paint style 조건이 맞지 않으면 false이고 fallback으로 넘어간다.
- TypeId 1은 직선/2는 두 점의 중심·거리로 정의한 링/3은 곡선 분기이며 요구 점수 미달은 false다.
- 이 TypeId와 FR segment Kind 번호는 서로 다른 값 체계다.

B의 화면/출력 공급값, 외부 Canvas transform, DPR의 모든 호출 문맥, ObjectScale이 점 좌표/공급 Paint에 미치는 전체 효과는 아직 미완이다. 이 식에서 곱셈 항이 안 보인다는 이유로 ObjectScale 전체 효과가 없다고 결론내리지 않는다.

## 4. shader uniform 11의 이전 해석 정정

- 이전 AOT-PATH-TRACE-2026-10-15.md는 uniform11을 _shaderFor 진입 첫 double(d0)로 적었다.
- 실제 명령 0x426c48은 진입 d0를 fp-0x20에 저장하고, 0x426c5c는 진입 d1을 fp-0x28에 저장한다.
- 뒤의 0x426da4/0x426db4는 각각 이 저장값을 사용한다.
- Blutter SetupParameters 요약보다 실제 명령/스택 슬롯 추적을 우선했다.

| uniform | _shaderFor 진입 인수 | 확인한 호출 의미 |
|---|---|---|
| 10 | d0 / 2 | W/2 |
| 11 | d1 | 보정된 sigma |
| 12 | d2 | 일반 직선·곡선 0, 링 1 (퇴화 링 전환 포함) |

- drawLine(0x42753c), drawCurve(0x425948), drawRing(0x427378), _drawRing(0x42741c)의 인수 재배치를 연결했다.
- 퇴화 직선/곡선이 링 분기로 전환되면 uniform12도 링값 1을 사용하므로 원래 TypeId만으로 모든 호출의 값을 고정하지 않는다.
- 이전 RGB 사전알파/GlowAlpha 대체 결론은 유지한다.
- uniform12를 세 번째 UI 숫자로 해석하지 않는다.
- 이 정정은 shader 경로의 의미이며 raster cache/MaskFilter에도 그대로 적용하는 식은 아니다.

## 5. blendMode는 전달 Paint를 따른다

- DrawGlowEffect는 입력 Paint.blendMode를 GLOW_PAINT에 복사한다(0x420e3c/0x420e48).
- TryDrawGlowWithShader에도 같은 모드를 전달(0x421248/0x42127c)하고 glow_shader._fill은 전달 모드를 Paint에 설정한다(0x425f30).
- 이름/강조 효과만으로 plus(단순가산)라고 할 근거가 없다.

- BuildDrawPlan은 isPreview에 따라 PREVIEW_OBJECT_PAINT 또는 OBJECT_PAINT를 선택한다(0x42beb4–0x42bf28). 두 초기화 함수(0x42d638/0x42d6e8)는 zero ByteData를 만들며 blend 슬롯은 0이다.
- 원본 ELF의 Paint.blendMode(0x428724)는 저장값을 _kBlendModeDefault와 XOR한 뒤 values에서 enum을 읽는다.
- IDA 이름으로 확인한 _kBlendModeDefault(0x42871c)는 Smi6=정수 3을 반환하고 PP enum index3 이름은 srcOver다.
- 따라서 **이 초기 Paint 상태는 srcOver**다.
- 이후 모든 경로에서 Paint를 변경하지 않는다는 전역 보장은 하지 않는다.

GLOW_PAINT는 전달 모드를 상속한다는 결론이 실제 불변 srcOver 결론보다 더 정확하다. 연결 객체들의 전체 합성/클리핑/다른 저장층 및 00–05 영상 실제 dispatch는 미확인 상태를 유지한다.

## 검증과 다음 행동

- 새 명령 표본 12개를 캐시 libapp.so의 PT_LOAD로 대응해 Capstone과 대조하여 통과했다.
- 2개 bl 표본의 초기 검사기 예상 주소 오기입을 원래 Blutter 주석과 대조하여 수정한 뒤 통과했으며, ELF/Blutter 불일치가 발견된 것은 아니다.
- 이는 새 표본 검증이며 모든 함수 의미/전체 프로그램 동등성 검사가 아니다.
- 집계는 AOT-DRAW-GLOW-AUDIT-2026-10-15.json. 기존 unit/probe/원본 시험은 문서 변경으로 반복하지 않았다.

- 정확한 다음: FrameInterpolationPlan._planFillRegions(0x62ff78)→renameTweenLinkedFill→canonicalize→held/interpolated/discard 분기와 색 선택을 제한적으로 연결한다.
- 그 뒤 B/D/Canvas transform의 실제 공급자와 shader/raster/fallback dispatch 연결을 보완한다.
- 휴대폰 재설치·Play설정변경·추가시험은 요청하지 않는다.

캐시: /workspace/scratch/e23c9fd610d3/private/blutter_out/{asm,pp.txt,ida_script/addNames.py}; ELF input/arm64-v8a/libapp.so; cached venv. 이번 표본 검사기/집계 임시본은 /workspace/scratch/25b8ca176661/private-trace/. 원본/assembly/private script는 공개하지 않고 직접작성 해석·집계만 반영한다.
