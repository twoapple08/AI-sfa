package com.aisfa.creator.gen

import java.util.Random
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

/** SFA 오브젝트 하나. 좌표는 기준 화면(1920×1080) 픽셀. type 1=직선, 2=원(지름 양끝), 3=2차 곡선. */
class Obj(
    val id: Int, val type: Int, val color: Int, val thick: Float, val pts: FloatArray,
    val glowR: Float = 0f, val glowT: Float = 0f, val glowColor: Int = -1, val glowA: Float = 0f,
    /** 같은 프레임 안 다른 점과의 연결(점 번호 → (오브젝트 id, 점 번호)). 원래 앱의 관절 연결(AC)을 흉내 낸다. */
    val links: List<IntArray> = emptyList(),
)

class OutFrame(val bg: Int, val objs: List<Obj>)

/**
 * 안무(기준 24fps)를 재생 fps F로 고르고, 세기별 이펙트를 붙인다.
 * - 가벼움: 스미어·속도선 / 중간: + 타격 섬광·먼지 / 결정타: + 임팩트 프레임(흑백 반전)·충격파·화면 흔들림
 * - 막힘: 작은 파란 섬광 / 빗나감: 스미어·속도선만
 */
class Scene(private val ch: Choreo, private val play: Int, private val dark: Boolean, private val seed: Long) {
    private val st = ch.bake()
    private val base = ch.frames
    val count = max(1, (base.toLong() * play / 24).toInt())

    private val bgColor = if (dark) 0xFF141414.toInt() else -1
    private val fig = if (dark) intArrayOf(0xFFF2F2F2.toInt(), 0xFFFF7A45.toInt()) else intArrayOf(0xFF1A1A1A.toInt(), 0xFFE0482E.toInt())
    private val figBack = if (dark) intArrayOf(0xFFB0B0B0.toInt(), 0xFFC4552F.toInt()) else intArrayOf(0xFF555555.toInt(), 0xFFA8361F.toInt())

    private fun baseOf(k: Int) = ((k * 24.0 / play).roundToInt()).coerceIn(0, base - 1)
    private fun outOf(t: Int) = ((t * play / 24.0).roundToInt()).coerceIn(0, count - 1)
    /** 출력 k가 사건 시각 t에서 몇 기준 프레임 떨어졌나. 사건 프레임은 F가 낮아도 반드시 한 장 나온다. */
    private fun local(k: Int, t: Int) = ((k - outOf(t)) * 24.0 / play).roundToInt()

    private fun sx(x: Float) = 960f + x * U
    private fun sy(y: Float) = GROUND - y * U

    /** 세계 좌표의 관절(머리 지름 단위, 위가 +y). */
    private fun world(i: Int, f: Int): FloatArray {
        val s = st[i][f.coerceIn(0, base - 1)]
        val j = s.pose.joints()
        val h = s.pose.drop(j) + s.air
        val out = FloatArray(j.size)
        for (n in 0 until Rig.N) { out[2 * n] = s.x + ch.face[i] * j[2 * n]; out[2 * n + 1] = h - j[2 * n + 1] }
        return out
    }

    fun frame(k: Int): OutFrame {
        val f = baseOf(k)
        val objs = ArrayList<Obj>()
        var bg = bgColor
        var mono = 0 // 1: 검은 바탕 흰 그림, 2: 흰 바탕 검은 그림
        var shakeX = 0f; var shakeY = 0f
        for (h in ch.hits) if (h.tier == 2 && h.kind == Hit.Kind.HIT) {
            val k0 = outOf(h.t)
            if (k == k0) mono = 1 else if (k == k0 + 1 && play >= 12) mono = 2
            val l = local(k, h.t)
            if (l in 0..4) { val r = Random(seed * 31 + k); val a = 0.45f * (1 - l / 5f); shakeX = (r.nextFloat() * 2 - 1) * a; shakeY = (r.nextFloat() * 2 - 1) * a }
        }
        if (mono == 1) bg = 0xFF000000.toInt() else if (mono == 2) bg = -1
        val monoCol = if (mono == 1) -1 else 0xFF000000.toInt()

        // 그리기 순서: 먼지 → 1번 캐릭터 → 0번 캐릭터 → 타격 이펙트(위)
        for ((n, d) in ch.dusts.withIndex()) dust(objs, n, d, k, mono, shakeX, shakeY)
        for (i in intArrayOf(1, 0)) fighter(objs, i, f, if (mono != 0) monoCol else fig[i], if (mono != 0) monoCol else figBack[i], shakeX, shakeY)
        for ((n, h) in ch.hits.withIndex()) hitFx(objs, n, h, k, mono, monoCol, shakeX, shakeY)
        return OutFrame(bg, objs)
    }

