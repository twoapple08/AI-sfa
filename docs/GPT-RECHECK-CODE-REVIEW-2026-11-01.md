# GPT 재확인 — 독립 코드 검토 응답·수정 (2026-11-01)

대상: `twoapple08/AI-sfa`, `claude/new-session-gknz4t`, **`344fc305e4c94f5dbbf1208f565dadc5b08a8b06`**. 요청 문서 `docs/GPT-PROMPT-RECHECK-CODE-REVIEW-2026-11-01.md`의 구분선 아래 지시와 Claude 답변 전체를 읽었다. `cb3f34f`, `8b38840` 및 그 사이의 I-10 변경·되돌림까지 대조했다. 줄 번호는 이 SHA 기준이다.

**대부분의 기존 반례는 막혔다. 그러나 업데이트 기록·면 범위·예비 저장본 전송·글로우 묶음 동치 판정에 새 반례가 있어 전체를 닫을 수 없다. E-02의 `np.vstack` 지적은 내 오류로 철회한다.**

표시: **[재현]** 이번에 실제 함수/시험을 실행한 것, **[반례]** 수정 후에도 남는 새 사례, **[의견]** 설계·해석·추가 확인 제안. 모형·서비스를 대체한 실행은 따로 적었다. GPU·Kaggle 실행과 앱 실행은 하지 않았다. 가중치·원본·키를 이 커밋에 넣지 않는다.

## 1. 기존 부록 A–C 재실행과 수정 확인

**[재현] 전체 시험: 154개, 19.612초, OK, 건너뜀 없음.** CPU용 torch/torchvision·Skia·ffmpeg를 사용했다. 같은 서버에서 전체 학습을 장시간 반복한 것은 아니다.

보고서 작성 뒤 본문의 vstack 예제와 부록 A–H, 총 9개 Python 블록도 각각 그대로 실행했다. 모두 정상 종료했다. 부록 A는 옛 블록을 모아 실행하는 장치이며, 그 안의 의도한 scipy 차단 오류·옛 저장 mock의 TypeError는 아래 표처럼 별도로 확인했다.

기존 보고서의 Python 코드 블록 8개를 **먼저 그대로** 각각 실행했다. 원문이 하위 함수를 직접 호출하거나 옛 호출 형태를 가정하는 부분과, 새 런처/공식 자격 확인을 구분해야 한다.

| 원문 블록·지적 | 그대로 실행한 결과 | 실제 수정 확인·판정 |
|---|---|---|
| A / I-02 | `same_fill_order`: 차이 1,224화소는 같지만 **perfect=False, order=0** | 기존 반례 차단. 같은 색 단색 선 교환은 만점 유지하는 회귀도 통과. |
| A / I-03 | `glow_order`: 차이 14,922화소, **perfect=False, order=0** | 기존 반례 차단. 다만 새 면 T 반례 R-02가 남는다. |
| A / I-10 | `remove_ac`: 차이 32화소, **perfect=False** | 기존 반례 차단. 새 `glow_group`에는 R-03의 과도한 감점이 있다. |
| A / I-09 | 묶음 내부 레이어 순서 보존, **차이 0화소** | 기존 반례 차단. LayerDef 순서 역전·AO 저장 순서 차이·정확 배치 조합을 다시 확인했다. 이번 추가 탐색에서 별도 I-09 반례는 찾지 못했다. 이것을 모든 조합의 증명으로 해석하지 않는다. |
| B-1 / I-01 | CPU GradScaler 단독 결과는 그대로 `1→1`, scale `65536→32768` | 원문은 `seq_train`을 부르지 않으므로 이 결과가 그대로인 것은 정상. 추가된 실제 학습기 실패 회귀는 통과. 새 실패 분기 문제 R-01은 별도. |
| B-2 / I-04 | 옛 명령(4분/1분·기본 20분 예약)은 여전히 0걸음 | 옛 명령을 바꾼 것이 아니라 **PC quick 호출부**가 바뀌었다. 새 호출의 예약 0.5분·생성 끔·검증 16장을 확인했고 제어 흐름을 실행했다: `[0]`은 거부, `[5,5]`도 거부, `[5,9]`는 성공. PC 명령은 대체했고 실제 Windows/GPU 실행은 아니다. 같은 범위에서 새 ‘0걸음인데 정상’ 반례는 찾지 못했다. |
| B-3 / I-05 | scipy import를 강제로 차단했으므로 의도대로 ModuleNotFoundError | 세 설치 배치의 scipy 설치·import 확인 추가는 정적 확인. 강제 차단 시험이 계속 실패하는 것을 설치 수정 실패로 해석하지 않는다. 이번에는 깨끗한 Windows 전체 설치를 실행하지 않았다. |
| B-4 / I-07·P-02 | 비공식은 **기준선 초과(추세)**. 같은 계획 재실행은 `True 1 → False None → False None` | 첫 공식→저장→연장 공식 2, 같은 종료점 `repeat`, 세 번째 종료점 `third` 회귀 통과. 조건 변경 탐지도 통과. 생성 제한이 다른 기록 비교는 R-06. |
| B-5 / I-08 | **TypeError**: 원문 mock `lambda *x`가 새 `tries=5` 인수를 받지 못함 | 제품 결함이 아닌 재현 장치의 옛 인터페이스다. mock을 `*x, **kw`로만 바꾸고 재실행하면 본·예비 모두 False일 때 중간 False 반환·저장 속도 미증가, 최종 SystemExit. `[False,True]`는 예비 성공. 새 전송 누락 R-05는 남는다. |
| C-1 / I-06 | 하위 로더·평가·`official_judgment`만 직접 부르므로 원문 출력은 여전히 `6 wrong-list 6 True True` | 새 호출부는 그 전에 `judge_list_ok`를 호출한다. **같은 잘못된 메타데이터를 넣으면 False**이고 추세로 내려간다. 원문의 마지막 True만 보고 수정 실패라고 결론내리면 안 된다. 축소·틀린 해시·폭·방향·묶음 변경 회귀 통과. 내용 검증의 한계는 R-04. |
| C-2 / P-01 | **45/45승, A=99.799942, F1=1, 건전성 92/92** 그대로 | 설계 한계로 인정한 항목이다. 검색기가 위치 입력을 쓰므로 현재 위치 시험 통과는 정당하다. 새 형상 재구성의 증거로 확대하지 않는다. |

