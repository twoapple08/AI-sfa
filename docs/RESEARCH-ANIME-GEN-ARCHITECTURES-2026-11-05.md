# 애니 전문 생성 AI들의 생성 구조 조사 (2026-11-05 Claude, 사용자 요청 "재계획 전에 개네 생성 구조부터")

상태: 웹 검색 1차 조사(논문 요약·리뷰 페이지 위주, 원문 PDF 전부 대조 전). 숫자는 출처 표기 그대로이며 2차 자료는 그렇게 적었다.

## 1. 네 갈래

|갈래|대표|출력|구조|바탕 모델|자료|
|---|---|---|---|---|---|
|애니 그림|Illustrious XL, NovelAI, Animagine|픽셀 그림 1장|확산(SDXL U-Net + 텍스트 인코더)|SDXL 1.0 미세조정|Danbooru 800만+ 장, 태그(인원·캐릭터·등급·일반·작가·점수·연도 순으로 재정렬), v2부터 문장 캡션 추가|
|애니 영상|AniSora(빌리빌리)|픽셀 영상(5초 360p를 8초에)|시공간 조건 확산(DiT), 시간·공간 마스크로 키프레임·부분 지시, RLHF판|Wan2.1(14B, 2차 자료)|애니 영상 100만~1000만(출처마다 다름), 평가 948클립|
|제작 공정 보조|ToonCrafter, AniDoc, ToonComposer|중간 장면·채색 영상|영상 확산 + 스케치 조건(ControlNet식, 장마다 선택)·참조 캐릭터 색|DynamiCrafter 등 실사 영상 모델 미세조정|애니 클립 + 선화 추출|
|**벡터 애니메이션**|**LottieGPT, OmniLottie(CVPR 2026)**, OmniSVG(NeurIPS 2025, 정지)|**편집 가능한 벡터(Lottie JSON / SVG)**|자기회귀 토큰 생성(다음 토큰 예측)|**Qwen2.5-VL(3B·7B) 미세조정**|LottieGPT: 애니메이션 66만 + 정지 벡터 1500만 / OmniLottie: MMLottie-2M / OmniSVG: MMSVG-2M|

## 2. 우리 목표(.sfa = 편집 가능한 벡터 애니)와 가장 가까운 것: LottieGPT

- **토큰 구조:** 계층(레이어 → 도형 → 속성)을 특수 토큰으로 표시. 도형은 원·채우기·그라데이션·선 같은 **의미 단위 하나**로(점 하나하나가 아님). 움직임은 **키프레임 시각 + 그 시각의 값 + 키 사이 감속 곡선(easing)** 만 저장.
- **길이:** 100장 이동이 키프레임 약 6개. 300장에서 최대 98% 압축(요약 자료 표기). **장마다 전부 적는 방식으로 바꾸면 유효 출력이 98.3% → 85.6%로 떨어짐**(논문 절제 실험).
- **학습 순서:** 1단계 정지 그림만(글→그림, 그림→벡터 반반) → 2단계 애니메이션(글 / 글+첫 장 / 글+키프레임 조건). 손실은 보통의 다음 토큰 교차 엔트로피.
- **바탕:** 처음부터 학습하지 않고 이미 글·그림을 이해하는 Qwen2.5-VL에 벡터 어휘를 더해 미세조정.
- 결과(7B): 글 입력 CLIP 0.933(OmniSVG 0.832), 유효 98.3%.

## 3. 공통 구조에서 보이는 것

1. **모두 거대한 사전학습 모델 위에서 시작**한다(SDXL, Wan2.1 14B, Qwen2.5-VL). 처음부터 학습한 것이 없다.
2. **자료가 수십만~수백만 단위**다. 애니 픽셀 쪽은 Danbooru·영상 플랫폼, 벡터 쪽은 이미 있는 Lottie/SVG 파일.
3. **"딸깍 한 번"으로 나오는 애니 영상 모델의 출력은 픽셀**이다. 편집 가능한 선·상자·레이어가 아니다. 공간 구성·분리를 해 주는 것이 아니라 그럴듯한 화소를 만든다.
4. **편집 가능한 벡터 애니메이션을 만드는 모델은 2026년에 나온 최신 연구**이고, 이들은 픽셀→벡터 변환을 거치지 않고 **벡터를 직접 생성**한다. 그리고 장마다 그리지 않고 **도형 + 키프레임 + 보간**으로 압축한다.
5. 제작 공정 보조 AI는 **사람이 그린 키프레임·스케치를 받아** 사이를 채우거나 색을 칠한다. 사람의 키 그림이 전제다.

