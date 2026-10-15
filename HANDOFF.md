# AI-sfa 현재 인수인계 — 2026-10-15

## 목표·상시 지침

- 한국어 소통. Stick Fighter51.0.0의 **모든 창작·편집 기능 분석과 실제 앱 검증**이 목표다. 최소SFA생성/렌더근사로목표축소금지. 사쿠가수집/학습/AI연결은보류.
- 직접작성보고서·집계·작업지침은main반영상시승인. 쓰기전최신head/tree/expected_sha확인,다른변경보존. 시스템자동승인거부우회금지.
- 공개금지: APK/SFA/영상/역컴파일소스/assembly/키/전체런타임로그. 레포에원본또는역컴파일코드첨부금지.
- FPS=(트위닝,재생). 레이어UI는전체프레임제작보조. 굽힘기능없음. 편집공간/출력사각형구분,음수·화면밖좌표임의삭제/중앙이동금지.
- 기존00–05시험/자료분석완료. 재출력·추가작품·제작자문의금지. 기존추출·도구설치·시험은새변경/실패관련필요없으면반복금지.
- 정확도유지하며캐시/읽은내용재사용·좁은출력·실제명령검증. AGENTS.md준수. 사용자잔여주간사용량직접조회불가. 인수인계필요시체크포인트저장후docs/HANDOFF-PROMPT.md제공.

## 현재 실행 환경·기능표 — 2026-10-15 20:32 KST

- PC 현재 사용 불가(20:26 사용자 보고). 서버의 기존 AOT/ELF/Capstone 접근은 정상. PC 소실과 서버 캐시를 혼동하지 않는다.
- 실행 환경·기존AOT/ELF/Capstone 접근복구. 원본재추출/도구재설치없음. 15:15의unavailable은해소됐고,캐시가유실된것은아니었음. license4 지속편집계측차단과는별개.
- 기능별실제표본/정적근거/미확인은docs/FEATURE-EVIDENCE-MATRIX-2026-10-15.md. 기존00–05영상·SFA재분석없음. 지금사용자추가작업없음.

## 현행 체크포인트 — 원근 선택·codec/root 해제·재생·객체 보간

먼저 AGENTS.md와 docs/AOT-OBJECT-TWEEN-PAIR-TRACE-2026-10-15.md를 읽는다. 기능별 근거는 FEATURE-EVIDENCE-MATRIX. 직전 상세패널/캐시/저장 세부사항은 각 보고서와 docs/history/HANDOFF-2026-10-15-before-autonomous-tools.md에 보존했다. 과거 ‘다음’을 반복하지 않는다.

