# 공유 채우기·이동 점 codec 표현 — 2026-10-15

SHARED-RESTORE의 읽기/저장 호출에 이어 기존 AOT의 codec 본문을 확인했다. DB 내부 표현이며 외부 .sfa 형식 전체와 동일하다는 뜻이 아니다. 원본 파일/assembly를 공개하거나 기존 파일을 재압축하지 않았다.

## 공유 채우기 payload

FillSetCodec._encode(0x332af4)는 아래 순서의 바이트를 만든 뒤 ZLibCodec으로 압축한다. _decode(0x3345ec)는 압축을 풀고 첫 바이트1을 확인한다. 첫 바이트가 없거나 버전이 다르면 FormatException 경로다.

U는 하위7비트씩, 뒤에 데이터가 있으면 bit7을 켜는 unsigned varint다. S는 signed 정수를 `(n<<1) XOR (n>>63)`로 바꿔 U로 기록하는 ZigZag다. decoder는 `(u>>>1) XOR −(u&1)`로 복원한다. 실행 정수폭·오류는 아래 제한을 따른다.

| 순서 | 내용 | 표현 |
|---|---|---|
| 1 | 버전 | byte1 |
| 2 | region 개수 | U |
| 3 | 각 region의 ARGB | S |
| 4 | 그 region의 segment 수 | U |
| 5 | 각 segment kind index | U |
| 6 | AO 참조 ID | S |
| 7 | contour index | U |
| 8 | edge의 optional presence | byte, 아래 bit표 |
| 9 | 있는 start/end 점 상대값 | 각각 S, start→end |
| 10 | 있는 start/end t | 각각 Float64 little endian, start→end |

kind0은 edge, kind1은 circle이다(기존 enum 객체 metadata 확인). circle은 kind/AO/contour까지만 기록하고 optional 부분을 쓰지 않는다(0x333328). edge optional presence는 bit0=start 점, bit1=end 점, bit2=start t, bit3=end t다. 네 필드의 nullable 여부로 조합한다. t는 8바이트 ByteData에 실제 str dN으로 쓰고 decoder도 ldr dN으로 읽는다. Float32나 소수 문자열이 아니다.

region/segment 목록 순서가 payload 순서다. 이 encode 본문에 geometry 기준 정렬은 없다. hash 동등성 비교·공유 set 재사용은 SHARED-RESTORE 보고서를 재사용한다.

## t와 점 참조 정규화

_StoredSegment.of(0x35a924)의 edge 분기는 start/end 점 ID가 음수이면 null, 아니면 first point ID를 뺀 상대값으로 만든다. t가 NaN이면 null로 바꾸며, 0과 같은 값은 +0으로 정규화한다. t의 일반 범위 clamp나 모든 nonfinite 제거를 수행하는 코드는 이 구간에 없다. 즉 infinity를 NaN과 같은 취급으로 확대하면 안 된다.

복원 toSegment(0x33add0)는 null 점을−1, 그 외는 기준 ID+상대값으로 만든다. null t는 시작0/끝1로 복원한다. circle은 점−1/−1, t0/1 기본값이다. 따라서 NaN의 payload와 negative zero의 부호를 그대로 보존하는 규칙이 아니다. 실제 경로를 그릴 때 t 처리·hole 조합은 FILL-PATH 보고서의 별도 단계다.

varint decoder에는 입력 범위·shift>63 오류 경로가 있고 Float64도 읽을8바이트가 있어야 한다. 이 본문만으로 압축 해제 크기 상한, 모든 중복·비정상 kind·뒤쪽 잉여 바이트 거부까지 보장하지 않는다. 전체 오류 처리·입력 보안 감사 완료는 아니다.

## 이동 점 codec: run과 예측 오차

MovedPointCodec.encode(0x35e01c)는 점 ID/offset 목록에서 직전+1이 아닌 곳을 run 시작 index로 기록한다. 버전 byte1→run 수 U→각 run 순서다. 각 run은 이전 run 끝 다음 위치부터의 시작 gap U, 길이 U, run 첫 점의 x/y 이동량 Float64 각8바이트, 점별 x/y 예측 오차 S를 기록한다. 마지막에 zlib 압축한다. 목록을 codec가 정렬하는 것은 아니며 호출자 _writeMovedPoints가 먼저 키를 sort한다.

한 축에 대해 run의 첫 점에서 Δ=target−base를 계산한다(0x35e6bc/0x35e72c). 각 점에서 predicted=base+Δ를 double 덧셈으로 계산한다(0x35eb00/0x35f034). target double과 predicted double을 같은64비트 정수 표현으로 해석하고 그 **정수 차이**를 ZigZag/varint로 쓴다(0x35ecb0/0x35f1dc). XOR 압축이나 좌표 정수 반올림이 아니다.

decode(0x351c0c)는 base callback에서 좌표를 받아 base+Δ를 만든 뒤 signed integer bit 표현에 저장 residual을 더하고 다시 Float64로 해석해 write callback에 전달한다(0x3524ac/0x352828,0x352654/0x3529c0,0x352a38). 이 방식은 일반적인 유효 입력에서 double 덧셈의 반올림 차이를 residual로 복구할 수 있도록 구성됐다. 단순 Δ만 저장하는 근사 형식으로 구현하면 다르다. 모든 NaN payload·signed overflow의 roundtrip을 실제 앱에서 증명했다는 뜻은 아니다.

base callback이 null인 점은 결과 callback을 생략하고 다음 점으로 진행한다(0x3521ec→0x352a3c). 입력 payload 읽기 자체는 앞에서 진행되므로 한 점 부재로 스트림을 그 점에 멈추는 구조가 아니다.

_readMovedPoints의 callback adapter는 codec의 offset에 FrameBase.first_point_id를 더해 외부 조회/쓰기 callback에 전달한다(0x3531f4/0x353288). ID의 절대 숫자와 codec offset을 혼동하면 안 된다.

## DB 저장 연결

_writeMovedPoints(0x35d82c)는 입력 변경 map이 비면 해당 frame의 moved_points 행을 삭제한다. 비어 있지 않으면 키 정렬→기준/대상 좌표 목록과 offset 목록→encode→frame별 UPSERT로 이어진다(0x35d944,0x35df34,0x35dfac). 이 분기에서 기준 좌표 map 조회에 실패하면 NullError 경로도 있으므로 임의의 빠진 기준값을0으로 채워 저장하면 안 된다.

_writeAnchorConnections(0x35f5e8)는 점을 withLinks=false로 로컬 구체화한 뒤 기존 **그 점의 outgoing 연결**을 삭제하고, 입력 연결의 대상 ID를 Set으로 중복 제거하여 순서대로 insert한다. 현재 helper를 양방향 연결 자동 생성이나 incoming 연결 전체 삭제로 확대하지 않는다. root 구체화의 Flags/참조 재배치는 ROOT-FLAGS-LAYER-SWAP 보고서를 따른다.

## 검증 범위

명령 대조는 AOT-CODEC-ROOT-AUDIT-2026-10-15.json을 따른다. 선택 주소 일치와 작성한 제어 흐름 해석이며 전체 binary codec의 독립 구현/실제 앱 왕복 검증은 아니다. 기존 unit/probe·영상·폰 시험은 반복하지 않았다. 원본/역컴파일·assembly는 비공개로 유지한다.
