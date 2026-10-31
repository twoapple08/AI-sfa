# GPT 재확인 — 조합 문제 1라운드 수정 코드 (2026-11-01)

검토 요청: `docs/GPT-RESPONSE-COMPOSE-ROUND1-2026-11-01.md` 전체를 읽고 수정 커밋 `8fb38f3`·`7ac663a`가 1라운드 지적을 반영했는지 확인. 특히 ④ 원 면 반전, ⑤ 추세 생성 상한, 공식 판정 조건을 확인했다.

검토한 브랜치 HEAD는 `e6a02fc3a46b8b6070cb51d39c828d12057cf927`이다. 이 문서는 검토 결과와 인공 반례를 전달하기 위한 기록이다. 학습 코드 수정이나 GPU 실행은 하지 않았다.

## 판정

**대부분 반영됐지만 아직 “논증거리 없음”으로 닫을 수 없다.** 반전 공식과 방향별 상한 문제는 해소됐다. 공식 판정의 시간 조건은 맞지만, 축소 평가 목록·고해상도를 배제하는 조건이 빠졌다. 또한 정합성 검사 추가로 고해상도 학습 영상의 굵기를 바꾸는 새로운 불일치가 생겼다.

## 1. ④ 원 부분 면 반전 — 반영됨

기존 원의 각도는 `θ(t)=θ0+2πt`다. 좌우 반사 후 각도는 `π−θ0−2πt`이고, 반사된 첫 점의 각도는 `π−θ0`이므로 새로운 매개변수는 `−t`다. 두 끝점에 **같은 정수 k**를 더한 `k−t`는 같은 경로다. 두 끝점의 차이 부호도 뒤집힌다.

- `_mirror_t()`가 두 끝점에 같은 k를 적용한다.
- `mirror_fs()`는 부분 원 조각에 이를 적용한다.
- 복합 윤곽 안 WHOLE 원의 `0→1`을 `1→0`으로 바꾸는 것도 맞다.
- 독립 WHOLE 원을 유지하는 것도 맞다.
- 조합 배치와 실제 장 변환 양쪽에 호출이 연결돼 있다.
- 비스듬한 지름의 부분 면·복합 WHOLE 원에 대한 기존 거울상 회귀 검사를 직접 실행했고 통과했다.

이 공식 자체에 추가 논증거리는 없다.

