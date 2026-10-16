# Flutter 전용 분석 도구 두 가지의 실제 시도

## 결과

- **Blutter는 스파 51.0.0의 AOT를 실제로 읽고 추출에 성공했다.**
- **reFlutter는 스냅샷을 인식했으나, 해당 덤프 엔진 배포가 없어 수정 APK 제작에 실패했다.**
- Blutter의 출력은 원래 Dart 소스 복원이 아니라 메타데이터와 함수별 어셈블리다. 추출 성공을 전체 알고리즘 해석 완료로 세지 않는다.
- 입력 체크섬·도구 커밋·수량·검증: [FLUTTER-TOOLS-AUDIT-2026-10-15.json](FLUTTER-TOOLS-AUDIT-2026-10-15.json)
- 제공 APK·공유 라이브러리·어셈블리·객체 풀·후킹 템플릿은 공개 저장소에 올리지 않았다.
- 이번 원본 분석을 위해 사용자에게 재출력·추가 작품·개발자 문의를 요청하지 않았다.

## 입력과 환경

- 기존 캐시의 ARM64 분할 APK에서 libapp.so / libflutter.so를 추출했다. libapp SHA는 기존 기록과 일치한다.
- 도구로 확인: Dart 3.12.0, 스냅샷 41be3daaabd524b8aa7423bc24584957, android/arm64/compressed-pointers/product.
- Ubuntu 24.04 / g++ 13.3.
  - CMake/Ninja/Python 모듈을 작업 폴더 venv에 설치했다.
  - ICU74 헤더와 기존 시스템 ICU74 라이브러리, Python wheel에 포함된 실물 Capstone 라이브러리·헤더를 사용했다.
- Blutter의 로컬 변경은 CMake의 Capstone 검색 경로와 Ninja 병렬 작업 수 2뿐이다.
  - 도구의 AOT 계산·해석 알고리즘에 기능 패치를 가하지 않았다.
  - Blutter가 원래 수행하는 Dart VM 분석용 패치는 그대로 사용했다.

## 1. Blutter

