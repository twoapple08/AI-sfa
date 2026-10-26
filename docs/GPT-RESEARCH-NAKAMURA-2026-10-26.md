# GPT 조사 결과 요약 + Claude 대조 (2026-10-26)

프롬프트: docs/GPT-PROMPT-NAKAMURA-RESEARCH-2026-10-26.md. GPT 답(사용자가 채팅에 붙여 넣음)의 요점을 정리한 것이다(원문 전체 아님).
표시: [GPT] = GPT가 출처와 함께 보고, [대조] = Claude가 웹 검색으로 존재·핵심 사실을 다시 확인, [정정] = 우리 기록과 다름.
GPT는 '최종 = 휴대폰 단독'을 전제로 답했다. 같은 날 사용자가 **B안(휴대폰은 화면, 생성은 GPU 서버)**으로 임시 결정했으므로 그 기준으로 다시 읽는다.

## 1. 공개 모델·데이터
- 나카무라(유타폰) 전용 LoRA·데이터셋: 검증 가능한 것 없음 [GPT, Claude 검색과 일치]. → 우리 클립 781개가 핵심 자산.
- 관련 공개물 [GPT]: Impact Frames LoRA(PixAI, SD 계열·학습 출처 불명), HunyuanVideo AnimeShots LoRA(외형 위주), sakugabooru2025(HF, 영상 15.5만), Sakuga-42M(신청제).
- 영상 LoRA 실제 사례 [GPT]: Wan2.2 I2V A14B 액션 LoRA(4090D 48GB, 5.5일), Wan2.1 14B 신카이 스타일, CogVideoX 5B Arcane, LTX-2.3 ReStyle IC-LoRA, Wan2.2 폭발 LoRA(실사풍). **Kaggle T4로 애니 이펙트 영상 LoRA를 학습한 공개 기록은 없음.** CogVideoX 2B FP16 LoRA 16GB 공식 표(4080 측정), 구형 LTX 2B 학습 최소 5GB(조건부).

## 2. 나카무라 작화 [GPT, 일본어 인터뷰·작화 위키·출판사 안내 인용]
- quick & slow(모았다가 급격히 방출), 무게.
- 장 걸이: 컷 분석상 대부분 1·2코마, 고정 규칙 없음 → 우리 실측(폭발 1장 57%·2장 31%)과 모순 없음.
- 실사 자연현상의 예상 밖 움직임 + 과장, 실루엣 중시, 형태가 사라질 정도의 스미어.
- 본인 소책자 『中村豊の白黒エフェクトの描き方』(연필 흑백 이펙트), 원화집 vol.2(타임시트·러프·인터뷰 수록) — 입수 가능 여부 미확인.
- 카메라: 콘티에 없던 카메라 이동·PAN 떨림을 직접 더함 → 이펙트 변형과 화면 전체 이동을 분리해 학습해야 한다는 제안.
- 회색 연기 편향을 "원작 스타일"로 해석하지 말 것(우리 3차 자료 대조 결과와 일치: 학습 자료의 explosion 그림은 대부분 회색 아님).

## 3. 장 사이 일관성 방법 [GPT 비교표 요약]
| 방법 | 우리 SDXL LoCon | T4 | 큰 형태 변화 |
|---|---|---|---|
| 독립 img2img(움직임 시험 1) | 그대로 | 가능 | 깜빡임 위험 큼 |
| + 고정 스타일 참조(IP-Adapter) + 이전 장 + 구조 제어 | 그대로(로더 확인) | 저해상도 가능 | 외형 고정에 유용 |
| AnimateDiff-SDXL / Hotshot-XL | 그대로(병합) | 8–16장 조건부 | 미검증 |
| 광류 워핑 + 재그리기, FRESCO/EbSynth | 일부 | 가능 | 새 불꽃·파열에 약함 |
| ToonCrafter(키 사이 생성) | 키프레임으로 간접 | 경량 구현 | 시점·경로가 임의로 바뀔 수 있음 |
| AniDoc(CVPR 2025, 선화 채색) | 간접 | 약 14GB | 블로킹이 선화 수준일 때 |
| ToonComposer(ICLR 2026, 드문 스케치 + 색 참조 → 사이 장·채색) | 간접 | 공식 약 57GB, 부적합 | 목표와 잘 맞는 접근 |
| 영상 모델(Wan VACE 1.3B 등) | 별도 영상 LoRA 필요 | 저해상도 시험 | 유망, 임팩트 희석 위험 |

