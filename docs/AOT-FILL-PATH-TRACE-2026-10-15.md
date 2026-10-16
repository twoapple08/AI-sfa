# AOT 구멍·경계 유효성·Path 조립 — 2026-10-15

- 기존 frame_fill_region.dart / PP / ELF 캐시를 재사용했다.
- 아래는 읽은 Flutter 경로의 정적 해석이다. Android 실물 편집이나 전체 픽셀 동등성을 검증하지 않았고, 원래 앱의 영상 dispatch 확정도 아니다.
- 기존 시험·전체 추출·설치·휴대폰 명령은 반복하지 않았다.

## 1. 구조 유효성과 기하학적 폐곡선은 별도다

- `_isFrameFillContourStructurallyValid`(0x36789c)는 빈 목록을 거르고, 각 segment의 ObjId로 AO를 찾아 `_matchesSegment`(0x367a5c)를 검사한다.
- 한 segment는 그 검사를 통과하면 허용한다.
- 여러 segment일 때는 완전 원 Kind가 섞이지 않아야 한다(0x3679f0–0x367a38; circle predicate 0x367dc0).
- 이 단계는 모든 끝점 좌표가 이미 연결되는지 검사하는 함수가 아니다.

`_matchesSegment`의 확인 조건:

| 조건 | 확인한 처리 |
|---|---|
| AO 없음 | false |
| edge의 T1/T2가 NaN/무한대 | false |
| edge의 abs(T1−T2) <= 1e-6 | false |
| edge의 0 이상 AP 참조 | 해당 AO의 점 목록에 존재해야 함 |
| 음수 AP 참조 | 존재 검사 생략 경로 |
| AO TypeId 1/2의 edge | 최소 2점 |
| AO TypeId 3의 edge | 최소 3점 |
| 완전 원 Kind | AO TypeId 2이며 최소 2점 |
| 그 밖의 AO 타입 | false |

- 일반 edge의 finite T가 반드시 0–1이어야 한다는 조건은 이 검사에 없다. 뒤의 primitive별 처리와 구분한다.
- AP 참조 존재 검사가 곧 임의 AP 두 개를 골라 새로운 자유 곡선을 만든다는 뜻도 아니다.
- 보간 경로 `_isInterpolatedContourStructurallyValid`(0x7963f0) / `_matchesInterpolatedSegment`(0x7965c0)에는 같은 비어 있음 / Kind / 타입 / 점 수 / 유한 T / 구간 폭 확인이 보인다.
  - 보간 AO의 점 표현을 검사하며, 원본 `_matchesSegment`와 같은 AP ID 존재 검색을 수행한다고 주장하지 않는다.

## 2. 외곽은 contour 0, 나머지 구멍은 독립적으로 처리한다

- `_storedFillContours`(0x367de4)는 segment의 contourIndex(field_33)로 묶고, 각 목록 안의 저장 순서를 유지한다.
- buildFrameFillRegionPath(0x415a84)는 contour 0 경로를 먼저 만든다.
  - 외곽 builder가 null이면 전체 Path도 null이다(0x415b80–0x415b94).
  - 정상 비음수 contour 번호 범위에서 양수 contour가 없으면 외곽 Path를 그대로 반환한다(0x420b48의 >0 검사 / 0x415ba0).
- 구멍이 있으면 각 구멍을 별도 Path로 만든다. builder가 null인 구멍은 빼기 목록에 넣지 않고 계속한다(0x415d0c/0x415d94).
- buildInterpolatedFrameFillRegionPath(0x794cd4)도 외곽 실패는 null이고, 구멍 실패는 기존 결과 유지다(0x794e30/0x794f24).

별도 데이터 정리 함수:
- FrameFillRegion.pruneInvalidContoursForObjectsById(0x3675ec)는 외곽이 구조적으로 부적합하면 null이고, 부적합 contour의 segments를 필터하는 경로가 있다.
- 변경이 없으면 기존 FR, 변경 시 ID·색을 보존한 새 FR을 반환하는 경로를 확인했다.
- 이 함수의 모든 편집·import 호출 범위까지 이번에 추적하지는 않았다.
- 렌더 중 null 생략과 저장 상태 정리 함수를 혼동하지 않는다.

