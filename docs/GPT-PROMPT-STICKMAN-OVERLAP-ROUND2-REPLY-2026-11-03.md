# GPT 답장 프롬프트 — 겹침 버그 (a)·(b) 구현 결과 검토(2026-11-03, 기존 GPT 세션용)

```
claude/new-session-gknz4t 브랜치(main 아님)를 받아 docs/STICKMAN-OVERLAP-DEBATE-2026-11-03.md의 '2차 — Claude: (a)·(b) 구현과 비교' 절을 읽어 줘. 코드: tools/rtmw_to_stickman_2d.py(pick_target select='coverage'), tools/rtmw_to_stickman_2d_v2.py(keypose_fit side_rule='valid'), tools/stickman_clip.py(--select, --side-rule). Drive AI-sfa/02_분석자료/stickman_proto_2026-11-03/overlap_bugs/ab/(비교 영상·SFA·before_after 시트·joints)와 overlap_bugs/pick_changes.jpg도 봐 줘.

결과물 검토만 부탁한다(짧게, 근거 표시 구분).
1. 바뀐 선택(빨강 1223–1226, 파랑 1076·1077·1151)과 유지된 1162가 원본 크기에서 맞는가.
2. (a)+(b) 출력에서 새로 망가진 곳(팔·지지 다리·정지 장, 다른 컷)이 있는가 — 장 번호로.
3. 파랑 1137–1140 골반이 (b)로 올라간 것을 원본으로 어떻게 보는가(판정 불가면 그렇게).
4. (c) 1217 길이·배율 비교 전에 Claude가 확인할 것이 있는가.

새 설계 라운드는 열지 말고, 문제가 없으면 '이견 없음'과 판독 요약 몇 줄만. 전문이 필요하면 docs/GPT-STICKMAN-OVERLAP-ROUND3-2026-11-03.md로 같은 브랜치에 저장하고 커밋 SHA와 Claude 전달 문구를 줘. 코드는 고치지 말고, 원본 영상·프레임·관절 원좌표 전체는 저장소에 올리지 마.
```
