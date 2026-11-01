# GPT 독립 전체 코드 검토 — 2026-11-01

검토 대상: `twoapple08/AI-sfa`, `claude/new-session-gknz4t`, **`68da6ce3048a1e18bb28e19f8c9328d0e1e6a10e`**. `7e65af9` 이후의 `2849b53` 수정도 포함한다. 아래 줄 번호는 이 SHA 기준이다. Claude의 검토 결론을 승인하는 방식이 아니라, 필독 문서 → 전체 코드 → 독립 반례 순서로 검토했다. 소스 수정은 하지 않았다.

**판정: CPU 기본 경로와 기존 회귀 시험은 작동하지만, 실제 업데이트 기록·만점 채점·공식 평가 목록 확인·PC 실행에 고칠 문제가 있다. 전체를 ‘구현 쟁점 없음’으로 닫을 수 없다.** 치명 등급으로 확정할 지적은 없다. 높은 등급 7건, 중간 등급 3건을 아래에 기록했다. 발생 빈도가 확인되지 않은 인공 반례를 실제 자료의 상시 결함으로 확대하지 않는다.

## 1. 범위와 직접 실행한 것

### 읽은 범위

- `AGENTS.md` 전체, `HANDOFF.md`, `docs/HANDOFF-PROMPT.md`.
- 지정한 판정 기준·구현·조합 학습·재설계 문서 네 개 전체.
- `docs/GPT-*-2026-11-01.md`에 해당하는 기존 문답 12개 전체(재현 부록 포함). 과거 검토의 실측은 인용 자료이며 이번 독립 실행과 구분했다.
- 핵심 17파일 **6,513행 전체**: `seq_train.py`, `seq_data.py`, `seq_judge.py`, `seq_bundle.py`, `seq_check.py`, `seq_trend.py`, `seq_flow_small.py`, `sfa_tokens.py`, `sfa_render.py`, `sfa_compose.py`, `sfa_objscore.py`, `sfa_paint_synth.py`, `vec_data.py`, `vec_train.py`, `kaggle_seq_worker.py`, `kaggle_seq_remote.py`, `pc_seq_run.py`.
- `tests/`의 Python 시험 23파일 **2,394행 전체**.
- 나머지 `tools/`는 추적 파일 242개 중 위 파일들을 제외한 목록·Python 로컬 import·실행 명령을 확인했다. 현재 경로에서 추가로 호출되는 `pc_vec_run.py` 전체, PC 배치 4개를 상세 검토했다. 보조 진단 `seq_diag.py`, `sfa_tokens_check.py`, `measure_toklen.py`, `analyze_toklen.py`도 읽었다. 나머지를 현재 학습에 사용하지 않는다는 판단은 이 호출 관계 기준이며, 과거 다른 학습 체계 전체의 정확성을 보증하지 않는다.
- `vec_train`의 현재 역할은 주로 `Yielder`, `low_priority`, `save`이고, `vec_data`에서는 파일 목록·영상 입출력이 사용된다. 옛 픽셀 지도 학습·조립은 현행 `seq_train`의 정답 경로가 아니다. 따라서 옛 정답 지도의 한계를 현행 모델의 새 결함으로 세지 않았다.

### 실행과 한계

| 구분 | 이번에 직접 확인한 결과 |
|---|---|
| 전체 시험 | 의존성 설치 후 `python -m unittest discover -s tests -v`: **142개, 15.818초, OK, 건너뜀 없음**. 첫 시도는 torch·cv2 등 환경 의존성 부재로 실패했으며 코드 실패로 집계하지 않았다. |
| CPU 실행 경로 | 자체 생성한 2장짜리 자료, 입력 폭 128→96→80→64, ResNet18·폭 32·1층. 다운로드를 막고 CPU 2스레드로 실행. 첫 회차 45 업데이트, 연장·재개 뒤 88 업데이트. 옵티마이저 내부 step도 45→88. 네 단계 정규 업데이트, 섞기, 단계별 분위 100% 유지, 계획 끝 종료, 검증 실패 0 확인. 실제 1080·전체 자료의 19항목 통합 시험을 재실행한 것은 아니다. |
| PC 빠른 시험 회귀 | 같은 시간 옵션을 작은 실제 학습기에 적용: 4분 요청과 1분 이어하기 **모두 0걸음**. I-04. |
| 채점 반례 | 인공 XML을 실제 채점기·Skia 렌더러로 비교. I-02·03·10. |
| 판정 자료 | 고정 목록 46장, **640폭만 로컬 재생성**. 외움 기준선 12.943391점 확인. GPU·Kaggle 호출 없음. |
| 외움 반례 | 원래 자리 정답만 저장한 184개 변환 템플릿 검색: 92/92 입력의 템플릿 선택 성공, **45/45승, A=99.799942, 엄격 F1=100%, 건전성 통과**. P-01. |
| 자료 경계 | 학습 403파일 × 파일당 난수 6장: 묶음 25,412개 중 다중 레이어 1개, I-09의 레이어 순서 불일치 0개. 씨앗·표본에 한정한다. 학습·시험 441파일의 Sequence `Thickness`는 모두 미지정이었다. |
| GPU·앱·원격 자료 | **GPU·Kaggle 실행 없음**, Windows/Stick Fighter 앱 실행 없음. Kaggle 판 8 전체 자료를 내려받거나 전체 정합성을 다시 검사하지 않았다. |

실행 환경: Python 3.12, torch `2.15.0+cpu`, torchvision `0.29.2+cpu`, OpenCV `5.0.0`, Skia `144.1`, ffmpeg. 재현용 XML·판정 npz·작은 모델 저장본은 저장소 밖 임시 경로에만 두었다. 원본 영상·원본 SFA·가중치·키는 이 보고서 커밋에 추가하지 않는다.

보고서 작성 뒤 부록의 Python 코드 블록 8개도 그대로 각각 실행했다. 7개는 정상 종료했고, scipy 부재를 주입하는 B-3은 의도한 `ModuleNotFoundError`로 종료했다. 기재한 핵심 수치가 재현됐다.

