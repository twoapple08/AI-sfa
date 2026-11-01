# GPT 재검토 — ROUND2-FLOWTEST 응답·수정 코드 (2026-11-01)

대상: `twoapple08/AI-sfa`, 분기 `claude/new-session-gknz4t`, 커밋 `143567e666f16a9f5af1d17c57275136d7e958d5`의 `docs/GPT-RESPONSE-ROUND2-FLOWTEST-2026-11-01.md` 전체와 지정 코드.

**전체 방향에는 대부분 동의한다. 다만 생성 시간 예상식, 큰 원의 특이점, 작은 통합 시험의 자료 구성에 재현 가능한 구현 문제가 남았다. 실패 시간의 학습 진행 포함과 첫 GPU 뒤 계획 확정은 별도의 정책 쟁점이다.**

보고된 작은 CPU 통합 시험 세 회차·Kaggle 자료 수치는 원문 실측 기록으로 읽었다. 이번에 전체 통합 시험이나 GPU/Kaggle 실행을 새로 한 것은 아니다. 직접 실행 범위는 기존 회귀 13개와 아래 인공/수식 반례다.

## 1. 항목별 입장

| 항목 | 입장 | 이유 |
|---|---|---|
| 3-1 공통 학습 진행 시계 | **부분 동의** | train_min을 학습률·단계·분위·공식 계획 끝에 공통 적용하고 읽기·평가·저장을 빼는 것은 맞다. 실패한 시도 시간까지 학습 진행으로 사용하는 부분에는 반대한다. |
| 3-2 절대 마감·마지막 평가 예상 | **부분 동의** | 작업자 시작 기준 마감 전달과 중간 평가/학습 시작 전 검사는 반영됐다. 그러나 새 생성 모형이 긴 출력 비용을 과소 추정한다. 현재는 예상에 따른 조기 종료이며 강제 마감 보장은 아니다. |
| 3-3 연장 분위 유지·학습률 | **동의** | cur_max가 단계별 허용 분위의 후퇴를 막는다. 해상도 유지·전체 길이 유지·명시적인 코사인 재가열 정책은 일관된다. 재가열은 성능 향상 보장이 아니라 사전 선언된 연장 정책이다. |
| 작은 CPU 통합 시험 | **부분 동의** | 네 단계·저장·재개·연장·마감 경로를 실제 학습기로 확인한 근거는 유효하다. 다만 --compose 40/30이 의도한 소량 실제·조합 혼합 자료를 만들지 않는다. |
| 3-4 섞기·선택 기록 | **동의** | 이전 단계는 전체 길이를 유지하고 선택·성공·실패·시간을 나누며 장·토큰은 expo로 보는 방향이 맞다. |
| 먼 곡선 여러 구간 | **보고된 범위에서 동의** | 원본·변환·판정 방향까지 발생 수를 잰 보완이 적절하다. 최대 2,259%, 정합성 0·11·33화소라는 실측 범위를 유지한다. |
| 아주 큰 원 | **부분 동의** | 호를 float64로 만들고 화면 근처를 보존하는 원으로 정규화하는 방향, 기존 쐐기 반례와 두 앱 화면 대조는 근거가 있다. 다만 중심이 화면 중앙과 같은 큰 원에서 0 나누기로 실패한다. |
| 검증 목록·실행 시간 기록 | **동의** | val_list로 원본 파일·Position을 식별하고, 전체 예산은 작업자 시간으로 보는 방향이 맞다. 자료/코드 커밋도 함께 유지해야 한다. |

## 2. 구현 쟁점 A — 생성 모형이 실제로 선형인 표본에서도 과소 추정

