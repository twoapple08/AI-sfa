# Blutter 제한 추적: 가져오기·그리기 계획·글로우·수동 링크

기존 Blutter 캐시를 재사용해 관련 함수만 읽었다. 설치/빌드/전체 추출, 00–05 SFA·영상 재분석, 앱 실행은 하지 않았다. 아래는 **정적 코드 경로 해석**이며 실제 영상의 실행 경로 확정이나 전체 렌더러 완성이 아니다. 공개한 것은 직접 작성한 해석과 주소·검증 집계뿐이다.

입력/추출의 기존 검증은 [FLUTTER-TOOLS-RESULTS-2026-10-15.md](FLUTTER-TOOLS-RESULTS-2026-10-15.md). 이번 집계는 [AOT-PATH-TRACE-AUDIT-2026-10-15.json](AOT-PATH-TRACE-AUDIT-2026-10-15.json). 아래 주소는 Blutter 코드주소이며 ELF 문자열 오프셋/ASLR 절대주소가 아니다. 경로는 `private/blutter_out/asm/sfa/` 기준이다.

## 1. XML 왕복의 DrawOrder/ObjectScale 변화 원인

`original_port/activities/import_animation_activity.dart`의 `_ImportSequenceXmlHandler.startElement`(0x5099ac)는 AO에서 ID/TypeId/Color/ThicknessScale/글로우/LayerId를 읽지만 **DrawOrder와 ObjectScale을 조회하지 않는다**. 함수 전체의 속성 조회를 한정 집계해 확인했다. 단순히 파일 전체 문자열 검색만으로 내린 결론이 아니다.

| 연결 | 근거 주소 | 해석 |
|---|---|---|
| 새 AO 생성 | startElement 0x50a964–0x50a9f8 → DataAccess.CreateNewAnimationObject 0x50c980 | XML AO ID에 대응하는 공통 객체가 없을 때 새 DB 객체를 만들고 대응 맵에 보관 |
| 새 순서값 | data_access.dart 0x50ca7c, 0x50cdf4–0x50ce1c | 새로 할당한 AO ID를 객체 field_2f에 넣고 UpdateAnimationObjectDrawOrder로 저장 |
| 크기 기본값 | animation_object.dart 생성자 0x3542b4, 0x354300–0x354304 | ThicknessScale(field_37), ObjectScale(field_3f)을 각각 1로 시작 |
| 상세값 저장 | data_access.dart 0x50ce54–0x50ce64; importer 0x50b0b8–0x50b0e0 | 생성 상세값에 크기 1을 전달. 이후 importer는 기존 field_3f를 다시 전달하며 XML ObjectScale으로 덮어쓰지 않음 |
| 내보내기 | animation_object.dart GetXml 0x5af2d4–0x5af368 | field_2f를 DrawOrder, field_37을 ThicknessScale, field_3f를 ObjectScale로 기록 |

따라서 이 가져오기 경로에서는 **명시한 XML 순서값 대신 첫 생성 순서에 따른 새 ID가 순서값이 되고, XML ObjectScale=2도 초기값 1로 남는 것**이 기존 01/02 왕복 관찰과 맞는다. 저장기가 임의로 값을 제거했다고 볼 근거는 없다. 별도 UI에서 크기를 바꾸고 저장한 04의 ObjectScale=2 보존과도 모순되지 않는다. 모든 복구/import 형식 또는 기존 객체 갱신 정책에 일반화하지 않는다.

DB 로드 SQL의 0x34f208/0x34f23c에는 `COALESCE(a.draw_order, a._id) ASC, a._id ASC` 정렬이 있다. `main.dart`의 compareDrawOrder(0x5b9c54)는 양수 DrawOrder, 아니면 AO ID를 비교하고 동률이면 ID를 비교한다. **이 closure의 부모는 _mergeLayerDown(0x5b86f4)**이다. 이름만 보고 FrameDrawPlan의 공통 comparator라고 확정하면 안 된다. SQL COALESCE와 closure의 비양수 fallback도 완전히 같은 식은 아니다.

## 2. FrameDrawPlan의 unit 배치와 FR 위치

