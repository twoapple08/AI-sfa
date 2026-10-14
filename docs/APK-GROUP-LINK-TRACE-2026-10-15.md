# 그룹 Flags의 참조 인코딩과 수동 링크 경로의 경계

## 새로 확인한 내용

04의그룹저장값을기존APK와대조해큰Flags값의참조인코딩을확인했다. **bit16(0x10)이설정된이표본에서 `Flags >> 6`은그룹기준점ID**이고,하위6비트는옵션비트를보존한다. 그룹이름이나색이 아니라점참조다. 숫자Flags를불투명한상수로복사하거나ID만재할당하면이참조를깨뜨릴수있다. 현재는분석근거만추가하며생성기/최적화기수정은없다.

기존캐시 `/workspace/scratch/6d77389e706a/private/`가존재했고재다운로드/재역컴파일하지않았다. libapp.so SHA-256은기존기록과같은 `35ce3936f08e5da6caf08e0f3d4c80e0c81777475ac4f682c66f9f4a00a32c1f`. Java자료를Flutter전체소스로해석하지않는다. 아래ELF오프셋은SQL/문자열위치이며실행함수주소가아니다.

## Flags — 실제 SFA와 독립 정적 근거

| 상태 | 위선Index0 ID | 아래선Index0 Flags | 해석 |
|---|---:|---:|---|
|grouped|1462471|93598163|`(1462471 << 6) \| 16 \| 3`와정확히동일|
|grouped_move|1462471|93598163|그룹동반이동후참조유지|
|baseline / ungrouped|해당파일의독립점ID|3|0x10없음,상위참조없음|

93598163의하위6비트는19(0x13),상위값은1462471이다. 아래점에는위점을향하는AC도있고위점에는아래점을향하는AC가있다. ‘Flags의그룹값이임의로큰상수’라는해석을벗어나지만,Flags와AC중어느조건을어떤UI연산이우선읽는지는아직모른다. 단순숫자식일치뿐아니라다음APK SQL과독립적으로부합한다.

| libapp.so 파일오프셋 | 직접 관찰한 SQL의 의미 |
|---|---|
|0x2d16d|점복사/삽입문은0x10이켜졌을때상위참조에파라미터오프셋을더한뒤6비트왼쪽이동,하위6비트보존. 꺼졌을때마스크47(0x2f) 적용|
|0x357a3 / 0xa781e|root/파생점조회 UNION에서도동일참조재매핑식. 파생점ID재구성과기준참조를따로계산|
|0x9fad7|범위내참조일때상위참조에서기준ID를빼고하위6비트보존. 범위밖/플래그미설정분기는0x2f마스크|

이식들은‘상위값을점ID공간에맞춰재매핑하는표현’임을강하게뒷받침한다. 해당SQL호출부/파라미터역할/실행상황을끝까지연결한것은아니다. 모든Flags상위비트가언제나그룹리더ID라는규칙이나0x2f의모든개별비트의미는확정하지않는다.

검증: grouped와grouped_move두상태에서ID압축식assert통과,baseline/ungrouped의Flags3복원assert통과. 기존11SFA구조검사와05영상96장검사는반복하지않았다.

## TweenLink — 저장·실제출력과네이티브함수를구분

05의Frame13 TweenLink는뒤AO를ID,앞AO를From으로저장하고실제중간원출력에영향을준다(별도UI보고서). Flutter AOT에는다음근거가있다.

| 위치 | 의미 |
|---|---|
|0xa8f8a|frame_tween_link테이블: frame_id / animation_object_id / from_animation_object_id,기본키(frame_id,animation_object_id)|
|0x57b76|프레임ID로대상AO/앞AO를조회하는SQL|
|0x8f7c3|프레임/대상AO/앞AO3값을삽입하는SQL|
|0x2b058 / 0x772c8|resolveTweenLinks / appendTweenLinksXml이름|
|0x33181 / 0x4ee21 / 0x665eb|UI드래그종료/시작/갱신이름. 이름만으로호출관계확정금지|

반면읽은네이티브`Y2.i.d`의두도형대응분기는뒤프레임map에앞도형의**같은AOID**로조회한다(약87–89/110–112행). `X2.a`/`Y2`에서frame_tween_link/TweenLink/from_animation_object_id를참조하는저장/로드코드는찾지못했다. 이범위의Java로더는raw_flags대신selectable과anchor_point_type를OR하여점Flags를만든다(X2.a약266/410행).

따라서읽은같은ID매칭분기만으로는05의다른ID링크효과를설명할수없다. 실제출력이다른렌더경로를쓰거나상위단계에서링크를해결하는가능성등이남는다. **05가Flutter렌더러라는실행경로를단정한것은아니다**. 읽은네이티브함수만으로05결과를설명할수없는경계를확인했다.

## DrawOrder / ObjectScale의원인추적은진행중

네이티브X2.a약150/381행은DB도형을draw_order→ID오름차순으로읽고,약190/389–390행은detail의thickness_scale/object_scale를구분해읽는다. AOT에는resolveDrawOrder(0x6dab5),compareDrawOrder(0x4a33b),importSequenceXmlText(0x61337),XML속성ObjectScale(0xa7579)와DrawOrder(0xa1db0)가있다.

그러나문자열발견만으로01순위변경/02ObjectScale2→1의정확한발생함수를확정할수없다. SFA가져오기·내부정규화·재내보내기의경계를계속추적한다. FR배치키도미확인으로유지한다.

## 다음 단계와 토큰 절약 지침

이제원본다운로드/역컴파일대신검증된캐시의AOT함수/상수참조를연결하는작업이필요하다. 사전에코드복원도구의호환성·입력·로컬가용성을확인하고,효과가없을가능성이큰전체덤프/재처리를반복하지않는다. 자료가부족하면부족한함수경계를기록하고전체앱완료로확대하지않는다. 기존시험재출력/제작자문의는요청하지않는다. 고정예측/File-2최적화/학습/AI연결계속보류.
