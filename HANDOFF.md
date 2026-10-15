# AI-sfa 현재 인수인계 — 2026-10-16

## 목표·권한·금지

- 한국어. 목표는 Stick Fighter51.0.0의 모든 창작·편집 기능 분석과 실제 앱 검증. 최소 생성기/렌더 근사로 축소하지 않는다. 사쿠가 수집·학습·AI 연결 보류.
- 사용자는 혼자 가능한 일을 전부 자율 진행하라고 반복 지시했다(최신20:32 KST). 작은 보고서·커밋마다 ‘다음은…’으로 턴을 끝내지 않는다. 미수행과 실제 차단을 구분한다. 모든 독립 분석이 끝났다는 거짓 완료 금지.
- 직접 작성 보고서·집계·작업지침 main 반영 상시 승인. 최신 remote head/tree 확인·expected_sha 보호·다른 변경 보존. 자동승인 거부 우회 금지.
- APK/SFA/영상 원본·역컴파일 소스/assembly·키·전체 로그 공개 금지. PREVIDEO 예측은3278146 고정, 정답에 맞춰 수정 금지. File-2 최초100%조건 미충족: 최적화/재압축/삭제/병합/원본수정 금지.
- FPS=(트위닝,재생). 굽힘 기능 없음. 음수/화면밖 좌표 임의 삭제·중앙 이동 금지. 레이어 UI는 전체 프레임 제작 보조. 편집 공간과 출력 사각형 구분.
- 기존00–05 영상·SFA 시험/분석은 완료한 범위 재사용. 재설치·페어링·getprop·폰 시작 시험·기존 영상 분석·새 작품/제작자 문의 반복/요청 금지. 문서 변경만으로 unit/probe 재실행 금지.

## 현재 환경과 차단

- 사용자20:26 보고로 PC 현재 없음. 이전 i7-8700/1050Ti/16GB를 가용 환경으로 전제하지 않는다. 폰 Wi-Fi는 학교망 제약. 과거에는 서버 AOT/ELF/Capstone 캐시가 정상이었다. **2026-10-16 현재 재확인 결과 기존 checkout/private 캐시 경로가 이 환경에 없다.** 공개 저장소는 같은 경로에 clone으로 복구했다. PC 소실과 별개인 분석 환경 차단이며 캐시 소실의 원인은 확인하지 못했다. 사용자 재설치·폰 시험을 요청하지 않는다.
- 계측 앱은 Gadget/Flutter/libapp 로드까지 실물 확인됐지만 Play license 응답4로 지속 편집 차단. 응답4의 정확한 서버 뜻은 미확인. 검사 우회 안 함. 원본00–05 실제 UI/출력 표본은 존재하므로 ‘앱 시험 전혀 없음’으로 쓰지 않는다.
- 원본 com.sG.stickfighter.activities51.0.0/code51000, min24/target36/user0/ARM64, Android16/SDK36/비루팅 이력. 학교망에서 현재 무선ADB 가능하다고 가정하지 않는다. 계측 com.twoapple08.sfa.instrument Test5는 원본보호242대조·서명/정렬 통과, 비공개 전달 완료. 재빌드 필요 없음.

### 제한 복구·자동 검토 차단

후속 사용자 지시 후 기존 APKS의 libapp.so/libflutter.so/glow.frag만 비공개 복구했고 과거 SHA-256 3개와 모두 일치했다. 위치는 `/workspace/scratch/5a16c98ed7ee/private-recovery/evidence`. AOT/PP/objs/기존 도구는 여전히 없음. 서버 분석 도구 설치와 Blutter clone은 자동 승인 검토에서 기존 설치·전체 재분석 반복 금지를 이유로 거절됨. 우회/재시도하지 않는다. 기존 포괄적 계속 지시와 명시적 예외 승인을 구분한다. 새 함수 분석·runtime 결과 없음. [복구 audit](docs/ANALYSIS-RECOVERY-AUDIT-2026-10-16.json).

## 현행 읽기 순서와 체크포인트