공식 저장소: [worawit/blutter](https://github.com/worawit/blutter). 실제 소스 커밋은 집계 JSON 참조.

1. 버전 검출 성공.
2. 해당 Dart SDK를 받아 분석용 Dart VM과 Blutter 빌드 성공.
3. 첫 자동 실행은 Capstone SONAME 라이브러리 탐색 문제로 실행되지 않았다. 실제 라이브러리로의 로컬 심볼릭 링크와 LD_LIBRARY_PATH 설정 후 재실행했다.
4. libapp 로드 → 애플리케이션 분석 → 객체 풀 덤프 → 어셈블리 → 후킹 템플릿 생성, 종료 코드 0.

출력:
- 671 파일 / 86,508,012 바이트. 그중 asm 파일 666개, 주소·크기 선언 블록 12,752개.
- 선언 블록 수가 독립 함수나 완전히 복원된 함수의 개수와 같다고 가정하지 않는다.
- 같은 버전의 빌드·추출은 다시 실행할 필요가 없으며 캐시를 재사용한다.

### 우선 추적할 함수 위치

- 아래는 Blutter가 표시한 코드 주소다.
- 이전 문서의 **ELF 문자열 바이트 오프셋과 다르다.**
- ASLR 런타임 절대 주소로 사용하지 않는다.

| 파일(asm/sfa 아래) | 함수 | 코드 주소 |
|---|---|---|
| original_port/activities/import_animation_activity.dart | importSequenceXmlText | 0x505c44 |
| 같은 파일 | _ImportSequenceXmlHandler 생성자 | 0x50e174 |
| original_port/data/android_database_recovery.dart | _importSequence | 0x34e224 |
| main.dart | compareDrawOrder closure | 0x5b9c54 |
| main.dart | resolveDrawOrder closure | 0x5b9d5c |
| original_port/data/data_access.dart | UpdateAnimationObjectDrawOrder | 0x50ce88 |
| original_port/sequences/tween_link.dart | resolveTweenLinks | 0x632d74 |
| original_port/sequences/frame.dart | _buildFillRegionInterpolationSegmentKey | 0x632930 |
| original_port/sequences/frame.dart | FrameDrawPlan.drawUnit | 0x414ee8 |
| original_port/sequences/frame_fill_region.dart | drawFrameFillRegionsForLayer | 0x41548c |

- glow_shader.dart, frame_fill_region.dart, fill_path_clipping.dart, perspective_overlay.dart, frame.dart, animation_object.dart도 추출됐다.
- 이름 발견만으로 알고리즘 해석 완료를 선언하지 않는다.

검증:
- 4개 코드 위치를 ELF PT_LOAD 매핑으로 원래 libapp의 실제 바이트에 대응시키고, 독립 Capstone 역어셈블러의 명령 종류와 비교했다.
- drawUnit 내 0x414f78에서 채우기 함수 0x41548c를 호출하는 대상 주소도 실제 바이트와 일치했다.
- 추출 주소의 표본 검증이며, 전체 12,752 블록의 정확성을 보장하는 검사는 아니다.

첫 한정 관찰:
- drawUnit에는 composite glow 호출 분기와 채우기 호출로 진행하는 분기가 있다.
- 실제 영상의 함수 경로나 plan의 unit 정렬 규칙은 아직 끝까지 추적하지 않았다.
- 01의 겹침 규칙을 짧은 분기만으로 확정하지 않는다.

## 2. reFlutter

공식: [Impact-I/reFlutter](https://github.com/Impact-I/reFlutter). clone한 0.9.8을 실제로 설치하고 ARM64 분할 APK에 dump mode `-p -n`을 실행했다.

- 스냅샷 인식 성공. enginehash.csv에는 같은 hash가 Flutter 3.44 계열로 기록돼 있다. **Dart 3.12와 Flutter 3.12를 혼동하지 않는다.**
- 덤프 엔진 다운로드 실패, 종료 코드 1.
  - 대상 release tag `android-v3-41be3daaabd524b8aa7423bc24584957`을 GitHub REST API로도 조회해 404를 확인했다.
  - 버전 인식 실패나 사용자 APK 불량으로 판정하지 않는다.
- `-b`의 commit 해결 모드는 성공하지만, 그것만으로 엔진 빌드·덤프 성공이 아니다.
  - 같은 hash의 행이 여러 개 있고 첫 후보는 beta engine commit이다.
  - 자체 빌드 시 실물 engine revision·호환성 확인이 필요하다.
- 제공된 local-release의 v3/build-only도 시도했지만 brew 부재 guard에서 종료 1. 스크립트는 macOS용 환경을 요구한다.
  - depot_tools는 받아 bootstrap 후 gclient 응답까지 확인했다.
  - Linux 수동 engine checkout/sync/GN 컴파일까지는 진행하지 않았다.
- 당시 환경에 adb/Android emulator가 없어, 재패키징해도 실제 앱 실행·JSONL dump 검증에는 실행 환경이 필요하다.
  - 분할 APK이므로 engine 분할만 단독 설치 가능한 APK로 취급하지 않는다.
  - 서명·전체 분할 일관성도 미검증이다.

결과:
- **이번에는 변경 APK도 dump.dart도 생성되지 않았다.**
- 원본 APK·사용자 설치 앱은 변경하지 않았다.
- reFlutter 소스에서 전용 engine을 만드는 방법은 남지만, 이번에 빌드에 성공했다고 주장하지 않는다.

## 다음의 정확한 행동 (작성 당시)

- 성공한 Blutter 출력에서 필요한 함수만 읽는다: XML importer의 DrawOrder/ObjectScale 가져오기·갱신 → FrameDrawPlan의 unit 정렬·FR 위치 → glow uniform·합성 → FrameInterpolationPlan / TweenLink 대응.
- 전체 재덤프·원본 영상 재분석을 반복하지 않는다.
- reFlutter custom engine build와 Android 실행 환경은 별도 미완 항목으로 남긴다.

**분석 도구·추출물 위치**
- 현재 환경: `/root/sfa-cache/extracted`에 `blutter_out/` 추출물, `bin/` Blutter 실행 파일, `lib/` 의존 라이브러리, `python/` Capstone·pyelftools, `tool-source/`, `evidence/`(libapp.so, libflutter.so, glow.frag)가 있다. Setup script가 복구한다.
- 실행 시 `LD_LIBRARY_PATH=<복구경로>/lib:<복구경로>/python/capstone/lib`, Python 디코더는 `PYTHONPATH=<복구경로>/python`(캐시의 RESTORE-KO.txt).
- 작성 당시 이전 환경에는 `blutter_out/`, `blutter/bin/`, `venv/`·`depsroot/` 의존(실행 시 `LD_LIBRARY_PATH=depsroot/lib`), `reFlutter/` 소스, `input/arm64-v8a/` 입력 라이브러리 2개가 있었다. 경로는 [원문](history/before-current-facts-2026-10-16/FLUTTER-TOOLS-RESULTS-2026-10-15.md)에 보존했다.
- reFlutter 소스는 현재 환경에 없다.

기타:
- 이번은 문서·집계만 공개.
- 고정 예측 변경·File-2 최적화는 계속 보류.
- 학습·AI 연결은 2026-10-16 사용자 결정으로 개인용 범위에서 진행한다(AGENTS.md "학습 단계 결정", [AI-PIPELINE-PLAN](AI-PIPELINE-PLAN-2026-10-16.md)).
- 기존 SFA·영상·22개 생성 검사 재실행 없음. 새로 4개 명령 위치 검증을 실행했다.
