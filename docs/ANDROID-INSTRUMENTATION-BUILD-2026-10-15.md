# 별도 Android 시작 계측 패키지 제작 — 2026-10-15

## 결과와 검증 범위

별도 테스트 패키지 `com.twoapple08.sfa.instrument`, 표시명 `SFA Instrument Test`를 제작했다. base·arm64_v8a·ja·ko·xxhdpi 5개 APK를 동일한 전용 로컬 테스트 키로 서명했다. 최종 5개 모두 uber-apk-signer의 정렬 검사 및 v1/v2/v3 서명 검증을 통과했다. 실기기 설치/시작/Gadget 로그는 아직 검증하지 않았다. 완성 렌더러/애니메이팅 AI 또는 원본과 동등한 앱으로 판단하지 않는다.

공식 GitHub release API 및 release asset 다운로드 성공. Apktool 3.0.3, uber-apk-signer 1.3.0, Frida Gadget 17.23.3/android-arm64를 확보했다. 다운로드 크기를 API와 대조했고 SHA-256을 기록했다. Apktool/Gadget은 API 제공 digest도 일치했다. signer API에는 digest가 없어 로컬 해시와 크기만 기록했다. 상세 수치는 ANDROID-INSTRUMENTATION-BUILD-AUDIT-2026-10-15.json.

## 변경과 보존

- 원본 캐시를 재사용했다. 사용자 Termux 설치·페어링·기기 정보 조회·00–05시험·JADX/Blutter 전체 분석은 반복하지 않았다.
- base와 4개 split의 manifest package를 변경했다. provider authorities 5개와 앱 자체 signature permission 선언/사용을 별도 이름으로 수정했다. 기존 fully qualified component 클래스명은 유지했다. 클래스명 전체 치환을 하지 않았다.
- 원래 application 클래스의 생성자에서 `System.loadLibrary("sfagadget")` 호출을 추가했다. 기존 attachBaseContext 라이선스 검사는 보존했으며 우회하지 않았다. 새 패키지/서명 때문에 시작이 차단될 가능성은 실제 실행으로 판단해야 한다. Firebase/로그인/결제/광고 동작은 시험 범위가 아니다.
- `extractNativeLibs=true`와 Gadget/script/config를 ARM64 split에 적용했다. script 경로는 Gadget과 같은 추출 디렉터리의 `libsfaprobe.so`. config는 `libsfagadget.config.so`이고 interaction=script, runtime=qjs다. TCP listen 서버를 열지 않는다. Java bridge는 사용하지 않는다.
- script는 `__android_log_write`로 SFAProbe 태그에 init stage/architecture 및 libapp.so/libflutter.so/libsfagadget.so의 모듈명·베이스주소·크기를 기록한다. Process.attachModuleObserver를 사용하며 Dart 주소 후킹/인수 해석/파일·통신 내용 수집은 없다.
- base에서는 manifest/classes2.dex/서명만 바뀌었다. classes.dex/classes3.dex, 원래 assets/res/resources.arsc는 원본 ZIP 항목으로 보존했다. 모든 split의 원래 lib/res/resources.arsc도 바이트 대조했다. 총 242개 보호 항목 대조 통과. libapp.so/libflutter.so는 변경하지 않았다.
- 원래 libapp/libflutter ELF PT_LOAD 정렬값은 65536, Gadget은 16384다. 실제 Android 로더 실행 통과를 의미하지 않는다.

Apktool의 raw-resource 빌드가 기존 res 파일을 누락시키는 문제가 최종 비교 전에 발견됐다. 최종 base는 원본 ZIP에서 manifest와 수정 classes2.dex만 교체하여 복구했고, 복구본을 재서명/대조했다. 누락된 중간 산출물은 전달하지 않는다. AAPT2로 최종 5개 manifest package/version/split을 확인하고 base label/authorities/permission/extractNativeLibs/application을 검증했다. 클래스 참조 및 SDK 설정은 보존했지만 모든 런타임 고정 패키지 참조의 동작을 검증한 것은 아니다.

## 비공개 전달과 다음 단계

전달 묶음: SFA-Instrument-Startup-2026-10-15.zip. APK 5개, 한국어 README, install-start.sh를 포함한다. 원본 기반 APK·역컴파일물·키는 공개 레포에 올리지 않는다. 묶음 비공개 저장 성공: libfile_a9e9671bcd3c8191b95a54915af9aa6d, 29,242,126바이트. 사용자 수령/설치 결과는 아직 없다. 서명 키는 private/instrument-build/sfa-test.jks에 보관해 향후 같은 테스트 앱 갱신에 재사용한다.

사용자는 중요한 작품의 앱 밖 SFA 백업 후 묶음을 압축 해제하고 `sh install-start.sh` 실행. 스크립트는 BACKUP 입력을 요구하며, 기존 ADB 연결로 테스트 APK 5개를 --user 0 install-multiple 설치한다. 원본 삭제/교체 명령 없음. 테스트 패키지의 기존 MainActivity 클래스에 am start 후 화면 확인을 기다리고 제한된 logcat 500줄(SFAProbe:I, AndroidRuntime:E)을 startup-log.txt로 저장한다. 로그 초기화/원본 작품 시험을 하지 않는다.

정확한 다음: 비공개 파일 전달 성공 확인 → 사용자 백업·설치 결과/빈 화면 시작 여부/startup-log.txt 수령 → 설치 실패·Gadget 로드 실패·라이선스 차단·Flutter 시작 실패를 구분. 시작 성공 뒤에만 필요한 렌더/보간 주소 후킹을 검토한다. 사용자 로그가 없는데 다음 주소 후킹 단계로 넘어가지 않는다. 연결 오류가 실제 발생할 때만 ADB 복구.

## 캐시와 작업 위치

- 도구: /workspace/scratch/37921248d0d6/private/instrument-tools (tools-audit.json, 다운로드 3개, AAPT2)
- 제작: /workspace/scratch/37921248d0d6/private/instrument-build (patch_axml.py, prepare.py, repack_base.py, verify.py, startup.js, 키, 최종 검사 로그, delivery/)
- 최종 서명 검사: verify-final.log, validation.json. 이 중간 파일은 공개하지 않는다.
- 전달 ZIP: /workspace/scratch/25b8ca176661/output/SFA-Instrument-Startup-2026-10-15.zip
- 문서 worktree: /workspace/scratch/25b8ca176661/AI-sfa, 시작 원격 490b35b. 이전 로컬 변경은 그대로 유지.

문서/집계 변경만 레포에 반영한다. 기존 unit/probe 생성 시험은 문서 변경으로 반복하지 않았다. 이번 제작의 서명·manifest·원본 항목 대조는 별도 실행했다.

공식 근거: https://github.com/iBotPeaches/Apktool/releases/tag/v3.0.3 , https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0 , https://github.com/frida/frida/releases/tag/17.23.3 , https://frida.re/docs/gadget/ , https://frida.re/docs/javascript-api/ .
