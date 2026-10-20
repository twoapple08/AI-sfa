package com.aisfa.viewer

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.InputStream
import java.io.OutputStream

/**
 * SFA 문서 전체를 기본형 배열로 담는다(프레임별 시작 위치 + 전역 배열).
 * 원래 앱처럼 DB에 옮기지 않으므로 열기가 빠르다. 한 번 변환한 뒤에는 [write]/[read] 캐시로 바로 연다.
 */
class SfaDoc {
    var ratio = 0.5625f
    var bgColor = -1

    // 프레임
    var frameCount = 0
    var fBg = IntArray(0)
    var fLayerStart = IntArray(0); var fLayerCount = IntArray(0)
    var fObjStart = IntArray(0); var fObjCount = IntArray(0)
    var fFillStart = IntArray(0); var fFillCount = IntArray(0)

    // 레이어(파일 목록 순서 = 그리는 순서, 첫 레이어가 맨 아래)
    var layerCount = 0
    var lId = IntArray(0); var lVisible = BooleanArray(0)

    // 오브젝트
    var objCount = 0
    var oType = ByteArray(0); var oColor = IntArray(0); var oLayer = IntArray(0); var oOrder = IntArray(0)
    var oThick = FloatArray(0); var oGlowR = FloatArray(0); var oGlowT = FloatArray(0)
    var oGlowColor = IntArray(0); var oGlowA = FloatArray(0)
    var oPtStart = IntArray(0); var oPtCount = ByteArray(0); var oGroup = IntArray(0)
    var oId = IntArray(0) // AO ID: 보간 때 앞뒤 프레임의 같은 오브젝트를 찾는다

    // 점
    var ptCount = 0
    var px = FloatArray(0); var py = FloatArray(0)
    var pIdx = IntArray(0) // AP Index: 보간 때 점 대응

    // 채우기와 경계 조각
    var fillCount = 0
    var flColor = IntArray(0); var flSegStart = IntArray(0); var flSegCount = IntArray(0)
    var segCount = 0
    var sObj = IntArray(0); var sT0 = FloatArray(0); var sT1 = FloatArray(0); var sCont = IntArray(0)

    fun write(out: OutputStream) {
        val d = DataOutputStream(out.buffered(1 shl 16))
        d.writeInt(MAGIC); d.writeInt(VERSION)
        d.writeFloat(ratio); d.writeInt(bgColor)
        d.writeInt(frameCount)
        for (a in arrayOf(fBg, fLayerStart, fLayerCount, fObjStart, fObjCount, fFillStart, fFillCount)) wI(d, a, frameCount)
        d.writeInt(layerCount); wI(d, lId, layerCount); for (i in 0 until layerCount) d.writeBoolean(lVisible[i])
        d.writeInt(objCount)
        d.write(oType, 0, objCount); wI(d, oColor, objCount); wI(d, oLayer, objCount); wI(d, oOrder, objCount)
        wF(d, oThick, objCount); wF(d, oGlowR, objCount); wF(d, oGlowT, objCount); wI(d, oGlowColor, objCount); wF(d, oGlowA, objCount)
        wI(d, oPtStart, objCount); d.write(oPtCount, 0, objCount); wI(d, oGroup, objCount); wI(d, oId, objCount)
        d.writeInt(ptCount); wF(d, px, ptCount); wF(d, py, ptCount); wI(d, pIdx, ptCount)
        d.writeInt(fillCount); wI(d, flColor, fillCount); wI(d, flSegStart, fillCount); wI(d, flSegCount, fillCount)
        d.writeInt(segCount); wI(d, sObj, segCount); wF(d, sT0, segCount); wF(d, sT1, segCount); wI(d, sCont, segCount)
        d.flush()
    }

    companion object {
        const val MAGIC = 0x53464131 // "SFA1"
        const val VERSION = 3

        private fun wI(d: DataOutputStream, a: IntArray, n: Int) { for (i in 0 until n) d.writeInt(a[i]) }
        private fun wF(d: DataOutputStream, a: FloatArray, n: Int) { for (i in 0 until n) d.writeFloat(a[i]) }
        private fun rI(d: DataInputStream, n: Int) = IntArray(n) { d.readInt() }
        private fun rF(d: DataInputStream, n: Int) = FloatArray(n) { d.readFloat() }

        fun read(inp: InputStream): SfaDoc? {
            val d = DataInputStream(inp.buffered(1 shl 16))
            if (d.readInt() != MAGIC || d.readInt() != VERSION) return null
            val s = SfaDoc()
            s.ratio = d.readFloat(); s.bgColor = d.readInt()
            val n = d.readInt(); s.frameCount = n
            s.fBg = rI(d, n); s.fLayerStart = rI(d, n); s.fLayerCount = rI(d, n)
            s.fObjStart = rI(d, n); s.fObjCount = rI(d, n); s.fFillStart = rI(d, n); s.fFillCount = rI(d, n)
            s.layerCount = d.readInt(); s.lId = rI(d, s.layerCount); s.lVisible = BooleanArray(s.layerCount) { d.readBoolean() }
            val o = d.readInt(); s.objCount = o
            s.oType = ByteArray(o).also { d.readFully(it) }
            s.oColor = rI(d, o); s.oLayer = rI(d, o); s.oOrder = rI(d, o)
            s.oThick = rF(d, o); s.oGlowR = rF(d, o); s.oGlowT = rF(d, o); s.oGlowColor = rI(d, o); s.oGlowA = rF(d, o)
            s.oPtStart = rI(d, o); s.oPtCount = ByteArray(o).also { d.readFully(it) }; s.oGroup = rI(d, o); s.oId = rI(d, o)
            val p = d.readInt(); s.ptCount = p; s.px = rF(d, p); s.py = rF(d, p); s.pIdx = rI(d, p)
            val f = d.readInt(); s.fillCount = f; s.flColor = rI(d, f); s.flSegStart = rI(d, f); s.flSegCount = rI(d, f)
            val g = d.readInt(); s.segCount = g; s.sObj = rI(d, g); s.sT0 = rF(d, g); s.sT1 = rF(d, g); s.sCont = rI(d, g)
            return s
        }
    }
}
