# AI-sfa working instructions

Read HANDOFF.md first for current scope and evidence. Keep it current at meaningful checkpoints.

- User-facing communication and project guides: Korean.
- Priority (2026-10-16 사용자 전환): (나) 분석형 스타일 학습 — 이펙트·연출·배경 우선, 뿌리 yutaka_nakamura(이펙트·배경·연출; 에반게리온 제외, 구작·최신작 공통 방식 가중; **impact_frames는 판정 '맞음'이면 연필·디지털·단색섬광 모두 학습 자료로 쓴다(2026-10-20 사용자, 이전의 '4B 연필만' 규칙 대체). 중요도 순위는 나중에 정하며 302394(비질란테)는 기본 낮음 — 최중요**)·nian41(**몸 뼈대 움직임 1순위**(옷·머리카락·장식·근육·얼굴 제외); 2026-10-20부터 배경·이펙트·연출 **보충 자료**로도 포함, 그림체는 제외). **배경·이펙트·연출은 나카무라가 압도적 1순위**이고 다른 애니메이터(nian41·riooo·optical-core·yukina_kosaka)는 나카무라에 없거나 적은 부분을 보충한다(2026-10-20 사용자, docs/PRIORITY-TIERS-2026-10-20.md). 현재 계획은 docs/STYLE-LEARNING-PLAN-2026-10-16.md, 후보는 docs/ARTIST-CANDIDATES-2026-10-16.md. 추가 애니메이터는 사용자 승낙 후에만 포함(2026-10-18 승낙: riooo — 규모 큰 전투씬의 이펙트·연출만, 인체·불 이펙트 제외; optical-core — 이펙트·연출만, 인체 제외. yukina_kosaka — 이펙트·연출·연필 임팩트, 인체 제외. 반려(원본 삭제): katsumi_ishizuka·sota_shigetsugu·isuta_meister. 범위는 docs/INTAKE-PROCEDURE-2026-10-18.md §4). 영상 원본은 저장소에 넣지 않고 분석 뒤 임시본을 지운다. Stick Fighter 기능 분석 결과는 생성 제약으로 재사용한다.
- Distinguish stored-state probes, inferred algorithms, and actual app/UI verification.
- Do not publish provided APKs, other users' animation/video originals, or decompiled app source.
- FPS order is (tween_fps, playback_fps).
- Run tests from repository root: `python -m unittest discover -s tests -v`.
- Generated probe files are reproducible with `python build_feature_probes.py`.
- Fetch current remote state before changing GitHub; preserve unrelated work.

## Accuracy-preserving token and handoff discipline

- Treat HANDOFF.md as a compact current-state entry point. Replace obsolete next steps; move historical detail to docs/history rather than appending it indefinitely. Preserve corrections and evidence in dedicated reports.
- In a new conversation, read HANDOFF.md and this file, then the named current report. Follow topic-specific links only as needed. Explicit user reading requests still take precedence.
- Within a conversation, reuse successfully read content and verified SHAs. Reread only when missing context or a possible change affects the decision. Do not reparse unchanged originals merely to recreate established counts.
- Print narrow excerpts and summaries. Filter tool metadata by exact names before printing; never dump the full registry. Inspect large JSON/XML/strings programmatically and return only relevant rows/counts. Keep original source, images and full dumps private.
- Batch independent reads; keep dependent analysis and writes sequential. Use purpose-built tools or local scripts when they reduce work without weakening verification. Do not add agents or skills solely to save tokens.
- Check known local evidence/cache paths before redownloading or decompiling. Reuse valid tools/extraction results in the same run. If absent, recover only files needed for the current question.
- Run relevant checks after a change, once. Repeat only after new changes, failures or unresolved concerns. Do not regenerate probes for documentation-only edits.
- Save meaningful findings, source locations, verification scope and remaining uncertainties. Avoid vague confidence percentages. A hypothesis must not silently become a confirmed rule during compaction.
- A handoff must state current priority, exact next action, blockers, protected files, environment/cache availability and validation status. Supply docs/HANDOFF-PROMPT.md when recommending a new conversation.
- Recommend a new conversation when repeated stale context, conflicting plans or bulky history make it more efficient. Do not claim automatic knowledge of remaining context capacity or promise zero degradation. Complete and persist the checkpoint first.