`original_port/sequences/frame.dart` BuildDrawPlan(0x42b910)은 AO ID 맵, FillRegionsByFigure, 연결 글로우 그룹을 만든 뒤 레이어 목록을 순회한다. 숨김 레이어를 건너뛰고 `_BuildLayerObjectGroups`(0x42c2c8) 결과를 순회한다. 이 그룹 함수는 해당 레이어의 AO를 입력 순서로 모으며 연결 그룹 ID를 키로 사용하고, 없으면 자신의 AO ID를 사용한다. 이 함수 자체에는 DrawOrder sort 호출이 없다. 입력 AO 목록의 모든 공급 경로에 대한 정렬 보장은 아직 확인하지 않았다.

각 그룹에서 먼저 glow-only unit을 추가(0x42bc34–0x42bc54)하고, 이어 그룹의 각 AO에 대해 FR 목록을 `take`한 object unit을 추가(0x42bd50–0x42bdf8)한다. `drawUnit`(0x414ee8)은 object가 없으면 그룹 글로우를 그리고 반환한다. object가 있으면 **그 unit의 FR을 먼저 그리고 그 AO의 기본 선/형상을 그린다**(0x414f78, 0x41509c).

따라서 이 planner는 레이어 전체를 단순히 ‘FR 전부→글로우 전부→선 전부’로 그리는 구조가 아니다. 뒤 object unit의 FR이 앞 object unit의 선을 덮을 수 있는 구조다. 01 청록 면 관찰과 부합하지만 해당 영상의 dispatch를 확정한 것은 아니다.

`frame_fill_region.dart` FillRegionsByFigure 생성자(0x42d20c)는 FR의 **outerSegments**가 참조하는 ObjId마다 해당 FR 인덱스를 역색인한다. 같은 FR에서 중복 ObjId는 제거한다. `resolveFrameFillRegionLayer`(0x415954)는 outerSegments를 순회해 처음 찾은 유효 AO의 LayerId를 반환하며 없으면 null이다. `take`(0x42bf90)는 현재 AO를 참조하는 후보 중 레이어가 맞고 아직 소비되지 않은 FR을 반환한다. BuildDrawPlan은 이를 소비 집합에 추가한다.

이 경로에서 FR 배치는 XML FR 목록만으로 정해지지 않는다. **그룹/AO 방문 순서·outerSegments 참조·레이어·소비 여부**가 관여한다. 같은 AO에 걸린 여러 FR의 후보 순서는 저장 목록을 따르므로 ‘FR 목록 순서는 언제나 무의미’로 확대하면 안 된다. 그룹 비연속 AO의 방문 순서, 혼합 레이어 FR, 유효하지 않은 경계 정책은 남은 추적 항목이다.

## 3. 글로우 알파·uniform과 fallback

`animation_object.dart` GetXml로 GlowRadius(field_f), GlowColor(field_17), GlowAlpha(field_1f), GlowThickness(field_27)를 대응시켰다. DrawGlowEffect(0x420dcc)에서 radius/alpha가 양수인지 확인하고, 0x421000–0x421024에서 **(GlowAlpha의 하위 8비트 << 24) | (GlowColor의 RGB 24비트)**를 만든다. GlowColor 자체의 알파를 곱하는 경로가 아니다. 기본 선 색상의 알파도 이 색 조합에는 들어가지 않는다. 기존 02의 GlowColor 알파 차이·기본선 알파0 발광과 부합한다.

같은 함수는 shader를 먼저 시도(0x421298), 성공하면 반환한다. 실패하면 raster plan/cache를 시도(0x42131c/0x421398)하고, 여의치 않으면 MaskFilter/DrawGlowGeometry(0x4213f4/0x421450)로 진행한다. 화면 밖 검사는 이 사이에 있다. 따라서 shader 한 식을 모든 출력 경로의 픽셀 정답으로 사용할 수 없다.

`sequences/glow_shader.dart` `_shaderFor`(0x426c38)의 확인된 uniform은 다음과 같다. a는 전달된 ARGB의 알파/255이다.

| 인덱스 | 값 |
|---|---|
| 0,1,2 | (R/255 × a), (G/255 × a), (B/255 × a) |
| 3 | a |
| 10 | 전달된 두께 인수 / 2 |
| 11 | 첫 double 인수(d0 진입값) |
| 12 | 세 번째 double 인수(d2 진입값) |

RGB는 사전 알파 적용이다. 11/12의 전체 호출자별 물리적 의미는 아직 모두 매핑하지 않았으므로 UI 숫자 단위라고 확정하지 않는다. `_drawRing`(0x42741c)은 중심/반경을 4/5/6에, 별도 값을19에 넣는다. `_fill`(0x425e9c)은 전달받은 blendMode를 paint에 설정한다. **blendMode의 실제 열거값/연결 객체별 정책은 미완**이다.