출처: [seq_train.py gen_model](https://github.com/twoapple08/AI-sfa/blob/143567e666f16a9f5af1d17c57275136d7e958d5/tools/seq_train.py#L651).

현재 식은 다음과 같다.

- a_w = 해당 폭의 가장 짧은 생성 시간.
- b = median((시간 − a_w) / 토큰 수).
- 예상 = a_w + b × 길이 상한.

가장 짧은 생성 시간에도 이미 디코더 비용이 포함돼 있다. 그것을 순수 고정 비용으로 전부 빼고 다시 전체 길이로 나누면 b가 작아진다.

**GPU 실측이 아니라 정답을 알고 있는 모의 표본** `T(L)=1+0.01L`을 실제 함수에 넣었다.

| 입력 표본 | 함수가 구한 a, b | 2,048토큰 예상 | 정해 둔 선형식의 값 |
|---|---|---:|---:|
| (64, 1.64초), (128, 2.28초) | a=1.64, b=0.0025 | **6.76초** | **21.48초** |
| (128, 2.28초) 한 개 | a=2.28, b=0 | **2.28초** | **21.48초** |

표본 한 개도 32토큰 이상이면 모형이 식별됐다고 보고 b=0을 사용한다. 현재의 '짧은 생성만 있으면 기본 몫' 조건만으로 부족하다. 1.25배 여유로도 이 과소 추정이 해결되지 않는다. 작은 시험의 고정 60초/기본 몫이 넉넉했다는 사실은 큰 모델의 긴 출력 예상 검증을 대신하지 않는다.

필요한 수정·검사:

1. 충분히 다른 길이가 없거나 표본이 하나면 기울기를 미확정으로 취급해 기본 몫을 쓴다.
2. 고정 비용을 별도로 재거나, 같은 폭의 서로 다른 길이 표본에서 절편·기울기를 함께 추정한다. 위 선형 모의 표본을 회귀 시험으로 넣는다.
3. 상한 2,048까지의 외삽을 검증한다. 최대 길이에 따른 디코더 비용이 선형에 가까운지도 GPU에서 측정한다.
4. gen_img 표본에는 채점·시트 등이 포함되지 않고 gen_one에는 추가 교사 강제 진단도 있다. 이 부분은 전체 평가 잔차로라도 따로 측정한다.

작업자 deadline = T0 + 회차 − 정리 몫(3분)은 방향이 맞다. 다만 읽기·양보·단일 평가가 진행되는 도중에는 마감 검사가 없고, 마지막 평가는 무조건 전부 실행한다. 따라서 '예상 몫을 남기려는 구현'과 '반드시 마감 안 종료'는 구분해야 한다. 특히 stage_set 자료 읽기 뒤에도 남은 몫을 다시 확인하는 검사가 유용하다.

## 3. 구현 쟁점 B — canon_circle의 화면 중앙 동심원 특이점

출처: [sfa_tokens.py canon_circle](https://github.com/twoapple08/AI-sfa/blob/143567e666f16a9f5af1d17c57275136d7e958d5/tools/sfa_tokens.py#L183).

다음 입력을 직접 실행했다. 좌표는 기존 BIG 범위 안이고 반지름은 정규화 상한보다 크다.

```python
xy = [(50 - 1e9, 50), (50 + 1e9, 50)]
canon_circle(xy, 0.5625)
```

원의 중심과 기준점 (50, 50)이 같아 n=0이 된다. 그 뒤 vx*t/n, wx*r/n, ux, uy에서 0으로 나눈다.

**canon_circle 직접 호출뿐 아니라 실제 K.encode와 R.render_frame도 모두 ZeroDivisionError로 실패했다.** 이는 인공 반례이며 실제 441파일에서 같은 실패가 관측됐다는 뜻은 아니다.

필요한 수정·검사:

- n=0 또는 가까운 경우의 안전한 처리를 정의한다. 이때 가장 가까운 점 Q의 방향은 유일하지 않다.
- 굵기·글로우를 포함해 화면에 영향 없는 원을 안전하게 제외하거나, 일관된 대체 경로를 쓴다. 눈에 보이는 영향을 새로 만들지 않아야 한다.
- 동심/거의 동심, 화면 안쪽·바깥쪽, 다른 화면 비율의 회귀 검사를 추가한다.

기존 HugeCircleTest 3개와 먼 곡선 5개는 직접 실행해 모두 통과했다. 기존의 거대한 원 띠와 일반적인 접선 정규화 사례는 고쳐졌다는 근거다. 이 새로운 특이점은 기존 8개 검사에 없다.

canon_circle은 반지름이 같은 원으로 바꾸는 정확한 동치 변환이 아니라 화면 근처 오차를 제한하는 근사다. 문서의 처짐 오차·적용 범위·앱 두 장의 눈 대조 범위는 계속 구분해서 유지하는 데 동의한다.

## 4. 구현 쟁점 C — 작은 시험의 --compose 40/30은 조합 작업을 만들지 않음

출처: [seq_flow_small.py 자료 준비](https://github.com/twoapple08/AI-sfa/blob/143567e666f16a9f5af1d17c57275136d7e958d5/tools/seq_flow_small.py#L38), [seq_data.py main_compose](https://github.com/twoapple08/AI-sfa/blob/143567e666f16a9f5af1d17c57275136d7e958d5/tools/seq_data.py#L327).

main_compose는 모든 학습 파일에 최소 한 장씩 실제 장 요청을 만든다. 문서의 403파일 조건을 넣어, 실제 함수의 작업 생성 부분을 실행했다.

| 요청 | 실제 장 요청 | 실제 작업 | 조합 작업 |
|---|---:|---:|---:|
| --compose 40 | **403** | 403개 | **0개** |
| --compose 30 | **403** | 403개 | **0개** |

이것은 작업 계획 확인이다. 실제 저장 장 수는 길이 탈락 등에 따라 달라진다. 다만 조합 작업이 0개라는 점은 확실하다. 그림 합성이 들어간 실제 장이 있더라도 kind=comp 문제와는 다르다.

따라서 '단계마다 실제·조합 문제 40장', '종류별 검증 소수'라는 설명과 실제 준비 경로가 다르다. 단계 전환·마감·재개 시험 전체가 무효라는 뜻은 아니다. 현재 경로 시험이 **조합 장까지 포함한 혼합 자료**를 검증했다는 결론은 보완해야 한다.

권고:

- 소량 요청에서도 실제/조합 목표 수를 맞추거나, 이미 만든 판 7 자료에서 종류별 소수 장을 명시적으로 추출한다.
- 각 해상도와 sc의 실제 장 수·kind별 수를 확인하고 comp와 real이 모두 있는지 시험한다.
- 네 단계의 정규 업데이트는 stage_steps(섞기 포함)뿐 아니라 sel의 폭|cur 성공 수로 검사한다.
- 재개는 '이어하기'라는 문구와 두 번째 최종 진행 증가만 검사하지 말고, 재개 직후 train_min이 이전 저장값과 같은지도 검사한다.
- 시험 자료의 판·씨앗을 확인한다. 현재 build는 done.json 존재만 보고 건너뛴다.

보고된 전환 순서·단계별 분위 시작·연장 유지·마감 5초 이내 종료는 경로가 작동한다는 긍정적 근거다. 위 자료 구성과 추가 실패 검출 범위를 보완한 작은 시험 한 번으로 확인하면 된다. 실제 크기 GPU의 시간 예상 정확도를 이 작은 시험으로 확정하지 않는다는 설명에는 동의한다.

## 5. 정책 쟁점 — 실패 시간의 학습 진행 포함에는 반대

성공한 학습 구간에서 읽기·평가를 제외하고, 학습률·단계·분위가 같은 train_min을 쓰는 것은 동의한다. 하지만 실패한 시도까지 넣으면 모델이 업데이트되지 않아도 단계가 진행한다.

실제 train_tick을 분리 실행하면 step=0인 상태에서도 120초를 더해 train_min=2.0이 된다. 소스에서 메모리 부족·비정상 손실 분기도 이 함수를 호출한다.

실패 시간을 자원 사용 시간으로 기록하는 것은 맞다. 그러나 그것을 학습률·문제 난도·공식 판정의 '학습 계획 끝'으로 모두 사용하는 데는 반대한다.

- 실패/넘침/업데이트 건너뜀 시간은 따로 기록하고 사용 예산에 반영한다.
- 학습 진행은 성공한 업데이트를 기준으로 두거나, 반복 실패 시 원인 조사로 멈춘다.
- 실패만 반복하는 인공 경로에서 단계·분위·공식 준비 상태가 성공 학습처럼 완료되지 않는지 검사한다.
- GPU의 실제 optimizer 업데이트와 성공 기록도 맞춰 본다.

또한 문서의 'tm[train]도 같은 동기 뒤'라는 설명은 현재 코드와 다르다. train_tick은 loss.item() 뒤라 학습 진행 측정은 동기 뒤다. tm['train'] 누적은 여전히 그 앞에 있다. 두 기록을 같게 쓰려면 위치를 맞추고, 구분해 쓴다면 문서의 측정 범위를 정정한다.

## 6. 계획 확정 시점 — 먼저 명시할 것

'첫 GPU 회차에서 비율을 잰 뒤 본 학습 계획을 사용자와 정한다'는 부분은, 기존 '첫 본 학습 회차에 전체 계획 고정'과 연결해 명시해야 한다.

현재 재개 코드는 계획 증가만 반영한다. 계획 600인 저장본에 --plan-minutes 480을 줘도 600으로 남는 것을 실제 분기로 확인했다.

따라서 첫 GPU가 별도 속도 측정인지 본 학습 1회차인지 구분해야 한다. 먼저 짧은 별도 속도 측정으로 본 학습 계산 계획을 정하거나, 최초 회차의 임시 계획을 이후 어떻게 확정할지 사전 정책을 정한다. 성적을 보고 계획을 바꾸자는 뜻은 아니다. 계산 목표·점유 예산·공식 종료 시점을 일관되게 고정하자는 뜻이다.

연장 때 cur_max 유지와 선언한 학습률 재가열은 이 문제와 구분해서 동의한다.

## 7. 측정 과제 — 구조적 수정과 분리

다음은 측정으로 결정할 일이다.

- 실제 크기 GPU에서 폭·길이별 생성 시간, 특히 상한 2,048의 비용.
- final_est_sec / final_sec / deadline_over_sec와 평가·채점·시트·저장 잔차.
- 학습 진행 대비 전체 점유 시간 비율과 본 학습 계산 목표.
- 섞기 선택·성공·실패·장·토큰·시간 비율, 단계 전환 전후 긴 장 성적.
- 실제/조합 생성 성적, 입력 교환/가림 교사 강제 좌표 진단.
- 큰 원 정규화와 여러 구간 곡선의 기존 자료·변환 범위 밖 사례, 앱 대조 확대.
- 검증 목록 hash + 자료·코드 커밋을 유지한 전후 비교.

반면 선형 모의 표본에서의 예상식 오류, 동심원 0 나누기, 작은 자료의 조합 작업 0개는 GPU 실측을 기다려야 알 수 있는 문제가 아니다.

## 8. 검증 범위와 문서 정리

- 직접 실행: test_far_quad.py 8개, test_gpt_recheck.py 5개 통과.
- 공식 판정 시험은 실제 소스에서 순수 공식 함수만 추출해 연결했다. 제어 흐름 시험은 원래 시험의 AST 방식이다. 전체 모델을 불러오지 않았다.
- 큰 원 직접 함수·인코딩·렌더 실패, 생성 예상식과 소량 작업 계획은 별도 인공 반례로 확인했다.
- 전체 통합 시험 세 회차·Kaggle 판 7 생성·14,875회 정합성 검사를 독립 재실행한 것은 아니다. 보고된 실측으로 읽었다.
- 응답 §2의 2.34/3.51분과 마지막 통합 표의 3.81/5.48분은 시험 차수를 표시하면 혼동을 줄일 수 있다.
- 추가 기록 정정: 최종 rec의 minutes는 마지막 교사 검증 뒤, 종류별 검증·생성·마지막 저장 전에 만들어진다. seq_flow_small.check의 wall_min은 이 값을 읽는다. 따라서 표의 벽시계 분을 회차 전체 완료 시각으로 해석하면 안 된다. 최종 평가·저장 뒤 갱신하거나 필드 의미를 명시한다. deadline_over_sec와 time_sec.wall은 뒤에서 계산되므로 이 기록 문제와 구분한다.

현재 상태를 '구현 쟁점 없음'으로 닫는 데에는 반대한다. 위 구현 세 항목과 학습 진행/계획 정의를 정리한 뒤, 그 밖의 성능·예상 정확도는 GPU 측정 과제로 진행하면 된다.

## 부록: 재현 코드

검토 기준 커밋 저장소 루트에 임시 파일로 저장해 실행한다. 원본 SFA·가중치·GPU·torch는 필요 없다. numpy·scipy·skia-python·opencv-python-headless를 사용한다. 생성 시간은 GPU 실측이 아니라 정해 둔 선형식의 모의 표본이다. 작업 계획은 403파일·파일당 한 장 이상이라는 보고 조건을 대체 입력으로 넣는다.

```python
import ast
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT/'tools'))
import sfa_tokens as K
import sfa_render as R
import sfa_compose as C

tree = ast.parse((ROOT/'tools/seq_train.py').read_text())
train = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='train')
cost_nodes = [n for n in train.body if isinstance(n,ast.FunctionDef) and n.name in ('gen_model','gen_cost')]
out = {'generation_model': []}
for samples in ([[64,1.64],[128,2.28]], [[128,2.28]]):
    env = dict(np=np,rate={'gen_s':{'640':samples}},final_plan=lambda final:[(640,2048)])
    exec(compile(ast.Module(body=cost_nodes,type_ignores=[]),'<actual-cost>','exec'),env)
    out['generation_model'].append(dict(samples=samples, model=env['gen_model'](),
        predicted=env['gen_cost'](True), known_affine_value=1+.01*2048))

sq = ET.Element('Sequence',HeightWidthRatio='0.5625',BackgroundColor='-1')
fr = ET.SubElement(sq,'Frame',Position='0')
ET.SubElement(fr,'LayerDef',ID='0',Visible='true')
ao = ET.SubElement(fr,'AO',ID='1',TypeId='2',LayerId='0',Color='-16777216',ThicknessScale='1',DrawOrder='0')
xy = [(50-1e9,50),(50+1e9,50)]
for i,(x,y) in enumerate(xy):
    ET.SubElement(ao,'AP',ID=str(i+10),X=str(x),Y=str(y))
out['centered_circle'] = {}
for key, call in [('canon',lambda:K.canon_circle(xy,.5625)),('encode',lambda:K.encode(sq,fr)),
                  ('render',lambda:R.render_frame(sq,fr,640,360))]:
    try:
        call()
        out['centered_circle'][key] = 'ok'
    except Exception as exc:
        out['centered_circle'][key] = type(exc).__name__+': '+str(exc)

source = ast.parse((ROOT/'tools/seq_data.py').read_text())
main = next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main_compose')
prefix = []
for node in main.body:
    if isinstance(node,ast.With):
        break
    prefix.append(node)
out['small_data_jobs'] = []
for total in (30,40):
    env = dict(a=SimpleNamespace(seed=0,W=640,compose=total,maxlen=2048,video=False,out_dir='unused'),
               V=SimpleNamespace(file_list=lambda:list(range(403))),ROOT='unused')
    root = SimpleNamespace(findall=lambda tag:[object()])
    with patch.object(C,'load',return_value=root), contextlib.redirect_stdout(io.StringIO()):
        exec(compile(ast.Module(body=prefix,type_ignores=[]),'<actual-compose-job-plan>','exec'),env)
    out['small_data_jobs'].append(dict(requested=total,real_jobs=sum(j[0]=='real' for j in env['jobs']),
        comp_jobs=sum(j[0]=='comp' for j in env['jobs']),real_requested=env['real_req'],n_comp=env['n_comp']))

tick = next(n for n in train.body if isinstance(n,ast.FunctionDef) and n.name=='train_tick')
env = dict(time=SimpleNamespace(time=lambda:120.),tm_load=[0.],yl=SimpleNamespace(paused=0.),
           st={'train_min':0.,'step':0},step_s=[0.])
exec(compile(ast.Module(body=[tick],type_ignores=[]),'<actual-tick>','exec'),env)
env['train_tick'](0.,0.,0.)
out['failed_attempt_clock'] = env['st']

restore = next(n for n in train.body if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='saved')
plan = next(n for n in restore.body if isinstance(n,ast.If) and 'plan_minutes' in ast.unparse(n.test))
env = dict(st={'plan_min':600.,'train_min':100.},a=SimpleNamespace(plan_minutes=480.,minutes=180.))
exec(compile(ast.Module(body=[plan],type_ignores=[]),'<actual-plan-restore>','exec'),env)
out['lower_plan_on_resume'] = dict(requested=480,retained=env['st']['plan_min'])
print(json.dumps(out,ensure_ascii=False,indent=2))

```
