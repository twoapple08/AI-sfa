# Android 실기기 계측 준비 인수인계 — 2026-10-15

## 완료

**기기·앱 확인**
- 사용자 휴대폰 한 대의 Termux/무선 ADB 연결을 확인했다.
- Android 16 / SDK 36, arm64-v8a를 포함한 ABI.
- 스파 com.sG.stickfighter.activities 51.0.0(versionCode 51000), minSdk 24, targetSdk 36.
- user 0에 설치된 분할 5개(base, arm64_v8a, ja, ko, xxhdpi)를 사용자 명령 결과로 확인했다.
- DEBUGGABLE은 출력 flags에 없다.
- 다른 기기는 사용 불가, Wi-Fi 사용, 루팅 X.

**연결 과정**
- 초기 adb는 C++ 심볼 누락으로 실행에 실패했다. 안내에서 `pkg upgrade`가 빠졌던 것을 정정했다.
- 이후 사용자가 adb shell의 기기·앱 정보 결과를 제공했으므로 실행 가능 상태를 확인했다.
- 전체 사용자 패키지 목록 조회 중 user 150 권한 오류는 user 0 지정으로 회피했다.
- 연결 준비를 다시 요청하지 않는다.

**이전 완료 작업**
- 앞서 완료한 AOT 추적과 11개 새 명령 검증은 [AOT-PATH-TRACE-2026-10-15.md](AOT-PATH-TRACE-2026-10-15.md)에 있다.
- 그 자료와 00–05 입력은 다시 분석하지 않는다.

## 제안 상태와 미완

**계획 단계(구현·실행 성공 아님)**
- reFlutter의 해당 dump 엔진 404는 기존 사실이다.
- 자체 엔진 빌드를 진행하지 않고, 기존 Flutter 엔진에 Frida Gadget을 추가하는 방법을 검토하기 시작했다.
- script 모드로 자율 계측이 가능하다는 공식 문서를 확인했다. Frida 17의 Java bridge는 별도 번들이 필요하다는 것도 확인했다.
- 최초 스크립트에서 Java를 쓰지 않는 최소 모듈·시작 기록을 검토할 수 있다.

**미완**
- 계측 APK 없음, 서명·분할 검증 없음, 사용자 전달 파일 없음, 실제 계측 로그 없음.
- APKTool / uber-apk-signer / ARM64 Gadget의 공식 최신 release API·다운로드를 시도한 프로세스 39459는 재개 시 존재하지 않았다. 출력 파일도 없다. 실패 원인을 네트워크 차단 등으로 확정하지 않는다.
- `/workspace/scratch/37921248d0d6/private/instrument-tools`는 실물 확인 결과 비어 있었다.
- java는 PATH에 있고, apktool/apksigner/aapt2는 PATH에서 찾지 못했다. 필요한 도구를 새로 준비해야 한다. Blutter/reFlutter를 재설치하라는 뜻이 아니다.

## 다음 실행 단위

1. 공식 도구를 받을 경로의 응답부터 짧은 timeout으로 확인한다. 버전·파일 크기·체크섬을 저장한다. 기존 빈 다운로드 프로세스를 재폴링하지 않는다.
2. 기존 base.apk에서 다음만 검사한다: manifest, 별도 패키지 설치에 영향을 주는 provider authorities, custom permissions, component 이름, resource/package 고정 참조. 전체 JADX 재실행은 금지.
3. 별도 패키지의 시작 확인용 최소 계측 APK와 필요한 분할을 제작하고, 같은 키로 서명하고, 정적으로 검증한다. 원래 libapp/libflutter 보존 여부를 확인한다. 임의 패키지명 치환만으로 완료 판정하지 않는다.
4. 처음에는 Gadget 시작·모듈 기록만 검증해, Hook 주소·압축 포인터 해석 오류와 앱 재패키징 오류를 분리한다. Dart 호출 규약을 일반 C 인수로 오독하지 않는다.
5. APK와 원본 기반 파일은 공개 GitHub에 올리지 않는다. 사용자에게 전달할 때는 Library 경로를 쓴다. 저장 전 현재 스킬·도구 가용성을 확인한다. repo에는 직접 작성한 도구·해석·집계만 둔다.
6. 사용자에게는 설치·시작 결과와 필요한 최소 로그만 요청한다. 원본 앱 삭제·덮어쓰기는 금지한다. 패키지 변경으로 로그인·결제 등의 작동이 보장되지 않으며, 그 기능을 시험 목표로 삼지 않는다.
7. 시작에 성공한 뒤 FrameDrawPlan / DrawGlowEffect / FrameInterpolationPlan의 필요한 주소만 추적한다. 아직 기존 앱과 출력·성능이 같다는 것이 검증된 것은 아니다.

## 캐시·보호 (작성 당시 경로)

- base: `/workspace/scratch/6d77389e706a/evidence/apk/base.apk`
- 제공 분할 모음: `/workspace/scratch/6d77389e706a/evidence/STICK FIGHTER (51.0.0).apks`
- ARM64: `/workspace/scratch/e23c9fd610d3/private/input/split_config.arm64_v8a.apk`
- AOT: `/workspace/scratch/e23c9fd610d3/private/blutter_out/asm/sfa`
- 기존 Java 읽기 캐시: `/workspace/scratch/6d77389e706a/private/decompiled/sources/com/sG/stickfighter/activities/MainActivity.java`
- 사용자 SFA 백업은 안내만 했고 완료 확인은 없다. 실제 설치 전에 확인한다.
- 공개 금지: APK / SFA / 영상 / 역컴파일 소스 / asm.
- 계속 보류: 고정 PREVIDEO 수정, File-2 최적화, 학습·AI 연결.
- 굽힘 기능 없음. FPS = (트위닝, 재생). 레이어 UI는 전체 프레임 제작 보조.
- 정리 메모(2026-10-16): 위 경로는 이전(ChatGPT) 환경의 것이다. 이후 학습·AI 연결은 사용자 결정으로 허용됐다(AGENTS.md "학습 단계 결정").

## 사용량·상시 승인

- 사용자 주간 잔여량은 이 환경에서 직접 조회할 수 없다.
- 대화 횟수 3–4개를 토큰 잔여량으로 환산하거나, 자동 감지가 가능하다고 약속하지 않는다.
- 사용자 알림·작업 체크포인트를 기준으로 HANDOFF와 재개 프롬프트를 갱신한다.
- 직접 작성한 보고서·집계·인수인계는 main 반영이 상시 승인돼 있다. 시스템 자동 검토는 변경할 수 없고, 거부되면 우회하지 않는다.
- 기존 main 847fea3에 AOT 보고서와 승인 지침을 반영했다.

공식 참고:
- https://frida.re/docs/gadget/
- https://frida.re/docs/javascript-api/
- https://github.com/iBotPeaches/Apktool
- https://github.com/patrickfav/uber-apk-signer
