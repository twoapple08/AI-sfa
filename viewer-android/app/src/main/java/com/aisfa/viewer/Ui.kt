package com.aisfa.viewer

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.FrameLayout

/** 색·모양은 Stick Fighter 최신 화면의 느낌(밝은 회색 바탕, 주황 강조, 둥근 카드)을 따른다. 배치는 우리 뷰어에 맞춘다. */
object Theme {
    const val BG = 0xFFF9F9F9.toInt()
    const val SURFACE = 0xFFEFEFEF.toInt()
    const val CARD = 0xFFFFFFFF.toInt()
    const val ORANGE = 0xFFFF8C3B.toInt()
    const val TEXT = 0xFF222222.toInt()
    const val SUB = 0xFF8A8A8A.toInt()
    const val ICON = 0xFF555555.toInt()
    const val TRACK = 0xFFDADDE1.toInt()

    fun round(color: Int, radiusPx: Float) = GradientDrawable().apply { setColor(color); cornerRadius = radiusPx }
    fun oval(color: Int) = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(color) }
}

/** 리소스 없이 Path로 그리는 단색 아이콘. */
class IconView(ctx: Context, var kind: Kind, var color: Int = Theme.ICON) : View(ctx) {
    enum class Kind { PLAY, PAUSE, PREV, NEXT, BACK, UPLOAD, PLUS, MORE }
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    private val path = Path()
    fun set(k: Kind) { if (k != kind) { kind = k; invalidate() } }

    override fun onDraw(c: Canvas) {
        val s = minOf(width, height) * 0.5f
        val cx = width / 2f; val cy = height / 2f
        val l = cx - s / 2; val t = cy - s / 2
        p.color = if (isEnabled) color else Color.argb(90, Color.red(color), Color.green(color), Color.blue(color))
        p.style = Paint.Style.FILL; p.strokeCap = Paint.Cap.ROUND; p.strokeJoin = Paint.Join.ROUND
        path.rewind()
        when (kind) {
            Kind.PLAY -> { path.moveTo(l + s * 0.12f, t); path.lineTo(l + s, cy); path.lineTo(l + s * 0.12f, t + s); path.close(); c.drawPath(path, p) }
            Kind.PAUSE -> { val w = s * 0.3f; c.drawRect(l + s * 0.08f, t, l + s * 0.08f + w, t + s, p); c.drawRect(l + s * 0.92f - w, t, l + s * 0.92f, t + s, p) }
            Kind.PREV -> { path.moveTo(l + s * 0.75f, t + s * 0.2f); path.lineTo(l + s * 0.3f, cy); path.lineTo(l + s * 0.75f, t + s * 0.8f); path.close(); c.drawPath(path, p) }
            Kind.NEXT -> { path.moveTo(l + s * 0.25f, t + s * 0.2f); path.lineTo(l + s * 0.7f, cy); path.lineTo(l + s * 0.25f, t + s * 0.8f); path.close(); c.drawPath(path, p) }
            Kind.BACK -> {
                p.style = Paint.Style.STROKE; p.strokeWidth = s * 0.14f
                path.moveTo(l + s * 0.7f, t + s * 0.05f); path.lineTo(l + s * 0.25f, cy); path.lineTo(l + s * 0.7f, t + s * 0.95f); c.drawPath(path, p)
            }
            Kind.UPLOAD -> {
                path.moveTo(cx, t); path.lineTo(l + s * 0.92f, t + s * 0.45f); path.lineTo(l + s * 0.64f, t + s * 0.45f)
                path.lineTo(l + s * 0.64f, t + s * 0.78f); path.lineTo(l + s * 0.36f, t + s * 0.78f); path.lineTo(l + s * 0.36f, t + s * 0.45f)
                path.lineTo(l + s * 0.08f, t + s * 0.45f); path.close(); c.drawPath(path, p)
                c.drawRect(l + s * 0.08f, t + s * 0.9f, l + s * 0.92f, t + s, p)
            }
            Kind.PLUS -> { p.style = Paint.Style.STROKE; p.strokeWidth = s * 0.12f; c.drawLine(cx, t + s * 0.1f, cx, t + s * 0.9f, p); c.drawLine(l + s * 0.1f, cy, l + s * 0.9f, cy, p) }
            Kind.MORE -> { val r = s * 0.11f; for (i in -1..1) c.drawCircle(cx + i * s * 0.36f, cy, r, p) }
        }
    }
}

/** 세로 화면에서 영상 칸: 폭에 맞추고 높이는 폭×비율(유튜브 세로 보기처럼 위쪽에 둔다). 너무 길면 화면 높이의 maxFrac까지만. */
class AspectBox(ctx: Context) : FrameLayout(ctx) {
    var ratio = 0.5625f
        set(v) { field = v; requestLayout() }
    var maxFrac = 0.6f
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val w = MeasureSpec.getSize(widthMeasureSpec)
        // 가로 화면처럼 부모가 높이를 정해 주면(weight) 그대로 쓰고, 세로 화면에서는 폭×비율로 정한다
        val h = if (MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.EXACTLY) MeasureSpec.getSize(heightMeasureSpec)
        // 멀티윈도우·팝업 창에서는 화면 전체가 아니라 지금 창 높이를 기준으로 한다
        else minOf((w * ratio).toInt(), (resources.configuration.screenHeightDp * resources.displayMetrics.density * maxFrac).toInt())
        super.onMeasure(MeasureSpec.makeMeasureSpec(w, MeasureSpec.EXACTLY), MeasureSpec.makeMeasureSpec(h, MeasureSpec.EXACTLY))
    }
}
