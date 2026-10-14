# 51.0.0 추가 정적 근거 — 2026-10-14

## 자료와 해석 범위

제공된 APKS의 SHA-256이 기존 기록과 일치함을 확인했다. 아래는 ARM64 Flutter AOT 바이너리의 문자열·SQL 스키마 관찰이다. 함수 호출 흐름이나 수학식을 확인한 결과가 아니며 실제 앱 검증으로 승격하지 않는다.

- APKS SHA-256: `c1c39e031f0fc4a904755f08c45406e4fd3c894dafe1e506c0c0ac7dd78eff76`
- 대상: `split_config.arm64_v8a.apk` 내부 `lib/arm64-v8a/libapp.so`
- libapp.so SHA-256: `35ce3936f08e5da6caf08e0f3d4c80e0c81777475ac4f682c66f9f4a00a32c1f`
- 위치는 ELF 파일 시작부터의 바이트 오프셋이다. 코드 주소나 호출 위치가 아니다.

## 근거와 미확인 항목

| ID | 위치/검색 표식 | 직접 관찰 | 미확인 |
|---|---|---|---|
| APK-LAYER-01 | `0x8243d`, layer_def 생성 SQL | frame_id, layer_index, name, is_visible, is_locked. 표시 기본값 1, 잠금 기본값 0 | UI 적용 범위, XML importer 대응, 영상 출력 적용 |
| APK-LINK-01 | `0xa8f90`, frame_tween_link 생성 SQL | frame_id, animation_object_id, from_animation_object_id. 기본 키는 (frame_id, animation_object_id) | 링크의 시간 방향·XML ID/From 대응·삭제 정책. DB 도형당 한 행이라는 구조를 UI 전체 제약으로 확대하지 않는다 |
| APK-LINK-02 | `0x772c8`, appendTweenLinksXml; `0x2b058`, resolveTweenLinks | XML 작성/링크 해결 관련 이름 | 호출 관계, 렌더러 적용, 알고리즘 |
| APK-FILL-01 | `0x49646`, frame_fill_region_segment 생성 SQL | segment_index/kind, 도형 ID, 시작·끝 점, 시작·끝 T, contour_index. contour_index 기본값 0 | Kind 전체 의미, 윤곽 방향/구멍 규칙, XML Contour 대응, 채우기 보간 |
| APK-GROUP-01 | `0xa2449`, all-group-this-layer; `0x25c94`, all-group-all-layers | 현재/전체 레이어 구별 문자열과 AllGroupScopePanel 이름 | 실제 한국어 메뉴, 잠긴/숨긴 레이어 포함 여부, 변형 기준점 |
| APK-PERSP-01 | `0x29047`, perspective-bend; `0xa1e7e`, perspective-lasso | 두 표식과 PerspectiveKindPanel, 선택/격자/드래그 함수 이름 | 전체 옵션 목록, 수학식, 퇴화 사각형 처리, 연결점 전파 |
| APK-FLAGS-01 | `0x3c76d`, raw_flags 갱신 SQL | NULL 행을 selectable과 anchor_point_type의 비트 OR로 채우는 SQL 문자열 | 전체 비트 정의·그룹 비트·현재 실행 여부·XML 변환 |
| APK-EDIT-01 | `0xa2272`, frame_base_moved_points 생성 SQL | frame_id 기본 키와 data BLOB, 조회/쓰기/삭제 SQL | BLOB 구조·사용 기능·SFA 저장 여부. 이름만으로 기준점 이동 기능이라고 확정하지 않는다 |

레이어 DB가 프레임 단위라는 사실은 13_layers 시험의 가정을 뒷받침하지만 앱 성공의 증거는 아니다. 여러 contour 저장 필드만으로 구멍 채우기 동작을 확정하지 않는다.

## 재확인과 다음 단계

같은 APKS를 압축 해제하고 ARM64 분할의 libapp.so를 추출해 체크섬과 바이트 검색 위치를 비교한다. part-N 이름은 추출 순서에 따라 달라지므로 분할 이름/내용으로 찾는다. APK·바이너리·전체 문자열 덤프는 공개 저장소에 넣지 않는다.

현재 환경에는 jadx/adb/Flutter 런타임이 없어 추가 Android 역컴파일 및 앱 실행을 수행하지 않았다. 기존 네이티브 분석은 [NATIVE-TWEEN-FINDINGS.md](NATIVE-TWEEN-FINDINGS.md)의 이전 근거로 유지한다.

먼저 v1 합본을 (트위닝 FPS, 재생 FPS)=(24,24)로 출력해 저장 상태 수용/표시를 확인한다. 이 결과 전에는 그룹·원근·구멍·수동 링크의 조작 실험을 일괄 요청하지 않는다. (24,24)는 추가 보간 검증이 아니다.
