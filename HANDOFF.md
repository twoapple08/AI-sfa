# AI-sfa 현재 인수인계 — 2026-10-15

## 목표·사용자 지침

- 2026-10-15 사용자 상시 승인: 직접 작성한 분석보고서·집계·인수인계/작업지침은 이 레포 main에 반복확인 없이 반영 가능. 원본/역컴파일물 공개와 기존 보호작업은 제외. 시스템 자동승인설정 자체는 변경불가.
- 한국어 소통. 사용자는 PC 없는 루팅 안 된 Android/Termux 환경. GitHub 반영 허용, 앱 제작자의 역공학 허가를 받았다고 설명했다.
- 먼저 Stick Fighter51.0.0의 모든 창작/편집 기능을 분석·명세·실제 앱 검증한다. 최소 SFA 생성으로 목표를 축소하지 않는다.
- 현재 우선순위: ① 채우기·구멍·겹침 순서 ② 글로우 강도·범위·합성 ③ 생성·삭제와 프레임 사이 보간.
- 사쿠가 수집·학습·AI 연결·Android 패키징은 보류. 현재 학습된 AI/완성 렌더 엔진/APK가 없다. 나무위키 금지.
- FPS 순서는 **(트위닝 FPS, 재생 FPS)**. 레이어 조작은 전체 프레임에 적용되는 제작 보조 기능. DB frame_id로 UI 범위를 추론하지 않는다.
- 편집 작업 공간과 흰 출력 사각형을 구분한다. 좌표를0–100으로 강제 제한/중앙 이동하지 않는다. 화면 밖 도형도 진입·채우기·글로우 참조 때문에 임의 삭제하지 않는다.
- APK/SFA/영상/역컴파일 소스/추출 프레임을 공개 저장소에 올리지 않는다. 보고서·집계·직접 작성한 도구만 반영한다.
- 사용자 추가 요청: 정확도를 유지하며 토큰 낭비를 적극 줄이고, 효율상 필요하면 자율적으로 인수인계와 새 대화 프롬프트를 갱신한다. 실행 지침은 AGENTS.md.

## 최신 체크포인트 — 사용자 Android 연결 완료 / 계측 APK 제작 전

