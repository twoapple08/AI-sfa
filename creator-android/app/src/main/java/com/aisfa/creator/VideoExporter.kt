package com.aisfa.creator

import android.graphics.Bitmap
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.MediaMuxer
import java.io.FileDescriptor

/**
 * 프레임을 하나씩 그려 H.264 MP4로 저장한다(휴대폰 내장 인코더).
 * 프레임 시각을 정확히 주려고 Surface 대신 YUV 버퍼 입력을 쓴다.
 */
class VideoExporter(private val doc: SfaDoc, private val tl: Timeline, private val width: Int = 1920) {
    private val fps = tl.fps
    private val height = ((width * doc.ratio).toInt() + 1) and 1.inv()

    fun export(out: FileDescriptor, progress: (Int, Int) -> Unit, cancelled: () -> Boolean): Boolean {
        // 여러 스레드가 앞 프레임들을 미리 그리고(픽셀 배열), 인코더는 순서대로 받아 쓴다.
        val threads = (Runtime.getRuntime().availableProcessors() - 1).coerceIn(1, 4)
        val pool = java.util.concurrent.Executors.newFixedThreadPool(threads)
        val renderers = ThreadLocal.withInitial { FrameRenderer(doc) }
        val bitmaps = ThreadLocal.withInitial { Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888) }
        val pending = java.util.ArrayDeque<java.util.concurrent.Future<IntArray>>()
        var submitted = 0
        fun fill() {
            while (submitted < tl.count && pending.size < threads + 1) {
                val f = submitted++
                pending.add(pool.submit<IntArray> {
                    val b = bitmaps.get()!!
                    renderers.get()!!.render(tl, f, b)
                    IntArray(width * height).also { b.getPixels(it, 0, width, 0, 0, width, height) }
                })
            }
        }
        val fmt = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            setInteger(MediaFormat.KEY_BIT_RATE, 16_000_000)
            setInteger(MediaFormat.KEY_FRAME_RATE, fps)
            setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1)
        }
        val codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        codec.configure(fmt, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
        codec.start()
        val muxer = MediaMuxer(out, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        var track = -1; var muxStarted = false
        val info = MediaCodec.BufferInfo()
        var next = 0; var inputDone = false; var ok = true
        try {
            while (true) {
                if (!inputDone) {
                    val ii = codec.dequeueInputBuffer(10_000)
                    if (ii >= 0) {
                        if (next >= tl.count || cancelled()) {
                            codec.queueInputBuffer(ii, 0, 0, ptsUs(next), MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true; if (cancelled()) ok = false
                        } else {
                            fill()
                            val argb = pending.poll()!!.get()
                            fill()
                            val img = codec.getInputImage(ii)!!
                            Yuv.fill(img, argb, width, height)
                            codec.queueInputBuffer(ii, 0, width * height * 3 / 2, ptsUs(next), 0)
                            next++
                            progress(next, tl.count)
                        }
                    }
                }
                val oi = codec.dequeueOutputBuffer(info, 10_000)
                if (oi == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    track = muxer.addTrack(codec.outputFormat); muxer.start(); muxStarted = true
                } else if (oi >= 0) {
                    val ob = codec.getOutputBuffer(oi)!!
                    if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) info.size = 0
                    if (info.size > 0 && muxStarted) { ob.position(info.offset); ob.limit(info.offset + info.size); muxer.writeSampleData(track, ob, info) }
                    codec.releaseOutputBuffer(oi, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                }
            }
        } finally {
            codec.stop(); codec.release()
            if (muxStarted) muxer.stop()
            muxer.release(); pool.shutdownNow()
        }
        return ok
    }

    private fun ptsUs(i: Int) = i * 1_000_000L / fps
}
