https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다(필요하면 fetch 후 이 브랜치에서 계속).
AGENTS.md → HANDOFF.md → docs/STYLE-LEARNING-PLAN-2026-10-16.md 순서로 읽고, 필요할 때만 docs/STYLE-KB-ROOTS-2026-10-16.md, docs/ARTIST-CANDIDATES-2026-10-16.md를 읽는다.

현재 우선순위: (나) 분석형 스타일 학습. 이펙트·연출·배경 먼저, 뿌리 yutaka_nakamura(이펙트·배경·연출)·nian41(인체 움직임). 추가 작가는 사용자 승낙 후에만 포함(1차 후보 6명 승낙/반려 대기). 개인 사용. 추가 지출은 가성비가 매우 좋을 때만.

바로 할 일 — Google Drive 연결:
1. 환경 변수 RCLONE_CONFIG_GDRIVE_TYPE/SCOPE/TOKEN 존재만 확인(값 출력 금지). 사용자가 2026-10-17에 넣었다고 함.
2. rclone 설치(서버 도구 설치 허용 범위) → `rclone lsd gdrive:`로 연결 확인. 공용 client_id 경고가 있었으므로 인증 오류면 개인 client_id 생성 안내.
3. drive.file 범위라 폴더는 서버가 만든다: AI-sfa/{00_목록,01_원본영상,02_분석자료,03_스타일지식베이스,04_SFA시험작}.
4. data/catalog.csv → 00_목록, 지식베이스 문서·observations.jsonl → 03에 올린다.
5. 원본 수집: 01_원본영상/<작가>/<post_id>_<md5>.<ext>. 1초 이상 간격, 이미 있는 md5는 건너뜀. 뿌리 두 명 404개(약 3.9GB)부터.
6. 이후 nian41 나머지 클립 분석(캐릭터 축)과 지식베이스 확장. 결과는 02/03과 저장소 양쪽에.

규칙: 토큰·키를 채팅/로그/커밋에 출력하지 않는다. 영상 원본·contact sheet는 GitHub에 올리지 않는다. 근거 등급([실측]/[추론]/[실물])을 구분한다. FPS는 (트위닝,재생). 혼자 가능한 일은 자율 진행.