## 2. 구현 결함

### I-01 — 높음: FP16 업데이트 건너뜀을 성공한 학습으로 기록한다

- **위치:** `tools/seq_train.py:1018`–`1023`, `1055`–`1074`.
- **근거:** 유한한 loss를 확인하지만 기울기의 유한성이나 GradScaler의 step 생략은 확인하지 않는다. `scaler.step(opt)`가 inf 기울기 때문에 업데이트를 하지 않아도 `step`, `sel` 성공, `stage_steps`, `expo`, `train_min`을 올리고 연속 실패를 0으로 만든다. ‘실패 시간은 학습 진행 밖’이라는 최근 결정이 이 경로에는 적용되지 않는다. GradScaler가 꺼지는 CPU/bf16에서는 비유한 기울기가 옵티마이저에 들어갈 위험도 있다.
- **직접 재현:** CPU GradScaler에 유한 loss=1, 역전파 뒤 inf 기울기를 주입했다. 가중치 **1→1**, scale **65536→32768**인데 현행 성공 분기로 이어진다. 부록 B-1은 GPU 없이 실행된다. GPU에서 자연 발생한 빈도를 측정했다는 뜻은 아니다.
- **수정 방향:** unscale 뒤 gradient norm/기울기를 검사하고 실제 업데이트 성공 여부를 확인한 경우에만 성공 기록·학습 시계를 올린다. AMP skip은 `fail_min`·연속 실패에 포함한다. scaler 비활성 경로도 비유한 기울기를 막는다. 성공 기록 합계와 옵티마이저 step을 비교하는 시험에 강제 overflow를 넣는다.

### I-02 — 높음: 같은 선·면 색이면 순서가 무관하다는 가정이 틀리다

- **위치:** `tools/sfa_objscore.py:310`–`325`, `344`–`345`.
- **근거:** `look`이 같은 오브젝트 쌍은 순서 검사를 생략한다. 검정 테두리+빨간 채우기를 가진 원 두 개가 겹치면, 나중 원의 채우기가 앞 원의 검정 테두리를 덮는다. 색 목록이 같아도 두 그리기 연산은 교환 가능하지 않다.
- **직접 재현:** 부록 A `same_fill_order`: 순서만 뒤집어도 **perfect=True, fill_f1=1, order=None**, 렌더 차이는 **1,224화소**, 흐림 비교는 **2,222화소**였다. ‘만점이면 영상도 같다’ 원칙의 반례다. 앱 실측은 아니다.
- **수정 방향:** 스타일 튜플 동일을 ‘겉모습 순서 무관’의 충분조건으로 쓰지 않는다. 면+선처럼 여러 연산으로 그리는 오브젝트는 보수적으로 순서를 검사한다. 순서 면제는 실제 교환 가능함을 확인한 경우로 한정한다.

### I-03 — 높음: 글로우·면의 실제 범위가 겹치는 순서 차이를 놓친다

- **위치:** `tools/sfa_objscore.py:303`–`308`, `323`–`325`.
- **근거:** 순서 후보의 경계는 기하 점/원의 경계와 선 두께뿐이다. 글로우 두께·반경을 보지 않고, 면 전체 경로가 주인 오브젝트 경계보다 넓을 수도 있다. 떨어진 선 두 개의 번짐이 겹치는 경우에도 순서를 무관하다고 처리한다.
- **직접 재현:** 부록 A `glow_order`: y=45와 55인 평행선에 다른 색 글로우(반경 30, 두께 200, 알파 200)를 주고 순서 교환. **perfect=True, order=None**, 실제 차이는 **14,922화소**, 흐림 비교 **14,940화소**.
- **수정 방향:** 선·글로우·면을 포함한 그리기 범위로 순서 후보를 만든다. 면 주인의 경계는 그 면을 이루는 모든 조각·자동 연결선·구멍을 반영한다. 글로우는 허용 오차에 따른 유효 번짐 범위를 사용한다. 단순 확대 경계도 안전한 방향이며, 불확실한 경우 순서를 생략하지 않는다.

### I-04 — 높음: 1050 Ti 빠른 시험은 정상 종료해도 학습을 한 번도 하지 않는다

- **위치:** `tools/pc_seq_run.py:82`–`87`; `tools/seq_train.py:697`–`702`, `954`–`957`.
- **근거:** PC quick은 `--minutes 4`, 재개는 `--minutes 1`인데 `--final-reserve-min`을 주지 않아 기본 **20분**이다. 첫 반복 전에 `지금+1200초 > 4분 마감`이 성립한다. 이어서도 길이별 생성 모형이 없으므로 같은 문제가 생긴다. PC 실행기는 rc=0만 보고 ‘4분 학습 정상·이어하기 정상’이라고 출력한다.
- **직접 재현:** 부록 B-2. 같은 시간·예약 설정으로 실제 `ST.main()`을 두 번 실행했다. 둘 다 **step=0, train_min=0, stop=deadline, final_est_sec=1200**. 모델과 자료는 작게 대체했지만 이 시간 분기는 현행 그대로다.
- **수정 방향:** quick 전용 작은 검증/생성 크기와 측정 가능한 평가 몫을 명시한다. 첫 실행 step>0, 두 번째 step 증가를 필수 성공 조건으로 검사한다. 4분이 GPU 계산 시간인지 전체 시간인지도 표시한다. 더 긴 자료 준비를 끝내고 0걸음으로 성공하는 현재 경로를 막는 시험이 필요하다.

### I-05 — 높음: 새 Windows PC 설치 배치에 필수 scipy가 없다