근거: [sfa_compose.py](https://github.com/twoapple08/AI-sfa/blob/e6a02fc3a46b8b6070cb51d39c828d12057cf927/tools/sfa_compose.py#L110).

## 2. ⑤ 추세 상한 — 반영됨

`judge_eval()`은 장 i의 네 방향 정답 길이 최댓값을 먼저 구하고, 어느 방향을 입력하든 그 값으로 같은 상한을 쓴다.

- 스가구신버2: 25/22/25/22 → 네 방향 모두 178.
- Jsjw_SPECTRUM: 97/100/97/100 → 네 방향 모두 328.
- 922: 최댓값 1738 → 네 방향 모두 모델 최대 길이 2048.
- 공식 판정에서는 `n_ans=None`을 전달하므로 정답 길이와 무관하게 2048을 쓴다.

이로써 이전의 “입력을 무시하는 같은 생성 흐름도 방향별로 다르게 잘린다”는 경로는 해소됐다. 정답 길이를 이용한 조기 제한이므로 추세 점수는 제한 없는 공식 점수와 구분해야 한다는 기존 조건은 유지한다.

생성 종료도 `eos/forced/limit`으로 구분하고 강제 종료를 완료로 보지 않도록 바뀌었다. 기본 탐욕 생성 경로의 구현은 취지에 맞다.

근거: [seq_train.py](https://github.com/twoapple08/AI-sfa/blob/e6a02fc3a46b8b6070cb51d39c828d12057cf927/tools/seq_train.py#L683).

## 3. 공식 판정 조건 — 시간 조건은 맞지만 충분하지 않음

현재 식은 다음과 같다.

```python
official = bool(final and st['done_min'] >= st['plan_min'] - 1e-6)
```

회차만 끝난 경우와 전체 계획이 끝난 경우를 구분하는 방향은 맞다. 마지막 경로에서는 먼저 `save_ckpt()`가 `done_min`을 갱신하므로, 단순히 오래된 저장 시각을 비교하는 문제는 아니다.

다만 이 식은 **평가 목록의 완전성과 판정 해상도를 확인하지 않는다.** 실제 코드의 조건식을 추출해 확인한 결과는 다음과 같다. 전체 학습을 실행한 결과가 아니라 조건식 단위 확인이다.

| 조건 | 현재 official |
|---|---|
| 중간 판정, 600/600분 | false |
| 마지막 판정, 599/600분 | false |
| 마지막 판정, 600/600분 | true |
| 마지막 판정, 600/600분, `--judge-n 3` | **true** |
| 마지막 판정, 600/600분, 판정 폭 1920 | **true** |

`--judge-n`은 CPU 흐름 시험용으로 목록을 줄이는 옵션인데 공식 판정에서 배제되지 않는다. 고해상도에서 계획 시간이 끝나도 고해상도 결과가 공식으로 표시되고, 뒤따르는 360 결과는 추세로 표시된다.

최소한 **전체 고정 평가 목록 사용 + 360 입력(640폭) + 계획 끝의 마지막 판정**을 함께 확인해야 한다. 축소 CPU 흐름 시험은 계획 시간이 끝나도 공식으로 표시하지 않아야 한다. 사전 지정된 최초 끝·연장 끝 두 기회라는 운용 조건도 유지해야 한다.

근거: [seq_train.py 700행](https://github.com/twoapple08/AI-sfa/blob/e6a02fc3a46b8b6070cb51d39c828d12057cf927/tools/seq_train.py#L700).

## 4. 새로 재현한 불일치 — 정합성 검사가 고해상도 선 굵기를 바꿈

**공식 검토를 닫기 전에 고쳐야 할 구현 문제다.**

`seq_check.mismatch()`는 640폭 검사를 위해 전역 렌더 설정을 다음과 같이 바꾼 뒤 복원하지 않는다.

```python
R.PARAMS['pad'] = 0.0
R.PARAMS['thick_mul'] = 640 / 1920
```

`seq_data.save_frames()`는 처음에 학습 폭에 맞는 굵기를 설정하지만, 그 뒤 위 검사를 실행하고, 변경된 설정 그대로 실제 학습 영상을 렌더한다.

실제 `save_frames(..., W=1920, video=True)`와 H.264 저장·복원 경로를 거친 인공 장면의 결과:

| 조건 | 저장된 1920×1080 영상의 선 두께 |
|---|---:|
| 정합성 검사 OFF | **36화소** |
| 정합성 검사 ON | **12화소** |

정답 토큰은 같았고, 검사 ON의 정합성 기록은 **0**이었다. 검사는 640폭에서 올바르게 그린 두 그림끼리 비교하므로, 이후 고해상도 저장 영상이 잘못되는 문제를 놓친다.

`CHECK_EVERY=50`에서도 첫 번째 저장 장이 반드시 검사되므로 검사 표본뿐 아니라 **해당 npz의 전체 장**에 영향을 준다. 선 굵기뿐 아니라 같은 설정을 사용하는 글로우의 폭·흐림에도 영향을 준다.

수정 방향:

1. `mismatch()`가 변경한 렌더 설정을 `try/finally`로 항상 복원한다.
2. 검사 ON/OFF에서 실제 저장·복원한 고해상도 영상이 같은지 통합 검사를 추가한다.
3. 이 코드로 만든 고해상도 자료는 수정 후 다시 만든다. 기존 자료가 완료 표시 때문에 재사용되지 않도록 자료 판 또는 코드 해시도 갱신한다. 특히 `seq_check.py`만 고칠 경우 현재 Kaggle `CODE` 목록에는 그 파일이 없다는 점을 반영해야 한다.

근거: [seq_check.py 29행](https://github.com/twoapple08/AI-sfa/blob/e6a02fc3a46b8b6070cb51d39c828d12057cf927/tools/seq_check.py#L29), [seq_data.py 144행](https://github.com/twoapple08/AI-sfa/blob/e6a02fc3a46b8b6070cb51d39c828d12057cf927/tools/seq_data.py#L144).

## 5. 그 밖의 지적과 검증 범위

- 모두 숨긴 레이어, 숨긴 면 주인, 자르기 순서·배경, 장마다 최대 3회, 원 면 반전에 대한 **인공 장면 기반 기존 회귀 검사 5개를 직접 실행해 모두 통과**했다.
- 공식 두 방향과 진단 네 방향의 지표 분리도 인공 자료로 확인했다. 공식 방향만 정답을 내고 추가 두 방향은 빈 출력을 내도록 했을 때, 공식 A=100·건전성 실패 0/6이고 진단 실패는 6/12로 별도 집계됐다.
- `--compose --holdout/--fixed` 금지, 실제 장 출처, 노출 기록, 자료 코드 해시의 합성기 추가는 코드에서 확인했다.
- 전체 116개 시험을 새로 실행한 것은 아니다. 실제 자료의 보고된 빈도, Kaggle 흐름 시험, GPU 학습, 앱 열기는 이번 재확인에서 독립적으로 재측정하지 않았다.
- 작품 묶음 누락률·시험/학습 작품 중복·생성 기준 종류별 점수·식별 불가 정답 비율은 응답 문서처럼 별도 측정 과제로 남겨도 된다.

**수정 방향에 대한 기존 논쟁은 대부분 닫혔다. 남은 핵심은 고해상도 렌더 설정 복원과 공식 판정의 완전한 조건이다. 이 둘이 남아 있으므로 전체 검토를 아직 “논증거리 없음”으로 끝내지는 않는다.**

## 부록: 직접 실행한 인공 반례

다음 코드는 검토 기준 커밋의 저장소 루트에 임시 파일로 저장해 실행할 수 있다. 원본 SFA·가중치·GPU·torch가 필요 없다. `numpy scipy skia-python opencv-python-headless`와 `ffmpeg/ffprobe`를 사용한다.

공식 판정 조건·생성 상한은 실제 `seq_train.py`의 AST에서 해당 식·함수를 추출해 확인한다. 전체 모델의 학습·생성 실행으로 해석하지 않는다.

```python
import ast
import contextlib
import copy
import io
import json
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'tools'))
import seq_data as D
import seq_check as SC
import sfa_compose as C
import sfa_render as R
import sfa_tokens as K


def scene():
    seq = ET.Element('Sequence', HeightWidthRatio='0.5625', BackgroundColor='-1')
    fr = ET.SubElement(seq, 'Frame', ID='1', Position='0')
    ET.SubElement(fr, 'LayerDef', ID='0', Visible='true')
    ao = ET.SubElement(fr, 'AO', ID='1', TypeId='1', Color='-16777216', LayerId='0',
                       DrawOrder='0', ThicknessScale=repr(C.snap_th(4)))
    for i, x in enumerate((20, 80)):
        ET.SubElement(ao, 'AP', ID=str(i+10), X=str(x), Y='50')
    return seq, fr


out = {}
seq, fr = scene()
R.PARAMS.update(pad=0.0, thick_mul=1.0)
out['check_global_state'] = {'before': R.PARAMS['thick_mul'], 'mismatch': SC.mismatch(seq, fr)[0],
                             'after': R.PARAMS['thick_mul']}
assert out['check_global_state']['after'] == 640 / 1920

with tempfile.TemporaryDirectory() as folder:
    results = {}
    for check in (0, 50):
        D.CHECK_EVERY = check
        name = f'sample_{check}.npz'
        D.save_frames(folder, name, [(seq, fr)], 0.5625,
                      dict(W=1920, maxlen=2048, video=True), 23, dict(compose='real'))
        data = np.load(Path(folder)/name)
        pix = D.V.decode_video(data['vid'], 1920, 1080)[0]
        results[check] = dict(black_width=int((pix[:, 960].mean(1) < 128).sum()),
                              global_thick_mul=R.PARAMS['thick_mul'],
                              check=json.loads(str(data['meta']))['items'][0].get('check'))
    out['saved_1080_video'] = {'check_off': results[0], 'check_on': results[50]}
    assert results[0]['black_width'] > 2 * results[50]['black_width']
    assert results[50]['check'] == 0
D.CHECK_EVERY = 50

tree = ast.parse((ROOT/'tools/seq_train.py').read_text())
train = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'train')
judge = next(n for n in train.body if isinstance(n, ast.FunctionDef) and n.name == 'judge_eval')
gen_cap = next(n for n in train.body if isinstance(n, ast.FunctionDef) and n.name == 'gen_cap')
official_ast = next(n.value for n in ast.walk(judge) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'official' for t in n.targets))
official_code = compile(ast.Expression(official_ast), '<actual-official-expression>', 'eval')
out['official_condition'] = []
for final, done, plan, judge_n, w in ((False,600,600,0,640), (True,599,600,0,640),
                                     (True,600,600,0,640), (True,600,600,3,640),
                                     (True,600,600,0,1920)):
    value = eval(official_code, dict(final=final, st=dict(done_min=done, plan_min=plan),
                                     a=SimpleNamespace(judge_n=judge_n), w=w))
    out['official_condition'].append(dict(final=final, done=done, plan=plan, judge_n=judge_n,
                                          width=w, official=value))
assert out['official_condition'][3]['official']
assert out['official_condition'][4]['official']

env = dict(a=SimpleNamespace(gen_len_mult=2.0), cfg=dict(maxlen=2048))
exec(compile(ast.Module(body=[gen_cap], type_ignores=[]), '<actual-gen-cap>', 'exec'), env)
out['caps'] = []
for lengths in ((25,22,25,22),(97,100,97,100),(1724,1712,1738,1712)):
    cap = env['gen_cap'](max(lengths))
    out['caps'].append(dict(lengths=lengths, trend_cap_all_directions=cap,
                            official_cap_all_directions=env['gen_cap'](None)))

print(json.dumps(out, ensure_ascii=False, indent=2))

```
