using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Xml;

namespace SfaCore
{
    /// <summary>SFA 문서를 기본형 배열로 담는다(안드로이드 뷰어 SfaDoc.kt와 같은 구조). 원래 앱처럼 DB에 옮기지 않아 열기가 빠르다.</summary>
    public sealed class SfaDoc
    {
        public float Ratio = 0.5625f;
        public int BgColor = -1;
        public int FrameCount;
        public int[] FBg, FLayerStart, FLayerCount, FObjStart, FObjCount, FFillStart, FFillCount;
        public int LayerCount; public int[] LId; public bool[] LVisible;
        public int ObjCount;
        public byte[] OType; public int[] OColor, OLayer, OOrder; public float[] OThick, OGlowR, OGlowT, OGlowA; public int[] OGlowColor;
        public int[] OPtStart; public byte[] OPtCount; public int[] OGroup;
        public int PtCount; public float[] Px, Py;
        public int FillCount; public int[] FlColor, FlSegStart, FlSegCount;
        public int SegCount; public int[] SObj, SCont; public float[] ST0, ST1;

        const int Magic = 0x53464131, Version = 2;

        public void Write(Stream s)
        {
            using var w = new BinaryWriter(new BufferedStream(s, 1 << 16), System.Text.Encoding.UTF8, leaveOpen: true);
            w.Write(Magic); w.Write(Version); w.Write(Ratio); w.Write(BgColor);
            w.Write(FrameCount);
            foreach (var a in new[] { FBg, FLayerStart, FLayerCount, FObjStart, FObjCount, FFillStart, FFillCount }) WI(w, a);
            w.Write(LayerCount); WI(w, LId); foreach (var b in LVisible) w.Write(b);
            w.Write(ObjCount); w.Write(OType); WI(w, OColor); WI(w, OLayer); WI(w, OOrder);
            WF(w, OThick); WF(w, OGlowR); WF(w, OGlowT); WI(w, OGlowColor); WF(w, OGlowA);
            WI(w, OPtStart); w.Write(OPtCount); WI(w, OGroup);
            w.Write(PtCount); WF(w, Px); WF(w, Py);
            w.Write(FillCount); WI(w, FlColor); WI(w, FlSegStart); WI(w, FlSegCount);
            w.Write(SegCount); WI(w, SObj); WF(w, ST0); WF(w, ST1); WI(w, SCont);
        }

        public static SfaDoc Read(Stream s)
        {
            using var r = new BinaryReader(new BufferedStream(s, 1 << 16), System.Text.Encoding.UTF8, leaveOpen: true);
            if (r.ReadInt32() != Magic || r.ReadInt32() != Version) return null;
            var d = new SfaDoc { Ratio = r.ReadSingle(), BgColor = r.ReadInt32() };
            int n = d.FrameCount = r.ReadInt32();
            d.FBg = RI(r, n); d.FLayerStart = RI(r, n); d.FLayerCount = RI(r, n); d.FObjStart = RI(r, n); d.FObjCount = RI(r, n); d.FFillStart = RI(r, n); d.FFillCount = RI(r, n);
            int l = d.LayerCount = r.ReadInt32(); d.LId = RI(r, l); d.LVisible = new bool[l]; for (int i = 0; i < l; i++) d.LVisible[i] = r.ReadBoolean();
            int o = d.ObjCount = r.ReadInt32(); d.OType = r.ReadBytes(o); d.OColor = RI(r, o); d.OLayer = RI(r, o); d.OOrder = RI(r, o);
            d.OThick = RF(r, o); d.OGlowR = RF(r, o); d.OGlowT = RF(r, o); d.OGlowColor = RI(r, o); d.OGlowA = RF(r, o);
            d.OPtStart = RI(r, o); d.OPtCount = r.ReadBytes(o); d.OGroup = RI(r, o);
            int p = d.PtCount = r.ReadInt32(); d.Px = RF(r, p); d.Py = RF(r, p);
            int f = d.FillCount = r.ReadInt32(); d.FlColor = RI(r, f); d.FlSegStart = RI(r, f); d.FlSegCount = RI(r, f);
            int g = d.SegCount = r.ReadInt32(); d.SObj = RI(r, g); d.ST0 = RF(r, g); d.ST1 = RF(r, g); d.SCont = RI(r, g);
            return d;
        }

        static void WI(BinaryWriter w, int[] a) { foreach (var v in a) w.Write(v); }
        static void WF(BinaryWriter w, float[] a) { foreach (var v in a) w.Write(v); }
        static int[] RI(BinaryReader r, int n) { var a = new int[n]; for (int i = 0; i < n; i++) a[i] = r.ReadInt32(); return a; }
        static float[] RF(BinaryReader r, int n) { var a = new float[n]; for (int i = 0; i < n; i++) a[i] = r.ReadSingle(); return a; }