- **위치:** `tools/pc_seq_1050ti_quick.bat:28`, `tools/pc_seq_4060.bat:50`, `tools/pc_seq_5060.bat:34`; `tools/sfa_objscore.py:14`.
- **근거:** 배치는 torch/torchvision과 skia-python·opencv-python-headless·numpy만 설치한다. 현행 `seq_train → sfa_objscore → scipy.optimize`와 본 학습의 `seq_judge`는 scipy를 필수 import한다. 배치의 설치 확인도 scipy/seq_train을 불러보지 않는다. 이 패키지들의 선언 의존성이 scipy 설치를 보장하지 않는다.
- **재현 구분:** 배치와 import 경로를 정적으로 확인했고, scipy import를 차단한 Python에서 `import seq_train`이 **ModuleNotFoundError**로 끝나는 것을 직접 확인했다. Windows 신규 설치 전체를 실행한 것은 아니다. 부록 B-3.
- **수정 방향:** 세 배치의 공통 의존성 파일에 scipy를 넣고, 자료 준비 전에 `import seq_train, seq_data, seq_judge`를 검사한다. 깨끗한 CPU 환경에서 이 import 검사만 실행해도 잡을 수 있다.

### I-06 — 높음: 다른/축소 판정 자료도 ‘전체 고정 목록’으로 공식 판정될 수 있다

- **위치:** `tools/seq_judge.py:301`–`317`; `tools/seq_train.py:535`–`540`, `831`, `1152`–`1156`.
- **근거:** JudgeSet은 자료 판과 어휘만 검사한다. 저장소 manifest의 entries/묶음/해시와 일치하는지 검사하지 않는다. `js_reduced`도 `--judge-n` 옵션을 줘서 자른 경우에만 참이다. 개발용으로 이미 6장만 만든 `judge.npz`를 주고 `--judge-n`을 생략하면 ‘전체 목록’으로 간주한다. `build --manifest`와 시험 코드가 축소 자료를 만들 수 있어 개발 산출물 혼동으로도 발생할 수 있다.
- **직접 재현:** 부록 C-1. 46장 자료에서 앞 6장으로 만든 형식상 정상 npz에 `manifest_sha='wrong-list'`를 넣었다. **JudgeSet 로드 성공, N=6, 정답 생성기의 passed_all=True, official_judgment=True**였다. 전체 학습을 돌린 결과가 아니라 실제 로더·평가 함수·공식 조건의 결합 확인이다.
- **수정 방향:** 공식 자격은 `--judge-n` 여부와 별개로 현재 고정 manifest와 entries·(파일,Position)·group·방향·자료 폭/판·해시가 일치할 때만 준다. 진단용 임의 manifest는 사용 가능하게 두되 공식 자격을 명확히 분리한다. 그 식별값을 로그·체크포인트에도 남긴다. 정상 기본 Kaggle 경로의 자료가 이번에 잘못됐다는 주장은 아니다.

### I-07 — 중간: 추세 표가 비공식 결과에도 ‘통과’를 출력하고 다른 조건끼리 성장으로 비교한다

- **위치:** `tools/seq_trend.py:40`–`48`, `53`–`75`.
- **근거:** `judge_official`, `judge_reduced`를 읽지 않고 `judge_passed_all`이면 ‘통과’를 붙인다. 또 첫 기록과 마지막 기록의 판정 폭·정답 기반 생성 상한·평가 목록/`val_list`가 달라도 바로 차이를 계산한다. 해상도 전환 효과나 검증 목록 변경을 모델의 성장과 구분할 수 없다.
- **직접 재현:** `judge_official=False, judge_reduced=True, judge_w=1920, judge_passed_all=True`인 행을 `table()`에 넣으면 **`3/3(3) 통과 @1920`**이라고 나온다. 부록 B-4. `verdict()`가 조건 식별값을 검사하지 않는 것은 코드 확인이다.
- **수정 방향:** ‘공식 통과’는 공식 플래그와 자격을 모두 확인한다. 나머지는 ‘추세 기준선 초과’로 쓴다. 조건별 시계열을 나누고 변경 지점에서는 전후 점수 비교의 한계를 표시한다. `gen_partial`은 비율이고 A는 0–100점이므로 현재처럼 단위 변환을 유지한다.

### I-08 — 높음: 저장 재시도 최종 실패를 무시하고 상태 보존을 완료한 것처럼 진행한다

- **위치:** `tools/seq_train.py:708`–`715`, `1091`–`1096`, `1125`–`1137`; `tools/vec_train.py:265`–`277`.
- **근거:** Windows 파일 잠금 때 `VT.save`는 재시도 후 False를 반환한다. 호출자는 이 값을 검사하지 않고 저장 횟수를 올린다. best도 저장 성공 전에 갱신한다. 특히 마지막 공식 판정 뒤 저장이 실패하면 `official_n`은 로그/메모리에만 있고 저장본에는 이전 값이 남아, 최근에 고친 ‘연장에서 다시 공식 1회’ 문제가 같은 조건에서 돌아온다. ckpt가 낡았는데 외부 실행은 성공할 수 있다.
- **직접 재현:** 실제 `save_ckpt` 함수를 AST로 꺼내 `VT.save → False`를 주입했다. 예외 없이 None 반환, `done_min` 갱신, `rate.save` 횟수 증가. 저장 파일 성공을 확인하는 분기가 없었다. 실제 Windows 잠금 발생률을 잰 것은 아니다. 부록 B-5.
- **수정 방향:** 성공/실패를 반환해 호출자가 처리한다. 최종 저장 실패는 별도 복구 경로의 저장본을 확보하거나 종료 실패로 알린다. best 값과 공식 결과 영구 저장 완료 표시는 성공 뒤에 갱신한다. 정상 저장뿐 아니라 `os.replace` 연속 실패·최종 저장 실패를 주입하는 회귀 시험이 필요하다.

### I-09 — 중간: 조합 묶음 내부의 원래 레이어 순서를 보존하지 않는다

