# Stick Fighter 분석 현황 — GPT·Gemini 공동작업용 설명서 (2026-10-16)

> 이 글은 Claude가 작성했다. 대상은 이 프로젝트에 새로 합류하는 GPT와 Gemini다. 이 글만 읽고도 현재까지의 분석 결과와 근거 수준, 금지사항을 이해할 수 있도록 썼다.
> 저장소: https://github.com/twoapple08/AI-sfa (공개). 세부 근거는 `docs/`의 각 보고서에 있다.

---

## 0. 먼저 지켜 줄 것 (요약)

1. **근거 수준을 섞지 않는다.** 이 프로젝트의 결론은 아래 네 등급 중 하나다. 의견을 낼 때도 어느 등급인지 밝혀 달라.
   - **[실물]** 실제 앱에서 사용자가 조작·저장·영상 출력한 결과로 확인한 것
   - **[정적]** APK의 Java(JADX) 코드나 Flutter AOT 기계어(blutter)를 읽어 확인한 코드 경로
   - **[저장]** `.sfa` 파일 안의 저장값만 보고 확인한 것
   - **[추론]** 위 근거에서 추정한 것. 확정 규칙처럼 쓰지 않는다
2. 사용자 제공 APK, 다른 사용자의 SFA·영상 원본, 역컴파일 소스, 어셈블리 덤프는 **공개하거나 요청하지 않는다.** 이 글에는 수식과 관찰 요약만 있다.
3. FPS는 항상 **(트위닝 FPS, 재생 FPS)** 순서로 적는다. 예: (60,12) = 트위닝 60, 재생 12.
4. Stick Fighter에는 **‘굽힘(bend)’ 기능이 없다** (사용자 정정). 내부 문자열에 비슷한 이름이 있어도 UI 기능으로 보지 않는다.
5. 화면 밖이나 음수 좌표의 도형을 지우거나 0–100으로 clamp/재중앙 정렬하지 않는다. 화면 밖 진입은 의도된 연출일 수 있다.
6. 완성도를 퍼센트로 말하지 않는다. ‘완전 분석’, ‘앱과 동일한 렌더러 완성’ 같은 주장도 하지 않는다. 현재 상태는 **정상 경로 상당 부분의 정적 분석과 제한된 실물 표본**이다.

---

## 1. 프로젝트 목표와 방향 전환

- 최종 목표: **자연어(+태그) 지시 → Stick Fighter에서 열고 편집할 수 있는 `.sfa` 애니메이션 생성.**
- 지금까지의 우선순위: Stick Fighter의 창작·편집 기능 전체를 분석하고, 앱 결과로 검증하는 것.
- **학습 방식은 바꾸기로 했다.** 이전 설계 초안(`docs/LOCAL-AI-DESIGN.md`)의 계획(Sakugabooru 영상 → 포즈 추출 → 로컬 모델 학습, 폰 로컬 실행)은 **더 이상 확정안이 아니다.** 새 학습 방식은 사용자가 따로 설명한다. 그 전에 옛 계획을 전제로 설계를 진행하지 말아 달라.
- 이전 설계에서 앞으로도 유효한 원칙:
  - 언어 모델이 모든 프레임의 XML을 직접 출력하게 하지 않는다. 키포즈·타이밍·경로 같은 **간결한 동작 표현**을 만들고, ID·연결·좌표·저장은 **결정적인 엔진**이 처리한다.
  - 앱의 보간은 대체로 선형이다(§5). 스미어나 임팩트 프레임처럼 의도된 급변은 키프레임으로 직접 넣어야 한다.

---

## 2. 앱 기본 정보

| 항목 | 내용 |
|---|---|
| 앱 | Stick Fighter 51.0.0 (versionCode 51000), 패키지 `com.sG.stickfighter.activities` |
| 구조 | **Flutter 앱**(Dart AOT, `libapp.so`/`libflutter.so`, arm64) + Android Java/Kotlin 부분(dex 3개) |
| 분석 도구 | Java 부분: JADX(일부 함수는 역컴파일 오류가 있음). Dart 부분: blutter로 AOT 기계어·객체 풀(PP)·VM dispatch 표를 복구해 명령 단위로 읽음 |
| 내부 저장 | 앱 안 **SQLite DB**(sequence, frame, animation_object, 점, 상세속성, fill 테이블 등). `.sfa`는 가져오기·내보내기 형식 |
| 영상 출력 | Dart가 프레임을 Picture로 그리고 Java 인코더로 넘긴다 |
| 화면 렌더 | Flutter Canvas. glow는 커스텀 **fragment shader**(`shaders/glow.frag`, 컴파일된 번들)와 raster 캐시, MaskFilter fallback 사용 |
| Android 네이티브 렌더/보간 경로 | Java 쪽에도 렌더러·보간 코드가 있다. **Flutter 경로와 같다고 보장할 수 없다.** 실제 앱 화면·출력이 어느 쪽을 쓰는지 구분해야 한다 |