## 4. 휴대폰 생성 현황 [GPT]
Core ML SDXL 768² 20스텝 iPhone 15 Pro Max 31초(2023 공식), Qualcomm SD1.5 512² 15초 미만, SnapGen(0.38B, 1.4초, 가중치 미공개), MobileWan(Wan2.2 5B 축소, Snapdragon 8 Gen 5 NPU, 연구용), CineMobile(피크 1.8GB 보고). → 24장 1초를 SDXL로 폰에서 만들면 단순 계산 약 12분 + 벡터 변환.

## 5. 벡터 직접 생성 [GPT]
OmniLottie(CVPR 2026, 4B, 텍스트·이미지·영상 → Lottie 벡터 애니, 추론 약 15GB), OmniSVG 1.1, DeepSVG(41MB 체크포인트), StrokeNUWA, SketchRNN, AniClipart/FlexiClip/LiveSVG(기존 벡터의 움직임), diffvg(미분 가능 렌더러), VTracer. SVG/Lottie → SFA는 3차→2차 근사(cu2qu)·변환·곡선 수 제한 변환기가 필요.

## 6. GPT 추천 경로
- A. 기존 LoRA + 시간 참조 강화(빠른 검증): 독립 img2img vs 고정 참조+이전 장 vs Hotshot/AnimateDiff.
- B. 2D 벡터 템플릿 + 작은 시퀀스 AI(최종 목표 1순위): 효과 조건 → 24장 [경로 ID, 2차 곡선 제어점, 색, 레이어, 활성 여부]. 발생·분열·소멸 표현 필요.
- C. 영상 LoRA 교사 + 벡터 학생(연구용): Wan2.1 1.3B 또는 구형 LTX 2B, 320×192, 9/13장, rank 8–16, 100 step 속도 측정 후 결정.

## Claude 대조·판단
- [대조] OmniLottie: CVPR 2026 논문·4B 모델·MMLottie-2M 공개 확인([CVF](https://openaccess.thecvf.com/content/CVPR2026/html/Yang_OmniLottie_Generating_Vector_Animations_via_Parameterized_Lottie_Tokens_CVPR_2026_paper.html)). 비슷한 LottieGPT(CVPR 2026)도 있음.
- [대조] ToonComposer: ICLR 2026, Tencent ARC, 스케치 1장 + 색 참조 1장으로도 동작, DiT 영상 기반 모델([HF papers](https://huggingface.co/papers/2508.10881)). 기반이 Wan2.1 I2V 14B인지는 검색 결과로 확인 못 함.
- [대조] MobileWan: Qualcomm AI Research, **Wan2.2 TI2V-5B** 기반(어텐션 헤드 약 23% 가지치기), 연구용 라이선스, 최적화 디코더 미배포([HF](https://huggingface.co/Qualcomm-AI-Research/mobilewan)). GPT의 RAM 9.9GB 수치는 재확인 못 함.
- [정정] GPT가 1순위로 제안한 "SFA 왕복 검증"은 이미 완료: 우리 변환기 SFA가 앱에서 열리고 48장 8.6MB 내보내기 성공, 서버 렌더와 장마다 평균 픽셀차 1.5–4.1(docs/SFA-CURVE-OPTIMIZATION-2026-10-25.md).
- [정정] 클립 12장의 의미: 23.976fps 원본의 **연속 12장(약 0.5초)**, 걸이(홀드) 그대로 보존(tools/lora_clips.py).
- B안(서버) 기준 판단: 경로 A가 지금 가장 직접적이다(서버에서 SDXL을 그대로 돌림). 경로 B는 AGENTS.md의 원래 원칙("형태 사전 + 계수 변형", tools/fx_gen.py 시제품)과 같은 방향이라 장기 후보로 유지. 경로 C는 T4 학습 기록이 없어 100 step 시험으로 가능성만 먼저 잰다.

## 다음 순서(제안)
1. 움직임 시험 1(독립 img2img, 숫자/실루엣 블로킹 × 강도 3) — 노트북 준비 완료, 3차 LoRA 결과 뒤 실행.
2. 움직임 시험 2: 같은 블로킹에 고정 스타일 참조(IP-Adapter) + 이전 장 참고, 그리고 Hotshot-XL/AnimateDiff-SDXL 비교. 임팩트 장 전후는 참조 초기화.
3. 영상 모델 시험: Wan VACE 1.3B로 블로킹 → 스타일 vid2vid 추론만 먼저(T4 속도·품질), 되면 나카무라 클립 100개로 영상 LoRA 100 step 측정.
4. 장기: 경로 B(벡터 시퀀스 생성기), 또는 OmniLottie류 벡터 애니 모델 조사.
