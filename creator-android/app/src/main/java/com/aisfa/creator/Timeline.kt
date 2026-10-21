package com.aisfa.creator

/**
 * 원래 앱의 내보내기 시간축(docs/NATIVE-TWEEN-FINDINGS.md, native_timing.py). (T, P) = (트위닝 fps, 재생 fps).
 * - T > P: 보간. 출력 fps = T, 출력 개수 = round(N × T / P). 출력 j의 원본 위치 = j × P / T.
 * - T ≤ P: 원본 프레임을 P fps로 그대로.
 * SFA 파일에는 이 값이 저장되지 않아(Sequence 속성은 이름·비율·프레임 수·배경색뿐) 사용자가 정한다.
 */
class Timeline(val src: Int, val tween: Int, val play: Int) {
    val interp = tween > play
    val fps = if (interp) tween else play
    val count = if (interp) maxOf(1, ((2L * src * tween + play) / (2L * play)).toInt()) else src
    /** 캐시 폴더 이름에 붙인다. 보간하지 않으면 재생 fps와 관계없이 같은 그림이다. */
    val key = if (interp) "t${tween}p$play" else "src"

    /** 출력 j의 앞 원본 프레임. */
    fun a(j: Int): Int = if (!interp) j else minOf((j.toLong() * play / tween).toInt(), src - 1)
    /** 출력 j의 뒤 원본 프레임(마지막이면 앞과 같음 = 정지). */
    fun b(j: Int): Int = minOf(a(j) + 1, src - 1)
    /** 앞→뒤 비율 0..1. 0이면 원본 프레임을 그대로 그린다. */
    fun t(j: Int): Float = if (!interp || a(j) == b(j)) 0f else ((j.toLong() * play % tween).toFloat() / tween)

    fun seconds(j: Int) = j.toDouble() / fps
}