## Concrete low-output tool discipline

- Before retrieving broad commit/PR metadata, determine which fields are needed. Filter returned structures inside the tool call and print only those fields; do not print diffs or full audit JSON to obtain a SHA.
- For structured multi-file writes, keep content inside the orchestration call. Preserve UTF-8 rather than expanding Korean into Unicode escapes. Check for truncated command output before parsing or writing; do not repeat a large dump after a truncation without changing the transfer approach.
- Use relevant tools/skills when they improve accuracy or reduce unnecessary work. Tool discovery/loading is selective, and does not by itself justify redundant downloads or repeated reads.
- When new wasteful behavior is observed, update this guidance and the compact handoff at the next meaningful checkpoint. Keep performance/verification limits explicit rather than sacrificing accuracy to reduce tokens.

- For large assembly reads, count/select semantic annotations or address windows before printing. Size the output budget to the selected excerpt; if truncated, recover only the missing address window. Trace a closure’s enclosing function before treating its name as a global planner rule.

## Standing GitHub authorization — 2026-10-15

- The user explicitly approved publication of the AOT path report and granted standing authorization for future changes of the same scope: directly authored analysis reports, aggregate metadata, and handoff/workflow documentation in twoapple08/AI-sfa main.
- Continue those authorized writes without repeatedly asking for permission. Preserve remote changes and use an expected-head check. This authorization does not change system approval settings or guarantee automatic approval.
- This does not authorize publication of APK/SFA/video originals, decompiled source, assembly dumps, or changing protected predictions, optimizing File-2, training, or AI integration. If automatic review rejects an action despite the standing authorization, do not bypass it; report the stated reason.

- Do not infer remaining weekly usage or a number of available turns. The assistant cannot inspect that quota here. When the user reports a low budget, persist a concrete checkpoint and provide the current handoff prompt. User Android setup is already verified: do not repeat installation, pairing, getprop, or APK inventory unless a changed environment or connection failure requires it.

- APK 재패키징은 서명 성공만으로 완료로 세지 않는다. 최종 APK의 원본 lib/assets/res/resources.arsc 및 미수정 dex 항목 보존을 대조한다. raw-resource 빌드의 파일 누락 여부를 확인하고, 중간 실패본은 전달하지 않는다. Manifest는 전체 덤프 대신 package/provider/permission/component의 필요한 항목만 출력한다.

- AOT에서 double 인수 의미는 SetupParameters 요약만 믿지 말고 실제 mov/stur/ldur와 호출 시 재배치로 연결한다. uniform·단위·BlendMode는 초기 상태/상속/실행 상태를 구분한다.

- 함수가 짧아 보여도 파일 전체 cat 전에 줄수/크기를 확인한다. AOT는 함수 주소창/선택 주석만 출력하고 긴 문자열은 별도 요약한다. 큰 파일의 반복 truncation이나 HANDOFF의 과거 체크포인트 누적이 생기면 역사 문서에 보존하고 현재 입구를 압축한다.

- AOT float 상수는 요약 d0=값만으로 읽지 않는다. ldr sN/str sN이면 PP 원시32비트를 IEEE754 Float32로, ldr dN이면64비트로 해석한다. scalar 폭·리터럴·fcvt/저장슬롯을 확인하고, 특히 0.000000 요약과 IMM 원시비트가 다르면 원시 명령/폭을 우선한다. GDT 슬롯번호는 클래스별로 다른 메서드에 재사용될 수 있어 번호만으로 메서드명을 일반화하지 않는다.

- 셰이더 asset 등 확장자만으로 텍스트를 가정하지 않는다. 먼저 file/바이너리 식별자·크기를 확인하고 필요한 텍스트 본문이나 메타데이터만 골라 읽는다. binary에 cat/sed를 실행해 전체 바이트를 출력하지 않는다.

