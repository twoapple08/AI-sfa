# AI-sfa 현행 인수인계 — 2026-11-10

한국어로만 답한다(중간 안내 포함). 브랜치는 `claude/new-session-gknz4t`만 쓴다(main 읽기/쓰기 금지). 저장 전 원격을 fetch하고 다른 변경을 보존한다. 커밋 전 루트에서 `python -m unittest discover -s tests` 전체 OK를 따로 확인한다(11-10 기준 530여 개). GPU·새 학습·Kaggle 실행은 사용자 명시 승인 뒤에만 한다.

- 이전 HANDOFF(11-08~11-09): `docs/history/HANDOFF-2026-11-08-new-session.md`. 그 전: `docs/history/HANDOFF-2026-11-08-before-new-session.md`.
- **목표 정리표:** `docs/GOALS-TABLE-2026-11-10.md`. **체크 목록:** `docs/REPLAN-PLAN-DRAFT-2026-11-05.md` 맨 위(11-10 갱신).

## 현재 우선순위(사용자 11-10)

**스틱맨 추출을 '딸깍'으로 거의 완벽하게.** "전부 다 스틱맨 뽑는 기술로 가져가야 한다." 고친 내용은 장 지정 데이터가 아니라 공통 규칙(코드)으로 남긴다. 장 지정(`pose_fixes`·`visible_views`·`depth_user`·`back_views`)은 공통 규칙으로 안 되는 장에만 쓴다.

### 바로 할 일(순서)
1. 새 구간(3072–3311) 자동 추출 남은 과제. 지표는 `tools/stickman_key_eval.py`(원본 판독 키 기준, 머리 지름 단위)로 잰다.
   - 팔만 보이는 근접 3221–3241: 검출이 몸 전체를 지어낸다. 보이는 부위만 자동으로 그린다.
   - 검출 없는 장(3112–3115 빨강, 3151–3154 파랑): 이웃 장 값을 그대로 끌어와 어긋난다.
   - 다리 오차가 가장 크다(발목·무릎 1.5–2 머리).
   - 자동이 맞는 구간에서는 원본 판독 키를 빼고 자동 결과를 쓴다. 3109 빨강 키는 판독 오류이고 3164도 의심된다.
2. 새 구간 빠진 인물(약 33장)과 판독 구간 경계의 튐(약 57곳).
3. 새 구간 `back_views` 지정, 교차점 재대조, 스미어 단계.
4. 체크 목록의 나머지 `- [ ]` 항목(위에서부터).

### 사용자 확인 대기(◆)
- 10초 뒷모습 구간 판독(파랑 1054–1071·1100–1135, 빨강 1032–1052·1066–1135·1152–1160): `scenes/nian41_1032-1271_smear.json` `back_views`.
- 최신 10초 깊이 칸 앱 확인: Drive `AI-sfa/04_SFA시험작/뒷모습머리_v2_2026-11-10/`(SFA `7bb9cd60…`).
- 스미어 자동 탐지 2안(소형 판정기 학습): GPU·학습 허락 필요.

## 11-09~11-10에 정한 것(상세: `docs/DEPTH-LAYERS-2026-11-08.md`, `docs/NEW-SEGMENT-3072-3311-2026-11-09.md`)

- **앱 그리기 순서:** 앱은 DrawOrder를 무시하고, 같은 레이어 안을 ID의 파일 전체 첫 등장 순서로 그린다. `sfa_depth_layers`가 첫 장에 모든 ID를 등록한다(보이지 않는 등록 객체, Color 0). 검사는 `tools/sfa_depth_audit.py order`. 미리보기 `sfa_overlay_video`도 같은 규칙으로 그린다.
- **깊이 칸 묶음:** core(몸통·망토), head(머리 원·가면), armA/B, legA/B. 같은 인물 안에서는 머리가 맨 위다(`head_top`). 다만 뒷모습 구간(`back_views`)에서는 머리를 가로지르는 자기 팔다리가 머리 위다.
  - 뒷모습은 1차 배정을 바닥으로 고정한 뒤 더한다. 다른 인물과의 순서를 뒤집는 뒷모습 제약은 버린다(1079).
- **깊이 칸 측정 규칙:** 팔다리 끝 색(`tip`), 한 색만 보이는 겹침(`visible`), 한쪽 가림, 추론 부위는 뒤(`--hidden-report`), 같은 인물 앞쪽/뒤쪽 팔다리(검출 점수, 검증 전).
  - 검출 점수만으로 팔을 얼굴 위로 올리는 추정은 뺐다.
  - 아래팔만 따로 칸에 두려면 `depth_user`에 `0:armA_lo`처럼 쓴다(1220–1227).
- **인물 고르기:** 머리(코·눈·귀) 색 → 몸 관절 색 → 상자 비율 순서로 본다. 머리와 몸 색이 다르면 섞인 검출로 보고 버린다. 단, 같은 장에 몸 색 인물의 깨끗한 검출이 있으면 머리 색을 따른다. 승인 10초에서는 결과가 바뀌지 않았다.
- **자동 추출 정확도(새 구간 키 469개, 원본 판독 없이 자동만):**

  | 판 | 오차 중앙값 | 머리 반 개 안 | 머리 하나 안 |
  |---|---|---|---|
  | 고치기 전 | 1.18 | 20% | 44% |
  | 인물 고르기 수정 | 0.83 | 29% | 56% |
  | + `--key-motion-v2` | 0.82 | 33% | 58% |

  앞으로 새 구간 자동 추출은 `--key-motion-v2`를 켠다.
