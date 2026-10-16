# 채우기 경로·그리기 계획·편집 기록 캐시의 재사용 경계 — 2026-10-15

- 기존 AOT/PP/원본 ELF를 이용한 정적 추적이다.
- 앱 수정 시험이나 기존 영상의 재분석은 하지 않았다.
- 직접 작성한 해석·집계만 공개한다.
- UI의 모든 변경 명령부터 갱신 완료까지 검증한 결과로 확대하지 않는다.

## 1. 캐시는 서로 다른 층에 있다

| 층 | 저장/재사용 대상 | 이번 연결 |
|---|---|---|
| _HoledFillPaths | 원본 Frame의 구멍 합성 결과 Path | 경로 명령·좌표 비트열 key, 최대 256개 LRU, 반환 복사 |
| FrameDrawPlanCache | 그룹/채우기/본체의 그리기 계획 | 객체 목록에 대한 Expando와 _KeptDrawPlan.fits |
| EditorFrameCache | Picture run·화면 image·underlay | 설정/구조 검사, 속성 snapshot, 변경 단위 집합, 재기록/폐기 |
| GlowRasterImageCache | 흰색 글로우 이미지 | 기존 GLOW-BACKEND의 local geometry·Wq/Rq·크기 양자화 key, 색은 나중에 입힘 |
| export 기록 | 출력용 Picture | _recordExportPicture의 새 recorder·동적 Draw·endRecording |

- 계획을 재사용한다고 완성된 픽셀을 그대로 재사용하는 것은 아니다.
- 색을 바꿨을 때 Path가 같아도 Picture는 달라질 수 있다.
- 실제 코드의 층별 결정을 분리한다.

## 2. 구멍 경로 key는 ID가 아니라 생성 명령·좌표다

buildFrameFillRegionPath(0x415a84)는 _storedFillContours 결과에서 contourIndex>0이 있는지 검사한다(closure0x420b48의 gt). 있으면 double 목록을 만들고 contour0과 각 hole을 빌드하면서 경로 steps를 기록한다. 없으면 steps=null이고 원본 외곽 Path를 바로 반환한다(0x415b98–0x415bac). 이 함수의 no-hole 경로에 _HoledFillPaths를 자동 적용하지 않는다.

- 경로 빌더는 moveTo의 명령 구분 값과 실제 좌표를 steps에 넣는다(0x41dd54–0x41ddec). line/curve/close에도 별도 명령과 인수 기록이 있다.
- 원형 contour도 구분 값 6과 화면 좌표를 기록하고 실제 Path를 addPath한다(0x41d7b4/0x41d950/0x41db14). 이 원형 기록은 단순 SFA 좌표만이 아니라 DrawInformation의 배율/offset과 연결된다.
- 이전 fill path의 좌표·hole 제외 규칙을 유지한다.

- hole 시작에는 7을 넣고(0x415cec), hole 생성 결과 null이면 8을 추가한다(0x415d0c–0x415df0). outer0 실패는 전체 null, hole 실패는 해당 hole 제외라는 기존 규칙이다.
- 따라서 유효한 hole들의 좌표뿐 아니라 실패 경계 표지도 key를 구성한다.
- 모든 marker·arc 인수 순서를 복제 구현으로 전개한 것은 아니다.

_StepsKey(0x416234)는 입력 double 목록을 **새 Float64 배열로 복사**한 뒤 같은 buffer를 Int64List로 본다(0x416294/0x4162b0/0x4162c8). hash는 길이에서 시작해 각 64bit word를 Object.hash로 누적한다. ==(0x7285f8)은 클래스/hash/길이를 먼저 확인한 다음 **모든 64bit word를 비교**한다(0x7286e8–0x7286fc). hash가 같다고 즉시 같은 key로 처리하지 않는다.

- 이 key에는 GlowRadius나 색을 단독 필드로 넣는 방식이 없다.
- key는 이미 빌더가 만든 steps다.
- 원본 AO/FR의 ID가 같아도 좌표·경로 명령이 달라지면 key가 달라진다.
- 반대로 다른 ID에서도 동일한 steps면 이 층에서 재사용 가능하다.
- 이 bit 비교는 glow 이미지의 round(value×2) 양자화와 다르다.
- 형상 의미가 같더라도 bit열이 다르면 cache miss가 될 수 있고, 모든 NaN/비정상 path 처리까지 보장한 것은 아니다.

## 3. _HoledFillPaths의 hit/miss와 반환 보호

resolve(0x415e70):

1. 새 _StepsKey를 만들고 map.remove(key)로 기존 Path를 꺼낸다.
2. hit이면 조합 closure를 호출하지 않는다. miss이면 closure를 실행해 Path를 만들고 miss 카운터를 증가시킨다.
3. miss 삽입 전에 기존 항목 수≥256이면 첫 key를 제거하고 반복한다(0x415f2c–0x415f9c).
4. hit/miss 모두 key→Path를 다시 삽입해 최근 항목을 뒤로 옮긴다.
5. 저장 Path 자체를 전달하지 않고 Path.from으로 복사해 반환한다(0x415fc0).