- 최신 보고서: docs/ANDROID-INSTRUMENTATION-HANDOFF-2026-10-15.md. 먼저 이 문서·AGENTS·이 보고서를 읽는다. AOT 의미 해석이 필요할 때만 AOT-PATH-TRACE-2026-10-15.md.
- 사용자: 다른 Android 기기/PC 사용 불가, Wi-Fi 사용, 루팅X. 관련 도구 없던 상태에서 Termux·android-tools 설치와 무선ADB 연결 완료. Termux linker 오류는 pkg upgrade 뒤 해결되어 adb shell getprop/pm/dumpsys 실제 성공. 설치·페어링/getprop를 다시 시키지 않는다. 세션 연결이 끊겼을 때만 연결 상태 확인.
- 실물: Android16/SDK36,ABI arm64-v8a,armeabi-v7a,armeabi. 스파 패키지 com.sG.stickfighter.activities,versionName51.0.0,versionCode51000,minSdk24,targetSdk36. user0의base+arm64_v8a+ja+ko+xxhdpi 총5APK. DEBUGGABLE표시없음. com.sfaclan.community는별도앱. user150조회SecurityException은user0지정으로회피;앱불량판정금지.
- 계측 제안: reFlutter 배포엔진 재시도 대신 원래 Flutter 엔진 유지+Frida Gadget의script 모드로 제한된 호출/인수 기록 검토. 사용자 한기기이므로 원본과동시 설치 가능한 별도package 및provider/permission/component참조/서명을 먼저검증. 패키지명변경만으로작동보장금지. 원본삭제/덮어쓰기/루팅요청없음.
- **아직 계측 APK/서명검증/설치파일/런타임로그 없음.** 구현·빌드·실물실행미완. 다운로드시도프로세스39459는현재Unknown process id이며instrument-tools폴더비어있음. 도구가다운로드됐다고주장하거나같은프로세스를재폴링하지않는다. APKTool/서명도구/Gadget 준비부터 필요.
- 정확한 다음: 기존base/split캐시확인(이미확인)→공식도구획득경로의네트워크응답/파일검증→base manifest와충돌참조의한정검사→별도package의최소시작계측APK 제작/서명검증→비공개사용자전달→사용자가설치·시작만확인. 시작성공뒤렌더/보간계측확장. 재덤프/전체JADX/00–05재분석금지.
- 캐시: /workspace/scratch/6d77389e706a/evidence/apk/base.apk 및 evidence/STICK FIGHTER (51.0.0).apks; ARM64입력 /workspace/scratch/e23c9fd610d3/private/input/split_config.arm64_v8a.apk;AOT /workspace/scratch/e23c9fd610d3/private/blutter_out/asm/sfa. 작업·빈도구폴더 /workspace/scratch/37921248d0d6/{AI-sfa,private/instrument-tools}. java있음,apktool/apksigner/aapt2의PATH명령없음(당시확인).
- 사용자작업은중요작품의앱밖SFA백업만안내했고완료답변은없음. 수정앱설치는준비전요청하지않는다. 백업여부와설치대상은실제설치단계에서확인. 기존시험재출력/추가작품/제작자문의없음.
- 사용자주간사용량/남은대화횟수는직접조회불가. 사용자가3–4대화남을때인수인계요청. 이번체크포인트로저장;실제잔여량을추정해단정하지않고사용자알림또는작업단위종료시재개프롬프트제공.
- GitHub main의기존AOT·상시승인문서는847fea3에반영. 동일범위의보고서/집계/인수인계상시승인유지. 시스템자동승인설정변경불가. APK/SFA/영상/역컴파일/asm공개금지,고정예측/File-2최적화/학습/AI연결보류유지.

## 이전 체크포인트 — AOT 경로 제한 추적

- 최신 보고서: docs/AOT-PATH-TRACE-2026-10-15.md, 집계: docs/AOT-PATH-TRACE-AUDIT-2026-10-15.json. 기존 성공 캐시만 읽음. 설치/빌드/전체덤프/00–05 재분석 없음.
- importer startElement(0x5099ac)는 XML DrawOrder/ObjectScale을 조회하지 않는다. 새 AO는 새 ID를 DrawOrder로 저장(0x50cdf8/0x50ce1c), ObjectScale은 생성 기본값1 유지. exporter는 두 필드를 기록한다. 01/02 왕복 변화의 코드 원인 확보; 모든 import/recovery 경로 일반화 금지.
- BuildDrawPlan(0x42b910): 레이어→연결 그룹별 glow-only unit→각 AO의 FR+base unit. drawUnit은 해당 FR 뒤 해당 AO 기본형상을 그림. FR 역색인은 outerSegments ObjId, take는 레이어/소비집합 검사. FR목록 하나만으로 전체 겹침순서를 설명하지 않음. compareDrawOrder closure의 부모는 _mergeLayerDown이며 planner comparator라고 확정 금지.
- DrawGlowEffect(0x420dcc)는 GlowAlpha로 GlowColor의 알파를 교체. shaderFor(0x426c38) uniform0–2는 RGB×alpha/255,3은alpha/255,10은두께/2. shader→raster cache→MaskFilter fallback 확인. 실제blend 열거값/모든단위/영상dispatch 미완.
- FrameInterpolationPlan(0x62f408)→resolveTweenLinks(0x632d74): 존재·TypeId·source중복/양쪽잔존ID충돌 검사. _samePoints는 목록길이/위치별Index 비교(좌표비교아님). 같은ID 먼저→링크대응,없으면쌍생략. 복잡한FR/링크실행검증 미완.
- 새11명령 실물ELF/Capstone 대조 통과,handler 속성목록 한정assert 통과. 전체의미/전체함수검증 아님. 문서만변경해기존unit/생성시험반복없음.
- 정확한 다음: GetAnimationObjects의로드·캐시공급순서/비연속그룹방문순서→TryDrawGlowWithShader(0x425458)의paint배율·blend→_planFillRegions(0x62ff78)/renameTweenLinkedFill·canonicalize·held/interpolated/discard·색정책. 아래 옛 '정확한 다음'은 이전 체크포인트다.
- 작업환경 /workspace/scratch/37921248d0d6/AI-sfa (origin/main 008b69e 기준 별도worktree). 이전 e23c9fd610d3/AI-sfa의변경은그대로보존. 캐시 /workspace/scratch/e23c9fd610d3/private/blutter_out/asm/sfa 재사용.
- reFlutter/Android/분할서명 미완,보호파일·최적화/학습보류·재출력/추가작품/제작자문의금지 유지. 새대화는 이 문서·AGENTS·AOT-PATH-TRACE부터;설치결과가필요할때만FLUTTER-TOOLS-RESULTS.

