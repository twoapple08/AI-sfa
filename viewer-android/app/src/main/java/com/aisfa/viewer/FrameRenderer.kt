package com.aisfa.viewer

import android.graphics.Bitmap
import android.graphics.BlurMaskFilter
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import kotlin.math.PI
import kotlin.math.atan2
import kotlin.math.ceil
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * 한 프레임을 그린다. 규칙은 서버 기준 렌더러(tools/sfa_render.py)와 같고, 앱 내보내기 영상과 픽셀 대조로 맞췄다.
 * - 기준 좌표계: 내보내기 1920 x (1920*비율). 여백 6px 안쪽에 비율 맞춤, x = ox + uw*X/100.
 * - 선 폭: round(1.14 * 8 * ThicknessScale), 둥근 끝·이음.
 * - 글로우: 폭 8*ThicknessScale*GlowThickness/10 띠를 Gaussian(sigma=sqrt(R^2+0.29^2))으로 흐림 x GlowColor x GlowAlpha.
 * - 순서: 레이어 목록 순서(첫 레이어가 맨 아래) → 레이어 안 DrawOrder → 연결 그룹 단위로 글로우 먼저, 그다음 오브젝트마다 채우기·선.
 * - 채우기: 경계 조각을 이어 붙이고 끊긴 곳에서 새 윤곽, 짝홀 규칙.
 */
class FrameRenderer(private val doc: SfaDoc) {
    val baseW = 1920f
    val baseH = (1920f * doc.ratio).roundToInt().toFloat()
    private val pad = 6f
    private val ox: Float; private val oy: Float; private val uw: Float; private val uh: Float

    init {
        val r = doc.ratio
        val aw = (baseW - 2 * pad).coerceIn(1f, baseW); val ah = (baseH - 2 * pad).coerceIn(1f, baseH)
        if (ah / aw > r) { uw = aw; uh = aw * r } else { uh = ah; uw = ah / r }
        ox = (baseW - uw) / 2; oy = (baseH - uh) / 2
    }

    private fun X(i: Int) = ox + uw * (if (tw) tx[i - tp0] else doc.px[i]) / 100f
    private fun Y(i: Int) = oy + uh * (if (tw) ty[i - tp0] else doc.py[i]) / 100f