I-01–I-10 각각에 대해 수정 경로를 한 단계 더 조사했다. 새 반례를 못 찾은 항목까지 억지로 결함으로 세지 않았다. 특히 I-05의 외부 설치 성공률, I-04의 실제 PC 처리 시간은 이번 재현의 범위 밖이다.

## 2. 수정 후 새 반례

### R-01 — 높음 / I-01: 유한한 기울기의 노름 넘침에서는 ‘실패’로 기록하면서 업데이트한다

**[반례]** `tools/seq_train.py:1054`–`1060`. `clip_grad_norm_`의 반환이 inf라는 사실은 GradScaler가 inf 기울기를 발견했다는 뜻과 다르다. 모든 기울기 값이 유한해도 float32에서 제곱합이 넘쳐 노름이 inf가 될 수 있다. 이때 클리핑 결과는 0이며 scaler의 `found_inf`는 0이다. 실패 분기의 `scaler.step(opt)`는 건너뛰지 않고 실제로 실행한다.

- CPU의 실제 GradScaler·AdamW에서 `[1e20,1e20]` 유한 기울기 → norm=inf → 클리핑 `[0,0]` → weight decay로 가중치 **`[1,1] → [0.99,0.99]`**, optimizer step=1을 확인했다.
- 실제 작은 `seq_train` 실행에도 적용했다. CPU에서 AMP 분기를 확인하기 위해 GradScaler만 CPU enabled로 대체하고, 노름 계산 직전에 기울기를 유한한 1e20으로 주입했다. **기록 step=0, train_min=0, 실패 3, stop=failures인데 옵티마이저 내부 step=3**이다. GPU 자연 발생 빈도/속도를 측정한 것은 아니다.
- 기존 회귀는 CPU에서 scaler가 꺼진 채 노름만 inf로 돌려줘 이 분기를 잡지 못한다.

**[의견] 수정 방향:** 실패하기로 정한 분기에서는 `optimizer.step`에 도달하지 않도록 한다. unscale 뒤 scaler 상태 정리와 optimizer 실행을 분리한다. 유한 기울기 여부와 안정적인 노름 계산(float64/스케일 조정)을 구분하고, **실패 기록 시 파라미터·optimizer step 모두 보존**되는지 시험한다. 기존 ‘업데이트 없이 성공 기록’은 고쳤지만 그 반대 반례가 남았다.

### R-02 — 높음 / I-03: 면 조각 T가 직선 끝점을 넘어가면 여전히 다른 영상에 만점을 준다

**[반례]** `tools/sfa_objscore.py:317`–`333`. 추가된 면 범위는 참조 오브젝트 원래 점들의 상자다. 렌더러의 **직선 FS T는 [0,1]로 자르지 않는다**. 따라서 T=3인 면은 원래 선의 끝점을 훨씬 넘어간다.

부록 D의 `extrapolated_fill`은 투명한 두 수평선의 T `0→3`, `3→0`으로 x=10~40의 빨간 면을 만들고, x=30의 파란 선을 면 앞/뒤로 바꾼다. 면 참조 선끼리의 순서는 그대로다. 결과는 **perfect=True, order=1, fill_f1=1**인데 서버 렌더 차이가 **588화소**, σ=1.5 비교 **1,174화소**다. T=3은 토큰 문법으로도 표현 가능한 값이다.

**[의견] 수정 방향:** 면의 실제 FS `[T0,T1]` 경로와 자동 연결선·구멍을 이용해 경계를 계산한다. 곡선은 렌더러처럼 T를 제한하고 직선·원은 제한하지 않는 차이를 그대로 따른다. ‘모든 참조 오브젝트 상자 합’만으로 안전한 상한이 된다고 보면 안 된다. 같은 점수·다른 영상 반례이며 공식 위치 부분 점수 자체의 정의를 바꾸자는 의견은 아니다.