---

## 3. `.sfa` 파일 형식 [저장]

- `.sfa` = **ZIP 안에 XML 1개.** 확장자 `.sfa.sfa`도 내용은 같다.
- 계층: `Sequence > Frame > (LayerDef, AO > AP/AC, FR > FS, TweenLink)`

| 요소 | 주요 속성 | 의미 |
|---|---|---|
| Sequence | Name, FrameCount, RatioX, RatioY, HeightWidthRatio, BackgroundColor | 작품 전체 |
| Frame | ID, Position(0부터), BackgroundColor | 원본 프레임 |
| LayerDef | ID, Name, Visible, Locked | 레이어. **프레임마다 저장되지만 UI상 레이어는 전체 프레임에 적용**되는 제작 보조층이다 |
| AO | ID, TypeId, Color, LayerId, DrawOrder, ThicknessScale, ObjectScale, Glow* | 도형 하나 |
| AP | ID, Flags, Index, X, Y | 도형의 점. **Index가 보간 대응 키**다. AP.ID와 혼동하지 않는다 |
| AC | ConnPtId | 같은 프레임의 다른 AP와 연결(관절 공유·그룹) |
| FR | Color | 채우기 영역. FR 자체에는 ID가 없다 |
| FS | Kind, ObjId, StartPtId, EndPtId, StartT, EndT, (Contour) | 채우기 경계 조각. Kind0은 점 ID 대신 −1과 0–1 T를 쓰는 부분 경계, Kind1은 ObjId만 있는 원 전체 참조. Contour는 여러 윤곽(구멍) 구분 |
| TweenLink | ID, From | 수동 트위닝 잇기(다른 ID 도형끼리 대응) |

- **TypeId**: 1 = 직선(점 2), 2 = 원(점 2 = 지름 양 끝), 3 = 곡선(점 3, 이차 베지어). 삼각형·사각형은 직선 여러 개와 AC 연결로 만든다.
- **좌표**: X·Y는 출력 화면 너비·높이에 대한 **백분율**. 흰 출력 사각형이 0–100이고 음수 Y는 위쪽이다. 화면 밖 좌표가 허용되며, 편집 공간(회색)에서는 보이지만 영상에서는 잘린다 [실물: 10_screen 시험].
- **색**: 32비트 ARGB(음수 정수로 저장될 수 있음).
- **기본 스틱맨**: AO 10개(원 1 + 직선 9), AP 20개. 관절 하나가 여러 AP 끝점과 AC로 표현된다.
- 같은 도형의 **AO ID는 프레임 사이에 유지되고 AP ID는 바뀐다** → 대응은 AO ID + AP Index로 한다.
- FPS·트위닝 설정은 XML에 없다. 앱 DB(`sequence.fps`, 기본 12 마이그레이션)와 SharedPreferences(`last_project_fps`, `smoothness_` 등)에 있다. 가져오기 후 UI가 (60,12)로 보인 사례가 있었다.
- 실제 대형 작품 규모 예: 프레임당 AO 최대 15,552개, 내부 XML 372MB. 생성기·도구는 **스트리밍 파싱**이 필요하다.

---

## 4. 렌더링 모델

### 4.1 도형·굵기 [정적]
- 원 = 두 점을 지름 양 끝으로 하는 원. 곡선 = 세 점 이차 베지어.
- 기본 선 굵기 배율(네이티브 경로): `max(0.05, sequence.thickness/100 × ThicknessScale)`. glow 경로에서는 ObjectScale도 곱한다. 도형별 최소값과 반올림 보정이 따로 있어서 이 식이 최종 픽셀 폭은 아니다.
- 그리기 순서: DB에서 DrawOrder 오름차순, 같으면 ID 오름차순. 레이어별로 **채우기 → glow → 기본 선**의 별도 패스. 채우기 순서와 AO DrawOrder는 서로 다른 순서 축이다.

### 4.2 채우기·구멍 [정적 + 일부 실물]
- Path는 EVEN_ODD 규칙. FS 조각을 이어 윤곽을 만들고, StartT>EndT이면 방향을 반전한다. 부분 곡선은 T를 0–1로 제한해서 분할한다.
- 실물: 단순 사각형 구멍, 윤곽 방향 반전, FR 목록 순서를 뒤집어도 겹침 결과가 같다는 것을 확인했다.
- 미완: 복잡한 다중 윤곽·부분 경계의 픽셀 재현.

