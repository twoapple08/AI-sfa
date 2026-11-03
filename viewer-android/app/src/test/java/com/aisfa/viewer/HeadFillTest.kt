package com.aisfa.viewer

import android.graphics.Bitmap
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class HeadFillTest {
    private fun doc(segments: String): SfaDoc {
        val xml = """<Sequence HeightWidthRatio="1"><Frame>
            <AO ID="1" TypeId="1" Color="-16776961" ThicknessScale="5" DrawOrder="1"><AP ID="11" X="50" Y="0"/><AP ID="12" X="50" Y="100"/></AO>
            <AO ID="2" TypeId="2" Color="-65536" DrawOrder="2"><AP ID="21" X="50" Y="30"/><AP ID="22" X="50" Y="70"/></AO>
            <FR Color="-1">$segments</FR></Frame></Sequence>"""
        val zip = ByteArrayOutputStream()
        ZipOutputStream(zip).use { it.putNextEntry(ZipEntry("fixture.xml")); it.write(xml.toByteArray()); it.closeEntry() }
        return SfaParser().parse(ByteArrayInputStream(zip.toByteArray()))
    }

    private fun center(d: SfaDoc): Int {
        val bitmap = Bitmap.createBitmap(400, 400, Bitmap.Config.ARGB_8888)
        FrameRenderer(d).render(0, bitmap)
        return bitmap.getPixel(200, 200).also { bitmap.recycle() }
    }

    @Test fun explicitWholeCircleOccludesAndMissingKindDoesNotHideTheDefect() {
        val good = doc("""<FS Kind="1" ObjId="2"/>""")
        val bad = doc("""<FS ObjId="2" StartT="0" EndT="1"/>""")
        assertEquals(0, good.invalidFillSegments)
        assertEquals(1, bad.invalidFillSegments)
        assertEquals(-1, center(good))
        assertEquals(-16776961, center(bad))
    }

    @Test fun wrongPointOwnerUnknownKindAndInvalidIntervalAreRejected() {
        val bad = listOf(
            """<FS Kind="0" ObjId="2" StartPtId="11" EndPtId="22" StartT="0" EndT="1"/>""",
            """<FS Kind="0" ObjId="2" StartPtId="999" EndPtId="22" StartT="0" EndT="1"/>""",
            """<FS Kind="0" ObjId="2" StartT="0.5" EndT="0.5"/>""",
            """<FS Kind="0" ObjId="2" StartT="NaN" EndT="1"/>""",
            """<FS Kind="1" ObjId="1"/>""",
            """<FS Kind="256" ObjId="2" StartT="0" EndT="1"/>"""
        )
        for (fs in bad) assertEquals(fs, 1, doc(fs).invalidFillSegments)
        assertEquals(0, doc("""<FS Kind="0" ObjId="2" StartPtId="21" EndPtId="22" StartT="0" EndT="1"/>""").invalidFillSegments)
        assertEquals(0, doc("""<FS Kind="0" ObjId="2" StartPtId="-1" EndPtId="-1" StartT="0" EndT="1"/>""").invalidFillSegments)
    }

    @Test fun wholeCircleCannotBeMixedWithOtherSegmentsInOneContour() {
        val d = doc("""<FS Kind="1" ObjId="2"/><FS Kind="0" ObjId="1" StartT="0" EndT="1"/>""")
        assertEquals(2, d.invalidFillSegments)
        assertEquals(-16776961, center(d))
    }

    @Test fun cachePreservesValidityAndOldVersionIsRejected() {
        val d = doc("""<FS ObjId="2" StartT="0" EndT="1"/>""")
        val output = ByteArrayOutputStream(); d.write(output)
        val copy = SfaDoc.read(ByteArrayInputStream(output.toByteArray()))!!
        assertArrayEquals(d.sKind, copy.sKind)
        assertArrayEquals(d.sValid, copy.sValid)
        assertEquals(center(d), center(copy))
        val old = ByteArrayOutputStream()
        DataOutputStream(old).use { it.writeInt(SfaDoc.MAGIC); it.writeInt(3) }
        assertNull(SfaDoc.read(ByteArrayInputStream(old.toByteArray())))
    }

    @Test fun suppliedClipRegressionWhenAvailable() {
        val folder = System.getenv("SFA_TEST_DIR")?.takeUnless { it.isBlank() } ?: return
        val old = File(folder, "legacy_head_fill.sfa"); val fixed = File(folder, "fixed_head_fill.sfa")
        if (!old.exists() || !fixed.exists()) return
        val a = old.inputStream().use { SfaParser().parse(it) }
        val b = fixed.inputStream().use { SfaParser().parse(it) }
        assertEquals(469, a.invalidFillSegments)
        assertEquals(0, b.invalidFillSegments)
        assertEquals(240, b.frameCount)
        assertArrayEquals(a.oId, b.oId)
        assertArrayEquals(a.px, b.px, 0f)
        assertArrayEquals(a.py, b.py, 0f)
    }
}
