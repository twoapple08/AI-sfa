# GPT 답장 프롬프트 — 겹침 버그 3차 회귀 수정 확인(2026-11-03, 기존 GPT 세션용)

```
claude/new-session-gknz4t 브랜치(main 아님)를 받아 docs/STICKMAN-OVERLAP-DEBATE-2026-11-03.md의 '3차 — Claude: 회귀 원인과 수정' 절을 읽어 줘. 코드는 tools/rtmw_to_stickman_2d.py pick_target(select='coverage': 몸통 소유권 검사를 후보 둘 이상일 때만). Drive AI-sfa/02_분석자료/stickman_proto_2026-11-03/overlap_bugs/ab2/(SFA·비교 영상·반속·check_1207-1236.jpg·joints)를 봐 줘.

확인할 것(짧게, 근거 표시 구분):
1. 빨강 1234–1236 회귀가 원본 기준으로 해소됐는가(기존과 같은 위치·움직임 복구).
2. 빨강 1207–1208: (b)에서 틀 안으로 접혀 있던 왼발목이 틀 밖으로 내려가고, 화면 안 팔다리 끝 거리가 13–19px 늘었다. 원본으로 보아 개선인가, 회귀인가, 판정 불가인가.
3. 이 밖에 (a)+(b) 수정판에서 새로 생긴 회귀가 있는가(장 번호로).

이견이 없으면 '이견 없음'과 판독 요약만. 전문이 필요하면 docs/GPT-STICKMAN-OVERLAP-ROUND4-2026-11-03.md로 같은 브랜치에 저장하고 커밋 SHA와 Claude 전달 문구를 줘. 코드는 고치지 말고, 원본 영상·프레임·관절 원좌표 전체는 저장소에 올리지 마. 문제가 없으면 다음은 (c) 1217 길이·배율 비교다.
```
