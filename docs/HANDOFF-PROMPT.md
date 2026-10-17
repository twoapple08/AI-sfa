https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘. 작업 브랜치는 `ccr-bccf15a6-d6ee46`이다(필요하면 fetch 후 이 브랜치에서 계속).
AGENTS.md → HANDOFF.md → docs/STYLE-LEARNING-PLAN-2026-10-16.md('현재 상태' 절) → docs/STYLE-KB-ROOTS-2026-10-16.md 순서로 읽는다. 후보는 필요할 때만 docs/ARTIST-CANDIDATES-2026-10-16.md.

현재 우선순위: (나) 분석형 스타일 학습. 뿌리 yutaka_nakamura(이펙트·배경·연출)·nian41(**사람 몸 움직임만**; 표정 같은 그림체·머리카락·이펙트·연출은 학습 제외, 옷자락은 확인 대기). nian41 몸 움직임은 docs/NIAN41-BODY-MOTION-2026-10-17.md. 추가 작가는 사용자 승낙 후에만(1차 후보 6명 승낙/반려 대기). 개인 사용. 추가 지출은 가성비가 매우 좋을 때만.

2026-10-17 완료 [실측]:
- rclone v1.75.2 설치(SHA256 대조), 환경 변수 RCLONE_CONFIG_GDRIVE_{TYPE,SCOPE,TOKEN}로 `gdrive:` 연결. 공용 client_id 폐지 예정 경고 있음 → 인증 오류가 나면 개인 client_id 생성 안내.
- Drive `AI-sfa/{00_목록,01_원본영상,02_분석자료,03_스타일지식베이스,04_SFA시험작}` 생성. 00=catalog.csv, 02=<post_id>/{timing.json,contact_sheet.jpg} 55개, 03=지식베이스 문서·observations.jsonl.
- nian41 36클립 전부 분석(완성본 24 + 색 지정 레이아웃 제작자료 12), yutaka_nakamura 확정 표기 완성본 점수 상위 20클립 추가(누적 28). observations.jsonl 64건, catalog analyzed 64. 지식베이스 v1(D 캐릭터, E 제작자료, F yutaka 확장 절).

차단:
- 01 원본 수집(`tools/sakuga_collect.py`, Drive 직접 스트리밍 + md5 대조)은 Claude Code 자동 승인 검토에서 거부됐다(사유 미표시). 우회하지 않는다. 사용자가 명시 허용하거나 권한 규칙을 추가하면 `python tools/sakuga_collect.py data/catalog.csv --limit 2`로 시험 후 전체(404개, 약 3.9GB) 진행.
- 분석용 임시 다운로드(받아서 측정 후 즉시 삭제)는 허용됐다.

2026-10-17 후반:
- nian41 학습 범위 축소 반영(KB D절·부록, observations.jsonl `learn_scope`). 몸 움직임 v1: 인물 색 마스크 측정으로 '몸 그림은 2s 기본 + 순간 1s'로 정정, 예비→순간→후속, 스미어 형태 정리(`tools/sakuga_timing.py --run` 연속 프레임 시트 추가).
- GPT 분담(2026-10-17 사용자 변경): 공개된 yutaka_nakamura 자료 전부 수집 → 분석 진행. 지시서 docs/GPT-TASK-YUTAKA-SOURCES(1순위)·GPT-TASK-YUTAKA-EFFECTS(분석 형식). 이전 안: yutaka 다음 30클립(점수순 21–50위) contact sheet·timing·작업목록 CSV를 Drive 02에 올림. GPT 결과(JSONL)가 오면 몇 클립을 직접 대조한 뒤 KB에 'GPT 시각 판독'으로 합친다. 이 30개는 Claude가 중복 분석하지 않는다.

