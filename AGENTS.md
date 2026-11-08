# AI-sfa working instructions

Read HANDOFF.md first for current scope and evidence. Keep it current at meaningful checkpoints.

- **신규 참여자 인계(2026-11-04 사용자 요청):** `docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md`, `docs/SESSION-COMPLETE-HANDOFF-2026-11-04.md`, `.claude/skills/stickman-extraction/START-HERE.md`에 목적·전체세션·현행결정·재현·최신개발자료를 모았다. 원본/좌표/결과는 스킬 `private-data/`에 실제로 두되 Git 제외/Drive 보존한다. 24사례는같은영상의개발자료로 held_out=false/training_ready=false이며새영상일반화/자동정답으로승격하지않는다. 과거스킬원문은 references/HISTORICAL-SKILL-THROUGH-2026-11-04.md,현행결정은새SKILL.md를따른다. 상세권한·작가범위는이문서의전체규칙을그대로적용한다.

- User-facing communication and project guides: Korean.
- **GPT→Claude 전달(2026-11-02 사용자 상시 요청):** Claude에게 전달할 GPT 토론 답변은 요약하지 않은 전체를 `docs/` 문서로 현재 지정 브랜치에 저장하고, 저장 확인 뒤 사용자에게 GitHub 링크와 복사할 전달 문구를 함께 준다. 현재 지정 브랜치는 `claude/new-session-gknz4t`이며 main에 쓰지 않는다. 이후 사용자가 브랜치나 전달 방식을 바꾸면 새 지시를 따른다.
- **Claude→GPT 답장 프롬프트(2026-11-03 사용자 상시 요청):** GPT 토론에 답(차수 답·보완)을 쓸 때마다 GPT에게 보낼 답장 프롬프트를 함께 만들어 `docs/GPT-PROMPT-*.md`에 저장하고 사용자에게 복사할 블록으로 준다. GPT는 GitHub 저장소와 Google Drive를 직접 볼 수 있으므로, 내용을 붙이지 말고 브랜치·파일 경로·Drive 경로로 가리킨다. 사용자가 새 GPT 세션용이라고 하면 프로젝트·브랜치·읽을 순서·지킬 것·저장 위치까지 담아 그것만으로 시작할 수 있게 쓴다(예: docs/GPT-PROMPT-ANIME-TO-STICKMAN-ROUND9-FRESH-2026-11-03.md).
- Priority (2026-10-16 사용자 전환): (나) 분석형 스타일 학습 — 이펙트·연출·배경 우선, 뿌리 yutaka_nakamura(이펙트·배경·연출; 에반게리온 제외, 구작·최신작 공통 방식 가중; **impact_frames는 판정 '맞음'이면 연필·디지털·단색섬광 모두 학습 자료로 쓴다(2026-10-20 사용자, 이전의 '4B 연필만' 규칙 대체). 중요도 순위는 나중에 정하며 302394(비질란테)는 기본 낮음 — 최중요**)·nian41(**몸 뼈대 움직임 1순위**(옷·머리카락·장식·근육·얼굴 제외); 2026-10-20부터 배경·이펙트·연출 **보충 자료**로도 포함, 그림체는 제외). **배경·이펙트·연출은 나카무라가 압도적 1순위**이고 다른 애니메이터(nian41·riooo·optical-core·yukina_kosaka)는 나카무라에 없거나 적은 부분을 보충한다(2026-10-20 사용자, docs/PRIORITY-TIERS-2026-10-20.md). 현재 계획은 docs/STYLE-LEARNING-PLAN-2026-10-16.md, 후보는 docs/ARTIST-CANDIDATES-2026-10-16.md. 추가 애니메이터는 사용자 승낙 후에만 포함(2026-10-18 승낙: riooo — 규모 큰 전투씬의 이펙트·연출만, 인체·불 이펙트 제외; optical-core — 이펙트·연출만, 인체 제외. yukina_kosaka — 이펙트·연출·연필 임팩트, 인체 제외. 반려(원본 삭제): katsumi_ishizuka·sota_shigetsugu·isuta_meister. 범위는 docs/INTAKE-PROCEDURE-2026-10-18.md §4). **인체 제외 이유(2026-10-28 사용자):** 캐릭터는 작품의 개성이라 그림체·비율이 작품마다 다르다(애니메이터가 같아도). 이펙트·연출은 대부분 애니메이터 본인 스타일대로라 작품이 달라도 같은 신호다. → 캐릭터 그림은 누구 것이든 화풍 학습에서 빼고, 장면 설명서에는 인물의 자리·상호작용(물듦·가림·타격점)만 남긴다. 같은 애니메이터의 이펙트 특징이 작품끼리 비슷하면 본인 스타일, 다르면 작품 요인으로 본다. 영상 원본은 저장소에 넣지 않고 분석 뒤 임시본을 지운다. Stick Fighter 기능 분석 결과는 생성 제약으로 재사용한다.
- Distinguish stored-state probes, inferred algorithms, and actual app/UI verification.
- Do not publish provided APKs, other users' animation/video originals, or decompiled app source. **예외(2026-10-28 사용자): 사용자가 모은 `.sfa` 파일은 '내보낸 파일 = 공유 동의'로 보고 `data/user_sfa/`(공개)에 보관한다.** 영상 원본·추출 프레임은 여전히 비공개.
- FPS order is (tween_fps, playback_fps). **사용자는 생성물을 항상 (24,24)로 만든다 — 앱 트위닝을 쓰지 않고 24장/초를 모두 직접 그린다(2026-10-25).**
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

