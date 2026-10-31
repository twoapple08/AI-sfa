# 이펙트 화풍 LoRA 학습 — PC방(RTX 4060 8GB) 실행 안내 (2026-10-25)

나카무라(와 보충 작가) 이펙트를 **그리는 방식**을 그림 모델에 가르친다. 사용자 결정(2026-10-25): 그림체 LoRA처럼 장면을 쪼개 태그를 달고(GPT 태깅 781클립), 원본 장면을 쓰며 인물·배경·카메라도 태그로 구분한다. 사용자 그림체 LoRA(`LoCon_ILv1_gwangsa`, 인물 그리기용)와는 **합치지 않고 따로 두며**, 생성할 때 필요한 것만 얹는다.

## 설정과 근거
| 항목 | 값 | 이유 |
|---|---|---|
| 기본 모델 | Illustrious-XL v1.0 (공개, 6.9GB) | 사용자 그림체 LoRA와 같은 바탕이라 나중에 함께 얹어도 덜 깨짐 |
| 방식 | LyCORIS LoCon, dim 32 / alpha 8, conv 16 / 4 | 사용자 그림체 LoRA에서 성공한 설정(466장 16바퀴)을 출발점으로 |
| 학습 범위 | 그림 부분(UNet)만, 학습률 4e-4, AdamW8bit, cosine | 8GB에 맞추려고 텍스트 인코더는 고정하고 출력을 미리 계산 |
| 자료 | 대표 장 777장 + 인물 뺀 판 255장 = 1,032장 + 캡션(태그 → 영어, `tools/lora_captions.py`) | 신호 낱말: 나카무라 `nkmr_fx`, riooo `riooo_fx`, optical-core `opticore_fx`, yukina `yukina_fx` |
| 해상도 | 1024 기준 버킷(640–1536) | 16:9 그림을 자르지 않고 학습 |
| 길이 | 8바퀴(약 8,260단계), 2바퀴마다 저장 | 4060에서 단계당 1.5–2초로 보면 3.5–4.5시간(추정) |

캡션 예: `nkmr_fx, anime screencap, embers, lightning, streaks, particles, white core orange rim, no outline, sharp tips, sustained, shaking, flying, anime character, city, wide shot, from above`

## 준비물 (Drive `AI-sfa/02_분석자료/LoRA_클립/학습실행/`)
- `pc_lora_train.bat` — 설치·받기·학습 한 번에
- `pc_lora_prepare.bat` — 준비만(설치·기본 모델·자료 풀기, 학습은 안 함)
- `dataset.toml` — 학습 자료 설정
- `lora_train_data.zip` — 그림 1,032장 + 캡션(67MB, 인물 뺀 판 포함)

## 순서
1. `H:\fx\train` 폴더를 만들고 위 파일 4개를 넣는다.
2. (인물 자르기가 아직 돌고 있으면) `pc_lora_prepare.bat`만 먼저 더블클릭 — 학습 프로그램·파이썬(약 4GB)과 기본 모델(6.9GB)을 H에 받아 둔다. GPU는 쓰지 않는다.
3. 인물 자르기가 끝나고 Claude가 '인물 뺀 판'을 넣은 새 `lora_train_data.zip`을 올리면 그것으로 바꾸고 `H:\fx\train\data` 폴더를 지운다(새 자료로 다시 풀게).
4. `pc_lora_train.bat` 더블클릭 → 학습 시작. 진행 막대에 남은 시간이 나온다.
5. 끝나면 `H:\fx\train\out`의 `nkmr_fx_ilxl-000002.safetensors` … `nkmr_fx_ilxl.safetensors`를 Drive `AI-sfa/05_모델/이펙트LoRA/`에 올린다. Claude가 바퀴별로 그림을 뽑아 비교해 가장 나은 것을 고른다.

- C 드라이브는 쓰지 않게 사용자 폴더·AppData·캐시를 모두 H로 돌린다(인물 자르기 때 pagefile 문제 경험). 크롬 등은 닫아 둔다.
- 오류가 나면 창이 멈춘다. 그 화면을 찍어 보낸다.

## 확인하지 못한 것
- 이 bat은 서버에서 윈도로 실행해 보지 못했다. 버전 조합(torch 2.4.1 cu124, sd-scripts v0.9.1, bitsandbytes 0.44.0 윈도판, lycoris-lora 3.1.1)은 각 배포처에서 존재만 확인했다.
- 8GB에서 1024 해상도 SDXL LoCon이 메모리에 들어가는지는 실행해 봐야 안다. 모자라면 해상도를 896으로 낮춘다.

## 갱신(2026-10-25)
- 인물 뺀 판: PC방 1단계 결과(person_raw)로 대표 장만 서버에서 구멍 메우기·2px 넓히기(`person_mid`) → 인물 자리를 검게 칠한 그림 + 캡션 `no humans, black area`. 흑백·반전·임팩트 프레임은 획·덩어리를 사람으로 잡는 일이 많아(c0219) 만들지 않음. 연기 덩어리를 사람으로 잡은 경우(c0594)는 일부 남아 있음.
- 학습 bat: numpy 1.26.4 고정, 토크나이저 curl 선다운로드 + 오프라인 학습(PC방 네트워크 인증서를 파이썬이 거부).
