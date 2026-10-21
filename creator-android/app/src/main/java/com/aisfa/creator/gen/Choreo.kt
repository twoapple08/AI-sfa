package com.aisfa.creator.gen

import java.util.Random
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

enum class Ease { LINEAR, IN, OUT, IO, STEP }

/** 한 기준 프레임(24fps)의 캐릭터 상태. x·air는 세계 좌표(머리 지름 단위), air는 땅 위로 띄운 높이. */
class State(val pose: Pose, val x: Float, val air: Float)

/** 핵심 자세 사이를 보간하는 키 목록. 나중 키가 앞선 키보다 이르면 그 뒤의 키를 지운다(연타가 회복 동작을 끊는다). */
class Track(start: Pose, x: Float) {
    class Key(val t: Int, val pose: Pose, val x: Float, val air: Float, val ease: Ease, val twos: Boolean)

    val keys = arrayListOf(Key(0, start, x, 0f, Ease.LINEAR, false))
    val last get() = keys.last()

    fun key(t: Int, pose: Pose, x: Float = last.x, air: Float = 0f, ease: Ease = Ease.IO, twos: Boolean = false) {
        while (keys.size > 1 && keys.last().t >= t) keys.removeAt(keys.size - 1)
        val tt = max(t, keys.last().t + 1)
        keys.add(Key(tt, pose, x, air, ease, twos))
    }

    fun hold(t: Int) { if (t > last.t) key(t, last.pose, last.x, last.air, Ease.LINEAR) }

    /** t 시점의 상태(키 사이 보간). */
    fun at(f: Int): State {
        var k = 1
        while (k < keys.size && keys[k].t < f) k++
        if (k >= keys.size) return keys.last().let { State(it.pose, it.x, it.air) }
        val a = keys[k - 1]; val b = keys[k]
        var ff = f
        // '2프레임에 한 장'(나카무라 정지 비율 반영): 느린 구간은 짝수 프레임만 새로 그린다
        if (b.twos) ff = a.t + ((f - a.t) / 2) * 2
        val u = ((ff - a.t).toFloat() / (b.t - a.t)).coerceIn(0f, 1f)
        val e = when (b.ease) {
            Ease.LINEAR -> u
            Ease.IN -> u * u
            Ease.OUT -> 1 - (1 - u) * (1 - u)
            Ease.IO -> u * u * (3 - 2 * u)
            Ease.STEP -> if (u >= 1f) 1f else 0f
        }
        return State(Pose.lerp(a.pose, b.pose, e), a.x + (b.x - a.x) * e, a.air + (b.air - a.air) * e)
    }
}

/** 타격 순간 기록. 위치는 굽기(bake) 뒤 계산한다. */
class Hit(val t: Int, val att: Int, val tipJoint: Int, val kind: Kind, val tier: Int) {
    enum class Kind { HIT, BLOCK, WHIFF }
}

class Dust(val t: Int, val who: Int, val big: Boolean)

/**
 * 1v1 맨손 육탄전 안무(배경·도구 없음).
 * - 몸 동작: 펀치 핵심 자세는 nian41 학습 자료, 발차기·피격·막기·피하기·쓰러짐은 규칙 자세(자료 부족, 2026-10-21 판단)
 * - 타이밍: 나카무라 통계(준비 뒤 멈춤 → 1–2프레임 타격 → 타격 뒤 멈춤, 연타 간격, 2프레임 정지)
 * - 세기: 0 가벼움, 1 중간, 2 결정타. 이펙트 단계는 Scene이 정한다
 * 0번은 왼쪽(오른쪽을 봄), 1번은 오른쪽(왼쪽을 봄). 서로 지나쳐 자리를 바꾸지 않는다.
 */
class Choreo(private val lib: MotionLib, seed: Long, val frames: Int) {
    private val rnd = Random(seed)
    val face = floatArrayOf(1f, -1f)
    val tr = arrayOf(Track(jit(STANCE), -2.9f), Track(jit(STANCE), 2.9f))
    val hits = ArrayList<Hit>()
    val dusts = ArrayList<Dust>()
    private val tm = lib.timing

