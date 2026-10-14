# AOT Paint 굵기 정정·변경·복원·호출 경로 — 2026-10-15

기존 AOT/PP/ELF 캐시만 재사용했다. 실제 UI/픽셀 실행검증이 아니라 읽은 경로의 정적 분석이다. 새명령표본14개 및 PP Float32 해석을 검증했다. 기존시험/추출/도구설치/휴대폰작업은반복하지않았다.

## 1. 중요 정정: 초기 strokeWidth는 0이 아니다

앞선 AOT-RENDER-CONTEXT 보고서에서 OBJECT/PREVIEW Paint의초기strokeWidth를0으로읽고공급미해결로기록한것은 잘못이었다. Blutter의요약주석 'd0=0.000000'만읽었으며바로아래명령/리터럴의실제폭을연결하지못했다.

원본명령과PP리터럴:

| Paint | scalar load/store | PP 원시32비트 | IEEE754 Float32 값 |
|---|---|---|---|
| OBJECT_PAINT | 0x42d6c8 ldr s0 →0x42d6cc str s0 | pp+0x11d28:0x41000000 | 8.0 |
| PREVIEW_OBJECT_PAINT | 0x42d778 ldr s0 →0x42d77c str s0 | pp+0x11d30:0x400ccccd | 2.200000047683716 |

scalar s0는Float32이며d0요약을Double수치로오독하면안된다. 일반B=8,previewB≈2.2가실제초기화식이다. PP원시메타데이터→struct Float32해석과ELF의load/store명령폭을연결했다. runtime Paint값을직접로그로읽은것은아니다.

paddinghelper기본인수8과일반Paint초기8은숫자가같지만다른공급근거다. 앞선'여백8을실제B로임의대입하지말자'는방법지침은유지하며,'초기0/비영값공급경로미해결'은이체크포인트로정정한다. 원본역컴파일/메타데이터를고치지않고직접작성보고서만정정했다.

## 2. FrameDrawPlan의 선택과 실제 호출자 범위

BuildDrawPlan(0x42b910)은 isPreview=false면OBJECT_PAINT, true면PREVIEW_OBJECT_PAINT를plan.field_f에보관하고drawUnit에서사용한다. 기존Frame자료의값을실행중바꿔버리는영구UI설정과별도다.

확인한공급자:
- EditorFrameCache._FrameRecord(0x4291b4)의0x42926c는named isPreview없이지금Frame.BuildDrawPlan을호출한다. 기본false이므로일반B8이다.
- FrameDrawPlanCache.planFor(0x51743c)의0x5174cc도기본false. ViewSequence.RecordPicture(0x516dc0)는0x5172b4에서이캐시를얻고Frame.Draw에넘긴다.
- renderSequenceActionFramePicture(0x4cf91c)는usePreviewPaint가생략되면false(0x4cf9f4)이고그값을Frame.Draw의isPreview로전달한다(0x4d0064–0x4d0098). true인호출은previewB≈2.2선택이가능하다.
- Frame.Draw(0x791c9c)는plan이없으면옵션으로BuildDrawPlan,있으면그plan을사용한뒤drawUnit을순회한다.

따라서'편집화면은전부preview2.2/출력은전부8'이라는결론은틀릴수있다. isPreview의구체호출값/캐시상태를따라야한다. 보간객체의 _drawLayerObjects/_drawCompositeObjectGlow에는OBJECT_PAINT를직접읽는경로도있다(0x793374/0x7967f8). 모든preview옵션의보간투과여부와사용자영상dispatch를이번에실물검증한것은아니다.

## 3. 일반 객체: 폭과 cap/join을 변경 후 정상 반환에서 복원

AnimationObject.DrawBaseObject(0x4150b8)는SetPaintThickness(0x4152bc)를호출해입력PaintB에현재sequence비율S,객체ThicknessScale T,DPR D를적용한다.

w = B × max(S×T,0) / D.

SetPaintThickness는이전B를double로반환한다. 새폭이양수가아니면원래B를복원하고return(0x415154–0x41516c). 양수면기존StrokeCap/Join을저장하고임시값1을설정한뒤AO종류의DrawObject로동적dispatch한다. 끝에서B/cap/join을복원한다(0x415248–0x41528c).

이는객체간배율이순차누적되지않도록하는정상경로다. 이함수에전체예외finally가있다고주장하지않는다. 가상dispatch의GDT슬롯번호만으로다른클래스의같은슬롯함수이름을붙이지않는다.

## 4. primitive는 기본 w에 화면 반올림 보정을 더한다