## 이전 체크포인트 — Blutter 성공 / reFlutter 배포 엔진 없음

- 최신보고서: docs/FLUTTER-TOOLS-RESULTS-2026-10-15.md,집계: docs/FLUTTER-TOOLS-AUDIT-2026-10-15.json. 사용자지시로두도구를순서대로실제로시도.
- **Blutter성공:** Dart3.12.0/android-arm64/스냅샷41be3daaabd524b8aa7423bc24584957. 버전별분석기빌드후종료0. 추출671파일/86,508,012바이트,asm666개/코드선언블록12,752. 원래Dart소스복원아님. 명령주소4개를실물ELF/Capstone과대조통과. 추출전체정확성/모든함수해석완료아님.
- **reFlutter0.9.8:** 스냅샷지원목록일치하지만dump용android-v3-tag GitHub API404/다운로드실패종료1. 변경APK/dump.dart생성없음. -b는engine commit선택만성공. macOS build-only스크립트는brew없음guard종료1;Linux수동엔진빌드미실시. depot_tools/gclient는bootstrap응답확인. adb/emulator없음. 분할APK의서명/실행검증미완.
- **정확한다음행동:** 성공한Blutter asm에서importSequenceXmlText/handler→DrawOrder/ObjectScale설정,FrameDrawPlan unit정렬/FR배치→글로우uniform/합성→FrameInterpolationPlan/TweenLink를필요한함수만추적. 도구빌드/추출/원본영상/SFA검사재실행금지(새변경/문제가있을때만). reFlutter자체엔진빌드·Android실행은별도미완.
- 캐시 /workspace/scratch/e23c9fd610d3/private/: blutter_out(asm/pp.txt/objs.txt/ida_script/blutter_frida.js), blutter/bin/blutter_dartvm3.12.0_android_arm64,venv,depsroot,input/arm64-v8a,reFlutter,depot_tools. 실행LD_LIBRARY_PATH=depsroot/lib. Blutter로컬변경은Capstone CMake검색과ninja -j2뿐;분석알고리즘패치없음. 옛캐시도유지. 비공개추출물공개금지.
- 보호상태그대로: 고정예측/File-2최적화/학습/AI연결보류. 00–05사용자자료완료,기존시험재출력/제작자문의요청없음. 이번문서/집계만반영.
- 다음대화는이문서/AGENTS와최신도구보고서부터. 정확한다음프롬프트: docs/HANDOFF-PROMPT.md. 길어진설치/분석기록대신이체크포인트를사용.

## 이전 추가 추적 — 그룹 참조 인코딩 / 경로 경계

