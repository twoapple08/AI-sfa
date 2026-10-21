package com.aisfa.creator.gen

import java.io.InputStream

/**
 * 이펙트 사전(assets/effects.txt, `tools/effect_library.py` + `tools/effect_palette.py`).
 * 형태는 '수학 함수로 그린 아이젠' 방식: 윤곽 = 구간 제한 포물선 조각(2차 베지어) 사슬. 바깥 윤곽(0) + 구멍.
 * - wedge·blob: 나카무라 임팩트 장면에서 딴 덩어리(중심 원점, 크기 = 면적 제곱근 1)
 * - scenes: 나카무라 임팩트 장면 플립북(높이 1 좌표). 결정타 임팩트 프레임에 쓴다
 * - palette: 임팩트 앞뒤 컬러 프레임의 이펙트 색(밝기순)
 * 다른 작가 그림에서 딴 형태라 저장소에 넣지 않는다(AGENTS.md 이펙트 그리기 원칙).
 */
class EffectLib(
    val wedges: List<Shape>, val blobs: List<Shape>, val scenes: List<SceneFx>, val palette: List<Int>,
) {
    /** 윤곽 목록. 0번이 바깥, 나머지는 구멍. 윤곽마다 [x0,y0,cx,cy,x1,y1]×n. */
    class Shape(val contours: List<FloatArray>)

    class SceneFrame(val whiteInk: Boolean, val w: Float, val groups: List<Shape>)
    class SceneFx(val name: String, val frames: List<SceneFrame>)

    companion object {
        val EMPTY = EffectLib(emptyList(), emptyList(), emptyList(), emptyList())

        fun read(inp: InputStream): EffectLib {
            val lines = inp.bufferedReader(Charsets.UTF_8).readLines()
            val wedges = ArrayList<Shape>(); val blobs = ArrayList<Shape>()
            val scenes = ArrayList<SceneFx>(); val pal = ArrayList<Int>()
            fun contour(s: String) = s.trim().split(' ').drop(2).map { it.toFloat() }.toFloatArray()
            var i = 0
            while (i < lines.size) {
                val f = lines[i].trim().split(' ')
                when (f[0]) {
                    "K" -> {
                        val n = f[3].toInt()
                        val sh = Shape((1..n).map { contour(lines[i + it]) })
                        if (f[1] == "wedge") wedges += sh else if (f[1] == "blob") blobs += sh
                        i += 1 + n
                    }
                    "Q" -> {
                        val nf = f[2].toInt(); i++
                        val frames = ArrayList<SceneFrame>()
                        repeat(nf) {
                            val h = lines[i].trim().split(' '); i++
                            val groups = ArrayList<Shape>()
                            repeat(h[3].toInt()) {
                                val nc = lines[i].trim().split(' ')[1].toInt(); i++
                                groups += Shape((0 until nc).map { k -> contour(lines[i + k]) }); i += nc
                            }
                            frames += SceneFrame(h[1] == "1", h[2].toFloat(), groups)
                        }
                        scenes += SceneFx(f[1], frames)
                    }
                    "P" -> { pal += (0xFF shl 24) or (f[1].toInt() shl 16) or (f[2].toInt() shl 8) or f[3].toInt(); i++ }
                    else -> i++
                }
            }
            return EffectLib(wedges, blobs, scenes, pal)
        }
    }
}