### 4.3 Glow [정적, 수식까지]
- 그룹 glow는 합성된 하나의 효과가 아니라 **객체별 누적 그리기**다. 객체마다 shader → raster 캐시 → MaskFilter 순서로 fallback한다.
- shader는 Gaussian band(오차함수 근사)로 coverage를 계산한다.
  - 직선/곡선 몸통: c=0이면 `B(−u,L−u)×B(−h−v,h−v)`. 곡률 c가 있으면 lo/hi를 1/c로 제한한 보정식(`docs/AOT-GROUP-SHADER-TIMELINE-TRACE-2026-10-15.md` §3).
  - 반원 cap과 ring(원)은 수치 적분으로 계산한다. coverage는 0–1로 제한한 뒤 uColor(사전곱 알파) 전체에 곱한다.
  - uniform: uColor, uA(시작점/원 중심·반경), uB.z = 반폭 h, uB.w = sigma(최소 0.001), uKind(>0.5이면 ring), uCaps, uCounts, uPieces[i](끝점 xy + 곡률).
- glow 강도는 기본 선 알파와 **독립**이다(기본 선 알파 0이어도 glow가 보임) [실물].
- 미완: 곡선·링·연결 그룹 glow의 실제 픽셀과 blend 결과.

---

## 5. 시간축·트위닝 [정적 + 실물 일치]

### 5.1 출력 시간축 (Dart PlaybackEnumeration) [정적]
F = 원본 프레임 수, (T,P) = (트위닝, 재생).

| 항목 | 규칙 |
|---|---|
| 보간 활성 | tweeningEnabled && T > P |
| 출력 FPS Q | 활성이면 T, 아니면 P |
| 단계 K | 활성이면 max(round(Q/P),1), 아니면 1 |
| 출력 수 N | ceil(max(F,0)×Q/P) |
| 원본 시작 a(j) | min(floor(j×P/Q), F−1) |
| 다음 b(j) | min(a+1, F−1) |
| 보간 계수 t | m/K, m = floor(((j×P) mod Q)×K/Q). 구간 첫 출력이거나 a=b이면 0 |

- 마지막 원본 프레임은 **처음으로 루프 보간하지 않고 유지**한다. 예: F=2, (60,12) → t=0,.2,.4,.6,.8 다음 마지막 원본 5회.
- 실물 일치: (60,12)에서 122→610프레임, 90→450프레임. (24,12)에서 120→240, 114→228. (24,24)는 보간 없음.
- 구현: `native_timing.py`(시간축만, 유리수 계산).

### 5.2 도형 보간 [정적 + 일부 실물]
- 앞·뒤 프레임에서 **같은 AO ID**를 찾고, 점은 **Index**로 대응한다. 대응한 점은 X/Y를 선형 보간하고, 대응점이 없으면 앞 좌표를 유지한다.
- ARGB 채널, ObjectScale·ThicknessScale, glow 속성도 보간한다(일부는 정수 반올림).
- **수동 트위닝 잇기(TweenLink)**: ID가 다른 도형끼리 잇는다. 뒤 key 정렬, 자연 ID 충돌, TypeId·같은 위치 Index 검사가 있다 [정적]. 다른 ID의 두 원을 이으면 중간 원이 나타난다 [실물].
- 채우기 보간: 경계 signature/topology로 앞·뒤 FR을 대응한다. 대응이 없는 앞 FR은 유지한다. 부분 T도 분할한다.
- 생성/삭제: ID가 바뀐 도형은 중간 프레임에서 빠질 수 있다. FR 생성과 삭제는 비대칭이다 [실물 표본].
- 주의: 공통 AO가 많다고 중간 프레임이 밝게 이어지는 것은 아니다. 실제 대형 작품에서 공통 AO 대부분이 선 알파 0·glow 알파 0이라 중간 출력이 어두웠던 사례가 있다.

---

## 6. 편집 기능별 분석 상태

