# LoRA 클립 인물 자르기 — PC(RTX 4060) 실행 안내 (2026-10-25)

이펙트 화풍 LoRA 학습용 클립 781개에서 **사람 형체(인물·실루엣·사람 모양 로봇)만** 찾아 마스크를 만든다. 서버 CPU로는 몇 시간이지만 4060이면 1시간 안쪽으로 예상한다. 방식 = 글로 찾기(Grounding DINO) + SAM 2 오리기 + 걸러내기(반대 낱말 비교·섬광 빼기·작은/반짝 덩어리 버리기) + 애니 전용 모델로 인물 안 구멍 메우기(사용자 "잘 적용된 부분만 모아서", `--model mix`). 도구 비교 근거: Drive `02_분석자료/LoRA_클립/인물도구비교/`.

## 준비물 (Drive `AI-sfa/02_분석자료/LoRA_클립/PC실행/`)
- `lora_clips_781.zip` — 클립 781개(173MB)
- `lora_person_mask.py` — 실행 스크립트
- `isnetis.onnx` — 애니 캐릭터 전용 분할 모델(176MB)
- 이 안내서

## 한 번에 실행 (PC방 권장, 2026-10-25 사용자 요청)
1. `H:\fx\lora` 폴더를 만들고 Drive `PC실행/`의 파일 4개(`lora_clips_781.zip`, `lora_person_mask.py`, `isnetis.onnx`, `pc_person_mask.bat`)를 넣는다.
2. `pc_person_mask.bat`를 더블클릭한다. 파이썬·패키지를 모두 H 드라이브(`H:\fx\py`, `H:\fx\lora\env`)에 깔고(처음 한 번 약 3GB, 다음부터는 건너뜀) 클립을 풀어 실행한다. C 드라이브는 쓰지 않는다.
3. 끝나면 `H:\fx\lora\person` 폴더를 Drive에 올린다(아래 4번).
아래 1–3번은 bat 없이 손으로 할 때의 순서다.

## 1. 받기
`H:\fx\lora`를 만들고 zip·스크립트·`isnetis.onnx`를 넣는다. zip은 그 자리에 압축을 풀어 `H:\fx\lora\clips\c0001.mp4 …`가 되게 한다.

## 2. 설치 (이전에 만든 `H:\fx\env` 그대로 씀, 한 번만)
명령 프롬프트에서 한 줄씩:
```
set TMP=H:\fx\tmp
set TEMP=H:\fx\tmp
set HF_HOME=H:\fx\hf
H:\fx\env\Scripts\python.exe -m pip install --no-cache-dir "transformers==4.49.0" onnxruntime
```
(SAM 2·torch(cu124)·opencv는 이펙트 클릭 도구 때 이미 설치함.)

## 3. 실행
```
set HF_HOME=H:\fx\hf
H:\fx\env\Scripts\python.exe H:\fx\lora\lora_person_mask.py H:\fx\lora\clips H:\fx\lora\person --model mix --anime H:\fx\lora\isnetis.onnx --conf 0.3 --grow 2 --clean --sheet H:\fx\lora\person_check.jpg
```
- 처음 실행 때 모델 두 개(약 1.1GB)를 자동으로 받는다.
- 클립마다 `c0001 인물 면적 12.3%`처럼 한 줄씩 나온다. 중간에 멈춰도 다시 실행하면 처음부터 다시 하니 끝까지 두면 된다.
- 끝나면 `H:\fx\lora\person\` 폴더(npz 781개)와 확인 그림 `person_check.jpg`, `person_check_02.jpg` …(50클립씩 16장)이 생긴다.
- 처음 몇 클립이 `인물 면적` 줄을 찍는지 확인하고, 오류가 나면 화면을 찍어 보내 주세요.

## 4. 올리기
`H:\fx\lora\person\` 폴더 전체를 Drive `AI-sfa/02_분석자료/LoRA_클립/인물마스크/`에 올리고 알려 주세요. `person_check.jpg`는 크면 안 올려도 됩니다.

## 참고 (Claude용)
- 출력 npz: `mask[T,H,W/8]` packbits(인물=1), `shape`. 클립 960x540.
- 서버 시험(CPU): 10클립 약 30분. GPU에서는 `torch.cuda.is_available()`이면 두 모델 모두 cuda로 올린다.
