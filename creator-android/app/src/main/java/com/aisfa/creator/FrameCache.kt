package com.aisfa.creator

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

/**
 * 재생용 프레임을 여러 스레드로 미리 그려 JPEG로 디스크에 저장한다.
 * 오브젝트가 많은 프레임은 한 장 그리는 데 수백 ms~수 초가 걸려 실시간 재생이 멈춘다(사용자 보고).
 * 미리 그려 두면 재생은 JPEG 디코딩(수 ms)만 하면 된다. 캐시는 다음에 같은 파일을 열 때도 쓴다.
 * 프레임 번호는 시간표([Timeline])의 출력 번호다. 보간하면 원본보다 많다.
 */
class FrameCache(private val doc: SfaDoc, val tl: Timeline, private val dir: File, val width: Int,
                 threads: Int = maxOf(1, Runtime.getRuntime().availableProcessors() - 1)) {
    val height = maxOf(2, (width * doc.ratio).toInt())
    private val state = ConcurrentHashMap<Int, Int>()   // 1 = 그리는 중, 2 = 완료
    private val pool = Executors.newFixedThreadPool(threads) { r -> Thread(r).apply { priority = Thread.NORM_PRIORITY - 1 } }
    private val renderers = ThreadLocal.withInitial { FrameRenderer(doc) }
    private val bitmaps = ThreadLocal.withInitial { Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888) }
    private val stopped = AtomicBoolean(false)
    val done = AtomicInteger(0)
    private val lock = Object()

    init {
        dir.mkdirs()
        for (f in 0 until tl.count) if (file(f).exists()) { state[f] = 2; done.incrementAndGet() }
    }

    private fun file(f: Int) = File(dir, "$f.jpg")

    fun isReady(f: Int) = state[f] == 2

    /** start 프레임부터 끝까지, 이어서 처음부터 start 전까지 아직 없는 프레임을 그린다. */
    fun prefetchFrom(start: Int) {
        for (k in 0 until tl.count) {
            val f = (start + k) % tl.count
            if (state.putIfAbsent(f, 1) != null) continue
            pool.execute { renderOne(f) }
        }
    }

    private fun renderOne(f: Int) {
        if (stopped.get()) { state.remove(f); return }
        try {
            val bmp = bitmaps.get()!!
            renderers.get()!!.render(tl, f, bmp)
            val tmp = File(dir, "$f.tmp")
            tmp.outputStream().buffered().use { bmp.compress(Bitmap.CompressFormat.JPEG, 92, it) }
            tmp.renameTo(file(f))
            state[f] = 2; done.incrementAndGet()
        } catch (e: Throwable) {
            state.remove(f)
        }
        synchronized(lock) { lock.notifyAll() }
    }

    /** 준비된 프레임을 읽는다. 아직이면 최대 waitMs 기다리고, 그래도 없으면 null. */
    fun get(f: Int, waitMs: Long, into: Bitmap?): Bitmap? {
        val end = System.currentTimeMillis() + waitMs
        while (state[f] != 2) {
            if (state[f] == null) { state[f] = 1; pool.execute { renderOne(f) } }
            val left = end - System.currentTimeMillis()
            if (left <= 0) return null
            synchronized(lock) { lock.wait(minOf(left, 50)) }
        }
        val opt = BitmapFactory.Options().apply { inMutable = true; if (into != null) inBitmap = into }
        return runCatching { BitmapFactory.decodeFile(file(f).path, opt) }.getOrNull()
            ?: BitmapFactory.decodeFile(file(f).path)
    }

    fun close() { stopped.set(true); pool.shutdownNow() }
}
