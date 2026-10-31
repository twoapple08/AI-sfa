# GPT 수집·분석 결과 1차 확인 (2026-10-17, Claude)

사용자가 Drive `AI-sfa` 폴더를 '링크가 있는 모든 사용자-뷰어'로 공유해, 서버에서 로그인 없는 공개 목록·다운로드로 확인했다. 서버 rclone은 drive.file 범위라 GPT가 올린 파일을 API로는 볼 수 없다.

## GPT가 올린 것 (목록 확인 [실측])

- `01_원본영상/yutaka_nakamura/`: `yutaka_tagged_reference_001…032.zip`(확인 시점 32개, 업로드 진행 중), `sakugabooru_posts_snapshot_2026-10-17.json`(368건), `corpus_policy_2026-10-17.json`, `external_access_check_2026-10-17.json`.
- `01_원본영상/yutaka_external_review_2026-10-17/`: Sakuga Taisen 직접 링크 영상 7개 + README. 모두 `admit_for_style_rules=false`(귀속 검토 대기).
- `00_목록/`: `external_sources.jsonl`(출처 후보 26), `external_media_results.jsonl`(7).
- `03_스타일지식베이스/`: `GPT-YUTAKA-REVIEW-2026-10-17.md`, `gpt_observations_2026-10-17.jsonl`(30줄).

## ZIP 무결성 표본 검사 [실측]

| ZIP | 크기 | testzip | 내용 | catalog md5 일치 |
|---|---|---|---|---|
| 001 | 94,190,197 B | 정상 | 57 + manifest·README | 57/57, 파일명 md5 일치 |
| 032 | 91,569,829 B | 정상 | 4 + manifest·README | 4/4 |

나머지 30개는 받지 않았다. 001에는 mp4 외에 jpg·gif 게시물도 들어 있다.

## GPT 정책·정정 (반영 여부)

- **에반게리온 제외:** GPT 정책 파일에 "사용자 요청: 에반게리온은 오래된 감각이므로 학습 대상에서 제외"로 적혀 있다(post 10개). Claude 관찰 28건에는 에반게리온이 없다. 2026-10-17 사용자 확인으로 KB·계획·AGENTS에 정식 반영했다.
- **presumed 61개:** 별도 검토 묶음, 학습 자동 편입 금지. Claude도 같은 방침.
- **귀속:** 단일 태그도 모든 컷의 단독 원화 증명은 아님. 공동 태그 8건(290894, 69068, 229832, 220613, 271644, 256847, 275235, 301585)은 개인 통계에서 보류. 301585(NGE #09) 마지막 폭발은 본인 인터뷰상 Shoichi Masuo 담당.
- **KB 일반화 정정 제안(동의):** '언제나 2톤·어두운 core'로 고정하지 않는다(239063, 250758). '1s 비중'은 화면 차이 측정이라 작화 타이밍 증명이 아니다 — Claude의 nian41 마스크 측정 결과와 같은 결론.

## 남은 일

- GPT 요청: Claude가 239063·229682·202164·224077·301585를 교차 판독한 뒤 GPT 관찰 30건을 observations에 병합.
- ZIP 업로드 완료 후 전체 manifest 대조(개수·md5).
