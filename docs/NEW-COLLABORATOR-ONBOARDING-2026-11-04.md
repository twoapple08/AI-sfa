# 처음 참여하는 사람을 위한 AI-sfa 인수인계

기준일 2026-11-04. 이 문서는 입구다. 작업 규칙 원문은 `AGENTS.md`, 현재 작업은 `HANDOFF.md`, 세션 경과는 `SESSION-COMPLETE-HANDOFF-2026-11-04.md`, 변경 근거는 `GPT-TAKEOVER-LOG-2026-11-03.md`가 맡는다. 과거 문서의 ‘최신/완료’는 작성 시점의 표현이며 아래 현재 상태를 덮지 않는다.

## 1. 무엇을 만드는가

최종 목표는 자연어·태그·스토리보드로 Stick Fighter에서 편집할 수 있는 `.sfa` 애니메이션을 만드는 창작 AI다. 기기 안에서 실행하는 목표가 있으나, 현재는 생성 서버와 휴대폰 화면을 나누는 임시 방향이다. Kaggle/Colab은 학습·실험용이며 상시 서비스 서버가 아니다.

현재 두 부품을 개발 중이다.

|부품|현재 역할|아직 완성하지 않은 것|
|---|---|---|
|사람 모션 추출|애니 영상의 RTMW 2D 관절 → 원본 그림 단위 키 → 피팅·보간 → 연결된 스틱맨 SFA|임의의 새 영상에서 구도·가림·부위 의미를 자동 판정하는 일반화|
|그림/SFA 변환기|입력 그림 → SFA 토큰. 사물·배경·이펙트·파편·스미어 그림 등을 편집 가능한 구성으로 옮기는 학습|모든 외형·종료·배치 품질의 합격, 긴 영상의 일관된 시간 추적|

후속 방향은 두 결과를 같은 시간·좌표·앞뒤 순서·접촉에 맞춰 합성하여 학습 자료를 만드는 것이다. 인물 뼈대만 좋아도 배경/이펙트가 깨지면 완성 자료가 아니다. 신체 자체가 스미어인 경우의 팔다리 복구는 사람 추출기의 대상이고, 스미어 그림의 외곽·색·연출은 변환기 대상이다. 현재 자료가 그대로 최종 학습 정답이 된다는 뜻은 아니다.

역사: `PROJECT-HISTORY-2026-10-31.md`, `history/PROJECT-HISTORY-2026-11-01-02.md`. 초기 README의 ‘학습/앱 분석 미구현’은 현재 사실이 아니어서 `history/README-BEFORE-ONBOARDING-2026-11-04.md`에 보존했다.

## 2. 처음 읽을 순서

1. 저장소 루트 `AGENTS.md` 전체. 학습 작가별 범위·보호 판정·권한·11-02/03/04 사용자 정정까지 읽는다.
2. 루트 `HANDOFF.md`의 현재 우선순위/바로 할 일/사용자 결정 대기.
3. `docs/HANDOFF-PROMPT.md`와 이 문서.
4. `.claude/skills/stickman-extraction/START-HERE.md`, `SKILL.md`.
5. `docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md`와 `docs/SESSION-COMPLETE-HANDOFF-2026-11-04.md`.
6. 10초 기준의 판단 배경은 `STICKMAN-OVERLAP-DEBATE-2026-11-03.md` 마지막 ‘5차 — 종결’, `STICKMAN-CLIP-1032-1271-2026-11-03.md`. 새 여캐는 `STICKMAN-PROTO4-A1500-1523-2026-11-03.md`의 비율/관절 확인 절차부터.

학습 작가별 범위를 이 요약에서 새로 정의하지 않는다. nian41 모션과 다른 작가의 이펙트·연출 범위를 섞거나 옷/얼굴/머리카락 그림체를 인체 움직임의 정답으로 바꾸지 않는다. `AGENTS.md`의 최신 명시 규칙이 기준이다.

## 3. 저장소와 비공개 자료

저장소는 `twoapple08/AI-sfa`, 브랜치는 **`claude/new-session-gknz4t` 하나**다. main은 읽지도 쓰지도 않는다. 새 환경은 `git clone --single-branch --branch claude/new-session-gknz4t https://github.com/twoapple08/AI-sfa.git`으로 시작한다. 인증 값은 출력하지 않는다. 저장 전 해당 브랜치만 fetch하고 다른 사람의 변경을 보존한다.

