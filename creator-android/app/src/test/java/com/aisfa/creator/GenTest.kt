package com.aisfa.creator

import com.aisfa.creator.gen.EffectLib
import com.aisfa.creator.gen.Generator
import com.aisfa.creator.gen.MotionLib
import com.aisfa.creator.gen.Request
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** 생성기 시험: 길이·FPS에 따른 프레임 수와 5초 분할, SFA 쓰기. SFA_OUT_DIR가 있으면 파일을 남긴다(서버 검사·렌더용). */
class GenTest {
    private val lib = File("src/main/assets/motion_lib.txt").inputStream().use { MotionLib.read(it) }
    private val fx = File("src/main/assets/effects.txt").takeIf { it.exists() }?.inputStream()?.use { EffectLib.read(it) } ?: EffectLib.EMPTY

    @Test fun libLoads() {
        assertTrue(lib.punches.size >= 20)
        assertEquals(7, lib.timing.gap[0])
    }

    @Test fun partsAndFiles() {
        val out = System.getenv("SFA_OUT_DIR")?.takeIf { it.isNotEmpty() }?.let { File(it).apply { mkdirs() } }
        for ((sec, t, p, seed) in listOf(listOf(12, 24, 24, 1), listOf(7, 24, 12, 2), listOf(10, 30, 15, 3))) {
            val g = Generator.generate(lib, fx, Request("1v1", sec, t, p, seed.toLong(), dark = seed == 3))
            assertEquals(sec * p, g.frameCount)
            assertEquals((sec + 4) / 5, g.parts.size)
            assertEquals(5 * p, g.parts[0].count())
            g.parts.forEachIndexed { i, r ->
                val name = "gen_s${seed}_${t}_${p}_${i + 1}"
                val f = out?.let { File(it, "$name.sfa") } ?: File.createTempFile(name, ".sfa")
                f.outputStream().use { Generator.writeSfa(g, r, name, it) }
                assertTrue(f.length() > 1000)
                if (out == null) f.delete()
            }
            println("seed=$seed ${sec}s ($t,$p): frames=${g.frameCount} parts=${g.parts.size} hits=${g.scene.let { 0 }}")
        }
    }
}
