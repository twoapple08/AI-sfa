# Android 실기기 계측 준비 인수인계 — 2026-10-15

## 완료

사용자 휴대폰 한 대의 Termux/무선 ADB 연결을 확인했다. Android16/SDK36, arm64-v8a를 포함한 ABI. 스파 com.sG.stickfighter.activities의51.0.0(versionCode51000),minSdk24,targetSdk36과user0에설치된분할5개(base,arm64_v8a,ja,ko,xxhdpi)를사용자명령결과로확인했다. DEBUGGABLE은출력flags에없다. 다른기기는사용불가,Wi-Fi사용,루팅X.

초기adb는C++심볼누락으로실행실패했다. 안내에서pkg upgrade가빠졌으며이를정정했다. 이후사용자가adb shell의기기/앱정보결과를제공했으므로실행가능상태확인. 전체사용자패키지목록조회중user150권한오류는user0지정으로회피했다. 연결준비를다시요청하지않는다.

앞서완료한AOT추적·11새명령검증은[AOT-PATH-TRACE-2026-10-15.md](AOT-PATH-TRACE-2026-10-15.md). 그자료와00–05입력은다시분석하지않는다.

## 제안 상태와 미완

reFlutter의해당dump엔진404는기존사실. 자체엔진빌드를진행하지않고기존Flutter엔진에Frida Gadget을추가하는방법을검토하기시작했다. 이는계획이며구현/실행성공이아니다. script모드로자율계측이가능한공식문서를확인했고Frida17의Java bridge별도번들필요성도확인했다. 최초스크립트에서Java를쓰지않는최소모듈/시작기록을검토할수있다.

- 계측APK없음,서명/분할검증없음,사용자전달파일없음,실제계측로그없음.
- APKTool/uber-apk-signer/ARM64 Gadget의공식최신release API/다운로드를시도한프로세스39459는재개시존재하지않음. 출력파일도없다. 실패원인을네트워크차단등으로확정하지않는다.
- /workspace/scratch/37921248d0d6/private/instrument-tools는실물확인결과비어있음.
- java는PATH에있고apktool/apksigner/aapt2는PATH에서발견못함. 필요한도구를새로준비해야한다. Blutter/reFlutter를재설치하라는뜻이아니다.

## 다음 실행 단위

1. 공식도구를받을경로의응답부터짧은timeout으로확인. 버전/파일크기/체크섬저장. 기존빈다운로드프로세스재폴링금지.
2. 기존base.apk의manifest와별도패키지설치에영향주는provider authorities,custom permissions,component명,resource/package고정참조만검사. 전체JADX재실행금지.
3. 별도패키지의시작확인용최소계측APK와필요분할을제작·같은키서명·정적검증. 원래libapp/libflutter보존여부확인. 임의패키지명치환만으로완료판정금지.
4. 처음에는Gadget시작/모듈기록만검증해Hook주소/압축포인터해석오류와앱재패키징오류를분리. Dart호출규약을일반C인수로오독하지않는다.
5. APK와원본기반파일은공개GitHub에올리지않고사용자전달시Library 경로사용. 저장전현재스킬/도구가용성확인. repo에는직접작성한도구·해석·집계만.
6. 사용자에게설치·시작결과와필요한최소로그만요청. 원본앱삭제/덮어쓰기금지. 패키지변경으로로그인/결제등작동이보장되지않고그기능을시험목표로삼지않는다.
7. 시작성공뒤FrameDrawPlan/DrawGlowEffect/FrameInterpolationPlan의필요주소만추적. 아직기존앱과출력동일성이나성능동일성이검증된것은아니다.

## 캐시/보호

- base /workspace/scratch/6d77389e706a/evidence/apk/base.apk
- 제공분할모음 /workspace/scratch/6d77389e706a/evidence/STICK FIGHTER (51.0.0).apks
- ARM64 /workspace/scratch/e23c9fd610d3/private/input/split_config.arm64_v8a.apk
- AOT /workspace/scratch/e23c9fd610d3/private/blutter_out/asm/sfa
- 기존Java읽기캐시 /workspace/scratch/6d77389e706a/private/decompiled/sources/com/sG/stickfighter/activities/MainActivity.java
- 사용자SFA백업은안내만했으며완료확인없음. 실제설치전확인.
- 공개금지:APK/SFA/영상/역컴파일소스/asm.계속보류:고정PREVIDEO수정,File-2최적화,학습/AI연결.굽힘기능없음.FPS=(트위닝,재생).레이어UI는전체프레임제작보조.

## 사용량·상시승인

사용자주간잔여량은이환경에서직접조회할수없다. 대화횟수3–4개를토큰잔여량으로환산하거나자동감지가능하다고약속하지않는다. 사용자알림/작업체크포인트기준으로HANDOFF와재개프롬프트를갱신한다.

직접작성한보고서/집계/인수인계는main반영상시승인.시스템자동검토는변경할수없고거부시우회금지.기존main847fea3에AOT보고서와승인지침반영.

공식참고:https://frida.re/docs/gadget/ , https://frida.re/docs/javascript-api/ , https://github.com/iBotPeaches/Apktool , https://github.com/patrickfav/uber-apk-signer .
