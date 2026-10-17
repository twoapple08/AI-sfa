https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다(필요하면 fetch 후 이 브랜치에서 계속).
AGENTS.md → HANDOFF.md → docs/STYLE-LEARNING-PLAN-2026-10-16.md('현재 상태' 절) → docs/STYLE-KB-ROOTS-2026-10-16.md 순서로 읽는다. 후보는 필요할 때만 docs/ARTIST-CANDIDATES-2026-10-16.md.

현재 우선순위: (나) 분석형 스타일 학습. 이펙트·연출·배경 먼저, 뿌리 yutaka_nakamura(이펙트·배경·연출)·nian41(인체 움직임). 추가 작가는 사용자 승낙 후에만(1차 후보 6명 승낙/반려 대기). 개인 사용. 추가 지출은 가성비가 매우 좋을 때만.

2026-10-17 완료 [실측]:
- rclone v1.75.2 설치(SHA256 대조), 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 `gdrive:` 연결. 공용 client_id 폐지 예정 경고 있음 → 인증 오류가 나면 개인 client_id 생성 안내.
- Drive `AI-sfa/{00_목록,01_원본영상,02_분석자료,03_스타일지식베이스,04_SFA시험작}` 생성. 00=catalog.csv, 02=<post_id>/{timing.json,contact_sheet.jpg} 35개, 03=지식베이스 문서·observations.jsonl.
- nian41 36클립 전부 분석(완성본 24 + 색 지정 레이아웃 제작자료 12). observations.jsonl 44건, catalog analyzed 44. 지식베이스 v1(D 캐릭터, E 제작자료 절).

차단:
- 01 원본 수집(`tools/sakuga_collect.py`, Drive 직접 스트리밍 + md5 대조)은 Claude Code 자동 승인 검토에서 거부됐다(사유 미표시). 우회하지 않는다. 사용자가 명시 허용하거나 권한 규칙을 추가하면 `python tools/sakuga_collect.py data/catalog.csv --limit 2`로 시험 후 전체(404개, 약 3.9GB) 진행.
- 분석용 임시 다운로드(받아서 측정 후 즉시 삭제)는 허용됐다.

다음 할 일:
1. 01 수집 허용 여부를 사용자에게 확인(허용 시 위 순서).
2. yutaka_nakamura 나머지 클립 분석(이펙트·배경 축 표본 확대). 임시 다운로드 → tools/sakuga_timing.py → contact sheet 판독 → observations.jsonl·KB 갱신 → Drive 02/03·catalog 동기화 → 클립 삭제.
3. 280830 원화 번호로 키 포즈 간격 측정.
4. 후보 승낙/반려가 오면 해당 작가 색인·분석.

규칙: 토큰·키를 채팅/로그/커밋에 출력하지 않는다. 영상 원본·contact sheet는 GitHub에 올리지 않는다(contact sheet는 Drive 02에만). 근거 등급([실측]/[추론]/[실물])을 구분한다. 출처가 "SB/ED"인 클립은 콘티·연출 근거로만 쓰고 작화 필치를 단정하지 않는다. FPS는 (트위닝,재생). 혼자 가능한 일은 자율 진행.