- 최신정적추적: docs/APK-GROUP-LINK-TRACE-2026-10-15.md. 먼저읽고필요한UI결과만연결한다. 기존private캐시가실제존재해다운로드/재역컴파일없음; libapp.so기존SHA일치.
- 그룹Flags93598163 = (위선기준점ID1462471 << 6) | 16 | 3. grouped/grouped_move에서확인;해제Flags3. AOT SQL도0x10/상위참조재매핑/하위6비트보존식을포함. **ID정규화시Flags내참조도대응해야함**. 단순그룹마스크상수로사용금지. 전체Flags비트/전파함수는미확인.
- frame_tween_link조회/삽입SQL은AOT에있고05와부합. 읽은네이티브Y2.i.d는같은AOID조회뿐이어서05다른ID링크효과를단독으로설명못함. 상위링크해결/다른출력경로중어느쪽인지미확인.
- **다음행동:** 캐시AOT상수/함수참조를연결할호환도구의로컬가용성을먼저확인. importer DrawOrder/ObjectScale변경함수/FR배치키/그룹전파·링크대응추적. 문자열발견을실행경로확정으로승격금지.
- 캐시: /workspace/scratch/6d77389e706a/private/{decompiled,libapp.so,jadx,glow.frag}. 04/05입력은현재형제upload/. 새Flags식4상태assert검증;기존구조/영상/22생성검사반복없음. AGENTS.md에큰메타데이터필터링/UTF-8구조쓰기/툴선택지침추가.

## 최신 체크포인트 — 04 실제 UI / 05 수동 링크 분석 완료

- 최신 보고서: docs/UI-04-05-RESULTS-2026-10-15.md. 집계: docs/UI-04-05-AUDIT-2026-10-15.json. 이전01/02/03은완료상태이며다시분석/출력요청하지않는다.
- 사용자정정: **‘굽힘’기능은없음**. 내부perspective-bend문자열을UI기능으로확정한기존판단을철회. 굽힘시험/요청폐기. 실제메뉴는색상 & 늘이기,원근 & 올가미,그룹,올그룹,트위닝잇기등.
- 반환SFA11개구조오류0. 04/05 seed왕복은이름/ID/절대순서/숫자표기정규화후보존. 녹화4개는접촉표와조작주변표본,실제출력2개총96장을800×450으로전수디코딩. 전체렌더엔진재현이아님.
- U1: 녹화에서손끝드래그뒤변형탭크기200%/굵기100%적용이누적됨. 최종스틱맨10AO ObjectScale2/ThicknessScale1,주황선불변. 손끝외19점은허리(35,40)기준2배. 단일아래팔2배시험아님. 손끝중간좌표는역산만. UI설정ObjectScale2보존은02입력왕복1변경과구분.
- U2: 첫결과20점은사영변환적합오차1.92e-12,아핀은3.24. 두번째는아핀x1.188627/y1.251527+이동,10AO의ObjectScale/ThicknessScale1.1820126. 핸들별전체계산식/굵기식미확인.
- U4: 독립이동위선만→그룹은두Index0점상호AC2개추가/아래Flags3→93598163→이동시두선동일변위→해제AC제거/Flags3→다시위선만이동. 12AO/24AP유지. 그룹은병합아님,AC는동일좌표관절에한정안됨. Flags상위참조인코딩은위추적참조;모든선택경로미확인.
- U5: 원본13에TweenLink ID=뒤AO/From=앞AO하나. 이름/링크제외전후XML동일. 실제전후각24FPS/48장/2초. 축소RGB차이는출력24만: 링크전원누락→후중앙원. 다른유형/FR/복잡한링크정책미확인.
- **정확한다음행동:** 기존APK복구가능여부를확인하고DrawOrder/ObjectScale importer변경,FR배치키,그룹Flags/AC전파,TweenLink경계함수를추적. 기존시험재출력/제작자문의/추가파일요청없음. 뒤집기/올그룹/원근핸들별공식/잠금등은미확인표에유지.
- 이번은문서/집계만변경. 고정예측/File-2최적화/학습/AI연결계속보류. 11SFA구조검사와96장경계비교실행,기존22생성검사는문서변경으로재실행안함.
- 현재환경: /workspace/scratch/e23c9fd610d3/AI-sfa. 입력17개는형제upload/,프레임·접촉표는evidence/. APK/역컴파일은위기존캐시발견후재사용가능. 원본은공개저장소에올리지않는다.

