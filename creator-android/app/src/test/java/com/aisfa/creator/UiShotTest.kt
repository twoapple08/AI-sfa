package com.aisfa.creator

import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Looper
import com.aisfa.creator.gen.Generator
import com.aisfa.creator.gen.MotionLib
import com.aisfa.creator.gen.Request
import org.json.JSONObject
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** 화면 배치 확인용: 첫 화면(빈 목록·최근 생성)과 결과 화면을 창 크기별 PNG로 저장한다(SFA_OUT_DIR 필요). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class UiShotTest {
    private fun shot(a: MainActivity, out: File) {
        val v = a.window.decorView
        val b = Bitmap.createBitmap(v.width.coerceAtLeast(1), v.height.coerceAtLeast(1), Bitmap.Config.ARGB_8888)
        v.draw(Canvas(b))
        out.outputStream().use { b.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun idle(ms: Long) {
        val end = System.currentTimeMillis() + ms
        while (System.currentTimeMillis() < end) { shadowOf(Looper.getMainLooper()).idle(); Thread.sleep(50) }
    }

    @Test fun screens() {
        val out = File(System.getenv("SFA_OUT_DIR").takeUnless { it.isNullOrEmpty() } ?: return).apply { mkdirs() }
        val lib = File("src/main/assets/motion_lib.txt").inputStream().use { MotionLib.read(it) }
        val g = Generator.generate(lib, Request("1v1", 12, 24, 24, 1, false))
        val sfa = File(out, "ui_sample.sfa").apply { outputStream().use { Generator.writeSfa(g, 0 until g.frameCount, "sample", it) } }
        val d = sfa.inputStream().use { SfaParser().parse(it) }
        val fb = Bitmap.createBitmap(1920, 1080, Bitmap.Config.ARGB_8888).also { FrameRenderer(d).render(53, it) }
        // 뒤의 셋은 멀티윈도우(화면 반)·팝업 창·펼친 폴드(거의 정사각)
        for (q in listOf("w411dp-h891dp-port-xxhdpi", "w891dp-h411dp-land-xxhdpi", "w411dp-h430dp-port-xxhdpi", "w300dp-h480dp-port-xhdpi", "w673dp-h841dp-port-xhdpi")) {
            RuntimeEnvironment.setQualifiers(q)
            val home = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            File(home.filesDir, "gens").deleteRecursively()
            val home0 = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            idle(300); shot(home0, File(out, "home_$q.png"))
            // 최근 생성 3개를 넣어 둔 첫 화면
            for (i in 1..3) {
                val dir = File(home.filesDir, "gens/g$i").apply { mkdirs() }
                File(dir, "parts").mkdirs()
                for (p in 1..((i * 5 + 4) / 5)) File(dir, "parts/x_$p.sfa").writeText("")
                File(dir, "meta.json").writeText(JSONObject().put("name", "1v1_1021_12000$i").put("prompt", "1v1").put("seconds", i * 5)
                    .put("tween", 24).put("play", if (i == 2) 12 else 24).put("seed", i).put("dark", i == 3).put("created", i.toLong()).toString())
                Bitmap.createScaledBitmap(fb, 480, 270, true).let { t -> File(dir, "thumb.jpg").outputStream().use { t.compress(Bitmap.CompressFormat.JPEG, 85, it) } }
            }
            val home2 = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            idle(300); shot(home2, File(out, "home2_$q.png"))
            val a = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            a.showForTest(d, fb, "1v1_1021_120001", g.parts.size)
            idle(300); shot(a, File(out, "player_$q.png"))
        }
    }
}
