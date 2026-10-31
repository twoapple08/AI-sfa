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
            val bmp = Bitmap.createBitmap(1920, (1920 * d.ratio).toInt(), Bitmap.Config.ARGB_8888)
            // SFA_FPS="21,11"이면 프레임 번호를 그 시간표의 출력 번호로 본다(보간 시험)
            val fps = System.getenv("SFA_FPS")?.split(",")?.map { it.trim().toInt() }
            val tl = if (fps != null) Timeline(d.frameCount, fps[0], fps[1]) else null
            for (f in fr.split(",").map { it.toInt() }) {
                val t0 = System.nanoTime()
                if (tl != null) r.render(tl, f, bmp) else r.render(f, bmp)
                println("render $name $f ${(System.nanoTime() - t0) / 1e6}ms glow=${r.tGlow/1e6} fill=${r.tFill/1e6} base=${r.tBase/1e6} bigGlow=${r.nGlowBig}"); r.tGlow=0; r.tFill=0; r.tBase=0; r.nGlowBig=0
                File(out, "${name}_$f.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
            }
        }
    }
}
