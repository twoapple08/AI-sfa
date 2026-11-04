# AI-sfa 현행 인수인계 — 2026-11-04

사용자는 이 세션 전체·최신 일반화 개선 자료·신규 참여자 안내·Claude 전달 프롬프트를 준비하도록 요청했다. 실제 Claude 실행/작업 이관 완료를 뜻하지 않는다. 한국어로 답한다. 구현·시험·문서·커밋·푸시 허용은 유지하며 GPU/새 학습/임의 Kaggle 재실행은 별도 허락이다.

- **브랜치:** claude/new-session-gknz4t만. main 읽기/쓰기 금지. 저장 전 지정 브랜치 fetch/다른 변경 보존.
- **읽기:** AGENTS.md 전체 → 이 문서 → docs/HANDOFF-PROMPT.md → docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md → .claude/skills/stickman-extraction/START-HERE.md.
- **이번 세션 전체:** docs/SESSION-COMPLETE-HANDOFF-2026-11-04.md, 세부 변경/SHA는 docs/GPT-TAKEOVER-LOG-2026-11-03.md.
- **전체 이전 HANDOFF:** docs/history/HANDOFF-BEFORE-ONBOARDING-2026-11-04.md. 과거 작성시점의 최신/승인/작업 대기를 현재판으로 오인하지 않는다.

## 현재 우선순위

