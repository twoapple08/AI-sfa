package com.aisfa.viewer

import android.graphics.Bitmap
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** 실제 안드로이드 그래픽(Robolectric 네이티브)으로 프레임을 그려 PNG로 저장한다. 앱 영상과의 비교는 서버 스크립트가 한다. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class RenderTest {
    @Test fun renderSamples() {
        val dir = System.getenv("SFA_TEST_DIR").takeUnless { it.isNullOrEmpty() } ?: return
        val out = File(System.getenv("SFA_OUT_DIR").takeUnless { it.isNullOrEmpty() } ?: return).apply { mkdirs() }
        val spec = System.getenv("SFA_FRAMES").takeUnless { it.isNullOrEmpty() } ?: "p1:0,30;p2:30,60;p3:30,60"
        for (part in spec.split(";")) {
            val (name, fr) = part.split(":")
            val d = File(dir, "$name.sfa").inputStream().use { SfaParser().parse(it) }
            val r = FrameRenderer(d)
            val bmp = Bitmap.createBitmap(1920, 1080, Bitmap.Config.ARGB_8888)
            for (f in fr.split(",").map { it.toInt() }) {
                val t0 = System.nanoTime()
                r.render(f, bmp)
                println("render $name $f ${(System.nanoTime() - t0) / 1e6}ms")
                File(out, "${name}_$f.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
            }
        }
    }
}
