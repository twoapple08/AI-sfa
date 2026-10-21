package com.aisfa.creator.gen

import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** 사용자 입력. FPS 순서는 (트위닝, 재생). */
class Request(val prompt: String, val seconds: Int, val tween: Int, val play: Int, val seed: Long, val dark: Boolean)

class Generated(val req: Request, val scene: Scene, val notes: List<String>) {
    val frameCount get() = scene.count
    /** 5초마다 끊은 파일 구간(재생 fps 기준 5×F 프레임). */
    val parts: List<IntRange> get() {
        val per = 5 * req.play
        return (0 until frameCount step per).map { it until minOf(it + per, frameCount) }
    }
}

object Generator {
    val SUPPORTED = listOf("1v1")

    /** NAI식 태그(쉼표 구분)를 읽는다. 지금은 1v1(맨손 둘, 배경·도구 없음)만 만든다. */
    fun tags(prompt: String) = prompt.split(',', '\n').map { it.trim().lowercase() }.filter { it.isNotEmpty() }

    fun generate(lib: MotionLib, req: Request): Generated {
        val notes = ArrayList<String>()
        val t = tags(req.prompt)
        val unknown = t.filter { it !in SUPPORTED }
        if ("1v1" !in t) notes += "1v1 태그가 없어 기본(1v1)으로 만들었습니다"
        if (unknown.isNotEmpty()) notes += "아직 지원하지 않는 태그는 무시했습니다: ${unknown.joinToString(", ")}"
        val base = req.seconds * 24
        val ch = Choreo(lib, req.seed, base).run()
        return Generated(req, Scene(ch, req.play, req.dark, req.seed), notes)
    }

    /** 프레임 구간을 SFA(ZIP 안 XML 하나)로 쓴다. 형식은 원래 앱 내보내기와 같은 요소·속성 이름을 쓴다(sfa.py validate 기준). */
    fun writeSfa(g: Generated, range: IntRange, name: String, out: OutputStream) {
        val zip = ZipOutputStream(out)
        zip.putNextEntry(ZipEntry("$name.xml"))
        val w = zip.bufferedWriter(Charsets.UTF_8)
        writeXml(g, range, name, w)
        w.flush()
        zip.closeEntry()
        zip.finish()
        zip.flush()
    }

    fun writeXml(g: Generated, range: IntRange, name: String, w: Appendable) {
        val seqBg = if (g.req.dark) 0xFF141414.toInt() else -1
        w.append("<?xml version='1.0' encoding='utf-8'?>\n")
        w.append("<Sequence Name=\"").append(esc(name)).append("\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" FrameCount=\"")
            .append(range.count().toString()).append("\" BackgroundColor=\"").append(seqBg.toString()).append("\">\n")
        var ptId = 1
        for ((pos, k) in range.withIndex()) {
            val fr = g.scene.frame(k)
            w.append("  <Frame BackgroundColor=\"").append((fr.bg.toLong() and 0xFFFFFFFFL).toString())
                .append("\" ID=\"").append((pos + 1).toString()).append("\" Position=\"").append(pos.toString()).append("\">\n")
            w.append("    <LayerDef ID=\"0\" Name=\"Layer 1\" Visible=\"true\" Locked=\"false\" />\n")
            // 점 ID를 먼저 매겨 연결(AC)을 양쪽에 적는다
            val ids = HashMap<Int, Int>()
            val start = ptId
            for (o in fr.objs) { ids[o.id] = ptId; ptId += o.pts.size / 2 }
            val conn = HashMap<Int, MutableList<Int>>()
            for (o in fr.objs) for (l in o.links) {
                val a = ids[o.id]!! + l[0]
                val b = (ids[l[1]] ?: continue) + l[2]
                conn.getOrPut(a) { ArrayList() }.add(b); conn.getOrPut(b) { ArrayList() }.add(a)
            }
            for ((order, o) in fr.objs.withIndex()) {
                w.append("    <AO ID=\"").append(o.id.toString()).append("\" TypeId=\"").append(o.type.toString())
                    .append("\" Color=\"").append(o.color.toString()).append("\" LayerId=\"0\" DrawOrder=\"").append((order + 1).toString())
                    .append("\" ThicknessScale=\"").append(f(o.thick)).append("\" ObjectScale=\"1.0\" GlowRadius=\"").append(f(o.glowR))
                    .append("\" GlowThickness=\"").append(f(o.glowT)).append("\" GlowColor=\"").append((o.glowColor.toLong() and 0xFFFFFFFFL).toString())
                    .append("\" GlowAlpha=\"").append(f(o.glowA)).append("\">\n")
                val p0 = ids[o.id]!!
                for (i in 0 until o.pts.size / 2) {
                    val id = p0 + i
                    val x = o.pts[2 * i] / 1920f * 100f; val y = o.pts[2 * i + 1] / 1080f * 100f
                    val c = conn[id]
                    w.append("      <AP ID=\"").append(id.toString()).append("\" Flags=\"").append(if (c != null) "4" else "5")
                        .append("\" Index=\"").append(i.toString()).append("\" X=\"").append(f(x)).append("\" Y=\"").append(f(y))
                    if (c == null) w.append("\" />\n") else {
                        w.append("\">\n")
                        for (b in c) w.append("        <AC ConnPtId=\"").append(b.toString()).append("\" />\n")
                        w.append("      </AP>\n")
                    }
                }
                w.append("    </AO>\n")
            }
            check(ptId > start || fr.objs.isEmpty())
            w.append("  </Frame>\n")
        }
        w.append("</Sequence>\n")
    }

    private fun f(v: Float): String = if (v == v.toInt().toFloat()) "${v.toInt()}.0" else "%.3f".format(java.util.Locale.ROOT, v)
    private fun esc(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