## 이전 완료 체크포인트 — v2 합본 01/02/03

- 최신 근거: docs/PRIORITY-V2-RESULTS-2026-10-14.md, 집계: docs/PRIORITY-V2-AUDIT-2026-10-14.json. 첫00왕복은 docs/ROUNDTRIP-V2-RESULT-2026-10-14.md. 해당 자료를 다시 분석/출력 요청하지 않는다.
- 입력 반환SFA5개와 녹화3개/실제출력4개 확인. 실제 출력은01=192장8초,02=288장12초,03무보간=168장7초/보간=336장14초, 모두24FPS·1920×1080. 총984장을디코딩해선택영역/경계수치를측정. 전체픽셀렌더재현검증은아님.
- **왕복 변화:**01 원본145–168의 반전 DrawOrder 상대순서가XML열거순서로변경(48상태차이).02 원본241–264의ObjectScale2→1(24상태차이). 이구간은의도한변수가앱상태에유지되지않아렌더규칙시험으로사용금지. 정확한변경함수는미확인. FR목록순서반전은보존됐고03의주요정규화차이0. 전프레임AO일대일ID대응도확인.
- **채우기:** 단순안쪽Contour는정방향/반대방향둘다구멍. FR목록순서반전해도파랑면앞. 경계AO순서등다른키연결가설은미확인. 청록FR이교차선중앙을덮으므로네이티브FR→글로우→선요약을전체출력규칙으로확정하지않는다.
- **글로우:** Radius증가시넓어지고근거리밝기는감소가능. Thickness/GlowAlpha효과관찰. 기본선알파0도발광. GlowColor알파64/255의측정B프로파일동일은GlowAlpha대체와부합하지만전체합성식확정아님. 독립동일객체2개더밝고단순가산과다름;연결그룹/셰이더uniform은미확인. ObjectScale효과는이번에판정불가.
- **보간:** 같은ID좌표/기본알파중간값관찰. 링크없이같은자리새ID교체시중간누락(출력108/120/132),공통회색선유지. 생성/삭제원은한쪽에만있으면중간누락. FR없음→있음은중간없고있음→없음은중간앞FR유지. 경계삭제하면FR중간누락. FR색은이번실제APID참조표본에서앞색유지;APID가매프레임변하는signature대응가설을원인확정/모든FR색정책으로확대하지않는다.
- 수동TweenLink는05의원대원경계검증을완료했고일반정책은미확인. 부분곡선/복잡한Contour/레이어간순서/정확한글로우단위는미확인. 사전예측/File-2/렌더러원본변경없음. 이번문서/집계만변경. 기존22검사는시험생성체크포인트의검증이며재실행안함.
- 당시04/05사용자시험은이제자료수령·분석완료. 다음행동은위최신체크포인트를따른다.
- **제작자와 소통 불가능: 문의 제외.** 연락/소스확보를진행조건으로삼지않는다. 기존문의문안은과거준비물이다.
- 최초FPS는00표본(24,12),02표본(60,12)을관찰. 항상60/12강제가정금지. 각시험에서설정직접확인.03녹화약84.6초(24,12)/굵기100%;조작중값을최종값으로사용하지않는다.

## 00왕복·사용자 실행 안내 요약

- 00은ID/숫자표기/순서절대값/Contour0생략을정규화하면24프레임주요속성/참조보존. Contour1구멍/Kind1파란원/투명기본선글로우출력. 설정전후SFA는Name외동일. UI초기(24,12)/100%,최종(24,24),24장1초.
- 생성v2파일6개:examples/priority_probes_v2/. 생성 코드는build_priority_probes.py. manifest는재생성초기값으로유지하며실측보고서와구별한다.
- ZIP은저장완료했고기존생성SFA6개를그대로사용할수있다. 안내의제작자문의절은제외로정정했다. 추가다운로드필요없음.

## 이전 분석 결과 — 기준 ba1f632