## 4. 우리가 해 온 방식과의 차이(재계획 근거)

|항목|업계/연구|우리(지금까지)|
|---|---|---|
|바탕 모델|거대 사전학습 모델 미세조정|변환기를 처음부터 학습(T4)|
|출력 표현|도형 의미 단위 + 키프레임·보간|장마다 SFA 전체 토큰(점 좌표까지)|
|자료 규모|수십만~수백만|사용자 SFA 수백 개 + 직접 변환한 애니 몇 클립|
|경로|벡터 직접 생성|애니 픽셀 → SFA 변환(스틱맨·이펙트·배경 각각 연구)|
|사람 역할|키 그림·스케치(보조 AI) 또는 글 프롬프트|눈 판정·지적이 매 단계|

- 중간 표현 초안(docs/SFA-INTERMEDIATE-REPRESENTATION-DRAFT-2026-11-04.md)의 "압축된 중간 표현을 생성하고 .sfa는 컴파일러가 만든다"는 LottieGPT의 키프레임 방식과 같은 방향이다. 다만 변환기 학습은 장마다 전체 토큰 방식이라 이 방향과 어긋나 있다.
- (24,24) 규칙(사용자가 모든 장을 직접 그림)은 **최종 .sfa의 규칙**이고, 생성 모델 내부 표현이 키프레임이어도 컴파일러가 24장을 모두 펼쳐 쓰면 지킬 수 있다(추론, 사용자 확인 필요).

## 5. 재계획에서 정할 질문(사용자)

1. 경로: (가) 벡터 직접 생성(LottieGPT식 — 사전학습 VLM + SFA 어휘 + 키프레임 표현) / (나) 픽셀 영상 모델 + 픽셀→SFA 변환 / (다) 둘 다.
2. 자료: 공개 Lottie·SVG 자료(MMLottie-2M, MMSVG-2M 등, 공개 여부·이용 조건 확인 필요)를 SFA로 바꿔 1단계 학습 재료로 쓸지.
3. 첫 완성판 범위: 예) 글 → 짧은 스틱맨 동작 .sfa.
4. GPU: 3B급 미세조정(LoRA)이 Kaggle T4×2에서 되는지 확인 필요(추정, 미측정).

## 출처
- AniSora: https://arxiv.org/html/2412.10255v2 , https://github.com/bilibili/Index-anisora , https://comfyui-wiki.com/en/models/wan/anisora (2차)
- ToonCrafter: https://arxiv.org/html/2405.17933v1
- Illustrious: https://www.alphaxiv.org/overview/2409.19946 (2차)
- OmniSVG: https://omnisvg.github.io , https://neurips.cc/virtual/2025/poster/115696
- OmniLottie: https://openaccess.thecvf.com/content/CVPR2026/html/Yang_OmniLottie_Generating_Vector_Animations_via_Parameterized_Lottie_Tokens_CVPR_2026_paper.html , https://chatpaper.com/paper/242479 (2차)
- LottieGPT: https://openaccess.thecvf.com/content/CVPR2026/html/Chen_LottieGPT_Tokenizing_Vector_Animation_for_Autoregressive_Generation_CVPR_2026_paper.html , https://en.papernotes.org/CVPR2026/video_generation/lottiegpt_vector_animation_generation/ (2차 요약)
- 제작 공정: https://arxiv.org/html/2501.06250v4 (설문), https://arxiv.org/html/2508.10881v1 (ToonComposer), https://openaccess.thecvf.com/content/CVPR2025/html/Meng_AniDoc_Animation_Creation_Made_Easier_CVPR_2025_paper.html
