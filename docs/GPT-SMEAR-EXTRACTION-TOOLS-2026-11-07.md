# 원본 스미어 추출 도구 조사 — 2026-11-07

사용자가 v7에 “아 이게 아닌데”라고 판정했다. v7은 요청 형태 재현에 실패한 검토판이며 채택하지 않는다. 이어 “스미어 잡는 프로그램, 마이너한 것도”를 질문해 웹으로 공식 문서와 공개 코드를 조사했다. 추론 수준 High 권장. 설치/모델 실행/GPU 사용/새 생성은 하지 않았다.

## 확인한 후보

| 후보와 공식 출처 | 확인한 기능 | 우리 용도의 미확인 사항 |
|---|---|---|
| [X-AnyLabeling + SAM2](https://github.com/CVHub520/X-AnyLabeling/blob/main/examples/interactive_video_object_segmentation/sam2/README.md) | 긍정/부정 점·상자 지정, 영상 분할 추적, 중간 장 수정 | 스미어 의미 인식이나 미세 톱니 보존 보장 없음. 구형 안내는 JPG 변환이므로 정밀 경계 비교에 입력 손실 확인 필요 |
| [Cutie](https://github.com/hkchengrex/Cutie) | 초기 마스크 기반 영상 객체 분할, 상호작용 GUI | 1~2장 나타났다 사라지는 변형 잔상 추적은 우리 자료로 미검증 |
| [AniLines](https://github.com/zhenglinpan/AniLines-Anime-Lineart-Extractor) | 애니 이미지/영상 선 추출, basic/detail 모드, 로컬 Gradio·배치 처리 | 스미어 전용 아님. 가는 잔상을 지우거나 선을 새로 해석할 수 있음. detail 우수 주장은 개발자 설명이며 우리 측 검증 아님 |
| [MangaLineExtraction PyTorch](https://github.com/ljsabc/MangaLineExtraction_PyTorch) | 만화·카툰·일러스트 구조선 추출, 논문 공식 구현 | 가는 스미어 손실 가능성, 영상 시간 대응 없음 |
| [Anime2Sketch](https://github.com/Mukosame/Anime2Sketch) | 애니/일러스트 스케치 추출 | 스미어 의미와 편집 획을 복원하는 기능은 확인하지 못함 |
| [SmearSmith](https://theluckyduck666.itch.io/smearsmith) | 2D 키프레임·스프라이트·경로 기반 스미어 생성, stretched/multiples/drybrush/squash | 원본의 스미어를 추출하는 도구가 아님. 제작자 기능 설명만 확인, 앱 실사용/품질 미검증 |
| [OpenCV 색 범위 분리](https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html) + [윤곽](https://docs.opencv.org/4.x/d4/d73/tutorial_py_contours_begin.html) | HSV 색 범위 마스크, 경계 좌표 추출, CHAIN_APPROX_NONE으로 경계점 보존 | 개발 라이브러리로 별도 연결 필요. 색이 섞인 곳/가림/압축 경계 불확실. 원래 획 순서나 의미 복원은 아님 |

## 제안과 경계

이번 검색 범위에서 애니 스미어의 자동 발견→정확한 획 분리→SFA 편집선 변환을 끝까지 제공하는 전용 도구는 확인하지 못했다. 존재하지 않는다고 단정하지 않는다. 3D 생성기 SMEAR 등은 조사 중 노출됐으나 현행 2D 경로 제약에 따라 추천에서 제외했다.

현재 실패의 원인은 원본 경계를 재기 전에 삼각형·사다리꼴·교대 연장 공식을 먼저 적용한 점이다. 다음 후보 실험은 기존 원본 한 장의 작은 잔상 영역에서 **수동 영역 지정 + 색/경계 추출**과 **AniLines detail**을 비교하는 것이다. 이 추천은 조사에 근거한 제안이며 효과 검증/실행 승인으로 세지 않는다. 어려운 배경에서 영역 선택 보조가 필요하면 SAM2 GUI 후보를 검토한다. 짧게 나타나는 잔상은 추적부터 자동으로 믿지 말고 해당 장을 따로 확인한다.

분리된 마스크를 분석에 사용하는 것은 출력 SFA를 면으로 채우는 것과 다르다. 최종 표현은 사용자 지침인 지그재그 선묶음/들쭉날쭉한 가장자리/활성 불투명/보통 글로우 없음 조건을 유지한다. 마스크·윤곽·선 그림 어느 것도 원래 작가의 획 순서·각 선 중심·SFA 점 연결을 유일하게 알려주지는 않는다. 최종 점·연결 재구성에는 별도 판단이 필요하다.

추출 대상은 실제 애니메이터 원본이다. 사용자4.sfa는 지그재그 구조와 밀도 등의 표현 참고로만 사용한다. 효과 위치/타이밍 학습 정답으로 바꾸지 않는다. 원본/프레임/좌표는 공개하지 않는다.

저장 검증: 전체 426개 검사 OK·종료코드0(29.287초), git diff --check 통과. 이는 기존 저장소 회귀 검사이며 조사 후보의 실행 성능 검증이 아니다.

## 추가 조사 — 사용자 “더없어?”

영역 분리뿐 아니라 가는 구조 선택·과학영상 선 검출·연결 좌표 변환까지 확장했다. 아래는 기능 존재/공개 구현 확인이며 현재 스미어 사례의 성능 검증이 아니다.

| 추가 후보·공식 출처 | 기능·가져올 요소 | 제약 |
|---|---|---|
| [Deep Interactive Thin Object Selection](https://github.com/liewjunhao/thin-object-selection) | 상하좌우 극점으로 가늘고 길게 뻗는 구조를 분리하는 WACV2021 공식 코드 | 스미어 전용 아님. Python3.7/PyTorch1.7.1/CUDA10.1 시험 환경으로 오래된 의존성 조정 필요 |
| [Fiji/ImageJ Ridge Detection](https://imagej.net/plugins/ridge-detection) | 밝은/어두운 선 검출, 폭 추정, 교차점과 선 결과표 | 구 플러그인 유지보수 중단, 공식 페이지가 ImageJ Ops 대안 안내. 폭/임계값 민감·겹침 해석 제한 |
| [Skeleton Tracing](https://github.com/LingDong-/skeleton-tracing) | 이진 영상의 중심선을 점 배열/꺾은선으로 변환, Python/C++/JS 등 구현 | 원본 영역 분리가 먼저 필요. 면이 뭉친 모양의 중심선은 작가의 지그재그 획과 다를 수 있음 |
| [AutoTrace](https://github.com/autotrace/autotrace/blob/master/README.md) | 외곽/중심선 추적과 SVG 출력 | 스미어 의미 인식 없음. 선 끊김/잡음/후처리 영향 확인 필요 |
| [PolyVectorization](https://github.com/bmpix/PolyVectorization) | 선 그림 벡터화 연구 구현 | 전경 분리가 명암 임계값에 의존. 기본 Douglas-Peucker·Laplacian smoothing이 끝의 요철을 바꿀 수 있음 |
| [PolyVector Flow](https://github.com/ivanpuhachov/line-drawing-vectorization-polyvector-flow) | Keypoint-Driven Line Drawing Vectorization via PolyVector Flow 연구 코드 | 연구 구현 후보로만 확인, 현행 스미어/환경 재현 미검증 |
| [ilastik Pixel Classification](https://www.ilastik.org/documentation/pixelclassification/pixelclassification) | 사용자 칠한 예시와 픽셀/경계/질감 특징으로 Random Forest 분류, 확률지도·불확실지도·배치 처리 | 실제 소규모 분류기 학습을 포함. 우리 스미어 검증/실행 없음 |
| [ISAT-SAM](https://isat-sam.readthedocs.io/en/latest/) | 점/상자 영역분리, 수동 편집·다시 칠하기, 영상 주석, SAM-HQ 등 선택 | 기존 SAM GUI와 같은 계열. 모델 변경만으로 미세 톱니 보존 보장 안 됨 |
| [GIMP Scissors Select](https://docs.gimp.org/3.0/en/gimp-tool-iscissors.html) | 사용자가 찍은 점 사이에서 대비 높은 경계를 따라 영역 선택 | 수동 보조. 공식 문서도 경계 선택이 거칠 수 있다고 설명하므로 정밀 정답 자동 생성으로 사용하지 않음 |

확장 후 추천은 작업 단계에 따라 구분한다. 실제 가장자리 모양을 재는 단계는 색/명암 경계와 수동 수정, 이미 분리된 선을 편집 좌표로 옮기는 단계는 Skeleton Tracing/AutoTrace, 얇은 구조가 일반 분리기에서 사라지는 경우는 Thin Object Selection 검토다. Fiji는 획 폭/길이 분석 후보다. 추가 도구 모두 설치/추론/학습을 실행하지 않았다. 이 조사는 앞선 AniLines 후보를 대체하는 성능 판정이 아니다.

추가 조사 저장 검증: 전체426개 OK·종료코드0(28.940초), git diff --check 통과. 후보 실행 검증과 구분한다.