- **위치:** `tools/sfa_compose.py:80`–`81`, `214`–`225`.
- **근거:** 묶음에 원래 LayerDef 순서를 보관하지 않고, `place()`는 AO가 XML에 처음 나타난 레이어 순서로 새 정의를 만든다. 실제 그리는 레이어 순서와 AO 저장 순서가 다르면 같은 묶음을 통째로 옮긴다는 설계와 달리 가림이 바뀐다. 실제 장 `real_crop`의 순서 보존 수정은 이 조합 배치 경로를 고치지 않는다.
- **직접 재현:** 부록 A `unit_layer_order`: 원래 레이어 순서 1→0, AO 저장 순서 0→1, 면 참조로 한 묶음인 겹친 두 선. `keep='exact'`로 좌표·반전·크기를 유지해도 빨강→검정이 검정→빨강으로 바뀌고 **4,728화소**가 다르다.
- **범위:** 별도 실제 자료 표본 25,412묶음에서는 해당 순서 불일치 **0개**였다. 현재 학습 입력과 정답이 서로 어긋나는 결함은 아니다. 조합기가 원본 묶음의 내부 가림을 바꾸는 경계 조건이다.
- **수정 방향:** 묶음에 원래 레이어 순서와 레이어 내부 실제 순서를 넣고 `place`에서 이를 따른다. 묶음 사이 배치는 무작위여도 묶음 안의 앞뒤는 유지한다. 기존 `real_crop` 시험 외에 `place` 시험을 추가한다.

### I-10 — 중간: AC를 정답 차이에서 제외하는 원칙과 렌더러의 그룹 그리기가 충돌한다

- **위치:** `tools/sfa_render.py:326`–`344`; `tools/sfa_objscore.py:329`–`345`.
- **근거:** 같은 AC 그룹에서는 모든 글로우를 먼저 그리고 모든 선/면을 나중에 그린다. AC를 지우면 ‘첫 선 → 둘째 글로우 → 둘째 선’이 될 수 있어, 좌표·스타일·오브젝트 순서가 같아도 결과가 달라진다. 채점기는 AC를 무시해 만점이다.
- **직접 재현:** 부록 A `remove_ac`: 교차한 두 선 중 둘째에 글로우를 넣고 AC만 삭제. **perfect=True, order=1, link_f1=0**, 렌더 차이 **32화소**, 흐림 비교 **24화소**. 스틱맨 동작 자체의 큰 차이를 측정한 것은 아니다.
- **수정 방향:** 사용자가 확정한 ‘점 연결 차이는 감점하지 않음’을 임의로 철회하지 않는다. 먼저 앱에서 이 작은 사례의 연결/비연결 영상을 대조해 그룹 그리기 모델이 맞는지 확인한다. 서버 렌더러가 틀렸다면 그쪽을 고친다. 앱도 다르면 AC 자체 대신 **실제 합성 순서/동등한 그리기 결과**를 표현·검증하는 방법을 정해야 한다. 현재 근거만으로 앱이 틀렸거나 사용자 정책을 바꿔야 한다고 결론내릴 수 없다.

## 3. 정책·설계 의견과 통계의 해석

### P-01 — 중간·설계 한계: 위치 시험 통과는 ‘형상을 외우지 않음’의 증명이 아니다

- **위치:** `tools/seq_judge.py:38`–`39`, `367`–`456`; 판정 기준 §2; `tools/seq_trend.py:2`–`7`.
- **실행 가능한 반례:** 부록 C-2는 원래 자리 정답 46개만 외운다. 각 정답을 고정된 네 방향으로 변환·렌더한 184개 작은 그림을 만들고, 입력을 64×36으로 줄여 가장 비슷한 템플릿을 고른 뒤 그 템플릿의 SFA를 낸다. 추론 함수는 입력 그림·화면 비율만 사용하며 정답 방향 d나 정답 토큰을 조회하지 않는다. i는 API상 이미지·비율을 읽는 데만 쓰인다.
- **직접 결과:** 92/92 템플릿 선택, **45승/45단위, 필요 30승, p=2.84217×10⁻¹⁴, Δ중앙=99.014934, A=99.799942, F1=1, 건전성 92/92**. 원래 자리 고정 출력 기준선은 12.943391점이다.
- **해석:** 이 반례는 입력의 위치/모습을 실제로 사용한다. 따라서 입력 교환 Δ가 입력 무시 생성기를 구별한다는 합의나 부호 검정 계산을 반박하지 않는다. 이미 학습 범위에 든 원형을 검색해 옮기는 방식만으로도 통과한다는 뜻이다. 새 작품 SFA 재구성 능력이나 애니 영상 일반화를 이 p값으로 주장하면 안 된다. 템플릿 선택 성공은 ‘실제 seq 모델이 이 방식으로 학습했다’는 증거도 아니다.
- **개선 방향:** 현재 공식 위치 시험은 좁은 의미 그대로 유지한다. 새 형상/새 작품의 생성 점수·시트와, 알려지지 않은 연속 이동/크기에 대한 별도 진단을 함께 본다. 시험을 사후 변경해 기존 공식 기회를 다시 만드는 대신 새로운 실험으로 선언한다.

### P-02 — 중간·운용 보강: 공식 횟수는 저장되지만 두 번·시점의 유일성은 코드가 강제하지 않는다

- **위치:** `tools/seq_train.py:831`–`833`, `846`–`849`, `1152`–`1156`.
- **직접 계산:** 기존 `tests/test_gpt_recheck.py`의 실제 소스 제어 흐름 장치에서 완료 상태를 같은 계획으로 세 번 넘기면 **`(공식=True, 1) → (True, 2) → (True, 3)`**이다. 실제 모델 재학습을 한 결과는 아니다. 저장 뒤 번호가 0으로 돌아가는 옛 결함은 정상 저장 경로에서 고쳐져 있다.
- **구분:** 응답 문서가 ‘두 기회는 운용 조건, 셋째부터 기준 밖’이라고 명시한 것은 읽었다. 따라서 횟수 저장 미구현으로 다시 지적하는 것이 아니다. 현재 도구의 ‘공식’ 표시는 그 운용 자격을 보장하지 못한다는 보강 의견이다. 결정론적인 같은 모델 재평가 자체가 새로운 독립 실험이 되는 것도 아니다.
- **개선 방향:** 최초 계획 끝·사전 지정 연장 끝의 식별값을 저장하고 재실행은 같은 결과의 재계산으로 처리한다. 셋째·같은 종료점 중복은 공식 통과 표시를 내지 않는다. 최초 판정 결과를 보고 난 뒤 연장 횟수/α를 늘리지 않는다.

