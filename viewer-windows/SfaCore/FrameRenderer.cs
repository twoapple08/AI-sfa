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

        float X(int i) => ox + uw * d.Px[i] / 100f;
        float Y(int i) => oy + uh * d.Py[i] / 100f;

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
                float t0 = d.ST0[k], t1 = d.ST1[k];
                if (d.OType[o] == 3) { t0 = Math.Clamp(t0, 0, 1); t1 = Math.Clamp(t1, 0, 1); if (Math.Abs(t1 - t0) <= 1e-6f) continue; }
                SegPoints(o, t0, t1);
            }
            if (sn < 3) return false;
            outp.MoveTo(sx[0], sy[0]); for (int i = 1; i < sn; i++) outp.LineTo(sx[i], sy[i]); outp.Close();
            return true;
        }

        void DrawFill(int fl, SKCanvas c)
        {
            int col = d.FlColor[fl];
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
            int col = d.OColor[o];
            if (((uint)col >> 24) == 0) return;
            float w = 8f * Math.Max(d.OThick[o], 0f);
            if (w <= 0) return;
            stroke.Color = new SKColor((uint)col);
            stroke.StrokeWidth = Math.Max(MathF.Round(1.14f * w, MidpointRounding.AwayFromZero), 0.5f);
            if (ObjPath(o, path)) c.DrawPath(path, stroke);
        }

        void DrawGlow(int o, SKCanvas c)
        {
            float gr = d.OGlowR[o], gt = d.OGlowT[o], ga = d.OGlowA[o];
            if (gr <= 0 || gt <= 0 || ga <= 0) return;
            if (ga > 1) ga /= 255f;
            float wg = 8f * Math.Max(d.OThick[o], 0f) * Math.Max(gt / 10f, 0f);
            float sig = MathF.Sqrt(gr * gr + 0.29f * 0.29f);
            if (!ObjPath(o, path)) return;
            uint gc = (uint)d.OGlowColor[o];
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
                for (int o = o0; o < o0 + on; o++) if (d.OLayer[o] == lid) objs.Add(o);
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
