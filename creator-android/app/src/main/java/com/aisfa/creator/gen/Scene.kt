package com.aisfa.creator.gen

import java.util.Random
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin

/** SFA 오브젝트 하나. 좌표는 기준 화면(1920×1080) 픽셀. type 1=직선, 2=원(지름 양끝), 3=2차 곡선(포물선 조각). */
class Obj(
    val id: Int, val type: Int, val color: Int, val thick: Float, val pts: FloatArray,
    val glowR: Float = 0f, val glowT: Float = 0f, val glowColor: Int = -1, val glowA: Float = 0f,
    /** 같은 프레임 안 다른 점과의 연결(점 번호 → (오브젝트 id, 점 번호)). 원래 앱의 관절 연결(AC)을 흉내 낸다. */
    val links: List<IntArray> = emptyList(),
)

/** 채우기(FR). 윤곽마다 경계 곡선 오브젝트 id 목록. 0번이 바깥, 나머지는 구멍(실제 앱: 바깥에서 뺀다). */
class Fill(val color: Int, val contours: List<IntArray>)

class OutFrame(val bg: Int, val objs: List<Obj>, val fills: List<Fill>)

/**
 * 안무(기준 24fps)를 재생 fps F로 고르고, 세기별 이펙트를 붙인다(AGENTS.md 이펙트 그리기 원칙).
 * - 이펙트 형태는 나카무라 임팩트 장면에서 딴 포물선 조각 윤곽(쐐기·덩어리·장면)을 채우기로 그린다. 원·직선 대용 금지
 * - 색은 학습 팔레트, 같은 형태를 크기·알파를 바꿔 여러 겹 겹쳐 그라데이션·번짐을 낸다
 * - 가벼움: 스미어·속도선 / 중간: + 타격 섬광·먼지 / 결정타: + 나카무라 임팩트 장면 2장·충격파·화면 흔들림
 * - 막힘: 작은 푸른 섬광 / 빗나감: 스미어·속도선만
 */
class Scene(private val ch: Choreo, private val fx: EffectLib, private val play: Int, private val dark: Boolean, private val seed: Long) {
    private val st = ch.bake()
    private val base = ch.frames
    val count = max(1, (base.toLong() * play / 24).toInt())

    private val bgColor = if (dark) 0xFF141414.toInt() else -1
    private val fig = if (dark) intArrayOf(0xFFF2F2F2.toInt(), 0xFFFF7A45.toInt()) else intArrayOf(0xFF1A1A1A.toInt(), 0xFFE0482E.toInt())
    private val figBack = if (dark) intArrayOf(0xFFB0B0B0.toInt(), 0xFFC4552F.toInt()) else intArrayOf(0xFF555555.toInt(), 0xFFA8361F.toInt())

    // 학습 팔레트(밝기순)에서 색 계열을 고른다. 없으면 비슷한 기본값
    private fun pal(r: Int, g: Int, b: Int): Int {
        if (fx.palette.isEmpty()) return (0xFF shl 24) or (r shl 16) or (g shl 8) or b
        return fx.palette.minBy { c -> val dr = (c shr 16 and 255) - r; val dg = (c shr 8 and 255) - g; val db = (c and 255) - b; dr * dr + dg * dg + db * db }
    }
    private val warm = intArrayOf(pal(194, 49, 46), pal(234, 131, 26), pal(246, 222, 37), pal(246, 234, 123))
    private val cool = intArrayOf(pal(56, 124, 173), pal(86, 218, 233), pal(86, 218, 233), 0xFFEFFBFF.toInt())
    private val dustCol = pal(196, 131, 92)

    /** 쐐기 형태의 긴 축 방향(도형 좌표). 회전해 진행 방향·방사 방향에 맞춘다. */
    private val wedgeAxis = fx.wedges.map { axis(it) }

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

