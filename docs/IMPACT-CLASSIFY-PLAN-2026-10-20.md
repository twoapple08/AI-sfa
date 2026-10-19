# 임팩트 프레임 전수 분류 계획 (2026-10-20, 세팅만·미실행)

사용자 결정(2026-10-19~20)을 모은 실행 계획이다. **원본 형식 분류(docs/SOURCE-FORMAT-2026-10-20.md)를 먼저 끝낸 뒤 시작한다.** 모델 훈련은 하지 않는다(공개 모델 추론·예시 비교만).

## 1. 대상과 제외

- 대상: yutaka_nakamura·optical-core·riooo·yukina_kosaka 영상 중 **디지털 시대·완성본**. 형식 분류 결과로 정한다.
- 제외:
  - 기법 자료(쿠츠나 라이트닝·이타노 서커스), nian41, 반려 3명
  - 이미지 게시물
  - **셀 시대 전부**. 사용자 결정 "그 시절은 너무 뿌얘서 지금 취향과 맞지 않음". 연도표 기준 yutaka 61개이고, 형식 분류로 확정한다.
- 원화(러프)·혼합 영상을 넣을지는 형식 분류 뒤 다시 정한다. Claude 추천은 완성본만이다.
- 에반게리온은 판정만 하고 '학습 제외'로 표시한다.
- 원본은 기존 위치에 그대로 둔다.

## 2. 이전 결과의 처리

- 2026-10-19 재검사 291건 판정과 Drive `05_임팩트 프레임 재검사`는 **없던 것으로 한다.**
  - 폴더는 시작할 때 지운다(사용자 승인 2026-10-19).
  - 판정은 채점에도 쓰지 않는다.
- 저장소의 `impact_recheck_claude_2026-10-19.csv` 등은 기록으로만 남긴다.

## 3. 정답(채점·규칙 기준)

1. 원본 태그에 `impact_frames`가 있고 사용자 기준에 맞는 것. 영상 안 위치는 Claude가 프레임으로 확인하고 '태그+Claude 위치확인'으로 표시한다.
2. 사용자 A 판정 31건, 기존 확정 임팩트, 사용자 예시 5장(03_스타일지식베이스/참고_임팩트예시)
3. 범위 밖 Sakugabooru 채점 전용 100개(2000년 이후만). 분류·학습에는 쓰지 않고, 원본은 쓴 뒤 지운다.
   - 정답 후보 60: `impact_frames` 태그. 2000·2010·2020년대, 연필·실루엣·고대비·단색섬광을 고루 섞는다.
   - 아님 40: `impact_frames` 태그가 없고 연기·폭발·번개·빔·파편·집중선·스미어·배경 애니메이션 태그가 있는 것
   - 빼는 것: 우리 목록에 있는 것, nian41·반려·기법·에반게리온. 30초 이하 우선, 고른 목록은 저장소에 기록

## 4. Drive 결과 구조

```
05_임팩트 프레임 분류/
├ 임팩트 프레임 맞음/단색섬광/<애니메이터>/<자료>
├ 임팩트 프레임 맞음/실루엣이미지/<애니메이터>/<자료>   (연필·해칭·고대비·반전 포함)
├ 임팩트 프레임 애매/<애니메이터>/<자료>
└ 임팩트 프레임 아님/<애니메이터>/<자료>
```

- 자료 폴더에는 후보 프레임 PNG와 문맥 띠를 넣는다.
- '옆에실제'는 실제 임팩트 위치를 따로 '맞음' 항목으로 만든다.

## 5. 방법

1. 전체 프레임 자동 검사: `impact_scan2` 기준을 넓혀서 돌린다. 정답이 모두 후보에 들어오는지 먼저 확인한다.
2. 자동 결정:
   - 그림 없는 단색 → 맞음(단색섬광)
   - `same_style=1` → 아님. 정답으로 다시 검증한 뒤 쓴다.
3. 보조 지표(정답으로 효과를 잰 뒤 채택):
   - WD Tagger v3: monochrome·greyscale·silhouette·sketch·lineart·high_contrast·hatching_(texture)·graphite_(medium) / 아님 쪽: speed_lines·motion_lines
   - Anime Style Classifier v6(stylised_pencil)
   - DINOv2 예시 유사도
   - iris-pse-detection 밝기 변화
   - PySceneDetect 컷 경계
   - LBP·Gabor 질감
   - 흑백 두 색 정도(bilevel)
4. 비슷한 후보는 묶어서 대표만 판정한다. 띠는 앞 3·후보·뒤 3, 128×72로 줄인다.
5. 애매한 것은 Gemini 교차 판정을 쓸 수 있다(그때 Drive 공유 요청).

## 6. 쓰지 않는 것 (검증 결과)

| 방법 | 이유 |
|---|---|
| 효과음 | 사용자: 없음 |
| "4프레임 이상이면 제외" | Gemini 자체 제안. 출처 없음, 철회됨. 길이 상한은 정답 분포로 정한다 |
| X-CLIP 문맥 창 | AUC 0.54 |
| TransNetV2 | PyTorch 가중치를 직접 변환해야 해서 후순위 |

## 7. 외부 조사 결과(2026-10-20, GPT·Gemini, 링크 확인됨)

- WD Tagger v3 태그 존재 여부:
  - 있음: monochrome, greyscale, silhouette, sketch, lineart, high_contrast, spot_color, partially_colored, limited_palette, black/white_background, speed_lines, motion_lines, hatching_(texture), traditional_media, graphite_(medium), film_grain, retro_artstyle
  - 없음: inverted_colors, impact_frames, flash, pencil_(medium)
- 오자와 카즈노리『アニメーションのエフェクト作画テクニック』(겐코샤 2019) 용어 해설: "白コマ・黒コマ … 黒いコマを使った黒コマ（ショックコマとも呼ばれる）". 단색섬광을 맞음으로 두는 사용자 결정과 맞는다.
- Sakuga Blog(2017-06-09) 히로아카 23화 나카무라 유타카 장면: "41 in 31 seconds" 임팩트 프레임
- Sakugabooru `impact_frames` 태그 게시물은 약 13,721건이다(Gemini가 사이트 표시를 확인). Sakuga-42M 통계가 아니다.