    private fun r(a: Int, b: Int) = a + rnd.nextInt(b - a + 1)
    private fun rf(a: Float, b: Float) = a + rnd.nextFloat() * (b - a)
    private fun jit(p: Pose, deg: Float = 4f) = Pose(FloatArray(10) { p.a[it] + rf(-deg, deg) })

    fun run(): Choreo {
        var now = r(3, 8)
        var att = rnd.nextInt(2)
        while (now < frames) {
            neutral(now, r(4, 10))
            now = max(tr[0].last.t, tr[1].last.t)
            if (rnd.nextFloat() < 0.6f) att = 1 - att
            val combo = r(1, 3)
            for (c in 0 until combo) {
                val lastOne = c == combo - 1
                val tier = when {
                    lastOne && combo >= 2 && rnd.nextFloat() < 0.5f -> 2
                    lastOne && rnd.nextFloat() < 0.12f -> 2
                    c >= 1 || rnd.nextFloat() < 0.3f -> 1
                    else -> 0
                }
                val kind = if (tier == 2) Hit.Kind.HIT else when (rnd.nextFloat()) {
                    in 0f..0.55f -> Hit.Kind.HIT
                    in 0.55f..0.85f -> Hit.Kind.BLOCK
                    else -> Hit.Kind.WHIFF
                }
                now = strike(att, now, tier, kind, combo = !lastOne)
                if (now >= frames) break
            }
            now = max(tr[0].last.t, tr[1].last.t) + 1
        }
        for (t in tr) t.hold(frames)
        return this
    }

    /** 서로 거리를 재며 몸을 들썩이고, 화면 가운데·적당한 간격으로 천천히 돌아온다. */
    private fun neutral(t0: Int, n: Int) {
        val mid = (tr[0].last.x + tr[1].last.x) / 2
        val gap = tr[1].last.x - tr[0].last.x
        val wantGap = rf(4.8f, 6.2f)
        val shift = (-mid).coerceIn(-1.2f, 1.2f)
        val half = (wantGap - gap) / 2
        for (i in 0..1) {
            val t = tr[i]
            val start = max(t0, t.last.t)
            val x1 = t.last.x + shift - face[i] * half.coerceIn(-1.2f, 1.2f)
            val step = abs(x1 - t.last.x) > 0.25f
            val bob = jit(STANCE, 3f).also { it.a[Pose.TH0] += 6f; it.a[Pose.TH1] -= 6f; it.a[Pose.SP] += 2f }
            t.key(start + n / 2, if (step) jit(STEP_MID, 3f) else bob, (t.last.x + x1) / 2, if (step) 0.12f else 0f, Ease.IO, twos = true)
            t.key(start + n, jit(STANCE, 3f), x1, 0f, Ease.IO, twos = true)
        }
    }