    /** 한 프레임에 쌓는 오브젝트·채우기. */
    private inner class Canvas {
        val objs = ArrayList<Obj>()
        val fills = ArrayList<Fill>()

        /** 형태(포물선 조각 윤곽)를 px 변환 tf로 옮겨 채운다. 경계 곡선은 보이지 않게(알파 0) 두고 채우기만 보인다. */
        fun shape(sh: EffectLib.Shape, idBase: Int, color: Int, tf: (Float, Float) -> FloatArray) {
            if ((color ushr 24) == 0) return
            var id = idBase
            val cons = ArrayList<IntArray>()
            for (c in sh.contours) {
                val ids = IntArray(c.size / 6)
                for (j in ids.indices) {
                    val o = 6 * j
                    objs += Obj(id, 3, 0x00000000, 0.1f, tf(c[o], c[o + 1]) + tf(c[o + 2], c[o + 3]) + tf(c[o + 4], c[o + 5]))
                    ids[j] = id++
                }
                if (ids.isNotEmpty()) cons += ids
            }
            if (cons.isNotEmpty()) fills += Fill(color, cons)
        }

        /** 형태를 세계 점 (wx, wy)에 크기 s(머리 지름 단위)·회전 ang(라디안)으로 놓는다. */
        fun place(sh: EffectLib.Shape, idBase: Int, color: Int, wx: Float, wy: Float, s: Float, ang: Float, dx: Float, dy: Float) {
            val c = cos(ang); val n = sin(ang)
            shape(sh, idBase, color) { x, y ->
                // 도형 좌표는 아래가 +y(화면). 세계 좌표는 위가 +y라 y를 뒤집는다
                val rx = x * c - (-y) * n; val ry = x * n + (-y) * c
                floatArrayOf(sx(wx + rx * s + dx), sy(wy + ry * s + dy))
            }
        }
    }

    fun frame(k: Int): OutFrame {
        val f = baseOf(k)
        val cv = Canvas()
        var bg = bgColor
        var mono = 0 // 1·2: 나카무라 임팩트 장면 0·1번 프레임
        var monoHit: Hit? = null; var monoN = 0
        var shakeX = 0f; var shakeY = 0f
        for ((n, h) in ch.hits.withIndex()) if (h.tier == 2 && h.kind == Hit.Kind.HIT) {
            val k0 = outOf(h.t)
            if (k == k0) { mono = 1; monoHit = h; monoN = n } else if (k == k0 + 1 && play >= 12) { mono = 2; monoHit = h; monoN = n }
            val l = local(k, h.t)
            if (l in 0..4) { val r = Random(seed * 31 + k); val a = 0.45f * (1 - l / 5f); shakeX = (r.nextFloat() * 2 - 1) * a; shakeY = (r.nextFloat() * 2 - 1) * a }
        }
        var inkCol = 0
        if (mono != 0 && fx.scenes.isNotEmpty()) {
            val h = monoHit!!
            val sc = fx.scenes[Random(seed * 977 + monoN).nextInt(fx.scenes.size)]
            val fr = sc.frames[min(mono - 1, sc.frames.size - 1)]
            inkCol = if (fr.whiteInk) -1 else 0xFF000000.toInt()
            bg = if (fr.whiteInk) 0xFF000000.toInt() else -1
            // 장면 높이 = 화면 높이. 장면 가운데를 타격 지점 쪽으로 조금 옮긴다
            val tip = world(h.att, h.t).let { floatArrayOf(sx(it[2 * h.tipJoint]), sy(it[2 * h.tipJoint + 1])) }
            // 장면이 화면을 덮도록 키운다(4:3 장면도 좌우가 비지 않게)
            val sc2 = max(1080f, 1920f / fr.w)
            val ox = 960f - fr.w * sc2 / 2 + ((tip[0] - 960f) * 0.4f).coerceIn(-150f, 150f).coerceIn(1920f - fr.w * sc2 - (960f - fr.w * sc2 / 2), -(960f - fr.w * sc2 / 2))
            val oy = 540f - sc2 / 2
            for ((gi, g) in fr.groups.withIndex()) cv.shape(g, 9_000_000 + gi * 2000, inkCol) { x, y -> floatArrayOf(ox + x * sc2, oy + y * sc2) }
        } else mono = 0
        val monoFig = if (mono == 1 || mono == 2) (if (inkCol == -1) -1 else 0xFF000000.toInt()) else 0

        // 그리기 순서: 먼지 → 1번 캐릭터 → 0번 캐릭터 → 타격 이펙트(위)
        if (mono == 0) for ((n, d) in ch.dusts.withIndex()) dust(cv, n, d, k, shakeX, shakeY)
        for (i in intArrayOf(1, 0)) {
            // 임팩트 장면 위에서는 반대색 테두리를 먼저 깔아 어느 바탕에서도 보이게 한다(검은 형태 위 검은 그림 방지)
            if (mono != 0) fighter(cv.objs, i, f, monoFig.inv(), monoFig.inv(), shakeX, shakeY, idOff = 200, thick = FIG_T * 2.6f)
            fighter(cv.objs, i, f, if (mono != 0) monoFig else fig[i], if (mono != 0) monoFig else figBack[i], shakeX, shakeY)
        }
        if (mono == 0) for ((n, h) in ch.hits.withIndex()) hitFx(cv, n, h, k, shakeX, shakeY)
        return OutFrame(bg, cv.objs, cv.fills)
    }