### R-03 — 중간 / I-10: `glow_group`이 영상이 같은 연결 차이까지 감점한다

**[반례]** `tools/sfa_objscore.py:348`–`360`; `tools/sfa_render.py:307`–`327`; `tools/sfa_tokens.py:223`–`246`.

두 경우 모두 **좌표·스타일·순서는 같고 AC만 다르다**.

| 새 사례 | 실제 서버 렌더 차이 | 채점 |
|---|---:|---|
| 서로 다른 보이는 레이어의 두 선을 연결/비연결 | **0화소, 흐림 비교도 0** | `glow_group=0`, **perfect=False** |
| 같은 레이어, 선 알파 0인 글로우 전용 두 선을 연결/비연결 | **0화소, 흐림 비교도 0** | `glow_group=0`, **perfect=False** |

첫 사례에서 renderer는 **레이어마다** 그룹을 나눠 그리는데 채점기는 전역 연결 그룹의 동일 여부를 비교한다. 둘째에서는 실제 선이 없어서 ‘글로우 A·글로우 B’라는 합성 순서가 같아진다. 그룹이 다르다는 것만으로 영상이 다르다는 충분조건이 되지 않는다. 앱에서도 같다는 실측은 이번에 하지 않았다.

**[의견] 수정 방향:** 레이어를 포함한 실제 그리기 연산 순서를 비교해야 한다. 그룹 관계를 진단값으로 두더라도 만점 감점은 순서가 바뀌는 **보이는 선/면과 글로우의 상호작용**에 연결한다. 같은 레이어 기본 V 반례를 막은 수정은 인정하지만 전역 그룹 관계를 곧바로 영상 동치의 필수조건으로 삼는 것은 과하다. 앱 교차 레이어 확인은 §3 설계로 한다.

### R-04 — 중간 / I-06: 메타데이터는 전체 목록인데 실제 내용은 한 장 반복이어도 자격을 통과한다

**[반례]** `tools/seq_train.py:1201`–`1205`; `tools/seq_judge.py:301`–`317`.

기존처럼 **메타데이터 entries 자체가 6개**인 자료는 이제 거부한다. 새 사례는 목록·해시·방향·폭을 그대로 두고, 실제 `img`, `tok`, `tok0`, offset 배열을 **첫 장의 네 방향 46회 반복**으로 바꾼 형식상 정상 npz다. 실제 로더·평가 함수를 실행한 결과:

```text
judge_list_ok=True, 메타 장 수=46, 실제 원래 자리 정답 종류=1,
독립 단위라고 계산한 N=45, 승=45, passed_all=True
```

**[의견] 범위와 수정 방향:** 정상 `build_data`가 이런 자료를 만든다는 증거는 없다. 생성 후 혼합·잘못된 복사·내용 손상을 메타데이터 검사만으로 검출하지 못한다는 보강 지적이다. `tok0`는 이미 manifest에 있는 각 장 `frame_hash`와 대조할 수 있다. 방향별 정답·영상의 개수/offset/크기도 검사하고, 생성 코드/자료 내용의 식별값을 신뢰하는 생성 기록에 연결한다. 같은 npz 안에 사용자가 다시 계산할 수 있는 checksum만 넣으면 고의 조작 방지까지 되는 것은 아니므로 그 보장 범위도 구분한다.

### R-05 — 높음 / I-08: 로컬 예비 저장본은 살리지만 PC/Drive/Kaggle 전송은 옛 본 파일만 가져간다

**[반례]** `tools/seq_train.py:720`–`738`; `tools/pc_seq_run.py:21`, `163`–`170`; `tools/kaggle_seq_remote.py:187`–`195`, `208`–`218`; `tools/kaggle_seq_worker.py:131`–`136`.

본 파일 잠금 실패를 주입하고 실제 torch 파일 저장으로 예비 저장본을 만들었다. 최종 `save_ckpt(final=True)`는 True다. 그러나 PC의 **실제 KEEP 목록**으로 로컬 전송을 모의하면:

```text
로컬 ckpt.pt:          step=10, official_n=1
로컬 ckpt.pt.fallback: step=20, official_n=2
전송된 ckpt.pt:        step=10, official_n=1
KEEP에 fallback:       False
```

Drive/Kaggle API는 호출하지 않았다. 같은 누락을 원격 `save-ckpt`, `to-drive`, `from-drive`와 Kaggle 입력 복사 목록에서도 코드로 확인했다. fallback만 있고 본 파일이 없으면 일부 경로는 아예 저장본이 없다고 거부한다. 로컬 `train`의 최신 파일 선택은 정상이어도 다른 PC/커널로 옮기면 최신 학습과 공식 횟수를 잃을 수 있다.

**[의견] 수정 방향:** 전송·zip·입력 복사 전에 본/예비 중 최신 **유효** 체크포인트를 고르는 함수를 공용으로 쓰고 정규 export 이름으로 내보낸다. 또는 두 파일을 모두 전달하고 수신 측도 같은 선택 규칙을 쓴다. ‘본 실패→예비 성공→전송→새 출력 폴더 재개’ 통합 회귀가 필요하다. 기존의 본·예비 모두 실패 시 최종 종료는 제대로 고쳐졌다.

