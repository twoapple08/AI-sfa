package com.aisfa.viewer

import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * SFA(ZIP 안의 XML 하나)를 한 번 훑어 [SfaDoc]으로 만든다.
 * 범용 XML 파서 대신 이 형식에 맞춘 바이트 스캐너를 써서 큰 파일(수백 MB XML)도 빠르게 읽는다.
 * 필요한 시작 태그(Sequence/Frame/LayerDef/AO/AP/AC/FR/FS)와 </Frame>만 본다.
 */
class SfaParser(private val progress: (Long) -> Unit = {}) {

    private class GI(cap: Int = 1024) {
        var a = IntArray(cap); var n = 0
        fun add(v: Int) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
        fun trim() = a.copyOf(n)
    }
    private class GF(cap: Int = 1024) {
        var a = FloatArray(cap); var n = 0
        fun add(v: Float) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
        fun trim() = a.copyOf(n)
    }
    private class GB(cap: Int = 1024) {
        var a = ByteArray(cap); var n = 0
        fun add(v: Byte) { if (n == a.size) a = a.copyOf(n * 2); a[n++] = v }
        fun trim() = a.copyOf(n)
    }

    // 전역 배열
    private val fBg = GI(); private val fLS = GI(); private val fLC = GI(); private val fOS = GI(); private val fOC = GI(); private val fFS = GI(); private val fFC = GI()
    private val lId = GI(); private val lVis = GB()
    private val oType = GB(); private val oColor = GI(); private val oLayer = GI(); private val oOrder = GI()
    private val oThick = GF(); private val oGR = GF(); private val oGT = GF(); private val oGC = GI(); private val oGA = GF()
    private val oPS = GI(); private val oPC = GB(); private val oGroup = GI(); private val oIdA = GI()
    private val px = GF(); private val py = GF(); private val pIdx = GI()
    private val flColor = GI(); private val flSS = GI(); private val flSC = GI()
    private val sObjRaw = GI(); private val sCont = GI(); private val sT0 = GF(); private val sT1 = GF()

    // 프레임 안 임시
    private val aoIdToLocal = HashMap<Long, Int>()
    private val apIdToLocal = HashMap<Long, Int>()
    private val acFrom = GI(); private val acTo = ArrayList<Long>()
    private var frameObj0 = 0; private var frameFill0 = 0; private var frameSeg0 = 0; private var frameLayer0 = 0
    private var inFrame = false

    private var ratio = 0.5625f
    private var seqBg = -1

    fun parse(input: InputStream): SfaDoc {
        val zin = ZipInputStream(input.buffered(1 shl 16))
        val e = zin.nextEntry ?: error("SFA 안에 XML이 없습니다")
        Scanner(zin).run()
        zin.close()
        return build()
    }

    private fun build(): SfaDoc {
        val s = SfaDoc()
        s.ratio = ratio; s.bgColor = seqBg
        s.frameCount = fBg.n
        s.fBg = fBg.trim(); s.fLayerStart = fLS.trim(); s.fLayerCount = fLC.trim()
        s.fObjStart = fOS.trim(); s.fObjCount = fOC.trim(); s.fFillStart = fFS.trim(); s.fFillCount = fFC.trim()
        s.layerCount = lId.n; s.lId = lId.trim(); s.lVisible = BooleanArray(lVis.n) { lVis.a[it].toInt() != 0 }
        s.objCount = oType.n
        s.oType = oType.trim(); s.oColor = oColor.trim(); s.oLayer = oLayer.trim(); s.oOrder = oOrder.trim()
        s.oThick = oThick.trim(); s.oGlowR = oGR.trim(); s.oGlowT = oGT.trim(); s.oGlowColor = oGC.trim(); s.oGlowA = oGA.trim()
        s.oPtStart = oPS.trim(); s.oPtCount = oPC.trim(); s.oGroup = oGroup.trim(); s.oId = oIdA.trim()
        s.ptCount = px.n; s.px = px.trim(); s.py = py.trim(); s.pIdx = pIdx.trim()
        s.fillCount = flColor.n; s.flColor = flColor.trim(); s.flSegStart = flSS.trim(); s.flSegCount = flSC.trim()
        s.segCount = sT0.n; s.sObj = sObjRaw.trim(); s.sT0 = sT0.trim(); s.sT1 = sT1.trim(); s.sCont = sCont.trim()
        return s
    }

    // ---- 태그 처리 ----
    private var curObjLocal = -1
    private var curApLocalOwner = -1