    private fun Int.inv() = (this and 0xFF000000.toInt()) or (this.inv() and 0xFFFFFF)

    private fun fighter(objs: MutableList<Obj>, i: Int, f: Int, col: Int, back: Int, dx: Float, dy: Float, idOff: Int = 0, thick: Float = FIG_T) {
        val w = world(i, f)
        fun p(n: Int) = floatArrayOf(sx(w[2 * n] + dx), sy(w[2 * n + 1] + dy))
        val b = 1 + i * 20 + idOff
        fun line(id: Int, a: Int, c: Int, color: Int, links: List<IntArray> = emptyList()) =
            Obj(b + id, 1, color, thick, p(a) + p(c), links = links)
        // 머리: 목 끝에서 머리 방향으로 지름
        val nk = p(Rig.NK); val hd = p(Rig.HD)
        val top = floatArrayOf(2 * hd[0] - nk[0], 2 * hd[1] - nk[1])
        val L = { a: Int, oid: Int, pi: Int -> intArrayOf(a, b + oid, pi) }
        objs += line(4, Rig.CH, Rig.E0, back, listOf(L(0, 1, 1))); objs += line(5, Rig.E0, Rig.H0, back, listOf(L(0, 4, 1)))
        objs += line(8, Rig.HIP, Rig.K0, back, listOf(L(0, 1, 0))); objs += line(9, Rig.K0, Rig.A0, back, listOf(L(0, 8, 1))); objs += line(10, Rig.A0, Rig.T0, back, listOf(L(0, 9, 1)))
        objs += line(1, Rig.HIP, Rig.CH, col)
        objs += line(2, Rig.CH, Rig.NK, col, listOf(L(0, 1, 1)))
        objs += Obj(b + 3, 2, col, thick, top + nk, links = listOf(intArrayOf(1, b + 2, 1)))
        objs += line(11, Rig.HIP, Rig.K1, col, listOf(L(0, 1, 0))); objs += line(12, Rig.K1, Rig.A1, col, listOf(L(0, 11, 1))); objs += line(13, Rig.A1, Rig.T1, col, listOf(L(0, 12, 1)))
        objs += line(6, Rig.CH, Rig.E1, col, listOf(L(0, 1, 1))); objs += line(7, Rig.E1, Rig.H1, col, listOf(L(0, 6, 1)))
    }

    private fun alpha(c: Int, a: Float) = ((a.coerceIn(0f, 1f) * 255).roundToInt() shl 24) or (c and 0xFFFFFF)