    /** 공격 하나. 반환값은 다음 동작을 시작할 시각. */
    private fun strike(a: Int, t0: Int, tier: Int, kind: Hit.Kind, combo: Boolean): Int {
        val d = 1 - a
        val f = face[a]
        val ta = tr[a]; val td = tr[d]
        val kick = rnd.nextFloat() < (if (tier >= 1) 0.35f else 0.2f)
        val windup: Pose; val hit: Pose; val follow: Pose; val tipJ: Int
        if (kick) {
            val high = rnd.nextBoolean()
            windup = jit(KICK_CH); hit = jit(if (high) KICK_HI else KICK_EX); follow = Pose.lerp(hit, KICK_CH, 0.5f); tipJ = Rig.A1
        } else {
            val p = lib.punches[rnd.nextInt(lib.punches.size)]
            hit = jit(p.strike, 3f)
            val k = p.arm
            val ua = if (k == 0) Pose.UA0 else Pose.UA1
            windup = hit.copy().set(ua, 118f + rf(-8f, 8f)).set(ua + 1, -35f + rf(-10f, 10f))
                .set(Pose.SP, hit.a[Pose.SP] - 8f).set(Pose.NK, hit.a[Pose.NK] - 4f)
            follow = Pose.lerp(p.follow, STANCE, 0.3f)
            tipJ = if (k == 0) Rig.H0 else Rig.H1
        }
        // 타격 순간 손·발 끝이 상대 몸 앞면에 닿도록 공격자 위치를 정한다
        val j = hit.joints()
        val tipX = j[2 * tipJ]
        val xd = td.last.x
        val xHit = (xd - f * (0.35f + tipX)).let { if (f > 0) min(it, xd - 1.3f) else max(it, xd + 1.3f) }
        val lunge = if (kick) 0.35f else 0.7f
        val xReady = xHit - f * lunge
        var t = max(t0, ta.last.t)
        if (!combo || abs(ta.last.x - xReady) > 0.5f) {
            val dist = abs(ta.last.x - xReady)
            if (dist > 0.3f) {
                val n = (dist / 0.38f).roundToInt().coerceIn(3, 10)
                ta.key(t + n / 2, jit(STEP_MID), (ta.last.x + xReady) / 2, 0.15f, Ease.LINEAR)
                ta.key(t + n, jit(STANCE), xReady, 0f, Ease.OUT)
                t += n
            }
        }
        val nw = r(3, 5)
        val pre = r(tm.preHold[0], max(tm.preHold[0], tm.preHold[1])).coerceAtLeast(1)
        val ns = if (tier == 2) 1 else r(1, 2)
        ta.key(t + nw, windup, xReady - f * 0.1f, 0f, Ease.IO)
        ta.hold(t + nw + pre)
        val ti = t + nw + pre + ns
        ta.key(ti, hit, xHit, if (kick) 0.05f else 0f, Ease.OUT)
        val post = intArrayOf(1, 2, 3)[tier] + r(tm.postHold[0], tm.postHold[1])
        ta.hold(ti + post)
        hits.add(Hit(ti, a, tipJ, kind, tier))
        react(d, ti, tier, kind, high = (hit.drop() - j[2 * tipJ + 1]) > 4.6f, push = f)
        if (combo) {
            // 연타: 회복 없이 다음 준비로(나카무라 간격)
            val gap = r(tm.gap[0], tm.gap[1])
            ta.key(ti + post + 2, follow, xHit - f * 0.2f, 0f, Ease.OUT)
            return max(ti + post + 2, ti + gap - 6)
        }
        ta.key(ti + post + 3, follow, xHit - f * 0.25f, 0f, Ease.OUT)
        ta.key(ti + post + 9, jit(STANCE), xHit - f * 0.6f, 0f, Ease.IO, twos = true)
        return ti + post + 9
    }

