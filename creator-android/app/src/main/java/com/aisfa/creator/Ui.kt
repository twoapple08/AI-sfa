package com.aisfa.creator

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.FrameLayout

/** 다크 테마. 질감은 Stick Fighter 최신 화면(주황 강조, 둥근 카드·알약 탭, 주황 원형 버튼)을 따르고 색만 어둡게 바꾼다. */
object Theme {
    const val BG = 0xFF121316.toInt()
    const val SURFACE = 0xFF1D1F24.toInt()
    const val CARD = 0xFF25272D.toInt()
    const val FIELD = 0xFF2E3037.toInt()
    const val ORANGE = 0xFFFF8C3B.toInt()
    const val TEXT = 0xFFF1F1F3.toInt()
    const val SUB = 0xFF9A9DA6.toInt()
    const val ICON = 0xFFCFD1D8.toInt()
    const val TRACK = 0xFF3A3D45.toInt()

    fun round(color: Int, radiusPx: Float) = GradientDrawable().apply { setColor(color); cornerRadius = radiusPx }
    fun oval(color: Int) = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(color) }
}

/** 리소스 없이 Path로 그리는 단색 아이콘. */
class IconView(ctx: Context, var kind: Kind, var color: Int = Theme.ICON) : View(ctx) {
    enum class Kind { PLAY, PAUSE, PREV, NEXT, BACK, UPLOAD, PLUS, MORE, DICE, SAVE }
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
            Kind.DICE -> {
                p.style = Paint.Style.STROKE; p.strokeWidth = s * 0.1f
                c.drawRoundRect(l, t, l + s, t + s, s * 0.2f, s * 0.2f, p)
                p.style = Paint.Style.FILL; val r = s * 0.09f
                for ((dx, dy) in listOf(0.28f to 0.28f, 0.72f to 0.72f, 0.5f to 0.5f, 0.72f to 0.28f, 0.28f to 0.72f)) c.drawCircle(l + s * dx, t + s * dy, r, p)
            }
            Kind.SAVE -> {
                path.moveTo(cx, t + s * 0.62f); path.lineTo(l + s * 0.92f, t + s * 0.2f); path.lineTo(l + s * 0.64f, t + s * 0.2f)
                path.lineTo(l + s * 0.64f, t); path.lineTo(l + s * 0.36f, t); path.lineTo(l + s * 0.36f, t + s * 0.2f)
                path.lineTo(l + s * 0.08f, t + s * 0.2f); path.close(); c.drawPath(path, p)
                c.drawRect(l + s * 0.08f, t + s * 0.88f, l + s * 0.92f, t + s, p)
            }
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