- PP 문자열/annotation은 필요한 주소·길이 제한으로 먼저 선택한다. 주소창 출력은 실제 명령을 우선해 중복 요약과 긴 문자열의 truncation을 피한다. 원격에 같은주제 체크포인트가 생기면 먼저 대조하고 추가근거만 보충하며, 중복표본수를 합산하지 않는다.

- 긴 함수의 주석 필터도 결과가 클 수 있다. 출력 전에 선택 결과 개수를 확인하고 출력 상한을 적용한다. 잘린 결과를 전체 재출력하지 말고 필요한 호출·필드의 주소창만 읽는다.

## Autonomous continuation — 2026-10-15 20:32 KST

- 사용자는 혼자 처리 가능한 일을 전부 진행하라고 반복 명시했다. 작은 보고서·커밋 하나가 끝났다는 이유만으로 다음 작업을 안내하고 턴을 끝내지 않는다. 확인 가능한 미완 항목을 계속 처리하며 의미 있는 체크포인트는 중간에 저장한다. 실제 차단 요인과 아직 수행하지 않은 일을 구분한다.
- PC는 20:26 KST 사용자 보고로 현재 사용 불가다. 이전 PC 사양/준비를 현행 가용 환경으로 전제하지 않는다. 휴대폰 재설치·페어링·시작 시험이나 기존 영상 반복을 요청하지 않는다.

- callback inventory는 긴 PP 원문 대신 주소·짧은 대상명·인수만 출력한다. 여러 주소창을 합치기 전 실제 명령 행수와 긴 SQL/PP annotation 길이를 예산에 반영한다. 보통0x200(128명령) 창을 기본으로 하고, 잘린 부분만 회수한다. 함수 이름의 ‘FrameDialog’를 시간축 frame복사/삽입 메뉴로 가정하지 말고 실제 callback 역할부터 확인한다.

## Environment continuity — 2026-10-16

- ‘캐시 정상’은 영구 보장이 아니다. 이번 환경에서는 지정된 과거 private 경로가 없어 공개 repo만 복구했다. 최신 HANDOFF/ANALYSIS-READINESS의 현행 관측을 우선한다. 자료가 없으면 본문 의미를 추측하거나 과거 audit를 새 ELF 검사로 표시하지 않는다. 원본 APKS 보유와 AOT/PP/objs/도구 캐시 보유를 구분한다. 사용자 금지인 설치·전체 재decompile·기존 시험 반복으로 차단을 우회하지 않는다.
- 저장소 tree/Library 목록은 필요한 경로·이름·크기만 필터 출력한다. raw 전체 tree/metadata/도우미 본문 출력은 피한다. 기존 근거를 정리한 색인은 새 함수 분석이나 runtime 검증으로 세지 않는다.

## 서버 분석 환경 복구 상시 예외 — 2026-10-16 02:02 KST

사용자가 명시했다: “서버 분석 도구 복구를 위한 설치·다운로드·AOT 재추출은 예외로 허용해”. 이 허용은 다음 인수인계/대화에도 유지한다. 서버 캐시·도구가 없거나 손상된 경우 분석 도구/의존성 설치·다운로드·원본에서 AOT 재추출을 복구 목적으로 진행할 수 있다. 같은 복구 범위의 허용을 다시 묻지 않는다. 사용 가능한 캐시가 있으면 계속 우선 재사용하며 불필요한 전체 재추출은 하지 않는다.

휴대폰 재설치·페어링·getprop·시작 시험·기존00–05 영상/SFA 재분석 금지는 그대로다. 라이선스 우회, 비공개 원본/역컴파일물 공개, PREVIDEO/File-2 변경, 학습·AI 연결을 허용하는 예외가 아니다. 과거 자동 검토 거절은 새 명시적 허용 이전의 기록이며, 새 허용 근거로 복구를 다시 시도할 수 있다. 시스템 자동 승인 통과를 보장하지 않으며 새 거절은 우회하지 않는다.

