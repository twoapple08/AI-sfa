package com.aisfa.viewer

import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Looper
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** 화면 배치 확인용: 첫 화면·플레이어(세로/가로)를 PNG로 저장한다(SFA_TEST_DIR, SFA_OUT_DIR 필요). */
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
        val dir = System.getenv("SFA_TEST_DIR").takeUnless { it.isNullOrEmpty() } ?: return
        val out = File(System.getenv("SFA_OUT_DIR").takeUnless { it.isNullOrEmpty() } ?: return).apply { mkdirs() }
        for (q in listOf("w411dp-h891dp-port-xxhdpi", "w891dp-h411dp-land-xxhdpi")) {
            RuntimeEnvironment.setQualifiers(q)
            val home = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            idle(300); shot(home, File(out, "home_$q.png"))
            val d = File(dir, "p1.sfa").inputStream().use { SfaParser().parse(it) }
            val fb = Bitmap.createBitmap(1920, (1920 * d.ratio).toInt(), Bitmap.Config.ARGB_8888).also { FrameRenderer(d).render(30, it) }
            val a = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            a.showForTest(d, fb, "VSJEDO2DDIRECTION")
            idle(300); shot(a, File(out, "player_$q.png"))
            File(a.filesDir, "thumbs").mkdirs()
            Bitmap.createScaledBitmap(fb, 480, 270, true).let { t -> File(a.filesDir, "thumbs/k1.jpg").outputStream().use { t.compress(Bitmap.CompressFormat.JPEG, 85, it) } }
            a.getSharedPreferences("v", 0).edit().putString("recent", """[{"uri":"content://x/1","name":"VSJEDO2DDIRECTION","key":"k1","frames":120},{"uri":"content://x/2","name":"VSSGTOILET","key":"k2","frames":114},{"uri":"content://x/3","name":"팡","key":"k1","frames":90}]""").commit()
            val home2 = Robolectric.buildActivity(MainActivity::class.java).setup().get()
            idle(300); shot(home2, File(out, "home2_$q.png"))
        }
    }
}
