# GPT 프롬프트 — 학습 조각 인물 태그 (2026-10-28)

목적: 나카무라 이펙트 LoRA가 프롬프트에 없는 인물을 그리는 문제(학습 캡션에 인물 낱말이 거의 없어 `nkmr_fx`가 인물을 흡수) → 사용자 결정 3번: 효과 없음 45조각 제거 + 인물이 보이는 조각 캡션에 인물 문장 추가.
GPT는 정해진 낱말로 태그만, Claude가 문장으로 바꿔 붙이고 묶음마다 표본 대조. 대상 437조각(`data/style_kb/person_scan_wanlora8_2026-10-28.json`에서 no_visible_effects 제외).

붙일 그림: `person_sheet_01.jpg`–`person_sheet_13.jpg`(scratch `pdet/gpt`, 조각마다 처음·가운데·끝 3장, 시트당 36조각). 1차 메시지에 01–07, 2차에 08–13.

## 복붙용 프롬프트(1차, 시트 01–07 첨부)

```
[학습 조각 인물 태그 — 시트 01–07 (다음 메시지에 08–13)]
목적: 이펙트 영상 학습 자료 캡션에 '화면에 보이는 인물'을 표시하려 한다. 이펙트는 판정하지 않는다.
시트 구성: 칸마다 위에 조각 번호(예: s0002_c0), 아래 3장 = 그 조각의 처음·가운데·끝 장.

조각마다 JSON 한 줄. 인물이 없어도 반드시 한 줄(빠짐 확인용). 형식:
{"clip":"s0002_c0","person":"large","kind":"face","frames":"all","unsure":false}

person (화면에서 가장 큰 인물 기준, 3장 중 가장 크게 보이는 장으로):
 none = 인물·생물·로봇 없음
 small = 화면 높이의 1/4 미만(멀리 작은 인물)
 medium = 그 사이
 large = 화면 높이의 절반 이상이거나 몸 일부 근접(얼굴·주먹 클로즈업)
kind (가장 큰 것 하나):
 face = 얼굴·머리 위주   fist_arm = 주먹·손·팔 위주   body = 상반신·전신 인물
 several = 비슷한 크기 인물 둘 이상   silhouette = 검은 실루엣·윤곽만
 creature = 사람 아닌 생물·괴물   robot = 로봇·기계 거인
 (person이 none이면 kind는 "none")
frames: all = 3장 모두 보임, some = 1–2장에만
unsure: 이펙트에 가려 인물인지 애매하면 true

규칙:
- 이펙트(연기·불·번개·빛)가 사람 모양처럼 보여도 실제 인물이 아니면 none.
- 무기·건물·탈것만 있으면 none.
- 출력은 코드 블록 하나에 JSONL만. 시트 순서대로. 설명 문장 없이.
- 마지막 줄 다음에 따로 한 줄: 처리 조각 수.
```

## 2차 메시지(시트 08–13 첨부)

```
[이어서 시트 08–13] 같은 규칙·형식으로 JSONL 코드 블록 하나 + 처리 조각 수.
```

## Claude 처리(결과 받은 뒤)
- 437줄·조각 번호 일치 검사, 시트마다 2–3조각 직접 대조.
- 문장 변환(예): large+face → "A character's face is visible in close-up." / small+body → "A small, distant character is visible." / frames=some → "briefly visible". creature·robot은 각각 "a creature"/"a giant robot".
- 효과 없음 45조각(`data/style_kb/wan_exclude_no_effect_2026-10-28.txt`) 제거 → 새 wanlora.zip.