    private fun startTag(name: String, attrs: Attrs) {
        when (name) {
            "Sequence" -> {
                ratio = attrs.float("HeightWidthRatio", 0.5625f).let { if (it <= 0f) 0.5625f else it }
                seqBg = attrs.argb("BackgroundColor", -1)
            }
            "Frame" -> {
                inFrame = true
                fBg.add(attrs.argb("BackgroundColor", seqBg))
                frameObj0 = oType.n; frameFill0 = flColor.n; frameSeg0 = sT0.n; frameLayer0 = lId.n
                aoIdToLocal.clear(); apIdToLocal.clear(); acFrom.n = 0; acTo.clear()
            }
            "LayerDef" -> {
                lId.add(attrs.int("ID", 0)); lVis.add(if (attrs.str("Visible") == "false") 0 else 1)
            }
            "AO" -> {
                val local = oType.n - frameObj0
                aoIdToLocal[attrs.long("ID", -1)] = local
                oType.add(attrs.int("TypeId", 1).toByte())
                oColor.add(attrs.argb("Color", -16777216))
                oLayer.add(attrs.int("LayerId", 0))
                oOrder.add(attrs.int("DrawOrder", attrs.int("ID", 0)))
                oThick.add(attrs.float("ThicknessScale", 1f))
                oGR.add(attrs.float("GlowRadius", 0f)); oGT.add(attrs.float("GlowThickness", 0f))
                oGC.add(attrs.argb("GlowColor", -1)); oGA.add(attrs.float("GlowAlpha", 0f))
                oPS.add(px.n); oPC.add(0); oGroup.add(local); oIdA.add(attrs.int("ID", local))
                curObjLocal = local
            }
            "AP" -> {
                if (curObjLocal >= 0) {
                    px.add(attrs.float("X", 0f)); py.add(attrs.float("Y", 0f)); pIdx.add(attrs.int("Index", oPC.a[frameObj0 + curObjLocal].toInt()))
                    val gi = frameObj0 + curObjLocal
                    oPC.a[gi] = (oPC.a[gi] + 1).toByte()
                    apIdToLocal[attrs.long("ID", -1)] = curObjLocal
                    curApLocalOwner = curObjLocal
                }
            }
            "AC" -> {
                if (curApLocalOwner >= 0) { acFrom.add(curApLocalOwner); acTo.add(attrs.long("ConnPtId", -1)) }
            }
            "FR" -> {
                curObjLocal = -1; curApLocalOwner = -1
                flColor.add(attrs.argb("Color", -16777216)); flSS.add(sT0.n); flSC.add(0)
            }
            "FS" -> {
                if (flColor.n > frameFill0) {
                    val objId = attrs.long("ObjId", -1)
                    sObjRaw.add(0); sCont.add(attrs.int("Contour", 0))
                    pendingSegObj.add(objId)
                    sT0.add(attrs.float("StartT", 0f)); sT1.add(attrs.float("EndT", 1f))
                    flSC.a[flColor.n - 1]++
                }
            }
        }
    }

    private val pendingSegObj = ArrayList<Long>()

