package com.aisfa.viewer

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
class VideoExporter(private val doc: SfaDoc, private val fps: Int = 24, private val width: Int = 1920) {
    private val height = ((width * doc.ratio).toInt() + 1) and 1.inv()

    fun export(out: FileDescriptor, progress: (Int, Int) -> Unit, cancelled: () -> Boolean): Boolean {
        val renderer = FrameRenderer(doc)
        val bmp = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
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
        val argb = IntArray(width * height)
        var next = 0; var inputDone = false; var ok = true
        try {
            while (true) {
                if (!inputDone) {
                    val ii = codec.dequeueInputBuffer(10_000)
                    if (ii >= 0) {
                        if (next >= doc.frameCount || cancelled()) {
                            codec.queueInputBuffer(ii, 0, 0, ptsUs(next), MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true; if (cancelled()) ok = false
                        } else {
                            renderer.render(next, bmp)
                            bmp.getPixels(argb, 0, width, 0, 0, width, height)
                            val img = codec.getInputImage(ii)!!
                            Yuv.fill(img, argb, width, height)
                            codec.queueInputBuffer(ii, 0, width * height * 3 / 2, ptsUs(next), 0)
                            next++
                            progress(next, doc.frameCount)
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
            muxer.release(); bmp.recycle()
        }
        return ok
    }

    private fun ptsUs(i: Int) = i * 1_000_000L / fps
}