    // ── 보간(중간 장면) 상태: 앞 프레임 구조에 섞은 값을 덮어쓴다. 원본 프레임을 그릴 때는 tw = false ──
    private var tw = false
    private var tp0 = 0; private var tx = FloatArray(64); private var ty = FloatArray(64)
    private var to0 = 0; private var tOn = BooleanArray(64); private var tCol = IntArray(64); private var tTh = FloatArray(64)
    private var tGR = FloatArray(64); private var tGT = FloatArray(64); private var tGC = IntArray(64); private var tGA = FloatArray(64)
    private var tf0 = 0; private var tFlOn = BooleanArray(16); private var tFlCol = IntArray(16)
    private var ts0 = 0; private var tS0 = FloatArray(64); private var tS1 = FloatArray(64)
    private fun col(o: Int) = if (tw) tCol[o - to0] else doc.oColor[o]
    private fun thick(o: Int) = if (tw) tTh[o - to0] else doc.oThick[o]
    private fun glowR(o: Int) = if (tw) tGR[o - to0] else doc.oGlowR[o]
    private fun glowT(o: Int) = if (tw) tGT[o - to0] else doc.oGlowT[o]
    private fun glowC(o: Int) = if (tw) tGC[o - to0] else doc.oGlowColor[o]
    private fun glowA(o: Int) = if (tw) tGA[o - to0] else doc.oGlowA[o]
    private fun segT0(k: Int) = if (tw) tS0[k - ts0] else doc.sT0[k]
    private fun segT1(k: Int) = if (tw) tS1[k - ts0] else doc.sT1[k]

    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND }
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }
    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeCap = Paint.Cap.ROUND; strokeJoin = Paint.Join.ROUND }
    private val bmpPaint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
    private val path = Path(); private val fpath = Path()

    /** 프레임 f를 bitmap 전체 크기에 맞춰 그린다. */
    fun render(f: Int, bmp: Bitmap) {
        val c = Canvas(bmp)
        val s = bmp.width / baseW
        c.drawColor(doc.fBg[f])
        c.save(); c.scale(s, s)
        draw(f, c, s)
        c.restore()
    }

    private fun objPath(o: Int, p: Path): Boolean {
        p.rewind()
        val st = doc.oPtStart[o]; val n = doc.oPtCount[o].toInt()
        when (doc.oType[o].toInt()) {
            1 -> { if (n < 2) return false; p.moveTo(X(st), Y(st)); p.lineTo(X(st + 1), Y(st + 1)) }
            2 -> {
                if (n < 2) return false
                val x1 = X(st); val y1 = Y(st); val x2 = X(st + 1); val y2 = Y(st + 1)
                p.addCircle((x1 + x2) / 2, (y1 + y2) / 2, hypot(x2 - x1, y2 - y1) / 2, Path.Direction.CW)
            }
            3 -> { if (n < 3) return false; p.moveTo(X(st), Y(st)); p.quadTo(X(st + 1), Y(st + 1), X(st + 2), Y(st + 2)) }
            else -> return false
        }
        return true
    }

    // 경계 조각 점 목록(기준 좌표)
    private var sx = FloatArray(256); private var sy = FloatArray(256); private var sn = 0
    private fun push(x: Float, y: Float) { if (sn == sx.size) { sx = sx.copyOf(sn * 2); sy = sy.copyOf(sn * 2) }; sx[sn] = x; sy[sn] = y; sn++ }

    private fun segPoints(o: Int, t0: Float, t1: Float) {
        val st = doc.oPtStart[o]; val n = doc.oPtCount[o].toInt()
        when (doc.oType[o].toInt()) {
            2 -> if (n >= 2) {
                val x1 = X(st); val y1 = Y(st); val x2 = X(st + 1); val y2 = Y(st + 1)
                val cx = (x1 + x2) / 2; val cy = (y1 + y2) / 2; val r = hypot(x2 - x1, y2 - y1) / 2
                val a0 = atan2(y1 - cy, x1 - cx)
                val k = max(2, ceil(kotlin.math.abs(t1 - t0) * PI * 2 * r / 2.0).toInt() + 1)
                for (i in 0 until k) { val t = t0 + (t1 - t0) * i / (k - 1); val a = a0 + 2 * PI * t; push((cx + r * cos(a)).toFloat(), (cy + r * sin(a)).toFloat()) }
            }
            3 -> if (n >= 3) {
                val x0 = X(st); val y0 = Y(st); val x1 = X(st + 1); val y1 = Y(st + 1); val x2 = X(st + 2); val y2 = Y(st + 2)
                val L = hypot(x1 - x0, y1 - y0) + hypot(x2 - x1, y2 - y1)
                val k = max(2, ceil(kotlin.math.abs(t1 - t0) * L / 2.0).toInt() + 1)
                for (i in 0 until k) { val t = t0 + (t1 - t0) * i / (k - 1); val u = 1 - t; push(u * u * x0 + 2 * u * t * x1 + t * t * x2, u * u * y0 + 2 * u * t * y1 + t * t * y2) }
            }
            else -> if (n >= 2) {
                val x0 = X(st); val y0 = Y(st); val x1 = X(st + 1); val y1 = Y(st + 1)
                push(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0); push(x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
            }
        }
    }

    /** 앱 규칙(AOT-FILL-PATH): 윤곽마다 조각을 잇고(간격은 직선으로) 닫아 짝홀 규칙, 외곽(윤곽 0)에서 나머지 윤곽을 차례로 뺀다. 곡선 T는 0–1로 자른다. */
    private fun contourPath(fl: Int, cont: Int, out: Path): Boolean {
        out.rewind(); out.fillType = Path.FillType.EVEN_ODD
        sn = 0
        val s0 = doc.flSegStart[fl]
        for (k in s0 until s0 + doc.flSegCount[fl]) {
            if (doc.sCont[k] != cont) continue
            val o = doc.sObj[k]; if (o < 0) continue
            var t0 = segT0(k); var t1 = segT1(k)
            if (doc.oType[o].toInt() == 3) {
                t0 = t0.coerceIn(0f, 1f); t1 = t1.coerceIn(0f, 1f)
                if (kotlin.math.abs(t1 - t0) <= 1e-6f) continue
            }
            segPoints(o, t0, t1)
        }
        if (sn < 3) return false
        out.moveTo(sx[0], sy[0]); for (i in 1 until sn) out.lineTo(sx[i], sy[i]); out.close()
        return true
    }

    private val holePath = Path()
    private fun drawFill(fl: Int, c: Canvas) {
        if (tw && !tFlOn[fl - tf0]) return
        val col = if (tw) tFlCol[fl - tf0] else doc.flColor[fl]
        if ((col ushr 24) == 0) return
        if (!contourPath(fl, 0, fpath)) return
        var maxC = 0
        val s0 = doc.flSegStart[fl]
        for (k in s0 until s0 + doc.flSegCount[fl]) if (doc.sCont[k] > maxC) maxC = doc.sCont[k]
        // 구멍 빼기(difference)는 휴대폰에서 매우 느리다(한 프레임 수 초). 구멍을 같은 짝홀 경로에 더하는 방식과
        // 기준 렌더러 대조 결과가 같았으므로(p0·p2·p3) 이 방식을 쓴다. 구멍끼리 겹치는 경우만 다를 수 있다.
        for (h in 1..maxC) if (contourPath(fl, h, holePath)) fpath.addPath(holePath)
        fill.color = col
        c.drawPath(fpath, fill)
    }

    private fun drawBase(o: Int, c: Canvas) {
        val col = col(o)
        if ((col ushr 24) == 0) return
        val w = 8f * max(thick(o), 0f)
        if (w <= 0f) return
        stroke.color = col
        stroke.strokeWidth = max((1.14f * w).roundToInt().toFloat(), 0.5f)
        if (objPath(o, path)) c.drawPath(path, stroke)
    }

    private val tmpRect = RectF()

    private fun drawGlow(o: Int, c: Canvas, s: Float) {
        val gr = glowR(o); val gt = glowT(o); var ga = glowA(o)
        if (gr <= 0f || gt <= 0f || ga <= 0f) return
        if (ga > 1f) ga /= 255f
        val wg = 8f * max(thick(o), 0f) * max(gt / 10f, 0f)
        val sig = sqrt(gr * gr + 0.29f * 0.29f)
        if (!objPath(o, path)) return
        val gc = glowC(o)
        val color = (((ga.coerceIn(0f, 1f) * 255f).roundToInt()) shl 24) or (gc and 0xFFFFFF)
        val sigPx = sig * s
        if (sigPx < 4f) {
            glowPaint.color = color; glowPaint.strokeWidth = wg
            glowPaint.maskFilter = if (sigPx > 0.5f) BlurMaskFilter(max((sig - 0.5f / s) / 0.57735f, 0.1f), BlurMaskFilter.Blur.NORMAL) else null
            c.drawPath(path, glowPaint)
            glowPaint.maskFilter = null
            return
        }
        nGlowBig++
        // 큰 번짐: 축소 비트맵에 띠를 그려 박스 블러 3회(가우스 근사) 후 확대해 합성
        path.computeBounds(tmpRect, true)
        val m = wg / 2 + 4 * sig + 2
        val l = tmpRect.left - m; val t = tmpRect.top - m; val r = tmpRect.right + m; val b = tmpRect.bottom + m
        val q = min(1f, 3f / sigPx) * s
        val bw = max(1, ceil((r - l) * q).toInt()); val bh = max(1, ceil((b - t) * q).toInt())
        if (bw.toLong() * bh > 6_000_000L) return
        val a = Bitmap.createBitmap(bw, bh, Bitmap.Config.ALPHA_8)
        val ac = Canvas(a)
        ac.scale(q, q); ac.translate(-l, -t)
        glowPaint.color = -1; glowPaint.strokeWidth = max(wg, 0.01f); glowPaint.maskFilter = null
        ac.drawPath(path, glowPaint)
        Blur.gaussianAlpha(a, sig * q)
        bmpPaint.color = color
        tmpRect.set(l, t, l + bw / q, t + bh / q)
        c.drawBitmap(a, null, tmpRect, bmpPaint)
        a.recycle()
    }

    /** 출력 프레임 j(시간표 기준)를 그린다. 원본 위치가 정수면 원본 프레임, 아니면 앞뒤를 섞은 중간 장면. */
    fun render(tl: Timeline, j: Int, bmp: Bitmap) {
        val t = tl.t(j)
        if (t <= 0f) { render(tl.a(j), bmp); return }
        prepareTween(tl.a(j), tl.b(j), t)
        try { render(tl.a(j), bmp) } finally { tw = false }
    }

    private var mapFrame = -1
    private val idMap = HashMap<Int, Int>()

    /**
     * 원래 앱의 중간 장면 규칙(AOT-OBJECT-TWEEN-PAIR, AOT-FILL-TWEEN)을 따른다.
     * - 오브젝트: 앞 프레임 오브젝트마다 뒤 프레임에서 같은 ID를 찾는다. 짝이 없는 오브젝트(앞에만·뒤에만 있는 것)는 중간 장면에 그리지 않는다.
     * - 점: 앞 점의 Index와 같은 뒤 점(같은 위치 먼저, 없으면 처음부터 찾기), 없으면 앞 좌표 유지. x/y 선형.
     * - 색 ARGB 채널별(앞 + round(차 × t)), 굵기 선형, 글로우 반경·두께 round(선형), 글로우 알파 앞 + trunc(차 × t).
     * - 채우기: 바깥 경계 오브젝트가 모두 짝 있는 것만 후보. 같은 경계(오브젝트·윤곽·T)끼리, 다음으로 T를 뺀 경계가 양쪽에 하나뿐인 것끼리 짝.
     *   짝은 색·T를 섞고, 짝 없는 앞 채우기는 그대로, 짝 없는 뒤 채우기는 그리지 않는다.
     * 근사: 수동 TweenLink, 경계 회전·방향 정규화, AP 참조 비교는 넣지 않았다(뷰어 문서 참고).
     */
    private fun prepareTween(fa: Int, fb: Int, t: Float) {
        val d = doc
        if (mapFrame != fb) {
            idMap.clear()
            for (o in d.fObjStart[fb] until d.fObjStart[fb] + d.fObjCount[fb]) idMap[d.oId[o]] = o
            mapFrame = fb
        }
        val o0 = d.fObjStart[fa]; val on = d.fObjCount[fa]
        val p0 = if (on > 0) d.oPtStart[o0] else 0
        val pe = if (on > 0) d.oPtStart[o0 + on - 1] + d.oPtCount[o0 + on - 1] else p0
        val np = pe - p0
        if (tx.size < np) { tx = FloatArray(np); ty = FloatArray(np) }
        if (tOn.size < on) { tOn = BooleanArray(on); tCol = IntArray(on); tTh = FloatArray(on); tGR = FloatArray(on); tGT = FloatArray(on); tGC = IntArray(on); tGA = FloatArray(on) }
        tp0 = p0; to0 = o0
        val paired = HashSet<Int>()
        for (k in 0 until on) {
            val o = o0 + k
            val st = d.oPtStart[o]; val n = d.oPtCount[o].toInt()
            for (i in 0 until n) { tx[st + i - p0] = d.px[st + i]; ty[st + i - p0] = d.py[st + i] }
            val ob = idMap[d.oId[o]]
            tOn[k] = ob != null
            if (ob == null) continue
            paired.add(d.oId[o])
            val sb = d.oPtStart[ob]; val nb = d.oPtCount[ob].toInt()
            for (i in 0 until n) {
                val idx = d.pIdx[st + i]
                var m = -1
                if (i < nb && d.pIdx[sb + i] == idx) m = sb + i
                else for (q in 0 until nb) if (d.pIdx[sb + q] == idx) { m = sb + q; break }
                if (m >= 0) {
                    tx[st + i - p0] = d.px[st + i] + (d.px[m] - d.px[st + i]) * t
                    ty[st + i - p0] = d.py[st + i] + (d.py[m] - d.py[st + i]) * t
                }
            }
            tCol[k] = lerpArgb(d.oColor[o], d.oColor[ob], t)
            tTh[k] = d.oThick[o] + (d.oThick[ob] - d.oThick[o]) * t
            tGR[k] = roundAway(d.oGlowR[o] + (d.oGlowR[ob] - d.oGlowR[o]) * t)
            tGT[k] = roundAway(d.oGlowT[o] + (d.oGlowT[ob] - d.oGlowT[o]) * t)
            tGC[k] = lerpArgb(d.oGlowColor[o], d.oGlowColor[ob], t)
            val a0 = d.oGlowA[o]; val a1 = d.oGlowA[ob]
            tGA[k] = if (maxOf(a0, a1) > 1f) a0 + ((a1 - a0) * t).toInt() else a0 + (a1 - a0) * t
        }
        // 채우기
        val f0 = d.fFillStart[fa]; val fn = d.fFillCount[fa]
        val g0 = d.fFillStart[fb]; val gn = d.fFillCount[fb]
        if (tFlOn.size < fn) { tFlOn = BooleanArray(fn); tFlCol = IntArray(fn) }
        tf0 = f0
        val s0 = if (fn > 0) d.flSegStart[f0] else 0
        val se = if (fn > 0) d.flSegStart[f0 + fn - 1] + d.flSegCount[f0 + fn - 1] else s0
        if (tS0.size < se - s0) { tS0 = FloatArray(se - s0); tS1 = FloatArray(se - s0) }
        ts0 = s0
        for (k in s0 until se) { tS0[k - s0] = d.sT0[k]; tS1[k - s0] = d.sT1[k] }
        fun ok(fl: Int): Boolean {
            var outer = 0
            for (k in d.flSegStart[fl] until d.flSegStart[fl] + d.flSegCount[fl]) {
                if (d.sCont[k] != 0) continue
                outer++
                val o = d.sObj[k]; if (o < 0 || d.oId[o] !in paired) return false
            }
            return outer > 0
        }
        fun key(fl: Int, withT: Boolean): String {
            val b = StringBuilder()
            for (k in d.flSegStart[fl] until d.flSegStart[fl] + d.flSegCount[fl]) {
                val o = d.sObj[k]
                b.append(d.sCont[k]).append(':').append(if (o < 0) "*" else d.oId[o].toString())
                if (withT) b.append(':').append(d.sT0[k]).append(':').append(d.sT1[k])
                b.append(';')
            }
            return b.toString()
        }
        val aList = (f0 until f0 + fn).filter { ok(it) }
        val bList = (g0 until g0 + gn).filter { ok(it) }
        for (i in 0 until fn) { tFlOn[i] = false; tFlCol[i] = d.flColor[f0 + i] }
        val pair = HashMap<Int, Int>()
        val usedB = HashSet<Int>()
        val q1 = HashMap<String, ArrayDeque<Int>>()
        for (g in bList) q1.getOrPut(key(g, true)) { ArrayDeque() }.add(g)
        for (fl in aList) q1[key(fl, true)]?.removeFirstOrNull()?.let { pair[fl] = it; usedB.add(it) }
        val ra = aList.filter { it !in pair }; val rb = bList.filter { it !in usedB }
        val ka = ra.groupBy { key(it, false) }; val kb = rb.groupBy { key(it, false) }
        for ((k, la) in ka) { val lb = kb[k]; if (la.size == 1 && lb != null && lb.size == 1) pair[la[0]] = lb[0] }
        for (fl in aList) {
            tFlOn[fl - f0] = true
            val g = pair[fl] ?: continue // 짝 없는 앞 채우기: 그대로
            tFlCol[fl - f0] = lerpArgb(d.flColor[fl], d.flColor[g], t)
            if (d.flSegCount[fl] == d.flSegCount[g]) for (i in 0 until d.flSegCount[fl]) {
                val ka2 = d.flSegStart[fl] + i; val kb2 = d.flSegStart[g] + i
                tS0[ka2 - s0] = d.sT0[ka2] + (d.sT0[kb2] - d.sT0[ka2]) * t
                tS1[ka2 - s0] = d.sT1[ka2] + (d.sT1[kb2] - d.sT1[ka2]) * t
            }
        }
        tw = true
    }

    private fun roundAway(v: Float): Float = if (v >= 0f) kotlin.math.floor(v + 0.5f) else -kotlin.math.floor(-v + 0.5f)

    /** Frame.InterpolateArgbColor: 채널마다 앞값 + round(차 × t), 0–255. */
    private fun lerpArgb(a: Int, b: Int, t: Float): Int {
        var r = 0
        for (sh in intArrayOf(24, 16, 8, 0)) {
            val ca = (a ushr sh) and 255; val cb = (b ushr sh) and 255
            val c = (ca + roundAway((cb - ca) * t).toInt()).coerceIn(0, 255)
            r = r or (c shl sh)
        }
        return r
    }

    var tGlow = 0L; var tFill = 0L; var tBase = 0L; var nGlowBig = 0
    private fun draw(f: Int, c: Canvas, s: Float) {
        val o0 = doc.fObjStart[f]; val on = doc.fObjCount[f]
        val f0 = doc.fFillStart[f]; val fn = doc.fFillCount[f]
        // 채우기의 주인 = 첫 번째 유효 경계 오브젝트
        val owned = HashMap<Int, MutableList<Int>>()
        for (fl in f0 until f0 + fn) {
            var owner = -1
            for (k in doc.flSegStart[fl] until doc.flSegStart[fl] + doc.flSegCount[fl]) if (doc.sObj[k] >= 0) { owner = doc.sObj[k]; break }
            owned.getOrPut(owner) { ArrayList(2) }.add(fl)
        }
        val drawn = BooleanArray(fn)
        val l0 = doc.fLayerStart[f]
        for (li in l0 until l0 + doc.fLayerCount[f]) {
            if (!doc.lVisible[li]) continue
            val lid = doc.lId[li]
            val objs = (o0 until o0 + on).filter { doc.oLayer[it] == lid && (!tw || tOn[it - to0]) }.sortedBy { doc.oOrder[it] }
            val units = LinkedHashMap<Int, MutableList<Int>>()
            for (o in objs) units.getOrPut(doc.oGroup[o]) { ArrayList(4) }.add(o)
            for (u in units.values) {
                var t = System.nanoTime(); for (o in u) drawGlow(o, c, s); tGlow += System.nanoTime() - t
                for (o in u) {
                    t = System.nanoTime()
                    owned[o]?.forEach { fl -> if (!drawn[fl - f0]) { drawn[fl - f0] = true; drawFill(fl, c) } }
                    tFill += System.nanoTime() - t; t = System.nanoTime()
                    drawBase(o, c); tBase += System.nanoTime() - t
                }
            }
        }
        for (fl in f0 until f0 + fn) if (!drawn[fl - f0]) drawFill(fl, c)
    }

}
