# Flutter 전용 분석 도구 두 가지의 실제 시도

## 결과

**Blutter는 스파51.0.0의AOT를 실제로 읽고 추출에 성공했다. reFlutter는 스냅샷을 인식했으나 해당 덤프 엔진 배포가 없어 수정APK제작에 실패했다.** Blutter의출력은 원래Dart소스복원이 아니라 메타데이터와 함수별어셈블리다. 추출성공을 전체알고리즘의해석완료로세지않는다.

입력체크섬/도구커밋/수량/검증은[FLUTTER-TOOLS-AUDIT-2026-10-15.json](FLUTTER-TOOLS-AUDIT-2026-10-15.json). 제공APK/공유라이브러리/어셈블리/객체풀/후킹템플릿은공개저장소에올리지않았다. 이번원본분석을위해사용자에게재출력/추가작품/개발자문의를요청하지않았다.

## 입력과 환경

- 기존캐시의ARM64분할APK에서libapp.so/libflutter.so를추출. libapp SHA는기존기록과일치.
- 도구로확인한Dart3.12.0,스냅샷41be3daaabd524b8aa7423bc24584957,android/arm64/compressed-pointers/product.
- Ubuntu24.04/g++13.3. CMake/Ninja/Python모듈을작업폴더venv에설치. ICU74헤더와기존시스템ICU74라이브러리,Python wheel에포함된실물Capstone라이브러리/헤더를사용.
- Blutter의로컬변경은CMake의Capstone검색경로와Ninja병렬작업수2뿐이다. 도구의AOT계산/해석알고리즘에기능패치를가하지않았다. Blutter가원래수행하는Dart VM분석용패치는그대로사용.

## 1. Blutter

공식저장소:[worawit/blutter](https://github.com/worawit/blutter). 실제소스커밋은집계JSON참조.

1. 버전검출성공.
2. 해당Dart SDK를받아분석용Dart VM과Blutter빌드성공.
3. 첫자동실행은Capstone SONAME라이브러리탐색문제로실행되지않음. 실제라이브러리로의로컬심볼릭링크와LD_LIBRARY_PATH설정후재실행.
4. libapp로드→애플리케이션분석→객체풀덤프→어셈블리→후킹템플릿생성,종료코드0.

출력671파일/86,508,012바이트. 그중asm파일666개,주소·크기선언블록12,752개. 선언블록수는독립함수나완전히복원된함수의개수와같다고가정하지않는다. 같은버전의빌드/추출은다시실행할필요없으며캐시를재사용한다.

### 우선 추적할 함수 위치

아래는Blutter가표시한코드주소다. 이전문서의**ELF문자열바이트오프셋과다르다**. ASLR런타임절대주소로사용하지않는다.

| 파일(asm/sfa 아래) | 함수 | 코드주소 |
|---|---|---|
|original_port/activities/import_animation_activity.dart|importSequenceXmlText|0x505c44|
|같은파일|_ImportSequenceXmlHandler 생성자|0x50e174|
|original_port/data/android_database_recovery.dart|_importSequence|0x34e224|
|main.dart|compareDrawOrder closure|0x5b9c54|
|main.dart|resolveDrawOrder closure|0x5b9d5c|
|original_port/data/data_access.dart|UpdateAnimationObjectDrawOrder|0x50ce88|
|original_port/sequences/tween_link.dart|resolveTweenLinks|0x632d74|
|original_port/sequences/frame.dart|_buildFillRegionInterpolationSegmentKey|0x632930|
|original_port/sequences/frame.dart|FrameDrawPlan.drawUnit|0x414ee8|
|original_port/sequences/frame_fill_region.dart|drawFrameFillRegionsForLayer|0x41548c|

glow_shader.dart, frame_fill_region.dart, fill_path_clipping.dart, perspective_overlay.dart, frame.dart, animation_object.dart도추출됐다. 이름발견만으로알고리즘의해석완료를선언하지않는다.

검증: 4코드위치를ELF PT_LOAD매핑으로원래libapp의실제바이트에대응시키고,독립Capstone역어셈블러의명령종류와비교했다. drawUnit내0x414f78에서채우기함수0x41548c를호출하는대상주소도실제바이트와일치했다. 추출주소의표본검증이며전체12,752블록의정확성을보장하는검사는아니다.

첫한정관찰: drawUnit에는composite glow호출분기와채우기호출로진행하는분기가있다. 실제영상의함수경로나plan의unit정렬규칙은아직끝까지추적하지않았다.01의겹침규칙을짧은분기만으로확정하지않는다.

## 2. reFlutter

공식:[Impact-I/reFlutter](https://github.com/Impact-I/reFlutter). clone한0.9.8을실제로설치하고ARM64분할APK에dump mode `-p -n`을실행했다.

- 스냅샷인식성공. enginehash.csv에는같은hash가Flutter3.44계열로기록돼있다. **Dart3.12와Flutter3.12를혼동하지않는다**.
- 덤프엔진다운로드실패,종료코드1. 대상release tag `android-v3-41be3daaabd524b8aa7423bc24584957`을GitHub REST API로도조회해404확인. 버전인식실패나사용자APK불량으로판정하지않는다.
- `-b`의commit해결모드는성공하지만그것만으로엔진빌드/덤프성공이아니다. 같은hash의여러행이있고첫후보는beta engine commit이다. 자체빌드시실물engine revision/호환성확인이필요하다.
- 제공된local-release의v3/build-only도시도했지만brew부재guard에서종료1. 스크립트는macOS용환경을요구한다. depot_tools는받아bootstrap후gclient응답까지확인했지만Linux수동engine checkout/sync/GN컴파일까지진행하지않았다.
- 현재환경에adb/Android emulator가없어재패키징해도실제앱실행/JSONL dump검증에는실행환경이필요하다. 분할APK이므로engine분할만단독설치가능한APK로취급하지않는다. 서명/전체분할일관성도미검증이다.

**이번에는변경APK도dump.dart도생성되지않았다.** 원본APK/사용자설치앱은변경하지않았다. reFlutter소스에서전용engine을만드는방법은남지만이번에빌드성공했다고주장하지않는다.

## 다음의 정확한 행동

먼저성공한Blutter출력에서XML importer의DrawOrder/ObjectScale가져오기·갱신→FrameDrawPlan의unit정렬/FR위치→glow uniform/합성→FrameInterpolationPlan/TweenLink대응을필요한함수만읽는다. 전체재덤프/원본영상재분석을반복하지않는다. reFlutter custom engine build와Android실행환경은별도미완항목으로남긴다.

현재private루트:/workspace/scratch/e23c9fd610d3/private/. blutter_out/추출물,blutter/bin/실행가능한분석기,venv/와depsroot/의존, reFlutter/소스,input/arm64-v8a/입력2라이브러리. 실행시LD_LIBRARY_PATH=depsroot/lib. 옛private캐시도유지한다. 환경변경후존재는보장되지않는다.

이번은문서/집계만공개. 고정예측·File-2최적화·학습·AI연결계속보류. 기존SFA/영상/22생성검사재실행없음. 새로4명령위치검증실행.
