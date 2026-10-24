# 이펙트 마스크 클릭 지정 — PC 설치·사용 안내 (2026-10-24)

이펙트 위를 몇 번 클릭하면 SAM 2(영상 분할 모델)가 그 이펙트만 오려서 구간 끝까지 따라갑니다. 결과 마스크로 Claude가 서버에서 SFA를 다시 만듭니다. 대상은 확인된 이펙트 후보 35구간(1,055장)입니다.

## 준비물 (Drive `AI-sfa/02_분석자료/이펙트_클릭마스크/`)
- `click_frames_35.zip` — 35구간 장면 사진(73MB)
- `fx_click_mask.py` — 클릭 프로그램
- 이 안내서

## 1. 설치 (처음 한 번, 30분 안팎)
1. **파이썬 3.11** 설치: python.org → Downloads → Python 3.11.x(Windows installer 64-bit). 설치 첫 화면에서 **"Add python.exe to PATH" 체크**.
2. **작업 폴더** `H:\fx`를 만들고 Drive의 `click_frames_35.zip`, `fx_click_mask.py`를 받아 넣습니다. zip은 그 자리에 압축을 풀어 `H:\fx\click_frames\001_239068_900\…`이 되게 합니다. **경로에 한글을 넣지 마세요**(사진 읽기가 실패할 수 있음).
3. **명령 프롬프트**(시작 → `cmd`)에서 한 줄씩:
   ```
   py -3.11 -m venv H:\fx\env
   H:\fx\env\Scripts\activate
   pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124
   pip install sam2 huggingface_hub opencv-python
   ```
   - `sam2` 설치가 빌드 오류로 실패하면 `set SAM2_BUILD_CUDA=0` 입력 후 마지막 줄을 다시 실행.
   - GPU 확인: `python -c "import torch; print(torch.cuda.is_available())"` → `True`가 나와야 합니다.

## 2. 실행
```
H:\fx\env\Scripts\activate
python H:\fx\fx_click_mask.py H:\fx\click_frames H:\fx\out
```
- 처음 실행할 때 모델(약 900MB)을 자동으로 받습니다.
- 구간이 하나씩 창에 뜹니다. 끝낸 구간은 다음에 실행해도 건너뜁니다(중간에 Q로 끝내도 됨).
- 특정 구간만: `--only 001,008`. 느리면 `--model small`.

## 3. 조작
| 키·마우스 | 동작 |
|---|---|
| **왼쪽 클릭** | 이펙트(이 부분을 잡아라) — 초록 점 |
| **오른쪽 클릭** | 아님(인물·바위·배경 — 빼라) — 빨간 점 |
| A / D | 앞 장 / 뒤 장 (이펙트가 가장 잘 보이는 장에서 클릭) |
| N | 새 물체 — 떨어진 다른 이펙트 덩어리(예: 불꽃 따로, 연기 따로) |
| Z | 마지막 클릭 취소 |
| R | 이 구간 처음부터 |
| **Enter** | 확정 → 구간 전체로 따라가기 → 결과가 두 바퀴 재생됨 → 아무 키: 저장, R: 다시 클릭 |
| S | 이 구간 건너뛰기(이펙트를 잡을 수 없을 때) |
| Q | 끝내기 |

**클릭 요령**
- 클릭하면 바로 색으로 덮인 결과가 보입니다. 이펙트 전체가 덮일 때까지 여러 군데(3–5번) 왼쪽 클릭.
- 인물·바위·배경이 같이 덮이면 그 위를 오른쪽 클릭.
- 불꽃이 여러 개로 흩어져 있거나 연기와 파편이 따로 있으면 N으로 물체를 나눠서 각각 클릭하는 편이 정확합니다.
- 이펙트가 중간에 처음 나타나는 구간은 D로 그 장까지 넘겨서 클릭하세요.
- 기준은 임팩트 때와 같습니다: 이펙트만, 인물·배경은 빼기.

## 4. 끝나면
`H:\fx\out` 폴더의 `*_click.npz`(와 건너뛴 구간의 `*_skip.txt`)를 Drive `AI-sfa/02_분석자료/이펙트_클릭마스크/결과/`에 올리고 알려 주세요. Claude가 이 마스크로 35개 SFA를 다시 만들어 비교 영상으로 보여 드립니다.

## 참고 (Claude용)
- 출력은 kaggle_fx_worker v3와 같은 키라 `effect_clip_sfa.py --mask <게시물>_<시작>_click.npz`로 바로 쓴다(frames = 원본 영상 장 번호).
- 서버 시험(2026-10-24): SAM 2.1 small, CPU, 008 210343 18장 — 점 입력·reset_state·앞뒤 propagate 정상(장당 약 4초). GPU 창 조작은 사용자 PC에서 처음 확인.
