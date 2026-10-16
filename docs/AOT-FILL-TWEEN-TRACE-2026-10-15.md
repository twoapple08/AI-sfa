# AOT 채우기 보간 추가 추적 — 2026-10-15

- 기존 Blutter/ELF 캐시만 읽어 FrameInterpolationPlan._planFillRegions와 실제 step apply를 연결했다.
- 정적 경로 해석이며 기존 영상의 dispatch 또는 전체 픽셀 일치를 검증한 것은 아니다.
- 기존 00–05 입력·영상·unit/probe 시험/전체추출/휴대폰시작 시험은 반복하지 않았다.

## 1. 채우기 후보 필터와 링크 이름 변환

_planFillRegions(0x62ff78)는 AO 보간 쌍 목록이 비면 null을 반환한다(0x62ffb0–0x62ffc4). 목록이 있으면 각 쌍의 앞 AO ID로 집합을 만든다(closure0x632d10). 앞 FR 목록과 링크 변환 뒤 FR 목록을 _fillRegionReferencesOnlyObjects(0x632bfc)로 필터한다.

- 이 필터는 **outerSegments**가 비었으면 false이고, 각 outer segment의 ObjId가 위 집합에 모두 있어야 true다.
- 이 함수 자체가 모든 안쪽 구멍 경계까지 검사한다고 확대하지 않는다.
- 탈락 FR은 이 planner의 후보에 포함되지 않는다.

FrameInterpolationPlan 생성자에서 링크용 역방향 맵을 만든다. resolved source→destination 링크를 따라 destination AO ID→source AO ID(0x62f7a0–0x62f7fc), 같은 목록 위치의 destination AP ID→source AP ID(0x62f8b4–0x62f938)를 만든 뒤 planner에 전달한다(0x62fe78/0x62fe7c/0x62fe80). resolver의 TypeId/Index/충돌 검사와 결합하는 경로이며 모든 AO/점에 자동 공간대응을 추정하는 기능이 아니다.

- renameTweenLinkedFill(0x63222c)은 이 맵을 사용해 뒤 FR의 ObjId와 필요한 AP 참조를 앞 기준 이름으로 바꾼다.
- 매핑된 edge의 필요한 AP 참조를 찾지 못하면 null 반환 분기가 있다(0x6325dc/0x632674). circle과 edge 경로를 구분하고 색·구간값·contour metadata를 보존한 새 FR를 만든다.
- null 결과가 후보 필터에 들어가는 전체 비정상 입력 안전성까지 검증한 것은 아니다.

## 2. 두 단계 대응: 원래 signature, 이후 경계 정규화 키

- 첫 단계(0x630280–0x630750)는 뒤 후보를 FR signature별 ListQueue로 모으고 앞 후보와 대응시키며 소비된 양쪽 인덱스를 기록한다.
- FR 색을 signature에 넣는 경로는 아니다.
- FrameFillSegment.signature(0x5cfc7c)는 circle/edge를 구분하고 ObjId, edge의 AP 참조 및 두 구간 double, contour 값을 포함한다.
- FR signature는 segment signature를 목록 순서대로 결합한다.

- 남은 앞/뒤 후보로 두 번째 키 맵을 만든다(0x63099c–0x630ca8). segments를 canonicalize하고 결과가 null이면 원래 segments를 사용해 _buildFillRegionInterpolationSegmentKey를 결합한다.
- 같은 키의 후보 수가 **양쪽 모두 1개인 경우에만** 추가 짝을 만든다(0x630e98/0x630ec0의 tagged2=length1 검사). 여러 후보가 모호하면 임의 짝을 추가하지 않고 held 단계에 남긴다.
- 첫 단계의 중복 signature 소비와 두 번째 단계의 유일성 조건을 혼동하지 않는다.

interpolation segment key(0x632930)는 다음과 같다.

| 종류 | 대응 키에 들어가는 정보 |
|---|---|
| circle | contourIndex, circle 구분, ObjId |
| edge | contourIndex, edge 구분, ObjId, 앞/뒤 AP 참조 |
| 음수 AP 참조 | 숫자 대신 * |
| 구간 double(T1/T2) | 이 두 번째 키에는 포함하지 않음 |

이전 보고서의 미확인 field_33은 FrameFillSegment.signature의 ':contour:' 문자열 결합(0x5cfe80–0x5cfed8)과 canonicalize의 contour별 묶음으로 **contour index**에 대응시켰다. 실제 segment enum Kind와 AO TypeId는 별도 체계다.

- AP 참조를 좌표나 AnchorPoint.Index로 자동 정규화하지 않는다.
- 같은 ObjId/좌표라도 0 이상 AP 참조가 달라지면 키가 달라질 수 있다.
- 따라서 기존 표본에서 앞색이 유지됐다는 사실을 모든 대응쌍의 색 정책으로 일반화하면 안 된다.

## 3. canonicalize의 확인 범위

_canonicalizeFillSegmentsForInterpolation(0x631534)은 contour index별로 segments를 묶고 contour0 존재를 요구한다(0x631674–0x631690). contour 키를 정렬하고 각 contour의 정규화 결과를 합친다.

- _canonicalizeFillContourForInterpolation(0x631868)은 빈 목록 및 circle 관련 단일 segment 경로를 따로 처리한다.
- 일반 contour는 입력 방향과 순서를 뒤집어 각 segment.reversed를 적용한 후보를 만들고(0x6319a4–0x631a18, closure0x632148), _compareRotatedKeys(0x631c68)로 방향/시작 위치 후보를 비교한다.
- 결과는 선택된 회전 순서의 불변 목록이다.
- edge.reversed(0x632178)는 AP 앞/뒤 및 T1/T2를 교환하고 contour 값을 보존한다.