- docs/FILL-GLOW-TWEEN-ANALYSIS-2026-10-14.md: 최신 APK/SFA/영상 대조. docs/BOUNDARY-AUDIT-2026-10-14.json: 좌표/ID 없는5경계 집계.
- File-2 84/85 공통1,752AO는 기본 선/글로우 알파 모두0. 앞에서 공통AO만 참조하는2,163FR은 모두 배경색. 뒤에는 배경색2,163+흰FR1. 38/39 공통1,734AO도 기본 선 알파0이며 남는6글로우 곡선 자체는 출력 아래. 공통AO 수로 밝은 형상 유지를 판단하지 않는다.
- **관찰 정정:** 원본39 위치(출력77)는 인물 잔존이 아니라 암부. 출력75는 인물/격자,76/77은800×450에서RGB16 단색. 기존 감사 JSON과 충돌한 비교 서술을 정정했다. 최초 고정 예측은 보존했다.
- 네이티브Y2.i.d/k: 공통AO 후보 → 모든 경계가 후보AO인FR 필터 → 경계signature/topology 대응. 미대응 앞FR 유지 분기, 부분T/색 보간 관찰. 전체 Flutter 규칙으로 확대하지 않는다.
- 네이티브Kind1 전체 원/이차곡선 부분T분할/EVEN_ODD/레이어별FR→글로우→선 패스 관찰. **X2.a.m/Y2.j가contour_index를 로드/보유하지 않으므로 Flutter 구멍 처리를 대신할 수 없다.** 큰 렌더 함수는 역컴파일 경고도 있다.
- 실물glow.frag shader bundle에 Gaussian계열ring/stroke coverage가 있다. uniform단위/사전알파/blend mode/경로선택은 미확인. 네이티브 원본/중간 굵기식도 다르다. 제공영상에 어느 경로가 실행됐는지는 미확인.
- tools/audit_sfa_boundaries.py는 읽기전용 XML 집계 도구. 렌더러가 아니다. 기존18검사 통과,5경계 집계는 별도 계산과 일치. 이 성공을 앱 전체 기능 완료로 세지 않는다.

## 반드시 보존할 검증 상태

- 두 famous user 작품: File-1 원본120 → 24FPS/240출력/10초, File-2 원본114 → 24FPS/228출력/9.5초. 사용자 설정(24,12). 최초 예측은 색채 고리·얼굴 세부·글로우·겹침·중간 암전을 놓쳐100%정확하지 않았다.
- docs/PREVIDEO-PREDICTIONS-2026-10-14.md 및 PREVIDEO-FRAME-AUDIT.json은3278146의 고정 예측. 정답에 맞춰 변경하지 않는다. 비교/정정은VIDEO-PREDICTION-COMPARISON-2026-10-14.md에 별도로 기록한다.
- **File-2 최적화는 최초 예측100%정확이라는 사용자 조건을 충족하지 못했다.** 재압축/삭제/병합/원본수정 금지 상태 유지.
- v1은16구간/768원본. (24,24) 반환 영상은24FPS/768출력/32초.14구간 표본 일치,13 레이어 프레임별 기대 철회,14 DrawOrder 전환 기대 불일치. 전체 픽셀 일치/실제 편집 버튼 재현이 아니다.
- DrawOrder는frame_id 없는animation_object 공통속성. 동일AO의 프레임별 상충값 처리와 importer는 미확인. APP-V1-ROUNDTRIP 재저장 요청은 현재 우선순위 뒤로 보류한다.
- 10_screen:5원본 모두 검정 스틱맨이 음수Y로 출력 위쪽 밖에 있고 글로우0. 실제 출력은흰색. 회색 편집 공간/플레이어 검정 여백과 구분. 이 사례의(T,P)는 별도 명시되지 않았다.

## 다음 작업과 중단점