    private fun hitFx(cv: Canvas, n: Int, h: Hit, k: Int, dx: Float, dy: Float) {
        val l = local(k, h.t)
        if (l < -1 || l > 8) return
        val idb = 100000 + n * 10000
        val r = Random(seed * 7919 + n)
        val tip = world(h.att, h.t).let { floatArrayOf(it[2 * h.tipJoint], it[2 * h.tipJoint + 1]) }
        val prev = world(h.att, h.t - 2).let { floatArrayOf(it[2 * h.tipJoint], it[2 * h.tipJoint + 1]) }
        var vx = tip[0] - prev[0]; var vy = tip[1] - prev[1]
        val vl = max(hypot(vx, vy), 1e-3f); vx /= vl; vy /= vl
        val dirA = atan2(vy, vx)
        val col = fig[h.att]

        // 스미어: 두 포물선(바깥 호·안쪽 호)으로 닫은 초승달을 3겹(넓고 옅게 → 좁고 진하게) 채운다
        if (l == 0 || l == 1) {
            val len = min(vl, 3.5f)
            val ax = tip[0] - vx * len; val ay = tip[1] - vy * len
            val side = ch.face[h.att]
            val layers = listOf(Triple(0.36f, col, 0.22f), Triple(0.24f, col, 0.42f), Triple(0.12f, warm[3], 0.75f))
            for ((m, lay) in layers.withIndex()) {
                val (bulge, c, a) = lay
                val mx = (tip[0] + ax) / 2; val my = (tip[1] + ay) / 2
                val ox = mx - vy * len * bulge * side; val oy = my + vx * len * bulge * side
                val ix = mx - vy * len * bulge * 0.35f * side; val iy = my + vx * len * bulge * 0.35f * side
                val seg = floatArrayOf(ax, ay, ox, oy, tip[0], tip[1], tip[0], tip[1], ix, iy, ax, ay)
                cv.shape(EffectLib.Shape(listOf(seg)), idb + m * 4, alpha(c, if (l == 0) a else a * 0.45f)) { x, y -> floatArrayOf(sx(x + dx), sy(y + dy)) }
            }
        }
        // 속도선: 학습 쐐기를 진행 방향으로 눕혀 손·발 끝 뒤에 반투명으로
        if (l in -1..1 && fx.wedges.isNotEmpty()) {
            val c = if (dark) 0xFF9A9A9A.toInt() else 0xFF8C8C8C.toInt()
            for (m in 0 until 5) {
                val w = (n * 5 + m) % fx.wedges.size
                val off = (m - 2) * 0.45f + (r.nextFloat() - 0.5f) * 0.2f
                val back = 1.4f + r.nextFloat() * 1.2f + (l + 1) * 0.3f
                val cx = tip[0] - vx * back - vy * off; val cy = tip[1] - vy * back + vx * off
                cv.place(fx.wedges[w], idb + 20 + m * 400, alpha(c, 0.5f - 0.12f * (l + 1)), cx, cy, 0.55f, dirA - wedgeAxis[w], dx, dy)
            }
        }
        if (h.kind == Hit.Kind.WHIFF || fx.wedges.isEmpty()) return

        val big = when { h.kind == Hit.Kind.BLOCK -> 0.6f; h.tier == 0 -> 0.8f; h.tier == 1 -> 1.15f; else -> 1.6f }
        val ramp = if (h.kind == Hit.Kind.BLOCK) cool else warm
        // 타격 섬광: 학습 쐐기를 방사형으로 놓고, 바깥(빨강·넓고 옅게) → 안쪽(연노랑·좁고 진하게) 3겹. 0–2장 동안 퍼지며 옅어진다
        if (l in 0..2) {
            val rays = when { h.kind == Hit.Kind.BLOCK -> 5; h.tier == 0 -> 6; h.tier == 1 -> 8; else -> 11 }
            val grow = 1f + l * 0.28f; val fade = 1f - l * 0.32f
            val layers = listOf(Triple(1.35f, ramp[0], 0.32f), Triple(1.0f, ramp[1], 0.6f), Triple(0.62f, ramp[3], 0.9f))
            for (m in 0 until rays) {
                val ang = (m + r.nextFloat() * 0.6f) / rays * 6.2832f
                val w = (n * 3 + m * 7) % fx.wedges.size
                val len = (0.5f + r.nextFloat() * 0.5f) * big
                for ((li, lay) in layers.withIndex()) {
                    val (sc, c, a) = lay
                    val s = len * sc * grow
                    val d = (0.35f * big + s * 1.2f)
                    cv.place(fx.wedges[w], idb + 3000 + (m * 3 + li) * 100, alpha(c, a * fade),
                        tip[0] + cos(ang) * d, tip[1] + sin(ang) * d, s, ang - wedgeAxis[w], dx, dy)
                }
            }
            // 가운데 번쩍임: 학습 덩어리 2겹
            if (fx.blobs.isNotEmpty() && l <= 1) {
                val b = fx.blobs[(n * 11) % fx.blobs.size]
                cv.place(b, idb + 2100, alpha(ramp[1], 0.4f * fade), tip[0], tip[1], 0.9f * big * grow, r.nextFloat() * 6.28f, dx, dy)
                cv.place(b, idb + 2500, alpha(ramp[3], 0.85f * fade), tip[0], tip[1], 0.45f * big * grow, r.nextFloat() * 6.28f, dx, dy)
            }
        }
        if (h.tier < 2 || h.kind != Hit.Kind.HIT) return
        // 결정타 충격파: 학습 쐐기를 원 둘레 접선 방향으로 늘어놓아 고리를 만든다. 2겹, 퍼지며 옅어진다
        if (l in 0..6) {
            val rr = 0.9f + l * 0.8f
            val segs = 14
            for (m in 0 until segs) {
                val ang = m.toFloat() / segs * 6.2832f
                val w = (m * 5 + n) % fx.wedges.size
                for ((li, lay) in listOf(0.7f to ramp[1], 0.4f to ramp[3]).withIndex()) {
                    val (sc, c) = lay
                    cv.place(fx.wedges[w], idb + 6400 + (m * 2 + li) * 100, alpha(c, (0.55f + li * 0.3f) * (1 - l / 7f)),
                        tip[0] + cos(ang) * rr, tip[1] + sin(ang) * rr, sc * (1f + l * 0.12f), ang + 1.5708f - wedgeAxis[w], dx, dy)
                }
            }
        }
    }