- 이는 시작 segment 위치나 순회 방향 차이를 흡수하는 대응 단계다.
- 좌표가 닮은 임의 다른 경계를 같은 contour로 합치거나, 구멍 contour 번호 자체를 재배정하는 것으로 해석하지 않는다.
- 전체 구조유효성/비정상 경계 정책과 모든 GDT dispatch 의미를 재구현한 것은 아니다.

## 4. 실제 apply: 대응된 FR과 미대응 FR은 색/존재 규칙이 다르다

_planFillRegions는 대응 후보에 _PairedFillStep, 남은 앞 후보에 _HeldFillStep(flag=true), 남은 뒤 후보에 _HeldFillStep(flag=false)를 만든다(0x63062c/0x630fdc/0x6311e4/0x631358). apply는 각각 아래 함수를 호출한다.

| step | t를 0–1로 제한한 상태의 동작 |
|---|---|
| Paired | 양쪽 ARGB 색 보간, 가능한 segment 구간 보간 |
| 앞 Held(true) | t<1이면 앞 FR 색/segments 유지, t=1이면 null |
| 뒤 Held(false) | t<1이면 null, t=1이면 뒤 FR 색/segments 유지 |
| 후보 필터 탈락 | 해당 planner step 없음 |

- _buildHeldFillRegion(0x7926b4)은 0x79272c/0x79274c의 t=1 비교와 flag 분기로 위 정책을 수행한다.
- 색 알파 0은 null. 점진적인 알파 페이드가 아니다.
- held의 segments 유지가 그 경계 AO 좌표까지 정지한다는 의미는 아니다.

_buildInterpolatedFillRegion(0x7920e4)은 clamp(t,0,1)로 InterpolateArgbColor(0x62e38c)를 호출한다(0x792178). 생성 색의 알파 0은 null이다. 따라서 **대응된 FR의 색도 앞색 고정이라는 결론은 틀리다.**

- InterpolateArgbColor는 A/R/G/B 각 채널에 대해 정수 앞값에 round((뒤값−앞값)×clamp(t,0,1))를 더하고 채널 범위로 제한해 합친다.
- round는 delta에 적용된다(0x62e464/0x62e488/0x62e4e0). 원본 의미를 재현할 때 Python의 ties-to-even round와 혼동하지 않는다.
- 이 코드의 채널 보간을 gamma/선형광 또는 사전알파 색공간 보간이라고 부르지 않는다.

## 5. segment 보간 실패에는 가까운 끝의 경계를 쓰는 fallback

_interpolateFillRegionSegments(0x7922b4)는 null/목록 길이 차이를 검사하고, 위치별 Kind/contourIndex/ObjId가 맞아야 한다(0x7923dc–0x792404). edge의 양수 앞 AP 참조는 유지하고 음수면 뒤 AP 참조를 선택한다(0x7924dc–0x7924f4). T1/T2는 각각 앞값+(뒤값−앞값)×clamp(t,0,1)로 보간한다(0x792508–0x792528).

- 이 함수가 null이면 _buildInterpolatedFillRegion은 **t<0.5이면 앞 FR의 원래 segments, t>=0.5이면 뒤 FR의 원래 segments**를 선택한다(0x7921c4–0x7921f4). 색은 이미 계산된 보간색을 사용한다.
- 이 경우 geometry의 단계 전환과 색의 연속 변화가 공존할 수 있다.
- paired가 생성됐다고 반드시 경계가 매끄럽게 보간된다는 보장은 아니다.

- _applyFillSteps(0x62e9e8)는 step.apply 결과가 null이면 출력 FR 목록에 넣지 않는다.
- 반환하는 FR는 새 ID=-1이고 계산한 색/segments를 가진다.
- 데이터 파일이 영구 삭제되는 UI 작업과 이 중간 렌더 목록의 null 생략을 구분한다.

## 검증·남은 문제

- 새 명령 표본 14개를 캐시 libapp.so PT_LOAD→Capstone과 Blutter 실제 명령으로 대조해 모두 통과했다.
- 집계는 AOT-FILL-TWEEN-AUDIT-2026-10-15.json. 검사기의 주석행 선택 regex를 interpreted/실제명령 양쪽에 맞게 수정했다.
- 새 전체추출/실물로그/픽셀 테스트가 아니며 기존 12개 검사를 재실행하지 않았다.

로컬 exec-server 연결이 한 번 끊겼으나 재연결 뒤 캐시 접근과 새 표본 검증이 성공했다. 연결실패를 캐시 손실/사용자 ADB 실패로 확대하지 않았다.

- 다음: canonicalize가 거르는 경계의 실제 구조유효성(_isFrameFillContourStructurallyValid), contour/hole의 렌더 Path 조립/부적합 경계 처리, 그리고 앞서 남은 B/DPR/Canvas transform 공급과 shader/raster dispatch를 한정 추적한다.
- 기존표본 재분석/휴대폰 명령/설치/라이선스 변경은 요청/실행하지 않는다.
- 현재 라이선스 차단과 보호작업은 그대로다.

캐시: e23c9fd610d3/private/blutter_out/asm/sfa/original_port/sequences/{frame,frame_fill_region,tween_link}.dart 및 input/arm64-v8a/libapp.so,venv. 새검사기/집계는 25b8ca176661/private-trace/{validate_fill.py,fill-validation.json}. 공개는 직접작성 해석·집계만, asm/source/original/log는 제외한다.
