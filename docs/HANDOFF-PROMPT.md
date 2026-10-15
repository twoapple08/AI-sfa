https://github.com/twoapple08/AI-sfa 작업을 이어서 진행해 줘.
최신 HANDOFF.md, AGENTS.md, docs/AOT-ROOT-FLAGS-LAYER-SWAP-TRACE-2026-10-15.md를 읽고 재개해. 과거전체인수인계/원본은필요할때만읽어.

다음은 일반 AO 앞뒤 순서 UI·레이어 이동 현재 프레임 메모리 갱신 → 기능별 정적 확인/실제 앱 검증 필요 항목 정리야. root 수명/moved point·연결 전체/codec 전체/재생 전용 캐시는 미완.
완료추가:storeRoot r=(F>>6)-P,bit4&&0≤r<n이면(r<<6)|(F&0x3f),아니면F&0x2f. 복원B+r대응연결/일반UPDATE로확대금지. storedPointRows는ID/Flags변환후비교·override/removed제외,storeRootPoint도복원/연결변환. point삭제→포함base범위removed표시→재공급제외. GlobalSwap은동일sequence AO.layer_id와현재frame제외layer_def index를임시번호3단계교환,외부현재SaveFrame/전체cacheevict연결. DrawOrder/색/좌표쿼리없음. 새48명령통과/중복합산금지.
완료추가:공유상세현재행우선/removed_detail상속차단/기반행fallback. root로컬raw_flags전체/null fallback,기반점bit4시((B+(F>>6))<<6)|(F&0x3f),아니면F&0x2f,B=FrameBase.field17. 저장역변환은최신root보고서로연결. 공유fill encode/FNV후보길이·전바이트확인→set/ref,읽기는frame키존재시공유반환/없으면로컬. regions기준region+순번/점상대값+기준point/contour별도복원. ID숫자차이만손실판정금지. codec전체형식·t정규화미완. 새55명령대조/기존표본중복합산금지.
완료추가:기본AO행 sequence/type/layer/thickness/DrawOrder비교,DrawOrder≤0 저장후보ID. thickness/objectscale≤0 AO값1보정. holdsDetail ARGB/두배율/glow4값일반동등성비교→필요UpdateDetail. AP selectable bit0/type mask0x2e와raw_flags전체저장별도. 공유fill storeSharedFills조기반환분기,로컬segment contourIndex→9번째DB인수확인. 공유선택전체규칙/재공급미완. 새44명령통과. 최초넓은검색출력잘림후주소창축소,기존시험반복없음.
완료추가:renderable cache는FrameID→Frame/LRU12,수정버전키없음.get remove재삽입/take는remove만/evict는AOmap+AOlist해제.markFrameDataDirty eftrue만,canvasdirty 현재IDevict+notifier. loadDetails는기존객체/take재사용가능,bind는집합밖evict+dirtyfalse. 레이어Up/Down→GlobalSwap+SaveFrame→실제setState closure 전체evict/주변목록비움/canvasdirty→onion/prefetch예약. saveCurrentFrame 정상저장후dirtyfalse/history,자체evict없음. SaveFrame에서changedOnly/replaceFill호출확인,세부저장비교미완. 새62명령통과/중복합산금지.
완료추가:AO→본체unit4f/glowunit53,FR→unit57,모든segment.ObjId→동일ID모든AO위치→followers5b. contour0필터없어hole도전파. 값변경은본체+followers+변경전OR후activeglowunit. active=Radius>0&&GlowAlpha>0.FR색별도자기unit. APFlags비교불일치→새record/plan;groupUI Flags설정해제연결. filltap삭제/새FR+불변복사segments추가,mergeLayerDown sort→evict→dirty→load. 모든UI계약완료아님. 새54명령통과/압축cmpNULL w22정규화,기존표본중복합산금지.
완료:원본hole-combine key는생성steps복사Float64→Int64 bit열,LRU256/반환Path.from복사. nohole은cache미사용,hit도contour계산하고combine생략. 보간fill별도combine. planFor AO목록Expando/구조fits,모든속성검사아님. editor설정/구조검사·색/두께/glow/point snapshot→영향unit집합→기록재생+직접그림/재기록.2D≤U와drag/집합조건구분. 생성의존집합연결완료,일반변경UI계약일부미완. 새65명령대조(압축sturNULL2곳w22정규화),앱시험/pixel검증아님.
기존glow이미지key localgeometry/Wq/Rq/크기양자화·색나중입힘·cache예산은GLOW-BACKEND유지. fillbit key와합치지마. export새recorder/Draw는editorpaint와다름,sharedcache전체미사용단정금지.
이전curve/ring보고서의n1–48/균일t+회전t혼합/중간부호곡률/ring2·4·8node·반폭원래W/2/퇴화radius0·8node/_fill3sigma/cull4sigma유지. group/shader/timeline/EXPORT-DISPATCH완료근거필요부분만참조. FPS=(T트위닝,P재생),OBJECT8/PREVIEW약2.2 Float32정정,기본B재추적금지.

캐시e23c9fd610d3/private/blutter_out/{asm/sfa,pp.txt,ida_script/addNames.py},input/arm64-v8a/libapp.so,venv. shader6d77389e706a/private/glow.frag는binary(전체cat금지),Java같은private/decompiled. 신규curve/ring/cache/dirty검사5a16c98ed7ee/private-trace,현행문서checkout5a16c98ed7ee/AI-sfa-publish. 이전cache/dirtyworktree보존,reset/덮어쓰기금지. 최신head/tree/expected_sha보호. 전체덤프·Blutter/JADX·도구설치·기존00–05/영상재분석반복금지.

환경2026-10-15 08:48–08:49 KST: PC확보(대략i7-8700/GTX1050Ti/RAM16GB),폰Wi-Fi는학교망연결가능하지만제약있음(정확한제약미확인). PC OS/인터넷/USB/ADB준비미확인,현재학교망무선ADB가능가정금지. 지금사용자추가작업없음. 루팅X/Android16·SDK36·ARM64. 별도5APK서명보존/Gadget·Flutter모듈로드완료,license응답4→오류창Close종료/지속렌더계측차단. PC확보로해결단정금지. 우회/검사변경/추가폰명령·설치·페어링·시작시험요청금지.

APK/SFA/영상/역컴파일/assembly/키/전체로그공개금지. 직접작성보고서·집계·인계main반영상시승인. 보호PREVIDEO/File-2최적화/학습/AI연결보류. 문서만변경시기존시험재실행없음. 사용자잔여사용량조회불가. 필요한새증거만검증하고체크포인트저장후인계갱신.