    /** 먼지·파편: 학습 덩어리를 2겹(넓고 옅게 + 작고 진하게) 반투명으로, 떠오르며 커지고 옅어진다. */
    private fun dust(cv: Canvas, n: Int, d: Dust, k: Int, dx: Float, dy: Float) {
        val l = local(k, d.t)
        if (l < 0 || l > 9 || fx.blobs.isEmpty()) return
        val r = Random(seed * 131 + n)
        val x = st[d.who][d.t.coerceIn(0, base - 1)].x
        val puffs = if (d.big) 7 else 4
        val light = if (dark) 0xFF6E6258.toInt() else 0xFFE8D9C8.toInt()
        for (m in 0 until puffs) {
            val ox = (m - puffs / 2f) * (if (d.big) 0.75f else 0.5f) + (r.nextFloat() - 0.5f) * 0.4f
            val s = (0.35f + l * (if (d.big) 0.09f else 0.06f)) * (0.7f + r.nextFloat() * 0.6f)
            val cy = s * 0.6f + l * 0.07f
            val b = fx.blobs[(n * 7 + m) % fx.blobs.size]
            val rot = r.nextFloat() * 6.28f
            val fade = 1 - l / 10f
            cv.place(b, 5_000_000 + n * 3000 + m * 300, alpha(light, 0.45f * fade), x + ox + dx, cy + dy, s * 1.3f, rot, 0f, 0f)
            cv.place(b, 5_000_000 + n * 3000 + m * 300 + 150, alpha(dustCol, 0.55f * fade), x + ox + dx, cy + dy, s * 0.75f, rot + 0.4f, 0f, 0f)
        }
    }

    companion object {
        const val U = 76f          // 머리 지름 = 76px(1920×1080 기준), 키 약 6.5 → 화면 높이의 약 46%
        const val GROUND = 965f
        const val FIG_T = 1.0f     // 선 굵기(ThicknessScale, 원래 앱 기본값)

        /** 형태 바깥 윤곽 점들의 주축 각도(도형 좌표를 세계 좌표처럼 y를 뒤집어 잰다). */
        fun axis(sh: EffectLib.Shape): Float {
            val c = sh.contours.firstOrNull() ?: return 0f
            var mx = 0f; var my = 0f; val n = c.size / 2
            for (i in 0 until n) { mx += c[2 * i]; my += -c[2 * i + 1] }
            mx /= n; my /= n
            var xx = 0f; var yy = 0f; var xy = 0f
            for (i in 0 until n) { val x = c[2 * i] - mx; val y = -c[2 * i + 1] - my; xx += x * x; yy += y * y; xy += x * y }
            return 0.5f * atan2(2 * xy, xx - yy)
        }

    }
}
