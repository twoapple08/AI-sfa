# AOT 구멍·경계 유효성·Path 조립 — 2026-10-15

기존 frame_fill_region.dart/PP/ELF 캐시를 재사용했다. 아래는 읽은 Flutter 경로의 정적 해석이다. Android 실물 편집/전체 픽셀 동등성을 검증하지 않았으며 원래 앱의 영상 dispatch 확정도 아니다. 기존 시험/전체추출/설치/휴대폰 명령은 반복하지 않았다.

## 1. 구조유효성과 기하학적 폐곡선은 별도다

_isFrameFillContourStructurallyValid(0x36789c)는 빈 목록을 거르고, 각 segment의 ObjId로 AO를 찾아 _matchesSegment(0x367a5c)를 검사한다. 한 segment는 그 검사를 통과하면 허용한다. 여러 segment일 때는 완전 원 Kind가 섞이지 않아야 한다(0x3679f0–0x367a38; circle predicate0x367dc0). 이 단계는 모든 끝점 좌표가 이미 연결되는지 검사하는 함수가 아니다.

_matchesSegment의 확인 조건:

| 조건 | 확인한 처리 |
|---|---|
| AO 없음 | false |
| edge의 T1/T2가 NaN/무한대 | false |
| edge의 abs(T1−T2)<=1e-6 | false |
| edge의 0 이상 AP 참조 | 해당 AO의 점 목록에 존재해야 함 |
| 음수 AP 참조 | 존재검사 생략 경로 |
| AO TypeId1/2의 edge | 최소2점 |
| AO TypeId3의 edge | 최소3점 |
| 완전 원 Kind | AO TypeId2이며 최소2점 |
| 그 밖의 AO 타입 | false |

일반 edge의 finite T가 반드시0–1이어야 한다는 조건은 이 검사에 없다. 뒤의 primitive별 처리와 구분한다. AP 참조 존재검사가 곧 임의 AP 두 개를 골라 새로운 자유곡선을 만든다는 뜻도 아니다.

보간 경로 _isInterpolatedContourStructurallyValid(0x7963f0)/_matchesInterpolatedSegment(0x7965c0)에는 같은 비어있음/Kind/타입/점수/유한 T/구간폭 확인이 보인다. 보간 AO의 점 표현을 검사하며, 원본 _matchesSegment와 같은 AP ID 존재검색을 수행한다고 주장하지 않는다.

## 2. 외곽은 contour0, 나머지 구멍은 독립적으로 처리한다

_storedFillContours(0x367de4)는 segment의 contourIndex(field_33)로 묶고 각 목록 안의 저장 순서를 유지한다. buildFrameFillRegionPath(0x415a84)는 contour0 경로를 먼저 만든다. 외곽 builder가 null이면 전체 Path도 null(0x415b80–0x415b94). 정상 비음수 contour 번호 범위에서 양수 contour가 없으면 외곽 Path를 그대로 반환한다(0x420b48의 >0 검사/0x415ba0).

구멍이 있으면 각 구멍을 별도 Path로 만든다. builder가 null인 구멍은 빼기 목록에 넣지 않고 계속한다(0x415d0c/0x415d94). buildInterpolatedFrameFillRegionPath(0x794cd4)도 외곽 실패는null이며 구멍 실패는기존결과유지다(0x794e30/0x794f24).

FrameFillRegion.pruneInvalidContoursForObjectsById(0x3675ec)는 별도 데이터 정리 함수다. 외곽이 구조적으로 부적합하면 null이고 부적합 contour의 segments를 필터하는 경로가 있다. 변경없으면 기존FR, 변경시ID/색을보존한새FR를 반환하는 경로를 확인했다. 이 함수의 모든 편집/import 호출 범위까지 이번에 추적하지는 않았다. 렌더중null 생략과 저장상태 정리 함수를 혼동하지 않는다.

## 3. evenOdd와 구멍 차감은 두 단계

원본/보간 contour builder 모두 NativePath fillType 인수1을 설정한다(0x41d664/0x79503c). 공식 Flutter 선언 순서에서1은 evenOdd다. 즉 개별 contour의 내부 판정은 경계 교차 홀짝 규칙이다. 이는 winding 방향만으로 구멍을 판정하는 nonZero 규칙과 다르다.

그 뒤 구멍 결합은 **PathOperation.difference**다. 원본 buildFrameFillRegionPath의 캐시 miss closure(0x4205c8)와 보간 builder에서 op 인수0을 전달한다(0x420734/0x420738,0x794f10/0x794f14). 이 앱 PP의 enum index0 이름도 difference다. 인수는 새 결과Path/현재 외곽결과/이번구멍Path/operation으로 연결된다. 성공 결과를 다음 구멍의 외곽 입력으로 갱신한다.

따라서 확인한 경로는 `((외곽 − 구멍1) − 구멍2)…`다. 모든 contour를 한 Path에 더하고 evenOdd 한 번만 적용하는 모델로 바꾸면 안 된다. 집합 연산상 여러 구멍이 겹쳐도 겹친 곳이 자동으로 채워지는 XOR 효과가 없다. 외곽 밖 구멍이 별도 채움 영역을 추가하는 방식도 아니다. 이 둘은 확인한 연산에서 도출한 결과이지 신규 실물 영상 시험이 아니다.