### P-03 — 중간·최종 평가 준비: 반복 판단용과 최종 미사용 묶음의 분리를 실제 산출물로 고정해야 한다

- **위치:** 판정 기준 §3; `tools/kaggle_seq_worker.py:44`, `tools/pc_seq_run.py:101`, `tools/seq_train.py:624`–`644`.
- **근거/확인 방법:** 두 실행기는 같은 `sv`를 반복 검증·생성 채점에 준다. 현재 런처에는 판단용/최종용을 나누는 별도 manifest/경로가 연결돼 있지 않다. `data/holdout_exclude.json`의 7·8장 제외는 학습 그림 중복을 빼는 장치로, 미사용 최종 묶음 보존과는 별개다. `rg -n 'holdout|final' tools/kaggle_seq_worker.py tools/pc_seq_run.py`로 경로를 확인할 수 있다. 별도 외부 관리로 보존한 자료가 없다고 단정하지는 않는다.
- **개선 방향:** 문서에 합의한 작품 묶음 기준으로 판단용·최종용 목록과 해시를 먼저 저장하고, 두 장만 제외하라는 사용자 결정을 그대로 유지한다. 이미 여러 차례 본 시험 파일은 ‘과거부터 미사용’이라고 부르지 않는다. 최종용에 맞춰 실제 장 비율·커리큘럼을 반복 조정하지 않는다.

## 4. 측정으로 정할 과제·효율 개선

다음은 위 구현 결함과 다르며 이번 CPU 시험만으로 답을 확정하지 않았다. 각 과제의 결과를 보고 정책을 정한다.

| ID·심각도 | 파일:줄·근거 | 재현 가능한 측정/계산 | 개선 방향 |
|---|---|---|---|
| M-01·중간 | `seq_train.py:661`–`706`, `1117`–`1141`: 생성 선형 회귀 자체의 기존 모의 반례 시험은 통과한다. 실제 KV 캐시는 길이 증가에 따라 self attention·복사 비용이 커지며 채점·시트 비용은 `gen_img` 표본 밖이다. | 향후 사용자 GPU 지시 뒤 폭별 L=64/128/256/512/1024/2048 시간, `final_est_sec`, `final_sec`, 초과 초를 비교. 현재 생성 표본은 길이별로 충분한지 먼저 확인. CPU 모의 선형 적합을 GPU 외삽 검증으로 부르지 않는다. | 초기 예약값·상한 비용을 실측으로 정하고 비선형 잔차가 크면 구간 모형/상한 모형 사용. 마지막 전체 판정을 줄여 시간을 맞추지 않는다. 현재 deadline은 예상 조기 정지이며 단일 작업 도중 강제 마감 보장이 아니다. |
| M-02·중간 | `seq_train.py:91`–`124`, `97`–`106`, `571`–`580`: 고해상도를 전부 풀어 JPEG로 상주시킨다. multiprocessing은 `list(imap(...))` 결과를 모은다. | CPU 자료 읽기 시간·프로세스별 최대 RSS·부모 RSS·두 해상도 동시 보유량을 측정. 예: 평균 JPEG J바이트면 두 4만장 그림만 `80,000×J`; J=100KB면 약 8GB, 토큰·Python 객체·작업자 메모리는 별도. 이는 실제 평균 크기 실측값이 아니다. | 파일별 순차 수집으로 일시 중복을 줄이고 JPEG/토큰 mmap·디스크 캐시·제한된 LRU를 비교. `ru_maxrss(RUSAGE_SELF)`만으로 작업자 합산 최대 메모리를 측정했다고 하지 않는다. |
| M-03·중간 | `sfa_compose.py:296`–`316`, `seq_data.py:151`–`160`, `seq_train.py:1060`–`1068`: 실제 장 저장 비율과 학습 노출 비율은 다르다. 가려진 정답도 남는다. | 해상도×길이 분위×real/comp별 성공 장·토큰·시간, 고정 실제/조합 생성 F1을 함께 기록. 완전 가림·동색·압축 뒤 소실 오브젝트 비율은 오브젝트를 하나씩 제외해 렌더 기여도를 재는 표본 검사로 측정. | 17%가 충분하다고 미리 확정하지 않는다. 묶음이 많은 파일이 풀에서 차지하는 비중도 보고 파일 균형 샘플러와 비교. 관측 불가능한 정답은 생성 모델의 실패와 구분해 보고하되 사용자 채점 기준을 임의로 바꾸지 않는다. |
| M-04·중간 | `seq_bundle.py:48`–`105`, `112`–`157`: 질문 16·참조 48·상위 3·MAX_OBJ=400 후보 탐색이다. 19/20은 알려진 변형 20파일의 결과다. | 회전/크기·반전·발췌·비율 변화별 정답 쌍, 음성 쌍의 누락/오탐을 별도로 측정. 큰 장이 많은 파일의 미측정 수를 남긴다. `frame_sim`은 두 XML을 같은 hwr로 채점하므로 실제 화면 비율이 다른 사본의 정규화도 확인한다. | 독립성 증명 대신 후보 검사로 표현. 미확정 묶음을 합치면 항상 보수적이라는 주장을 되살리지 않는다. 그 결과를 본 뒤 통과가 쉬운 묶음 방식을 고르지 않는다. |
| E-01·제안 | `kaggle_seq_worker.py:84`–`87`, `149`–`155`: 판정 자료를 CPU 자료 커널에 미리 만드는 최근 수정은 코드상 연결돼 있다. | `sj` 판·평가 해시·자료 코드 해시가 같은 정상 재사용과 불일치 거부를 로컬 mock으로 검사. | CPU 자료 재생성을 반복하기 전에 내용 영향이 없는 코드 변경과 실제 자료 변경을 구분하되, 해시 검사를 무작정 끄지 않는다. I-06의 공식 자격 확인도 공통 사용한다. |
| E-02·제안 | `seq_train.py:149`–`153`, `seq_train.py:1238`: 문서·실행 식별 비용. | 실패 시 사전학습 가중치 없이 시작했는지 cfg/run에 영구 기록하고, 시트는 비율별 높이가 다른 경우도 확인. `draw`는 각 행 높이가 달라 `np.vstack(rows)`가 실패할 수 있는 코드 경로다(이번 직접 실행 아님). | `pretrained` 실제 사용 여부·전체 코드 SHA·자료/판정 목록 해시·시작 체크포인트 식별값을 짧은 메타데이터로 남긴다. 큰 로그/원본을 반복 전송하지 않는다. 혼합 비율 시트는 셀 크기를 고정한다. |

