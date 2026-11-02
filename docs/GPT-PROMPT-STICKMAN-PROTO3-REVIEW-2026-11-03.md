# GPT 답장 프롬프트 — 스틱맨 시제품 3 결과물 검토(2026-11-03, 기존 GPT 세션용)

시제품 2용 프롬프트를 시제품 3으로 바꿨다(시제품 2 검토는 보내지 않아도 된다).

```
claude/new-session-gknz4t 브랜치(main 아님)를 받아 줘. 스틱맨 시제품이 사용자 앱 판정을 거쳐 3까지 왔다. 시제품 1은 조작 문제없음, 떨림, 목 추가, 몸 선 굵게였다. 시제품 2b는 굵기를 롤백했고 목은 문제없었지만 떨림이 남았다. 진행 방식대로 설계 토론이 아니라 결과물 검토만 부탁한다.

읽을 것: docs/STICKMAN-PROTO2-B300-334-2026-11-03.md(특히 '시제품 3' 절), tools/rtmw_to_stickman_2d_v2.py(drawing_segments, keypose_fit, pchip_wrap, fit_all), tests/test_rtmw_to_stickman_2d_v2.py, data/stickman_motion/proto3_B300-334_report_2026-11-03.json
볼 것(Drive): AI-sfa/02_분석자료/stickman_proto_2026-11-03/proto3/ 의 B300-334_proto3_compare.mp4·_slow.mp4·B300-334_proto3.sfa·_joints.json. 원본·RTMW 경로는 시제품 1 때와 같다.

확인해 줄 것(짧게, 근거 표시 구분: 파일·코드 / CPU 계산 / 원본 눈 판독 / 추론):
1. 떨림 원인 판단(원본 3컷 작화: 새 그림 장 이동 0.07 이상, 사이 장 0.007–0.016)과 그림 구간 13개가 원본과 맞는가.
2. 키포즈를 그림 구간 가운데에 놓고 PCHIP으로 잇는 방식의 문제(타이밍이 원본보다 앞당겨지거나 늦어지는 곳, 범위 끝 300·334 처리).
3. 원본 대비 가장 어색한 장과 원인 후보(장 번호로). 문서·보고 수치에서 틀린 것.

사용자 판정이 최종이다. 새 설계 라운드를 열지 말고, 문제가 없으면 '이견 없음'과 눈 판독 요약 몇 줄만 답해 줘. 고칠 것이 있으면 전문을 docs/GPT-STICKMAN-PROTO3-REVIEW-2026-11-03.md로 같은 브랜치에 저장하고 커밋 SHA와 Claude 전달 문구를 줘. 기존 판정 JSON은 고치지 말고, 원본 영상·프레임은 저장소에 올리지 마.
```