- 셸에서 `cat >> 파일`을 입력(heredoc) 없이 쓰지 않는다. 2026-11-04 Claude도 같은 실수로 명령 묶음이 멈춰 TaskStop했다(빈 파일 생성). 표준입력을 기다리며 명령 묶음 전체가 멈췄다(2026-10-26, 두 번). 파일 덧붙이기는 heredoc이나 Edit로만.

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
- **PC방 PC 사양(2026-10-27 사용자 작업 관리자·탐색기 캡처):** RTX 5060 8GB(전용) + GPU 1(사용 0%), RAM 31.6GB, CPU 4.41GHz, 드라이버 32.0.15.9597. 디스크: C 79.8GB 중 52.4GB 여유, D(LV-MA) 14.5TB 중 8.12TB 여유, S 19.9GB 중 3.99GB 여유. 작업 폴더는 C 권장(D·S는 PC방 공용일 수 있음). 시간이 짧으니 설치·실행을 bat 하나로 빨리. 5060은 CUDA 12.8용 PyTorch 필요. 공용 PC라 계정·토큰을 남기지 않는다.
  - **GPU 가용성(2026-10-28 밤 사용자):** 당분간 GTX 1050 Ti(4GB)만 상시 사용 가능, 5060은 가끔 2시간 미만. 영상 모델 학습·생성의 주 GPU는 Kaggle T4×2로 계획한다.
- PC는 20:26 KST 사용자 보고로 현재 사용 불가다. 이전 PC 사양/준비를 현행 가용 환경으로 전제하지 않는다. 휴대폰 재설치·페어링·시작 시험이나 기존 영상 반복을 요청하지 않는다.

- callback inventory는 긴 PP 원문 대신 주소·짧은 대상명·인수만 출력한다. 여러 주소창을 합치기 전 실제 명령 행수와 긴 SQL/PP annotation 길이를 예산에 반영한다. 보통0x200(128명령) 창을 기본으로 하고, 잘린 부분만 회수한다. 함수 이름의 ‘FrameDialog’를 시간축 frame복사/삽입 메뉴로 가정하지 말고 실제 callback 역할부터 확인한다.

- **할 일 상시 검토(2026-10-22 사용자):** "너가 더 할 일 없는지 항상 검토해." 기다리는 동안(Kaggle·사용자 확인 등)에도 지금 자료로 할 수 있는 일을 스스로 찾아 진행한다. 결과가 모여야 의미 있는 일(표본이 적어 치우칠 일)은 기다리되, 그 이유를 말한다.

## Environment continuity — 2026-10-16

- ‘캐시 정상’은 영구 보장이 아니다. 이번 환경에서는 지정된 과거 private 경로가 없어 공개 repo만 복구했다. 최신 HANDOFF/ANALYSIS-READINESS의 현행 관측을 우선한다. 자료가 없으면 본문 의미를 추측하거나 과거 audit를 새 ELF 검사로 표시하지 않는다. 원본 APKS 보유와 AOT/PP/objs/도구 캐시 보유를 구분한다. 사용자 금지인 설치·전체 재decompile·기존 시험 반복으로 차단을 우회하지 않는다.
- private cache 경로는 컨테이너마다 다를 수 있다. 새 대화에서는 과거 `/workspace/scratch/...` 외에 `/root/sfa-cache/extracted` 같은 환경 제공 cache를 먼저 찾고 `CACHE-MANIFEST.json` hash로 대조한 뒤 재사용한다(2026-10-27 확인).
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

- **GPT 분담(2026-10-24 사용자):** "GPT가 더 능률이 뛰어난 부분은 GPT한테 맡겨야 한다, 너가 다 하려고 하지 마라." 그림 눈 판정(장별·구간별 판정 시트), 문장·캡션 작성처럼 GPT가 효율이 좋은 일은 GPT 프롬프트 문서(docs/GPT-PROMPT-*.md)로 넘기고, Claude는 서버 계산(추출·렌더·규칙 반영)과 조정을 맡는다. 현재 분담: docs/COORDINATION-2026-10-24.md.
- **GPT 상시 이용(2026-10-26 사용자):** "GPT를 항상 이용할 수 있으면 이용해, 상시 대기 중이니까." 기다리는 시간·눈 판정·조사·문장 일은 GPT 프롬프트(docs/GPT-PROMPT-*.md, 복붙용 + 붙일 그림 목록)를 먼저 만들어 넘긴다.
  - 사용자가 GPT를 언급하지 않아도, GPT를 쓰는 게 낫다고 판단되면 항상 쓴다(2026-10-26 사용자 재확인). 붙일 그림은 한 장으로 합쳐 파일로 보내고 "이 파일 하나 + 프롬프트"로 안내한다.