1. Flutter Contour 경로 생성·채우기 planner/유효성·그리기 순서를 추적한다.
2. shader uniform 배율·알파·blend mode·연결 객체 합성·fallback 선택을 추적한다.
3. Flutter TweenLink/생성·삭제·점index/FR 대응을 네이티브 관찰 및 영상 경계와 대조한다.
4. 00–05자료분석은완료체크포인트. 기존시험재출력/추가작품은요청하지않는다.
5. 실제 늘이기/원근/그룹의남은전파·기준점공식,뒤집기/올그룹/잠금과importer초기설정을확인. 굽힘은존재하지않는항목으로제외.

미확인과 막힌 이유의 목록은 docs/OPEN-QUESTIONS.md. 위 순서가 현재 작업이며 이전 기록 속 “다음 요청”은 현행 지침이 아니다.

## 읽기 경로 — 현재 대화에서 읽은 것은 반복하지 말 것

- 새 대화: 이 문서와AGENTS.md → ANDROID-INSTRUMENTATION-HANDOFF-2026-10-15.md. 기능 전체 범위가 필요하면FEATURE-COVERAGE.md.
- 채우기/글로우/보간: FILL-GLOW-TWEEN-ANALYSIS-2026-10-14.md, 필요한 경우NATIVE-TWEEN-FINDINGS.md/APK-EVIDENCE-51.0.0.md.
- 영상 사실: VIDEO-PREDICTION-COMPARISON-2026-10-14.md 및 필요한 프레임의VIDEO-FRAME-AUDIT.json. JSON 전체를 대화에 출력하지 않는다.
- 출력 범위: EDITOR-OUTPUT-BOUNDS.md. v1: FEATURE-PROBE-GUIDE.md/APP-VERIFICATION.md.
- 과거 전체 기록: docs/history/HANDOFF-2026-10-14-before-compaction.md. 충돌 확인/역사 추적 때만 읽는다.

## 환경·도구·파일 복구

- 저장소 표준 라이브러리 Python: sfa.py, native_timing.py, build_feature_probes.py, tests/. HTML preview는 채우기/글로우/앱보간을 재현하지 않는 근사다.
- tools/audit_sfa_boundaries.py는 스트리밍 집계. File-2 XML372,172,417바이트/최대15,552AO. sfa.read_sfa의32MiB 한계를 임의 해제하지 않는다.
- 기존 소규모 samples:01_base~09_tween, anonymous user File-1/2(122/90원본,(60,12)), wave/probes. 필요할 때 해당 자료만 복구한다.
- 이번 대화 환경: /workspace/scratch/6d77389e706a/AI-sfa. 원본은 형제evidence/, jadx1.5.6·역컴파일·libapp·shader는형제private/. 존재 여부는 다음 환경에서 보장되지 않는다. 필요 경로만 확인하고 없으면 원본 이름으로Library에서 복구한다.
- 주요 원본 이름: STICK FIGHTER (51.0.0).apks, Anonymous famous user file-1.sfa/file-2.sfa,1000326603.mp4/1000326604.mp4,10_screen.sfa. 체크섬은 근거 문서 참조.
- APK는Flutter AOT+Android 혼합. JADX의Java출력을Flutter전체소스로 해석하지 않는다. 이번전체JADX는62오류. 앱실행/adb는이번분석에서사용하지못했다.
- GitHub connector 쓰기 성공. 터미널push 인증 실패 이력을 연결 재설정 필요로 확대하지 않는다. 쓰기 전최신head/tree확인,expected_sha보호. 다른대화의변경을보존한다.
- 이전 변경이원격반영돼도로컬HEAD가뒤처질수있다. 먼저실제바이트/원격SHA를비교해중복커밋을피한다. 무조건reset/덮어쓰기금지.

## 검증 명령

저장소 루트에서 필요한 검사만 실행한다. 분석문서만 바뀌면 이미통과한검사를반복하지않는다.

```bash
python -m unittest discover -s tests -v
python tools/audit_sfa_boundaries.py '<File-2 경로>' --pairs 38:39 72:73 84:85 94:95 103:104
```

새대화프롬프트: docs/HANDOFF-PROMPT.md. 인수인계 시 완료/미확인/다음행동/금지사항을 갱신한다.