`Yielder.tick()`의 heavy 대기는 마감 중간 검사가 없어 게임이 끝날 때까지 머물 수 있다(`vec_train.py:239`–`246`, `seq_train.py:958`). PC에서 전체 시간 제한이 필요한 실행이면 deadline을 Yielder에도 전달하는 것이 좋다. 실제 장시간 게임을 켜서 검증한 것은 아니다. 기존 문서가 남긴 ‘단일 작업 중 초과 가능’의 구체적 경로다.

## 5. 시험의 빈틈과 사용자 결정 대조

| 현재 확인 | 빠진 검사/다음 조치 |
|---|---|
| 실패 시계 순수 함수, OOM 예외, 정상 CPU 업데이트는 시험한다. | **I-01:** 실제 scaler가 step을 생략하는 경우와 비유한 기울기 주입. loss 유한성만 검사하는 시험으로는 부족하다. |
| 서로 다른 면 색의 순서·원 T 구간·원 방향 반례가 있다. | **I-02·03:** 두 오브젝트의 스타일은 같지만 각 오브젝트의 선과 면은 서로 다른 색인 경우의 내부 합성, 글로우/넓은 면의 범위. 정답 자기 채점 100%는 잘못된 동치 판정을 검증하지 않는다. |
| 공식 함수의 640/축소 옵션·횟수 정상 저장을 AST로 검사한다. | **I-06·08, P-02:** 잘못된 자료를 실제 로더에 전달, 저장 반환 False, 동일 종료점 재실행. AST 장치는 연결된 전체 파일 저장·로딩과 다르다. |
| CPU 작은 통합 도구는 19항목을 검사한다. | `실패 시간은 학습 진행 밖` 항목은 `fail_min` 키 존재만 검사한다(`seq_flow_small.py:104`). overflow/실패를 강제로 일으킨 통합 시험이 추가로 필요하다. |
| `real_crop` 원래 순서·숨김·원 면 반전을 검사한다. | **I-09:** `place`의 레이어 순서를 별도로 검사. 실제 자료 발생 0인 경계 반례도 회귀 시험으로 가치가 있다. |
| 전체 Python 시험이 성공한다. | **I-04·05:** PC quick은 step 증가를 검사하지 않으며 배치 의존성 설치도 기존 환경 시험에 가려져 있다. |
| 추세 생성 상한은 네 방향 최대 길이 기준, 공식은 모델 최대 길이. | 방향별 상한 누출은 현재 고쳐졌다. I-07처럼 표시·전후 비교에서 공식/추세를 다시 섞지 않아야 한다. |

사용자 결정의 코드 반영을 별도로 대조했다.

- **반영 확인:** 1080→720→480→360 기본 단계·앞 단계 30% 선택, 단계별 쉬운 것부터, 연장 때 단계/최고 분위 유지, 그림 비율 전달, 정답과 함께 굵기 변환, 이전 인코더 이어 쓰기, 흰 바탕 페인트 합성, 두 시험 장만 제외, 동점 ±0.5, 동점/OOM을 고정 N에서 빼지 않음, 공식 640·전체 계획 끝 조건, 공식/진단 점수 분리, GPU push의 `--gpu-ok` 방어.
- **반영됐지만 끝까지 보장되지 않음:** 성공 학습만 진행(I-01), 만점의 영상 동등성(I-02·03·10), 전체 고정 평가 목록(I-06), 공식 상태 재개(I-08), 추세/공식 표시(I-07).
- **미측정 또는 향후 단계:** 앱 열기·편집 확인, 실제 GPU 수치/최대 예산 내 운영, 새 형상 일반화, 장 사이 ID 추적. 현재는 한 장→한 장 1판이므로 장 사이 추적 미구현 자체를 현재 버그로 세지 않았다. 24/24·트위닝 없음 결정은 유지해야 한다.

수정 우선순위는 **I-01, I-02·03, I-06·08 → PC 경로 I-04·05 → 추세 표시 → 나머지 경계/측정**을 권한다. 이 보고서는 GPU 실행 지시나 기준 변경 승인이 아니다.

## 부록 A. 인공 채점·조합 반례

저장소 루트에서 아래를 `review_visual_repro.py`로 임시 저장해 실행한다. 새 원본 자료·가중치·GPU가 필요 없다. 화소 차이의 정의는 RGB 채널 최대 절댓값 차이>24, 640×360이다. blur는 `seq_check.tolerant_diff`(σ=1.5)다.