        // ---------- SFA(ZIP 안 XML) 읽기 ----------
        sealed class LI { public int[] A = new int[1024]; public int N; public void Add(int v) { if (N == A.Length) Array.Resize(ref A, N * 2); A[N++] = v; } public int[] Trim() { var r = new int[N]; Array.Copy(A, r, N); return r; } }
        sealed class LF { public float[] A = new float[1024]; public int N; public void Add(float v) { if (N == A.Length) Array.Resize(ref A, N * 2); A[N++] = v; } public float[] Trim() { var r = new float[N]; Array.Copy(A, r, N); return r; } }
        sealed class LB { public byte[] A = new byte[1024]; public int N; public void Add(byte v) { if (N == A.Length) Array.Resize(ref A, N * 2); A[N++] = v; } public byte[] Trim() { var r = new byte[N]; Array.Copy(A, r, N); return r; } }

        static long L(string s, long d) => s == null ? d : long.TryParse(s, out var v) ? v : double.TryParse(s, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var x) ? (long)x : d;
        static float F(string s, float d) => s == null ? d : float.TryParse(s, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var v) ? v : d;

        public static SfaDoc Parse(Stream sfa, Action<long> progress = null)
        {
            using var zip = new ZipArchive(sfa, ZipArchiveMode.Read);
            ZipArchiveEntry entry = null;
            foreach (var e in zip.Entries) { entry = e; break; }
            if (entry == null) throw new InvalidDataException("SFA 안에 XML이 없습니다");
            using var raw = entry.Open();
            var counting = new CountingStream(raw, progress);
            using var x = XmlReader.Create(counting, new XmlReaderSettings { IgnoreWhitespace = true, IgnoreComments = true, DtdProcessing = DtdProcessing.Ignore });

            var d = new SfaDoc();
            LI fBg = new(), fLS = new(), fLC = new(), fOS = new(), fOC = new(), fFS = new(), fFC = new();
            LI lId = new(); LB lVis = new();
            LB oType = new(); LI oColor = new(), oLayer = new(), oOrder = new(); LF oThick = new(), oGR = new(), oGT = new(), oGA = new(); LI oGC = new();
            LI oPS = new(); LB oPC = new(); LI oGroup = new();
            LF px = new(), py = new();
            LI flColor = new(), flSS = new(), flSC = new();
            LI sObj = new(), sCont = new(); LF sT0 = new(), sT1 = new();
            var aoIdToLocal = new Dictionary<long, int>(); var apIdToLocal = new Dictionary<long, int>();
            var acFrom = new List<int>(); var acTo = new List<long>(); var pendingSeg = new List<long>();
            int frameObj0 = 0, frameFill0 = 0, frameSeg0 = 0, frameLayer0 = 0, curObj = -1, curApOwner = -1;
            int seqBg = -1;

            while (x.Read())
            {
                if (x.NodeType == XmlNodeType.EndElement && x.Name == "Frame")
                {
                    int n = oType.N - frameObj0;
                    for (int k = 0; k < pendingSeg.Count; k++)
                        sObj.A[frameSeg0 + k] = aoIdToLocal.TryGetValue(pendingSeg[k], out var loc) ? frameObj0 + loc : -1;
                    pendingSeg.Clear();
                    var parent = new int[n]; for (int i = 0; i < n; i++) parent[i] = i;
                    int Find(int a) { while (parent[a] != a) { parent[a] = parent[parent[a]]; a = parent[a]; } return a; }
                    for (int k = 0; k < acFrom.Count; k++)
                        if (apIdToLocal.TryGetValue(acTo[k], out var to)) { int a = Find(acFrom[k]), b = Find(to); if (a != b) parent[a] = b; }
                    for (int i = 0; i < n; i++) oGroup.A[frameObj0 + i] = Find(i);
                    fLS.Add(frameLayer0); fLC.Add(lId.N - frameLayer0); fOS.Add(frameObj0); fOC.Add(n); fFS.Add(frameFill0); fFC.Add(flColor.N - frameFill0);
                    curObj = -1; curApOwner = -1;
                    continue;
                }
                if (x.NodeType != XmlNodeType.Element) continue;
                switch (x.Name)
                {
                    case "Sequence":
                        d.Ratio = F(x.GetAttribute("HeightWidthRatio"), 0.5625f); if (d.Ratio <= 0) d.Ratio = 0.5625f;
                        seqBg = (int)L(x.GetAttribute("BackgroundColor"), -1); d.BgColor = seqBg; break;
                    case "Frame":
                        fBg.Add((int)L(x.GetAttribute("BackgroundColor"), seqBg));
                        frameObj0 = oType.N; frameFill0 = flColor.N; frameSeg0 = sT0.N; frameLayer0 = lId.N;
                        aoIdToLocal.Clear(); apIdToLocal.Clear(); acFrom.Clear(); acTo.Clear(); break;
                    case "LayerDef":
                        lId.Add((int)L(x.GetAttribute("ID"), 0)); lVis.Add((byte)(x.GetAttribute("Visible") == "false" ? 0 : 1)); break;
                    case "AO":
                    {
                        int local = oType.N - frameObj0;
                        aoIdToLocal[L(x.GetAttribute("ID"), -1)] = local;
                        oType.Add((byte)L(x.GetAttribute("TypeId"), 1)); oColor.Add((int)L(x.GetAttribute("Color"), -16777216));
                        oLayer.Add((int)L(x.GetAttribute("LayerId"), 0)); oOrder.Add((int)L(x.GetAttribute("DrawOrder"), L(x.GetAttribute("ID"), 0)));
                        oThick.Add(F(x.GetAttribute("ThicknessScale"), 1)); oGR.Add(F(x.GetAttribute("GlowRadius"), 0)); oGT.Add(F(x.GetAttribute("GlowThickness"), 0));
                        oGC.Add((int)L(x.GetAttribute("GlowColor"), -1)); oGA.Add(F(x.GetAttribute("GlowAlpha"), 0));
                        oPS.Add(px.N); oPC.Add(0); oGroup.Add(local); curObj = local; break;
                    }
                    case "AP":
                        if (curObj >= 0)
                        {
                            px.Add(F(x.GetAttribute("X"), 0)); py.Add(F(x.GetAttribute("Y"), 0));
                            oPC.A[frameObj0 + curObj]++; apIdToLocal[L(x.GetAttribute("ID"), -1)] = curObj; curApOwner = curObj;
                        }
                        break;
                    case "AC":
                        if (curApOwner >= 0) { acFrom.Add(curApOwner); acTo.Add(L(x.GetAttribute("ConnPtId"), -1)); }
                        break;
                    case "FR":
                        curObj = -1; curApOwner = -1;
                        flColor.Add((int)L(x.GetAttribute("Color"), -16777216)); flSS.Add(sT0.N); flSC.Add(0); break;
                    case "FS":
                        if (flColor.N > frameFill0)
                        {
                            sObj.Add(0); sCont.Add((int)L(x.GetAttribute("Contour"), 0)); pendingSeg.Add(L(x.GetAttribute("ObjId"), -1));
                            sT0.Add(F(x.GetAttribute("StartT"), 0)); sT1.Add(F(x.GetAttribute("EndT"), 1)); flSC.A[flColor.N - 1]++;
                        }
                        break;
                }
            }
            d.FrameCount = fBg.N; d.FBg = fBg.Trim(); d.FLayerStart = fLS.Trim(); d.FLayerCount = fLC.Trim(); d.FObjStart = fOS.Trim(); d.FObjCount = fOC.Trim(); d.FFillStart = fFS.Trim(); d.FFillCount = fFC.Trim();
            d.LayerCount = lId.N; d.LId = lId.Trim(); d.LVisible = new bool[lVis.N]; for (int i = 0; i < lVis.N; i++) d.LVisible[i] = lVis.A[i] != 0;
            d.ObjCount = oType.N; d.OType = oType.Trim(); d.OColor = oColor.Trim(); d.OLayer = oLayer.Trim(); d.OOrder = oOrder.Trim();
            d.OThick = oThick.Trim(); d.OGlowR = oGR.Trim(); d.OGlowT = oGT.Trim(); d.OGlowColor = oGC.Trim(); d.OGlowA = oGA.Trim();
            d.OPtStart = oPS.Trim(); d.OPtCount = oPC.Trim(); d.OGroup = oGroup.Trim();
            d.PtCount = px.N; d.Px = px.Trim(); d.Py = py.Trim();
            d.FillCount = flColor.N; d.FlColor = flColor.Trim(); d.FlSegStart = flSS.Trim(); d.FlSegCount = flSC.Trim();
            d.SegCount = sT0.N; d.SObj = sObj.Trim(); d.ST0 = sT0.Trim(); d.ST1 = sT1.Trim(); d.SCont = sCont.Trim();
            return d;
        }

        sealed class CountingStream : Stream
        {
            readonly Stream s; readonly Action<long> p; long total, lastReport;
            public CountingStream(Stream s, Action<long> p) { this.s = s; this.p = p; }
            public override int Read(byte[] b, int o, int c) { int n = s.Read(b, o, c); total += n; if (p != null && total - lastReport > (8 << 20)) { lastReport = total; p(total); } return n; }
            public override bool CanRead => true; public override bool CanSeek => false; public override bool CanWrite => false;
            public override long Length => throw new NotSupportedException(); public override long Position { get => total; set => throw new NotSupportedException(); }
            public override void Flush() { } public override long Seek(long o, SeekOrigin r) => throw new NotSupportedException();
            public override void SetLength(long v) => throw new NotSupportedException(); public override void Write(byte[] b, int o, int c) => throw new NotSupportedException();
        }
    }
}