    private fun endFrame() {
        val n = oType.n - frameObj0
        // 채우기 경계의 ObjId → 전역 오브젝트 번호(없으면 -1)
        for (k in pendingSegObj.indices) {
            val loc = aoIdToLocal[pendingSegObj[k]]
            sObjRaw.a[frameSeg0 + k] = if (loc == null) -1 else frameObj0 + loc
        }
        pendingSegObj.clear()
        // 연결 그룹(union-find): AC가 가리키는 점의 주인 오브젝트와 묶는다
        val parent = IntArray(n) { it }
        fun find(x0: Int): Int { var x = x0; while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x] }; return x }
        for (k in 0 until acFrom.n) {
            val to = apIdToLocal[acTo[k]] ?: continue
            val a = find(acFrom.a[k]); val b = find(to)
            if (a != b) parent[a] = b
        }
        for (i in 0 until n) oGroup.a[frameObj0 + i] = find(i)
        // 옛 형식(2023 이전 등)은 LayerDef가 없다. 원래 앱은 레이어 목록이 없으면 오브젝트 전체를 그린다(AOT-OBJECT-TWEEN-PAIR).
        // 오브젝트의 LayerId 값마다(대개 0 하나) 보이는 레이어를 만들어 준다.
        if (lId.n == frameLayer0) {
            val seen = LinkedHashSet<Int>()
            for (i in frameObj0 until oType.n) seen.add(oLayer.a[i])
            for (v in seen) { lId.add(v); lVis.add(1) }
        }
        fLS.add(frameLayer0); fLC.add(lId.n - frameLayer0)
        fOS.add(frameObj0); fOC.add(n)
        fFS.add(frameFill0); fFC.add(flColor.n - frameFill0)
        inFrame = false; curObjLocal = -1; curApLocalOwner = -1
    }

    // ---- 바이트 스캐너 ----
    class Attrs {
        val names = ArrayList<String>(16); val vals = ArrayList<CharSequence>(16)
        fun clear() { names.clear(); vals.clear() }
        fun str(k: String): String? { val i = names.indexOf(k); return if (i < 0) null else vals[i].toString() }
        fun float(k: String, d: Float): Float { val i = names.indexOf(k); return if (i < 0) d else parseF(vals[i]) ?: d }
        fun long(k: String, d: Long): Long { val i = names.indexOf(k); return if (i < 0) d else parseL(vals[i]) ?: d }
        fun int(k: String, d: Int): Int = long(k, d.toLong()).toInt()
        /** 색은 부호 있는/없는 32비트가 섞여 있다. 하위 32비트만 쓴다. */
        fun argb(k: String, d: Int): Int = long(k, d.toLong()).toInt()
    }

    private inner class Scanner(private val inp: InputStream) {
        private val buf = ByteArray(1 shl 16); private var len = 0; private var pos = 0; private var total = 0L
        private fun next(): Int {
            if (pos >= len) {
                len = inp.read(buf); pos = 0
                if (len <= 0) return -1
                total += len
                if ((total and 0xFFFFFL) < len) progress(total)
            }
            return buf[pos++].toInt() and 0xFF
        }
        private val name = StringBuilder(); private val an = StringBuilder()
        private val attrs = Attrs()
        private val valPool = ArrayList<StringBuilder>()

        fun run() {
            var c = next()
            while (c >= 0) {
                if (c != '<'.code) { c = next(); continue }
                c = next()
                if (c == '/'.code) { // 끝 태그
                    name.setLength(0); c = next()
                    while (c >= 0 && c != '>'.code) { name.append(c.toChar()); c = next() }
                    if (name.trim().toString() == "Frame") endFrame()
                    c = next(); continue
                }
                if (c == '?'.code || c == '!'.code) { while (c >= 0 && c != '>'.code) c = next(); c = next(); continue }
                name.setLength(0)
                while (c >= 0 && c != ' '.code && c != '>'.code && c != '/'.code && c != '\n'.code && c != '\t'.code && c != '\r'.code) { name.append(c.toChar()); c = next() }
                attrs.clear(); var vi = 0
                // 속성
                while (c >= 0 && c != '>'.code) {
                    if (c == '/'.code || c == ' '.code || c == '\n'.code || c == '\t'.code || c == '\r'.code) { c = next(); continue }
                    an.setLength(0)
                    while (c >= 0 && c != '='.code && c != '>'.code && c != ' '.code) { an.append(c.toChar()); c = next() }
                    if (c != '='.code) continue
                    c = next() // 따옴표
                    val q = c
                    if (vi == valPool.size) valPool.add(StringBuilder())
                    val v = valPool[vi++]; v.setLength(0)
                    c = next()
                    while (c >= 0 && c != q) { v.append(c.toChar()); c = next() }
                    attrs.names.add(an.toString()); attrs.vals.add(v)
                    c = next()
                }
                startTag(name.toString(), attrs)
                c = next()
            }
        }
    }

    companion object {
        fun parseL(s: CharSequence): Long? {
            var i = 0; var neg = false; var v = 0L
            if (s.isEmpty()) return null
            if (s[0] == '-') { neg = true; i = 1 }
            if (i >= s.length) return null
            while (i < s.length) { val ch = s[i]; if (ch < '0' || ch > '9') return s.toString().toDoubleOrNull()?.toLong(); v = v * 10 + (ch - '0'); i++ }
            return if (neg) -v else v
        }

        fun parseF(s: CharSequence): Float? {
            // 빠른 경로: [-]digits[.digits][e[-]digits]
            var i = 0; val n = s.length; if (n == 0) return null
            var neg = false
            if (s[0] == '-') { neg = true; i++ }
            var m = 0L; var exp = 0; var digits = 0
            while (i < n && s[i] in '0'..'9') { if (digits < 18) { m = m * 10 + (s[i] - '0'); digits++ } else exp++; i++ }
            if (i < n && s[i] == '.') { i++; while (i < n && s[i] in '0'..'9') { if (digits < 18) { m = m * 10 + (s[i] - '0'); digits++; exp-- }; i++ } }
            if (i < n && (s[i] == 'e' || s[i] == 'E')) {
                i++; var eneg = false
                if (i < n && (s[i] == '-' || s[i] == '+')) { eneg = s[i] == '-'; i++ }
                var e = 0; while (i < n && s[i] in '0'..'9') { e = e * 10 + (s[i] - '0'); i++ }
                exp += if (eneg) -e else e
            }
            if (i != n) return s.toString().toFloatOrNull()
            val v = m.toDouble() * Math.pow(10.0, exp.toDouble())
            return (if (neg) -v else v).toFloat()
        }
    }
}