## 3. evenOdd와 구멍 차감은 두 단계

**contour 내부 판정**
- 원본·보간 contour builder 모두 NativePath fillType 인수 1을 설정한다(0x41d664/0x79503c).
- 공식 Flutter 선언 순서에서 1은 evenOdd다. 즉 개별 contour의 내부 판정은 경계 교차 홀짝 규칙이다.
- 이는 winding 방향만으로 구멍을 판정하는 nonZero 규칙과 다르다.

**구멍 결합**
- 구멍 결합은 **PathOperation.difference**다.
- 원본 buildFrameFillRegionPath의 캐시 miss closure(0x4205c8)와 보간 builder에서 op 인수 0을 전달한다(0x420734/0x420738, 0x794f10/0x794f14). 이 앱 PP의 enum index 0 이름도 difference다.
- 인수는 새 결과 Path / 현재 외곽 결과 / 이번 구멍 Path / operation으로 연결된다. 성공 결과를 다음 구멍의 외곽 입력으로 갱신한다.
- 따라서 확인한 경로는 `((외곽 − 구멍1) − 구멍2)…`다.
- 모든 contour를 한 Path에 더하고 evenOdd를 한 번만 적용하는 모델로 바꾸면 안 된다.
- 연산에서 도출한 결과(신규 실물 영상 시험은 아님):
  - 여러 구멍이 겹쳐도 겹친 곳이 자동으로 채워지는 XOR 효과가 없다.
  - 외곽 밖 구멍이 별도 채움 영역을 추가하는 방식도 아니다.

**캐시와 실패 처리**
- 원본 경로는 양수 contour가 있을 때 `_HoledFillPaths.resolve`(0x415e70)의 geometry steps 키 캐시를 사용한다. cache miss에서 위 difference를 계산하고, 반환 시 Path.from 복사 경로가 있다(0x415fc0).
- 보간 builder는 읽은 함수 안에서 직접 difference를 수행한다.
- 캐시 전체 키 정확성·용량·모든 무효화는 미확인이다.
- Native Path combine의 실패값은 StateError('Path.combine() failed…NaN…') 경로로 연결된다(0x420764/0x794f44).
- 구멍 builder가 null인 경우의 생략과 native op 실패의 예외는 다른 처리다. 임의의 모든 실패를 "해당 구멍만 무시"로 합치면 안 된다.

## 4. 경계 조립은 간격을 연결하고 마지막을 닫는다

- `_buildFrameFillContourPath`(0x41d5c0)와 `_buildInterpolatedFrameFillContourPath`(0x794f9c)는 구조 검사 후 저장된 edge들을 순회한다.
  - 첫 시작점 moveTo, 이어 필요한 lineTo / arcTo / quadraticBezierTo를 호출한다.
  - 완전 원 single Kind는 별도 circle builder 경로다.
- 현재 끝점과 다음 segment 시작점 사이 거리가 0.1보다 크면 시작점까지 연결 lineTo를 추가한다(예: 0x41de34/0x795354).
- 마지막 끝점과 첫 시작점도 같은 거리 검사 후 필요한 lineTo, 그 뒤 close를 호출한다(0x41eb38/0x41eb98/0x41eca0, 0x7958b0/0x79590c/0x79594c).
- 임계 0.1은 TranslateToScreen 계열 이후 이 Path 입력 좌표의 거리다. 최종 영상의 0.1 물리 픽셀로 확정하지 않는다.

해석:
- 틈이 있다는 이유만으로 구조 검사가 false라고 추정하면 안 된다.
- 경계 순서가 원하는 둘레 순서와 다르면 연결선 때문에 다른 형상이 될 수 있다.
- 이것은 좌표 순으로 가장 좋은 폐곡선을 찾는 전체 자동 정렬 알고리즘이 아니다.
- 자기 교차·면적 0·곡선 단일 contour의 전체 기하 유효성은 이번 조건만으로 보장되지 않는다.

