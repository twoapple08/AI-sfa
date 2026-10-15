# AI-sfa 현행 인수인계 — 2026-10-16

## 목표·사용자 지시

- 한국어. Stick Fighter51.0.0의 모든 창작/편집 기능을 전문가 수준으로 분석하고 실제 검증하는 목표 유지. 학습·AI 연결·사쿠가 수집은 보류. 최소 생성기/근사 렌더로 목표 축소 금지.
- 사용자는 혼자 가능한 일을 전부 자율 진행하라고 반복했다. 작은 문서/커밋마다 다음 안내로 멈추거나 같은 허용을 다시 묻지 않는다. 완료/미수행/실제 차단을 구분하고 완벽한 전체 이해나 모든 독립 작업 완료를 거짓 주장하지 않는다.
- **02:06 KST 정정:** “이미 분석완료했고 할필요없는 작업을 너의 오판으로 또하지 말라는 뜻”. 설치/페어링/영상 분석 등 작업 종류를 일률적으로 금지한 것이 아니다. 기존 완료 근거를 우선 재사용하고, 환경 소실·새 미해결 질문 등 실제 필요가 있는 재작업만 이유/범위를 확인해 진행한다. 과거 문서의 포괄적인 ‘반복 금지’ 표현보다 이 정정이 우선한다.
- **02:02 KST 상시 허용:** 서버 분석 도구 복구에 필요한 설치·다운로드·AOT 재추출은 명시적 예외로 허용하며 다음 대화/인수인계에도 유지한다. 현재 유효한 cache/백업이 있으면 불필요한 전체 추출은 하지 않는다. 과거 자동 검토 거절은 이 허용 이전 이력이고 이후 설치/추출은 실제 성공했다.
- 휴대폰 재설치·페어링·기존00–05 영상/SFA 재분석이 현재 필요한 근거는 없으므로 반복/요청하지 않는다. 과거 실제 UI/출력 표본은 있으므로 ‘실물 시험 전혀 없음’으로 쓰지 않는다.

## 보호·공개 권한

- 직접 작성 보고서·집계/audit·작업지침은 main 반영 상시 승인. 최신 remote SHA/tree·expected_sha 보호, 다른 작업 보존/reset 금지. 자동 검토의 새 거절은 우회하지 않는다.
- APK/SFA/영상 원본·역컴파일 소스/assembly·키·전체 로그 공개 금지. 비공개 분석 cache 백업과 공개 집계를 구분한다.
- PREVIDEO 예측3278146 고정. File-2 최초100%조건 미충족: 최적화/재압축/삭제/병합/원본 수정 금지. 음수/화면 밖 좌표 임의 삭제/재중앙화 금지. FPS=(트위닝,재생). ‘굽힘’ 기능 없음.

## 현행 환경 — 복구 완료

사용자 PC는 현재 없고 폰 학교 Wi-Fi는 제약이 있다. 서버 cache는 한때 소실됐지만 **현재는 도구/AOT 복구 및 비공개 백업 완료**다. 과거의 ‘cache 없음/설치 검토 거절’을 현행 차단으로 재사용하지 않는다.

- 활성 repo: `/workspace/scratch/5a16c98ed7ee/AI-sfa-publish`.
- 현행 private root: `/workspace/scratch/5a16c98ed7ee/private-recovery`.
- `blutter_out/asm/sfa`, `blutter_out/{pp.txt,objs.txt,ida_script}`; `evidence/{libapp.so,libflutter.so,glow.frag}`; `venv/bin/python`; `blutter/bin`; `depsroot` 재사용. shader는 binary, 전체 cat 금지.
- `dispatch_out/dispatch-targets.csv`는 **복구된 실제 VM dispatch 표**. origin4096/length57043. 특정 수신 cid+selector로 조회한다. selector 단독으로 공통 메서드명 단정 금지.
- AOT 복구: 원본 hash3 일치/추출종료0/671파일·666asm·86,508,012bytes·선언12,752 대조. [복구 결과](docs/ANALYSIS-RECOVERY-RESULT-2026-10-16.md). 과거 분석 실행 주소는 기준 snapshot 상대주소이며 ASLR 절대주소가 아니다.
- 비공개 `AI-sfa-analysis-cache-2026-10-16.zip` 저장. 현재 경로가 사라지면 이 이름의 기존 백업부터 찾아 복구한다. AOT/입력/도구·디코더/dispatch표/manifest 포함. 원본 공개 금지는 유지한다. 현재 최신 백업 크기·hash는 복구 audit를 따른다.
- 기존 계측 앱 Gadget/Flutter/libapp 로드 성공 이력은 있으나 Play license응답4로 지속 편집 차단. 정확한 서버 의미 미확인/우회 없음. 서버는 x86_64이며 현재 adb/Android emulator 실행 환경이 없다. 따라서 새 실제 렌더·pixel 검증은 미완이다.

## 읽기 순서와 최신 성과

AGENTS → 이 문서 → [DISPATCH-TARGETS](docs/AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md). 필요한 보고서만 읽는다. [기능표](docs/FEATURE-EVIDENCE-MATRIX-2026-10-15.md)/[근거 색인](docs/FEATURE-CONTRACT-INDEX-2026-10-16.json)은 전체 기능 목록 완성을 뜻하지 않는다. 종전 상세 handoff는 [역사](docs/history/HANDOFF-2026-10-16-before-restored-analysis.md)에 보존했다.