|위치|내용|
|---|---|
|`tools/`, `tests/`|공통 추출·표시·재현·검사·변환기·학습 도구와 회귀 시험|
|`profiles/`, `scenes/`|고정 뼈대/선택 표시 프로필, 소량 장면 설정. 큰 원좌표는 넣지 않음|
|`data/stickman_motion/generalization_cases/`|좌표 원본이 없는 개발 사례 메타 3종/24항목|
|`.claude/skills/stickman-extraction/`|Claude가 읽는 기술 입구·복원 도구·자료 색인·현행 결정|
|스킬의 `private-data/`|실제 비공개 자료. **Git 제외**. 휴대 묶음과 Drive에서 복원|
|Drive `AI-sfa/01_원본영상/`|원본 영상|
|Drive `AI-sfa/02_분석자료/`|RTMW 전체 관절, 원본 발췌, 분석/재현/개발 자료/SFA|
|Drive `AI-sfa/07_도구/SFA뷰어/`|모바일 SFA 뷰어 APK|

현재 환경 비공개 작업장은 `/workspace/ai-sfa-private/`다. 새 환경의 경로가 다르면 스킬 manifest를 기준으로 복원한다. 토큰/키/서명키/가중치는 인계 묶음에 넣지 않았다. `.gitignore`가 무시하는 자료도 `git add -f`로 넣지 않는다. 연결된 Drive 도구 또는 기존 정상 rclone 설정을 사용하고, 인증 복구를 이유로 비밀 값을 출력하지 않는다.

인계 폴더: https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK

## 4. 지금 이어갈 기준

**최신 SFA는 사용자 제보 수정판이며 최종 승인판은 아니다.** 원본 432–1871 / 재생 1–1440 / 24fps 기준 60초 / 1920×1080 출력이다. 원본 1152×720에서 y63..711을 사용했다. 재생장+431=원본장. 예전 1032 시작 240장 클립은 재생장+1031이므로 섞지 않는다.

- 최신 SFA: https://drive.google.com/file/d/1ypI8kpPl-B_D_PjCC9MybVVpoitORGGp/view
- 정지 비교 99/169/320/516: https://drive.google.com/file/d/1qWoDEGD6KT7Dc90qhAQVJAyzr01WE_n-/view
- 정지 비교 868/951/969/1144: https://drive.google.com/file/d/1F-OwsBDeTnz0nlFFhcITX1l9sqINMmzT/view
- 최신 필수 재현: https://drive.google.com/file/d/1xzyOVobHLMWbr-Vc7dZnQ3fcNkQ4vFli/view
- 실제 새 폴더 재현 증거: https://drive.google.com/file/d/14Rk0QGtCjbU6vcXX6PaCsLvRCD7_WX-E/view
- 최신 개발 자료: https://drive.google.com/file/d/1r8KY-8vESuofwe1QWS7ApKp9Efv1K7gg/view

구현 `8cad3d73441877720ad4f0b865e855eeb9e60d17`에 지문 고정. 인계 전 저장 HEAD는 `6a851dda70fa039e46a01bbf79108d74845f01cf`다. 인계 문서/복원 도구 커밋은 별도로 남긴다. SFA 바이트 SHA256 `9f0f0ce00bbcfcfe76c99969bacf4f0adf7228d51f8eeb052cb2f6bd5aa823d5`, XML SHA256 `f2141adffe4d085b74660e849a853f415a65f98e8a4e1f86ba8f91430e98cc85`다. ZIP 타임스탬프가 다를 수 있어 재생성의 핵심 동치 판정은 XML이다.

최신 판에는 11종 고정 입력/결정과 229개 도구·프로필 지문이 필요하다. **보존 중간 뼈대부터 수동/추론 입력을 포함해 재생성**한 범위에서 XML 일치를 확인했다. 새 원본에서 눈 판정을 다시 만들어 동일해진다는 검증이 아니다. 이전 dea13677/a8a0e3f 재현 묶음은 각각 그 버전에서만 재현하며 해시 검사를 끄지 않는다.

## 5. 현재 유효한 스틱맨 규칙

