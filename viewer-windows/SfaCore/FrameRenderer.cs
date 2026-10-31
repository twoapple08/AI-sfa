using System;
using System.Collections.Generic;
using SkiaSharp;

namespace SfaCore
{
    /// <summary>
    /// 한 프레임 그리기. 규칙은 안드로이드 뷰어(FrameRenderer.kt)·서버 기준 렌더러(tools/sfa_render.py)와 같다.
    /// 기준 화면 1920 x (1920*비율), 여백 6px 안 비율 맞춤 / 선 폭 round(1.14*8*ThicknessScale) /
    /// 레이어 목록 순서 → DrawOrder → 연결 그룹마다 글로우 먼저 / 채우기는 Contour별 윤곽을 짝홀 규칙으로.
    /// 안드로이드도 Skia로 그리므로 SkiaSharp로 같은 결과를 낸다.
    /// </summary>
    public sealed class FrameRenderer
    {
        readonly SfaDoc d;
        public readonly float BaseW = 1920f, BaseH;
        readonly float ox, oy, uw, uh;
        readonly SKPaint stroke = new() { IsAntialias = true, Style = SKPaintStyle.Stroke, StrokeCap = SKStrokeCap.Round, StrokeJoin = SKStrokeJoin.Round };
        readonly SKPaint fill = new() { IsAntialias = true, Style = SKPaintStyle.Fill };
        readonly SKPaint glow = new() { IsAntialias = true, Style = SKPaintStyle.Stroke, StrokeCap = SKStrokeCap.Round, StrokeJoin = SKStrokeJoin.Round };
        readonly SKPath path = new(), fpath = new(), hole = new();
        float[] sx = new float[256], sy = new float[256]; int sn;

        public FrameRenderer(SfaDoc doc)
        {
            d = doc; BaseH = MathF.Round(1920f * doc.Ratio);
            float r = doc.Ratio, pad = 6f;
            float aw = Math.Clamp(BaseW - 2 * pad, 1, BaseW), ah = Math.Clamp(BaseH - 2 * pad, 1, BaseH);
            if (ah / aw > r) { uw = aw; uh = aw * r; } else { uh = ah; uw = ah / r; }
            ox = (BaseW - uw) / 2; oy = (BaseH - uh) / 2;
        }

        float X(int i) => ox + uw * (tw ? tx[i - tp0] : d.Px[i]) / 100f;
        float Y(int i) => oy + uh * (tw ? ty[i - tp0] : d.Py[i]) / 100f;

        // ── 보간(중간 장면) 상태: 앞 프레임 구조에 섞은 값을 덮어쓴다. 원본 프레임을 그릴 때는 tw = false ──
        bool tw;
        int tp0, to0, tf0, ts0;
        float[] tx = new float[64], ty = new float[64], tTh = new float[64], tGR = new float[64], tGT = new float[64], tGA = new float[64], tS0 = new float[64], tS1 = new float[64];
        bool[] tOn = new bool[64], tFlOn = new bool[16];
        int[] tCol = new int[64], tGC = new int[64], tFlCol = new int[16];
        int Col(int o) => tw ? tCol[o - to0] : d.OColor[o];
        float Thick(int o) => tw ? tTh[o - to0] : d.OThick[o];
        float GlowR(int o) => tw ? tGR[o - to0] : d.OGlowR[o];
        float GlowT(int o) => tw ? tGT[o - to0] : d.OGlowT[o];
        int GlowC(int o) => tw ? tGC[o - to0] : d.OGlowColor[o];
        float GlowA(int o) => tw ? tGA[o - to0] : d.OGlowA[o];
        float SegT0(int k) => tw ? tS0[k - ts0] : d.ST0[k];
        float SegT1(int k) => tw ? tS1[k - ts0] : d.ST1[k];

        /// <summary>출력 프레임 j(시간표 기준)를 그린다. 원본 위치가 정수면 원본 프레임, 아니면 앞뒤를 섞은 중간 장면.</summary>
        public void Render(Timeline tl, int j, SKCanvas c, int width)
        {
            float t = tl.T(j);
            if (t <= 0f) { Render(tl.A(j), c, width); return; }
            PrepareTween(tl.A(j), tl.B(j), t);
            try { Render(tl.A(j), c, width); } finally { tw = false; }
        }

        int mapFrame = -1;
        readonly Dictionary<int, int> idMap = new();