- 이 경로는 **최대 256개 항목의 LRU**다.
- 저장 용량을 bytes나 픽셀 예산으로 해석하지 않는다.
- miss가 곧 전체 map.clear라는 뜻도 아니다.
- 좌표/구멍 변경은 새 key 선택으로 이어지고 기존 entry는 이후 eviction까지 남을 수 있다.

- hit에서도 앞의 contour 빌드는 진행되어 key를 만든다.
- 재사용으로 생략되는 것은 읽은 resolve closure의 최종 hole combine 작업이다.
- ‘경로 캐시 hit라서 모든 geometry 계산 생략’은 틀리다.
- 반환 복사 덕분에 호출자가 반환 Path를 바꾸는 것이 저장 entry 자체를 바꾸는 경로와 구분된다.

- 보간은 별도로 확인했다.
- buildInterpolatedFrameFillRegionPath(0x794ce8)는 보간 outer/hole을 만들고 __op native Path.combine으로 합성한다(0x794d48/0x794e28/0x794f14). 읽은 함수에는 위 _HoledFillPaths.resolve 호출이 없다.
- 원본의 exact steps LRU를 모든 보간 t에도 적용한다고 일반화하지 않는다.

## 4. 그리기 계획 캐시는 구조를 확인한다

FrameDrawPlanCache.planFor(0x51743c)는 Frame.field_1f의 AO 목록을 Expando key로 조회하고 _KeptDrawPlan.fits(0x517d38)가 true이면 보관된 plan을 반환한다. miss/부적합이면 BuildDrawPlan을 다시 만들고 AO 목록에 새 kept plan을 연결한다(0x517484/0x51749c/0x5174cc/0x517524).

- fits의 확인한 조건은 Frame identity, AO 목록 identity/길이, AO의 목록 순서별 identity·LayerId·점 수, Frame의 layer/fill 관련 목록 identity/길이, layer identity와 저장 값, fill 관련 항목 identity 등이다.
- AO의 LayerId는 GetXml0x5af2ac로 대응했다.
- 같은 GDT 슬롯을 근거 없이 다른 클래스의 같은 메서드명으로 일반화하지 않았다.

- 이 함수 전체를 읽은 범위에서 점 x/y, AO Color, ThicknessScale, ObjectScale, GlowRadius 등을 매번 비교하는 snapshot 루프는 아니다.
- plan의 객체 참조를 유지하는 것과 편집 화면의 Picture를 유지하는 것은 별도다.
- 좌표·색만 바뀌어 plan이 재사용되더라도 drawUnit이 현재 객체를 읽는 경로가 있다.

- 특히 모든 in-place 변경이 fits에 완전히 감지된다고 보장하지 않는다.
- DrawOrder/Flags/contour 목록의 직접 변경이 실제 UI에서 어떤 목록 교체·정렬·revision과 함께 이루어지는지는 후속 호출자 범위다.
- 여기서 UI 버그나 무효화 누락을 확정한 것은 아니다.

## 5. 편집 기록에는 속성 snapshot 비교가 있다

EditorFrameCache.paint(0x414738)는 _settingValues로 설정 목록을 만들고 이전 목록과 listEquals한다(0x414850). 설정이 다르면 _dropUnderlay와 새 _FrameRecord 경로로 간다. 기록이 있고 설정이 같으면 _FrameRecord.update를 시도한다(0x4148bc). 기록이 없거나 update 결과 null이면 _dropRecordings, 새 _FrameRecord로 이어진다(0x4148ec/0x414900). 새 record 생성자는 BuildDrawPlan을 직접 호출한다(0x42926c).

update(0x42db0c)는 Frame·목록 구조/순서/LayerId/점 수/anchor connection 수와 값을 대조하고 부적합하면 null을 반환한다. 값 변경의 경우 _holdsValues(0x42e928)를 사용한다.

_addValues(0x42af24)와 _holdsValues를 연결한 AO snapshot은 다음을 포함한다:

- TypeId, Color, ThicknessScale, ObjectScale.
- GlowRadius, GlowColor, GlowAlpha, GlowThickness, DrawOrder.
- field_5f boolean을 숫자로 만든 값.
- 각 point의 x(field_33),y(field_3b),Index(field_23).

- Glow 관련 XML 필드는 GetXml0x5af3a4–0x5af45c와 연결했다.
- field_5f를 임의 UI 옵션명으로 이름 붙이지 않았다.
- 이 snapshot은 glow 이미지 key와 달리 Color/GlowColor도 비교한다.
- 비교는 값의 fcmp이며 Float64 bit key와 같은 방식이라고 합치지 않는다.

값이 다르면 _addValues로 snapshot을 갱신하고 영향 unit 집합에 인덱스/의존 집합을 넣는 경로가 있다(0x42e394–0x42e61c). 정상값 변화가 모두 전체 record를 null로 만드는 것은 아니다. 영향 집합의 본체/glow/fill별 매핑과 그룹·구멍 의존 전파의 완전한 공급자는 아직 아래 다음 범위다.

