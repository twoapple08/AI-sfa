# GPU 속도 측정 회차 실행표 (2026-11-01 밤 준비, 실행은 사용자 지시 뒤)

근거: docs/GPT-RESPONSE-VERIFY-ROUND2-FLOWTEST-2026-11-01.md §5(첫 GPU는 본 학습과 분리한 속도 측정). 계획(학습 진행 분)은 첫 본 학습 회차에 고정하고 줄이지 않으므로, 그 전에 학습 외 시간을 실측한다.

## 전제
- Kaggle 자료 판 9(sj 포함)가 끝나고 `data-check`가 모두 0일 것.
- 사용자 GPU 지시(코드도 `--gpu-ok` 없이는 GPU push를 거부).

## 명령(한 번)
```
python tools/kaggle_seq_remote.py push --prebuilt --prebuilt-any-code --gpu-ok --fresh --minutes 60 --plan-minutes 16 --extra "--gen-minutes 15"
python tools/kaggle_seq_remote.py wait
python tools/kaggle_seq_remote.py pull 작업폴더      # save-ckpt는 하지 않는다(본 학습이 이 모델을 이어받지 않게)
```
- `--fresh`: 이어하기 자료를 붙이지 않는다. 결과를 `save-ckpt`하지 않으면 본 학습(aisfa-seq-ckpt)과 섞이지 않는다.
- `--plan-minutes 16`: 학습 진행 16분이면 네 해상도 단계(20/25/25/30% = 3.2/4/4/4.8분)를 모두 지나 단계마다 자료 읽기·걸음 속도를 잰다. 계획 끝에 전체 목록 마지막 평가까지 간다(학습 전 모델이라 생성이 상한까지 가는 최악 쪽 비용).
- `--gen-minutes 15`: 중간 생성 채점 1회 이상을 잰다.
- 판정 자료는 자료 커널이 만든 sj를 쓴다(콘솔 '판정 자료: 미리 만든 것 사용' 확인 — R4).
- 예상 GPU 사용 40–60분(주간 30시간 중).

- `--prebuilt-any-code`: 판 9 자료(cb3f34f 코드) 뒤 렌더러·정답 문장 코드가 바뀌었지만(묶음 규칙 정리·레이어 투명도) 학습 파일 3,772장 표본에서 그림·정답이 옛 코드와 모두 같다(11-02). 자료 판은 그대로 9.

## 볼 것(기록 → 계획 계산)
| 항목 | 어디서 |
|---|---|
| 커널 준비(설치·자료 붙이기) | train_console 첫 줄 ~ 학습 시작, run.json `minutes` − 마지막 기록 `minutes` |
| 단계별 자료 읽기 | 콘솔 '해상도 단계 … → …폭' 전후, `time_sec.load` |
| 단계별 걸음 속도 | `stage_steps` ÷ 단계별 학습 분 |
| 중간 평가(교사 검증·생성 채점·판정) | `val_sec`·`gen_sec`·`judge_sec` |
| 마지막 평가 예상 대 실제 | `final_est_sec`·`final_sec`·`deadline_over_sec`(M-01) |
| 메모리 | `rss_gb`·`sets_loaded`(M-02, 1080 단계 RAM 29GB 한도) |
| 실패 | `fail_min`·`stop`(failures면 원인부터) |

계획 계산(성적을 보지 않고 시간만으로)
- 회차마다 학습 외 시간 = 준비 + 그 회차 단계 자료 읽기 + 중간 평가(간격당) + 마지막 평가 몫 + 정리 3분
- 계획(학습 진행 분) = 사용자 벽시계 예산 − Σ회차 학습 외 시간 → 첫 본 학습 회차 `--plan-minutes`로 고정

## 측정 뒤 사용자에게 올릴 것
- 위 표 실측값, 계산한 계획 분, 회차 수·길이 제안, 본 학습 시작 명령.