- **다 GPT에 맡기지 말 것(2026-10-27 사용자):** "전부 다 GPT한테 맡기면 안 된다, 너가 잘하는 건 너가 해야 해." 대량 눈 판정(태깅)은 GPT, 그러나 GPT 결과 품질 검사(묶음마다 2–3컷 직접 시트 대조)·자료 가공·측정·버그 찾기·학습 설정·결과 평가의 1차 판정과 해석은 Claude가 직접 한다. 평가는 Claude 판정 + GPT 독립 2차 의견 + 사용자 최종.
- **먼저 답하고 계획을 말한 뒤 작업(2026-10-25 사용자):** "작업을 할 거면 계획이라도 얘기하고 대답해." 사용자 질문·제안에는 먼저 답한다. 긴 작업은 시작 전에 무엇을·왜·얼마나 걸릴지 짧게 말하고 시작한다. 답을 뒤로 미루고 작업부터 길게 하지 않는다.
- 하위 판정자(Agent) 대량 투입 전 토큰 비용을 먼저 추정해 사용자에게 알린다. 이미지 시트 판정은 판정자 1명당 약 75k–120k 토큰이 들었다(2026-10-20 동작 세기 36명 계획 → 사용자 중단). 표본 먼저, 간격·인원 최소화.

## 최종 목표 — 2026-10-21 사용자

기기 안에서만 도는 앱(APK·EXE)에 창작 AI를 넣는다. 태그·자연어·스토리보드 프롬프트를 받아 .sfa 애니메이션을 만든다. 서버 모델이 아니라 기기 안에서 돌아야 한다. 분석 결과는 이 AI의 작곡 지식이 된다. 상세는 docs/HANDOFF-PROMPT.md의 '최종 목표'에 있다. 앱에 AI를 넣거나 모델을 학습하는 일은 사용자가 따로 허가해야 한다.

**실행 위치 임시 결정 (2026-10-26 사용자, "B로 임시로 정할게"):** 휴대폰은 접근용 화면(프롬프트 입력·결과 보기)이고, 생성은 별도 서버(GPU)에서 돌린다. 위의 "기기 안에서만 도는" 목표는 폐기가 아니라 보류다. 근거: 픽셀 생성 → SFA 변환은 휴대폰에서 몇 초 분량에 몇 시간이 걸린다(추정, GPT 조사로 확인 예정). 나중 후보: 휴대폰은 곡선 조립(가벼운 생성기), 서버는 고품질 모드(섞기). 서버 후보: 집 GPU PC(지금 없음) 또는 쓸 때만 켜는 클라우드 GPU. Kaggle·Colab은 학습·실험용이라 상시 서버로 쓰지 않는다.

**기본 테스트 영상 (2026-10-22 사용자):** 완성된 AI의 기본 테스트는 기준 프롬프트 1이다(`docs/storyboards/bench01_city_landing.json`의 '원문'). 내용은 도시 한복판, 하늘에서 붉은 섬광 후 낙하·착지, 균열과 부유 파편, 뒤로 빠지는 카메라, 솟는 붉은 가시, 걷기→달리기, 순간이동 펀치, 암전이다. 새 모델·도구가 생길 때마다 이 프롬프트로 끝까지 만들어 보고 이전 결과와 비교한다. 사용자가 글을 바꾸기 전에는 원문을 고치지 않는다. 길이·T/F 설정 규칙은 docs/STORYBOARD-SCHEMA-2026-10-22.md를 따르며, 초·최소초는 모두 비워 둘 수 있고 비우면 AI가 정한다.

**허가와 범위 (2026-10-21 사용자):**
- '모든 걸 허용한다': AI 연결(기기용 소형 모델 탑재), 모델 학습·미세조정, 학습용 데이터 가공을 허용한다. 이전 규칙의 '모델 훈련은 하지 않는다(추론만)'와 '학습·AI 연결 금지'를 대체한다.
- 첫 플랫폼은 안드로이드 APK다.
- 사용 범위는 사용자 혼자 쓰는 개인용이다(공개 배포 아님).
- 그대로 지킬 것: 원본 영상·역컴파일물을 공개 저장소에 올리지 않는다. 토큰·키를 출력하지 않는다. 시스템 승인과 안전 정책을 우회하지 않는다.

**뼈대 학습 범위 (2026-10-21 사용자):** 나카무라도 뼈대(몸동작) 학습에 넣는다. 역할은 이렇게 나눈다.
- nian41: 몸 구조와 동작 원리(기본기)
- 나카무라: 타격 타이밍·간격, 그리고 이펙트와 몸동작이 맞물리는 방식. 검출이 어려우므로 정확한 관절보다 '빠름·멈춤' 같은 타이밍 정보 위주로 쓴다.
- riooo·optical-core·yukina의 몸동작은 여전히 세지 않는다.

## 이펙트 그리기 원칙 — 2026-10-21 사용자 재지시(이전 대화 지시가 기록에서 빠졌던 것)