## 반복 방지 지시의 정확한 의미 — 2026-10-16 02:06 KST

사용자가 정정했다: “이미 분석완료했고 할필요없는 작업을 너의 오판으로 또하지 말라는 뜻”. 작업 종류 자체의 일률적 금지가 아니다. 완료된 분석·시험·설치 결과는 재사용하고, 같은 결과를 얻기 위한 불필요한 반복을 하지 않는다. 실제 환경 소실·새로운 미해결 질문·유효하지 않은 기존 근거 등으로 필요한 재작업은 이유와 범위를 확인해 자율 진행한다. 같은 범위의 허용을 다시 묻지 않는다.

이 정정은 이 문서와 과거 보고서의 ‘재설치/페어링/기존 영상 재분석 금지’라는 포괄적 표현보다 우선한다. 현재 휴대폰 재설치·페어링이나 기존 영상 재분석이 필요하다는 근거는 없으므로 요청/반복하지 않는다. 서버 분석 캐시가 실제로 없는 것은 확인됐으므로 필요한 설치·다운로드·AOT 복구를 진행한다. 라이선스 우회·원본 공개·보호 자료 변경·학습/AI 통합까지 허용한 뜻은 아니다.

## 3자 협업 상시 허용 — 2026-10-16

사용자가 Claude·GPT·Gemini 각각에게 지시했다. (1) 품질을 최대로 유지하며 토큰을 아낄 수 있다면 외부 프로그램·도구·스킬 등 모든 수단을 허용한다. (2) 품질을 높일 수 있다면 모든 수단을 허용한다. (3) 작업 전에 그 작업에 가장 알맞은 모델·추론 강도 설정을 먼저 알린다. 품질·검증을 희생한 절약은 허용 범위가 아니다. 원본·역컴파일물 공개, 라이선스 우회, 보호 자료 변경, 시스템 승인·안전 정책 우회는 여전히 금지다. 학습 방식은 변경 예정이며 새 방식의 상세는 아직 전달되지 않았다. 외부 AI용 설명서: docs/AI-COLLAB-BRIEFING-2026-10-16.md.

**조정 권한 (2026-10-17 사용자 지시):** "조정사항이 있을 시 조정은 모두 Claude에게 맡김." GPT·Claude·Gemini 역할 배정과 충돌 조정은 Claude가 결정하고 docs/COORDINATION-*.md에 기록한다. 사용자의 새 지시가 항상 우선한다.

**로컬 포즈 추정 허가 (2026-10-17 19시 KST 사용자):** PC방 GPU(RTX 4060)에서 "가장 빨리 되는 것" — 이미 만들어진 포즈 모델(YOLO11-pose)로 nian41 영상의 관절 좌표를 **추론만** 하는 것을 허가. 모델 학습(분류기·스타일 AI)은 이 허가에 포함되지 않는다. 공용 PC에 계정·토큰을 남기지 않는다. 실행 파일: tools/pose_extract.py.

- 하위 판정자(Agent) 대량 투입 전 토큰 비용을 먼저 추정해 사용자에게 알린다. 이미지 시트 판정은 판정자 1명당 약 75k–120k 토큰이 들었다(2026-10-20 동작 세기 36명 계획 → 사용자 중단). 표본 먼저, 간격·인원 최소화.

## 최종 목표 — 2026-10-21 사용자

기기 안에서만 도는 앱(APK·EXE)에 창작 AI를 넣는다. 태그·자연어·스토리보드 프롬프트를 받아 .sfa 애니메이션을 만든다. 서버 모델이 아니라 기기 안에서 돌아야 한다. 분석 결과는 이 AI의 작곡 지식이 된다. 상세는 docs/HANDOFF-PROMPT.md의 '최종 목표'에 있다. 앱에 AI를 넣거나 모델을 학습하는 일은 사용자가 따로 허가해야 한다(현재 미허가).
