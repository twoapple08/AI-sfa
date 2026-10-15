https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘.
최신 HANDOFF.md와 AGENTS.md, docs/FEATURE-EVIDENCE-MATRIX-2026-10-15.md를 읽고 재개해.

현행 정적 체크포인트는 docs/AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md다.
2026-10-15 15:15 KST 세션은 실행 환경 unavailable/터미널 없음으로 신규 AOT·ELF 추적이 막혔다. 캐시 유실·손상을 확인한 것은 아니다. GitHub 문서 기반으로 기존 실제 표본과 정적 근거를 기능표에 분류했고 새 기능 테스트/영상 재분석/명령 검증은 하지 않았다.

환경이 사용 가능하면 먼저 기존 캐시 경로만 확인해 재사용해. 다음은:
1. _moveSelectedLayer 0x5bc818와 UpdateLayerSelectionAfterMove 0x5bd12c에서 현재 프레임 메모리의 미확인 변경만 추적.
2. 일반 AO 앞뒤 순서 UI의 존재·dispatch 식별. UpdateAnimationObjectDrawOrder라는 이름만으로 UI를 확정하지 마. 기존0x50ce1c는 객체 생성 경로라 일반 순서 UI의 증거가 아니야.
3. 새 근거만 추가하고 실제 앱 검증 필요 항목과 구분.

완료된 핵심은 기능표/최신 보고서를 재사용해. 기반 그룹 참조 저장 r=(F>>6)-P와 복원 B+r, point override/removed 제외, 공유 fill의 상대 point/contour 복원, 동일 sequence의 레이어 번호 교환과 SaveFrame/cache eviction 연결은 이미 확인했어. DB helper와 기존 shader/timeline/FPS를 다시 분석하지 마.
미완은 현재 프레임의 layer 메모리 변경, 일반 AO 순서 UI, root 수명/moved point·연결 전체, codec 전체, 재생 전용 캐시야.
01–05 실제 앱 표본이 일부 있어. ‘모든 실제 테스트 없음’으로 쓰지 마. 반대 DrawOrder 지정 시험은 왕복 중 값이 바뀌어 의도한 시험이 불성립했고, 04 UI ObjectScale2는 보존됐어. ‘굽힘’은 없는 기능이라는 정정 유지.

캐시: /workspace/scratch/e23c9fd610d3/private/{blutter_out,input/arm64-v8a/libapp.so,venv}. 현행 문서 checkout /workspace/scratch/5a16c98ed7ee/AI-sfa-publish, 비공개 검사 ../private-trace. 이전 dirty worktree 보존/reset 금지. shader6d77389e706a/private/glow.frag는 binary이므로 전체cat 금지.
GitHub 최신 head/tree 확인 및 expected_sha 보호. 직접 작성 보고서·집계·인계 main 반영은 상시 승인돼 있어. 원본 APK/SFA/영상/역컴파일·assembly/키/전체로그 공개 금지. 문서 변경만으로 기존 unit/probe 재실행 금지.

PC i7-8700/GTX1050Ti/RAM16GB 확보, 폰 Wi-Fi는 학교망 제약 있음. PC OS/인터넷/USB·ADB 미확인. 이전 무선 ADB 사용 가능을 현재도 가정하지 마. 계측 APK의 Gadget/Flutter 로드는 됐지만 license응답4로 지속 편집 차단. 이번 분석 환경 장애와 별개야. 설치·페어링·휴대폰 시작 시험·기존 영상 분석을 반복하거나 요청하지 마.
PREVIDEO 고정 예측/File-2 보호/학습·AI 연결 보류 유지. 사용자 잔여 사용량은 직접 조회 불가.