### R-06 — 중간 / I-07: 추세 상한과 공식 최대 길이를 여전히 같은 조건으로 비교한다

**[반례]** `tools/seq_trend.py:44`–`46`, `67`–`94`. 조건 키에는 폭·축소·장 수·검증 목록만 있다. 같은 폭·목록에서 `judge_official=False`인 정답 길이 기반 상한 평가와 `True`인 최대 길이 평가는 `cond()`가 같다. 부록 H의 모의 기록은 상한 강제 종료 92개 → 자연 종료 92개를 넣어도 조건 변경 경고 없이 **‘위치를 더 읽음’**이라고 한다.

**[의견] 수정 방향:** 실제 생성 상한/옵션과 판정 목록 식별값을 기록하고 조건 키에 넣는다. 공식 여부만 나눠도 현재 상한/최대 길이 혼합을 우선 막을 수 있지만, `--gen-len-mult` 변경까지 보려면 실제 옵션이 필요하다. 새 `badge`의 공식 표시 수정과 해상도/검증 목록 분리는 인정한다. 이 모의 기록을 실제 모델의 성장/퇴보 실측으로 해석하지 않는다.

## 3. I-10 앱 근거에 대한 의견과 추가 시험 설계

**[의견] 기본 결론에는 동의하되 적용 범위를 제한한다.** 문서상 유효한 test3·test4의 V 모양·점 값·이음 방향·일방 AC 대조와 실제 파일 두 장은 ‘같은 레이어의 연결 무리에서 글로우를 먼저 모두 그린다’는 작동 가설을 지지한다. 잘못된 점 ID로 만든 test1·test2는 반증 자료에서 제외하는 것이 맞다. 실제 파일 대조로 보완한 것도 적절하다.

다만 이번 저장소에는 네 시험 SFA와 앱 화면 원본이 없어서 **내가 화면·파일 불변 조건을 독립적으로 다시 본 것은 아니다**. 위 판단은 Claude 응답과 `GROUP_MODE` 주석의 실측 기록에 대한 검토다. 이것만으로 다른 레이어·숨긴 연결 다리·복합 면·원/곡선에도 같은 범위로 적용됨을 증명했다고 말할 수 없다. `link_groups(..., frs=())`의 `frs`는 현재 쓰이지 않아 면 참조 자체가 그룹을 합치는지도 이 코드만으로 확인되지 않는다.

보고된 93/4,703장(2.0%)은 ‘글로우 있는 연결 무리가 있음’의 후보 빈도다. 실제로 만점 여부가 바뀌는 장 수나 새 반례의 발생률을 직접 측정한 수치로 해석하지 않는다.

추가 앱 시험은 다음처럼 최소한의 차이만 만든다. 원본/스크린샷을 공개 저장소에 올리라는 요청이 아니다. 이 보고서에는 **설계만** 남긴다.

| 파일·장 | 고정할 것 / 장마다 바꿀 것 | 볼 곳·구별되는 가설 |
|---|---|---|
| T-L, 4장: 다른 레이어 | 검정 A는 레이어 0, 빨간 선+청록 글로우 B는 레이어 1, 레이어 순서 0→1 고정. 0장 AC 없음, 1장 A→B, 2장 양방향, 3장 숨긴 레이어 2의 C를 경유한 A–C–B. 좌표/색/굵기 동일. | 교차점의 검정 위에 청록이 덮이는지. 현재 renderer는 보이는 레이어를 따로 그리므로 네 장 동일을 예측한다. 달라지면 전역 그룹/숨긴 다리가 레이어 그리기에 개입하는 범위를 다시 모델링해야 한다. |
| T-F, 4장: 면 주인과 그룹 | 같은 레이어. 삼각형 면 경계 A0/A1/A2와 겹치는 글로우 선 B. AO 최초 등장 순서는 A0,B,A1,A2로 고정, FR 첫 FS 주인은 A0 고정. 0장 AC 없음, 1장 A0–B, 2장 A1–B, 3장 A0–A1만 연결. FR/좌표는 동일. | 빨간 면 위/아래의 청록 번짐과 B 선을 비교. 면을 참조한다는 이유만으로 그룹이 합쳐지는지, 첫 FS 주인만 그리기 시점을 정하는지, AC 그룹의 삽입 순서가 영향을 주는지 가른다. |
| T-Q, 4장: 원·곡선·추이 연결 | 오브젝트 종류를 고정: 곡선 A, 원 B, 직선 C. 끝점이 실제로 만나는 배치, 각 글로우 색은 구별 가능하게. 0장 연결 없음, 1장 A–B, 2장 A–C, 3장 둘 다. | 원·곡선에서도 같은 ‘그룹 글로우 먼저’인지, A를 통한 추이 그룹이 맞는지. TypeId를 같은 ID에서 바꾸지 않는다. |
| T-G, 2장: 글로우 전용 | 같은 레이어 두 오브젝트. 선 Color 알파 0, 서로 다른 색 글로우만 보임. 0장 연결 없음, 1장 연결. | 두 영상이 같으면 R-03처럼 그룹 관계 자체를 감점하면 안 된다. 다르면 현재 renderer에 없는 앱 연산이 있는 것이다. |

