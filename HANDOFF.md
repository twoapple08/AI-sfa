# AI-sfa 현재 인수인계 — 2026-10-15

## 목표·권한·금지

- 한국어. 목표는 Stick Fighter51.0.0의 모든 창작·편집 기능 분석과 실제 앱 검증. 최소 생성기/렌더 근사로 축소하지 않는다. 사쿠가 수집·학습·AI 연결 보류.
- 사용자는 혼자 가능한 일을 전부 자율 진행하라고 반복 지시했다(최신20:32 KST). 작은 보고서·커밋마다 ‘다음은…’으로 턴을 끝내지 않는다. 미수행과 실제 차단을 구분한다. 모든 독립 분석이 끝났다는 거짓 완료 금지.
- 직접 작성 보고서·집계·작업지침 main 반영 상시 승인. 최신 remote head/tree 확인·expected_sha 보호·다른 변경 보존. 자동승인 거부 우회 금지.
- APK/SFA/영상 원본·역컴파일 소스/assembly·키·전체 로그 공개 금지. PREVIDEO 예측은3278146 고정, 정답에 맞춰 수정 금지. File-2 최초100%조건 미충족: 최적화/재압축/삭제/병합/원본수정 금지.
- FPS=(트위닝,재생). 굽힘 기능 없음. 음수/화면밖 좌표 임의 삭제·중앙 이동 금지. 레이어 UI는 전체 프레임 제작 보조. 편집 공간과 출력 사각형 구분.
- 기존00–05 영상·SFA 시험/분석은 완료한 범위 재사용. 재설치·페어링·getprop·폰 시작 시험·기존 영상 분석·새 작품/제작자 문의 반복/요청 금지. 문서 변경만으로 unit/probe 재실행 금지.

## 현재 환경과 차단

- 사용자20:26 보고로 PC 현재 없음. 이전 i7-8700/1050Ti/16GB를 가용 환경으로 전제하지 않는다. 폰 Wi-Fi는 학교망 제약. 서버 AOT/ELF/Capstone 캐시는 정상이며 PC 소실과 다르다. 지금 사용자 추가 작업 없음.
- 계측 앱은 Gadget/Flutter/libapp 로드까지 실물 확인됐지만 Play license 응답4로 지속 편집 차단. 응답4의 정확한 서버 뜻은 미확인. 검사 우회 안 함. 원본00–05 실제 UI/출력 표본은 존재하므로 ‘앱 시험 전혀 없음’으로 쓰지 않는다.
- 원본 com.sG.stickfighter.activities51.0.0/code51000, min24/target36/user0/ARM64, Android16/SDK36/비루팅 이력. 학교망에서 현재 무선ADB 가능하다고 가정하지 않는다. 계측 com.twoapple08.sfa.instrument Test5는 원본보호242대조·서명/정렬 통과, 비공개 전달 완료. 재빌드 필요 없음.

## 현행 읽기 순서와 체크포인트

AGENTS.md → docs/AOT-COMPACTION-PHASES-TRACE-2026-10-15.md → 필요한 주제 보고서만 읽는다. 기능 구분은 docs/FEATURE-EVIDENCE-MATRIX-2026-10-15.md. 이전 전체 handoff는 docs/history/HANDOFF-2026-10-15-before-group-history-rebase.md에 보존했다. 과거의 ‘다음’은 현행 지시가 아니다.

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

1. 새 UI 명령에서 바로 이어갈 구체 경로: main `_mergeLayerDown`0x5b86f4/`_deleteSelectedLayer`0x5bb280/`_addLayer`0x5b9e04. 새 callback inventory에서 찾았으며 반복PP검색아님. merge는GetFramesForSequence/필요frame AO·fill로드→SaveFrame scope→MoveLayerObjectsGlobal0x5b9b34→DeleteLayerDefinitionsGlobal0x5b9a68→commit→cacheevict/reload→history전부clear/현재entry기록. 아직몸체세부미검증. delete는DeleteLayerGlobal0x5bb4ec→선택초기화/cache갱신/historyclear. add는GetNextLayerIdForSequence0x5ba2bc→AddLayerToAllFrames0x36c3c8. SQL/메모리 guard/연결·fill처리남음.
2. 일반undo/redo 정상stack·asyncguard/compaction정상단계·PlainRanks·moved병합/DBRewrite는이번보고서범위를읽었으므로처음부터반복하지마. 전체UI command coverage·hash내부필드/동적호출actualtarget·오류/외부수정·전체객체수명보장은별도미완.
3. 상세변형fallback GDT+0x85e4 actualgetter는 기존 cache에 selector↔target표가 없어 미해결. Adopt layer fallback도 같은 selector지만 대상class다름. ‘첫점/첫레이어’ 단정금지. 완전 재decompile 반복금지.
4. 일반AO 앞뒤/별도 lock toggle UI 미식별. 같은 PP/이름검색·생성DrawOrder 재추적 반복금지. 새로운 구체 caller가 있을 때만 추적.
5. codec malformed입력/overflow/전체객체수명/동시·DB실패 보장,모든곡선·그룹glow·backend pixel·UI실결과는 미완. 정적미수행을 실물로만 가능한 것으로 분류하지 않는다. license4지속편집차단 유지/사용자추가시험요청없음.

## 캐시·검증·보호

- 활성 checkout /workspace/scratch/5a16c98ed7ee/AI-sfa-publish. 선택명령 검사 /workspace/scratch/5a16c98ed7ee/private-trace. 기존dirtyworktree와다른체크아웃보존/reset금지.
- AOT/ELF /workspace/scratch/e23c9fd610d3/private/{blutter_out,input/arm64-v8a/libapp.so,venv,depsroot}. asm/sfa,pp.txt,objs.txt재사용. 원본추출·Blutter설치/전체재실행필요없음. 도구gdb없음.
- shader /workspace/scratch/6d77389e706a/private/glow.frag는binary:cat금지. 원본apk6d77389e706a/evidence,계측tools37921248d0d6/private,비공개ZIP25b8ca176661/output. 상세이력은이전handoff/ANDROID-INSTRUMENTATION-BUILD/FLUTTER-TOOLS-RESULTS보고서.
- 이번변경은문서·명령audit뿐. ELF대조GROUP57/HISTORY178/REBASE62/REWRITE52/PHASES178모두통과. 링크·JSON·diff검사후main반영. 코드변경시에만필요검사: python -m unittest discover -s tests -v. 기존unit/probe반복하지않음.
- 잔여주간사용량조회불가. 인수인계추천시체크포인트저장후docs/HANDOFF-PROMPT.md제공. 다음대화에서도자율진행지시유지.