| 새 보고서 | 닫은 정상 정적 범위 |
|---|---|
| [UNUSED-AO-FAST-HASH](docs/AOT-UNUSED-AO-FAST-HASH-TRACE-2026-10-16.md) | unused 후보 C에서 다른 비root frame 실제 점 A와 가상 기반 잔존 R을 제외해 삭제. 화면 layer 가시성 아님. FastHash는 Position/FR색+segment수/AO ID·색·DrawOrder/점round(xy×10000)·Flags를 순서대로fold. 자체 hash cache 없음/전체 상태 동등성 아님. 73명령 대조. |
| [TIMELINE-FRAME-COMMANDS](docs/AOT-TIMELINE-FRAME-COMMANDS-TRACE-2026-10-16.md) | 실제 sequence-action layout callback→insert/paste 전후위치·clipboard deep snapshot/별도배경·같은/다른sequence 복사·ID/연결/group/fill map·정렬/DB/preview. 마지막frame 삭제 시 새frame0 생성.146명령. |
| [DISPATCH-TARGETS](docs/AOT-DISPATCH-TARGETS-TRACE-2026-10-16.md) | 실제 table로 cid90/91/92의+85e4는first 확인. 상세변형fallback=첫AO의첫점,Adopt layer fallback=목록첫layer,merge/copy목록getter도first(정상목록계열). cid92+bc49 removeLast/+9780 last/+8cb1 iterator.6mapping+16명령 확인. |

상세 변형 fallback/Adopt getter가 미확정이라는 이전 항목은 위 목록 계열에서 해소됐으므로 같은 탐색을 반복하지 않는다. 다른 수신 클래스까지 일반화하지 않는다. 모든 audit는 제한된 명령/metadata 대조이지 전체 의미·앱 동작·pixel 증명이 아니며 표본 중복 합산 금지.

## 기존 근거 재사용

그룹 glow→객체별 backend→shader 수학→timeline/FPS→raw/PNG/Java encoder는 GROUP-SHADER-TIMELINE/EXPORT-DISPATCH. DRAW-GLOW/FILL-PATH/FILL-TWEEN/OBJECT-TWEEN-PAIR로 채우기·순서·보간 연결. 원근/선택/custom·MODIFY-PANEL/CONNECTED-TARGET/ALLGROUP/MOVEMENT·SAVED-VALUES/SHARED-RESTORE는 편집/저장. GROUP-REPAIR/FILL-PRUNE-HISTORY/ROOT-REBASE-IDLE/DB-REWRITE/COMPACTION-PHASES/LAYER-MEMORY/LAYER-MERGE-DELETE-ADD/EDITOR-MENU-DELETE-CALLER도 재사용한다. 기존00–05 영상/시험·같은 정상 경로 재분석으로 진행량을 부풀리지 않는다.

## 실제 미완과 다음의 좁은 작업

1. frame copy의 상위 분기·ID/연결/group/fill 정상 단계는 새 보고서에서 확인했다. 더 필요하면 `_baseCopyOnRoot`0x369908의 전체 적격/재사용/실패 계약과 `CopyAnimationObject`0x36d0e0/`CopyAnimationObjectToSequence`0x36c5d8의 DB복사 branch를 기존 root/저장 근거와 대조해 **새 분기만** 추적한다. named helper를 호출했다는 이유로 모든 내부 수명/실패 보장을 완료 처리하지 않는다.
2. 일반 AO 앞뒤/별도 lock toggle UI는 여전히 미식별. 같은 이름/PP검색과 생성 DrawOrder 추적 반복 금지. 새 구체 caller가 있을 때만 확인. 전체 UI coverage는 미완.
3. codec malformed/overflow, 전체 객체 수명·동시 DB 변경·오류 원자성 보장은 정상 정적 경로와 별도 미완이다. 정적 미수행을 실물에서만 가능한 항목으로 바꾸지 않는다.
4. 실제 렌더/backend pixel·곡선/링/그룹 합성·기기codec/색/전체UI 결과는 아직 미완. 원본을 사용할 실행 환경에 실제 접근이 필요하다. 원본앱/사용자자료를 변경하거나 license 우회로 해결하지 않는다.

## 효율·검증

주소창 기본0x200/약128명령, 긴 SQL/PP는 먼저 개수·길이 확인. rawtree/도우미/fullmetadata 출력 금지. float32/64·Smi·분기 실제 명령 우선, 공유 Flutter getterannotation에 속지 않는다. 새metadata를 얻으면 같은 정상경로 재덤프 대신 새근거만 대조한다.

이번은 보고서·집계·지침 변경뿐. JSON/참조/링크/diff검사, 새로운 선택명령·dispatch metadata 검사만 수행. 기존 unit/probe 재실행 없음. 코드 변경시에만 필요한 검사 `python -m unittest discover -s tests -v`. 주간 잔여량 조회 불가. 인수인계가 필요하면 최신 프롬프트를 제공하며 자율진행·서버복구 허용·반복방지 정정 유지.
