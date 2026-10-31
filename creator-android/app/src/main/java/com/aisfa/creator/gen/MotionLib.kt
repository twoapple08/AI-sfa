package com.aisfa.creator.gen

import java.io.InputStream

/**
 * 학습 자료(assets/motion_lib.txt, `tools/motion_lib.py`가 만든다).
 * - 펀치 핵심 자세: nian41 포즈에서 고른 준비·타격·뒤따름 자세(몸 뼈대 동작)
 * - 타이밍: 나카무라 포즈의 타격 전 멈춤·타격 길이·타격 뒤 멈춤·타격 간격(24fps 프레임 수)과 정지 프레임 비율
 */
class MotionLib(val punches: List<Punch>, val timing: Timing) {
    class Punch(val arm: Int, val reach: Float, val height: Float, val wind: Int, val strike: Pose, val follow: Pose)

    /** 각 값은 (중앙값, 75%) 프레임 수. */
    class Timing(val preHold: IntArray, val strike: IntArray, val postHold: IntArray, val gap: IntArray, val stillRatio: Float) {
        companion object {
            val DEFAULT = Timing(intArrayOf(1, 1), intArrayOf(5, 10), intArrayOf(0, 1), intArrayOf(7, 11), 0.37f)
        }
    }

    companion object {
        fun read(inp: InputStream): MotionLib {
            val lines = inp.bufferedReader(Charsets.UTF_8).readLines().filter { it.isNotBlank() }
            var timing = Timing.DEFAULT
            val punches = ArrayList<Punch>()
            var i = 0
            fun pose(s: String) = Pose(s.trim().split(' ').map { it.toFloat() }.toFloatArray())
            while (i < lines.size) {
                val f = lines[i].trim().split(' ')
                when (f[0]) {
                    "T" -> {
                        fun pair(s: String) = s.split(',').map { it.toInt() }.toIntArray()
                        timing = Timing(pair(f[1]), pair(f[2]), pair(f[3]), pair(f[4]), f[5].toFloat())
                        i++
                    }
                    "P" -> {
                        // 준비 자세(i+1)는 흔들림이 많아 쓰지 않는다. 준비는 타격 자세에서 팔을 당겨 만든다(Choreo)
                        punches.add(Punch(f[1].toInt(), f[2].toFloat(), f[3].toFloat(), f[4].toInt(), pose(lines[i + 2]), pose(lines[i + 3])))
                        i += 4
                    }
                    else -> i++
                }
            }
            return MotionLib(punches, timing)
        }
    }
}