**점·오브젝트 ID 불변 조건:** 각 파일에서 A=AO 10, B=20, C=30처럼 역할별 ID를 고정하고 점도 A의 100/101(/102), B의 200/201처럼 고정한다. 같은 점 ID를 다른 AO/다른 역할로 재사용하지 않는다. 모든 장에서 같은 AO의 LayerId·TypeId·점 역할·파일 공통 레이어 순서를 유지하고 AC만 바꾼다. Frame ID와 Position은 장별로 구별한다. 사용하지 않는 C도 숨긴 채 같은 역할로 두며 점 ID를 B에 돌려 쓰지 않는다. 면 시험은 A0/A1/A2 각 AO에 별도의 고정 점 ID 구간을 준다. 제작 시 파일 전체에서 `AP.ID→AO.ID`, `AO.ID→LayerId/TypeId`가 하나로 정해지는지 자동 검사하고, 앱을 닫았다 다시 열었을 때도 같은지 확인한다.

배치 예시는 T-L에서 A `(30,25)→(50,65)`, B `(50,65)→(70,25)`로 두고 이미 겹친 끝점끼리 연결한다. T-Q는 A의 세 점 `(30,25),(30,60),(50,65)`, 원 B의 지름 끝 `(50,65),(50,35)`, 직선 C `(50,65)→(70,25)`로 공통 끝점을 만든다. T-F는 삼각형 꼭짓점 `(25,25),(60,25),(45,70)`과 첫 변에 겹친 B를 쓰면, A0–B와 A1–B 모두 실제로 겹친 점끼리 연결할 수 있다. 앱이 연결하면서 점을 옮기는 효과가 시험에 섞이지 않도록 한다.

## 4. E-02 반론 — 내 지적을 철회한다

**[재현]** `np.vstack`은 높이(축 0)를 이어 붙인다. 폭·채널이 같으면 높이가 달라도 된다.

```python
import numpy as np
a=np.zeros((270,1440,3),np.uint8)
b=np.zeros((480,1440,3),np.uint8)
print(np.vstack([a,b]).shape)  # (750, 1440, 3)
```

**[의견] Claude 반론이 맞다.** `draw`의 각 행은 3×W 폭과 3채널로 같으므로 hwr 때문에 행 높이가 다른 것만으로 실패하지 않는다. 내가 앞 보고서 E-02에 적은 ‘높이가 달라 vstack 실패’는 잘못된 지적이었다. 그 수정 권고를 철회한다. 출력 SFA가 첫 장의 비율을 쓰는 별도 제약은 이 vstack 논쟁의 근거가 아니다. 원래 보고서는 역사 기록으로 남기고 여기서 정정한다.

## 5. P-01·P-03: 사용자에게 제시할 선택지

**[의견] 아래는 선택지이며 이번 재검토에서 임의로 실행·기준 변경하지 않았다.** 현재 위치 공식 기회 두 번과 α=0.025를 소급 변경하지 않는다. 이미 CPU 흐름 시험 등에서 본 sv를 ‘처음부터 미사용’이라고 부르지 않는다. `47112(2_2)-1`의 7·8장만 제외하는 결정도 유지한다.

| 선택지 | 장점 | 한계·비용 |
|---|---|---|
| **A. 현재 시험 유지, 주장 범위 제한** | 기존 위치 공식 시험과 sv 추세·시트를 그대로 쓴다. 추가 자료 분리/생성 비용이 가장 작다. | ‘위치를 입력에서 사용함’은 말할 수 있지만 일반적인 새 형상 재구성의 독립 최종 확인은 약하다. 같은 sv 결과로 계속 방식을 조정한 선택 편향이 남는다. 추가 GPU 평가를 요구하지 않는 선택이다. |
| **B. 이후부터 판단용·최종용 작품 묶음 분리 — 권고** | sv 38파일을 내용 묶음으로 확인한 뒤 대략 2/3 판단용·1/3 최종용에서 시작한다. 고정 목록·해시·분리 시점을 기록하고 최종용은 이후 중간 평가/설정 선택에서 제외한다. 기존 위치 공식 시험과 새 작품 최종 확인의 역할이 분명하다. | 이미 본 과거는 지울 수 없다. 약 13파일이라는 숫자는 예시이며 실제 그룹 수는 내용 대조 뒤 확정해야 한다. CPU 중복 검사·목록 준비, 최종 1회 생성 비용이 든다. 정확 시간은 자료 크기·속도 측정 뒤 산정하며 GPU 실행을 먼저 요구하지 않는다. 작은 최종 그룹 수의 불확실성도 함께 보고한다. |
| **C. 새 미사용 작품/형상으로 별도 공식 실험** | 사용 승인을 받은 새 자료에서 독립 작품 묶음·장·평가 방법을 사전 고정한다. 새로운 형상과 연속 이동/크기까지 별도 확인할 수 있어 가장 강한 일반화 근거다. | 자료 확보·허용 범위 확인·중복 검사·앱/정답 품질 검사의 비용이 가장 크다. 새 작가/자료를 임의로 추가하지 않는다. 생성 수를 K장으로 고정하면 최종 비용은 `Σ(폭별 고정비용 + 길이별 생성비용 + 채점)`이며 GPU 시간은 기존 속도 측정 이후 계산한다. 현재 모델의 성적을 본 뒤 유리한 장/합격선을 고르면 안 된다. |