Line.DrawObject(0x791a44)와Curve.DrawObject(0x791660)는StabilizeCurvedStrokeWidth(0x43f6a0)를호출한다. 함수이름의'Curved'만보고곡선전용이라판정하면안된다. Circle.DrawObject(0x7912f8)는StabilizeCircleStrokeWidth(0x43f730)에배율1.14를전달한다.

이읽은보정경로에서실제stroke폭은 `round(1.14×w×D)/D`다. 각primitive는그폭을임시로쓰고이전폭을다시저장하는경로가있다. filled/stroke/type별전체분기·모든pixel AA동작은별도확인범위다.

이전여백계산의circle배율1.24는여백helper용이고이actual Circle.DrawObject의1.14와구분한다. 일반B8도최종stroke가항상8이라는뜻은아니다. 예를들어정상양수S=T=D=1이고이보정분기를사용하면기본w8→round9.12=9,preview의경우w약2.2→round2.508…=3이다. 이는코드식의계산예시이며새실물측정이아니다.

글로우W는입력Paint B와GlowThickness로계산하는별도경로다. 따라서'최종기본선반올림폭×GlowThickness/10'로글로우W를대체하면안된다.

## 5. 보간 객체의 변경·복원

InterpolatedAnimationObject.DrawBaseObject(0x7935a4)는원래Float32폭비트/색을저장하고보간ThicknessScale에대해같은B×max(S×T,0)/D를계산한다. 양수인경우보간Color/새폭을Paint에넣고DrawGeometry를호출한다. 정상끝에서폭의원래Float32비트를그대로복원하고색도복원한다(0x7937e0/0x7937ec).

DrawGeometry의원/곡선/선보정호출은확인했다(0x793af4/0x793e04/0x7940ac). 원은1.14를전달한다. branch별temporary폭저장/복원도있다. rawFloat32비트저장과fcvt로계산한double저장을같은값표현으로취급하지않는다.

보간DrawGlowEffect는입력Paint의상태를임시로바꾸며shader/cull/raster/fallback의여러종료경로에서_restorePaint(0x797bd8)를호출한다. 이helper는mask관련바이트슬롯을0으로만들고width/color/style/cap/join/blend및보존된object/filter참조를복원하는경로다. 임의기존maskFilter와모든예외까지원상복구를보장한다는주장은하지않는다. 원본AO의공용GLOW_PAINT사용과보간AO의입력Paint임시변경을같은구현으로합치지않는다.

## 6. 현재 출력 dispatch 연결과 한계

직접읽은연결은 다음과 같다.
- Frame.Draw → FrameDrawPlan.drawUnit →그룹Glow또는FR/DrawBaseObject.
- EditorFrameCache._record(0x414ba4)는NativePictureRecorder/Canvas를만들고각unit.drawUnit(0x414d64)을기록한다. 이후 _drawWithRecordings로재사용하는경로가있다.
- ViewSequence.RecordPicture는clipRect/배경/planFor/Draw/endRecording으로연결된다.
- export _recordExportPicture의동기closure는DPR1범위에서NativePictureRecorder/Canvas/배경/동적Draw/endRecording. 이후toImage/toByteData로연결된다.

이들은Dart측Picture기록경로다. Android쪽영상인코더와의연결,optimized/native대체경로의최종선택,사용자영상이확인한어느경로를썼는지는아직미확인이다. NativeCanvas FFI라는이름만으로앱의Java네이티브renderer와동일하다고판정하면안된다.

## 검증·다음 작업

신규명령표본14개를ELF PT_LOAD/Capstone과대조해통과했고,초기폭PP리터럴2개의IEEE754Float32값을검증했다. audit:AOT-PAINT-DISPATCH-AUDIT-2026-10-15.json. 기존다른14/원본/unit/probe시험을재실행하지않았다. 명령/메타데이터검증은전체함수의미/실물픽셀확정이아니다.

다음은shader load lifecycle→프로그램준비/Style gate→raster cache 생성/hit/단위조건→MaskFilter fallback의구체선택을연결한다. 그다음export optimized/native encoder dispatch를필요부분만연결한다. 요청된전체기능분석은계속진행중이며실기기렌더계측은기존라이선스차단상태다. 휴대폰추가명령/설치/Play설정요청없음.

캐시:e23c9fd610d3/private/blutter_out/asm/sfa/original_port/sequences/{animation_object,interpolated_animation_object,line,circle,curve}.dart,editor/editor_frame_cache.dart,pp.txt,ELF/venv.새검사25b8ca176661/private-trace/{validate_paint.py,paint-validation.json}.공개는직접작성해석/집계만.앞선Float32오독은AGENTS와기존보고서에정정.