AGENTS.md → docs/ANALYSIS-READINESS-2026-10-16.md → 필요한 주제 보고서만 읽는다. 기능 구분은 docs/FEATURE-EVIDENCE-MATRIX-2026-10-15.md. 이전 전체 handoff는 docs/history/HANDOFF-2026-10-15-before-group-history-rebase.md에 보존했다. 과거의 ‘다음’은 현행 지시가 아니다.

새 추가 분석:

- GROUP-REPAIR: ResolveGroupParentId는 방문 ID 순환 차단/비그룹T2 부모 요구. null lookup에서만 조건부 legacy16bit token fallback; 실제 잘못된 부모에서는 fallback 없음. Repair는 ID정렬→자기참조 해제→없는 부모 복원/해제→순환 최소ID 한 점 해제→비T2 부모 재배정→잔여 flags 정리. Reassign은 구조 연결 후보 비그룹T2 최소ID. 기존 어느 한 방향 연결이 있으면 양방향 보완하지 않음. 메모리 변경 map/제거·추가 쌍→frame helper 초기화→DB transaction의 flags/양방향삭제/각끝점 outgoing 재저장. 57 선택 명령 ELF 대조.
- FILL-PRUNE-HISTORY: 외곽0 무효→region 제거; 무효 양수구멍·음수contour segment 제거/나머지 순서와 ID 유지. edge 유한t/abs차>1e−6/참조점·Type1·2≥2점·Type3≥3점. circle Type2≥2점; 다중segment의 circle 금지. 기하학 폐곡선 보장 아님. custom undo/redo snapshot deep clone/activeID/ID목록불일치 reset/중복비교/확인 push stack60/DB prune→SaveFrame→reload. 일반undo/redo는frameID별stack/signature(FastHash+linkhash)/push60,적용bool→16msawait→mounted재확인/종료·예외bool해제. 동적stack호출역할은typedreceiver/caller종합해석이며dispatch표복원아님. 일반복원은 live layer 적용→prune→변경AO 또는전체저장/배경·tweenlink별도. Adopt는 live AO ID맞고layer유효하면 LayerId+DrawOrder 보존, 아니면유효snapshot layer유지/활성layerfallback. fallback GDT getter 미확정. history비교는 layer/AO/점/연결/fill의 순서도민감; double은 NaN쌍동등,±0구분. 178 선택 명령 대조.
- ROOT-REBASE-IDLE: N>0/기존base없음/점ID범위 다른frame·가상base중첩없음/root행·크기/ID대응 AO·Index N일치/holdsRootExactly 통과때만 점/outgoing/중복상세삭제→base삽입. rID=rootFirst−(fID−B). holds는 좌표·flags복원·연결중복/외부연결·root상세기본값동등 검사. idle compaction은 시작전6ms검사/DBidentity 상태재사용/처리대상실패최대3. Rewrite 필요=DB·depthguard후 page_size<4096 또는 auto_vacuum!=2, 그외빈공간≥8MiB&&빈page≥전체1/4. 원본압축 실행 아님. 62 선택 명령 대조.

- DB-REWRITE: readOnly 원본연결/VACUUM INTO .compact/quick_check첫값ok/isolate 뒤DBidentity·depth·totalChanges·data_version·idle재확인. release후WAL유/길이>0중단·reopen,그외sidecar삭제→rename→reopen. 실패공통handler는임시정리false/모든위치즉시reopen보장아님.52선택명령.
- COMPACTION-PHASES: sequence최소ID/frameposition·ID순/진행job·반복3guard/12enum단계. 이전root반절prefix/contiguousprefix·다음frame대응으로새root후보/상대flags·점·연결·상세복사. PlainRanks는AO·Index·selectable·type·정수Flags/removed/범위/num좌표·연결set대응,기존base때유효moved좌표재검사. check→moved병합저장→remove재검사callback ID만삭제→단일동등상세정리. 기존moved는dummy좌표로ID만수집→root실좌표map→재해독→새targetaddAll우선.178선택명령. 프레임압축/DB재작성실행안함.

앞서 완료한 근거도 재사용:

