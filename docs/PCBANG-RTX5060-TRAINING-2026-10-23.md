# PC방(RTX 5060)에서 동작 모델 6차·7차 학습 (2026-10-23)

목적: 애니 자료가 동작을 좋게 하는지 판단한다. 5차(애니 비중 4배)는 이미 끝났으므로 여기서는 두 판만 돌린다.
- **6차**: 애니 없이 모캡만(`motion_data_mds6.zip`) — 애니 비중 0배
- **7차**: 5차와 같은 자료(`motion_data_mds5.zip`), 애니 비중 1배(`--style-rep 1`)

## RTX 5060에서 다른 점
- RTX 50 시리즈는 **CUDA 12.8용 torch(2.7 이상)**가 있어야 돌아간다. 집 PC(1050 Ti)용 `cu118`판이나 앞서 만든 `run_v5_v6.bat`(`cu121`판)을 쓰면 학습 시작 때 `no kernel image is available` 오류가 난다. 이 문서의 `run_v6_v7_rtx5060.bat`을 쓴다.
- GPU 메모리가 8GB라 배치 16은 넉넉하다.
- 예상 시간(추정): 받기·설치 15–25분, 6차·7차 각각 5–10분. 2시간 안에 충분히 끝난다.

## 순서
1. **Python 3.11 설치**(이미 있으면 버전만 확인: cmd에서 `python --version`)
   - python.org에서 Python 3.11 설치 파일을 받아 실행한다.
   - 첫 화면에서 **"Add python.exe to PATH"를 체크**하고 "Customize installation" → 다음 화면에서 "Install for all users"를 끄고 **설치 위치를 `D:\ph`**로 바꾼다(torch 등 설치 패키지도 여기에 들어간다).
   - 3.13은 쓰지 않는다(글 이해 모델 CLIP 설치가 실패한 적이 있다).
2. **파일 받기**: Drive `AI-sfa/07_도구/동작학습_1050ti/`에서 아래 7개를 **한 폴더**에 받는다. 브라우저 다운로드 폴더(C)에 받아도 된다 — bat이 실행될 때 6개 자료 파일을 `D:\mm`으로 옮긴다.

   | 파일 | 크기 |
   |---|---|
   | `run_v6_v7_rtx5060.bat` | 실행 파일 |
   | `momask_finetune.py` | 학습 스크립트 |
   | `momask_code.zip` | 1MB |
   | `momask_checkpoints.zip` | 188MB |
   | `ViT-B-32.pt` | 354MB |
   | `motion_data_mds6.zip` | 359MB |
   | `motion_data_mds5.zip` | 363MB |

   다른 파일(`motion_data_mds.zip`·`mds3`·`mds4`, `run_v5_v6.bat`, `결과` 폴더)은 받지 않는다.
3. **`run_v6_v7_rtx5060.bat` 더블클릭.** 작업 위치는 **`D:\mm`로 고정**이다(압축 풀기·임시 파일·pip 캐시·결과 모두 D). 설치 → GPU 확인 → 압축 풀기 → 6차 → 7차 → 결과 묶기를 자동으로 한다. D 드라이브가 없으면 바로 멈춘다.
   - [2/6]에서 `GPU True NVIDIA GeForce RTX 5060`과 `계산 확인 True`가 나오면 정상이다.
   - 학습 중에는 50단계마다 `단계 50 mask …/… res …/… 걸린초`가 나온다.
   - 오류가 나면 "오류로 멈췄습니다"에서 멈춘다. 그 화면을 찍어 보낸다.
4. "끝"이 나오면 **`D:\mm\results_v6_v7.zip`**을 Drive `동작학습_1050ti/결과/`에 올린다.
5. **정리**: Google 로그아웃, `D:\mm` 삭제(학습 자료는 원본 애니에서 나온 자료다). 설치한 Python을 남기지 않으려면 제어판에서 제거한다.

## 시간이 모자라면
- 6차가 끝난 뒤([5/6] 7차 시작) 창을 닫아도 6차 결과는 남는다. `D:\mm\momask-codes\checkpoints\t2m\` 안의 `…_ft_v6_gpu` 두 폴더만 올린다.
- 학습 도중에 끄면 마지막 '저장' 줄(250단계마다)까지의 결과가 남는다. 그 단계 수를 같이 알려 준다.

## 결과를 받은 뒤(Claude)
기본·5차(4배)·7차(1배)·6차(0배)를 `tools/bench_compare.py` + 관절 막대 그림(씨앗 1–3)으로 비교해, 애니 비중이 일어서기·착지·걷기·펀치에 주는 영향을 본다.