        /// <summary>
        /// 원래 앱의 중간 장면 규칙(AOT-OBJECT-TWEEN-PAIR, AOT-FILL-TWEEN). 안드로이드 FrameRenderer.prepareTween과 같다.
        /// 같은 ID 오브젝트끼리만 짝(짝 없는 것은 중간 장면에 그리지 않음), 점은 Index 대응, 색 ARGB 채널별, 굵기 선형,
        /// 글로우 반경·두께 round, 글로우 알파 앞 + trunc. 채우기는 짝이면 색·T를 섞고, 짝 없는 앞 채우기는 그대로, 뒤 채우기는 그리지 않는다.
        /// </summary>
        void PrepareTween(int fa, int fb, float t)
        {
            if (mapFrame != fb)
            {
                idMap.Clear();
                for (int o = d.FObjStart[fb]; o < d.FObjStart[fb] + d.FObjCount[fb]; o++) idMap[d.OId[o]] = o;
                mapFrame = fb;
            }
            int o0 = d.FObjStart[fa], on = d.FObjCount[fa];
            int p0 = on > 0 ? d.OPtStart[o0] : 0;
            int pe = on > 0 ? d.OPtStart[o0 + on - 1] + d.OPtCount[o0 + on - 1] : p0;
            if (tx.Length < pe - p0) { tx = new float[pe - p0]; ty = new float[pe - p0]; }
            if (tOn.Length < on) { tOn = new bool[on]; tCol = new int[on]; tTh = new float[on]; tGR = new float[on]; tGT = new float[on]; tGC = new int[on]; tGA = new float[on]; }
            tp0 = p0; to0 = o0;
            var paired = new HashSet<int>();
            for (int k = 0; k < on; k++)
            {
                int o = o0 + k, st = d.OPtStart[o], n = d.OPtCount[o];
                for (int i = 0; i < n; i++) { tx[st + i - p0] = d.Px[st + i]; ty[st + i - p0] = d.Py[st + i]; }
                tOn[k] = idMap.TryGetValue(d.OId[o], out int ob);
                if (!tOn[k]) continue;
                paired.Add(d.OId[o]);
                int sb = d.OPtStart[ob], nb = d.OPtCount[ob];
                for (int i = 0; i < n; i++)
                {
                    int idx = d.PIdx[st + i], m = -1;
                    if (i < nb && d.PIdx[sb + i] == idx) m = sb + i;
                    else for (int q = 0; q < nb; q++) if (d.PIdx[sb + q] == idx) { m = sb + q; break; }
                    if (m >= 0)
                    {
                        tx[st + i - p0] = d.Px[st + i] + (d.Px[m] - d.Px[st + i]) * t;
                        ty[st + i - p0] = d.Py[st + i] + (d.Py[m] - d.Py[st + i]) * t;
                    }
                }
                tCol[k] = LerpArgb(d.OColor[o], d.OColor[ob], t);
                tTh[k] = d.OThick[o] + (d.OThick[ob] - d.OThick[o]) * t;
                tGR[k] = MathF.Round(d.OGlowR[o] + (d.OGlowR[ob] - d.OGlowR[o]) * t, MidpointRounding.AwayFromZero);
                tGT[k] = MathF.Round(d.OGlowT[o] + (d.OGlowT[ob] - d.OGlowT[o]) * t, MidpointRounding.AwayFromZero);
                tGC[k] = LerpArgb(d.OGlowColor[o], d.OGlowColor[ob], t);
                float a0 = d.OGlowA[o], a1 = d.OGlowA[ob];
                tGA[k] = Math.Max(a0, a1) > 1f ? a0 + (int)((a1 - a0) * t) : a0 + (a1 - a0) * t;
            }
            // 채우기
            int f0 = d.FFillStart[fa], fn = d.FFillCount[fa], g0 = d.FFillStart[fb], gn = d.FFillCount[fb];
            if (tFlOn.Length < fn) { tFlOn = new bool[fn]; tFlCol = new int[fn]; }
            tf0 = f0;
            int s0 = fn > 0 ? d.FlSegStart[f0] : 0, se = fn > 0 ? d.FlSegStart[f0 + fn - 1] + d.FlSegCount[f0 + fn - 1] : s0;
            if (tS0.Length < se - s0) { tS0 = new float[se - s0]; tS1 = new float[se - s0]; }
            ts0 = s0;
            for (int k = s0; k < se; k++) { tS0[k - s0] = d.ST0[k]; tS1[k - s0] = d.ST1[k]; }
            bool Ok(int fl)
            {
                int outer = 0;
                for (int k = d.FlSegStart[fl]; k < d.FlSegStart[fl] + d.FlSegCount[fl]; k++)
                {
                    if (d.SCont[k] != 0) continue;
                    outer++;
                    int o = d.SObj[k]; if (o < 0 || !paired.Contains(d.OId[o])) return false;
                }
                return outer > 0;
            }
            string Key(int fl, bool withT)
            {
                var b = new System.Text.StringBuilder();
                for (int k = d.FlSegStart[fl]; k < d.FlSegStart[fl] + d.FlSegCount[fl]; k++)
                {
                    int o = d.SObj[k];
                    b.Append(d.SCont[k]).Append(':').Append(o < 0 ? "*" : d.OId[o].ToString());
                    if (withT) b.Append(':').Append(d.ST0[k].ToString("R")).Append(':').Append(d.ST1[k].ToString("R"));
                    b.Append(';');
                }
                return b.ToString();
            }
            var aList = new List<int>(); for (int fl = f0; fl < f0 + fn; fl++) if (Ok(fl)) aList.Add(fl);
            var bList = new List<int>(); for (int g = g0; g < g0 + gn; g++) if (Ok(g)) bList.Add(g);
            for (int i = 0; i < fn; i++) { tFlOn[i] = false; tFlCol[i] = d.FlColor[f0 + i]; }
            var pair = new Dictionary<int, int>(); var usedB = new HashSet<int>();
            var q1 = new Dictionary<string, Queue<int>>();
            foreach (var g in bList) { var k = Key(g, true); if (!q1.TryGetValue(k, out var q)) q1[k] = q = new Queue<int>(); q.Enqueue(g); }
            foreach (var fl in aList) if (q1.TryGetValue(Key(fl, true), out var q) && q.Count > 0) { int g = q.Dequeue(); pair[fl] = g; usedB.Add(g); }
            var ka = new Dictionary<string, List<int>>(); var kb = new Dictionary<string, List<int>>();
            foreach (var fl in aList) if (!pair.ContainsKey(fl)) { var k = Key(fl, false); if (!ka.TryGetValue(k, out var l)) ka[k] = l = new List<int>(); l.Add(fl); }
            foreach (var g in bList) if (!usedB.Contains(g)) { var k = Key(g, false); if (!kb.TryGetValue(k, out var l)) kb[k] = l = new List<int>(); l.Add(g); }
            foreach (var kv in ka) if (kv.Value.Count == 1 && kb.TryGetValue(kv.Key, out var lb) && lb.Count == 1) pair[kv.Value[0]] = lb[0];
            foreach (var fl in aList)
            {
                tFlOn[fl - f0] = true;
                if (!pair.TryGetValue(fl, out int g)) continue; // 짝 없는 앞 채우기: 그대로
                tFlCol[fl - f0] = LerpArgb(d.FlColor[fl], d.FlColor[g], t);
                if (d.FlSegCount[fl] == d.FlSegCount[g])
                    for (int i = 0; i < d.FlSegCount[fl]; i++)
                    {
                        int ka2 = d.FlSegStart[fl] + i, kb2 = d.FlSegStart[g] + i;
                        tS0[ka2 - s0] = d.ST0[ka2] + (d.ST0[kb2] - d.ST0[ka2]) * t;
                        tS1[ka2 - s0] = d.ST1[ka2] + (d.ST1[kb2] - d.ST1[ka2]) * t;
                    }
            }
            tw = true;
        }

