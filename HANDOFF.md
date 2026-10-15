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

## 현행 환경 — 2026-10-16 Claude Code 클라우드

- 사용자가 환경 Network access에 Drive 도메인을 허용한 뒤 같은 세션에서 백업 다운로드 성공: 40,381,872bytes·SHA256 `d6d5f1ff…cff676` 일치, ELF/셰이더 hash3 일치, asm666. 압축해제 위치는 세션 scratchpad의 `cache/`(세션 종료 시 소멸). 새 세션은 환경 Setup script가 `/root/sfa-cache`로 자동 복구하도록 사용자에게 안내함(적용 여부는 새 세션에서 확인). 도구: 시스템 Python3.13+`PYTHONPATH=cache/python`의 capstone5.0.7 동작. 환경변수 추가 불필요.
- 이번에는 새 AOT 분석 없이 [APP-V3 시간축 명령 검사](docs/APP-V3-FRAME-COMMANDS-PROTOCOL-2026-10-16.md)를 추가했다: 정적 결과의 SFA 관측 가능성 대조, 시드 `examples/frame_commands_v3/`, `tools/check_frame_commands.py`, 단위시험6개. 앱 결과는 없음.

## 이전 환경(ChatGPT) — 복구 완료 기록

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

추가로 [ROOT-COPY-DB-BRANCHES](docs/AOT-ROOT-COPY-DB-BRANCHES-TRACE-2026-10-16.md)(49명령)를 확인했다. source base의 원점 ID/AO rank 연속prefix p가 2(N−p)≤N이면 그 root를 p개만재사용,아니면새root생성→조건부source rebase시도→targetbase삽입. ID예약은 AUTOINCREMENT schema에따라sqlite_sequence상향 vs가상base꼬리정리. 같은sequence AO ID유지/다른sequence새ID/DB점·상세복사 상위단계확인. 정상분기를다시미수행으로세지않는다.

