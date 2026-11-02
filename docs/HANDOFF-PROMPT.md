# 인수인계 프롬프트 (2026-11-03 — 1단계 2회차 + 스틱맨 시제품 1 사용자 판정 대기)

https://github.com/twoapple08/AI-sfa 작업을 이어서 한다. **모든 답을 한국어로만 쓴다.**

**브랜치:** 작업은 `claude/new-session-gknz4t`에만 있다. main은 옛 단계라 읽지 않고, 아무것도 올리지 않는다. 시작하면 먼저 다음을 한다.
1. `git fetch origin claude/new-session-gknz4t`
2. `git checkout -B <시스템이 배정한 브랜치> origin/claude/new-session-gknz4t`
3. `git log --oneline -1`로 HEAD를 확인한다. 커밋할 때는 같은 HEAD를 배정 브랜치와 `claude/new-session-gknz4t` 둘 다에 푸시한다.

**읽기 순서:**
1. AGENTS.md
2. HANDOFF.md: 현재 우선순위, 바로 할 일, 결정 대기, 이번 세션 실수
3. docs/ANIME-TO-STICKMAN-DEBATE-2026-11-02.md: 맨 끝 '8차 — Claude 답'과 '사용자 판정·지시 기록'만 먼저 읽는다
4. GPT 8차 답: `docs/GPT-ANIME-TO-STICKMAN-ROUND8-2026-11-02.md`. GPT가 지정 브랜치에 저장했다. 없으면 사용자에게 묻는다.

필요할 때만 더 읽는다: docs/STICKMAN-LABEL-SPEC-2026-11-02.md, docs/history/PROJECT-HISTORY-2026-11-01-02.md, docs/STAGE2-GENERATOR-DESIGN-2026-11-02.md.

## 지금 위치
- **1단계(영상 → SFA 변환 AI):** Kaggle `aisfa-seq-train` 판 7(2회차, 이어하기)을 11-02 15:47 UTC에 시작했다. 예상 종료는 01:00–01:45 UTC다.
  - 끝나면 다음 순서로 한다.
    1. `python tools/kaggle_seq_remote.py pull 폴더`
    2. `save-ckpt 폴더`
    3. `python tools/seq_trend.py 폴더/log.jsonl`
    4. 1회차와 같은 조건의 판정끼리 비교해 보고한다. 판정 시트(입력 | AI SFA | 정답)도 보고, 숫자보다 그림을 먼저 보여 준다.
  - 3회차는 사용자 허락 뒤에 한다.
- **2단계(애니 인물 → 스틱맨):**
  - 진행 방식 전환은 확정이다(11-03 사용자·GPT 동의). 토론은 결정이 필요할 때만 하고, GPT는 결과물을 검토한다.
  - 시제품 1 → 2 → 2b → 3 경과는 HANDOFF '바로 할 일 2'에 있다. 시제품 3(B, 키포즈 보간)은 '부드러워졌다'는 판정을 받았다. 현행은 시제품 4(A 1500–1523, docs/STICKMAN-PROTO4-A1500-1523-2026-11-03.md)다. 성공 판정이 나면 기본 스틱맨 변환, 실루엣 깎기, 곡선 몸통의 세 작업을 한다. **사용자 판정을 기다린다.** 판정 전에는 새 설계 토론이나 추가 시제품을 만들지 않는다.
  - SFA 규칙: 점 ID는 장마다 새로, 오브젝트 ID는 장끼리 유지, (24, 24).
- **GPU:** 사용자 지시 없이 실행하지 않는다. 스틱맨 쪽 GPU 일은 Colab에서 한다(Claude가 노트북을 만들고 사용자가 실행).

## 새 컨테이너 준비
- 다음을 설치한다.
  - pip: `opencv-python-headless numpy scipy skia-python kaggle`
  - CPU torch·torchvision: `--index-url https://download.pytorch.org/whl/cpu`
  - apt: `rclone libegl1 libgl1`
- scratchpad 자료는 사라진다. Drive에서 다시 받는다.
  - 원본: `gdrive:AI-sfa/01_원본영상/nian41/x_self_posts/1913231262086463573.mp4`
  - RTMW: `gdrive:AI-sfa/02_분석자료/포즈_RTMW/nian41/1913231262086463573.jsonl.gz`
  - 해시는 HANDOFF.md에 있다.

## 사용자와 일하는 방식(핵심)
- 먼저 답하고, 계획(무엇·왜·얼마나)을 말한 뒤 작업한다.
- 근거 범위 안에서만 말한다. 측정·시각 판독·가설을 구분한다. 지난 세션에서 근거 없는 단정 때문에 정정 라운드가 여러 번 생겼다.
- 그림 판정은 원본 크기와 차이 지도로 한다. 작은 시트로 단정하지 않는다.
- GPT 답은 저장소 docs에 전문이 온다. 토론에 답할 때마다 **GPT 답장 프롬프트**를 `docs/GPT-PROMPT-*.md`로 저장하고 복사할 블록으로 준다(11-03 사용자). GPT는 GitHub·Drive를 직접 보므로 경로로 가리킨다. 새 GPT 세션용이면 그것만으로 시작할 수 있게 쓴다.
- 원본 영상·추출 프레임·가중치·앱 녹화는 저장소에 넣지 않는다(Drive만). 토큰·키를 출력하지 않는다.
- 애니메이터별 범위 규칙은 최신 기록으로 고정돼 있다. 다시 해석하지 않는다.
