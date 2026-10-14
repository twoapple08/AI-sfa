# AI-sfa

자연어로 지시한 동작을 Stick Fighter에서 편집할 수 있는 `.sfa` 애니메이션으로 만드는 프로젝트입니다.

현재는 **샘플 기반 파일 도구와 호환성 시험 단계**입니다. AI 모델 연결·자료 학습·앱과 동일한 트위닝은 아직 구현하지 않았습니다. APK는 아직 분석하지 않았습니다.

## 첫 버전에서 할 수 있는 일

- ZIP 안의 XML로 구성된 `.sfa` 읽기와 요약
- 프레임 수·좌표·레이어·연결 참조 검사
- 알 수 없는 XML 요소/속성을 유지하면서 다시 저장
- 기본 스틱맨의 48프레임 팔 흔들기 시험 파일 생성
- 설치 없이 브라우저에서 보는 HTML 미리보기

Python 표준 라이브러리만 사용합니다. API 키나 유료 API 호출이 필요하지 않습니다.

## Termux에서 시작

```bash
pkg update
pkg install python git
termux-setup-storage
git clone https://github.com/twoapple08/AI-sfa.git
cd AI-sfa
python sfa.py validate examples/wave_test.sfa
```

이미 저장소를 받았다면 해당 폴더에서 `git pull`로 업데이트합니다.

**먼저 앱 호환성을 시험하세요.** 휴대폰 브라우저에서 저장소의 `examples/wave_test.sfa`를 다운로드하거나, Termux에서 아래처럼 복사한 뒤 Stick Fighter의 가져오기 기능으로 열어 보세요.

```bash
cp examples/wave_test.sfa ~/storage/downloads/AI_sfa_wave_test.sfa
```

이 파일은 48개의 실제 프레임을 포함합니다. 원본 재생속도 24FPS로 설정하면 약 2초의 팔 흔들기가 목표입니다. 우선 트위닝도 24로 설정해 파일 자체를 확인하세요. **앱에서 직접 열기 검증은 아직 남아 있습니다.**

## 파일 분석과 저장

예시 입력 경로를 실제 다운로드 파일명으로 바꿔 주세요.

```bash
python sfa.py inspect ~/storage/downloads/01_base.sfa
python sfa.py validate ~/storage/downloads/01_base.sfa
python sfa.py roundtrip ~/storage/downloads/01_base.sfa ~/storage/downloads/roundtrip_test.sfa
python sfa.py wave ~/storage/downloads/01_base.sfa ~/storage/downloads/my_wave.sfa --frames 48
python sfa.py preview examples/wave_test.sfa ~/storage/downloads/wave_preview.html --playback-fps 24 --tween-fps 48
```

출력 파일이 이미 있거나 입력과 같으면 중단합니다. 다른 출력 이름을 사용하세요.
`wave`는 제공된 원형 그대로의 기본 스틱맨만 지원합니다. 임의의 커스텀 캐릭터에는 사용할 수 없습니다.

생성한 HTML은 파일 앱에서 브라우저로 열 수 있습니다. 또는 저장소에서 아래 명령으로 서버를 열고 휴대폰 브라우저로 `http://127.0.0.1:8000/examples/wave_preview.html`에 접속하세요. 종료는 Ctrl+C입니다.

```bash
python -m http.server 8000 --bind 127.0.0.1
```

## FPS 두 가지의 의미

사용자가 설명한 현재 앱의 동작을 기준으로 합니다.

| 설정 | 의미 |
|---|---|
| 재생속도 FPS | 초당 재생할 원본 애니메이션 프레임 수 |
| 트위닝 강도 FPS | 보간 후 실제로 보여 주는 목표 초당 프레임 수 |

24/24이면 추가 트위닝이 없고, 재생 24 / 트위닝 48이면 중간 예측 프레임이 생성됩니다.
제공된 XML에서는 이 두 설정을 저장하는 항목을 찾지 못했습니다. 임의의 FPS 필드를 `.sfa`에 추가하지 않으며, 가져온 뒤 앱에서 설정해야 합니다. 설정의 실제 저장 위치는 미확인입니다.

HTML 미리보기의 `--tween-fps`는 목표값을 표시할 뿐입니다. **현재 HTML은 원본 프레임만 재생하며 트위닝을 계산하지 않습니다.**

## 범위와 남은 검증

- 커스텀 제작 편집기는 우선 범위에서 제외합니다. 기존 캐릭터를 사용할 때 필요한 연결·채우기 데이터는 보존합니다.
- 미리보기는 구조 확인용입니다. 원/곡선 렌더링은 샘플에서 추론했으며 채우기·글로우·정확한 굵기와 겹침 순서는 완전 재현하지 않습니다.
- `validate` 성공은 구조 검사 통과입니다. 앱에서 열림·외형·재생 일치를 보장하지 않습니다.
- 동일 도형의 AO ID가 프레임 사이 유지되는 것은 관찰했으나, 앱이 이를 트위닝에 쓰는 정확한 규칙은 아직 모릅니다.
- 자료 수집은 모델의 영구 학습과 다릅니다. 후속 단계에서 동작 명령 형식, 자료 검색, 생성 결과 평가를 만든 뒤 학습 필요성을 판단합니다.

형식 근거와 불확실성은 [docs/FORMAT.md](docs/FORMAT.md)에 정리했습니다. 나무위키는 근거로 사용하지 않습니다.

## 검사

```bash
python -m unittest discover -s tests -v
```