- 이펙트는 **학습한 이펙트 형태를 '수학 함수로 그린 아이젠' 영상 방식으로** 그린다. 그 영상은 Desmos에서 `y=a(x+b)²+c {구간}`·`x=a(y+b)²+c {구간}` 같은 **구간 제한 포물선 조각 수백 개**로 선화를 쌓는다.
- SFA에서는 포물선 조각 = 2차 베지어(TypeId 3)다. 나카무라 이펙트 선화(연기·섬광·파편·충격파·스미어 등)의 윤곽을 포물선 조각으로 맞춰 형태 사전을 만들고, 생성할 때 그 조각들로 그린다.
- 원·직선 같은 기본 도형으로 이펙트를 대신 그리지 않는다(v0.1의 원 충격파·직선 섬광은 이 원칙 위반).
- 추출한 이펙트 형태(다른 작가 그림에서 딴 선)는 공개 저장소에 넣지 않고 Drive에만 둔다. 저장소에는 도구·통계만 둔다.
- **투명도 적극 사용(2026-10-21 사용자):** 색의 알파(반투명)로 그라데이션·색 겹침·번짐을 만든다. 예시는 반투명 짧은 획을 여러 겹 쌓아 하늘·바다를 칠한 SFA 배경이다. 이펙트는 같은 형태를 크기·알파·색을 바꿔 여러 겹 겹쳐(바깥 넓고 옅게 → 안쪽 좁고 진하게) 색감과 번짐을 낸다. 단색 한 겹으로 끝내지 않는다.
- **곡선으로 형태를 만든다(2026-10-25 사용자):** 점 하나하나(픽셀 윤곽)를 따라가지 않는다. 곡선 하나가 길게 휘며 덮고, 선은 곡선+굵기의 선 객체, 채색 면은 성긴 다각형으로 선 아래. 상세: docs/SFA-CURVE-OPTIMIZATION-2026-10-25.md.
- **글로우·투명도가 이펙트 품질의 핵심(2026-10-26 사용자):** "글로우(크기는 그 오브젝트의 선 두께와도 연관)와 투명도 활용을 잘할수록 이펙트 퀄리티가 훨씬 올라간다." 생성 그림의 번짐은 면을 겹겹이 쌓지 말고 안 보이는 곡선의 글로우(굵기 × 글로우 두께로 폭, 반경으로 흐림)와 반투명으로 옮긴다. 고정 글로우 하나로 끝내지 않고 층마다 번짐을 재서 맞춘다. 참고: '배' 파일(굵기 1.0 투명 곡선 + 글로우 두께 97–300).
  - **뜻 정정(2026-10-26 사용자):** "곡선에 그리 집착하지 마. 픽셀 하나당 오브젝트로 채우는 효율 나쁜 짓을 하니까 그런 거야." 곡선 원칙은 '픽셀 윤곽을 점마다 오브젝트로 따는 비효율'을 막는 것이지, 픽셀 그림 생성 → SFA 변환 경로를 버리라는 뜻이 아니다. 생성 방식 문제를 곡선 탓으로 돌리지 않는다.
- **그림 과정 그대로 그리기(2026-10-21 사용자, 참고 sfaclan.com/community/82):** 스틱파이터는 완전한 그림 도구다(선화 → 점을 이은 채우기 영역 → 밑색 → 반투명 명암 여러 겹 → 배경). 생성기도 이 과정으로 그린다: 선 레이어(곡선 테두리), 밑색 채우기 레이어, 명암 레이어(반투명), 배경 레이어(검은 바탕 + 흰 오브젝트 가능). 학습은 이펙트를 '선 + 영역 + 명암 층'으로 분해한 사전, 창작은 그 수식 계수(곡선·명암·색·궤적)를 바꾸고 섞어 새 그림을 만드는 것이다. 덩어리 찍어 붙이기·도형 대용 금지. 조각 수 등 임의 상한을 두지 않는다.

## 전체 학습 결정 — 2026-10-21 사용자

- 모델·도구는 비상업 개인용이므로 라이선스 무관, 최고 품질 기준으로 고른다. 생성 시간 제한 없음(품질 우선).
- 나카무라 관절을 몸 동작 학습 데이터에도 섞는다(이전 '타이밍 위주' 확장).
- 보충 애니메이터(riooo·optical-core·yukina_kosaka) 이펙트를 모두 쓴다. 몸 동작 포함 여부는 확인 대기.
- **임의 상한을 두지 않는다. Colab GPU 등 쓸 수 있는 모든 수단을 쓰고, 혼자 해결하려다 품질을 떨어뜨리지 말고 사용자에게 부탁할 것은 전부 말한다.**
- 준비 계획: docs/PREP-PLAN-2026-10-21.md

## 스틱맨 움직임 — 2026-10-28 사용자
- "내 주된 목적은 스틱맨의 움직임을 다루는 것." 수집 SFA(`data/user_sfa/`)의 주 용도는 스틱맨 동작이고 이펙트·기법 분석은 부수적. 현황: docs/STICKMAN-MOTION-2026-10-28.md
- **용어(11-01 사용자 정정):** **관절점** = 앱 편집 화면의 주황점, 파일 `(Flags & 0x2f) == 0x21`(값 33). 이 점을 축으로 바깥 가지가 꺾인다. **연결점** = 점끼리 이어져(AC) 있지만 관절처럼 꺾이지 않는 점(빨간 점). 이어진 점을 통틀어 '관절'이라 부르지 않는다. 옛 기록의 '관절 연결(10-31 채점)'은 점 연결(AC)을 뜻한다.(SFA 뼈대 추출 → 관절 궤적). 3D는 여전히 거치지 않는다.