권고는 **B를 준비하되, C는 실제로 새 자료가 확보되고 강한 일반화 주장이 필요할 때 별도 실험으로 선언**하는 것이다. 판단용 결과만으로 설정을 바꾸고 최종용은 한 번 확인한다. 실패했으면 실패/불확실로 기록하며, 같은 최종 목록을 계속 보고도 ‘미사용 최종’이라는 이름을 유지하지 않는다.

## 6. 다음 조치와 검증 범위

**[의견] 우선 수정할 것:** R-01의 실패 분기 optimizer 실행, R-02의 FS T 경계, R-05의 예비 파일 전송. R-03은 기존 앱 기본 V 결론을 철회할 사유가 아니라, 채점에서 그 결론을 적용하는 범위를 정교하게 할 사유다. R-04는 정상 생성 경로 결함 주장과 구분한 내용 무결성 보강, R-06은 표시/추세 해석 보강이다.

보고서의 반례는 서버 렌더·CPU 함수·제어 흐름·파일 직렬화로 확인했다. Windows 잠금·앱 화면·Kaggle 자료 판 9 완료·GPU 속도/overflow 빈도를 이번에 독립 측정하지 않았다. 임시 산출물과 작은 가중치는 `/tmp/gpt-recheck-*`에만 두었으며 영구 보존을 전제하지 않는다. 아래 부록에 공개 가능한 인공 재현 코드를 남긴다.

## 부록. 실행 가능한 재현 코드

저장소 루트에서 코드 블록을 각각 임시 `.py`로 저장해 실행한다. 모델 다운로드·GPU·Kaggle을 사용하지 않는다. torch는 CPU 빌드로 실행하거나 `CUDA_VISIBLE_DEVICES=''`를 설정한다. 코드/시험 수정은 하지 않는다.

### A. 기존 보고서 Python 블록 8개를 그대로 실행

```python
import re,sys,subprocess,tempfile
from pathlib import Path
text=Path('docs/GPT-CODE-REVIEW-2026-11-01.md').read_text(encoding='utf-8')
blocks=re.findall(r'```python\n(.*?)\n```',text,re.S)
with tempfile.TemporaryDirectory() as td:
    for i,b in enumerate(blocks):
        p=Path(td)/f'repro_{i}.py'; p.write_text(b,encoding='utf-8')
        r=subprocess.run([sys.executable,str(p)],capture_output=True,text=True,timeout=120)
        print('BLOCK',i,'RC',r.returncode)
        print(r.stdout)
        if r.returncode: print(r.stderr[-1000:])
```

C-1/C-2에 필요한 로컬 판정 자료는 기존 부록의 `python tools/seq_judge.py build /tmp/gpt-review-judge --stage-w ''`로 준비한다. 이 자료는 비공개 임시 경로에 두고 커밋하지 않는다. B-5 재현 장치를 새 인터페이스에 맞추려면 **그 블록에서만** `save=lambda *x:False`를 `save=lambda *x,**kw:False`로 바꾼다. 기존 시험의 새 실패 처리·공식 자격 확인도 함께 실행한다.

```sh
CUDA_VISIBLE_DEVICES='' python -m unittest discover -s tests -v
```

### B. 유한 기울기 노름 넘침과 실제 학습 기록

```python
import torch
p=torch.nn.Parameter(torch.ones(2))
opt=torch.optim.AdamW([p],lr=.1,weight_decay=.1)
sc=torch.amp.GradScaler('cpu')
sc.scale(p.square().sum()).backward()
p.grad.fill_(sc.get_scale()*1e20)
sc.unscale_(opt)
assert torch.isfinite(p.grad).all()
norm=torch.nn.utils.clip_grad_norm_([p],1.)
if not torch.isfinite(norm):
    sc.step(opt); sc.update()  # 현행 실패 분기
print(norm.item(),p.tolist(),float(opt.state[p]['step']))
# inf [0.9900000095367432, 0.9900000095367432] 1.0

# 작은 실제 학습기의 실패 기록과 옵티마이저 step을 비교한다.
import sys,json,torch
from unittest.mock import patch
sys.path[:0]=['tools','tests']
from test_gpt_code_review import toy_run
real_scaler=torch.amp.GradScaler;real_clip=torch.nn.utils.clip_grad_norm_;real_opt=torch.optim.AdamW;opts=[]
def cpu_scaler(*a,**kw):return real_scaler('cpu',enabled=True)
def clip(params,*a,**kw):
 ps=list(params)
 for p in ps:
  if p.grad is not None:p.grad.fill_(1e20)
 return real_clip(ps,*a,**kw)
def optimizer(*a,**kw):
 o=real_opt(*a,**kw);opts.append(o);return o
r=toy_run(['--plan-minutes','.5','--max-fail-row','3','--lr','1'],patches=[patch.object(torch.amp,'GradScaler',cpu_scaler),patch.object(torch.nn.utils,'clip_grad_norm_',clip),patch.object(torch.optim,'AdamW',optimizer)])
print('finite_grad_norm_overflow',{'record_step':r['step'],'record_train_min':r['train_min'],'stop':r['stop'],'failed':sum(x[2] for x in r['sel'].values()),'optimizer_step':max(float(s['step']) for s in opts[0].state.values())})
```