```python
import copy, random, sys
import xml.etree.ElementTree as E
import numpy as np
sys.path[:0] = ['tools', 'tests']
import sfa_render as R, sfa_tokens as K, sfa_objscore as OS
import sfa_compose as C, seq_check as SC
from test_sfa_objscore import frame, BLACK, RED
R.PARAMS.update(pad=0., thick_mul=640/1920)
sq = E.Element('Sequence', HeightWidthRatio='.5625', BackgroundColor='-1')
def report(name, p, a):
    x, y = R.render_frame(sq,p,640,360), R.render_frame(sq,a,640,360)
    s = OS.score(p,a)
    print(name, {k:s[k] for k in ('perfect','order','fill_f1','link_f1')},
          int((np.abs(x.astype(int)-y.astype(int)).max(-1)>24).sum()),
          SC.tolerant_diff(x,y))
base = [('2',[(20,50),(50,50)],BLACK,0,[]),
        ('2',[(40,50),(70,50)],BLACK,1,[])]
a = frame(base, fills=[(RED,[0]),(RED,[1])])
p = frame([(t,xy,c,1-o,l) for t,xy,c,o,l in base],
          fills=[(RED,[0]),(RED,[1])])
report('same_fill_order',p,a)
base = [('1',[(20,50),(80,50)],BLACK,0,[(0,10)]),
        ('1',[(50,20),(50,80)],RED,1,[(0,0)])]
a = frame(base,glow={1}); p = copy.deepcopy(a)
for ap in p.iter('AP'):
    for ac in list(ap): ap.remove(ac)
report('remove_ac',p,a)
base = [('1',[(20,45),(80,45)],BLACK,0,[]),
        ('1',[(20,55),(80,55)],RED,1,[])]
a = frame(base,glow={0,1}); p = copy.deepcopy(a)
for f in (a,p):
    for i,o in enumerate(f.findall('AO')):
        o.attrib.update(GlowRadius='30',GlowThickness='200',GlowAlpha='200',
                        GlowColor=str(0xFF0000 if i==0 else 0x0000FF))
for o in p.findall('AO'): o.set('DrawOrder',str(1-int(o.get('DrawOrder'))))
report('glow_order',p,a)
src = E.Element('Frame',ID='1',Position='0',BackgroundColor='-1')
for lid in ('1','0'): E.SubElement(src,'LayerDef',ID=lid,Visible='true')
for i,(lid,col) in enumerate((('0',BLACK),('1',RED))):
    ao = E.SubElement(src,'AO',ID=str(i+1),TypeId='1',LayerId=lid,
                      Color=str(col),DrawOrder=str(i),ThicknessScale=str(C.snap_th(4)))
    for j,x in enumerate((20,80)):
        E.SubElement(ao,'AP',ID=str(10*i+j),X=str(x),Y='50')
f = E.SubElement(src,'FR',Color='0')
for i in (1,2): E.SubElement(f,'FS',Kind='1',ObjId=str(i))
u = C.units_of(src,.5625)[0]; dst = E.Element('Frame',BackgroundColor='-1'); layers=[]
C.place(u,dst,.5625,random.Random(0),C.Ids(),layers,keep='exact')
for i,ld in enumerate(layers): dst.insert(i,ld)
print('unit_order', [a.get('Color') for _,a in K.order_objects(sq,src)],
      [a.get('Color') for _,a in K.order_objects(sq,dst)])
report('unit_layer_order',dst,src)
```

## 부록 B. 업데이트·PC·공식 제어·저장 반례

### B-1. 실제 CPU GradScaler의 step 생략

```python
import torch
p=torch.nn.Parameter(torch.tensor(1.))
opt=torch.optim.SGD([p],lr=.1); sc=torch.amp.GradScaler('cpu')
loss=p.square(); sc.scale(loss).backward(); p.grad.fill_(float('inf'))
sc.unscale_(opt); norm=torch.nn.utils.clip_grad_norm_([p],1.)
s0=sc.get_scale(); sc.step(opt); sc.update()
print(loss.item(), p.item(), norm.item(), s0, sc.get_scale())
# 1.0 1.0 inf 65536.0 32768.0
# seq_train.py:1055 뒤는 이 생략을 검사하지 않고 성공으로 기록한다.
```

### B-2. 실제 학습기에서 PC quick의 0걸음 확인

```python
import sys,tempfile,json,io,contextlib
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as E
import numpy as np, torch
sys.path.insert(0,'tools')
import seq_train as ST, sfa_tokens as K
sq=E.Element('Sequence',HeightWidthRatio='.5625',BackgroundColor='-1')
fr=E.SubElement(sq,'Frame',Position='0'); E.SubElement(fr,'LayerDef',ID='0',Visible='true')
ao=E.SubElement(fr,'AO',ID='1',TypeId='1',LayerId='0',Color='-16777216',DrawOrder='0')
for i,x in enumerate((20,80)): E.SubElement(ao,'AP',ID=str(i+10),X=str(x),Y='50')
t=K.encode(sq,fr)[0]; real_net=ST.Net
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp)/'data'; d.mkdir(); out=Path(tmp)/'out'
    np.savez_compressed(d/'toy.npz',img=np.full((1,36,64,3),255,np.uint8),
        tok=np.array(t,np.int16),fld=np.array(K.fields(t),np.int8),
        off=np.array([0,len(t)]),pos=np.array([0]),
        meta=json.dumps(dict(file='toy',W=64,hwr=.5625)))
    for minutes in (4,1):
        cli=['seq_train','train',str(d),str(d),str(out),'--minutes',str(minutes),
             '--in-w','64','--maxlen','64','--d','32','--layers','1','--heads','2',
             '--backbone','resnet18','--val-n','1','--gen-n','1']
        if minutes==4: cli+=['--plan-minutes','60']
        def small(*a,**kw): return real_net(*a,**dict(kw,pretrained=False))
        with patch.object(ST,'Net',small),patch.object(ST.os,'cpu_count',lambda:2), \
             patch.object(sys,'argv',cli),contextlib.redirect_stdout(io.StringIO()):
            ST.main()
        r=json.loads((out/'log.jsonl').read_text().splitlines()[-1])
        print(minutes,r['step'],r['train_min'],r['stop'],r['final_est_sec'])
# 4 0 0.0 deadline 1200 / 1 0 0.0 deadline 1200
```