- 사용자 최신 지시: 혼자 처리 가능한 작업은 자율 진행. 사용자 추가 시험 요청 없음. 설치/페어링/폰시작/기존 영상 반복 금지. 전체 기능 분석 목표 유지, 학습·AI연결 보류.
- CONNECTED-TARGET-REFLECTION: tap→CollectGroupClosure→AO ID 첫 발견 중복제거 목록→상세 dialog. closure는 AC·소유 AO 점·그룹 parent/children을 입력 map 범위에서 큐로 확장. 반사는 start x 중심 x'=2c−x, start ID 제외, tap→saveAfterMove 연결. DrawOrder sort 아님.
- ALLGROUP-BOX: layer 표시/잠금 필터, 전역 설정 bool에 따른 활성 layer 제한. 초기 점 화면좌표/속성 snapshot에서 상자 변환; 모서리만 t/o 배율 및 Radius=min(round(R0*k),max(300,R0)); 측면/이동/회전은 해당 속성 loop 제외. 최소 화면 크기8, rotate snap45도 진입.55도/유지.96도. pan종료 moved면saveAfterMove. movedFigures는 동일Frame/구조에서 좌표만 비교하며 속성diff로 일반화 금지. 표시 토글→sequence DB 전달 확인; 별도 잠금 UI 미식별.
- MOVEMENT-DISPATCH: pose tool0, stretch1. T=Flags&0x2e로 전체이동/회전/PivotTo 분기; 0x21 조상 예외 별도. concurrent는 일반 AC만 따라가며 그룹연결 제외. 늘이기는 이 점들을 같은 포인터 좌표로 이동. 전체이동 closure는 그룹 확장 포함. 회전은 화면좌표에서 수행 후 역변환.
- _branchOf: pivot 일반연결점 ID를 경계로 두고 branch seed에서 비그룹 AC+소유 AO 점 확장. RotateBranch에서 현재 점==pivot이면 적용 후 회전중심 다시 구성하는 조건 있음. GetClusterHead는 parent가 일반연결점 안일 때 위로 이동.
- BuildTree: map 점 parent/children 초기화→선호점+T2 후보 전체 ID정렬→미방문 후보 탐색, 비그룹AC 후 AO다른점 확장/parent지정. 남은점은 map값순 새탐색. 선호점 무조건 첫 root 단정금지. 0x5114b0 공유몸체는 fieldb=null이며 Flutter dispose 의미로 읽지마.
- 새175개 선택 명령 ELF/Capstone 대조 통과(CONNECTED-ALLGROUP audit). 전체함수/실제앱/pixel 검증 아님; 다른 보고서 표본과 중복 합산 금지. 문서만변경/unit·probe재실행 없음.
- PERSPECTIVE-WARP: 일반핸들8개·시작snapshot·screen18 hit-test·valid quad=maxpairdistance>2(볼록/면적검사아님). D,S순 인수; signedH/V로 목적abs≤.5 또는 둘abs>.5반전이면bilinear우선,그외projective,실패시bilinear. homography분모abs<1e−6/비finite 또는점하나실패→전체fallback. bilinear는sourcequad bbox의u/v로D0→D1,D3→D2보간/clamp없음. solver pivot최대abs<1e−7실패. 일반helper는좌표만저장;lasso→AllGroup별도라모드전체속성불변일반화금지. 새130선택명령대조/실제앱미검증.
- 올가미경로 닫힘:resolveLassoTarget=선택screenmap키→Frame점ID필터,ofPoints=점목록+소유AO ID중복제거 별도. 시작AllGroupDrag/update dragTo우선/종료leftBox·기존anchor ID재선택·저장. 새polygon 내부판정helper아님.
- 새 SELECTION-CUSTOM: 원근후보 visible T2만,activeLayer bucket. bounds=연결점screen bbox inflate18/min48;다시inflate26후거리²≤676,score8d²+.0015area+.015center거리². anchor는첫비그룹T2→첫그룹T2→입력. fallback점우선순위3/1/0과제곱거리여유9. 일반/custom수학공유,custom종료dirty→saveCurrent이며일반saveAfterMove와다름. 새80명령대조. contexthelper는hidden층제외/locked필드미조회,모드전체lock무관으로확대금지.
- 새 FILL-MOVED-CODEC: fill=zlib/버전1/U7varint+ZigZag/ARGB·kind·AO·contour/edgeoptional점·Float64LE. NaNt→null→복원0/1,−0→+0,범위clamp없음. moved=연속IDrun/gap·길이/첫delta64bit+각점predicted와target signedbit정수차를ZigZag. XOR/정수좌표양자화아님. callbackoffset+B. outgoing연결갱신은withLinks=false구체화→그점기존outgoing삭제→대상ID중복제거insert. 전체비정상바이트보장아님.
- 새 ROOT-RELEASE: base존재/root참조base행정확히1/2N<R일때만잔여점·연결구체화→moved좌표반영→상세복사→dropbase. drop은removed/moved/base삭제후아무base도참조안하는root점/outgoing/detail/root정리. noteRowsLeaving공통bool은recordScope대상−1표시로소비;즉시참조복구메커니즘으로단정금지. CODEC-ROOT 새102선택명령대조.
- 새 PLAYBACK-BUFFER: sourceindex→Frame LRU100/읽은Frameidentity별점수500000초과&&2개초과시목록/map해제. outputindex→Picture?와Placement맞는Image별도. recordahead최대120/6000µs/각64MiB검사,finishAhead4후보중최초1Image변환후return. plan앞뒤identity쌍재사용. displayed소유권dispose분리. clock은목표+최대8ms허용/한period초과늦으면기준재설정;exporttimeline과분리. 새90명령대조.
- 새 OBJECT-TWEEN: 앞AO기준쌍,수동대응우선→같은ID,미대응중간AO추가없음. link입력뒤ID→앞ID/뒤key정렬,앞반환중복·양frame자연ID충돌·TypeId·동위치Index목록검사. 점은앞목록순/같은위치Index우선→뒤첫Index검색→없으면앞좌표유지. p0+(p1−p0)t,새보간객체/원본점수정아님. tScale선형,R/GlowThickness반올림,GlowAlpha=앞+trunc(delta*t),색ARGB. ObjectScale일괄lerp로일반화금지. 그룹ID앞연결집합공급. 새64명령대조.
- 모든audit는선택명령일치이며전체함수/앱/pixel검증아님. 표본수독립누적합산금지. 코드변경없음/기존unit·probe·폰·영상반복없음.
- 사용자20:32재지시: 혼자진행가능한일전부. 작은보고서·커밋끝마다다음안내로멈추지마. 앞서안내한원근tap/custom/저장보간작업은이번정상경로를처리함. **완전한앱이해/모든독립분석완료주장은금지.**
- 남은 구체 정적범위: 상세변형fallback GDT+0x85e4의concretegetter(기존cache에selector↔target표없음/첫점단정금지),GroupFlagRepair/RepairGroupFlags의비정상그룹정규화,전체UI명령coverage/undo·custom fill prune,root rebase/compaction의나머지분기. 보간·codec전체오류입력/수명·동시실패의일반보장미완. 이항목은실물없어서본질적으로불가능한것으로분류하지마.
- 일반AO앞뒤/별도잠금UI는미식별. 같은이름·PP검색·생성DrawOrder호출재추적반복금지. 새로운구체UIcaller가있을때만추적. 기존renderer·fill·timeline·modify보고서재사용. 실제pixel/backend와미검증UI결과는별도실물검증범위이며license4차단유지. PC재확보/폰재설치요청없음.