## 방향 결정 — 2026-10-23 밤 사용자
- "학습한 게 의미 없어. 캐릭터 빼고 연출이나 이펙트류부터 배워 보게 하자. **3D는 하지 마라.**"
- 3D 동작 모델(MoMask 미세조정)·2D→3D 올리기 경로는 중단한다. 다시 제안하지 않는다.
- 캐릭터 동작은 뒤로 미룬다. 다시 다룰 때도 3D를 거치지 않는다(2D 포즈 추적을 그대로 쓰는 방식).
- 지금 우선순위: **이펙트·연출 학습(2D)**. 자료: 나카무라 이펙트 분리 마스크(Kaggle v3), 이펙트 형태 사전, 임팩트 책, 이펙트 타이밍·카메라 흐름 통계.
- 결과는 숫자보다 영상으로 먼저 보여 주고 사용자 판단을 받는다.

## 2026-10-27 밤 추가
- GPT↔Claude 토론(사용자 중계, GPT 보고가 먼저): 반대할 것은 근거로 반대, 맞는 것은 인정, 더 나은 방법은 찾아 제안. 인상이나 상대 권위로 결정하지 않는다. 합의 안 되면 '미결'로 기록.
- scratch 스크립트 이름을 표준 모듈 이름(struct, dis, json 등)으로 짓지 않는다(10-27에 dis.py·struct.py가 표준 모듈을 가려 두 번 실패).
- 예측·모형은 맞춘 점 수와 검증 여부를 같이 적는다. 미지수 수만큼의 측정으로 맞춘 모형은 검증이 아니다(10-27 로딩 3항 모형 예측 1:16, 실제 1:31).
- 장 번호 보정 같은 '항상 n장 밀린다' 류 결론은 여러 원본에서 다시 재고 쓴다(10-27 a+1 결론이 틀려 학습 자료 266/274컷이 1장 밀림).

- (사용자 공통 지시 10-27 밤) 사용자의 심판이 필요한 경우가 있으면 사용자에게 부탁한다: GPT와 Claude가 근거를 주고받아도 합의가 안 되거나, 측정으로 가를 수 없는 눈 판정·취향·방향 결정이면 혼자 정하거나 '미결'로 묻어 두지 않고 쟁점·양쪽 근거(장 번호·측정값)·보여 줄 시트/장 이미지를 정리해 사용자에게 판정을 요청한다. 판정 전까지 학습엔 현재 GPT 검토본을 쓴다.
- (10-31) 기준·합격선의 근거로 쓰는 주장은 먼저 실제 자료로 잰다. '외운 AI는 위치 시험 0점'이라고 근거로 썼다가 실측 17.7점으로 틀렸다. 판정 장치는 '그 장치만으로 통과하는 반례(예: 영상 없이 고정 이동만 더하기)'를 먼저 찾아본다.
- (10-31) 재설계·인수인계 때 '그대로 쓴다'·'사용자 지시'로 적은 항목이 실제 코드에 들어갔는지 대조한다(10-29 해상도 단계·페인트 합성·인코더 이어 쓰기가 재설계 뒤 빠져 있었다).
- (10-28 사용자, 세 번 지적) 사용자에게 하는 답은 처음부터 끝까지 한국어로만 쓴다. 영어 문장으로 답하지 않는다. 파일 이름·명령·화면에 나오는 글자처럼 꼭 필요한 것만 원문 그대로 둔다.