### B-3. 의존성 부재를 주입한 import

```python
import sys,importlib.abc
class MissingScipy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname=='scipy' or fullname.startswith('scipy.'):
            raise ModuleNotFoundError("No module named 'scipy'")
sys.meta_path.insert(0,MissingScipy()); sys.path.insert(0,'tools')
import seq_train  # ModuleNotFoundError
```

### B-4. 표시·공식 재실행

```python
import sys
sys.path[:0]=['tools','tests']
import seq_trend as T
from test_gpt_recheck import _controller
r=dict(minutes=1,step=1,judge_N=3,judge_win=3,judge_need=3,
       judge_passed_all=True,judge_health_passed=True,
       judge_official=False,judge_reduced=True,judge_w=1920)
print(T.table([r]))  # 비공식인데 '3/3(3) 통과 @1920'
run=_controller(); s=dict(stage=0,done_min=600,train_min=600,plan_min=600)
for _ in range(3):
    r=run(s); s=r['saved']
    print(r['rec']['judge_official'],r['rec']['judge_official_n'])
# True 1 / True 2 / True 3 (모델·채점·저장은 기존 AST 시험의 대체물)
```

### B-5. 실제 저장 제어 함수에 실패 반환 주입

```python
import sys,ast,time,random,types,torch
sys.path.insert(0,'tools')
tree=ast.parse(open('tools/seq_train.py',encoding='utf-8').read())
tr=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='train')
n=next(n for n in tr.body if isinstance(n,ast.FunctionDef) and n.name=='save_ckpt')
st={'official_n':1}; rate={}; empty=types.SimpleNamespace(state_dict=lambda:{})
env=dict(time=time,st=st,done0=0,active_min=lambda:3.,random=random,torch=torch,
         dev='cpu',VT=types.SimpleNamespace(save=lambda *x:False),net=empty,
         opt=empty,scaler=empty,cfg={},ck='unused',rate=rate)
exec(compile(ast.Module(body=[n],type_ignores=[]),'<actual-save>','exec'),env)
print(env['save_ckpt'](),st,rate)  # 실패인데 None, done_min=3, save 횟수=1
```

## 부록 C. 실제 평가 자료를 쓰는 로컬 재현

원본 SFA는 기존 저장소에서 읽기만 한다. 생성한 정답 npz·그림은 비공개 임시 디렉터리에 두며 커밋하지 않는다. GPU/Kaggle 없이 준비한다.

```sh
python tools/seq_judge.py build /tmp/gpt-review-judge --stage-w ''
```

### C-1. 축소/다른 평가 자료의 공식 자격 누락

```python
import sys,tempfile,json,pathlib,numpy as np
sys.path.insert(0,'tools')
import seq_judge as J, seq_train as ST
with np.load('/tmp/gpt-review-judge/judge.npz') as z:
    d={k:z[k] for k in z.files}
n=6; nd=4; m=json.loads(str(d['meta']))
m['entries']=m['entries'][:n]; m['manifest_sha']='wrong-list'
d.update(img=d['img'][:n*nd],tok=d['tok'][:int(d['off'][n*nd])],
         off=d['off'][:n*nd+1],tok0=d['tok0'][:int(d['off0'][n])],
         off0=d['off0'][:n+1],meta=json.dumps(m))
with tempfile.TemporaryDirectory() as td:
    np.savez_compressed(pathlib.Path(td)/'judge.npz',**d)
    js=J.JudgeSet(td,640)
    o,_=J.evaluate(js,lambda i,d:(js.tok[i][d],True,0.),dirs=range(2))
    print(len(js),js.meta['manifest_sha'],o['judge']['N'],o['judge']['passed_all'],
          ST.official_judgment(True,600,600,False,640,640))
# 6 wrong-list 6 True True
```

### C-2. 외운 SFA의 변환 템플릿 검색기

```python
import sys,copy,json,xml.etree.ElementTree as E
import numpy as np,cv2
sys.path.insert(0,'tools')
import seq_judge as J,sfa_tokens as K,sfa_render as R
js=J.JudgeSet('/tmp/gpt-review-judge')
R.PARAMS.update(pad=0.,thick_mul=640/1920)
gallery=[]; answers=[]; hrs=[]
for i,e in enumerate(js.ents):
    seq=E.Element('Sequence',HeightWidthRatio=str(e['hwr']),BackgroundColor='-1')
    fr=K.decode(js.tok0[i].tolist())  # 원래 자리 정답만 외움
    h=max(2,int(round(640*e['hwr']/2))*2)
    for trans in J.DIRS:
        moved=J.transform(copy.deepcopy(fr),trans)
        pix=R.render_frame(seq,moved,640,h)
        gallery.append(cv2.resize(pix,(64,36),interpolation=cv2.INTER_AREA).astype(np.float32))
        answers.append(K.encode(seq,moved)[0]); hrs.append(e['hwr'])
gallery=np.stack(gallery); hrs=np.array(hrs)
def retrieve(i,d):
    # 실제 입력과 그 비율만 사용. 방향 번호나 옮긴 정답 토큰을 답으로 조회하지 않는다.
    im=cv2.resize(js.image(i,d),(64,36),interpolation=cv2.INTER_AREA).astype(np.float32)
    dist=((gallery-im)**2).mean((1,2,3))
    dist[np.abs(hrs-js.ents[i]['hwr'])>1e-6]=float('inf')
    return answers[int(dist.argmin())],True,0.
o,_=J.evaluate(js,retrieve,dirs=range(2),memo=J.memo_baseline(js,J.OFFICIAL))
print({k:o[k] for k in ('A','f1','health','memo')})
print(o['judge'])
# N=45, win=45, need=30, passed_all=True; A≈99.799942, f1=1
```

이 스크립트는 고정 판정 목록에 한정한 반례다. 새 작품 정확도·연속 변환 정확도를 측정하지 않으며 실전 모델의 성능 수치로 사용하면 안 된다.