    private fun fighter(objs: MutableList<Obj>, i: Int, f: Int, col: Int, back: Int, dx: Float, dy: Float) {
        val w = world(i, f)
        fun p(n: Int) = floatArrayOf(sx(w[2 * n] + dx), sy(w[2 * n + 1] + dy))
        val b = 1 + i * 20
        fun line(id: Int, a: Int, c: Int, color: Int, links: List<IntArray> = emptyList()) =
            Obj(b + id, 1, color, FIG_T, p(a) + p(c), links = links)
        // 머리: 목 끝에서 머리 방향으로 지름
        val nk = p(Rig.NK); val hd = p(Rig.HD)
        val top = floatArrayOf(2 * hd[0] - nk[0], 2 * hd[1] - nk[1])
        val L = { a: Int, oid: Int, pi: Int -> intArrayOf(a, b + oid, pi) }
        objs += line(4, Rig.CH, Rig.E0, back, listOf(L(0, 1, 1))); objs += line(5, Rig.E0, Rig.H0, back, listOf(L(0, 4, 1)))
        objs += line(8, Rig.HIP, Rig.K0, back, listOf(L(0, 1, 0))); objs += line(9, Rig.K0, Rig.A0, back, listOf(L(0, 8, 1))); objs += line(10, Rig.A0, Rig.T0, back, listOf(L(0, 9, 1)))
        objs += line(1, Rig.HIP, Rig.CH, col)
        objs += line(2, Rig.CH, Rig.NK, col, listOf(L(0, 1, 1)))
        objs += Obj(b + 3, 2, col, FIG_T, top + nk, links = listOf(intArrayOf(1, b + 2, 1)))
        objs += line(11, Rig.HIP, Rig.K1, col, listOf(L(0, 1, 0))); objs += line(12, Rig.K1, Rig.A1, col, listOf(L(0, 11, 1))); objs += line(13, Rig.A1, Rig.T1, col, listOf(L(0, 12, 1)))
        objs += line(6, Rig.CH, Rig.E1, col, listOf(L(0, 1, 1))); objs += line(7, Rig.E1, Rig.H1, col, listOf(L(0, 6, 1)))
    }