1. **최신 사용자 제보 수정 SFA의 눈·앱 확인 대기.** docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md. 최신 SFA [1ypI8kpPl-B_D_PjCC9MybVVpoitORGGp](https://drive.google.com/file/d/1ypI8kpPl-B_D_PjCC9MybVVpoitORGGp/view), 정지 비교 [상체/구겨짐](https://drive.google.com/file/d/1qWoDEGD6KT7Dc90qhAQVJAyzr01WE_n-/view) / [폭/앞뒤/누락팔](https://drive.google.com/file/d/1F-OwsBDeTnz0nlFFhcITX1l9sqINMmzT/view). 영상 제작 생략/SFA 중심 선호 유지.
2. **Kaggle A/B version2는 ERROR(2026-11-04 Claude 확인).** 부모 그림8장은 생성됐지만 token-v1 분기가 50업데이트 전 fp16 배율 넘침을 치명 오류로 처리해 중단. 비교 결과/업데이트/comparable 없음. `seq_refine.py`의 넘침 처리(같은 묶음 재계산·업데이트 수 동일 유지)를 수정·시험했다. **재실행은 사용자 승인 대기**, GPU 잔여시간 미조회. 진단 출력 Drive `AI-sfa/02_분석자료/seq/refine_ab_v2_error_2026-11-04/`. 상세 docs/GPT-SEQ-OBJECTIVE-REFINEMENT-2026-11-03.md 마지막 절.
3. **(11-04 Claude)** 5겹침 전부와 가속 후보 일부를 원본 대조, **869장 파랑 왼발목 공중 복제 오류를 수정**한 새 SFA [1Ba4WVy8NzRHIfjqxh4BsMLDQN6boIAeJ](https://drive.google.com/file/d/1Ba4WVy8NzRHIfjqxh4BsMLDQN6boIAeJ/view)(XML 7c6f311b…, 재현 1Kn2utrinBXfYGoHJpFCt2nw1RDKCE53O). 가속 후보24개는 모두 실제 빠른 동작으로 판독(수정0). 미확정: 1572/1574 빨강 팔(모호), **876–877 파랑 근경 다리/몸 출력 없음**(사용자 판정 필요). 상세 docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md 마지막 절. 이전 문구: 최신 수정판의5겹침/24수치 후보 중 미확정 부분을 실제 원본과 대조한다. 실제 교차·빠른 동작도 포함하므로 자동삭제/평활 금지. 새 제보가 있으면 원본/재생 장번호부터 맞춘다.
4. 새 영상 일반화는 보정 안 한 입력에 공통 처리만 적용한 첫 결과를 고정해 검증한다. 지금 개발자료/보존판단 재현을 일반화 성공으로 세지 않는다.

## 최신 기준과 바로 할 일

- 원본432–1871/재생1–1440/24fps 기준60초. **원본=재생+431**. 예전10초1032시작 클립은+1031로 다르다.
- 최신 수정: 재생99/169/320/516의 상체 가짜 하체·부분구도·착지 골반,868/969의 앞뒤,951의 표시폭/한줄기면,1144=원본1575의 중복 앞팔. 문자 그대로 원본1144의 파랑 양팔은 유지.
- 팔737–784는 지역 팔끝이 아니라 병·파편 오검출에 끌린 몸통/머리가 원인. 채택8키로48장 보간,목 한장최대346.93→16.73px,팔꿈치/손목변경0. 팔길이 추가 재투영은 미채택.
- 951주변은 한 팔다리 두 마디를 한12곡선 경계/FR로 연결,공유폭/접선 일치,얇은판의1.5→축소끝1.0 표시게인. 96M/97M 객체영역 분리로 장간형식 충돌 해소. 표시판단이지 실제거리 측정 아님.
- 최종 파일 1440장/25,669 AO/53,778 AP/48,236 AC/2,165 FR. 전체순서·면·망·머리·접촉 검사0,직전 구현304시험OK(exit0). 최신 인계 도구 추가 검증은 GPT 로그의 마지막 절 참조.
- 최신 구현8cad3d73441877720ad4f0b865e855eeb9e60d17,인계 직전HEAD6a851dda70fa039e46a01bbf79108d74845f01cf. SFA SHA9f0f0ce00bbcfcfe76c99969bacf4f0adf7228d51f8eeb052cb2f6bd5aa823d5. 재현 XML SHA f2141adffe4d085b74660e849a853f415a65f98e8a4e1f86ba8f91430e98cc85.
- **바로 할 일:** 사용자에게 위 최신 SFA/시트를 다시 연결하고951의 경계/굵기·1144앞팔·99/320의 실제앱/눈판정을 이어받는다. 과거10초 긍정판정을 새1분 전장 승인으로 확대하지 않는다.

## 데이터·스킬과 인계 준비

- **인계 전달물:** docs/HANDOFF-DELIVERY-2026-11-04.md. 문서/스킬/실행입력 휴대 묶음과Claude프롬프트를Drive에보존,휴대묶음코드만으로도최종XML일치확인. 인계구현3ec48fe77da6ad389ff430563d3a1d313644b5d8.

- 스킬 .claude/skills/stickman-extraction/에 현재규칙/프로젝트전체/세션전체/실데이터 manifest/24개사례/복원도구를 모았다. 실제파일은 Git 제외 private-data/에 두고 Drive 보존한다. 원본/전체좌표/SFA/프레임/가중치/앱녹화/키를 Git에 넣지 않는다.
- 3개자료집9+7+8=24항목,같은한영상/중첩구간의 개발자료다. held_out=false/training_ready=false. 일반화 개선/회귀용이며 자동학습정답/새영상 일반화 성공 아님.
- latest/replay.zip은11고정입력/229코드프로필지문. 보존 중간뼈대→최종 XML 재현 검증. 새원본에서 수동판정 자동생성한 성공 아님. 복원도구는 import/지문검사/입력추출만 하며 학습/코드실행 안 함.
- [Drive 신규자 인계 폴더](https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK). 휴대 묶음/파일목록과 기존3개자료집 링크를 제공한다. 구버전 재현은 해당 코드에서만,지문검사 해제 금지.

## 현재 유효한 사용자 결정·미확인

- 사람만 추출,나머지 사물/연출은 변환기. 2D/직선몸통/기본11편집망/장마다새점/객체연속/Flags3하나/틀밖허용/(24,24).
- 머리 A안·흰Kind1·투명11번 연결. **손가락/발가락/발길이0**,근경단순연속면유지. 상세외곽/3·5손가락/발바닥 시험은 미채택.
- 전신누락≠부위없음. 색지지/고점수≠의미정답. 실제접촉만 보완하고 근접회피를 붙이지 않는다. 근경지역폭/몸전체표시척도 구분,50px fallback 금지.
- 사용자 확인: 과거10초 A안 접합/숙임/앱편집 정상,근경면 모양 긍정,405다리/축소팔 개선 긍정. 최신1분 전장·새면의 앱편집·새영상 일반화·모바일1.1 실제폰은 별도 미확인.
- 모바일1.1(11) APK [1wfJrOYh08UG9w1qdnR65lGFT_8R5tPHS](https://drive.google.com/file/d/1wfJrOYh08UG9w1qdnR65lGFT_8R5tPHS/view). 기존1.0과서명다름/최근FPS캐시초기화. 서명키는 인계묶음에없음. docs/SFA-VIEWER-1.1-2026-11-03.md 참조.
- Kaggle 본2회차78709는 위치통과/미완료34/92로전체미통과. 승인 A/B는같은부모/각500update/각최대20분. v1글꼴실패→승인수정v2실행. 추가30h는다른계정추후연결 약속이며 현재자원/잔여시간 미확인.
- **재현 주의(11-04 Claude):** latest/replay.zip의229지문은 `tools/seq_refine.py` 등 공개 도구 전체를 포함한다. 이후 도구 커밋이 있으면 현재 HEAD에서는 지문이 달라지므로 `git worktree add <새폴더> 8cad3d7`(또는 df7e297)에서 재현한다. 해시 검사를 끄지 않는다. 이 환경에서 df7e297 코드로 XML f2141adf… 일치/11결정/exit0 재확인.
- 커밋 전 루트 전체 unittest의OK/exit0을따로확인,시험파이프와커밋연결금지. 보호판정JSON/작가학습범위재해석금지. HANDOFF/로그/SHA를갱신한다.
