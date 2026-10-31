package com.aisfa.creator.gen

import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

/**
 * 리그 A(머리 1 : 키 약 6.5, 사용자 선택 2026-10-21). 길이 단위는 머리 지름.
 * 각도는 도, 0=오른쪽 90=아래(화면 좌표), '오른쪽을 보는' 자세 기준이다. 왼쪽을 볼 때는 그릴 때 x만 뒤집는다.
 */
object Rig {
    const val HEAD = 1f
    const val NECK = 0.25f
    const val SPINE = 1.6f
    const val UA = 1.25f
    const val FA = 1.15f
    const val TH = 1.55f
    const val SH = 1.5f
    const val FOOT = 0.45f

    // 관절 번호(joints 배열의 점 번호)
    const val HIP = 0; const val CH = 1; const val NK = 2; const val HD = 3
    const val E0 = 4; const val H0 = 5; const val E1 = 6; const val H1 = 7
    const val K0 = 8; const val A0 = 9; const val T0 = 10; const val K1 = 11; const val A1 = 12; const val T1 = 13
    const val N = 14
}

/** 각도 10개: 몸통, 목, 팔0(위·아래), 팔1(위·아래), 다리0(허벅지·정강이), 다리1(허벅지·정강이). 0번 팔다리는 뒤쪽, 1번은 앞쪽에 그린다. */
class Pose(val a: FloatArray) {
    fun copy() = Pose(a.copyOf())
    fun set(i: Int, v: Float) = apply { a[i] = v }

    /** 엉덩이를 원점으로 한 관절 좌표(아래가 +y). 길이 2N 배열 [x0,y0,x1,y1,…]. */
    fun joints(out: FloatArray = FloatArray(Rig.N * 2)): FloatArray {
        fun put(i: Int, x: Float, y: Float) { out[2 * i] = x; out[2 * i + 1] = y }
        fun from(i: Int, src: Int, ang: Float, len: Float) {
            val r = Math.toRadians(ang.toDouble())
            put(i, out[2 * src] + len * cos(r).toFloat(), out[2 * src + 1] + len * sin(r).toFloat())
        }
        put(Rig.HIP, 0f, 0f)
        from(Rig.CH, Rig.HIP, a[SP], Rig.SPINE)
        from(Rig.NK, Rig.CH, a[NK], Rig.NECK)
        from(Rig.HD, Rig.NK, a[NK], Rig.HEAD / 2)
        from(Rig.E0, Rig.CH, a[UA0], Rig.UA); from(Rig.H0, Rig.E0, a[FA0], Rig.FA)
        from(Rig.E1, Rig.CH, a[UA1], Rig.UA); from(Rig.H1, Rig.E1, a[FA1], Rig.FA)
        from(Rig.K0, Rig.HIP, a[TH0], Rig.TH); from(Rig.A0, Rig.K0, a[SH0], Rig.SH)
        from(Rig.T0, Rig.A0, footAngle(a[SH0]), Rig.FOOT)
        from(Rig.K1, Rig.HIP, a[TH1], Rig.TH); from(Rig.A1, Rig.K1, a[SH1], Rig.SH)
        from(Rig.T1, Rig.A1, footAngle(a[SH1]), Rig.FOOT)
        return out
    }

    /** 몸에서 가장 낮은 곳(머리 아래쪽 포함)의 엉덩이 기준 깊이. 땅에 닿게 하려면 엉덩이를 이만큼 띄운다. */
    fun drop(j: FloatArray = joints()): Float {
        var m = j[2 * Rig.HD + 1] + Rig.HEAD / 2
        for (i in 0 until Rig.N) if (i != Rig.HD) m = max(m, j[2 * i + 1])
        return m
    }

    companion object {
        const val SP = 0; const val NK = 1; const val UA0 = 2; const val FA0 = 3; const val UA1 = 4; const val FA1 = 5
        const val TH0 = 6; const val SH0 = 7; const val TH1 = 8; const val SH1 = 9

        /** 발은 정강이에 거의 수직이고, 서 있을 때 앞을 향한다. */
        fun footAngle(shin: Float) = (shin - 90f) * 0.35f

        fun of(vararg v: Float) = Pose(v)

        fun lerpAng(a: Float, b: Float, t: Float): Float {
            val d = ((b - a) % 360f + 540f) % 360f - 180f
            return a + d * t
        }

        fun lerp(p: Pose, q: Pose, t: Float) = Pose(FloatArray(10) { lerpAng(p.a[it], q.a[it], t) })
    }
}