- 시험 결과를 `| tail` 뒤에 `&&`로 커밋·푸시에 이어 붙이지 않는다. tail은 항상 성공해 실패한 시험 뒤에도 커밋된다(11-01 실제 발생). 시험을 먼저 따로 돌려 OK를 확인한 뒤 커밋한다.
- `pkill -f` 패턴에 스크래치 경로(`/tmp/claude-0…`)를 넣지 않는다. 내 셸 명령줄도 그 경로를 담아 자기 셸이 죽었다(11-01, exit 144). 멈출 작업은 TaskStop이나 PID로. `pgrep -f '도구 이름'`으로 PID를 찾아 kill해도 같은 일이 생긴다(11-03, 내 셸 명령줄에 같은 문자열이 있어 셸이 죽음). PID는 `ps -eo pid,args | grep '^ *[0-9]* python '`처럼 실행 파일로 좁혀 찾는다.
- Kaggle 자료 커널 출력(파일 3,000개+)은 `pull`/기본 목록으로 받지 않는다. 기본 20개씩 목록이라 요청 제한에 걸린다. `kaggle_seq_remote.py data-check`(한 쪽 200개)를 쓴다.
- 규칙 대조는 '코드가 규칙 문구를 담는가'로 끝내지 않는다. 그 규칙을 깨는 반례(같은 점수인데 다른 영상, 업데이트 없는데 성공 기록 등)를 실제로 만들어 본다(11-01 코드 검토: Claude가 '확인함'으로 넘긴 채점 순서·업데이트 기록에서 GPT가 반례를 찾음).
- 앱 확인용 시험 SFA는 실제 파일의 불변 조건을 지킨다: 점·오브젝트 ID는 장마다 같은 대상을 가리키고, **같은 점 ID의 연결(AC)은 모든 장에서 같다**(실제 파일 24,566장 위반 0, 11-02). 장마다 연결을 바꿔 비교하려면 장마다 새 ID를 쓴다(5차 시험이 이를 어겨 결과가 섞였다). 11-01 시험 1·2가 이를 어겨 '점 연결 묶음 없음'이라는 틀린 결론으로 커밋까지 갔다. 결론 전에 실제 파일 한두 장으로도 확인한다. **정정(11-02 사용자 앱 시험·전수 조사):** 실제 여러 장 파일 304개 모두 **점 ID는 장마다 새로** 쓰고(이웃 장끼리 공유 0) 오브젝트 ID만 장끼리 이어진다. 위 '같은 점 ID의 연결은 모든 장에서 같다'는 점 ID가 장을 넘어 반복되지 않아 생긴 당연한 결과였다. 점 ID를 모든 장에서 같게 쓴 파일(스틱맨 v2–v4)은 앱 편집에서 조각이 떨어졌고 1장짜리만 정상이었다. 시험·생성 SFA는 점 ID를 장마다 새로 쓴다.
- (11-02 밤 사용자) **애니 사람 캐릭터 → 스틱맨 전환은 진짜 처음부터 다시 한다.** 하던 변환(v1–v5, `tools/pose_to_stickman.py`)은 중단했다. 주제는 "어떻게 하면 애니 사람 캐릭터의 움직임을 스틱맨으로 전환할 수 있을까"이고, GPT와의 토론·의논 형식으로 정한다. 3D 배제는 뺐지만 **3D에 매몰되지 않는다**(2D 방법과 같은 자리에서 실험으로 겨룸, 사용자 11-02 밤). GPT도 같은 GitHub·Drive를 본다. **Claude와 GPT 모두 외부 프로그램·도구·스킬 등 모든 것에 제약이 없다.** 채택은 사용자가 결정한다. 프롬프트는 docs/GPT-PROMPT-ANIME-TO-STICKMAN-FRESH-2026-11-02.md, 기록은 docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md에 있다. GPU 실행은 여전히 사용자 허락을 받고 한다. **스틱맨 기본 비율은 유지하지 않아도 된다**(사용자 11-02 밤, 인물마다 원본 비율 허용). 필수 조건은 앱에서 연결 유지 + 포즈 편집 가능이다. 10조각은 첫 실험의 기본 구조일 뿐이고, 사용자가 확정한 조건이 아니다(GPT 2차 지적 수용). **스틱맨 쪽 GPU 시험은 Colab을 쓴다**(사용자 11-02 밤: Kaggle은 변환기 학습 중). Claude가 노트북을 만들고, 사용자가 실행한다. 2D 초기안은 Drive `02_분석자료/포즈_RTMW/`의 기존 RTMW-x 결과를 먼저 재사용한다.
- **GPT 일시 전담(11-03 사용자):** Claude 주간 사용량 소진 기간에 사용자가 말하면 GPT가 구현까지 모두 맡는다(docs/GPT-PROMPT-TAKEOVER-2026-11-03.md). Claude는 복귀하면 docs/GPT-TAKEOVER-LOG-2026-11-03.md와 그 기간 커밋을 먼저 검토한다.
- **스틱맨 토론 진행 방식(11-03 사용자·GPT 동의):** 토론은 결정이 필요할 때만 한다. 구현 세부는 Claude가 바로 만들고, GPT는 설계 문장이 아니라 결과물(SFA·비교 영상·보고 JSON)을 검토한다. 사용자 판정이 필요한 동안에는 새 설계 토론·추가 시제품을 만들지 않는다.
- (11-03 사용자 지적) 결과 시트를 보낼 때, 시트에 보이는 문제를 '장 몇 개의 개별 문제'로 적고 넘기지 않는다. 같은 증상이 여러 장에 있으면 공통 원인을 장별 수치(관측·뺀 점·출력)로 먼저 찾는다. 다리가 굳은 모습이 시트 다섯 장에 있었는데 두 장만 적어 지적을 받았다.
- **애니메이터별 학습 범위 규칙은 최신 기록 기준으로 고정(사용자 11-02: "규칙 자체는 더 이상 건들면 안 돼", "최신 규칙을 기준으로")**. 기록끼리 다르면 날짜가 늦은 쪽(예: 10-20 임팩트 규칙이 10-18 yukina '디지털 임팩트 제외'를 대체)을 따르고, 그 뒤로는 다시 해석·조정·재질문하지 않는다.