- 2D, 직선 몸통, 기본 11객체와 AC 편집망 유지. 점 ID는 장마다 새로, 객체 ID는 같은 대상을 장끼리 이어준다. 인물마다 Flags3 하나, 화면 밖 좌표 허용, 앱 설정 (24,24).
- 고정 뼈대는 연결 구조를 뜻한다. 투영 길이·비율·관절 위치는 자세/원근에 따라 달라도 된다. 원본 그림 하나=키 하나, 원본의 2/3컷 정지는 부드럽게 잇는다.
- 흰 머리는 FS Kind1 원 전체 채움. A안은 몸통/팔 유지·머리 최소 이동, 내부 투명 연결 11번 유지. 사용자의 앱 정상 확인은 이전 10초 A안 범위다.
- **손가락·발가락·발길이 부속 0**. 과거 실루엣/세 손가락/다섯 손가락/발바닥 막대는 미채택 이력이다. 근경은 단순 중심선의 연속 면을 유지한다. 몸통 곡선/인체 외곽 세부를 만드는 방향이 아니다.
- 몸 전체/상체 표시척도와 한 부위 극근경의 지역 폭을 구분한다. 화면 밖 가짜 머리로 극근경 거리 추정 금지. 측정 실패를 고정 50px 반지름으로 덮지 않는다.
- 같은 팔다리 두 마디는 선택 `joined_chains=True`에서 한 경계/한 채움으로 연결한다. 공유 폭의 실제 AP 끝점 순서와 경계 접선을 맞춘다. 기존 96M/새 97M 객체 영역을 섞지 않는다.
- 실제 접촉만 맞춘다. 아슬아슬한 회피/가림/추론 끝점에 접촉을 강제하지 않는다. 색 지지/높은 점수/구조 오류0은 부위 의미의 정답이 아니다.
- 단순 미검출로 사람/팔다리를 없애지 않는다. 전신 없음/부분 부위 존재/완전 가림/실제 퇴장을 구분한다. 숨은 점은 추론으로 저장한다.
- 최신 선호는 **미리보기 영상 생략, SFA와 필요한 정지 근거**다. 검토/원본 크기 판독까지 생략하라는 뜻은 아니다.

## 6. 복원과 최소 검증

Python 3.11+ 권장. 최소 재현은 NumPy/SciPy, 전체 CPU 시험/렌더는 스킬의 `references/ENVIRONMENT.md`를 참고한다. 기존 유효 캐시를 먼저 재사용하고 필요하지 않은 GPU·모델 다운로드·전체 재피팅을 하지 않는다.

```bash
# 저장소 루트에서, Drive에서 내려받은 파일들을 파일명과 무관하게 SHA로 맞춘다.
python .claude/skills/stickman-extraction/scripts/restore_data.py --import-path /내려받은_인계파일_폴더

# 지문 확인만: 필수 자료가 없거나 다르면 exit 2. 필요한 Drive ID가 결과에 나온다.
python .claude/skills/stickman-extraction/scripts/restore_data.py

# 실제 새 폴더 재생성. 기존 폴더는 덮지 않는다.
python tools/stickman_replay.py .claude/skills/stickman-extraction/private-data/latest/replay.zip --destination /비공개/새_재현폴더

# 코드 수정 후 커밋 전 필수. 성공과 종료코드를 확인한 다음 별도 커밋한다.
python -m unittest discover -s tests
```

`restore_data.py --extract-replay /새_입력폴더`는 입력만 푼다. `--expand-cache /새_캐시폴더`는 보존 피팅 캐시를 푼다. 재현/추출/학습을 자동 실행하지 않는다. 지문 불일치 시 원인을 확인해 지정 코드와 입력을 복구한다. 강제로 manifest를 새 hash로 바꿔 통과시키지 않는다.

복원 자료에는 47개 선택 NPZ·54개 피팅 NPZ, 얼굴 보조 관측/보고, 수동 판단, 이전/최신 출력, 원본 발췌와 미채택 시도가 포함된다. 파일별/중첩 ZIP 색인은 스킬 `data/archive_inventory.json`에 있다. 원본 전체 영상과 RTMW는 별도 Drive 파일이며 필수 재현에는 필요하지 않다.

현재 환경에 남아 있는 사용자 제보 스크린샷5개도 별도로 보존했다. 이전 첨부7개는 현환경에 원파일이 남아 있지 않아 보존현황에 부재를 표시했다. 그때의 문제/사용자 판정/처리와 Drive 결과 연결은 세션 전체 문서와 GPT 로그에 있다. 없는 원파일을 묶음에 포함했다고 설명하지 않는다.

## 7. 새 장면 작업 방법과 일반화 검증

장면 데이터를 공통 코드에 장 번호 예외로 박지 않는다. 기본 구조/공통 연산/장면 구도·가시성·접촉·키/표시층을 분리한다. 같은 증상이 여러 장이면 원관측 → 유효 축·뺀 점 → 출력 허브·팔다리 → 저장 XML을 측정해 공통 원인부터 찾는다. 컷·빠른 차기·실제 교차를 무조건 평활하지 않는다.

일반화 검증은 **보정하지 않은 새 영상에 공통 처리만 적용한 결과를 먼저 보존**해야 한다. 그 뒤 수동 수정한 자료는 개발로 옮기고 held-out 성공으로 세지 않는다. 현재 3종/24사례는 같은 알려진 영상에서 나온 중첩 사례다. `development_known_clip`, `held_out=false`, `training_ready=false`다. 24개 독립 영상/자동 학습정답/임의 영상 일반화 완료가 아니다.

근거 표시는 파일·코드 / CPU 계산 / 원본 눈 판독 / 추론 / 실제 앱·사용자 확인으로 나눈다. 구조 검사0, 서버 렌더, 실제 앱 열기/편집, 사용자 눈 승인, 새 영상 일반화는 서로 다른 단계다. 결과를 숫자로만 보고하지 말고 필요한 정지 그림을 먼저 보여 준다.