- 자료 출처 조사(사용자 공통 지시: Claude=nian41, GPT=yutaka_nakamura): docs/NIAN41-SOURCES-2026-10-17.md, data/sources/nian41_sources.csv. 핵심 A등급=본인 Bilibili lo 업로드(JJK S3#09 虎杖vs日車, BV1A9PyzfExr). Bilibili 목록은 비로그인 위험 제어로 차단(우회 안 함). GPT용 지시서 docs/GPT-TASK-YUTAKA-SOURCES-2026-10-17.md.

- 사용자 제공 nian41 X 영상 12개(본인 게시, 담당 명시) 메타데이터·타이밍·시트 확보. Sakugabooru 제작자료 9개+216085+301142가 본인 그린 부분으로 확정(observations `proof`). 영상 원본은 서버 임시 폴더뿐 — Drive 01 저장은 자동 승인 거부(2회째, 'Auto-Mode Bypass')로 사용자 권한 설정 대기.

- Gemini 합류: docs/GEMINI-PASTE-2026-10-17.md(붙여 넣기용 현행 요약). Gemini 몫=후보 6명 평가 + nian41 몸 움직임 규칙 교차 검증. 결과가 오면 대조 후 병합.

- GPT 진행(2026-10-17 사용자 보고): yutaka_nakamura 원본을 직접 내려받아 검증하고 90MiB 이하 독립 ZIP 42개로 Drive에 올리는 중. 서버 rclone은 drive.file 범위라 GPT 파일이 **보이지 않는다**(정상). 받는 법: GPT 폴더를 '링크가 있는 모든 사용자-뷰어'로 공유받아 공개 다운로드하거나, GPT가 CSV/JSONL을 텍스트로 붙여 넣게 한다. yutaka 원본은 Claude가 중복 수집하지 않는다.
- 미완: nian41 본인 작화 3개(X 1913589758644908348 초능입방 원화3, 1943223713455051062 곤탄천하, 1613887197383622656 PF1) 마스크 측정은 끝(1s 35–52%, 2s 24–31%), 연속 프레임 판독은 미착수. 컬러 완성본·이펙트색이 섞여 수치 신뢰도는 280544보다 낮음.

- GPT 결과 1차 확인: docs/GPT-RESULTS-CHECK-2026-10-17.md. 사용자가 Drive AI-sfa 폴더를 링크 공개(https://drive.google.com/drive/folders/1M8Fk05crDvs42R9Eqt7FdJv2fPSiX8Xy)로 바꿔 embeddedfolderview·drive.usercontent 공개 다운로드로 확인 가능. ZIP 32개(진행 중), 표본 2개 무결성·md5 일치.

- 사용자 지시(2026-10-17, GPT에도 전달됨): (1) **최중요** impact_frames는 4B 연필로 직접 그린 느낌만 학습, 디지털 단색 느낌 제외. (2) yutaka 구작·최신작 비교 — 양쪽 모두에 있는 방식(yutapon_cubes 등) 중요도 상향. (3) 에반게리온 제외. KB 상단 '학습 범위' 참조. 기존 임팩트 관찰은 아직 연필/디지털 미분류.
- 계획(담당 미정): GPT 업로드가 끝나면 Drive 원본의 중복·오류·누락 점검(ZIP manifest md5 대조, catalog 대비 누락, 같은 장면 다른 인코딩 중복).

- **조정 권한은 Claude(사용자 지시).** 현재 배정: docs/COORDINATION-2026-10-17.md. GPT=nian41 원본 보관(Claude 업로드 차단 대체)·yutaka 외부 7개 검토·yutaka 분석 계속(최근작부터, era·old_new_common)·impact 분류. Claude=GPT 30건 교차 판독·병합, nian41 몸 움직임, 결과 통합. Gemini=후보 평가·nian41 규칙 검증.
- 메타데이터 감사 완료: GPT manifest 368 ↔ catalog 368, 누락·md5 불일치·중복 0. parent_id 장면 중복 71건(삭제 안 함, 한 장면으로 계산).

다음 할 일:
1. 01 수집 허용 여부를 사용자에게 확인(허용 시 위 순서).
2. (GPT 결과 대기 중이면) nian41 몸 움직임 표본 확대: 다른 제작자료(280833·280835·287139 등)에 마스크 측정·연속 시트 적용, 280830 원화 번호 계수. yutaka 나머지: 확정 표기 완성본 영상 159개 중 GPT 30개를 뺀 129개를 점수순으로(다음 묶음은 /tmp 스크립트 없이 같은 방식 재작성: 미분석·비presumed·비제작자료·mp4/webm을 score 내림차순). 이후 presumed 56개, 제작자료 76개. 임시 다운로드 → tools/sakuga_timing.py → contact sheet 판독 → observations.jsonl·KB 갱신 → Drive 02/03·catalog 동기화 → 클립 삭제.
3. 280830 원화 번호로 키 포즈 간격 측정.
4. 후보 승낙/반려가 오면 해당 작가 색인·분석.

규칙: 토큰·키를 채팅/로그/커밋에 출력하지 않는다. 영상 원본·contact sheet는 GitHub에 올리지 않는다(contact sheet는 Drive 02에만). 근거 등급([실측]/[추론]/[실물])을 구분한다. 출처가 "SB/ED"인 클립은 콘티·연출 근거로만 쓰고 작화 필치를 단정하지 않는다. FPS는 (트위닝,재생). 혼자 가능한 일은 자율 진행.