- **투영 길이·머리 표현(11-03 사용자):** 자세·구도·각도·가림에 따라 신체 길이를 늘리거나 줄여도 된다. 고정 길이 때문에 원본 포즈를 꼬이게 하지 않는다. 제시한 시트는 예시이며 같은 증상을 구간 전체로 확대 점검한다. 모든 스틱맨 머리는 내부 흰색·인물색 윤곽으로 하고, 고개 숙임은 사용자 녹화처럼 원의 위치를 몸통 쪽으로 옮겨 겹침으로 표현한다. 구현·검증은 docs/GPT-STICKMAN-PROJECTION-2026-11-03.md.
- **새 장면 뼈대 재사용(11-03 사용자 정정):** 새 장면마다 완성된 뼈대의 구조·코드를 다시 수정해야 하는 방식으로 작업하지 않는다. 고정 프로필 `profiles/stickman_2d_v1.json`을 유지하고, 접촉·보완 관측·부분 가시성은 `scenes/*.json`의 장면 데이터로 적용한다. 사용법은 docs/STICKMAN-SCENE-CONFIG.md. 새 장면 수용과 실제 공통 구조 결함 수정은 구분하고, 후자는 버전·근거·회귀 검증을 기록한다.
- **60초 실패 뒤 정정(11-03):** '고정 뼈대'는 객체/연결/편집 구조를 뜻하고 팔다리 길이·좌표 고정이나 추출의 일반화 성공을 뜻하지 않는다. 기존10초의 수동 보완과 공통 자동 처리의 검증을 구분한다. v2 선택 시험은 `docs/GPT-STICKMAN-GENERIC-V2-2026-11-03.md`. 구도 태그로 좌표를 자동 측정했어도 구도 분류까지 자동이라고 부르지 않는다. 숨긴 마디·실제 좌우·부분 다리 굵기/발목 해석은 추론으로 남긴다. 기본v1/승인 파일을 v2 미완성 진단판으로 교체하지 않는다.

- **2D 뼈대 추출 기술 v1 정착(11-03 사용자):** 추출·가림·튐·접촉 작업은 `docs/STICKMAN-EXTRACTION-V1.md`와 `.claude/skills/stickman-extraction/SKILL.md` 절차를 재사용한다. 고정 뼈대/장면 데이터를 분리하고 `stickman_finalize.py`·`stickman_quality.py`로 재현/검사한다. 자동 기능과 원본 판독/추론 보완을 구분하며 현재 기준판의 남은 관측 잔차는 최종 검토 보고서를 따른다.

- **11-03 사용자 정정:** Claude용 스킬 준비는 담당 이관 지시가 아니다. GPT가 계속 맡는다. 최종 검토에서 찾은 수정 가능한 오류는 목록만 남기고 종료하지 말고 실제 수정·검증·비교 결과까지 제공한다. 눈 판정이 필요한 미확정 사항은 근거와 함께 사용자에게 제시한다.

- **근경 팔다리 면 시험(11-03 사용자):** 부위별 선 굵기의 이음 경계를 없애기 위해 아주 가까운 다리는 기존 스틱맨 모양의 연속 면으로 처리하는 시험을 허용했다. 기본 뼈대는 보존하고 선택 면 표시층을 더한다. 최종 전체 객체 수·추가 연결을 명시하며 `stickman_quality.py --surface`로 검증한다. 현재 범위는 docs/GPT-STICKMAN-LIMB-SURFACE-TRIAL-2026-11-03.md. 전체 사람 실루엣/곡선 몸통으로 확대하지 않는다.

- **머리 채움 저장 형식 정정(11-03 사용자 실제 앱 녹화):** 흰 머리 FS는 Kind=1(원 전체)을 명시하고 edge의 점/T를 섞지 않는다. 저장 검사에서 종류·소유 원·단일 외곽도 확인한다. `docs/GPT-STICKMAN-HEAD-FILL-APP-FIX-2026-11-03.md`. 서버 뷰어가 보완해서 그린 픽셀을 앱 호환 증거로 쓰지 않는다. 고정 뼈대 구조는 유지하고 저장 형식 revision2/지문으로 공통 결함만 보완한다. 요청된 모바일 뷰어만 v1.1로 수정하며 PC 버전은 이번 범위에 포함하지 않는다.

- **근경 신체 모양(11-04 사용자):** 자세히 묘사되는 손은 손모양을 만들며 발/몸통 등 다른 부위도 포함한다. 평소 고정 뼈대는 유지하고 가까운 부위의 선택 곡선/면 표시층을 별도로 시험한다. 이전 실루엣 보류는 이 명시한 근경 모양 시험을 금지하는 뜻으로 적용하지 않는다. 손 내부 마디/숨은 신체 정답 복원과 바깥 모양 표시는 구분한다. docs/STICKMAN-BODY-DETAIL-TRIAL-2026-11-04.md를 따른다. 기존 애니메이터별 학습 범위는 변경하지 않는다.

- **근경 표현 재정정(11-04 사용자,이전 모양 시험보다 우선):** 외곽/단색 면을 자세히 따지 않는다. 스틱맨 팔에 손가락 몇 개,발목에 발바닥 길이의 막대를 추가하고,몸통 등은 보이는 길이/너비에 맞게 늘린다. body-detail-curves-v1의 상세 면은 보류·미채택. 기본 뼈대와 단순 부속 확장을 분리한다.


- **최신 정정(11-04):** 단순화를 이유로 가까운 부위의 연속 면을 없애지 않는다. 팔/손의 원근 폭을 면으로 유지하고 손가락은 다섯 개 구조로 만든다. 가는 선/세 손가락 simple-parts-v1은 미채택. 기본11객체와 선택 v2부속24/근경 면을 분리한다. 원본 외곽/주름을 세밀하게 따는 방식과 중심선의 원근 면은 다르다. docs/STICKMAN-NEAR-FIVE-FINGERS-2026-11-04.md의 생성·검사·재현·수동키/추론 한계를 따른다.


