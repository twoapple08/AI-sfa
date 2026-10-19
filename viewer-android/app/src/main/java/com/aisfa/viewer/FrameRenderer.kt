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

    private fun X(i: Int) = ox + uw * doc.px[i] / 100f
    private fun Y(i: Int) = oy + uh * doc.py[i] / 100f

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

    private fun drawFill(fl: Int, c: Canvas) {
        val col = doc.flColor[fl]
        if ((col ushr 24) == 0) return
        fpath.rewind(); fpath.fillType = Path.FillType.EVEN_ODD
        var started = false; var startIdx = 0
        sn = 0
        val s0 = doc.flSegStart[fl]
        for (k in s0 until s0 + doc.flSegCount[fl]) {
            val o = doc.sObj[k]; if (o < 0) continue
            val before = sn
            segPoints(o, doc.sT0[k], doc.sT1[k])
            if (sn == before) continue
            if (started && hypot(sx[before] - sx[before - 1], sy[before] - sy[before - 1]) > GAP) {
                emit(startIdx, before); startIdx = before
            }
            started = true
        }
        if (sn > startIdx) emit(startIdx, sn)
        fill.color = col
        c.drawPath(fpath, fill)
    }

    private fun emit(a: Int, b: Int) {
        if (b - a < 3) return
        fpath.moveTo(sx[a], sy[a]); for (i in a + 1 until b) fpath.lineTo(sx[i], sy[i]); fpath.close()
    }

    private fun drawBase(o: Int, c: Canvas) {
        val col = doc.oColor[o]
        if ((col ushr 24) == 0) return
        val w = 8f * max(doc.oThick[o], 0f)
        if (w <= 0f) return
        stroke.color = col
        stroke.strokeWidth = max((1.14f * w).roundToInt().toFloat(), 0.5f)
        if (objPath(o, path)) c.drawPath(path, stroke)
    }

    private val tmpRect = RectF()

    private fun drawGlow(o: Int, c: Canvas, s: Float) {
        val gr = doc.oGlowR[o]; val gt = doc.oGlowT[o]; var ga = doc.oGlowA[o]
        if (gr <= 0f || gt <= 0f || ga <= 0f) return
        if (ga > 1f) ga /= 255f
        val wg = 8f * max(doc.oThick[o], 0f) * max(gt / 10f, 0f)
        val sig = sqrt(gr * gr + 0.29f * 0.29f)
        if (!objPath(o, path)) return
        val gc = doc.oGlowColor[o]
        val color = (((ga.coerceIn(0f, 1f) * 255f).roundToInt()) shl 24) or (gc and 0xFFFFFF)
        val sigPx = sig * s
        if (sigPx < 4f) {
            glowPaint.color = color; glowPaint.strokeWidth = wg
            glowPaint.maskFilter = if (sigPx > 0.5f) BlurMaskFilter(max((sig - 0.5f / s) / 0.57735f, 0.1f), BlurMaskFilter.Blur.NORMAL) else null
            c.drawPath(path, glowPaint)
            glowPaint.maskFilter = null
            return
        }
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
            val objs = (o0 until o0 + on).filter { doc.oLayer[it] == lid }.sortedBy { doc.oOrder[it] }
            val units = LinkedHashMap<Int, MutableList<Int>>()
            for (o in objs) units.getOrPut(doc.oGroup[o]) { ArrayList(4) }.add(o)
            for (u in units.values) {
                for (o in u) drawGlow(o, c, s)
                for (o in u) {
                    owned[o]?.forEach { fl -> if (!drawn[fl - f0]) { drawn[fl - f0] = true; drawFill(fl, c) } }
                    drawBase(o, c)
                }
            }
        }
        for (fl in f0 until f0 + fn) if (!drawn[fl - f0]) drawFill(fl, c)
    }

    companion object { const val GAP = 1.5f }
}