0-1. **APP-V3 실물 결과(2026-10-16):** 사용자 SFA 6개, 연속 5쌍 실패0. 같은 sequence 붙여넣기(AO ID 유지/새 점 ID/연결·그룹·fill 재작성/배경·레이어)와 ‘앞에 붙여넣기’, 새 프레임(레이어 복제), 단일 삭제가 실물과 부합. 가져오기 단계 그룹 사슬 평탄화 실물 확인. 휴지통 개별 삭제로 마지막 삭제 시 AO0/기본레이어1 새 frame 생성 확인(ID2297 재사용은 비AUTOINCREMENT 기존DB 추정). 하단 버튼(←붙여넣기/◂새프레임/수정/복사/▸새프레임/→붙여넣기/휴지통)↔callback 대응 사용자 화면으로 확인. 결과는 APP-V3 문서 말미.
0. **완료(2026-10-16):** [AXIS-FIX-DRAWORDER-WRITERS](docs/AOT-AXIS-FIX-DRAWORDER-WRITERS-TRACE-2026-10-16.md) — DrawOrder SQL쓰기5함수/메모리store 전수, 잠금 스키마(layer만), 축고정·회전스냅 UI→드래그 연결. 일반 앞뒤/별도 lock 항목은 이 쓰기경로 근거로 대체하고 같은 탐색을 반복하지 않는다. 편집 보조 환경설정 7키는 [EDITOR-AIDS-PREFS](docs/AOT-EDITOR-AIDS-PREFS-TRACE-2026-10-16.md)로 DB/SFA/출력 무관 정리. 렌더 기준 시험 [APP-R1](docs/APP-R1-RENDER-REFERENCE-PROTOCOL-2026-10-16.md) 실물 MP4 측정 완료: 출력 좌표 x=10.65+18.987x,y=5.98+10.68y(여백P≈10.65px, DrawInformation 식과 부합), 화면밖 여백에도 그림, 색 오차≤3, 선 FWHM 9px/scale1, glow σ≈R px·W≈0.75T px(일부 모델 오차), fill src-over 일치, 그룹은 심지가 glow 위(그룹 단위 순서). 기준 렌더러 [RENDERER-V0](docs/RENDERER-V0-2026-10-16.md)(sfa_render.py, numpy) 완료: APP-R1 9장면 MAE 0.05–0.76, p99≤12(맞춤에 쓴 장면이라 일반화 미측정). 좌표=중앙 균일축소(x=10.708+18.99x,y=5.81+10.685y). 보간 `sfa_tween.py`(PlaybackEnumeration 시간축·객체/점/속성/채우기 규칙)와 `tools/render_video.py` 구현, 시험 [APP-T1](docs/APP-T1-TWEEN-REFERENCE-PROTOCOL-2026-10-16.md)(examples/tween_v1, (30,12)→예측 35프레임) 생성·사용자 MP4 요청. APP-T1 실물 판정 완료: 35프레임/30fps 일치, 렌더 수정(숨긴 레이어 미출력·채우기는 테두리 아래) 후 35프레임 MAE≤0.256. 7사례 중 hidden_layer만 예측 수정. 실제 사용자 작품 1(122→244프레임, (24,12)) 종합 대조: 평균 MAE 5.10→1.155([USER-ARTWORK-1](docs/USER-ARTWORK-1-RENDER-CHECK-2026-10-16.md)). 확정: 배경색 보간, AC연결 glow 묶음(glow→fill→본체), 레이어 목록순 적층, ObjectScale 선굵기 무반영, 선폭 정수 반올림, 선굵기→glow·여백. 이후 [DRAW-PLAN-GROUPS](docs/AOT-DRAW-PLAN-GROUPS-TRACE-2026-10-16.md)(20명령) 정적 추적과 glow 폭×ThicknessScale 발견으로 작품 평균 MAE 0.908(최대 3.38, 98%<2). **다음:** 사용자가 앱 이해 완료 후 학습 방식을 설명할 예정. 남은 앱 이해 항목(FillRegionsByFigure 키 closure 0x42d798, InterpolatedFrame 그리기 본문, glow 끝 모양 세부)은 소규모.
1. frame copy의 상위·ID/연결/group/fill·rootprefix/예약schema·AO DB복사 정상 경로는 확인했다. 원시 DB helper 전체 수명/실패 원자성·비정상 입력을 이 결과만으로 완료 처리하지 않는다. 해당 질문에 실제 필요한 새 branch가 있을 때만 추가한다. 다음 기능 단계는 기존 기능표에 아직 직접 연결하지 않은 실제 UI callback을 구체적으로 식별해 coverage를 보충하는 것이다. 완료한 정상copy/root 경로를 다시 따라가지 않는다.
2. 일반 AO 앞뒤/별도 lock: 쓰기경로 전수로 정리(위 완료). 위젯 receiver 미확정·계산값 bit0 경로는 미배제. 전체 UI coverage는 미완.
3. codec malformed/overflow, 전체 객체 수명·동시 DB 변경·오류 원자성 보장은 정상 정적 경로와 별도 미완이다. 정적 미수행을 실물에서만 가능한 항목으로 바꾸지 않는다.
4. 실제 렌더/backend pixel·곡선/링/그룹 합성·기기codec/색/전체UI 결과는 아직 미완. 원본을 사용할 실행 환경에 실제 접근이 필요하다. 원본앱/사용자자료를 변경하거나 license 우회로 해결하지 않는다.

## 효율·검증

주소창 기본0x200/약128명령, 긴 SQL/PP는 먼저 개수·길이 확인. rawtree/도우미/fullmetadata 출력 금지. float32/64·Smi·분기 실제 명령 우선, 공유 Flutter getterannotation에 속지 않는다. 새metadata를 얻으면 같은 정상경로 재덤프 대신 새근거만 대조한다.

이번(APP-V3)은 코드·시드 추가로 `python -m unittest discover -s tests -v` 28개 통과. 기존 probe 재생성 없음. 코드 변경시에만 필요한 검사 `python -m unittest discover -s tests -v`. 주간 잔여량 조회 불가. 인수인계가 필요하면 최신 프롬프트를 제공하며 자율진행·서버복구 허용·반복방지 정정 유지.