## 필요한 이전 정적 사실·근거

| 주제 | 현행 근거·제한 |
|---|---|
| 좌표/DPR/여백 | AOT-RENDER-CONTEXT-TRACE-2026-10-15.md: Offset+UsableSize×p/100/aspectfit/DPRoverride→view→1/export동기DPR1. 초기0해석은PAINT-DISPATCH보고서로정정. |
| 채우기 보간 | AOT-FILL-TWEEN-TRACE-2026-10-15.md: rawsignature→유일canonical후보대응. paired색보간,앞held t<1유지/뒤held t1만. 경계보간실패시t.5기준앞/뒤segments+보간색. '모든FR앞색유지'금지. field_33=contourIndex. |
| 구멍·경계 | AOT-FILL-PATH-TRACE-2026-10-15.md: outer0실패전체null/hole실패생략. 개별contour evenOdd후holes순차difference. 거리>0.1Path좌표연결lineTo/close. 선Tclamp없음/곡선clamp분할/arc기준각+2πT. |
| 공급·그룹·glow | AOT-DRAW-GLOW-TRACE-2026-10-15.md: getter DB자동조회없음/null빈목록만DB공급. DB정렬COALESCE(draw_order,id),id. 비연속그룹A(g),B(h),C(g)→A,C,B. shader11=d1/sigma로정정,10=W/2,12일반0/링1. blend입력Paint상속/초기srcOver. |
| import/링크 | AOT-PATH-TRACE-2026-10-15.md: importer DrawOrder/ObjectScale미조회→생성ID순서/default1. 수동링크TypeId/Index/충돌검사. 모든import/general링크정책확정금지. |
| UI실측 | UI-04-05-RESULTS-2026-10-15.md: '굽힘없음',그룹Flags상위ID참조/AC,원대원TweenLink출력복구. 전체기능완료아님. |
| 00–03영상 | PRIORITY-V2-RESULTS-2026-10-14.md,ROUNDTRIP-V2-RESULT-2026-10-14.md. 기존측정/왕복변화재분석금지. |

## Android 실물 상태 — 추가 사용자 작업 없음

