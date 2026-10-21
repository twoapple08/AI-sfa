package com.aisfa.creator

import android.app.Activity
import android.app.AlertDialog
import android.content.ContentValues
import android.content.Intent
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Outline
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.MediaStore
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.view.WindowInsets
import android.view.WindowManager
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.NumberPicker
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import com.aisfa.creator.gen.Generated
import com.aisfa.creator.gen.Generator
import com.aisfa.creator.gen.MotionLib
import com.aisfa.creator.gen.Request
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.roundToInt

/**
 * SFA 생성기. 첫 화면에서 프롬프트·길이·FPS(트위닝, 재생)를 정해 기기 안에서 만들고,
 * 결과 화면(SFA 뷰어 1.0의 플레이어)에서 미리 보고 5초 단위 SFA 파일로 저장한다.
 */
class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private val lib by lazy { assets.open("motion_lib.txt").use { MotionLib.read(it) } }

    // 플레이어 화면 부품: 회전할 때 다시 배치만 하고 새로 만들지 않는다
    private lateinit var view: FrameView
    private lateinit var title: TextView
    private lateinit var status: TextView
    private lateinit var frameLabel: TextView
    private lateinit var timeLabel: TextView
    private lateinit var info: TextView
    private lateinit var seek: SeekBar
    private lateinit var playBtn: IconView
    private lateinit var prevBtn: IconView
    private lateinit var nextBtn: IconView
    private lateinit var backBtn: IconView
    private lateinit var saveIcon: IconView
    private lateinit var saveBtn: TextView
    private lateinit var exportBtn: TextView
    private lateinit var againBtn: TextView
    private lateinit var fpsBtn: TextView
    private lateinit var partsRow: LinearLayout
    private val videoBox by lazy { AspectBox(this).apply { setBackgroundColor(Color.BLACK) } }
    private var onPlayer = false
    private var doc: SfaDoc? = null
    private var cache: FrameCache? = null
    private var cur: Gen? = null
    private val playing = AtomicBoolean(false)
    private val wanted = AtomicInteger(0)
    private var renderThread: Thread? = null
    private val busy = AtomicBoolean(false)
    private val exporting = AtomicBoolean(false)
    private val cancelExport = AtomicBoolean(false)
    private var tl = Timeline(0, 24, 24)
    private val fps get() = tl.fps

    // 첫 화면 입력값(회전해도 유지)
    private var prompt = "1v1"
    private var seconds = 10
    private var tween = 24
    private var play = 24
    private var seed = System.currentTimeMillis() % 100000
    private var dark = false
    private var homeScroll = 0

    /** 저장된 생성 결과 하나: gens/<id>/ 안에 meta.json, preview.sfa(전체), parts 폴더(5초 단위 SFA), thumb.jpg. */
    private class Gen(val dir: File, val meta: JSONObject) {
        val id get() = dir.name
        val name get() = meta.optString("name")
        val req get() = Request(meta.optString("prompt"), meta.optInt("seconds"), meta.optInt("tween"), meta.optInt("play"), meta.optLong("seed"), meta.optBoolean("dark"))
        val parts get() = File(dir, "parts").listFiles()?.sortedBy { it.name.substringAfterLast('_').substringBefore('.').toIntOrNull() ?: 0 } ?: emptyList()
    }

    private fun dp(v: Float) = (v * resources.displayMetrics.density).roundToInt()
    private fun dp(v: Int) = dp(v.toFloat())
    // 멀티윈도우·팝업 창·폴드 펼침에서는 기기 방향이 아니라 지금 창의 크기로 배치를 정한다
    private val winW get() = resources.configuration.screenWidthDp
    private val winH get() = resources.configuration.screenHeightDp
    private val landscape get() = winW > winH
    private val compact get() = winH < 480 || winW < 340
    private val wide get() = winW >= 600 && !compact

    /** targetSdk 35는 화면이 상태 표시줄·홈 버튼 바 밑까지 그려진다. 그 높이만큼 안쪽 여백을 준다. */
    private fun edge(root: View): View {
        root.setOnApplyWindowInsetsListener { v, ins ->
            if (Build.VERSION.SDK_INT >= 30) {
                val b = ins.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
                v.setPadding(b.left, b.top, b.right, b.bottom)
            } else {
                @Suppress("DEPRECATION")
                v.setPadding(ins.systemWindowInsetLeft, ins.systemWindowInsetTop, ins.systemWindowInsetRight, ins.systemWindowInsetBottom)
            }
            ins
        }
        root.requestApplyInsets()
        return root
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = Theme.BG
        window.navigationBarColor = Theme.BG
        val p = getSharedPreferences("c", MODE_PRIVATE)
        prompt = p.getString("prompt", prompt)!!; seconds = p.getInt("seconds", seconds)
        tween = p.getInt("tween", tween); play = p.getInt("play", play); dark = p.getBoolean("dark", dark)
        makePlayerParts()
        showHome()
    }

    private fun savePrefs() {
        getSharedPreferences("c", MODE_PRIVATE).edit().putString("prompt", prompt).putInt("seconds", seconds)
            .putInt("tween", tween).putInt("play", play).putBoolean("dark", dark).apply()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        if (onPlayer) showPlayer() else showHome()
    }

    @Deprecated("Back")
    override fun onBackPressed() {
        if (!onPlayer) { @Suppress("DEPRECATION") super.onBackPressed(); return }
        if (exporting.get()) { Toast.makeText(this, "내보내기 중입니다. 먼저 취소하세요", Toast.LENGTH_SHORT).show(); return }
        closePlayer(); showHome()
    }

    // ───────── 공통 부품 ─────────

    private fun text(size: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
        setTextSize(TypedValue.COMPLEX_UNIT_SP, size); setTextColor(color)
        if (bold) typeface = Typeface.create("sans-serif-medium", Typeface.BOLD)
        includeFontPadding = false
    }

    private fun icon(kind: IconView.Kind, color: Int = Theme.ICON, onClick: () -> Unit) = IconView(this, kind, color).apply {
        isClickable = true; setOnClickListener { onClick() }
        background = android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(0x33FFFFFF), null, Theme.oval(Color.WHITE))
    }

    private fun pillButton(label: String, fill: Int, fg: Int, onClick: () -> Unit) = text(15f, fg, true).apply {
        gravity = Gravity.CENTER; text = label; background = Theme.round(fill, dp(24).toFloat())
        setPadding(dp(20), dp(14), dp(20), dp(14)); setOnClickListener { onClick() }
    }

    private fun card() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; background = Theme.round(Theme.SURFACE, dp(22).toFloat())
        setPadding(dp(if (compact) 14 else 20), dp(if (compact) 12 else 18), dp(if (compact) 14 else 20), dp(if (compact) 12 else 18))
    }

    private fun detach(v: View) { (v.parent as? ViewGroup)?.removeView(v) }

    private fun makePlayerParts() {
        view = FrameView(this)
        title = text(20f, Theme.ORANGE, true).apply { gravity = Gravity.CENTER; maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END }
        status = text(12f, Theme.SUB).apply { gravity = Gravity.CENTER }
        frameLabel = text(16f, Theme.TEXT, true)
        timeLabel = text(14f, Theme.ORANGE, true)
        info = text(13f, Theme.SUB).apply { setLineSpacing(0f, 1.35f) }
        seek = SeekBar(this).apply {
            progressTintList = ColorStateList.valueOf(Theme.ORANGE)
            progressBackgroundTintList = ColorStateList.valueOf(Theme.TRACK)
            thumbTintList = ColorStateList.valueOf(Theme.ORANGE)
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(sb: SeekBar, p: Int, fromUser: Boolean) { if (fromUser) { wanted.set(p); updateLabels(p); kick() } }
                override fun onStartTrackingTouch(sb: SeekBar) { setPlaying(false) }
                override fun onStopTrackingTouch(sb: SeekBar) {}
            })
        }
        playBtn = icon(IconView.Kind.PLAY, Theme.ORANGE) { togglePlay() }
        prevBtn = icon(IconView.Kind.PREV) { step(-1) }
        nextBtn = icon(IconView.Kind.NEXT) { step(1) }
        backBtn = icon(IconView.Kind.BACK, Theme.TEXT) { onBackPressed() }
        saveIcon = icon(IconView.Kind.SAVE) { saveSfa() }
        saveBtn = pillButton("SFA 파일 저장", Theme.ORANGE, Color.WHITE) { saveSfa() }
        exportBtn = pillButton("MP4 내보내기", Theme.CARD, Theme.TEXT) { exportOrCancel() }
        againBtn = pillButton("다시 생성(새 시드)", Theme.CARD, Theme.TEXT) { regenerate() }
        fpsBtn = text(14f, Theme.TEXT, true).apply {
            gravity = Gravity.CENTER; background = Theme.round(Theme.CARD, dp(20).toFloat())
            setPadding(dp(16), dp(10), dp(16), dp(10)); setOnClickListener { askFps(true) }
        }
        partsRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        view.setOnClickListener { togglePlay() }
        setControlsEnabled(false)
    }

    private fun setControlsEnabled(on: Boolean) {
        for (v in listOf(playBtn, prevBtn, nextBtn, saveIcon, seek, fpsBtn)) v.isEnabled = on
        for (b in listOf(fpsBtn, saveBtn, exportBtn, againBtn)) { b.isEnabled = on; b.alpha = if (on) 1f else 0.4f }
        saveIcon.invalidate(); playBtn.invalidate(); prevBtn.invalidate(); nextBtn.invalidate()
    }

    // ───────── 첫 화면: 프롬프트·설정·생성, 최근 생성 ─────────

    private fun showHome() {
        onPlayer = false
        val root = FrameLayout(this).apply { setBackgroundColor(Theme.BG) }
        val pad = if (compact) 12 else 18
        val head = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        head.addView(text(if (compact) 26f else if (landscape) 30f else 36f, Theme.ORANGE, true).apply {
            text = "SFA CREATOR"; gravity = Gravity.CENTER; letterSpacing = -0.02f
            typeface = if (Build.VERSION.SDK_INT >= 28) Typeface.create(Typeface.DEFAULT, 900, false) else Typeface.DEFAULT_BOLD
            paint.isFakeBoldText = true
        }, LinearLayout.LayoutParams(-1, -2))
        if (!compact && winW >= 360) head.addView(text(13f, Theme.SUB).apply { text = "프롬프트로 Stick Fighter 애니메이션 만들기 · 기기 안에서"; gravity = Gravity.CENTER },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })

        val form = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        form.addView(tabs(), LinearLayout.LayoutParams(-2, -2).apply { gravity = Gravity.CENTER_HORIZONTAL; topMargin = dp(if (compact) 10 else 22); bottomMargin = dp(if (compact) 10 else 16) })
        form.addView(promptCard(), LinearLayout.LayoutParams(-1, -2))
        form.addView(settingsCard(), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        form.addView(pillButton("생성하기", Theme.ORANGE, Color.WHITE) { generate() }.apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f); setPadding(dp(20), dp(if (compact) 12 else 17), dp(20), dp(if (compact) 12 else 17))
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) })

        val recent = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        recentList(recent, if (wide) (winW / 2 - 40) else winW)

        val scroll = ScrollView(this)
        if (wide) {
            // 넓은 창(폴드 펼침·가로): 왼쪽 입력, 오른쪽 최근 생성
            val cols = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            val left = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
            left.addView(head); left.addView(form)
            cols.addView(left, LinearLayout.LayoutParams(0, -2, 1f).apply { marginEnd = dp(12) })
            cols.addView(recent, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(12); topMargin = dp(8) })
            scroll.addView(cols.apply { setPadding(dp(pad + 6), dp(if (landscape) 16 else 28), dp(pad + 6), dp(24)) })
        } else {
            val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(pad), dp(if (compact) 10 else if (landscape) 16 else 30), dp(pad), dp(24)) }
            list.addView(head); list.addView(form)
            list.addView(recent, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(26) })
            scroll.addView(list)
        }
        scroll.post { scroll.scrollTo(0, homeScroll) }
        scroll.viewTreeObserver.addOnScrollChangedListener { homeScroll = scroll.scrollY }
        root.addView(scroll, FrameLayout.LayoutParams(-1, -1))
        setContentView(edge(root))
    }

    /** 입력 방식 탭. 지금은 태그만 된다(자연어·스토리보드는 나중에). */
    private fun tabs(): View {
        val pill = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; background = Theme.round(Theme.SURFACE, dp(28).toFloat()); setPadding(dp(5), dp(5), dp(5), dp(5)) }
        for ((i, label) in listOf("태그", "자연어", "스토리보드").withIndex()) {
            pill.addView(text(14f, if (i == 0) Theme.TEXT else Theme.SUB, i == 0).apply {
                text = label; gravity = Gravity.CENTER
                if (i == 0) background = Theme.round(Theme.CARD, dp(24).toFloat())
                setPadding(dp(if (compact) 16 else 22), dp(11), dp(if (compact) 16 else 22), dp(11))
                if (i != 0) setOnClickListener { Toast.makeText(this@MainActivity, "$label 입력은 준비 중입니다. 지금은 태그(1v1)만 됩니다", Toast.LENGTH_SHORT).show() }
            })
        }
        return pill
    }

    private fun promptCard(): View {
        val c = card()
        c.addView(text(15f, Theme.TEXT, true).apply { text = "프롬프트" })
        val edit = EditText(this).apply {
            setText(prompt); setTextColor(Theme.TEXT); setHintTextColor(Theme.SUB); hint = "태그를 쉼표로 구분 (예: 1v1)"
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f); background = Theme.round(Theme.FIELD, dp(14).toFloat())
            setPadding(dp(14), dp(12), dp(14), dp(12)); minLines = 2; gravity = Gravity.TOP or Gravity.START
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            addTextChangedListener(object : android.text.TextWatcher {
                override fun afterTextChanged(s: android.text.Editable?) { prompt = s?.toString() ?: ""; savePrefs() }
                override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, d: Int) {}
                override fun onTextChanged(s: CharSequence?, a: Int, b: Int, d: Int) {}
            })
        }
        c.addView(edit, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        val chips = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        for (tag in Generator.SUPPORTED) chips.addView(text(14f, Theme.ORANGE, true).apply {
            text = "+ $tag"; background = Theme.round(0x33FF8C3B, dp(16).toFloat()); setPadding(dp(14), dp(8), dp(14), dp(8))
            setOnClickListener {
                val t = Generator.tags(edit.text.toString())
                if (tag !in t) edit.setText((t + tag).joinToString(", "))
            }
        }, LinearLayout.LayoutParams(-2, -2).apply { marginEnd = dp(8) })
        c.addView(HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(chips) }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        c.addView(text(12f, Theme.SUB).apply {
            text = "지금 되는 태그: 1v1 (맨손 둘, 도구·배경 없음). 다른 태그는 무시됩니다."; setLineSpacing(0f, 1.3f)
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        return c
    }

    private fun row(label: String, sub: String?, right: View): View {
        val r = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, dp(8), 0, dp(8)) }
        val texts = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        texts.addView(text(15f, Theme.TEXT).apply { text = label })
        if (sub != null) texts.addView(text(12f, Theme.SUB).apply { text = sub }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(4) })
        r.addView(texts, LinearLayout.LayoutParams(0, -2, 1f))
        r.addView(right, LinearLayout.LayoutParams(-2, -2))
        return r
    }

    private fun valueChip(label: String, onClick: () -> Unit) = text(15f, Theme.TEXT, true).apply {
        text = label; gravity = Gravity.CENTER; background = Theme.round(Theme.CARD, dp(20).toFloat())
        setPadding(dp(16), dp(10), dp(16), dp(10)); setOnClickListener { onClick() }
    }

    private fun settingsCard(): View {
        val c = card()
        c.addView(text(15f, Theme.TEXT, true).apply { text = "설정" })
        val files = (seconds + 4) / 5
        c.addView(row("총 길이", "5초마다 SFA 파일 1개 → ${files}개", valueChip("${seconds}초") { askSeconds() }), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(6) })
        c.addView(row("FPS (트위닝, 재생)", if (tween > play) "트위닝이 크면 Stick Fighter가 사이를 섞어 보여 줍니다" else "파일 하나 = ${5 * play}프레임",
            valueChip("$tween, $play") { askFps(false) }))
        val bgPill = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; background = Theme.round(Theme.CARD, dp(20).toFloat()); setPadding(dp(4), dp(4), dp(4), dp(4)) }
        for ((i, label) in listOf("흰색", "검정").withIndex()) {
            val on = (i == 1) == dark
            bgPill.addView(text(14f, if (on) Color.WHITE else Theme.SUB, on).apply {
                text = label; gravity = Gravity.CENTER; setPadding(dp(14), dp(7), dp(14), dp(7))
                if (on) background = Theme.round(Theme.ORANGE, dp(16).toFloat())
                setOnClickListener { dark = i == 1; savePrefs(); showHome() }
            })
        }
        c.addView(row("배경", "그림 바탕색(앱 화면은 늘 어둡게)", bgPill))
        val seedRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        seedRow.addView(valueChip("$seed") { askSeed() })
        seedRow.addView(icon(IconView.Kind.DICE, Theme.ORANGE) { seed = (Math.random() * 100000).toLong(); showHome() }, LinearLayout.LayoutParams(dp(44), dp(44)).apply { marginStart = dp(4) })
        c.addView(row("시드", "같은 시드·설정이면 같은 결과", seedRow))
        return c
    }

    private fun picker(min: Int, max: Int, v: Int) = NumberPicker(this).apply { minValue = min; maxValue = max; value = v.coerceIn(min, max); wrapSelectorWheel = false }

    private fun askSeconds() {
        val p = picker(1, 120, seconds)
        AlertDialog.Builder(this).setTitle("총 길이(초)").setView(p)
            .setPositiveButton("적용") { _, _ -> seconds = p.value; savePrefs(); showHome() }
            .setNegativeButton("취소", null).show()
    }

    private fun askSeed() {
        val e = EditText(this).apply { setText("$seed"); inputType = InputType.TYPE_CLASS_NUMBER; setPadding(dp(24), dp(16), dp(24), dp(16)) }
        AlertDialog.Builder(this).setTitle("시드").setView(e)
            .setPositiveButton("적용") { _, _ -> e.text.toString().toLongOrNull()?.let { seed = it }; showHome() }
            .setNegativeButton("취소", null).show()
    }

    /** (T, P) 고르기. 결과 화면에서 바꾸면 같은 시드로 다시 만든다(싸움 내용은 같고 프레임만 다시 고른다). */
    private fun askFps(fromPlayer: Boolean) {
        if (exporting.get()) return
        val t0 = if (fromPlayer) cur?.req?.tween ?: tween else tween
        val p0 = if (fromPlayer) cur?.req?.play ?: play else play
        val pt = picker(1, 120, t0); val pp = picker(1, 120, p0)
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(12), dp(24), 0) }
        box.addView(text(13f, Theme.SUB).apply {
            text = "Stick Fighter에서 쓸 값을 넣으세요. SFA 파일에는 저장되지 않습니다.\n파일 하나는 5초 = 5×재생 fps 프레임입니다."
            setLineSpacing(0f, 1.3f)
        })
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        for ((label, p) in listOf("트위닝" to pt, "재생" to pp)) {
            val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER_HORIZONTAL }
            col.addView(text(14f, Theme.TEXT, true).apply { text = label })
            col.addView(p)
            row.addView(col, LinearLayout.LayoutParams(0, -2, 1f))
        }
        box.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
        fun apply(t: Int, p: Int) {
            if (fromPlayer) {
                val g = cur ?: return
                if (t == g.req.tween && p == g.req.play) return
                val r = g.req
                startGenerate(Request(r.prompt, r.seconds, t, p, r.seed, r.dark), replace = g)
            } else { tween = t; play = p; savePrefs(); showHome() }
        }
        AlertDialog.Builder(this).setTitle("FPS (트위닝, 재생)").setView(box)
            .setPositiveButton("적용") { _, _ -> apply(pt.value, pp.value) }
            .setNeutralButton("24, 24") { _, _ -> apply(24, 24) }
            .setNegativeButton("취소", null).show()
    }

    // ───────── 생성·저장 목록 ─────────

    private val gensDir get() = File(filesDir, "gens").apply { mkdirs() }

    private fun gens(): List<Gen> = (gensDir.listFiles() ?: emptyArray()).mapNotNull { d ->
        runCatching { Gen(d, JSONObject(File(d, "meta.json").readText())) }.getOrNull()
    }.sortedByDescending { it.meta.optLong("created") }

    private fun recentList(box: LinearLayout, widthDp: Int) {
        box.addView(text(15f, Theme.TEXT, true).apply { text = "최근 생성" }, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(12); marginStart = dp(6) })
        val items = gens()
        if (items.isEmpty()) {
            box.addView(text(14f, Theme.SUB).apply { text = "아직 없습니다. 위에서 생성해 보세요"; gravity = Gravity.CENTER },
                LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(24); bottomMargin = dp(24) })
            return
        }
        val cols = (widthDp / 180).coerceIn(1, 6) // 창 폭에 맞춰 카드 열 수
        var row: LinearLayout? = null
        items.take(30).forEachIndexed { i, g ->
            if (i % cols == 0) { row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }; box.addView(row, LinearLayout.LayoutParams(-1, -2)) }
            row!!.addView(genCard(g), LinearLayout.LayoutParams(0, -2, 1f).apply { setMargins(dp(6), 0, dp(6), dp(18)) })
        }
        val rest = items.take(30).size % cols
        if (rest != 0) repeat(cols - rest) { row!!.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f).apply { setMargins(dp(6), 0, dp(6), 0) }) }
    }

    private fun genCard(g: Gen): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val r = dp(18).toFloat()
        val thumb = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP; background = Theme.round(Theme.SURFACE, r)
            clipToOutline = true
            outlineProvider = object : ViewOutlineProvider() { override fun getOutline(v: View, out: Outline) { out.setRoundRect(0, 0, v.width, v.height, r) } }
            val f = File(g.dir, "thumb.jpg")
            if (f.exists()) setImageBitmap(BitmapFactory.decodeFile(f.path))
            setOnClickListener { open(g) }
        }
        box.addView(thumb, LinearLayout.LayoutParams(-1, 0).also { lp -> thumb.post { lp.height = (thumb.width * 0.5625f).toInt(); thumb.layoutParams = lp } })
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val texts = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        texts.addView(text(15f, Theme.TEXT, true).apply { text = g.name; maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END })
        val q = g.req
        texts.addView(text(12f, Theme.SUB).apply { text = "${q.seconds}초 · (${q.tween}, ${q.play}) · 파일 ${g.parts.size}개" }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(5) })
        row.addView(texts, LinearLayout.LayoutParams(0, -2, 1f))
        row.addView(icon(IconView.Kind.MORE, Theme.TEXT) {
            AlertDialog.Builder(this).setTitle(g.name).setItems(arrayOf("이 설정을 입력칸으로", "지우기")) { _, w ->
                if (w == 0) { prompt = q.prompt; seconds = q.seconds; tween = q.tween; play = q.play; seed = q.seed; dark = q.dark; savePrefs(); showHome() }
                else { g.dir.deleteRecursively(); showHome() }
            }.show()
        }, LinearLayout.LayoutParams(dp(40), dp(40)))
        box.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        return box
    }

    private fun generate() {
        if (Generator.tags(prompt).isEmpty()) prompt = "1v1"
        startGenerate(Request(prompt, seconds, tween, play, seed, dark), replace = null)
        seed = (Math.random() * 100000).toLong() // 다음 생성은 새 시드
    }

    private fun regenerate() {
        val g = cur ?: return
        val r = g.req
        startGenerate(Request(r.prompt, r.seconds, r.tween, r.play, (Math.random() * 100000).toLong(), r.dark), replace = null)
    }

    /** 기기 안에서 만든다: 안무 → 장면 → 5초 단위 SFA + 미리보기용 전체 SFA. replace가 있으면 그 결과를 바꾼다(FPS 변경). */
    private fun startGenerate(req: Request, replace: Gen?) {
        if (busy.getAndSet(true)) return
        if (onPlayer) closePlayer()
        setControlsEnabled(false); seek.progress = 0
        title.text = "생성 중"; info.text = ""; status.text = "안무 짜는 중…"
        partsRow.removeAllViews()
        showPlayer()
        io.execute {
            try {
                val t0 = SystemClock.elapsedRealtime()
                val g: Generated = Generator.generate(lib, req)
                val stamp = SimpleDateFormat("MMdd_HHmmss", Locale.ROOT).format(Date())
                val name = replace?.name ?: "1v1_$stamp"
                val dir = replace?.dir ?: File(gensDir, stamp + "_" + req.seed)
                File(dir, "parts").deleteRecursively(); File(dir, "parts").mkdirs()
                File(dir, "thumb.jpg").delete()
                g.parts.forEachIndexed { i, r ->
                    ui.post { status.text = "파일 쓰는 중 ${i + 1}/${g.parts.size}" }
                    File(dir, "parts/${name}_${i + 1}.sfa").outputStream().use { Generator.writeSfa(g, r, "${name}_${i + 1}", it) }
                }
                ui.post { status.text = "미리보기 준비 중…" }
                val preview = File(dir, "preview.sfa")
                preview.outputStream().use { Generator.writeSfa(g, 0 until g.frameCount, name, it) }
                val meta = JSONObject().put("name", name).put("prompt", req.prompt).put("seconds", req.seconds).put("tween", req.tween)
                    .put("play", req.play).put("seed", req.seed).put("dark", req.dark).put("created", System.currentTimeMillis())
                    .put("notes", g.notes.joinToString("\n")).put("ms", SystemClock.elapsedRealtime() - t0)
                File(dir, "meta.json").writeText(meta.toString())
                val gen = Gen(dir, meta)
                ui.post { busy.set(false); open(gen) }
            } catch (e: Throwable) {
                ui.post { busy.set(false); status.text = "생성 실패: ${e.message}"; title.text = "생성 실패" }
            }
        }
    }

    // ───────── 결과 화면(플레이어) ─────────

    private fun showPlayer() {
        onPlayer = true
        for (v in listOf(view, title, status, frameLabel, timeLabel, info, seek, playBtn, prevBtn, nextBtn, backBtn, saveIcon, saveBtn, exportBtn, againBtn, fpsBtn, videoBox, partsRow)) detach(v)
        videoBox.removeAllViews(); videoBox.addView(view, FrameLayout.LayoutParams(-1, -1))
        videoBox.ratio = doc?.ratio ?: 0.5625f
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Theme.BG) }
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(6), dp(4), dp(6), dp(4)) }
        header.addView(backBtn, LinearLayout.LayoutParams(dp(48), dp(48)))
        val playSize = if (landscape || compact) 48 else 76
        val partsScroll = HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(partsRow) }
        if (landscape && !wideTall()) {
            title.gravity = Gravity.START or Gravity.CENTER_VERTICAL; title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
            header.addView(title, LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(4) })
            status.gravity = Gravity.END or Gravity.CENTER_VERTICAL
            header.addView(status, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(12); marginEnd = dp(8) })
            header.addView(fpsBtn, LinearLayout.LayoutParams(-2, -2).apply { marginEnd = dp(4) })
            header.addView(saveIcon, LinearLayout.LayoutParams(dp(48), dp(48)))
            root.addView(header, LinearLayout.LayoutParams(-1, -2))
            root.addView(videoBox.also { it.maxFrac = 1f }, LinearLayout.LayoutParams(-1, 0, 1f))
            val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(12), dp(4), dp(12), dp(4)) }
            bar.addView(playBtn, LinearLayout.LayoutParams(dp(playSize), dp(playSize)))
            bar.addView(timeLabel, LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(8) })
            bar.addView(seek, LinearLayout.LayoutParams(0, -2, 1f))
            bar.addView(frameLabel, LinearLayout.LayoutParams(-2, -2))
            bar.addView(prevBtn, LinearLayout.LayoutParams(dp(44), dp(44)).apply { marginStart = dp(8) })
            bar.addView(nextBtn, LinearLayout.LayoutParams(dp(44), dp(44)))
            frameLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            root.addView(bar, LinearLayout.LayoutParams(-1, -2))
            if (!compact) root.addView(partsScroll, LinearLayout.LayoutParams(-1, -2).apply { setMargins(dp(12), 0, dp(12), dp(6)) })
        } else {
            // 세로(또는 펼친 폴드처럼 높이가 충분한 창): 영상은 위쪽 전체 폭, 조작·정보는 그 아래
            title.gravity = Gravity.CENTER; title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            header.addView(title, LinearLayout.LayoutParams(0, -2, 1f))
            header.addView(saveIcon, LinearLayout.LayoutParams(dp(48), dp(48)))
            root.addView(header, LinearLayout.LayoutParams(-1, -2))
            root.addView(videoBox.also { it.maxFrac = if (compact) 0.5f else 0.55f }, LinearLayout.LayoutParams(-1, -2))
            val pd = if (compact) 12 else 22
            val body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(pd), dp(if (compact) 8 else 16), dp(pd), dp(24)) }
            val labels = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
            frameLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            labels.addView(frameLabel, LinearLayout.LayoutParams(0, -2, 1f))
            labels.addView(timeLabel)
            body.addView(labels, LinearLayout.LayoutParams(-1, -2).apply { setMargins(dp(8), 0, dp(8), dp(10)) })
            body.addView(seek, LinearLayout.LayoutParams(-1, -2))
            val ctl = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            ctl.addView(prevBtn, LinearLayout.LayoutParams(dp(56), dp(56)))
            ctl.addView(playBtn, LinearLayout.LayoutParams(dp(playSize), dp(playSize)).apply { setMargins(dp(36), 0, dp(36), 0) })
            ctl.addView(nextBtn, LinearLayout.LayoutParams(dp(56), dp(56)))
            body.addView(ctl, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
            body.addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
            val card = card()
            card.addView(text(15f, Theme.TEXT, true).apply { text = "SFA 파일 (5초씩)" })
            card.addView(partsScroll, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
            card.addView(info, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
            val fpsRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
            fpsRow.addView(text(14f, Theme.TEXT).apply { text = "FPS (트위닝, 재생)" }, LinearLayout.LayoutParams(0, -2, 1f))
            fpsRow.addView(fpsBtn, LinearLayout.LayoutParams(-2, -2))
            card.addView(fpsRow, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
            card.addView(saveBtn, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) })
            val two = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            two.addView(exportBtn, LinearLayout.LayoutParams(0, -2, 1f).apply { marginEnd = dp(6) })
            two.addView(againBtn, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(6) })
            card.addView(two, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
            body.addView(card, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(20) })
            root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        }
        setContentView(edge(root))
        updateLabels(seek.progress)
    }

    /** 가로로 넓지만 높이도 충분한 창(펼친 폴드 등)은 세로식 배치가 더 보기 좋다. */
    private fun wideTall() = winH >= 640 && winW < winH * 1.25f

    private fun fillParts(g: Gen) {
        partsRow.removeAllViews()
        val per = 5 * g.req.play
        g.parts.forEachIndexed { i, _ ->
            partsRow.addView(text(13f, Theme.TEXT, true).apply {
                text = "${i + 1}  ${i * 5}–${minOf((i + 1) * 5, g.req.seconds)}초"; background = Theme.round(Theme.CARD, dp(16).toFloat())
                setPadding(dp(14), dp(8), dp(14), dp(8))
                setOnClickListener {
                    val j = (i * per).let { src -> if (tl.interp) (src.toLong() * tl.tween / tl.play).toInt() else src }.coerceIn(0, maxOf(0, tl.count - 1))
                    setPlaying(false); seek.progress = j; wanted.set(j); updateLabels(j); kick()
                }
            }, LinearLayout.LayoutParams(-2, -2).apply { marginEnd = dp(8) })
        }
    }

    private fun updateLabels(f: Int) {
        val n = if (doc != null) tl.count else 0
        frameLabel.text = if (n > 0) "${f + 1} / $n" else "– / –"
        fun t(fr: Int) = "%02d:%02d".format(fr / fps / 60, fr / fps % 60)
        timeLabel.text = if (n > 0) "${t(f)} / ${t(n)}" else ""
    }

    private fun closePlayer() {
        setPlaying(false)
        renderThread?.interrupt(); renderThread = null
        cache?.close(); cache = null
        doc = null; view.clear()
    }

    /** 저장된 결과를 연다: 미리보기 SFA를 뷰어 파서로 읽고 (T, P) 시간표로 미리 그린다. */
    private fun open(g: Gen) {
        if (busy.getAndSet(true)) return
        if (onPlayer) closePlayer()
        cur = g
        setControlsEnabled(false); seek.progress = 0
        title.text = g.name; info.text = ""; status.text = "여는 중…"
        fillParts(g)
        showPlayer()
        io.execute {
            try {
                val d = File(g.dir, "preview.sfa").inputStream().use { SfaParser().parse(it) }
                ui.post { onLoaded(g, d) }
            } catch (e: Throwable) {
                ui.post { status.text = "열기 실패: ${e.message}"; busy.set(false) }
            }
        }
    }

    private fun onLoaded(g: Gen, d: SfaDoc) {
        busy.set(false)
        if (!onPlayer || cur !== g) return
        doc = d
        videoBox.ratio = d.ratio
        setControlsEnabled(true)
        val q = g.req
        tl = Timeline(d.frameCount, q.tween, q.play)
        val fc = FrameCache(d, tl, File(cacheDir, "frames_${g.id}_${q.tween}_${q.play}"), 1280)
        fc.prefetchFrom(0)
        cache = fc
        fpsBtn.text = "${q.tween}, ${q.play}"
        val how = if (tl.interp) "Stick Fighter처럼 보간해 ${tl.fps}fps로 미리보기" else "보간 없음 · ${tl.fps}fps"
        val notes = g.meta.optString("notes").let { if (it.isBlank()) "" else "\n$it" }
        info.text = "프롬프트: ${q.prompt}\n${q.seconds}초 · ${d.frameCount}프레임 · 파일 ${g.parts.size}개 · 시드 ${q.seed}\n$how · 생성 ${g.meta.optLong("ms")}ms$notes"
        seek.max = maxOf(tl.count - 1, 0); seek.progress = 0
        wanted.set(0); updateLabels(0); startRenderLoop(); kick()
        saveThumb(fc, File(g.dir, "thumb.jpg"))
    }

    /** 첫 화면 카드용 미리보기(타격이 있을 법한 1/3 지점, 폭 480). */
    private fun saveThumb(fc: FrameCache, out: File) {
        if (out.exists()) return
        Thread {
            val b = fc.get(fc.tl.count / 3, 60_000, null) ?: return@Thread
            runCatching {
                val s = Bitmap.createScaledBitmap(b, 480, maxOf(2, (480f * b.height / b.width).toInt()), true)
                out.outputStream().use { s.compress(Bitmap.CompressFormat.JPEG, 85, it) }
            }
        }.start()
    }

    private val lock = Object()
    private fun kick() { synchronized(lock) { lock.notifyAll() } }

    private fun setPlaying(p: Boolean) { playing.set(p); playBtn.set(if (p) IconView.Kind.PAUSE else IconView.Kind.PLAY); kick() }
    private fun togglePlay() { if (doc != null && !exporting.get()) setPlaying(!playing.get()) }
    private fun step(dir: Int) {
        val d = doc ?: return
        setPlaying(false)
        if (d.frameCount == 0) return
        val f = (seek.progress + dir).coerceIn(0, tl.count - 1)
        seek.progress = f; wanted.set(f); updateLabels(f); kick()
    }

    /** 표시 스레드: 미리 그려 둔 프레임(JPEG 캐시)을 읽어 보여 준다. 재생 중이면 시간표 fps 간격으로 넘긴다. */
    private fun startRenderLoop() {
        renderThread?.interrupt()
        val fc = cache ?: return
        val n = fc.tl.count; val step = 1000.0 / fc.tl.fps
        if (n == 0) return
        renderThread = Thread {
            var last = -1
            var spare: Bitmap? = null
            var nextAt = SystemClock.elapsedRealtime().toDouble()
            fun prep() = if (fc.done.get() >= n) "미리 그리기 완료" else "미리 그리기 ${fc.done.get()}/$n"
            try {
                while (!Thread.currentThread().isInterrupted) {
                    val f = wanted.get().coerceIn(0, n - 1)
                    if (f == last && !playing.get()) {
                        view.post { if (!exporting.get()) status.text = prep() }
                        synchronized(lock) { lock.wait(300) }; continue
                    }
                    val bmp = fc.get(f, 200, spare)
                    if (bmp == null) {
                        view.post { if (!exporting.get()) status.text = "그리는 중… (${prep()})" }
                        continue
                    }
                    val now = SystemClock.elapsedRealtime()
                    if (playing.get() && nextAt > now) Thread.sleep((nextAt - now).toLong())
                    spare = view.swap(bmp)
                    last = f
                    view.post { seek.progress = f; updateLabels(f) }
                    if (playing.get()) {
                        nextAt = maxOf(nextAt + step, SystemClock.elapsedRealtime() - step)
                        wanted.set(if (f + 1 >= n) 0 else f + 1)
                    } else {
                        fc.prefetchFrom(f)
                        nextAt = SystemClock.elapsedRealtime().toDouble()
                    }
                }
            } catch (_: InterruptedException) {}
        }.apply { priority = Thread.MAX_PRIORITY; start() }
    }

    /** 5초 단위 SFA를 다운로드/SfaCreator/<이름>/ 에 저장한다(Stick Fighter에서 열기). */
    private fun saveSfa() {
        val g = cur ?: return
        if (busy.getAndSet(true)) return
        io.execute {
            try {
                var n = 0
                for (f in g.parts) {
                    if (Build.VERSION.SDK_INT >= 29) {
                        val cv = ContentValues().apply {
                            put(MediaStore.Downloads.DISPLAY_NAME, f.name); put(MediaStore.Downloads.MIME_TYPE, "application/octet-stream")
                            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/SfaCreator/" + g.name)
                        }
                        val u = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv)!!
                        contentResolver.openOutputStream(u)!!.use { o -> f.inputStream().use { it.copyTo(o) } }
                    } else {
                        val d = File(getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "SfaCreator/${g.name}").apply { mkdirs() }
                        f.copyTo(File(d, f.name), overwrite = true)
                    }
                    n++
                }
                ui.post {
                    status.text = "저장됨: 다운로드/SfaCreator/${g.name}/ (${n}개)"
                    Toast.makeText(this, status.text, Toast.LENGTH_LONG).show()
                }
            } catch (e: Throwable) {
                ui.post { status.text = "저장 실패: ${e.message}" }
            } finally { busy.set(false) }
        }
    }

    private fun exportOrCancel() {
        val d = doc ?: return
        val g = cur ?: return
        if (exporting.get()) { cancelExport.set(true); return }
        if (busy.getAndSet(true)) return
        exporting.set(true); cancelExport.set(false); setPlaying(false)
        exportBtn.text = "취소"
        io.execute {
            try {
                val name = "${g.name}.mp4"
                val (uri, fdHolder) = if (Build.VERSION.SDK_INT >= 29) {
                    val cv = ContentValues().apply {
                        put(MediaStore.Video.Media.DISPLAY_NAME, name); put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                        put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/SfaCreator"); put(MediaStore.Video.Media.IS_PENDING, 1)
                    }
                    val u = contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, cv)!!
                    u to contentResolver.openFileDescriptor(u, "w")!!
                } else {
                    val f = File(getExternalFilesDir(Environment.DIRECTORY_MOVIES), name)
                    Uri.fromFile(f) to android.os.ParcelFileDescriptor.open(f, android.os.ParcelFileDescriptor.MODE_CREATE or android.os.ParcelFileDescriptor.MODE_READ_WRITE or android.os.ParcelFileDescriptor.MODE_TRUNCATE)
                }
                val t0 = SystemClock.elapsedRealtime()
                val ok = fdHolder.use { pfd ->
                    VideoExporter(d, tl).export(pfd.fileDescriptor, { i, n -> ui.post { status.text = "MP4 내보내는 중 $i/$n"; exportBtn.text = "취소 ($i/$n)" } }, { cancelExport.get() })
                }
                if (Build.VERSION.SDK_INT >= 29) {
                    if (ok) contentResolver.update(uri, ContentValues().apply { put(MediaStore.Video.Media.IS_PENDING, 0) }, null, null)
                    else contentResolver.delete(uri, null, null)
                }
                val dt = (SystemClock.elapsedRealtime() - t0) / 1000.0
                ui.post {
                    status.text = if (ok) "저장됨: 동영상/SfaCreator/$name (${"%.1f".format(dt)}초)" else "내보내기 취소됨"
                    Toast.makeText(this, status.text, Toast.LENGTH_LONG).show()
                }
            } catch (e: Throwable) {
                ui.post { status.text = "내보내기 실패: ${e.message}" }
            } finally {
                ui.post { busy.set(false); exporting.set(false); exportBtn.text = "MP4 내보내기" }
            }
        }
    }

    /** 화면 배치 시험용(UiShotTest): 백그라운드 그리기 없이 결과 화면을 띄운다. */
    internal fun showForTest(d: SfaDoc, first: Bitmap, name: String, parts: Int) {
        doc = d; title.text = name; videoBox.ratio = d.ratio
        tl = Timeline(d.frameCount, 24, 24); fpsBtn.text = "24, 24"
        info.text = "프롬프트: 1v1\n${d.frameCount / 24}초 · ${d.frameCount}프레임 · 파일 ${parts}개 · 시드 1\n보간 없음 · 24fps · 생성 120ms"
        status.text = "미리 그리기 완료"
        partsRow.removeAllViews()
        repeat(parts) { i -> partsRow.addView(text(13f, Theme.TEXT, true).apply { text = "${i + 1}  ${i * 5}–${(i + 1) * 5}초"; background = Theme.round(Theme.CARD, dp(16).toFloat()); setPadding(dp(14), dp(8), dp(14), dp(8)) }, LinearLayout.LayoutParams(-2, -2).apply { marginEnd = dp(8) }) }
        seek.max = tl.count - 1; setControlsEnabled(true); showPlayer(); view.swap(first)
    }

    override fun onDestroy() { renderThread?.interrupt(); cache?.close(); io.shutdownNow(); super.onDestroy() }
}

/** 현재 프레임 비트맵을 비율 유지해 가운데에 그린다. */
class FrameView(ctx: android.content.Context) : View(ctx) {
    private var bmp: Bitmap? = null
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val dst = RectF()
    @Volatile private var prev: Bitmap? = null
    fun swap(b: Bitmap): Bitmap? {
        val old = prev
        prev = bmp; bmp = b
        postInvalidate()
        return if (old !== b) old else null
    }
    fun clear() { bmp = null; prev = null; invalidate() }
    override fun onDraw(c: Canvas) {
        c.drawColor(Color.BLACK)
        val b = bmp ?: return
        val s = minOf(width.toFloat() / b.width, height.toFloat() / b.height)
        val w = b.width * s; val h = b.height * s
        dst.set((width - w) / 2, (height - h) / 2, (width + w) / 2, (height + h) / 2)
        c.drawBitmap(b, null, dst, paint)
    }
}