        /// <summary>Frame.InterpolateArgbColor: 채널마다 앞값 + round(차 × t), 0–255.</summary>
        static int LerpArgb(int a, int b, float t)
        {
            int r = 0;
            foreach (int sh in new[] { 24, 16, 8, 0 })
            {
                int ca = (int)(((uint)a >> sh) & 255), cb = (int)(((uint)b >> sh) & 255);
                int c = Math.Clamp(ca + (int)MathF.Round((cb - ca) * t, MidpointRounding.AwayFromZero), 0, 255);
                r |= c << sh;
            }
            return r;
        }

        /// <summary>프레임 f를 canvas(가로 width 픽셀)에 그린다.</summary>
        public void Render(int f, SKCanvas c, int width)
        {
            float s = width / BaseW;
            c.Clear(new SKColor((uint)d.FBg[f]));
            c.Save(); c.Scale(s, s);
            Draw(f, c);
            c.Restore();
        }

        bool ObjPath(int o, SKPath p)
        {
            p.Rewind();
            int st = d.OPtStart[o], n = d.OPtCount[o];
            switch (d.OType[o])
            {
                case 1: if (n < 2) return false; p.MoveTo(X(st), Y(st)); p.LineTo(X(st + 1), Y(st + 1)); return true;
                case 2:
                {
                    if (n < 2) return false;
                    float x1 = X(st), y1 = Y(st), x2 = X(st + 1), y2 = Y(st + 1);
                    p.AddCircle((x1 + x2) / 2, (y1 + y2) / 2, MathF.Sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)) / 2);
                    return true;
                }
                case 3: if (n < 3) return false; p.MoveTo(X(st), Y(st)); p.QuadTo(X(st + 1), Y(st + 1), X(st + 2), Y(st + 2)); return true;
                default: return false;
            }
        }

        void Push(float x, float y) { if (sn == sx.Length) { Array.Resize(ref sx, sn * 2); Array.Resize(ref sy, sn * 2); } sx[sn] = x; sy[sn] = y; sn++; }

        void SegPoints(int o, float t0, float t1)
        {
            int st = d.OPtStart[o], n = d.OPtCount[o];
            switch (d.OType[o])
            {
                case 2:
                    if (n >= 2)
                    {
                        float x1 = X(st), y1 = Y(st), x2 = X(st + 1), y2 = Y(st + 1);
                        float cx = (x1 + x2) / 2, cy = (y1 + y2) / 2, r = MathF.Sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1)) / 2;
                        double a0 = Math.Atan2(y1 - cy, x1 - cx);
                        int k = Math.Max(2, (int)Math.Ceiling(Math.Abs(t1 - t0) * Math.PI * 2 * r / 2.0) + 1);
                        for (int i = 0; i < k; i++) { double t = t0 + (t1 - t0) * i / (k - 1); double a = a0 + 2 * Math.PI * t; Push((float)(cx + r * Math.Cos(a)), (float)(cy + r * Math.Sin(a))); }
                    }
                    break;
                case 3:
                    if (n >= 3)
                    {
                        float x0 = X(st), y0 = Y(st), x1 = X(st + 1), y1 = Y(st + 1), x2 = X(st + 2), y2 = Y(st + 2);
                        float L = MathF.Sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0)) + MathF.Sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
                        int k = Math.Max(2, (int)Math.Ceiling(Math.Abs(t1 - t0) * L / 2.0) + 1);
                        for (int i = 0; i < k; i++) { float t = t0 + (t1 - t0) * i / (k - 1), u = 1 - t; Push(u * u * x0 + 2 * u * t * x1 + t * t * x2, u * u * y0 + 2 * u * t * y1 + t * t * y2); }
                    }
                    break;
                default:
                    if (n >= 2)
                    {
                        float x0 = X(st), y0 = Y(st), x1 = X(st + 1), y1 = Y(st + 1);
                        Push(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0); Push(x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1);
                    }
                    break;
            }
        }

        bool ContourPath(int fl, int cont, SKPath outp)
        {
            outp.Rewind(); outp.FillType = SKPathFillType.EvenOdd; sn = 0;
            int s0 = d.FlSegStart[fl];
            for (int k = s0; k < s0 + d.FlSegCount[fl]; k++)
            {
                if (d.SCont[k] != cont) continue;
                int o = d.SObj[k]; if (o < 0) continue;
                float t0 = SegT0(k), t1 = SegT1(k);
                if (d.OType[o] == 3) { t0 = Math.Clamp(t0, 0, 1); t1 = Math.Clamp(t1, 0, 1); if (Math.Abs(t1 - t0) <= 1e-6f) continue; }
                SegPoints(o, t0, t1);
            }
            if (sn < 3) return false;
            outp.MoveTo(sx[0], sy[0]); for (int i = 1; i < sn; i++) outp.LineTo(sx[i], sy[i]); outp.Close();
            return true;
        }

        void DrawFill(int fl, SKCanvas c)
        {
            if (tw && !tFlOn[fl - tf0]) return;
            int col = tw ? tFlCol[fl - tf0] : d.FlColor[fl];
            if (((uint)col >> 24) == 0) return;
            if (!ContourPath(fl, 0, fpath)) return;
            int maxC = 0, s0 = d.FlSegStart[fl];
            for (int k = s0; k < s0 + d.FlSegCount[fl]; k++) if (d.SCont[k] > maxC) maxC = d.SCont[k];
            for (int h = 1; h <= maxC; h++) if (ContourPath(fl, h, hole)) fpath.AddPath(hole);
            fill.Color = new SKColor((uint)col);
            c.DrawPath(fpath, fill);
        }

        void DrawBase(int o, SKCanvas c)
        {
            int col = Col(o);
            if (((uint)col >> 24) == 0) return;
            float w = 8f * Math.Max(Thick(o), 0f);
            if (w <= 0) return;
            stroke.Color = new SKColor((uint)col);
            stroke.StrokeWidth = Math.Max(MathF.Round(1.14f * w, MidpointRounding.AwayFromZero), 0.5f);
            if (ObjPath(o, path)) c.DrawPath(path, stroke);
        }

        void DrawGlow(int o, SKCanvas c)
        {
            float gr = GlowR(o), gt = GlowT(o), ga = GlowA(o);
            if (gr <= 0 || gt <= 0 || ga <= 0) return;
            if (ga > 1) ga /= 255f;
            float wg = 8f * Math.Max(Thick(o), 0f) * Math.Max(gt / 10f, 0f);
            float sig = MathF.Sqrt(gr * gr + 0.29f * 0.29f);
            if (!ObjPath(o, path)) return;
            uint gc = (uint)GlowC(o);
            byte a = (byte)Math.Round(Math.Clamp(ga, 0, 1) * 255);
            glow.Color = new SKColor((byte)(gc >> 16), (byte)(gc >> 8), (byte)gc, a);
            glow.StrokeWidth = Math.Max(wg, 0.01f);
            using var mf = SKMaskFilter.CreateBlur(SKBlurStyle.Normal, sig);
            glow.MaskFilter = mf;
            c.DrawPath(path, glow);
            glow.MaskFilter = null;
        }

        void Draw(int f, SKCanvas c)
        {
            int o0 = d.FObjStart[f], on = d.FObjCount[f], f0 = d.FFillStart[f], fn = d.FFillCount[f];
            var owned = new Dictionary<int, List<int>>();
            for (int fl = f0; fl < f0 + fn; fl++)
            {
                int owner = -1;
                for (int k = d.FlSegStart[fl]; k < d.FlSegStart[fl] + d.FlSegCount[fl]; k++) if (d.SObj[k] >= 0) { owner = d.SObj[k]; break; }
                if (!owned.TryGetValue(owner, out var lst)) owned[owner] = lst = new List<int>(2);
                lst.Add(fl);
            }
            var drawn = new bool[fn];
            int l0 = d.FLayerStart[f];
            var objs = new List<int>();
            for (int li = l0; li < l0 + d.FLayerCount[f]; li++)
            {
                if (!d.LVisible[li]) continue;
                int lid = d.LId[li];
                objs.Clear();
                for (int o = o0; o < o0 + on; o++) if (d.OLayer[o] == lid && (!tw || tOn[o - to0])) objs.Add(o);
                objs.Sort((a, b) => { int x = d.OOrder[a].CompareTo(d.OOrder[b]); return x != 0 ? x : a.CompareTo(b); });
                var units = new Dictionary<int, List<int>>(); var keys = new List<int>();
                foreach (var o in objs) { int g = d.OGroup[o]; if (!units.TryGetValue(g, out var u)) { units[g] = u = new List<int>(4); keys.Add(g); } u.Add(o); }
                foreach (var g in keys)
                {
                    var u = units[g];
                    foreach (var o in u) DrawGlow(o, c);
                    foreach (var o in u)
                    {
                        if (owned.TryGetValue(o, out var fls)) foreach (var fl in fls) if (!drawn[fl - f0]) { drawn[fl - f0] = true; DrawFill(fl, c); }
                        DrawBase(o, c);
                    }
                }
            }
            for (int fl = f0; fl < f0 + fn; fl++) if (!drawn[fl - f0]) DrawFill(fl, c);
        }
    }
}