### C. 전체 목록 메타데이터 + 반복된 실제 내용

```python
import sys,tempfile,json,pathlib,numpy as np
sys.path.insert(0,'tools');import seq_judge as J,seq_train as ST
with np.load('/tmp/gpt-review-judge/judge.npz') as z:d={k:z[k] for k in z.files}
m=json.loads(str(d['meta']));n=len(m['entries']);tok=d['tok'];off=d['off'];samples=[tok[off[k]:off[k+1]] for k in range(4)];t0=d['tok0'][d['off0'][0]:d['off0'][1]]
d.update(img=np.concatenate([d['img'][:4]]*n),tok=np.concatenate(samples*n),off=np.cumsum([0]+[len(t) for t in samples*n]),tok0=np.concatenate([t0]*n),off0=np.arange(n+1)*len(t0))
with tempfile.TemporaryDirectory() as td:
 np.savez_compressed(pathlib.Path(td)/'judge.npz',**d);js=J.JudgeSet(td,640)
 out,_=J.evaluate(js,lambda i,d:(js.tok[i][d],True,0.),dirs=range(2))
 print('duplicated_payload',{'list_ok':ST.judge_list_ok(js.meta,J.load_manifest()),'meta_n':len(js),'unique_original_answers':len({tuple(t) for t in js.tok0}),'N':out['judge']['N'],'wins':out['judge']['win'],'passed_all':out['judge']['passed_all']})
```

### D. FS T·교차 레이어·글로우 전용 반례

```python
import sys,copy,xml.etree.ElementTree as E
sys.path[:0]=['tools','tests']
import numpy as np
import sfa_render as R,sfa_objscore as OS,seq_check as SC,sfa_tokens as K
from test_sfa_objscore import frame,BLACK,RED
R.PARAMS.update(pad=0.,thick_mul=640/1920)
sq=E.Element('Sequence',HeightWidthRatio='.5625',BackgroundColor='-1')
def report(name,p,a):
 x,y=R.render_frame(sq,p,640,360),R.render_frame(sq,a,640,360);s=OS.score(p,a)
 print(name,{k:s.get(k) for k in ('perfect','order','glow_group','fill_f1')},'raw',int((np.abs(x.astype(int)-y.astype(int)).max(-1)>24).sum()),'blur',SC.tolerant_diff(x,y),flush=True)
# I-03 bypass: line fill T beyond [0,1] extends well beyond original object bounding boxes.
a=frame([('1',[(10,20),(20,20)],0,0,[]),('1',[(10,80),(20,80)],0,1,[]),('1',[(30,30),(30,70)],-16776961,2,[])])
r=E.SubElement(a,'FR',Color=str(RED))
for k,t0,t1 in ((0,0,3),(1,3,0)):
 E.SubElement(r,'FS',Kind='0',ObjId=str(1000+k),StartPtId=str(k*10),EndPtId=str(k*10+1),StartT=str(t0),EndT=str(t1))
K.fields(K.encode(sq,a)[0])  # T=3을 포함한 정답 문법 확인
p=copy.deepcopy(a)
for k,o in enumerate(p.findall('AO')):o.set('DrawOrder',str((1,2,0)[k]))
report('extrapolated_fill',p,a)
# I-10 false rejection: AC crosses layers but renderer processes each layer separately.
a=frame([('1',[(20,50),(80,50)],BLACK,0,[(0,10)]),('1',[(50,20),(50,80)],RED,1,[(0,0)])],glow={1})
E.SubElement(a,'LayerDef',ID='1',Visible='true');a.findall('AO')[1].set('LayerId','1');p=copy.deepcopy(a)
for ap in p.iter('AP'):
 for ac in list(ap):ap.remove(ac)
report('cross_layer_link',p,a)
# I-10 false rejection: glow-only strokes have no interleaved visible base layer.
a=frame([('1',[(20,50),(80,50)],0,0,[(0,10)]),('1',[(50,20),(50,80)],0,1,[(0,0)])],glow={0,1})
a.findall('AO')[1].set('GlowColor',str(0xFF0000));p=copy.deepcopy(a)
for ap in p.iter('AP'):
 for ac in list(ap):ap.remove(ac)
report('glow_only_link',p,a)
# E-02: heights may differ in vstack.
print('vstack',np.vstack([np.zeros((270,1440,3),np.uint8),np.zeros((480,1440,3),np.uint8)]).shape)
```

### E. 예비 저장본 성공 뒤 전송 누락

