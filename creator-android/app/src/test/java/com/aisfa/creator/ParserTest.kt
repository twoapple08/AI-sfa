package com.aisfa.creator

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File

class ParserTest {
    @Test fun numbers() {
        assertEquals(-16777216L, SfaParser.parseL("-16777216"))
        assertEquals(4294967295L, SfaParser.parseL("4294967295"))
        assertEquals(1.5e-5f, SfaParser.parseF("1.5e-05")!!, 1e-10f)
        assertEquals(-22.3f, SfaParser.parseF("-22.3")!!, 1e-5f)
        assertEquals(151.41157f, SfaParser.parseF("151.41157772902395")!!, 1e-3f)
    }

    /** SFA_TEST_DIR 안의 *.sfa를 읽고 개수·캐시 왕복을 출력한다(파일은 저장소에 넣지 않는다). */
    @Test fun realFiles() {
        val dir = System.getenv("SFA_TEST_DIR").takeUnless { it.isNullOrEmpty() } ?: return
        for (f in File(dir).listFiles { x -> x.name.endsWith(".sfa") }!!.sortedBy { it.name }) {
            val t0 = System.nanoTime()
            val d = f.inputStream().use { SfaParser().parse(it) }
            val t1 = System.nanoTime()
            val bo = ByteArrayOutputStream(); d.write(bo)
            val t2 = System.nanoTime()
            val d2 = SfaDoc.read(ByteArrayInputStream(bo.toByteArray()))!!
            val t3 = System.nanoTime()
            assertEquals(d.objCount, d2.objCount); assertEquals(d.segCount, d2.segCount)
            val groups = (0 until d.objCount).map { d.fObjStart.let { _ -> 0 } }.size
            println("${f.name}: frames=${d.frameCount} layers=${d.layerCount} AO=${d.objCount} AP=${d.ptCount} FR=${d.fillCount} FS=${d.segCount} badSeg=${d.sObj.count { it < 0 }} parse=${(t1 - t0) / 1e6}ms cache=${bo.size() / 1e6}MB write=${(t2 - t1) / 1e6}ms read=${(t3 - t2) / 1e6}ms")
        }
    }
}