- **최신 사용자 정정(11-04):** 손가락·발가락·발길이 부속은 제거한다. 가까운 단순 연속 면은 유지한다. 유효 폭을 못 얻었다고50px 같은 고정 반지름으로 채우지 않는다. 근거 있는 표시 척도를 명시하고 원근 측정/추론을 구분한다. 현재 기준은 docs/STICKMAN-WIDTH-FIX-REPLAY-2026-11-04.md. 기존 구간은 보존한표시키/입력/코드지문과 stickman_replay.py로 재현·XML대조하며,스킬만으로 영상부터 새로 판단해 동일 출력이 보장된다고 말하지 않는다.

- **마디 면 경계 정정(11-04 사용자):** 가까운신체를부위별선굵기나별도캡슐경계가드러나는모양으로대신하지않는다.951주변은두마디팔다리를한연속채움으로잇는선택표시층으로보완하고굵기도조금높여비교한다.몸통직선/기본편집뼈대는유지한다.새표시층과기존승인v1을구분하며 docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md를따른다.

- **스미어 탐지 평가(11-07 Claude):** 스미어 탐지 개선은 `tools/smear_eval.py`와 비공개 라벨로 기존/새 방식을 같은 기준(AP·상위k·오탐 부위)으로 비교해 보고한다. 후보 수·재현율·합성 테스트를 성공으로 쓰지 않는다. 개발/시험 구간에서 손 계수를 바꿔 ±2개 차이를 개선이라 하지 않는다. 새 환경 복원: GPT가 올린 Drive 파일은 링크 공유가 아니면 `drive.usercontent` 다운로드와 rclone(drive.file) 모두 막힌다. 공유 링크 생성(권한 변경)은 자동 검토가 거절했으므로 사용자에게 공유를 부탁한다. 테스트 의존성: opencv-python-headless, scikit-image, skia-python(+libegl1), CPU torch/torchvision.
- **스미어 배치 상시 규칙(11-08 사용자):** 스틱맨 팔다리가 스미어 끝 밖으로 튀어나오면 안 된다. 맞추려고 스틱맨 팔다리 길이를 줄이지 말고 스미어 길이를 늘린다(11-08 사용자 재확인). 다리 전체 스미어 같은 예외 모드에도 똑같이 적용한다. 스미어 폭은 물체(팔다리) 두께가 아니라 스미어로 선이 일그러진 정도다. 11-08 사용자 승인 이후 기본 표시 폭은 GPT 표시 테이퍼(꺾임 방향=국소 이동, 폭=말단폭×관절→말단 위치비, 앞뒤 58:42, 밀도 v1.1 original-gap)를 따른다(docs/CLAUDE-SMEAR-IMPROVEMENT-HANDOFF-2026-11-08.md). 원본 측정 좌우 비대칭을 다시 섞을 때는 이 테이퍼를 깨지 않는 범위에서 사용자 확인 후 한다.
- **직진 스미어(11-08 사용자 선택):** 팔 축 방향 이동은 `tools/sfa_axial_smear.py` 갈래형(후보 B)으로 그린다. 직진/회전은 회전각 ≤15°/≥40°로 자동 분류하고, 15–40°는 회전각만으로 나뉘지 않으므로(1158 21° 회전, 1181 31° 직진) 원본 시트로 사용자 판정을 받아 `scenes/*_axial_smear.json`에 적는다. 한 장에 직진형과 휘두르기형이 같이 있는 것은 부위가 달라서이며, 같은 부위에 두 모양을 겹치지 않는다.
- **레이어 번호(11-08 사용자 앱 화면):** 앱은 레이어를 번호 오름차순(아래→위)으로 그린다. LayerDef를 적은 순서나 DrawOrder로 뒤에 깔지 않는다. 층을 추가한 SFA는 `tools/sfa_layer_order.py`로 번호를 아래→위 순서에 맞추고 `check`로 확인한 뒤 전달한다. 서버 렌더 결과를 앱 층 순서의 근거로 쓰지 않는다.
- **깊이 칸(11-08 사용자):** 요소별 레이어를 유지하되, 앞뒤가 바뀌는 부위·스미어·파편은 인물×앞뒤 레이어가 아니라 인물과 상관없는 깊이 칸(zK_outline/body/smear/debris)으로 나눈다. 사람 편집은 고려하지 않는다(사람이 할 일은 거의 없게). 앞뒤 측정은 근사이므로 상승 장은 시트로 사용자 판정을 받는다. `tools/sfa_depth_layers.py`, `docs/DEPTH-LAYERS-2026-11-08.md`.
- **재작성 시 기존 승인 처리 누락 금지(11-08 사용자 지적):** 빌더를 새로 짤 때 이전 판에서 사용자가 요청·승인한 처리(예: v6 스미어 끝 정리, 1147 자세 교정)를 목록으로 대조해 빠짐없이 넣고 수치 검사로 확인한다. 사용자 승인 뼈대를 자동 교정으로 일괄 바꾸지 않는다(v15 자동 교정이 맞는 자세를 망가뜨림). 사용자에게 하는 중간 안내·결과 설명은 모두 한국어로만 쓴다.
