https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘.
최신 HANDOFF.md, AGENTS.md, docs/AOT-PATH-TRACE-2026-10-15.md를 읽어. 이미 읽은 자료/기존 시험을 불필요하게 재처리하지 마.
Blutter Dart3.12.0 ARM64 스파51.0.0 AOT 추출 성공(671파일/asm666개/선언12,752개), 원래 Dart 소스 복원 아님. 캐시 /workspace/scratch/e23c9fd610d3/private/blutter_out/asm/sfa 재사용. 새11명령 실물ELF/Capstone 대조 통과(기존4와별도);전체해석 검증 아님.
importer는 XML DrawOrder/ObjectScale을 조회하지 않아 새ID순서/ObjectScale1이 되는 원인 확인. planner는 레이어·연결그룹 glow unit→각AO FR+base unit. FR outerSegments참조/레이어/소비집합이 배치에 관여. GlowAlpha로색알파교체·RGB사전알파·shader/raster/MaskFilter fallback 확인. TweenLink는존재/같은TypeId/점목록길이·Index/중복·잔존ID충돌 검사. 일부표본을모든조건으로일반화하지마.
다음은GetAnimationObjects 로드·캐시공급순서와비연속그룹방문순서→TryDrawGlowWithShader(0x425458) paint배율·blend 실제값→_planFillRegions(0x62ff78)/renameTweenLinkedFill·canonicalize·held/interpolated/discard·색정책을필요한함수만추적해. compareDrawOrder closure는_mergeLayerDown 소속이며planner 공통규칙이라고가정금지. 함수코드주소와옛ELF문자열오프셋구분.
설치/빌드/전체덤프/기존00–05자료분석반복금지. reFlutter dump엔진태그404로변경APK/dump미생성,자체engine빌드/Android환경/분할서명미완. 굽힘기능없음. 04Flags의bit16/상위기준점ID압축확인.05원대원다른ID수동링크확인.
기존시험재출력·제작자문의·추가작품요청없음. 고정PREVIDEO예측수정·File-2최적화·학습·AI연결계속보류. APK/SFA/영상/역컴파일소스공개금지. FPS는(트위닝,재생),레이어전체프레임제작보조,편집공간과출력범위구분. 정확도를유지하며토큰낭비를줄이고필요하면자율적으로인수인계갱신해.
