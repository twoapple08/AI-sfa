package com.aisfa.viewer

import android.app.Activity
import android.content.ContentValues
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class MainActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor()
    private lateinit var view: FrameView
    private lateinit var status: TextView
    private lateinit var seek: SeekBar
    private lateinit var playBtn: Button
    private lateinit var exportBtn: Button
    private var doc: SfaDoc? = null
    private var renderer: FrameRenderer? = null
    private var fileName = "sfa"
    private val playing = AtomicBoolean(false)
    private val wanted = AtomicInteger(0)
    private var renderThread: Thread? = null
    private val busy = AtomicBoolean(false)
    private val cancelExport = AtomicBoolean(false)
    private val fps = 24

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.BLACK) }
        val top = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        val open = Button(this).apply { text = "열기"; setOnClickListener { pick() } }
        status = TextView(this).apply { setTextColor(Color.WHITE); text = "SFA 파일을 여세요"; setPadding(16, 0, 16, 0) }
        exportBtn = Button(this).apply { text = "MP4 내보내기"; isEnabled = false; setOnClickListener { exportOrCancel() } }
        top.addView(open); top.addView(status, LinearLayout.LayoutParams(0, -2, 1f)); top.addView(exportBtn)
        view = FrameView(this)
        val bottom = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        playBtn = Button(this).apply { text = "재생"; isEnabled = false; setOnClickListener { togglePlay() } }
        seek = SeekBar(this).apply {
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onProgressChanged(sb: SeekBar, p: Int, fromUser: Boolean) { if (fromUser) { wanted.set(p); kick() } }
                override fun onStartTrackingTouch(sb: SeekBar) { playing.set(false); playBtn.text = "재생" }
                override fun onStopTrackingTouch(sb: SeekBar) {}
            })
        }
        bottom.addView(playBtn); bottom.addView(seek, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(top, LinearLayout.LayoutParams(-1, -2))
        root.addView(view, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(bottom, LinearLayout.LayoutParams(-1, -2))
        setContentView(root)
        intent?.data?.let { load(it) }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); intent.data?.let { load(it) } }

    private fun pick() {
        if (busy.get()) return
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type = "*/*" }, 1)
    }

    @Deprecated("Activity result")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 1 && resultCode == RESULT_OK) data?.data?.let { load(it) }
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
        playing.set(false); playBtn.isEnabled = false; exportBtn.isEnabled = false
        io.execute {
            val t0 = SystemClock.elapsedRealtime()
            try {
                val (name, size) = meta(uri)
                fileName = name.substringBeforeLast('.')
                val key = (name + "_" + size).hashCode().toUInt().toString(16)
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
                ui.post { onLoaded(d!!, "$name · ${d.frameCount}프레임 · 오브젝트 ${d.objCount} · $how ${"%.1f".format(dt)}초") }
            } catch (e: Throwable) {
                ui.post { status.text = "열기 실패: ${e.message}"; busy.set(false) }
            }
        }
    }

    private fun onLoaded(d: SfaDoc, msg: String) {
        doc = d; renderer = FrameRenderer(d)
        status.text = msg
        seek.max = maxOf(d.frameCount - 1, 0); seek.progress = 0
        playBtn.isEnabled = true; exportBtn.isEnabled = true
        busy.set(false)
        wanted.set(0); startRenderLoop(); kick()
    }

    private val lock = Object()
    private fun kick() { synchronized(lock) { lock.notifyAll() } }

    /** 그리기 전용 스레드: 원하는 프레임을 그려 화면에 넘긴다. 재생 중이면 24fps에 맞춰 다음 프레임으로 간다. */
    private fun startRenderLoop() {
        renderThread?.interrupt()
        val d = doc ?: return; val r = renderer ?: return
        renderThread = Thread {
            var last = -1
            var bmpA: Bitmap? = null; var bmpB: Bitmap? = null
            try {
                while (!Thread.currentThread().isInterrupted) {
                    val vw = view.width.coerceAtLeast(2)
                    val w = minOf(vw, 1280); val h = maxOf(2, (w * d.ratio).toInt())
                    if (bmpA == null || bmpA.width != w || bmpA.height != h) {
                        bmpA = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888); bmpB = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
                    }
                    val f = wanted.get().coerceIn(0, d.frameCount - 1)
                    if (f == last && !playing.get()) { synchronized(lock) { lock.wait(200) }; continue }
                    val t0 = SystemClock.elapsedRealtime()
                    r.render(f, bmpA!!)
                    val shown = bmpA; bmpA = bmpB; bmpB = shown
                    last = f
                    val took = SystemClock.elapsedRealtime() - t0
                    view.post { view.show(shown) ; seek.progress = f; if (playing.get()) status.text = "${f + 1}/${d.frameCount} · ${if (took > 0) minOf(1000 / took, 99) else 99}fps 그리기" }
                    if (playing.get()) {
                        val wait = 1000L / fps - took
                        if (wait > 0) Thread.sleep(wait)
                        wanted.set(if (f + 1 >= d.frameCount) 0 else f + 1)
                    }
                }
            } catch (_: InterruptedException) {}
        }.apply { priority = Thread.MAX_PRIORITY; start() }
    }

    private fun togglePlay() {
        val p = !playing.get(); playing.set(p); playBtn.text = if (p) "정지" else "재생"; kick()
    }

    private fun exportOrCancel() {
        val d = doc ?: return
        if (busy.get()) { cancelExport.set(true); return }
        busy.set(true); cancelExport.set(false); playing.set(false); playBtn.text = "재생"
        exportBtn.text = "취소"
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
                    VideoExporter(d, fps).export(pfd.fileDescriptor, { i, n -> ui.post { status.text = "내보내는 중 $i/$n" } }, { cancelExport.get() })
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
                ui.post { busy.set(false); exportBtn.text = "MP4 내보내기" }
            }
        }
    }

    override fun onDestroy() { renderThread?.interrupt(); io.shutdownNow(); super.onDestroy() }
}

/** 현재 프레임 비트맵을 비율 유지해 가운데에 그린다. */
class FrameView(ctx: android.content.Context) : View(ctx) {
    private var bmp: Bitmap? = null
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val dst = RectF()
    fun show(b: Bitmap?) { bmp = b; invalidate() }
    override fun onDraw(c: Canvas) {
        c.drawColor(Color.BLACK)
        val b = bmp ?: return
        val s = minOf(width.toFloat() / b.width, height.toFloat() / b.height)
        val w = b.width * s; val h = b.height * s
        dst.set((width - w) / 2, (height - h) / 2, (width + w) / 2, (height + h) / 2)
        c.drawBitmap(b, null, dst, paint)
    }
}