## 5. 부분 구간의 처리도 primitive마다 다르다

- **직선** `_resolveLineSegmentPoints`(0x41ffc0): 첫 2점의 TranslateToScreen 결과에서 Offset.lerp(T1), lerp(T2)를 계산한다(0x42013c/0x420158). 이 함수 안에 T를 0–1로 clamp하는 호출은 없다.
- **이차 곡선** `_resolveQuadraticSegmentPoints`(0x41f248):
  - 첫 3점의 화면 좌표를 만들고 T1/T2를 0–1로 clamp한다.
  - clamp 뒤 구간 폭이 1e-6 이하면 null.
  - min/max로 subsegment를 추출하고, 원래 T 방향이 반대면 끝점을 바꾼다(0x41f4d8–0x41f5b0).
- `_extractQuadraticSubsegment`(0x41f600)는 `_splitQuadraticBezier`를 연결해 부분 곡선을 추출한다. 원래 제어점을 유지한 채 끝점만 이동하는 식이 아니다. 전체 베지어 수치 정밀도 재현은 미검증.
- **원형 AO의 edge/arc** `_resolveCircleArc`(0x41f9ac):
  - 두 점의 중심과 거리/2로 원 반경을 구한다.
  - 중심에서 첫 점으로 향하는 기준각(P0−center의 atan2)에 2π×T1 / 2π×T2를 더한다(0x41fb24/0x41fb60/0x41fb70).
  - radius 양수·유한 T 검사가 있으며, 읽은 함수 안에 T clamp 호출은 없다.
  - 완전 원 Kind의 별도 전체 원 Path와 혼동하지 않는다.

- 이 차이 때문에 "모든 부분 경계 T는 그대로 쓰기" 또는 "항상 0–1로 잘라 쓰기"를 공통 규칙으로 사용하면 안 된다.
- ObjectScale / Canvas / DPR이 만드는 최종 좌표는 (작성 당시) 다음 공급 추적 대상이다.

## 검증과 다음 행동

**검증**
- 새 명령 표본 14개(구멍 operation / Path fillType / 구간 / 연결 거리 / 부분 곡선 호출)를 캐시 ELF PT_LOAD와 Capstone으로 대조해 모두 통과했다.
- 집계: AOT-FILL-PATH-AUDIT-2026-10-15.json
- 이전 보간 14개 시험을 재실행한 것이 아니다.
- 전체 함수의 모든 분기·실물 렌더·동등성 증명이 아니다.
- 문서 작업이라 기존 unit/probe 생성 시험 반복 없음.

**다음 (작성 당시)**
- TranslateToScreenX/Y, `_screenOffsets`와 interpolated transform → OBJECT/PREVIEW Paint baseStrokeWidth B와 ResolveDevicePixelRatio 공급 → 화면·영상 shader-raster-fallback dispatch.
- `_HoledFillPaths` 키·무효화와 영역 레이어 의미 확인도 유지한다.
- 휴대폰 추가 작업·설치·라이선스 변경 요청 없음.

**근거 캐시**
- **근거 캐시(현재 환경):** `/root/sfa-cache/extracted`의 `blutter_out/asm/sfa/original_port/sequences/frame_fill_region.dart`, `blutter_out/pp.txt`, `evidence/libapp.so`, `python/`(Capstone·pyelftools). Setup script가 복구한다.
- 현재 환경에 없는 것: 작성 당시 새 검사(`validate_path.py`, `path-validation.json`). 작성 당시 이전 환경 경로는 [원문](history/before-current-facts-2026-10-16/AOT-FILL-PATH-TRACE-2026-10-15.md)에 보존했다.
- 공개는 직접 작성한 보고서·집계만.

**공식 enum 근거**
- https://api.flutter.dev/flutter/dart-ui/PathFillType.html
- https://api.flutter.dev/flutter/dart-ui/PathOperation.html
- 문서의 enum 의미와 이 앱의 호출 인수·PP 메타데이터를 연결한 정적 해석이다.