| 기능 | 확인 범위 | 남은 것 |
|---|---|---|
| 점·도형 이동, 상세 패널 크기 변형 | pending 일괄 적용, pivot 선택, `c + m(p−c)`, 두 배율 속성 저장·복원 [정적]. 손끝 드래그 + 전체 2배 [실물] | 전체 hit-test, 비정상 연결 |
| 원근 | 8핸들, 시작 snapshot, 사영/쌍선형 선택, 실패 fallback [정적]. 사영 적합·아핀 확대 [실물] | 곡선·원 최종 픽셀 |
| 올가미·올그룹 | 선택 → AllGroup, 상자·레이어 필터, 모서리 확대, 회전 보조 [정적] | UI 전체 |
| 연결·그룹·해제 | AC/Flags 변화, 동반 이동, 해제 후 독립 이동 [실물]. Flags → 구조 갱신, 기반 그룹 참조 상대화·복원, 순환 수리 [정적] | 중첩 그룹 트위닝, 잠금 UI |
| 레이어 | 위·아래 이동, 병합(DrawOrder 슬롯 재배정), 삭제(참조·fill 정리), 추가(전체 프레임), history 초기화 [정적] | 실물 결과, DB 실패 rollback |
| 객체 삭제 | 도구 모드 route, 현재 프레임 대상, 저장·history 연결 [정적] | — |
| 프레임 명령 | 삽입·붙여넣기 전후 위치, clipboard deep snapshot, 같은/다른 sequence 복사, ID·연결·그룹·fill 재매핑, 마지막 프레임 삭제 시 새 frame0 생성 [정적] | 실패 원자성 |
| 프레임 복사의 ID 처리 | root prefix를 절반 이상 공유하면 재사용, 아니면 새 root. ID 예약은 sqlite_sequence 상향. 같은 sequence는 AO ID 유지, 다른 sequence는 새 ID [정적] | — |
| 저장·undo/redo | 프레임별 undo stack, FastHash 비교(Position, FR색, AO ID·색·DrawOrder, 점 round(xy×10000), Flags), 비동기 guard, 프레임 압축(moved run/잔차), unused AO 정리 [정적] | 실제 압축 무손실 증명 |
| 일반 AO 앞뒤 순서 변경·개별 잠금 UI | **미식별** | 새로운 구체 caller가 있을 때만 확인 |
| 내보내기 | (T,P) 시간축, Picture → Java 인코더, 재생 버퍼·clock [정적] | 모든 FPS 조합, 픽셀 동등성 |

‘root/가상 기반’은 앱의 프레임 저장 최적화다. 프레임마다 모든 점을 저장하지 않고 기반(root) 상태와 바뀐 점(moved run, bit residual)만 저장한다. `.sfa`로 내보낼 때는 프레임마다 완전한 AO/AP가 풀려 나온다 [저장].

---

## 7. 실물 검증 이력 [실물]

- 01–03: 채우기·순서·glow·생성/삭제 시험. 984 출력 프레임 측정.
- 04–05: 그룹/해제, 크기, 원근, 수동 트위닝 잇기를 실제 UI로 조작.
- 10_screen: 화면 밖 도형은 편집 공간에서는 보이지만 영상에서는 잘린다.
- 실제 사용자 작품 4개(일반 2, 대형 2)의 영상 비교: 시간축은 일치. 중간 출력의 어두운 구간은 알파 0 도형 때문.
- 계측 앱(Frida gadget)은 로드에 성공했지만 Play 라이선스 응답(4) 때문에 계속 편집할 수 없었다. **라이선스 우회는 하지 않는다.**

---

## 8. 저장소 도구

| 파일 | 기능 |
|---|---|
| `sfa.py` | inspect / validate / roundtrip(모르는 요소 보존) / wave(기본 스틱맨 팔 흔들기) / preview(HTML 근사 미리보기, 트위닝 미계산) |
| `native_timing.py` | (T,P) 출력 시간축 계산 |
| `build_feature_probes.py` | 기능 시험용 SFA 합본 생성 |
| `tools/audit_sfa_boundaries.py` | 대형 SFA 프레임 경계 집계(좌표 비출력) |
| 테스트 | `python -m unittest discover -s tests -v` |

Python 표준 라이브러리만 쓴다. API 키는 필요 없다.

---

## 9. 아직 모르는 것

1. 실제 앱의 픽셀 결과: 곡선·링·그룹 glow 합성, 복잡한 채우기, 기기 코덱·색.
2. 일반 AO 앞뒤 순서 변경 UI와 개별 잠금 UI의 존재·위치.
3. 비정상 입력(손상된 codec, overflow, 동시 DB 변경)에서의 동작과 오류 원자성.
4. 전체 UI coverage. 지금까지 확인한 것은 주요 기능의 정상 경로다.
5. 가져오기 직후 FPS·기본 굵기 초기값이 정해지는 정확한 경로.

현재 서버는 x86_64이고 Android 에뮬레이터가 없다. 사용자 PC도 지금은 쓸 수 없어서 새 실물·픽셀 검증은 보류 중이다.

---

## 10. 공동작업 요청

- 제안할 때는 **근거 등급**과 **확인 방법**을 함께 적어 달라.
- 이 글과 모순되는 주장이 있다면 어느 항목과 어떻게 다른지, 근거가 무엇인지 밝혀 달라.
- 생성기 설계 의견은 §3 형식 규칙(AO ID 유지, AP Index 대응, AC 연결, 백분율 좌표, 화면 밖 허용)과 §5 시간축·보간 규칙을 지키는 방향이면 바로 쓸 수 있다.
- 새 학습 방식에 대한 설명은 사용자가 별도로 전달한다.