원본 경로는 양수 contour가 있을 때 _HoledFillPaths.resolve(0x415e70)의 geometry steps 키 캐시를 사용한다. cache miss에서위difference를 계산하고 반환시Path.from 복사경로가 있다(0x415fc0). 보간 builder는읽은함수안에서직접difference를수행한다. 캐시전체키정확성/용량/모든무효화는미확인.

Native Path combine의 실패값은 StateError('Path.combine() failed…NaN…') 경로로 연결된다(0x420764/0x794f44). 구멍 builder가 null인 경우의 생략과 native op 실패의 예외는 다른 처리다. 임의 모든 실패를 '해당 구멍만 무시'로 합치면 안 된다.

## 4. 경계 조립은 간격을 연결하고 마지막을 닫는다

_buildFrameFillContourPath(0x41d5c0)와 _buildInterpolatedFrameFillContourPath(0x794f9c)는 구조검사 후 저장된 edge들을 순회한다. 첫 시작점 moveTo, 이어 필요한 lineTo/arcTo/quadraticBezierTo를 호출한다. 완전 원 single Kind는별도circle builder 경로다.

현재끝점과다음segment시작점 사이 거리가0.1보다크면 시작점까지 연결 lineTo를 추가한다(예:0x41de34/0x795354). 마지막끝점과첫시작점도같은거리검사 후필요한lineTo,그뒤close를호출한다(0x41eb38/0x41eb98/0x41eca0,0x7958b0/0x79590c/0x79594c). 임계0.1은 TranslateToScreen 계열 이후 이 Path 입력좌표의 거리이며 최종 영상의0.1물리픽셀로 확정하지 않는다.

따라서 틈이 있다는 이유만으로 구조검사가 false라고 추정하면 안 된다. 경계순서가원하는둘레순서와다르면 연결선으로다른형상이될수있다. 이것은좌표순으로가장좋은폐곡선을찾는전체자동정렬알고리즘이아니다. 자기교차/면적0/곡선단일contour의전체기하유효성은이번조건만으로보장되지않는다.

## 5. 부분 구간의 처리도 primitive마다 다르다

- 직선 _resolveLineSegmentPoints(0x41ffc0)는 첫2점의TranslateToScreen 결과에서Offset.lerp(T1),lerp(T2)를계산한다(0x42013c/0x420158). 이 함수 안에 T를0–1로clamp하는호출은없다.
- 이차곡선 _resolveQuadraticSegmentPoints(0x41f248)는첫3점의화면좌표를만들고T1/T2를0–1로clamp한다. clamp뒤구간폭이1e-6이하면null. min/max로subsegment를추출하고원래T방향이반대면끝점을바꾼다(0x41f4d8–0x41f5b0).
- _extractQuadraticSubsegment(0x41f600)는_splitQuadraticBezier를연결해부분곡선을추출한다. 단순히원래제어점을유지하며끝점만이동하는식이아니다. 전체베지어수치정밀도재현은미검증.
- 원형AO의edge/arc _resolveCircleArc(0x41f9ac)는두점의중심과거리/2로원반경을구하고중심에서첫점으로향하는기준각(P0−center의atan2)에2π×T1/T2를더한다(0x41fb24/0x41fb60/0x41fb70). radius양수/유한T검사가있으며읽은함수안에T clamp호출은없다. 완전원Kind의별도전체원Path와혼동하지않는다.

이들 차이 때문에 '모든부분경계T는그대로쓰기' 또는 '항상0–1로잘라쓰기'를공통규칙으로사용하면안된다. ObjectScale/Canvas/DPR가만드는최종좌표는현재다음공급추적대상이다.

## 검증과 다음 행동

새명령표본14개(구멍operation/Path fillType/구간/연결거리/부분곡선호출)를캐시ELF PT_LOAD와Capstone으로대조해모두통과했다. 집계AOT-FILL-PATH-AUDIT-2026-10-15.json. 이전보간14개시험을재실행한것이아니다. 전체함수의모든분기/실물렌더/동등성증명아님. 문서작업으로기존unit/probe생성시험반복없음.

다음: TranslateToScreenX/Y,_screenOffsets와interpolated transform→OBJECT/PREVIEW Paint baseStrokeWidth B와ResolveDevicePixelRatio 공급→화면/영상 shader-raster-fallback dispatch. _HoledFillPaths 키/무효화와영역레이어의미확인도유지한다. 휴대폰추가작업/설치/라이선스변경요청없음.

근거캐시 e23c9fd610d3/private/blutter_out/asm/sfa/original_port/sequences/frame_fill_region.dart,pp.txt,input/arm64-v8a/libapp.so,venv. 새검사25b8ca176661/private-trace/{validate_path.py,path-validation.json}. 공개는직접작성보고서/집계만.

공식enum근거: https://api.flutter.dev/flutter/dart-ui/PathFillType.html , https://api.flutter.dev/flutter/dart-ui/PathOperation.html . 문서의enum의미와이앱의호출인수/PP메타데이터를연결한정적해석이다.
