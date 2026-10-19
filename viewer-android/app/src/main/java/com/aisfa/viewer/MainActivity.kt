package com.aisfa.viewer

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
import android.provider.OpenableColumns
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.ViewOutlineProvider
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.roundToInt

class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
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
    private lateinit var exportIcon: IconView
    private lateinit var exportBtn: TextView
    private val videoBox by lazy { AspectBox(this).apply { setBackgroundColor(Color.BLACK) } }
    private var onPlayer = false
    private var doc: SfaDoc? = null
    private var cache: FrameCache? = null
    private var cacheKey = ""
    private var fileName = "sfa"
    private var curUri: Uri? = null
    private val playing = AtomicBoolean(false)
    private val wanted = AtomicInteger(0)
    private var renderThread: Thread? = null
    private val busy = AtomicBoolean(false)
    private val exporting = AtomicBoolean(false)
    private val cancelExport = AtomicBoolean(false)
    private val fps = 24

    private fun dp(v: Float) = (v * resources.displayMetrics.density).roundToInt()
    private fun dp(v: Int) = dp(v.toFloat())
    private val landscape get() = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = Theme.BG
        window.navigationBarColor = Theme.BG
        @Suppress("DEPRECATION")
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR
        makePlayerParts()
        val data = intent?.data
        if (data != null) load(data) else showHome()
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); intent.data?.let { load(it) } }

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
        background = android.graphics.drawable.RippleDrawable(ColorStateList.valueOf(0x22000000), null, Theme.oval(Color.WHITE))
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
        exportIcon = icon(IconView.Kind.UPLOAD) { exportOrCancel() }
        exportBtn = text(15f, Color.WHITE, true).apply {
            gravity = Gravity.CENTER; text = "MP4 내보내기"; background = Theme.round(Theme.ORANGE, dp(24).toFloat())
            setPadding(dp(24), dp(14), dp(24), dp(14)); setOnClickListener { exportOrCancel() }
        }
        view.setOnClickListener { togglePlay() }
        setControlsEnabled(false)
    }

    private fun setControlsEnabled(on: Boolean) {
        for (v in listOf(playBtn, prevBtn, nextBtn, exportIcon, seek)) v.isEnabled = on
        exportBtn.isEnabled = on; exportBtn.alpha = if (on) 1f else 0.4f
        exportIcon.invalidate(); playBtn.invalidate(); prevBtn.invalidate(); nextBtn.invalidate()
    }

    // ───────── 첫 화면: 최근 파일 ─────────

    private fun showHome() {
        onPlayer = false
        val root = FrameLayout(this).apply { setBackgroundColor(Theme.BG) }
        val list = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(if (landscape) 20 else 56), dp(18), dp(120)) }
        list.addView(text(if (landscape) 30f else 38f, Theme.ORANGE, true).apply {
            text = "SFA VIEWER"; gravity = Gravity.CENTER; letterSpacing = -0.02f
        }, LinearLayout.LayoutParams(-1, -2))
        list.addView(text(13f, Theme.SUB).apply { text = "Stick Fighter 애니메이션 미리보기 · 내보내기"; gravity = Gravity.CENTER },
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        // 탭 모양 머리말(질감만 가져옴)
        val pill = FrameLayout(this).apply { background = Theme.round(Theme.SURFACE, dp(28).toFloat()); setPadding(dp(5), dp(5), dp(5), dp(5)) }
        pill.addView(text(14f, Theme.TEXT, true).apply {
            text = "최근 파일"; gravity = Gravity.CENTER; background = Theme.round(Color.WHITE, dp(24).toFloat()); setPadding(dp(28), dp(12), dp(28), dp(12))
        }, FrameLayout.LayoutParams(-2, -2))
        list.addView(pill, LinearLayout.LayoutParams(-2, -2).apply { gravity = Gravity.CENTER_HORIZONTAL; topMargin = dp(28); bottomMargin = dp(22) })

        val items = recent()
        if (items.isEmpty()) {
            list.addView(text(15f, Theme.SUB).apply { text = "아래 + 버튼으로 SFA 파일을 여세요"; gravity = Gravity.CENTER },
                LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(48) })
        } else {
            val cols = if (landscape) 4 else 2
            var row: LinearLayout? = null
            items.forEachIndexed { i, o ->
                if (i % cols == 0) { row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }; list.addView(row, LinearLayout.LayoutParams(-1, -2)) }
                row!!.addView(card(o), LinearLayout.LayoutParams(0, -2, 1f).apply { setMargins(dp(8), 0, dp(8), dp(22)) })
            }
            val rest = items.size % cols
            if (rest != 0) repeat(cols - rest) { row!!.addView(View(this), LinearLayout.LayoutParams(0, 1, 1f).apply { setMargins(dp(8), 0, dp(8), 0) }) }
        }
        root.addView(ScrollView(this).apply { addView(list) }, FrameLayout.LayoutParams(-1, -1))
        val fab = IconView(this, IconView.Kind.PLUS, Color.WHITE).apply {
            background = Theme.oval(Theme.ORANGE); elevation = dp(8).toFloat(); isClickable = true; setOnClickListener { pick() }
        }
        root.addView(fab, FrameLayout.LayoutParams(dp(68), dp(68)).apply {
            gravity = if (landscape) Gravity.BOTTOM or Gravity.END else Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
            setMargins(dp(24), dp(24), dp(24), dp(28))
        })
        setContentView(root)
    }

    private fun card(o: JSONObject): View {
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val r = dp(22).toFloat()
        val thumb = ImageView(this).apply {
            scaleType = ImageView.ScaleType.CENTER_CROP; background = Theme.round(Theme.SURFACE, r)
            clipToOutline = true
            outlineProvider = object : ViewOutlineProvider() { override fun getOutline(v: View, out: Outline) { out.setRoundRect(0, 0, v.width, v.height, r) } }
            val f = File(filesDir, "thumbs/${o.optString("key")}.jpg")
            if (f.exists()) setImageBitmap(BitmapFactory.decodeFile(f.path))
            setOnClickListener { load(Uri.parse(o.getString("uri"))) }
        }
        box.addView(thumb, LinearLayout.LayoutParams(-1, 0).also { lp -> thumb.post { lp.height = (thumb.width * 0.62f).toInt(); thumb.layoutParams = lp } })
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val texts = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        texts.addView(text(16f, Theme.TEXT, true).apply { text = o.optString("name"); maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END })
        texts.addView(text(13f, Theme.SUB).apply { text = "${o.optInt("frames")} frames" }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(6) })
        row.addView(texts, LinearLayout.LayoutParams(0, -2, 1f))
        row.addView(icon(IconView.Kind.MORE, Theme.TEXT) {
            AlertDialog.Builder(this).setTitle(o.optString("name")).setItems(arrayOf("목록에서 지우기")) { _, _ -> forget(o.optString("uri")); showHome() }.show()
        }, LinearLayout.LayoutParams(dp(40), dp(40)))
        box.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        return box
    }

    private fun recent(): List<JSONObject> {
        val a = runCatching { JSONArray(getSharedPreferences("v", MODE_PRIVATE).getString("recent", "[]")) }.getOrElse { JSONArray() }
        return (0 until a.length()).map { a.getJSONObject(it) }
    }

    private fun saveRecent(items: List<JSONObject>) {
        getSharedPreferences("v", MODE_PRIVATE).edit().putString("recent", JSONArray(items.take(24)).toString()).apply()
    }

    private fun remember(uri: Uri, name: String, frames: Int) {
        val o = JSONObject().put("uri", uri.toString()).put("name", name).put("key", cacheKey).put("frames", frames)
        saveRecent(listOf(o) + recent().filter { it.optString("uri") != uri.toString() })
    }

    private fun forget(uri: String) = saveRecent(recent().filter { it.optString("uri") != uri })

    // ───────── 플레이어 화면 ─────────

    private fun showPlayer() {
        onPlayer = true
        for (v in listOf(view, title, status, frameLabel, timeLabel, info, seek, playBtn, prevBtn, nextBtn, backBtn, exportIcon, exportBtn, videoBox)) detach(v)
        videoBox.removeAllViews(); videoBox.addView(view, FrameLayout.LayoutParams(-1, -1))
        videoBox.ratio = doc?.ratio ?: 0.5625f
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Theme.BG) }
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(6), dp(4), dp(6), dp(4)) }
        header.addView(backBtn, LinearLayout.LayoutParams(dp(48), dp(48)))
        val playSize = if (landscape) 48 else 76
        if (landscape) {
            title.gravity = Gravity.START or Gravity.CENTER_VERTICAL; title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
            header.addView(title, LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(4) })
            status.gravity = Gravity.END or Gravity.CENTER_VERTICAL
            header.addView(status, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(12); marginEnd = dp(8) })
            header.addView(exportIcon, LinearLayout.LayoutParams(dp(48), dp(48)))
            root.addView(header, LinearLayout.LayoutParams(-1, -2))
            root.addView(videoBox.also { it.maxFrac = 1f }, LinearLayout.LayoutParams(-1, 0, 1f))
            // 아래 막대: 재생 · 시간 · 이동 막대 · 프레임 · 앞뒤
            val bar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(dp(12), dp(4), dp(12), dp(4)) }
            bar.addView(playBtn, LinearLayout.LayoutParams(dp(playSize), dp(playSize)))
            bar.addView(timeLabel, LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(8) })
            bar.addView(seek, LinearLayout.LayoutParams(0, -2, 1f))
            bar.addView(frameLabel, LinearLayout.LayoutParams(-2, -2))
            bar.addView(prevBtn, LinearLayout.LayoutParams(dp(44), dp(44)).apply { marginStart = dp(8) })
            bar.addView(nextBtn, LinearLayout.LayoutParams(dp(44), dp(44)))
            frameLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            root.addView(bar, LinearLayout.LayoutParams(-1, -2))
        } else {
            // 세로: 유튜브 세로 보기처럼 영상은 위쪽 전체 폭, 조작은 그 아래
            title.gravity = Gravity.CENTER; title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20f)
            header.addView(title, LinearLayout.LayoutParams(0, -2, 1f))
            header.addView(exportIcon, LinearLayout.LayoutParams(dp(48), dp(48)))
            root.addView(header, LinearLayout.LayoutParams(-1, -2))
            root.addView(videoBox.also { it.maxFrac = 0.62f }, LinearLayout.LayoutParams(-1, -2))
            val body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(22), dp(18), dp(22), dp(24)) }
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
            body.addView(ctl, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
            body.addView(status, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
            val card = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL; background = Theme.round(Theme.SURFACE, dp(22).toFloat()); setPadding(dp(20), dp(18), dp(20), dp(18))
            }
            card.addView(text(15f, Theme.TEXT, true).apply { text = "파일 정보" })
            card.addView(info, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
            card.addView(exportBtn, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(18) })
            body.addView(card, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(24) })
            root.addView(ScrollView(this).apply { addView(body) }, LinearLayout.LayoutParams(-1, 0, 1f))
        }
        setContentView(root)
        updateLabels(seek.progress)
    }

    private fun updateLabels(f: Int) {
        val n = doc?.frameCount ?: 0
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

    // ───────── 열기·재생·내보내기 ─────────

    private fun pick() {
        if (busy.get()) return
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type = "*/*" }, 1)
    }

    @Deprecated("Activity result")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 1 && resultCode == RESULT_OK) data?.data?.let { u ->
            runCatching { contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            load(u)
        }
    }

    private fun meta(uri: Uri): Pair<String, Long> {
        var name = "sfa"; var size = -1L
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val ni = c.getColumnIndex(OpenableColumns.DISPLAY_NAME); val si = c.getColumnIndex(OpenableColumns.SIZE)
                if (ni >= 0) name = c.getString(ni) ?: name
                if (si >= 0) size = c.getLong(si)
            }
        }
        return name to size
    }

    private fun load(uri: Uri) {
        if (busy.getAndSet(true)) return
        if (onPlayer) closePlayer()
        curUri = uri
        setControlsEnabled(false); seek.progress = 0
        title.text = "불러오는 중"; info.text = ""; status.text = "파일 여는 중…"
        showPlayer()
        io.execute {
            val t0 = SystemClock.elapsedRealtime()
            try {
                val (name, size) = meta(uri)
                fileName = name.substringBeforeLast('.')
                ui.post { title.text = fileName }
                val key = (name + "_" + size).hashCode().toUInt().toString(16)
                cacheKey = key
                val cache = File(cacheDir, "$key.sfab")
                var d: SfaDoc? = null
                var how = "캐시"
                if (cache.exists()) d = runCatching { cache.inputStream().use { SfaDoc.read(it) } }.getOrNull()
                if (d == null) {
                    how = "변환"
                    d = contentResolver.openInputStream(uri)!!.use { inp ->
                        SfaParser { read -> ui.post { status.text = "읽는 중… XML ${read / 1_000_000} MB" } }.parse(inp)
                    }
                    ui.post { status.text = "캐시 저장 중…" }
                    runCatching { File(cacheDir, "$key.tmp").also { tmp -> tmp.outputStream().use { d.write(it) }; tmp.renameTo(cache) } }
                }
                val dt = (SystemClock.elapsedRealtime() - t0) / 1000.0
                val msg = "불러오기: $how ${"%.1f".format(dt)}초"
                ui.post { onLoaded(uri, d!!, msg) }
            } catch (e: Throwable) {
                ui.post {
                    status.text = "열기 실패: ${e.message}"; title.text = "열기 실패"; busy.set(false)
                    if (e is SecurityException) { forget(uri.toString()); Toast.makeText(this, "파일 권한이 없어졌습니다. + 버튼으로 다시 여세요", Toast.LENGTH_LONG).show() }
                }
            }
        }
    }

    private fun onLoaded(uri: Uri, d: SfaDoc, msg: String) {
        busy.set(false)
        remember(uri, fileName, d.frameCount)
        if (!onPlayer || curUri != uri) return
        doc = d
        val fc = FrameCache(d, File(cacheDir, "frames_${cacheKey}_1280"), 1280).also { it.prefetchFrom(0) }
        cache = fc
        info.text = "${d.frameCount}프레임 · ${"%.1f".format(d.frameCount.toDouble() / fps)}초 (24fps)\n" +
            "1920×${(1920 * d.ratio).roundToInt()} · 오브젝트 ${"%,d".format(d.objCount)}개\n$msg"
        videoBox.ratio = d.ratio
        seek.max = maxOf(d.frameCount - 1, 0); seek.progress = 0
        setControlsEnabled(true)
        wanted.set(0); updateLabels(0); startRenderLoop(); kick()
        saveThumb(fc, cacheKey)
    }

    /** 첫 화면 카드용 미리보기(0번 프레임, 폭 480). */
    private fun saveThumb(fc: FrameCache, key: String) {
        val out = File(filesDir, "thumbs/$key.jpg")
        if (out.exists()) return
        Thread {
            val b = fc.get(0, 60_000, null) ?: return@Thread
            runCatching {
                out.parentFile?.mkdirs()
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
        val f = (seek.progress + dir).coerceIn(0, d.frameCount - 1)
        seek.progress = f; wanted.set(f); updateLabels(f); kick()
    }

    /** 표시 스레드: 미리 그려 둔 프레임(JPEG 캐시)을 읽어 보여 준다. 재생 중이면 24fps 간격으로 넘기고, 준비 안 된 프레임은 기다린다. */
    private fun startRenderLoop() {
        renderThread?.interrupt()
        val d = doc ?: return; val fc = cache ?: return
        renderThread = Thread {
            var last = -1
            var spare: Bitmap? = null
            var nextAt = SystemClock.elapsedRealtime()
            fun prep() = if (fc.done.get() >= d.frameCount) "미리 그리기 완료" else "미리 그리기 ${fc.done.get()}/${d.frameCount}"
            try {
                while (!Thread.currentThread().isInterrupted) {
                    val f = wanted.get().coerceIn(0, d.frameCount - 1)
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
                    if (playing.get() && nextAt > now) Thread.sleep(nextAt - now)
                    spare = view.swap(bmp)
                    last = f
                    view.post { seek.progress = f; updateLabels(f) }
                    if (playing.get()) {
                        nextAt = maxOf(nextAt + 1000L / fps, SystemClock.elapsedRealtime() - 1000L / fps)
                        wanted.set(if (f + 1 >= d.frameCount) 0 else f + 1)
                    } else {
                        fc.prefetchFrom(f)
                        nextAt = SystemClock.elapsedRealtime()
                    }
                }
            } catch (_: InterruptedException) {}
        }.apply { priority = Thread.MAX_PRIORITY; start() }
    }

    private fun exportOrCancel() {
        val d = doc ?: return
        if (exporting.get()) { cancelExport.set(true); return }
        if (busy.getAndSet(true)) return
        exporting.set(true); cancelExport.set(false); setPlaying(false)
        exportBtn.text = "취소"; exportIcon.color = Theme.ORANGE; exportIcon.invalidate()
        io.execute {
            try {
                val name = "$fileName.mp4"
                val (uri, fdHolder) = if (Build.VERSION.SDK_INT >= 29) {
                    val cv = ContentValues().apply {
                        put(MediaStore.Video.Media.DISPLAY_NAME, name); put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                        put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/SfaViewer"); put(MediaStore.Video.Media.IS_PENDING, 1)
                    }
                    val u = contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, cv)!!
                    u to contentResolver.openFileDescriptor(u, "w")!!
                } else {
                    val f = File(getExternalFilesDir(Environment.DIRECTORY_MOVIES), name)
                    Uri.fromFile(f) to android.os.ParcelFileDescriptor.open(f, android.os.ParcelFileDescriptor.MODE_CREATE or android.os.ParcelFileDescriptor.MODE_READ_WRITE or android.os.ParcelFileDescriptor.MODE_TRUNCATE)
                }
                val t0 = SystemClock.elapsedRealtime()
                val ok = fdHolder.use { pfd ->
                    VideoExporter(d, fps).export(pfd.fileDescriptor, { i, n -> ui.post { status.text = "MP4 내보내는 중 $i/$n"; exportBtn.text = "취소 ($i/$n)" } }, { cancelExport.get() })
                }
                if (Build.VERSION.SDK_INT >= 29) {
                    if (ok) contentResolver.update(uri, ContentValues().apply { put(MediaStore.Video.Media.IS_PENDING, 0) }, null, null)
                    else contentResolver.delete(uri, null, null)
                }
                val dt = (SystemClock.elapsedRealtime() - t0) / 1000.0
                ui.post {
                    status.text = if (ok) "저장됨: 동영상/SfaViewer/$name (${"%.1f".format(dt)}초)" else "내보내기 취소됨"
                    Toast.makeText(this, status.text, Toast.LENGTH_LONG).show()
                }
            } catch (e: Throwable) {
                ui.post { status.text = "내보내기 실패: ${e.message}" }
            } finally {
                ui.post { busy.set(false); exporting.set(false); exportBtn.text = "MP4 내보내기"; exportIcon.color = Theme.ICON; exportIcon.invalidate() }
            }
        }
    }

    /** 화면 배치 시험용(UiShotTest): 백그라운드 그리기 없이 문서와 첫 프레임만 넣어 플레이어를 띄운다. */
    internal fun showForTest(d: SfaDoc, first: Bitmap, name: String) {
        doc = d; fileName = name; title.text = name; videoBox.ratio = d.ratio
        info.text = "${d.frameCount}프레임 · ${"%.1f".format(d.frameCount.toDouble() / fps)}초 (24fps)\n1920×${(1920 * d.ratio).roundToInt()} · 오브젝트 ${"%,d".format(d.objCount)}개"
        status.text = "미리 그리기 완료"
        seek.max = d.frameCount - 1; setControlsEnabled(true); showPlayer(); view.swap(first)
    }

    override fun onDestroy() { renderThread?.interrupt(); cache?.close(); io.shutdownNow(); super.onDestroy() }
}

/** 현재 프레임 비트맵을 비율 유지해 가운데에 그린다. */
class FrameView(ctx: android.content.Context) : View(ctx) {
    private var bmp: Bitmap? = null
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val dst = RectF()
    /** 새 비트맵을 보여 주고, 화면에 더 이상 쓰이지 않는 이전 비트맵을 돌려준다(다음 디코딩에 재사용). */
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
