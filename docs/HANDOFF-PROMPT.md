https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다(필요하면 fetch 후 이 브랜치에서 계속).
AGENTS.md → HANDOFF.md → docs/STYLE-LEARNING-PLAN-2026-10-16.md('현재 상태' 절) → docs/STYLE-KB-ROOTS-2026-10-16.md 순서로 읽는다. 후보는 필요할 때만 docs/ARTIST-CANDIDATES-2026-10-16.md.

현재 우선순위: (나) 분석형 스타일 학습. 뿌리 yutaka_nakamura(이펙트·배경·연출)·nian41(**사람 몸 움직임만**; 표정 같은 그림체·머리카락·이펙트·연출은 학습 제외, 옷자락은 확인 대기). nian41 몸 움직임은 docs/NIAN41-BODY-MOTION-2026-10-17.md. 추가 작가는 사용자 승낙 후에만(1차 후보 6명 승낙/반려 대기). 개인 사용. 추가 지출은 가성비가 매우 좋을 때만.

2026-10-17 완료 [실측]:
- rclone v1.75.2 설치(SHA256 대조), 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 `gdrive:` 연결. 공용 client_id 폐지 예정 경고 있음 → 인증 오류가 나면 개인 client_id 생성 안내.
- Drive `AI-sfa/{00_목록,01_원본영상,02_분석자료,03_스타일지식베이스,04_SFA시험작}` 생성. 00=catalog.csv, 02=<post_id>/{timing.json,contact_sheet.jpg} 55개, 03=지식베이스 문서·observations.jsonl.
- nian41 36클립 전부 분석(완성본 24 + 색 지정 레이아웃 제작자료 12), yutaka_nakamura 확정 표기 완성본 점수 상위 20클립 추가(누적 28). observations.jsonl 64건, catalog analyzed 64. 지식베이스 v1(D 캐릭터, E 제작자료, F yutaka 확장 절).

차단:
- 01 원본 수집(`tools/sakuga_collect.py`, Drive 직접 스트리밍 + md5 대조)은 Claude Code 자동 승인 검토에서 거부됐다(사유 미표시). 우회하지 않는다. 사용자가 명시 허용하거나 권한 규칙을 추가하면 `python tools/sakuga_collect.py data/catalog.csv --limit 2`로 시험 후 전체(404개, 약 3.9GB) 진행.
- 분석용 임시 다운로드(받아서 측정 후 즉시 삭제)는 허용됐다.

2026-10-17 후반:
- nian41 학습 범위 축소 반영(KB D절·부록, observations.jsonl `learn_scope`). 몸 움직임 v1: 인물 색 마스크 측정으로 '몸 그림은 2s 기본 + 순간 1s'로 정정, 예비→순간→후속, 스미어 형태 정리(`tools/sakuga_timing.py --run` 연속 프레임 시트 추가).
- GPT 분담: docs/GPT-TASK-YUTAKA-EFFECTS-2026-10-17.md. yutaka 다음 30클립(점수순 21–50위) contact sheet·timing·작업목록 CSV를 Drive 02에 올림. GPT 결과(JSONL)가 오면 몇 클립을 직접 대조한 뒤 KB에 'GPT 시각 판독'으로 합친다. 이 30개는 Claude가 중복 분석하지 않는다.

- 자료 출처 조사(사용자 공통 지시: Claude=nian41, GPT=yutaka_nakamura): docs/NIAN41-SOURCES-2026-10-17.md, data/sources/nian41_sources.csv. 핵심 A등급=본인 Bilibili lo 업로드(JJK S3#09 虎杖vs日車, BV1A9PyzfExr). Bilibili 목록은 비로그인 위험 제어로 차단(우회 안 함). GPT용 지시서 docs/GPT-TASK-YUTAKA-SOURCES-2026-10-17.md.

다음 할 일:
1. 01 수집 허용 여부를 사용자에게 확인(허용 시 위 순서).
2. (GPT 결과 대기 중이면) nian41 몸 움직임 표본 확대: 다른 제작자료(280833·280835·287139 등)에 마스크 측정·연속 시트 적용, 280830 원화 번호 계수. yutaka 나머지: 확정 표기 완성본 영상 159개 중 GPT 30개를 뺀 129개를 점수순으로(다음 묶음은 /tmp 스크립트 없이 같은 방식 재작성: 미분석·비presumed·비제작자료·mp4/webm을 score 내림차순). 이후 presumed 56개, 제작자료 76개. 임시 다운로드 → tools/sakuga_timing.py → contact sheet 판독 → observations.jsonl·KB 갱신 → Drive 02/03·catalog 동기화 → 클립 삭제.
3. 280830 원화 번호로 키 포즈 간격 측정.
4. 후보 승낙/반려가 오면 해당 작가 색인·분석.

규칙: 토큰·키를 채팅/로그/커밋에 출력하지 않는다. 영상 원본·contact sheet는 GitHub에 올리지 않는다(contact sheet는 Drive 02에만). 근거 등급([실측]/[추론]/[실물])을 구분한다. 출처가 "SB/ED"인 클립은 콘티·연출 근거로만 쓰고 작화 필치를 단정하지 않는다. FPS는 (트위닝,재생). 혼자 가능한 일은 자율 진행.