## 8. 변환기와 Kaggle 인수인계

출제는 `sfa_compose.py`가 실제 SFA의 연결/면 단위를 가져와 이동·크기·반전·굵기·겹침을 변형하고, 변형 SFA의 렌더/압축 그림을 입력·동일 SFA 토큰을 정답으로 만든다. `seq_data.py`가 미리 생성한 자료이며 매 업데이트 새 출제가 아니다. 실제/합성 비율은 코드 목표값과 실현 개수를 나눠 확인한다. 종료만 좋아지고 면/색/배경/배치가 깨지면 품질 개선이 아니다.

본 2회차(aisfa-seq-train 판7)는 900.009분/78709걸음으로 끝났다. 위치31/45는 통과했으나 미완료34/92로 전체 미통과다. 34개는 한도 직전 강제 EOS였고 CPU 진단에서 후반 반복·EOS 미선택도 확인했다. 부모 가중치/데이터/공식 합격선을 보존한다.

사용자 허락으로 별도 비공개 `twoapple08/aisfa-seq-refine-ab-v1`에 종료/첫 객체/외형 보조손실 A/B 비교를 시작했다. 기존/보정 각각500업데이트·순수 최대20분, 동일 부모78709·자료·순서·seed, 새 optimizer lr1e-5다. version1은 글꼴 경로 문제로 학습 전 실패. 승인받아 글꼴 fallback을 수정하고 version2를 실행했다. **마지막 실제 관측은 2026-11-04 12:13 KST RUNNING**이며 현재 완료/성공/업데이트 수는 미확인이다. 이번 인계 준비에서 새로 조회하지 않았다.

다음 담당은 상태/출력 조회부터 한다. 모니터링은 사용자가 Claude에 맡겼다. `GPT-SEQ-OBJECTIVE-REFINEMENT-2026-11-03.md`의 명령으로 `refinement_run.json`, `comparison/results.json`, `train.jsonl`, 고정 입력을 확인하고 같은 조건 그림을 먼저 비교한다. 임의 재실행·장기3회차·GPU 추가 실행은 하지 않는다. 추가30시간은 현재 계정 소진 후 다른 계정을 연결한다는 약속이며 아직 연결된 자원이 아니다. 현재 GPU 잔여 시간도 모른다.

```bash
kaggle kernels status twoapple08/aisfa-seq-refine-ab-v1
# 완료/실패가 확인되면 새 비공개 폴더에 출력만 받는다.
kaggle kernels output twoapple08/aisfa-seq-refine-ab-v1 -p /비공개/새_출력폴더
```

인증 값 출력 금지. 전체 자료 커널의 수천 파일을 무조건 pull하지 않는다. 작은 metadata/목록/필요 출력부터 확인한다. 비교가 완료·동일 조건인지 먼저 확인하고 실패를 성능 결과로 세지 않는다.

## 9. 뷰어·앱·바로 할 일

모바일 뷰어 v1.1(11): https://drive.google.com/file/d/1wfJrOYh08UG9w1qdnR65lGFT_8R5tPHS/view . Drive `07_도구/SFA뷰어/`. 이번 배포는 모바일만이다. Kind 누락을 허용하던 뷰어의 관대함을 고쳐 실제 앱 채움 오류를 드러내고 캐시/오류 표시를 수정했다. Android9개 시험·APK 서명/정렬 검사는 통과했지만 실제 휴대폰 검증과 다르다. 기존1.0과 서명이 달라 삭제 후 설치가 필요할 수 있고 최근 목록/FPS 캐시가 초기화된다. 서명키는 배포/일반화 자료에 포함하지 않는다. 새 환경에서 같은 서명 업데이트를 보장하지 않는다.

우선순위는 (1) 최신 수정 SFA/정지 비교의 사용자 눈·앱 확인, (2) Claude가 Kaggle 상태/실제 A/B 출력 확인, (3) 남은 5겹침/24수치 후보를 원본과 대조, (4) 새 영상 공통 처리만의 일반화 검증이다. 아직 1440장 전부의 원본 눈 판정과 실제 앱 검증을 완료하지 않았다. 새 제보는 재생/원본 번호를 먼저 대응한다. 중간 저장을 작업 완료로 보고하지 않는다.

커밋 전 전체 시험 성공/exit0을 별도로 확인하고 지정 브랜치를 갱신한다. `HANDOFF.md`와 GPT 로그에 코드/이유/근거/검증/한계/SHA를 기록한다. 새 담당이 시작할 때는 현재 상태를 짧게 설명한 뒤 미완 작업을 이어간다.
