# SFA 변환기 목적함수 보정 준비·실제 출제 감사 — 2026-11-03

## 그림부터

[실제 출제 입력 / SFA 정답 / 기존 모델 첫 객체 CPU 진단](https://drive.google.com/file/d/1okfO1r3mx7FBYej05aBNQrWcfC_64HjJ/view).
이 그림은 기존 가중치의 첫 객체만 자른 진단이다. 새 가중치의 개선 결과나 전체 자유 생성 품질 판정이 아니다. 입력과 정답에는 배경·곡선·면·번짐이 있지만 기존 모델 첫 객체는 그 구성을 놓치는 사례가 보인다. 첫 객체가 그림 전체를 재현해야 한다는 뜻은 아니다.

## 사용자 요청과 유지 범위

사용자는 모션을 추출하더라도 이펙트·배경 연출을 SFA로 깔끔하게 옮기지 못하면 학습에 쓸 수 없으므로 변환기도 수정하라고 요청했다. 현재 GPT 전담을 유지하며 Claude 자료는 사전 준비다. 추가 Kaggle 30시간은 현재 계정 시간을 소진한 뒤 별도 계정을 연결할 예산이다. 아직 연결된 것으로 가정하지 않는다.

이번 구현은 출제기·토큰 문법·생성 정책·공식 합격선을 그대로 두고 손실함수의 균형을 비교하는 실험 준비다. 이 단계만으로 이펙트·배경 변환이 완성됐다고 하지 않는다. 아래 준비 기록 시점에는 GPU 미실행이었다. 이후 사용자 명시 승인으로 시작한 최신 상태는 끝의 실행 절을 따른다.

## 실제 문제를 내는 방식 — 파일·코드 근거

`tools/sfa_compose.py`의 AC/FR 연결 묶음(unit)을 여러 SFA에서 가져와 위치·크기·반전·굵기·겹침 순서 등을 바꾼다. 변형 SFA를 렌더하고 영상 압축한 그림이 입력, 같은 변형 SFA의 토큰이 정답이다. `tools/seq_data.py`가 문제를 미리 만들며 매 업데이트마다 새로 출제하는 구현은 아니다.

실제 장은 목표 약30%이고 부족분은 조합으로 보충하므로 실현 비율을 고정30/70으로 설명하지 않는다. 큰 실제 장은 연결 묶음을 보존한 부분 문제 `real_crop` 경로도 있다. 일부 흰 바탕 문제에는 합성 배경·그림자·빛 등이 들어간다.

Kaggle 저장 자료의 커밋은 `f731e51033050b0c8c44866ccde0b9bf472d1b42`, version10·maxlen2048이다. 기본 sd의 40,050문제는 조합33,799·실제5,295·실제 부분956이다. sv는965문제이며 기존 겹침 제외 규칙을 적용한 후 검증 대상을 선정한다. 자료가 기록한 7개 출제 관련 코드 해시와 현재 코드가 모두 일치했다.

실제로 받은 조합100문제에는 곡선86·면51·글로우45·레이어 투명도41·흰색 아닌 배경40문제가 있었다. 별도 실제15문제에는 곡선15·흰색 아닌 배경15문제가 있었다. 이 115문제 전부의 엄격 문법·종료·칸 번호 검사가 통과했다. 일부 파일의 표본이며 전체4만 문제의 기능 비율로 확대하지 않는다.

**해석 정정:** 원본403파일22,371장의 토큰 길이 중앙값360,2048초과1,931장은 원본 통계다. `real_crop`과 조합 재시도가 있으므로 이를 실제 학습 누락률로 해석하면 안 된다. 전체 원본 이펙트가 학습 문제에 얼마나 보존됐는지는 별도 coverage 감사가 필요하다.

## 무엇을 수정했나 — 코드·CPU 계산

- `seq_train.token_loss`로 기존 토큰별 손실 계산을 분리했다. 기존 `loss_fn`의 평균·정확도·토큰 수는 보존한다. 기존 기본 경로와의 수치 일치를 시험했다.
- `seq_objective.py`에서 기본 손실에 종료/계속0.2·첫 객체0.2·색/배경색/굵기/글로우/면 참조0.1의 보조 손실을 더하는 `balanced-v1`을 추가했다. 수치는 실험 후보이며 확정 최적값이 아니다.
- 종료/계속은 EOS가 문법상 가능한 위치에서만 계산하고, 장별 끝의 종료와 중간의 계속을 각각 평균한다. 객체가 많아 종료 한 토큰이 묻히는 현상을 줄이는 목적이다. 조기 강제종료나 객체 수 제한을 추가하지 않는다.
- 첫 객체는 첫 타입부터 해당 객체의 스타일·좌표·연결 전체를 포함한다. 외형 보조항은 특성군별 평균으로 균형을 잡으며 나머지 토큰도 기본 손실로 계속 학습한다.
- `seq_target_audit.py`는 원본 통계와 실제 출제 npz 검사를 구분한다. `seq_refinement_audit.py`는 실제 출제 표본에서 기존 모델의 로그잇 기울기와 그림을 CPU로 확인한다.

정답 judge 184열의 EOS·칸 정합성이 통과했다. 별도 실제 출제 CPU 표본3개에서는 정답 끝 선택이 EOS·EOS·LAYER였다. 마지막 표본은 EOS 기울기가 -0.02381에서 -0.12381로 바뀌어 종료를 밀어 주는 방향을 확인했다. 이는 손실이 의도한 신호를 주는 증거이지 새 가중치 품질 개선의 증거가 아니다. 가중치·옵티마이저 업데이트는 없었다. 기존 judge6장의 종료 실패를 모든 학습 문제에 일반화하지 않는다.

## 준비된 작은 비교와 평가

`profiles/seq_refinement_balanced_v1.json`, `tools/seq_refine.py`, `tools/kaggle_seq_refinement.py`를 준비했다.

| 항목 | 고정 조건 |
| --- | --- |
| 출발 가중치 | 2회차 best,78709걸음 |
| SHA-256 | `636145f296d0434adaefb6cc9908f6ef1e3be4023bbacced811e198d7c67854e` |
| 두 분기 | 기존 token-v1 / 보정 balanced-v1 |
| 업데이트 | 각각500회,같은 입력 묶음과 순서·시드·새 옵티마이저 |
| 학습률 | 0.00001 |
| 시간 제한 | 순수 학습 각각20분,합계 최대40분.학습·평가 하위프로세스75분 제한(설치·입력 준비 별도) |
| 입력 | 기존 sd,640폭·2048문맥.해상도 커리큘럼 재시작 안 함 |
| 검증 | 기존 sv 겹침 제외 후 고정64문제,기존 토큰 손실·정확도 |
| 그림 | 출력 보기 전 고정한 검증 앞6장과 기능별 학습 진단 표본,부모·두 분기 동일 자유 생성 |
| 실행 장소 | 새 비공개 aisfa-seq-refine-ab-v1.기존 공식 학습 커널 유지 |

실행 코드는 커밋 SHA,자료 커밋과 출제 코드 해시,부모 가중치 SHA를 고정하고 다르면 시작 전 중단한다. 기존 ckpt/best를 덮지 않는다. OOM/비유한 기울기는 자동 건너뛰지 않는다. 한 분기라도500회를 못 마치면 업데이트 수가 같은 완료 비교로 세지 않는다. 기본 명령은 CPU 계획 저장이고 `--run-gpu`/`--push --gpu-ok`가 있어야 실제 학습한다.

재학습 결과는 입력/정답/부모/기존/보정 그림을 먼저 비교하고 자연 종료·한도 종료·객체/위치·색/면/글로우/배경을 함께 본다. 단순 손실 감소나 빨리 끝났다는 이유로 성공 판정하지 않는다. 기능별 학습 표본은 일반화 검증과 분리한다. 작은 비교 자체가 공식 새 합격 판정이나 전체 애니메이션 연출 변환 검증을 대신하지 않는다.

## 검증·남은 일·보관

루트 `python -m unittest discover -s tests` 전체236개 통과. 기존227개와 종료 기울기·불법 EOS 위치·객체 수 희석 반례·외형 칸·정답 오류 거부·원본 가중치 보호·실제 npz 기능·비공개 실행 고정 등 새9개를 포함한다. GPU 경로 자체의 실동작은 아직 검증하지 않았다.

준비 당시 남은 일은 GPU 실행 허락 뒤 작은 비교 실행 및 실제 생성 그림 검토였다. 이후 실행 승인을 받아 시작했으며 최신 상태는 아래를 따른다. 그 결과로 보정 채택·재설계·긴 문제 처리 우선순위를 결정한다. 현 단계에서 본 학습을30시간 추가 예약하지 않는다.

비공개 자료: `/workspace/ai-sfa-private/seq_refinement/`의 `prebuilt_metadata/`, `problem_samples/`, `target_audit.json`, `problem_audit.json`, `loss_audit/`, `prepared_gpu_plan/`, `tests.log`. Drive: [objective_refinement_2026-11-03](https://drive.google.com/drive/folders/1MQpAXinaqWrvmnVIFZvGuYehhI95_Zgl). 원본·문제 npz·그림·가중치는 저장소에 넣지 않는다. 기존 판정 JSON은 수정하지 않았다.


## 최신 실행 — 2026-11-03 12:21 UTC / 한국21:21

사용자가 “Claude가 내일이면 다시 가능하니까 Kaggle 모니터링은 걔에게 맡기고 GPT는 시작만”이라고 지시했다. 이 명시 승인으로 위 고정 조건의 비교만 실행했다. `Kernel version 1 successfully pushed` 응답 후 **RUNNING** 상태를 확인했다. 학습 업데이트·완료·품질 개선까지 확인한 뜻은 아니다. GPT는 장시간 모니터링이나 후속 학습을 시작하지 않는다.

- 작업: [twoapple08/aisfa-seq-refine-ab-v1](https://www.kaggle.com/code/twoapple08/aisfa-seq-refine-ab-v1), 비공개·T4.
- 실행 코드: `fd936f08c9befc432fca136551debf7742411907`. 준비 기록 SHA: `3093b0dbaeb1bed80697e38e6d157b2cddbb033f`.
- 자료/부모 가중치는 위 SHA로 고정, 기존 공식 `aisfa-seq-train` 및 `aisfa-seq-ckpt`는 그대로 유지.
- 시작 전 계정 GPU: 사용19.26시간·남음10.74시간·총30시간. 다음 초기화11월7일00:00 UTC(한국09:00). 추가 계정30시간은 아직 연결 전이다.

Claude의 다음 확인 명령(읽기 전용):

```bash
kaggle kernels status twoapple08/aisfa-seq-refine-ab-v1
```

완료 또는 오류 상태라면 새 비공개 로컬 폴더로 받는다. 이 명령은 기존 자료 커널 전체3,000파일을 받는 작업이 아니다.

```bash
kaggle kernels output twoapple08/aisfa-seq-refine-ab-v1 -p /workspace/ai-sfa-private/seq_refinement/kaggle_output
```

먼저 `refinement_run.json`의 rc/오류, `refinement_console.txt`, `pinned_inputs.json`을 확인한다. 이어 `comparison/results.json`의 두 분기500업데이트·complete/comparable, `run.json`의 자료/순서 해시, `train.jsonl`을 확인한다. 실패·시간 초과·업데이트 수 불일치는 성공 비교로 세지 않는다. 출력이 없는 경우에도 자동 재실행하지 않는다.

그림은 `comparison/parent/`, `comparison/token-v1/`, `comparison/balanced-v1/`의 `probe_*.png`/`probes_native.png` 및 `probes.json`을 같은 번호끼리 대조한다. 각 단일 시트는 입력/해당 모델/정답 순이다. 기능별 학습 표본과 검증 표본을 구분하고, 종료만 좋아져 그림을 덜 그리거나 배경·이펙트가 빠진 경우 개선으로 세지 않는다. 새 pt/그림/상세 진단은 Drive `AI-sfa/02_분석자료/seq/run2_2026-11-03/objective_refinement_2026-11-03/`에 보존한다. 합격선·기존 판정 JSON을 고치지 않는다. 장기3회차나 추가 실행은 별도 사용자 허락이 필요하다.


## 2026-11-04 KST — 사용자 요청 상태 조회: 학습 전 ERROR

- 읽기 전용 `kaggle kernels status twoapple08/aisfa-seq-refine-ab-v1` 결과 `KernelWorkerStatus.ERROR`.
- 진단 파일만 선택 다운로드. 비공개 위치 `/workspace/ai-sfa-private/seq_refinement/kaggle_output_check_20261104/`. `refinement_run.json`: rc1,wall_seconds461.28920912742615(작업 내부 약7분41초,설치 등을 포함한 전체 GPU 사용 시간으로 해석하지 않는다).
- `refinement_console.txt`에서 `seq_refine.py:73`, `ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)`가 `OSError: cannot open resource`로 실패했다. Kaggle에 이 고정 글꼴 경로가 없다. GPU 메모리 부족/시간 소진으로 판정하지 않는다.
- 파일/코드 대조: `train_pair`는 기준 모델 평가와 `generate_probes(...,'parent',...)` 이후에 업데이트 루프에 진입한다. 이 그림 생성에서 실패했으므로 기존/보정 각500회 학습은 시작하지 못했다. `comparison/run.json`은 계획/고정입력 기록이며 완료 증거가 아니다. `comparison/results.json`도 출력되지 않았다.
- 기존 공식2회차 가중치/커널은 변경하지 않았다. 개선 비교 결과는 없으며,새 학습 성공으로 세지 않는다. 글꼴 로딩의 대체 경로/기본 글꼴 처리를 넣고 없는 환경에서 그림 생성을 검증하는 것이 다음 수정이다. 이번에는 상태 조회·진단 수령만 했고 코드 수정/재실행/추가GPU/학습은 하지 않았다. 현재 잔여 GPU 시간도 조회하지 않았다.
