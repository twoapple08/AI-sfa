# AI-sfa 현행 인수인계 — 2026-11-08 (새 세션용)

한국어로만 답한다(중간 안내 포함). 브랜치 `claude/new-session-gknz4t`만 쓴다(main 읽기/쓰기 금지). 작업 브랜치 `claude/smear-detection-redesign-3032w2`에도 같은 커밋을 올려 왔다. 저장 전 원격 fetch·다른 변경 보존. 커밋 전 루트 `python -m unittest discover -s tests` 전체 OK/exit0을 따로 확인한다(최근 510개 OK). GPU/새 학습/Kaggle 실행은 사용자 명시 승인 뒤에만.

이전 HANDOFF 전문(11-05~11-08 경과, 변환기·SFA화·60초판·단계 2 상세)은 `docs/history/HANDOFF-2026-11-08-before-new-session.md`에 그대로 보존했다. 필요한 갈래만 찾아 읽는다.

## 지금 할 일(사용자 11-08 지시)
**"새 세션에서 가장 위에 체크 안 된 것부터 하나씩."** 체크 목록은 `docs/REPLAN-PLAN-DRAFT-2026-11-05.md` 맨 위 '체크 목록'이다(PDF로도 사용자에게 줬다). 위에서부터 `- [ ]` 항목을 하나씩 처리한다. 항목마다 시작 전에 무엇을·왜·얼마나 걸릴지 한 줄로 말하고 시작한다. 끝나면 체크하고 근거·커밋을 적는다. `[~]`(진행 중/부분)와 '11-08 대체됨' 표시는 건너뛴다.

위에서부터 순서(11-08 기준):
1. ~~원본 가닥 방향 지정~~ — 11-08 새 세션 완료(체크 목록 근거 참고). 11-09 1231 빨강 정강이·1176 앞뒤 수정까지 반영.
2. ~~예전 v18 모양으로 둔 곳 정리~~ — 11-09 완료: 6곳 모두 유지(사용자 "잘되어있는데 왜 바꾸냐").
3. 직진 후보에서 아예 빠진 장면 점검.
4. 자동 탐지의 손·신발 오탐(의미 판정).
5. 새 구간에 처음부터 적용(정립한 기술의 재사용 시험). 손목이 상대 손에 잡혀 팔이 꺾이는 RTMW 오류(1036·1037·1230·1231에서 4회)를 먼저 점검한다.
6. 깊이 칸에 파편(debris) 넣기(파편 추출기 필요).
7. 옛 기준판·GPT 테두리 시험 파일의 레이어 번호 결함.
8. 이어서 11-06 구조 재검토 항목(결합 경로 A/B/C 등), 전용 도구 항목, 단계 1~6 남은 항목(단계 2는 **끝 기준 대비 미달**: 18구간 28초 vs 초안 300구간·20분).

## 스미어 현재 상태(반완성·보류)
- 절차: 스킬 `.claude/skills/stickman-extraction/references/SMEAR-PIPELINE.md`(스틱맨 확정 → 탐지/사용자 확인 라벨 → `smear_from_labels` → `sfa_axial_smear` → `sfa_depth_layers` → `smear_checks` → `sfa_overlay_video`).
- 장면 설정: `scenes/nian41_1032-1271_smear.json`(인물색→slot, extra, pose_fixes, drop, smear_size, depth_flat), `scenes/nian41_1032-1271_axial_smear.json`(axial_overrides 부위별 키, stretch_directions, forced_streaks).
- 용어: **앞뒤** = 직진 갈래(폭 팔 굵기×1.6, 선 굵기 75%), **좌우** = 원본 측정 v18 지그재그(`keep_v18`) 또는 GPT 표시 테이퍼. 회전 `rotate_deg`는 삼각함수 기준(음수=오른쪽이 내려감).
- **전달물은 깊이 칸 판만**(SFA + 원본 겹침·SFA만 영상). 앱은 레이어를 번호순으로 그린다(`sfa_layer_order`).
- 최신 결과: Drive `AI-sfa/04_SFA시험작/nian41_10초_1176앞뒤_1231다리_2026-11-09/`(방향 지정 + 1231 다리 + 1176 앞뒤, SFA `8c001c0f…`, 앱 확인 전). 그 전: `..._방향지정_2026-11-08/`, 그 전 판: `AI-sfa/04_SFA시험작/nian41_10초_1230팔_2026-11-08/`(깊이 칸 SFA·영상, 스미어 99, 검사 통과). 그 직전 판(`..._판정반영2_...`)까지 사용자 앱 확인 "잘됐음". 1230 팔 펴기판은 앱 재확인 전.
- 상세 경과: `docs/SMEAR-AXIAL-STREAK-2026-11-08.md`, `docs/DEPTH-LAYERS-2026-11-08.md`, `docs/SMEAR-DETECTION-REDESIGN-2026-11-07.md`, 이전 HANDOFF 보존본.

## 새 환경 복원(비공개 자료, Git 제외)
- Drive는 환경 rclone 리모트 `gdrive:`(drive.file 범위)로 접근한다. 사용자 공유 폴더는 `--drive-root-folder-id`로 읽는다.
- 원본 영상: 스킬 `data/artifact_manifest.json`의 Drive ID `16KkKd-rqx_NEtjBTcJ8Hpug8q61ujFVG`(SHA `5736947008f14fe3…`). 프레임은 `ffmpeg -i video.mp4 -vf "select=between(n\,1032\,1271),crop=1152:648:0:63" -vsync 0 -start_number 1032 frames/%d.png`.
- RTMW: manifest Drive ID `16MtJnEfLU1U66-DFCdgk1QZAldDQRN-c`(SHA `6c7905164776c208…`).
- 스미어 입력 3종(스미어 전 스틱맨 `c3a1777c…`, 확인 라벨 `a9a38222…`, 사슬 틀 `dfb2ef3e…`): Drive `AI-sfa/02_분석자료/스미어파이프라인_입력_2026-11-08/`.
- 새 컨테이너에는 rclone이 없을 수 있다: 공식 zip을 받아 `/usr/local/bin/rclone`에 두고 `RCLONE_CONFIG=/dev/null`로 실행한다(리모트는 환경변수 `RCLONE_CONFIG_GDRIVE_*`). libegl1은 `apt-get update` 뒤에 설치된다.
- 테스트 의존성: opencv-python-headless, scikit-image, skia-python(+libegl1), CPU torch/torchvision, pandoc(문서 PDF).

## 지킬 것(이번 세션에서 받은 지적)
- 요청 범위만 바꾼다("팔을 펴랬지 누가 스미어 형식도 바꾸래?"). 더 나은 변경은 먼저 묻는다.
- 승인 뼈대를 자동 교정하지 않는다. 자세 교정은 원본 판독 좌표로 장마다 `pose_fixes`에 적는다. **다만 원본과 분명히 어긋난 장을 Claude가 찾았으면 고칠지 묻지 말고 고쳐서 전후 시트로 보인다**(11-09 사용자 "고쳐야지 당연한거 아니야?"). 금지는 일괄 자동 교정이다.
- 앞뒤(깊이 칸)가 원본과 다른 장은 장면 설정 `depth_user`(frame, front, back, kind)로 지정한다. 측정보다 우선한다(11-09 1176).
- 스틱맨 팔다리 끝은 스미어 끝 밖으로 나오지 않는다(스미어를 늘린다). `smear_checks --scene`으로 검사한다.
- 체크 표시와 단계 완료를 혼동하지 않는다. 끝 기준과 비교해 말한다.
- 결과는 그림·영상으로 먼저 보이고, 영상은 MP4도 함께 준다.