| 보고서 접두어(AOT-…-2026-10-15.md) | 확인 범위·주의 |
|---|---|
| OBJECT-TWEEN-PAIR-TRACE | 앞AO 기준/수동link우선→동일ID/미대응skip. Index위치→뒤첫Index→앞좌표유지. 새객체/선형좌표/tScale·glow정수화/앞그룹ID. ObjectScale일괄lerp단정금지.64선택명령. |
| PLAYBACK-BUFFER-TRACE | Frame sourceindex LRU100/읽은점500000·2frameguard. output Picture/Image별예산64MiB·120/6ms,finishAhead최초1변환. plan쌍identity/clock과export분리.90명령. |
| FILL-MOVED-CODEC-TRACE, ROOT-RELEASE-TRACE | fillzlib/v1/U7/ZigZag/optional64bit;NaNt→null→0/1,−0→+0. moved연속run/첫delta+signedbit정수잔차(XOR아님). root해제1ref&&2N<R/잔여구체화/drop.공동102명령. |
| PERSPECTIVE-SELECTION-CUSTOM-TRACE | visibleT2/활성bucket/bboxinflate18·min48→inflate26거리²≤676/score8d²+.0015area+.015center². anchor/fallback우선순위3/1/0,여유9. customdirty→saveCurrent차이.80명령. |
| PERSPECTIVE-WARP-TRACE | source/destination signed축반전bilinear우선/projective실패전체fallback;validquad距離>2,볼록검사아님. 일반좌표저장/올가미AllGroup별도.130명령. |
| CONNECTED-TARGET-REFLECTION-TRACE, ALLGROUP-BOX-TRACE, MOVEMENT-DISPATCH-TRACE | closure/AO중복제거·반사/레이어필터·상자속성모서리loop/pose·stretch·branch·BuildTree.상세는역사handoff링크.공동175명령. |
| DRAW-GLOW-TRACE, GROUP-SHADER-TIMELINE-TRACE, EXPORT-DISPATCH-TRACE | DB공급/정렬COALESCE(draw_order,id),id/비연속그룹단위/shader11=d1/sigma,10=W/2,12일반0링1/blend상속/출력FPS timeline. |
| FILL-TWEEN-TRACE, FILL-PATH-TRACE | fill대응·held앞t<1/뒤t1·경계실패t.5선택+색보간/outer실패전체null·hole실패생략/evenOdd·difference. |
| RENDER-CONTEXT-TRACE, SAVED-VALUES-TRACE, SHARED-RESTORE-TRACE, ROOT-FLAGS-LAYER-SWAP-TRACE, LAYER-MEMORY-TRACE | 좌표/DPR/속성저장·공유복원/레이어교환·표시토글DB연결.別lockUI미식별. |

모든 audit는 선택 명령 일치이며 전체 함수/실제 앱/pixel 검증 아님. 보고서 간 중복 표본을 독립 누적 합산하지 않는다. GDT slot만으로 concrete target 메서드명 추정 금지. float폭·Smi와 실제 명령 우선. 공유 Flutter annotation에 속지 않는다.

## 다음 실제 작업·미완

현재 다음 단계는 [근거 통합·검증 준비](docs/ANALYSIS-READINESS-2026-10-16.md). [기계 판독 색인](docs/FEATURE-CONTRACT-INDEX-2026-10-16.json)은 기존 근거만 재분류했다. 원본 분석 캐시 복구 전 아래 미완을 새로 확정할 수 없다. 정적 미수행을 실물 전용으로 바꾸거나 전체 완료로 처리하지 않는다.