    /** 맞은 쪽 반응. push는 밀려나는 방향(공격자가 보는 방향). */
    private fun react(d: Int, ti: Int, tier: Int, kind: Hit.Kind, high: Boolean, push: Float) {
        val t = tr[d]
        val x0 = t.last.x
        fun clampX(x: Float) = x.coerceIn(-10.5f, 10.5f)
        when (kind) {
            Hit.Kind.BLOCK -> {
                t.key(ti - 3, jit(GUARD), x0, 0f, Ease.OUT)
                t.key(ti, jit(GUARD, 2f).also { it.a[Pose.SP] -= 5f }, clampX(x0 + push * 0.35f), 0f, Ease.STEP)
                t.key(ti + 3, jit(GUARD), clampX(x0 + push * 0.5f), 0f, Ease.OUT)
                t.key(ti + 9, jit(STANCE), clampX(x0 + push * 0.5f), 0f, Ease.IO, twos = true)
            }
            Hit.Kind.WHIFF -> {
                val dodge = if (high) jit(DUCK) else jit(SWAY)
                t.key(ti - 2, dodge, clampX(x0 + push * 0.5f), 0f, Ease.OUT)
                t.hold(ti + 3)
                t.key(ti + 9, jit(STANCE), clampX(x0 + push * 0.6f), 0f, Ease.IO, twos = true)
            }
            Hit.Kind.HIT -> if (tier < 2) {
                val kb = if (tier == 0) 0.5f else 1.2f
                t.key(ti, jit(if (high) HIT_HEAD else HIT_BODY, 6f), clampX(x0 + push * kb * 0.5f), 0f, Ease.STEP)
                t.key(ti + 2 + tier, jit(if (high) HIT_HEAD else HIT_BODY, 3f), clampX(x0 + push * kb), 0f, Ease.OUT)
                t.key(ti + 10 + tier * 2, jit(STANCE), clampX(x0 + push * kb * 1.1f), 0f, Ease.IO, twos = true)
                if (tier == 1) dusts.add(Dust(ti + 1, d, false))
            } else {
                // 결정타: 날아가 쓰러졌다 일어난다
                val far = (x0 + push * rf(4.5f, 6f)).coerceIn(-8f, 8f) // 누운 몸이 화면 밖으로 나가지 않게
                t.key(ti, jit(HIT_HEAD, 4f), clampX(x0 + push * 0.4f), 0f, Ease.STEP)
                t.key(ti + 3, jit(FLY), clampX(x0 + push * 2.2f), 1.4f, Ease.OUT)
                t.key(ti + 8, jit(FLY, 2f).also { it.a[Pose.SP] += 8f }, (far + clampX(x0 + push * 2.2f)) / 2 + push * 1f, 0.6f, Ease.LINEAR)
                t.key(ti + 11, jit(LIE, 2f), far, 0f, Ease.IN)
                t.key(ti + 14, jit(LIE, 1f), clampX(far + push * 0.5f), 0f, Ease.OUT)
                t.hold(ti + 22)
                t.key(ti + 30, jit(CROUCH), clampX(far + push * 0.5f), 0f, Ease.IO, twos = true)
                t.key(ti + 38, jit(STANCE), clampX(far + push * 0.5f), 0f, Ease.IO, twos = true)
                dusts.add(Dust(ti + 11, d, true))
            }
        }
    }

    /** 기준 프레임(24fps)별 상태. 땅 위 엉덩이 높이 = 자세의 가장 낮은 점 깊이 + 띄움. */
    fun bake(): Array<Array<State>> = Array(2) { i -> Array(frames) { f -> tr[i].at(f) } }

    companion object {
        // 오른쪽을 보는 기준 자세(도). 0번 팔다리 = 뒤, 1번 = 앞
        val STANCE = Pose.of(-84f, -80f, 100f, -75f, 65f, -70f, 112f, 100f, 68f, 92f)
        val STEP_MID = Pose.of(-86f, -82f, 95f, -70f, 70f, -65f, 96f, 98f, 84f, 100f)
        val GUARD = Pose.of(-96f, -72f, 40f, -95f, 30f, -85f, 120f, 104f, 62f, 88f)
        val HIT_HEAD = Pose.of(-114f, -138f, 160f, 175f, 128f, 165f, 108f, 100f, 72f, 82f)
        val HIT_BODY = Pose.of(-58f, -38f, 70f, 120f, 50f, 110f, 104f, 95f, 76f, 102f)
        val SWAY = Pose.of(-126f, -124f, 110f, -60f, 80f, -60f, 124f, 95f, 70f, 80f)
        val DUCK = Pose.of(-48f, -35f, 60f, -40f, 40f, -50f, 25f, 118f, 62f, 128f)
        val FLY = Pose.of(-162f, -172f, -150f, -160f, -138f, -128f, -14f, 10f, 12f, 22f)
        val LIE = Pose.of(178f, 178f, 168f, 176f, 150f, 162f, -2f, 2f, 8f, -4f)
        val CROUCH = Pose.of(-58f, -62f, 82f, 62f, 58f, 82f, 92f, 172f, 8f, 95f)
        val KICK_CH = Pose.of(-100f, -95f, 120f, -60f, 40f, -80f, 96f, 92f, -25f, 95f)
        val KICK_EX = Pose.of(-112f, -100f, 125f, -55f, 45f, -75f, 98f, 92f, -8f, -5f)
        val KICK_HI = Pose.of(-130f, -112f, 140f, 160f, 70f, -60f, 100f, 95f, -45f, -50f)
    }
}
