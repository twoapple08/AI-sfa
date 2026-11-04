# AI-sfa

자연어·태그·스토리보드로 Stick Fighter에서 편집할 수 있는 `.sfa` 애니메이션을 만드는 프로젝트입니다. 현재 **사람 모션 추출기와 그림→SFA 변환 AI를 개발·검증 중**입니다. APK/파일 형식 분석, 학습 실험, 모바일 뷰어도 진행했습니다. 임의의 영상 전체를 자동 완성하거나 새 영상 일반화가 확인된 단계는 아닙니다.

**처음 참여하면 [신규 참여자 인수인계](docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md)부터 보세요.** 작업 전에는 [AGENTS.md](AGENTS.md) 전체와 [HANDOFF.md](HANDOFF.md)를 읽습니다. 저장소는 **claude/new-session-gknz4t만** 사용하며 main은 읽거나 쓰지 않습니다.

- [이번 세션 전체 경과·채택/미채택·미완](docs/SESSION-COMPLETE-HANDOFF-2026-11-04.md)
- [Claude에게 보낼 프롬프트](docs/CLAUDE-RESTART-PROMPT-2026-11-04.md)
- [추출 스킬과 최신 데이터 입구](.claude/skills/stickman-extraction/START-HERE.md)
- [최신 1분 제보 수정판·정지 비교·재현 증거](docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md)
- [GPT 전담 상세 변경·검증·커밋 기록](docs/GPT-TAKEOVER-LOG-2026-11-03.md)
- [Drive 인계 폴더](https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK)

사람 추출은 RTMW 2D 관절/그림키/장면 판단을 사용합니다. 사물·배경·이펙트는 별도 변환기 대상입니다. 스킬에 실제 개발자료를 연결·복원할 수 있지만, 수동 보정/추론을 자동 정답으로 학습시키지 않습니다. 알려진 한 영상의24개 사례는 일반화 개선용 개발 자료입니다.

원본 영상·전체 관절·원본 발췌·SFA/비교 결과·가중치·앱 녹화·자격증명은 저장소에 넣지 않습니다. 실제 자료는 Drive와 Git 제외인 스킬 private-data/에 있습니다. 새 환경에서는 스킬의 manifest/복원 도구를 사용합니다. 전체 시험은 루트에서 python -m unittest discover -s tests이며 커밋 전 성공을 별도로 확인합니다. GPU/새 학습은 별도 사용자 허락이 필요합니다.

초기 파일 도구 sfa.py도 남아 있습니다. 오래된 시작 안내는 [이전 README](docs/history/README-BEFORE-ONBOARDING-2026-11-04.md)에 보존했습니다. 그 문서의 ‘학습/앱 분석 미구현’은 당시 상태이며 현재 설명이 아닙니다.
