AI-sfa 프로젝트를 이어 맡아 줘. 모든 답은 처음부터 끝까지 한국어로 해.

저장소는 GitHub twoapple08/AI-sfa, 브랜치는 claude/new-session-gknz4t만 사용해(main은 읽지도 쓰지도 마). Google Drive는 rclone 리모트 gdrive:로 연결돼 있어.

다음 순서로 읽어:
1. AGENTS.md 전체 → HANDOFF.md
2. docs/GOALS-TABLE-2026-11-10.md(목표 정리표) → docs/REPLAN-PLAN-DRAFT-2026-11-05.md 맨 위 '체크 목록'
3. 스틱맨 작업이면 .claude/skills/stickman-extraction/SKILL.md, 레이어(깊이 칸)면 docs/DEPTH-LAYERS-2026-11-08.md, 새 구간이면 docs/NEW-SEGMENT-3072-3311-2026-11-09.md, 스미어면 .claude/skills/stickman-extraction/references/SMEAR-PIPELINE.md

지금 할 일: HANDOFF.md '바로 할 일'부터 해. 목표는 스틱맨 추출을 '딸깍'으로 거의 완벽하게 만드는 거야. 고친 건 장 지정 데이터가 아니라 공통 규칙(코드)으로 남기고, tools/stickman_key_eval.py로 전후를 재. 작업 전에 무엇을·왜·얼마나 걸릴지 한 줄로 말하고, 끝나면 체크 목록을 체크하고 근거와 커밋을 남겨. 결과는 원본과 나란히 놓은 시트(tools/stickman_review_sheets.py)로 먼저 보여 주고, 사용자 판정이 필요한 건 판정을 받아. 비공개 자료는 HANDOFF.md '새 환경 복원'대로 Drive에서 받아. GPU·새 학습·Kaggle 실행은 내 허락을 받고 해.
