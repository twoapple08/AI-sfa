package com.aisfa.creator

import android.media.Image

/** ARGB → 인코더 입력 Image(YUV420, 평면 간격은 기기마다 다르므로 stride를 따른다). BT.601 limited range. */
object Yuv {
    fun fill(img: Image, argb: IntArray, w: Int, h: Int) {
        val pl = img.planes
        val yb = pl[0].buffer; val ys = pl[0].rowStride; val yp = pl[0].pixelStride
        val ub = pl[1].buffer; val us = pl[1].rowStride; val up = pl[1].pixelStride
        val vb = pl[2].buffer; val vs = pl[2].rowStride; val vp = pl[2].pixelStride
        for (y in 0 until h) {
            val row = y * w; val yo = y * ys
            for (x in 0 until w) {
                val c = argb[row + x]
                val r = (c shr 16) and 255; val g = (c shr 8) and 255; val b = c and 255
                yb.put(yo + x * yp, (((66 * r + 129 * g + 25 * b + 128) shr 8) + 16).toByte())
            }
        }
        for (y in 0 until h / 2) {
            for (x in 0 until w / 2) {
                val i = (2 * y) * w + 2 * x
                var r = 0; var g = 0; var b = 0
                for (k in intArrayOf(i, i + 1, i + w, i + w + 1)) { val c = argb[k]; r += (c shr 16) and 255; g += (c shr 8) and 255; b += c and 255 }
                r /= 4; g /= 4; b /= 4
                ub.put(y * us + x * up, (((-38 * r - 74 * g + 112 * b + 128) shr 8) + 128).toByte())
                vb.put(y * vs + x * vp, (((112 * r - 94 * g - 18 * b + 128) shr 8) + 128).toByte())
            }
        }
    }
}