1. LAYER-MERGE-DELETE-ADD 정상경로도추가완료: 목록위치직전layer로병합,AO대표source/target각sort→target먼저+source뒤→기존effectiveorderkey정렬슬롯을각AO모든frame인스턴스에배정.1부터새번호아님. frame별SaveFrame→전역LayerId갱신·definition삭제→commit/cache무효화/reload/history전부clear후entry. delete는layer둘이상/sequence전체AO·fill·기반참조·incoming/outgoing·상세·definition삭제/historyclear. add는DB최대+1/메모리열린layer충돌회피/모든frame에visibletrue·lockedfalse로정의추가.138선택명령.
2. 삭제보조도확인: root의비삭제AO source가삭제AO의실제override target을가리키면source를가상ID로먼저구체화;실제override/removed없는가상targetincoming별도삭제;범위실제삭제점removed표시. fill공유withoutFigures는영향outer0이면빈segment storedregion유지/영향hole만제거,SQL기존행은outerregion행삭제/hole segment삭제로표현차이. 전체실패·수명보장은아님.
3. EDITOR-MENU-DELETE-CALLER(65선택명령)추가확인. _buildCurrentFrameDialog는실제callback상도구모드·속성·배경·축/zoom/snap·레이어surface다. 이름으로frame복사/삽입버튼이있다고가정한이전‘다음’을정정한다. 실제tap4perspective/5fill/7tween,panstart4perspective/6AllGroup/7tween. 나머지mode이름추측금지. 선택객체삭제는활성anchor→연결AOIDset+자기소유AO→현재frameAO필터→transaction DeleteAnchorPointsOfFigures/removeWhere/prune/SaveFrame→historyentry. layer전역삭제와구분.
4. 다음실제미완: time-axis frame추가·복사·삭제의구체caller를먼저찾기(현재FrameDialog를그입구로가정하지마),DataAccess._cleanupUnusedAnimationObjects0x3662a4,Frame.GetFastHash0x51cb64 포함필드/무효화. _deleteAnchorPoint0x3608b0의note→연결/점삭제→removed기록기본흐름은ROOT-FLAGS-LAYER-SWAP에이미있으므로반복하지않음. 다른frame보호·전체수명은별도미완. 먼저기존보고서의완료세부와대조해새분기만. 전체UIcoverage·오류/외부수정·전체수명·dynamicactualtarget미완유지. 기존compaction/Rewrite/undo/레이어정상경로재분석반복금지.
5. 상세변형fallback GDT+0x85e4 actualgetter는 기존 cache에 selector↔target표가 없어 미해결. Adopt layer fallback도 같은 selector지만 대상class다름. ‘첫점/첫레이어’ 단정금지. 완전 재decompile 반복금지.
6. 일반AO 앞뒤/별도 lock toggle UI 미식별. 같은 PP/이름검색·생성DrawOrder 재추적 반복금지. 새로운 구체 caller가 있을 때만 추적.
7. codec malformed입력/overflow/전체객체수명/동시·DB실패 보장,모든곡선·그룹glow·backend pixel·UI실결과는 미완. 정적미수행을 실물로만 가능한 것으로 분류하지 않는다. license4지속편집차단 유지/사용자추가시험요청없음.

## 캐시·검증·보호

- 활성 checkout /workspace/scratch/5a16c98ed7ee/AI-sfa-publish는 main clone으로 복구. 현재 private-trace에는 정리/문서검사만 있고 이전 ELF 검증 스크립트는 없다. 기존 dirtyworktree는 현재 관측되지 않으며 삭제/reset을 실행하지 않았다.
- **현재 없음(과거 경로):** AOT/ELF /workspace/scratch/e23c9fd610d3/private/{blutter_out,input/arm64-v8a/libapp.so,venv,depsroot}. asm/sfa,pp.txt,objs.txt는 복구되면 재사용. 현재 없음. 완전 재decompile·도구 재설치는 사용자 금지 범위여서 진행하지 않았다. 원본 APKS/계측 배포 ZIP은 백업 목록에 있으나 분석 캐시 백업으로 확인되지 않았다.
- 과거 shader /workspace/scratch/6d77389e706a/private/glow.frag도 현재 없음. 복구 시 binary:cat금지. 원본apk6d77389e706a/evidence,계측tools37921248d0d6/private,비공개ZIP25b8ca176661/output. 상세이력은이전handoff/ANDROID-INSTRUMENTATION-BUILD/FLUTTER-TOOLS-RESULTS보고서.
- 과거 ELF대조GROUP57/HISTORY178/REBASE62/REWRITE52/PHASES178/LAYER138/EDITOR65통과기록은기존audit다. 현재변경은기존근거색인·문서정정뿐이며새ELF검사는없다. 링크·JSON·diff검사통과후main반영. 코드변경시에만필요검사: python -m unittest discover -s tests -v. 기존unit/probe반복하지않음.
- 잔여주간사용량조회불가. 인수인계추천시체크포인트저장후docs/HANDOFF-PROMPT.md제공. 다음대화에서도자율진행지시유지.