paint는 기존 recordings와 새 영향 집합의 관계 검사에 통과하면 _drawWithRecordings로 간다. 새 기록 선택에서 변경 unit 수 D와 plan unit 수 U가 2D≤U인 조건을 검사한다(0x414a44–0x414a64). 이 조건과 drag/이전 집합 조건이 맞으면 _record에 변경 집합을 넘기고, 다른 분기에는 빈 집합을 넘겨 다시 기록한다(0x414aac/0x414b40). 따라서 ‘변경이 작으면 언제나 같은 Picture 유지’라는 무조건 규칙은 아니다.

_drawWithRecordings에는 Picture 재생(0x428c68)과 특정 unit을 drawUnit으로 다시 그리는 경로(0x428cd4)가 같이 있다. _dropRecordings는 참조를 null로 만들고 각 run의 native 자원을 폐기하는 경로, _dropUnderlay는 Picture.dispose 후 관련 참조를 null로 만든다(0x42d974/0x42eeac–0x42eeb8). 이 폐기를 global glow/holed-path cache 전체 초기화로 읽으면 틀린다.

## 6. 수정별 재사용 경계와 export 구분

| 수정/조건 | 원본 hole-combine cache | glow raster image cache | 편집 기록 |
|---|---|---|---|
| 색·글로우색/알파만 변경, geometry 같음 | 동일 steps면 재사용 가능 | 동일 key면 흰 mask 재사용·새 색 입힘 | 색/알파 snapshot 차이를 검사 |
| 점 좌표 변경 | 생성 steps bit열이 달라지면 miss | local/크기/양자화 key가 달라지면 miss | point x/y snapshot 차이를 검사 |
| 전체 평행 이동 | screen steps가 달라지면 miss | 절대 원점 제외,동일 local/dimension key면 재사용 가능 | 좌표 변화에 따른 기록 갱신 경로 |
| 두께·글로우 반경 변경 | fill steps가 동일하면 이 층 재사용 가능 | Wq/Rq·dimension key에 따라 hit/miss | ThicknessScale/GlowRadius/GlowThickness 검사 |
| 구멍/경계 변경 | 명령·좌표·hole 표지가 달라지면 miss | 이 층의 mask 생성은 개별 AO geometry 기준 | 구조/의존 집합 공급자를 더 확인해야 함 |
| Frame/목록 구조 부적합·설정 변화 | 호출될 때 새 steps로 결정 | 호출될 때 새 plan key로 결정 | underlay/recordings 폐기·record 재생성 경로 |

- 조건부 표다.
- 같은 색 변경에서도 geometry/설정이 함께 변하면 다른 결과가 나올 수 있다.
- glow key의 세부 q/예산/ColorFilter·blend는 AOT-GLOW-BACKEND-TRACE-2026-10-15.md를 유지한다.
- 모든 이동/확대가 같은 image key라고 단정하지 않는다.

- export _recordExportPicture closure(0x62dc88)는 새 PictureRecorder를 만들고 배경·동적 Draw·endRecording한다(0x62dcb0/0x62df14/0x62df1c). 이 읽은 closure는 EditorFrameCache.paint/_recordings를 호출하지 않는다.
- export의 Frame/InterpolatedFrame Draw 아래 정적 geometry/glow cache와, 편집기 run Picture cache를 동일하게 취급하지 않는다.
- 이전 EXPORT-DISPATCH의 raw/PNG 동일 Picture 기록 연결과 runtime 제한을 유지한다.

## 7. 검증과 정확한 다음

- 새 65명령 ELF PT_LOAD/Capstone 대조 통과. Blutter가 압축 pointer의 stur 피연산자를 NULL로만 적은 두 곳(0x42d974/0x42eeb4)은 실제 32bit w22로 정규화해 대조했다.
- 이 폭 정규화를 audit에 명시한다.
- AOT-CACHE-BOUNDARY-AUDIT-2026-10-15.json. 명령 표본 검증은 전체 함수 의미·실제 UI 변경·픽셀 일치 증명이 아니다.

- 문서만 변경하며 기존 unittest/probe/영상/폰시험은 반복하지 않았다.
- 학교 Wi-Fi의 정확한 제약/USB/PC OS는 미확인, 지금 사용자 추가작업 없음.
- 라이선스 응답 4 차단과 보호 원본/고정 예측 상태 유지.

- **다음:** _FrameRecord 생성자의 AO→본체/glow/fill unit 인덱스·의존 집합 생성과 update 전파를 연결한다.
- 이어 실제 편집 변경 호출자의 DrawOrder/Flags/FR contour 변경·목록 교체/무효화 계약을 좁게 확인한다.
- 객체 하나를 움직일 때 그룹 glow·연결된 fill/구멍이 함께 갱신되는지를 정적 경로로 먼저 닫는다.

캐시:e23c9fd610d3/private/blutter_out/asm/sfa/original_port/{sequences/{frame,frame_fill_region,animation_object}.dart,editor/editor_frame_cache.dart,activities/sequence_action_activity.dart},PP/원본 ELF/venv. 새검사 5a16c98ed7ee/private-trace/{validate_cache_boundary.py,cache-boundary-validation.json}. 문서 worktree5a16c98ed7ee/AI-sfa-publish,옛 dirtyworktree보존.