    private fun hitFx(objs: MutableList<Obj>, n: Int, h: Hit, k: Int, mono: Int, monoCol: Int, dx: Float, dy: Float) {
        val l = local(k, h.t)
        if (l < -1 || l > 8) return
        val idb = 1000 + n * 80
        val r = Random(seed * 7919 + n)
        val tip = world(h.att, h.t).let { floatArrayOf(it[2 * h.tipJoint], it[2 * h.tipJoint + 1]) }
        val prev = world(h.att, h.t - 2).let { floatArrayOf(it[2 * h.tipJoint], it[2 * h.tipJoint + 1]) }
        var vx = tip[0] - prev[0]; var vy = tip[1] - prev[1]
        val vl = max(hypot(vx, vy), 1e-3f); vx /= vl; vy /= vl
        val col = if (mono != 0) monoCol else fig[h.att]
        fun P(x: Float, y: Float) = floatArrayOf(sx(x + dx), sy(y + dy))

        // 스미어: 손·발 끝이 지나간 자리를 휘어진 띠로(타격 프레임 + 다음 한 장)
        if (l == 0 || l == 1) {
            val len = min(vl, 3.5f)
            val sx0 = tip[0] - vx * len; val sy0 = tip[1] - vy * len
            val cx = (tip[0] + sx0) / 2 - vy * len * 0.28f * ch.face[h.att]; val cy = (tip[1] + sy0) / 2 + vx * len * 0.28f * ch.face[h.att]
            val a = if (l == 0) 0x99 else 0x44
            for ((m, th) in floatArrayOf(2.6f, 1.4f, 0.6f).withIndex()) {
                val o = (m - 1) * 0.18f
                objs += Obj(idb + m, 3, (a shl 24) or (col and 0xFFFFFF), th * (if (l == 0) 1f else 0.6f),
                    P(sx0 - vy * o, sy0 + vx * o) + P(cx - vy * o, cy + vx * o) + P(tip[0], tip[1]))
            }
        }
        // 속도선: 진행 방향 뒤로 평행한 가는 선
        if (l in -1..1) {
            val c = if (mono != 0) monoCol else (if (dark) 0xFF8A8A8A.toInt() else 0xFF9A9A9A.toInt())
            for (m in 0 until 5) {
                val off = (m - 2) * 0.45f + (r.nextFloat() - 0.5f) * 0.2f
                val back = 1.2f + r.nextFloat() * 1.8f + (l + 1) * 0.3f
                val ax = tip[0] - vx * 0.6f - vy * off; val ay = tip[1] - vy * 0.6f + vx * off
                objs += Obj(idb + 4 + m, 1, c, 0.35f, P(ax, ay) + P(ax - vx * back, ay - vy * back))
            }
        }
        if (h.kind == Hit.Kind.WHIFF) return

        val big = when { h.kind == Hit.Kind.BLOCK -> 0.6f; h.tier == 0 -> 0.8f; h.tier == 1 -> 1.2f; else -> 1.8f }
        val sparkCol = if (mono != 0) monoCol else if (h.kind == Hit.Kind.BLOCK) 0xFFCDEBFF.toInt() else 0xFFFFE27A.toInt()
        val glowCol = if (h.kind == Hit.Kind.BLOCK) 0xFF3BA0FF.toInt() else 0xFFFF8C3B.toInt()
        val glowA = if (mono != 0) 0f else 1f
        // 타격 섬광: 사방으로 뻗는 선(0–2장). 같은 id라 트위닝하면 이어진다
        if (l in 0..2) {
            val rays = when { h.kind == Hit.Kind.BLOCK -> 6; h.tier == 0 -> 6; h.tier == 1 -> 10; else -> 14 }
            for (m in 0 until rays) {
                val ang = (m + r.nextFloat() * 0.6f) / rays * 6.2832f
                val r0 = (0.25f + l * 0.55f) * big
                val r1 = r0 + (0.9f + r.nextFloat() * 1.4f) * big * (1 - l * 0.3f)
                objs += Obj(idb + 10 + m, 1, sparkCol, 0.7f * (1 - l * 0.25f),
                    P(tip[0] + cos(ang) * r0, tip[1] + sin(ang) * r0) + P(tip[0] + cos(ang) * r1, tip[1] + sin(ang) * r1),
                    glowR = 8f, glowT = 14f, glowColor = glowCol, glowA = glowA)
            }
            if (l == 0) {
                val rr = 0.35f * big
                objs += Obj(idb + 30, 2, sparkCol, 2.2f * big, P(tip[0], tip[1] + rr) + P(tip[0], tip[1] - rr),
                    glowR = 14f, glowT = 20f, glowColor = glowCol, glowA = glowA)
            }
        }
        if (h.tier < 2 || h.kind != Hit.Kind.HIT) return
        // 결정타: 충격파 고리(0–6장, 같은 id로 커진다)
        if (l in 0..6) {
            val rr = 0.6f + l * 0.75f
            val a = (255 * (1 - l / 7f)).roundToInt()
            val c = if (mono != 0) monoCol else (a shl 24) or (glowCol and 0xFFFFFF)
            objs += Obj(idb + 31, 2, c, 2.4f * (1 - l / 8f), P(tip[0], tip[1] + rr) + P(tip[0], tip[1] - rr),
                glowR = 10f, glowT = 12f, glowColor = glowCol, glowA = if (mono != 0) 0f else 0.8f * (1 - l / 7f))
        }
        // 임팩트 프레임 집중선(흑백 두 장)
        if (mono != 0 && l in 0..1) {
            for (m in 0 until 28) {
                val ang = (m + r.nextFloat() * 0.7f) / 28 * 6.2832f
                val r0 = 2.2f + r.nextFloat() * 2.5f
                val r1 = 16f
                objs += Obj(idb + 40 + m, 1, monoCol, 0.25f + r.nextFloat() * 0.9f,
                    P(tip[0] + cos(ang) * r0, tip[1] + sin(ang) * r0) + P(tip[0] + cos(ang) * r1, tip[1] + sin(ang) * r1))
            }
        }
    }

    private fun dust(objs: MutableList<Obj>, n: Int, d: Dust, k: Int, mono: Int, dx: Float, dy: Float) {
        val l = local(k, d.t)
        if (l < 0 || l > 9) return
        if (mono == 1) return
        val r = Random(seed * 131 + n)
        val x = st[d.who][d.t.coerceIn(0, base - 1)].x
        val puffs = if (d.big) 7 else 4
        val c0 = if (mono != 0) 0xFF000000.toInt() else if (dark) 0xFF6E6E6E.toInt() else 0xFFB8B8B8.toInt()
        for (m in 0 until puffs) {
            val ox = (m - puffs / 2f) * (if (d.big) 0.75f else 0.5f) + (r.nextFloat() - 0.5f) * 0.4f
            val rr = (0.2f + l * (if (d.big) 0.12f else 0.08f)) * (0.7f + r.nextFloat() * 0.6f)
            val cy = rr + l * 0.06f
            val a = (255 * (1 - l / 10f)).roundToInt()
            objs += Obj(5000 + n * 10 + m, 2, (a shl 24) or (c0 and 0xFFFFFF), 1.4f * (1 - l / 11f),
                floatArrayOf(sx(x + ox + dx), sy(cy + rr + dy)) + floatArrayOf(sx(x + ox + dx), sy(cy - rr + dy)))
        }
    }

    companion object {
        const val U = 76f          // 머리 지름 = 76px(1920×1080 기준), 키 약 6.5 → 화면 높이의 약 46%
        const val GROUND = 965f
        const val FIG_T = 1.0f     // 선 굵기(ThicknessScale, 원래 앱 기본값)
    }
}
