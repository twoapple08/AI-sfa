package com.aisfa.viewer

import android.graphics.Bitmap
import java.nio.ByteBuffer
import kotlin.math.floor
import kotlin.math.sqrt

/** ALPHA_8 비트맵을 박스 블러 3회로 가우스 근사(sigma 기준). */
object Blur {
    fun gaussianAlpha(bmp: Bitmap, sigma: Float) {
        if (sigma < 0.3f) return
        val w = bmp.width; val h = bmp.height
        val buf = ByteBuffer.allocate(bmp.rowBytes * h)
        bmp.copyPixelsToBuffer(buf)
        val rb = bmp.rowBytes
        val src = FloatArray(w * h)
        val raw = buf.array()
        for (y in 0 until h) for (x in 0 until w) src[y * w + x] = (raw[y * rb + x].toInt() and 0xFF).toFloat()
        val tmp = FloatArray(w * h)
        for (r in boxes(sigma, 3)) {
            boxH(src, tmp, w, h, r); boxV(tmp, src, w, h, r)
        }
        for (y in 0 until h) for (x in 0 until w) raw[y * rb + x] = (src[y * w + x] + 0.5f).toInt().coerceIn(0, 255).toByte()
        buf.rewind(); bmp.copyPixelsFromBuffer(buf)
    }

    private fun boxes(sigma: Float, n: Int): IntArray {
        val wIdeal = sqrt(12.0 * sigma * sigma / n + 1)
        var wl = floor(wIdeal).toInt(); if (wl % 2 == 0) wl--
        val wu = wl + 2
        val mIdeal = (12.0 * sigma * sigma - n * wl * wl - 4.0 * n * wl - 3.0 * n) / (-4.0 * wl - 4)
        val m = Math.round(mIdeal).toInt()
        return IntArray(n) { ((if (it < m) wl else wu) - 1) / 2 }
    }

    private fun boxH(s: FloatArray, d: FloatArray, w: Int, h: Int, r: Int) {
        if (r <= 0) { s.copyInto(d); return }
        val div = 2f * r + 1
        for (y in 0 until h) {
            val row = y * w; var acc = 0f
            for (x in 0..minOf(r, w - 1)) acc += s[row + x]
            for (x in 0 until w) {
                d[row + x] = acc / div
                val addX = x + r + 1; val subX = x - r
                if (addX < w) acc += s[row + addX]
                if (subX >= 0) acc -= s[row + subX]
            }
        }
    }

    private fun boxV(s: FloatArray, d: FloatArray, w: Int, h: Int, r: Int) {
        if (r <= 0) { s.copyInto(d); return }
        val div = 2f * r + 1
        for (x in 0 until w) {
            var acc = 0f
            for (y in -r..r) if (y in 0 until h) acc += s[y * w + x]
            for (y in 0 until h) {
                d[y * w + x] = acc / div
                val addY = y + r + 1; val subY = y - r
                if (addY < h) acc += s[addY * w + x]
                if (subY >= 0) acc -= s[subY * w + x]
            }
        }
    }
}