이름과 달리 Frame._DrawCompositeObjectGlow(0x420c30)는 현재 읽은 범위에서 각 AO의 DrawGlowEffect를 순회 호출한다. 이름만으로 saveLayer나 그룹 전체의 단일 가산 합성을 주장하지 않는다. 단위 환산에서는 sequence thickness/100, ThicknessScale, paint stroke width, devicePixelRatio, GlowThickness/10이 결합되고 radius에도 sequence 배율/DPR이 들어가는 코드가 보인다(0x4210e8–0x421200). 각 paint 입력의 생성까지 연결해야 최종 공식을 확정할 수 있다.

## 4. FrameInterpolationPlan과 수동 TweenLink의 제한

`tween_link.dart` resolveTweenLinks(0x632d74)는 링크 키를 정렬해 순회한다. 원/뒤 프레임의 객체 맵과 링크 맵을 조회한 뒤 다음 조건을 검사한다.

- 양쪽 객체가 존재하며 같은 TypeId(field_47)이어야 한다(0x632f58–0x633000).
- 같은 원본 ID에 중복 결과를 넣지 않고, 양쪽에 그대로 살아 있는 ID와 충돌하는 링크를 건너뛰는 검사들이 있다(0x632f68–0x632fe8). 구체적으로 반환 맵의 source 중복, 앞 객체 맵의 destination 존재, 뒤 객체 맵의 source 존재를 배제한다.
- `_samePoints`(0x633088)는 점 목록 길이와 **목록 위치별 AnchorPoint.Index(field_23)**가 같은지 검사한다. 좌표/점 ID/Flags가 같아야 한다는 검사로 오독하지 않는다. field_23은 anchor_point.dart GetXml 0x5af690–0x5af69c로 Index에 대응했다.

FrameInterpolationPlan(0x62f408)은 0x62f6d4에서 이 resolver를 호출하며, AO 쌍 선택에서 같은 ID 대응을 먼저 찾고 없으면 해석된 링크 맵을 조회한다(0x62faf4–0x62fb40). 대응이 없으면 그 AO의 보간 쌍을 추가하지 않는 분기가 있다. 이는 03의 새 ID 중간 누락과 05 원대원 수동 링크 복구를 설명하는 Flutter 경로를 제공한다. 실제 앱 dispatch/여러 링크 충돌 사례의 실행 검증은 추가하지 않았다.

FR 보간은 별도 `_planFillRegions`(0x62ff78)에서 renameTweenLinkedFill(0x630170), canonicalize(0x630650 등)를 호출한다. `_buildFillRegionInterpolationSegmentKey`(0x632930)는 circle/edge를 구분하고 ObjId·점 참조(음수이면 `*`)·추가 field_33을 키에 넣는다. 이 field의 완전한 매핑과 held/interpolated/discard 분기·색 정책은 **다음 추적 대상**이다. APID만 같은지 보는 단순 규칙이나 모든 FR색은 앞색이라는 일반화는 아직 불가하다.

## 검증·다음 체크포인트

새로운 11개 명령주소를 원본 libapp의 PT_LOAD로 대응해 독립 Capstone 명령과 대조했고 모두 통과했다. importer의 속성 목록 집계도 통과했다. 기존 4개 검사를 재실행하거나 원본 파일을 다시 분석하지 않았다. 이는 주소·명령 표본 검증이며 위 모든 의미 해석/전체 함수의 정확성 보증은 아니다. 문서 변경이라 기존 생성·unit test는 반복하지 않았다.

다음은 ① Frame.GetAnimationObjects의 로드·캐시 공급자가 planner에 주는 순서와 비연속 연결 그룹의 방문순서 ② TryDrawGlowWithShader(0x425458)/DrawGlowEffect의 paint 배율·blendMode 실제값 ③ _planFillRegions(0x62ff78)와 renameTweenLinkedFill, canonicalize, held/interpolated 분기를 좁게 추적한다. 이번에 확정한 XML 속성 누락/기본값·기존 00–05 영상은 다시 처리하지 않는다.

reFlutter 엔진 빌드/Android 실행/분할APK 서명 미완은 그대로다. 고정 PREVIDEO 예측, File-2 최적화, 학습·AI 연결은 계속 보류한다.