- 환경갱신(사용자보고2026-10-15 08:48–08:49 KST): 당시 PC사용가능,대략i7-8700/GTX1050Ti/RAM16GB였으나 20:26 KST 현재 PC사용불가로 정정. 휴대폰Wi-Fi는학교망연결가능하나제약있음(08:49 KST정정,정확한제약미확인). PC의OS/인터넷/USB연결·ADB준비상태는미확인. Android16/SDK36/ARM64·루팅X 유지. Termux/android-tools/pkgupgrade/무선ADB/저장공간접근완료는이전이력이며현재학교망무선ADB사용가능으로가정금지. PC확보만으로라이선스응답4차단해결단정금지. 기존정적캐시추적계속,설치·페어링/getprop/시작시험자동재실행·요청금지.
- 원본 com.sG.stickfighter.activities51.0.0/versionCode51000,min24/target36,user0 base+arm64+ja+ko+xxhdpi,DEBUGGABLE없음. user150권한오류는user0사용.
- 별도 com.twoapple08.sfa.instrument/SFA Instrument Test5APK 제작/동일키v1/v2/v3서명·정렬·원본보호항목242대조통과,비공개전달완료. 기존libapp/libflutter보존. gadget script/qjs시작·모듈로그만,서버/Java bridge/렌더Hook없음.
- 실물동일PID12555에서Gadget early/arm64/libflutter/libapp로드성공. LicenseClient기존패키지조회NameNotFound→Play연결/요청성공→응답4예외→오류창,Close시앱종료.라이선스코드4정확한서버뜻미확인(명시invalid package코드는3).원본삭제/Play비활성단정금지.
- 실제지속편집/렌더검증없음.검사변경/우회미실시.추가사용자명령/재설치/Play설정/시작시험요청없음.자세한근거ANDROID-INSTRUMENTATION-BUILD-2026-10-15.md.
- SFA앱밖백업은설치스크립트질문으로안내했으나사용자BACKUP응답원문은없음.완료확정을만들지않는다.

## 보호 상태·검증

- PREVIDEO-PREDICTIONS-2026-10-14.md/PREVIDEO-FRAME-AUDIT.json은3278146고정예측. 정답맞춰수정금지. 비교/정정은별도VIDEO-PREDICTION-COMPARISON.
- File-2최초예측100%조건불충족으로최적화/재압축/삭제/병합/원본수정금지. 영상경계정정/실측은각보고서참조.
- 보고서집계/명령표본은렌더러/완성AI/학습결과아님. 기본HTML preview는근사. sfa.read_sfa32MiB한계임의해제금지.
- 코드변경시필요검사:repo루트 python -m unittest discover -s tests -v. 문서만변경하면기존시험반복안함.

## 캐시·재개

- AOT/ELF: /workspace/scratch/e23c9fd610d3/private/{blutter_out,input/arm64-v8a/libapp.so,venv,depsroot}. asm/sfa,pp.txt,ida_script/addNames.py재사용. Blutter성공은원래Dart소스복원아님.
- 원본base /workspace/scratch/6d77389e706a/evidence/apk/base.apk,분할모음같은evidence/STICK FIGHTER (51.0.0).apks. 기존Java캐시6d77389e706a/private/decompiled.
- 계측도구/빌드 /workspace/scratch/37921248d0d6/private/{instrument-tools,instrument-build}. 전용키sfa-test.jks재사용. 공식tools Apktool3.0.3/signer1.3.0/Gadget17.23.3 ARM64확보됨. 빈도구폴더/다운로드미완은옛상태.
- 비공개ZIP /workspace/scratch/25b8ca176661/output/SFA-Instrument-Startup-2026-10-15.zip,libfile_a9e9671bcd3c8191b95a54915af9aa6d. 원본기반APK공개금지.
- 현행문서checkout5a16c98ed7ee/AI-sfa-publish;curve/ring/cache검사5a16c98ed7ee/private-trace/. 이전문서checkout1be6baf45de3/AI-sfa;읽은shader텍스트1be6baf45de3/private-trace/. 이전문서worktree25b8ca176661/AI-sfa;이전검사/집계private-trace/. 이전37921248d0d6/e23c9fd610d3의로컬변경보존.remote반영뒤localHEAD뒤처질수있음;캐시문서덮어쓰기/reset/중복커밋금지.
- reFlutter해당dumpengine404/자체engine빌드미실시이력은FLUTTER-TOOLS-RESULTS-2026-10-15.md.재시도요청없음.
- 압축전인수인계전체보존:docs/history/HANDOFF-2026-10-15-before-render-context.md.현재내용이우선이며역사기록의낡은'다음'을재실행하지않는다.

- 추가 검증 캐시5a16c98ed7ee/private-trace;추가문서반영clean worktree5a16c98ed7ee/AI-sfa-publish. 기존1be6baf45de3캐시/체크포인트와옛dirtyworktree는보존.
