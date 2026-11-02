# GPT 답장 프롬프트 — 겹침 버그 (c) 1217 비교 결과(2026-11-03, 기존 GPT 세션용)

```
claude/new-session-gknz4t 브랜치(main 아님)를 받아 docs/STICKMAN-OVERLAP-DEBATE-2026-11-03.md의 '4차 — Claude: (c) 1217 길이·배율 비교' 절을 읽어 줘(코드: tools/stickman_clip.py --quantile/--scale-smooth/--resym/--key-sigma, tools/rtmw_to_stickman_2d_v2.py run_core resym·scale_smooth).

확인할 것(짧게, 근거 표시 구분):
1. 길이·배율 조정(c1·c2·c3)이 1217을 고치지 못하고 c2는 무릎·발목을 맞바꾸며 전체 오차·떨림을 늘린다는 해석에 이견이 있는가.
2. 키 평활 끔(d)이 1217을 조금 줄이고 가까운·먼 컷 떨림을 13–49% 늘린다는 결과를 보고, (a)+(b) 기준판 유지 + 1217 '알려진 한계' 제안에 이견이 있는가.
3. c3(fallback 뒤 재대칭)을 기본값으로 바꿀지에 대한 의견.

이견이 없으면 '이견 없음'과 짧은 의견만. 전문이 필요하면 docs/GPT-STICKMAN-OVERLAP-ROUND5-2026-11-03.md로 같은 브랜치에 저장하고 커밋 SHA와 Claude 전달 문구를 줘. 코드는 고치지 말고, 원본 영상·프레임·관절 원좌표 전체는 저장소에 올리지 마.
```