- **최신 추출 기술 확인:** 이 작업 전 마지막 판은 11-04 GPT 공통 v2(선택 옵션)다. 코드는 모두 이 브랜치에 있다. Drive `AI-sfa_Claude_세션전체전달_2026-11-07/`은 스미어 인계 자료이고, 그보다 새로운 추출 코드는 없다.
- **뒷모습 자동 판별:** 애니 얼굴 검출과 RTMW 어깨 순서로는 불안정했다(측정). 지금은 판독 구간을 쓰고, 자동 판별은 과제로 남긴다.

## 새 환경 복원(비공개 자료, Git 제외)

- Drive는 rclone 리모트 `gdrive:`다. 없으면 공식 zip을 `/usr/local/bin/rclone`에 두고 `RCLONE_CONFIG=/dev/null`로 실행한다(리모트는 환경변수 `RCLONE_CONFIG_GDRIVE_*`). 전체 목록(`lsf -R`)은 10분 넘게 걸리니, 경로를 알면 그 폴더만 본다.
- 원본 영상: 스킬 `data/artifact_manifest.json` Drive ID `16KkKd-rqx_NEtjBTcJ8Hpug8q61ujFVG`(SHA `5736947008f14fe3…`). RTMW는 ID `16MtJnEfLU1U66-DFCdgk1QZAldDQRN-c`(SHA `6c7905164776c208…`).
- 프레임(위 63px를 자른다):
  - 10초: `ffmpeg -i video.mp4 -vf "select=between(n\,1032\,1271),crop=1152:648:0:63" -vsync 0 -start_number 1032 frames/%d.png`
  - 새 구간: 같은 방식으로 3072–3311을 뽑아 `frames_new/`에 둔다.
- 스미어 입력 3종: Drive `AI-sfa/02_분석자료/스미어파이프라인_입력_2026-11-08/`.
- **11-10 작업 입력:** Drive `AI-sfa/02_분석자료/작업입력_2026-11-10/`(SHA256SUMS·읽어주세요 포함).
  - 10초 깊이 칸 입력 `r6.sfa`와 추출 보고(앞뒤)
  - 새 구간 스틱맨 fix15와 보고, 자동만 v2
  - 최신 깊이 칸 두 구간과 보고(검사 기준선)
  - 얼굴 검출 결과와 얼굴 모델(`face_detect_v1.4_n.onnx`, SHA `fd860b65…`)
- 테스트 의존성: opencv-python-headless, scikit-image, skia-python(+libegl1, `apt-get update` 뒤), CPU torch/torchvision.

## 자주 쓰는 명령(비공개 경로는 바꿔 쓴다)

```bash
# 자동 추출(새 구간): 원본 판독 키를 뺀 장면으로 돌리면 '딸깍' 성능을 잴 수 있다
python tools/stickman_clip.py rtmw.jsonl.gz video.mp4 자동.sfa --start 3072 --end 3311 --cuts <컷> --crop-y 63 \
  --select coverage --side-rule valid --projection --image-keys --key-motion-v2 --thick-ref 10:blue:3.853 235:red:0.975 \
  --scene 키뺀장면.json --report 자동_report.json
python tools/stickman_key_eval.py 자동.sfa --scene scenes/nian41_3072-3311.json --start 3072
# 깊이 칸과 검사
python tools/sfa_depth_layers.py --sfa 스미어결과.sfa --frames frames --scene scenes/nian41_1032-1271_smear.json \
  --hidden-report 추출보고.json --out 깊이칸.sfa --report 깊이칸.json
python tools/sfa_depth_audit.py order 스미어결과.sfa 깊이칸.sfa 깊이칸.json
python tools/sfa_depth_audit.py cross-flip 이전.sfa 이전.json 새.sfa 새.json --frame-base 1032
python tools/smear_checks.py 깊이칸.sfa --frame-base 1032 --same-shapes-as 스미어결과.sfa --depth-report 깊이칸.json --scene scenes/nian41_1032-1271_smear.json
# 원본 대조 시트(ab·diff·cross·heads·dets·keys)
python tools/stickman_review_sheets.py diff 이전.sfa 새.sfa --frames-dir frames --base 1032 --list 1100-1135 --out 시트.jpg
```

## 지킬 것(이번 세션 지적 요약, 전문은 AGENTS.md)

- 형식 검사 통과(뒤집힘 0, 구조 0)는 품질이 아니다. 원본과 장별·교차점별로 대조한 결과부터 보고한다. 같은 순서를 두 방식으로 비교한 시트(의도 순서와 앱 순서)는 원본 대조가 아니다.
- 명백한 오류는 묻지 말고 고친다. 잘된 것은 바꾸지 않는다. 요청 범위만 바꾼다.
- 새 규칙을 넣으면 승인 구간에서 바뀐 장을 모두 렌더 차이로 찾아 원본과 대조한다. 다른 인물과의 순서가 뒤집히지 않았는지(`cross-flip`)도 본다.
- 가려진 몸은 숨기지 않는다(깊이 칸으로 처리). 추론 부위는 앞에 두지 않는다. 머리 지름은 가림으로 줄이지 않는다.
- 결과는 그림·영상으로 먼저 보이고, SFA와 MP4를 함께 Drive에 올린다.
