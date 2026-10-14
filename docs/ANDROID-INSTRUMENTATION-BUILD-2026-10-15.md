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

## 실기기 시작 계측 결과 — 2026-10-15 03:40 KST

사용자 제공 logcat에서 같은 PID12555의 SFAProbe 기록을 확인했다. 03:40:35.588 gadget-init(stage=early, arch=arm64), 03:40:35.632 libflutter.so 로드(size11788288), 03:40:35.660 libapp.so 로드(size8065024). ASLR 주소는 공개 문서에 재기록하지 않는다. 이는 Gadget script와 모듈 로드 성공이며 렌더/보간 실행이나 편집 화면 정상 작동의 증거가 아니다.

사용자 스크린샷에 SFA Instrument Test와 Google Play 확인 오류 안내가 나타났고, 사용자는 오류와 앱 화면이 함께 뜨며 오류 창을 닫으면 앱도 종료된다고 확인했다. 따라서 시작 준비 단계까지만 통과, 지속적인 앱 사용은 차단된 상태다. 보존된 라이선스 검사와 관련될 가능성이 있지만 정확한 오류 코드/실패 분기는 아직 확인하지 않았다. 제공한 제한 태그 로그에는 이를 특정하는 기록이 없다. 다른 PID12716의 heap tagging 오류를 테스트 앱 PID12555의 종료 원인으로 단정하지 않는다. display property 경고만으로 로더 실패도 판단하지 않는다.

초기 startup-log.txt는 빈 파일이었다. 수집을 시작 전에 켠 후 재시작한 startup-debug-log.txt에서 위 성공 기록을 확보했다. 최근500줄/2태그만 사후 추출하는 기존 install-start.sh는 시작 로그를 놓칠 수 있으므로 동일 방식 재시험 금지. 사용자 Termux 저장공간 권한은 termux-setup-storage 후 접근/로그 저장 성공. 연결/설치/페어링 재요청 없음. install-start.sh의 BACKUP 응답 자체는 대화에 없으므로 백업 완료를 별도 확정하지 않는다.

정확한 다음: 현재 캐시의 LicenseClient와 오류 안내 호출 경로만 제한적으로 읽어 실패 분기/증거 확보 가능성을 확인한다. 사용자 재설치/Play설정 변경/추가 시작 시험은 요청하지 않는다. 라이선스 검사 변경이나 우회는 이번 결과 처리에서 하지 않는다. 편집 기능을 사용할 실행 경로가 확보되기 전 렌더/보간 Hook 확장은 보류하고, 기존 AOT의 미확인 planner/glow/FR 규칙 추적을 진행할 수 있다. 이 결과는 위 제작 보고서의 '실물 시작/로그 없음'과 다음 설치 요청을 대체한다.

기존 Java 캐시 한정 확인: LicenseActivity.showErrorDialog의 안내 문구가 사용자 스크린샷과 일치하며 Close는 closeApp을 호출한다. LicenseClient.handleError는 LicenseClient 태그 ERROR 로그에 검사 예외를 기록한 뒤 상태에 따라 오류 Activity를 시작한다. 실제 예외/오류코드는 아직 미수령. 다음 최소 요청은 재시작 없이 `adb logcat -d -v threadtime -s LicenseClient:V LicenseActivity:V`로 현재 버퍼의 검사 로그만 읽는 것이다. 버퍼가 비었으면 같은 시험을 무조건 반복하지 않는다. 정적 코드 존재와 이번 실행 분기 확정을 구분한다.

## 실제 검사 예외 수령 — 2026-10-15 03:44 KST

사용자 기존 버퍼에서 03:38/03:40/03:41의 세 PID가 공통으로 local installer check의 기존 패키지 com.sG.stickfighter.activities 조회 NameNotFoundException, main licensing service 연결/요청 성공, 응답 코드4 → Unexpected response code4 예외를 보였다. 특히 PID12555는 앞선 Gadget/Flutter 모듈 로그와 일치한다. 원본 앱 제거를 의미하지 않는다. 별도 앱의 package visibility/조회 주체 차이 등이 가능하며 실제 원인은 아직 구분하지 않았다.

기존 캐시 한정검사에서 LicenseClient.packageName은 원래 패키지 상수이고, local getPackageInfo/getInstallSourceInfo와 V2 라이선스 요청에 공통으로 사용됨을 확인했다. manifest 변경이 이 상수를 바꾸지 않았다. processResponse는 0=검사응답검증,2=paywall,3=invalid package 처리와 나머지 예외 경로를 가지며 코드4는 나머지 경로다. **이 앱 코드만으로 서비스 코드4의 정확한 의미나 서버측 원인을 정의할 수 없다. 코드3과 혼동하여 invalid package 응답으로 단정하지 않는다.**

Gadget/ELF 모듈 로드 성공과 라이선스에 의한 지속 실행 차단을 분리한다. Play 서비스 비활성/미연결은 이번 로그와 맞지 않으므로 Play 설정변경/재설치/페어링은 요청하지 않는다. 기존 패키지명을 테스트 이름으로 단순 치환하거나 queries 추가만으로 정식 검사 성공을 보장하지 않는다. 검사상수/응답/종료경로 변경 또는 우회는 미실시. 이번 원인분류에 필요한 최소 로그 수령은 완료됐으므로 추가 시작시험을 요청하지 않는다.

다음 작업은 사용가능한 실행경로 설계 전 기존 AOT의 미확인 GetAnimationObjects 공급/그룹방문순서 및 TryDrawGlowWithShader paint/blend의 한정 정적추적을 재개한다. 라이선스 없는 정상 편집 실행을 확보했다고 주장하지 않는다. 공개 저장소에는 이 직접작성 요약만, 전체 로그/역컴파일소스/주소/원본은 올리지 않는다.