```python
import ast,time,random,types,sys,tempfile,pathlib,shutil,torch
sys.path.insert(0,'tools');import vec_train as VT,pc_seq_run as PC
tr=next(n for n in ast.parse(pathlib.Path('tools/seq_train.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='train');node=next(n for n in tr.body if isinstance(n,ast.FunctionDef) and n.name=='save_ckpt');empty=types.SimpleNamespace(state_dict=lambda:{})
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);ck=root/'ckpt.pt';torch.save({'state':{'step':10,'official_n':1}},ck)
 def save(obj,path,**kw):return False if path==str(ck) else VT.save(obj,path,**kw)
 env=dict(time=time,st={'step':20,'official_n':2},done0=0,active_min=lambda:3.,random=random,torch=torch,dev='cpu',VT=types.SimpleNamespace(save=save),net=empty,opt=empty,scaler=empty,cfg={},ck=str(ck),rate={})
 exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-save>','exec'),env)
 print('save_result',env['save_ckpt'](final=True))
 dst=root/'copy';dst.mkdir()
 # PC final upload/zip exact whitelist; no service is contacted.
 for f in PC.KEEP:
  if (root/f).exists():shutil.copy(root/f,dst/f)
 print('transfer',{'local_main':torch.load(ck,weights_only=False)['state'],'local_fallback':torch.load(str(ck)+'.fallback',weights_only=False)['state'],'transferred':torch.load(dst/'ckpt.pt',weights_only=False)['state'],'fallback_in_KEEP':'ckpt.pt.fallback' in PC.KEEP})
```

### F. PC quick 호출 계약·성공 판정

```python
import tempfile,sys,json,io,contextlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'tools')
import pc_seq_run as PC
for steps in ([0],[5,5],[5,9]):
    calls=[]
    def run(cmd,out):
        calls.append(cmd)
        Path(out,'log.jsonl').write_text(json.dumps({'step':steps[len(calls)-1]})+'\n')
    with tempfile.TemporaryDirectory() as td,patch.object(PC.P,'sh'),          patch.object(PC.P,'keep_awake'),patch.object(PC.P,'run_logged',run),          patch.object(sys,'argv',['pc_seq_run','--root',td,'--quick','--no-stages']),          contextlib.redirect_stdout(io.StringIO()):
        try: PC.main(); status='ok'
        except SystemExit: status='rejected'
    print(steps,status,[all(x in c for x in
          ('--final-reserve-min 0.5','--gen-minutes 0','--val-n 16')) for c in calls])
# [0] rejected / [5,5] rejected / [5,9] ok
# P.sh와 run_logged는 대체하므로 Windows 명령/설치/GPU를 실행하지 않는다.
```

### G. 새 저장 실패 처리·목록 자격·공식 기회 확인

```python
import sys,ast,types,time,random,io,contextlib,torch
from pathlib import Path
sys.path[:0]=['tools','tests']
import seq_train as ST,seq_judge as J
from test_gpt_recheck import _controller
m=J.load_manifest()
meta=dict(manifest_sha=J.manifest_sha(m),entries=m['entries'][:6],
          dirs=J.DIRS,W=640)
assert not ST.judge_list_ok(meta,m)
meta=dict(meta,entries=m['entries'],manifest_sha='wrong-list')
assert not ST.judge_list_ok(meta,m)
tr=next(n for n in ast.parse(Path(ST.__file__).read_text(encoding='utf-8')).body
        if isinstance(n,ast.FunctionDef) and n.name=='train')
n=next(n for n in tr.body if isinstance(n,ast.FunctionDef) and n.name=='save_ckpt')
empty=types.SimpleNamespace(state_dict=lambda:{})
env=dict(time=time,st={'official_n':1},done0=0,active_min=lambda:3.,random=random,
         torch=torch,dev='cpu',VT=types.SimpleNamespace(save=lambda *x,**kw:False),
         net=empty,opt=empty,scaler=empty,cfg={},ck='unused',rate={})
exec(compile(ast.Module(body=[n],type_ignores=[]),'<save>','exec'),env)
assert env['save_ckpt']() is False and 'save' not in env['rate']
try: env['save_ckpt'](final=True)
except SystemExit: print('final save correctly rejected')
else: raise AssertionError('final save was accepted')
run=_controller(); a=run(dict(stage=0,train_min=600,done_min=600,plan_min=600))
b=run(a['saved']); c=run(dict(b['saved'],train_min=780,plan_min=780))
d=run(dict(c['saved'],train_min=900,plan_min=900))
assert a['rec']['judge_official_n']==1
assert b['rec']['judge_official_blocked']=='repeat'
assert c['rec']['judge_official_n']==2
assert d['rec']['judge_official_blocked']=='third'
print('list/official/save checks OK')
```

### H. 상한/최대 길이 평가를 같은 추세 조건으로 취급

```python
import sys
sys.path.insert(0,'tools')
import seq_trend as T
a=dict(judge_N=45,judge_win=0,judge_need=30,judge_delta_median=0,
       judge_w=640,judge_n_entries=46,judge_reduced=False,val_list={'hash':'v'},
       judge_official=False,judge_end={'forced_cap':92})
b=dict(a,judge_win=45,judge_delta_median=95,judge_official=True,judge_end={'eos':92})
print(T.cond(a)==T.cond(b))  # True
print(T.verdict([a,b]))     # 조건 변경 경고 없이 '위치를 더 읽음'
```
