# 영상 기본 모델 후보 조사 — 2026-10-28 밤

질문(사용자): 지금 쓰는 Wan2.1 T2V 1.3B가 애니 학습에 부적합한 것 아닌가?
제약: 학습 GPU = Kaggle T4 16GB ×2(fp16, bf16 느림), 5060은 가끔 2시간 미만.

## 현재 근거로 가른 것(평가 1–3판)
- 인물 새어 나옴: base 0, LoRA만 → 자료·캡션 문제(모델 탓 아님). 2판 재학습으로 확인 중.
- 화풍: base도 평면 셀 경향 있음, LoRA로 로봇 장면이 3D CG → 셀 채색으로 뚜렷이 이동 → 애니를 못 배우는 모델은 아님.
- 번개 갈래가 뭉개짐: 1.3B 용량·512×288 해상도 한계일 가능성(미검증). 기본 16fps 출력도 24fps 리듬과 어긋남.

## 후보(Hugging Face 직접 확인 + 웹 조사, 10-28)
| 후보 | 공개 | 크기·형식 | T4 학습 | 비고 |
|---|---|---|---|---|
| Wan2.2-TI2V-5B (Wan-AI) | 공개, Apache-2.0 | 5B, 글→영상·그림→영상 겸용, 24fps·720p 기본 | 16GB LoRA 학습 사례 있음(커뮤니티, 확정 수치 없음) | **현실적 1순위** — 같은 musubi-tuner 계열, 24fps 기본 |
| Index-AniSora V3/V3.1/V3.2 (bilibili) | 공개, Apache-2.0 | Wan2.1-14B 기반(V3.2는 Wan2.2 A14B), 본체 약 66GB(fp32), 그림→영상 중심 | 사실상 불가(14B) | 애니 전용 1천만 클립 학습. 생성만은 fp8 양자화본(Kijai/WanVideo_comfy)으로 T4에서 느리게 가능할 수도 — 첫 장 그림이 필요 |
| Wan2.2 A14B / Wan2.1 14B | 공개 | 14B | 사실상 불가 | |
| Wan 2.7 이후 | 가중치 공개 여부 불확실(공식 저장소엔 2.2까지만 확인) | — | — | |
| LTX-2.x | 공개 | 약 22B(출처마다 다름) | 어려움 | 미세조정 생태계는 큼 |

## 제안
1. 2판 재학습 결과로 '자료 문제'를 먼저 분리.
2. 그다음 Kaggle에서 생성만 비교: Wan2.2-TI2V-5B base vs Wan2.1-1.3B base(+LoRA) — 평가 3판과 같은 프롬프트·씨앗·CPU 노이즈, 24fps. 5B의 애니 표현·번개 형태가 확실히 나으면 다음 학습부터 5B로(T4 메모리·속도 시험 먼저).
3. AniSora는 '그림 한 장 → 애니 움직임' 경로(예: 생성한 첫 장을 움직이기)로 따로 시험할 가치가 있음 — 14B라 학습 대상은 아님.

출처: huggingface.co/api/models?author=Wan-AI, huggingface.co/IndexTeam/Index-anisora, github.com/bilibili/Index-anisora, github.com/kohya-ss/musubi-tuner/discussions/455, howaiworks.ai/alibaba-wan-open-weights-stopped-at-2-2
