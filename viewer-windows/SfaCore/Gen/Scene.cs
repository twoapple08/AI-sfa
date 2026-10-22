using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Globalization;
using System.IO.Compression;
using System.Text;

// 안드로이드 Scene.kt·Generator.kt를 옮긴 것(같은 규칙·같은 난수 순서).
namespace SfaCore.Gen
{
    /// <summary>SFA 오브젝트 하나. 좌표는 기준 화면(1920×1080) 픽셀. type 1=직선, 2=원(지름 양끝), 3=2차 곡선.</summary>
    public sealed class Obj
    {
        public int id, type, color; public float thick; public float[] pts;
        public float glowR, glowT, glowA; public int glowColor = -1;
        /// <summary>점 번호 → (오브젝트 id, 점 번호) 연결.</summary>
        public List<int[]> links = new();
    }

    public sealed class Fill { public int color; public List<int[]> contours; }
    public sealed class OutFrame { public int bg; public List<Obj> objs; public List<Fill> fills; }

    /// <summary>안무(기준 24fps)를 재생 fps로 고르고 세기별 이펙트를 붙인다(AGENTS.md 이펙트 그리기 원칙).</summary>
    public sealed class Scene
    {
        public const float U = 76f, GROUND = 965f, FIG_T = 1.0f;
        readonly Choreo ch; readonly EffectLib fx; readonly int play; readonly bool dark; readonly long seed;
        readonly State[][] st; readonly int baseN;
        public readonly int Count;
        readonly int bgColor; readonly int[] fig, figBack, warm, cool; readonly int dustCol;
        readonly List<float> wedgeAxis;

        static int C(uint v) => unchecked((int)v);

        public Scene(Choreo ch, EffectLib fx, int play, bool dark, long seed)
        {
            this.ch = ch; this.fx = fx; this.play = play; this.dark = dark; this.seed = seed;
            st = ch.Bake(); baseN = ch.frames;
            Count = Math.Max(1, (int)((long)baseN * play / 24));
            bgColor = dark ? C(0xFF141414) : -1;
            fig = dark ? new[] { C(0xFFF2F2F2), C(0xFFFF7A45) } : new[] { C(0xFF1A1A1A), C(0xFFE0482E) };
            figBack = dark ? new[] { C(0xFFB0B0B0), C(0xFFC4552F) } : new[] { C(0xFF555555), C(0xFFA8361F) };
            warm = new[] { Pal(194, 49, 46), Pal(234, 131, 26), Pal(246, 222, 37), Pal(246, 234, 123) };
            cool = new[] { Pal(56, 124, 173), Pal(86, 218, 233), Pal(86, 218, 233), C(0xFFEFFBFF) };
            dustCol = Pal(196, 131, 92);
            wedgeAxis = fx.wedges.Select(Axis).ToList();
        }

        int Pal(int r, int g, int b)
        {
            if (fx.palette.Count == 0) return C(0xFF000000) | (r << 16) | (g << 8) | b;
            int best = fx.palette[0]; int bd = int.MaxValue;
            foreach (var c in fx.palette)
            {
                int dr = (c >> 16 & 255) - r, dg = (c >> 8 & 255) - g, db = (c & 255) - b, d = dr * dr + dg * dg + db * db;
                if (d < bd) { bd = d; best = c; }
            }
            return best;
        }

        static int Rd(double v) => (int)Math.Floor(v + 0.5);
        int BaseOf(int k) => K.Clamp(Rd(k * 24.0 / play), 0, baseN - 1);
        int OutOf(int t) => K.Clamp(Rd(t * play / 24.0), 0, Count - 1);
        int Local(int k, int t) => Rd((k - OutOf(t)) * 24.0 / play);
        static float Sx(float x) => 960f + x * U;
        static float Sy(float y) => GROUND - y * U;

        float[] World(int i, int f)
        {
            var s = st[i][K.Clamp(f, 0, baseN - 1)];
            var j = s.pose.Joints();
            float h = s.pose.Drop(j) + s.air;
            var o = new float[j.Length];
            for (int n = 0; n < Rig.N; n++) { o[2 * n] = s.x + ch.face[i] * j[2 * n]; o[2 * n + 1] = h - j[2 * n + 1]; }
            return o;
        }

        sealed class Canvas
        {
            public readonly List<Obj> objs = new(); public readonly List<Fill> fills = new();

            public void Shape(EffectLib.Shape sh, int idBase, int color, Func<float, float, float[]> tf)
            {
                if (((uint)color >> 24) == 0) return;
                int id = idBase; var cons = new List<int[]>();
                foreach (var c in sh.contours)
                {
                    var ids = new int[c.Length / 6];
                    for (int j = 0; j < ids.Length; j++)
                    {
                        int o = 6 * j;
                        objs.Add(new Obj { id = id, type = 3, color = 0, thick = 0.1f, pts = K.Cat(tf(c[o], c[o + 1]), tf(c[o + 2], c[o + 3]), tf(c[o + 4], c[o + 5])) });
                        ids[j] = id++;
                    }
                    if (ids.Length > 0) cons.Add(ids);
                }
                if (cons.Count > 0) fills.Add(new Fill { color = color, contours = cons });
            }

            public void Place(EffectLib.Shape sh, int idBase, int color, float wx, float wy, float s, float ang, float dx, float dy)
            {
                float c = (float)Math.Cos(ang), n = (float)Math.Sin(ang);
                Shape(sh, idBase, color, (x, y) =>
                {
                    float rx = x * c - (-y) * n, ry = x * n + (-y) * c;
                    return new[] { Sx(wx + rx * s + dx), Sy(wy + ry * s + dy) };
                });
            }
        }

        /// <summary>알파는 그대로 두고 RGB만 뒤집는다(Kotlin판 버그 수정, Gen.cs 머리말 참고).</summary>
        static int InvRgb(int c) => (c & C(0xFF000000)) | (~c & 0xFFFFFF);

        public OutFrame Frame(int k)
        {
            int f = BaseOf(k);
            var cv = new Canvas();
            int bg = bgColor;
            int mono = 0; Hit monoHit = null; int monoN = 0;
            float shakeX = 0f, shakeY = 0f;
            for (int n = 0; n < ch.hits.Count; n++)
            {
                var h = ch.hits[n];
                if (h.tier != 2 || h.kind != HitKind.HIT) continue;
                int k0 = OutOf(h.t);
                if (k == k0) { mono = 1; monoHit = h; monoN = n; } else if (k == k0 + 1 && play >= 12) { mono = 2; monoHit = h; monoN = n; }
                int l = Local(k, h.t);
                if (l >= 0 && l <= 4) { var r = new JRandom(seed * 31 + k); float a = 0.45f * (1 - l / 5f); shakeX = (r.NextFloat() * 2 - 1) * a; shakeY = (r.NextFloat() * 2 - 1) * a; }
            }
            int inkCol = 0;
            if (mono != 0 && fx.scenes.Count > 0)
            {
                var h = monoHit;
                var sc = fx.scenes[new JRandom(seed * 977 + monoN).NextInt(fx.scenes.Count)];
                var fr = sc.frames[Math.Min(mono - 1, sc.frames.Count - 1)];
                inkCol = fr.whiteInk ? -1 : C(0xFF000000);
                bg = fr.whiteInk ? C(0xFF000000) : -1;
                var w = World(h.att, h.t); float tipX = Sx(w[2 * h.tipJoint]);
                float sc2 = Math.Max(1080f, 1920f / fr.w);
                float lo = 1920f - fr.w * sc2 - (960f - fr.w * sc2 / 2), hi = -(960f - fr.w * sc2 / 2);
                float ox = 960f - fr.w * sc2 / 2 + K.Clamp(K.Clamp((tipX - 960f) * 0.4f, -150f, 150f), lo, hi);
                float oy = 540f - sc2 / 2;
                for (int gi = 0; gi < fr.groups.Count; gi++) cv.Shape(fr.groups[gi], 9_000_000 + gi * 2000, inkCol, (x, y) => new[] { ox + x * sc2, oy + y * sc2 });
            }
            else mono = 0;
            int monoFig = mono != 0 ? (inkCol == -1 ? -1 : C(0xFF000000)) : 0;

            if (mono == 0) for (int n = 0; n < ch.dusts.Count; n++) DustFx(cv, n, ch.dusts[n], k, shakeX, shakeY);
            foreach (int i in new[] { 1, 0 })
            {
                if (mono != 0) Fighter(cv.objs, i, f, InvRgb(monoFig), InvRgb(monoFig), shakeX, shakeY, idOff: 200, thick: FIG_T * 2.6f);
                Fighter(cv.objs, i, f, mono != 0 ? monoFig : fig[i], mono != 0 ? monoFig : figBack[i], shakeX, shakeY);
            }
            if (mono == 0) for (int n = 0; n < ch.hits.Count; n++) HitFx(cv, n, ch.hits[n], k, shakeX, shakeY);
            return new OutFrame { bg = bg, objs = cv.objs, fills = cv.fills };
        }

        void Fighter(List<Obj> objs, int i, int f, int col, int back, float dx, float dy, int idOff = 0, float thick = FIG_T)
        {
            var w = World(i, f);
            float[] P(int n) => new[] { Sx(w[2 * n] + dx), Sy(w[2 * n + 1] + dy) };
            int b = 1 + i * 20 + idOff;
            Obj Line(int id, int a, int c, int color, params int[][] links) => new() { id = b + id, type = 1, color = color, thick = thick, pts = K.Cat(P(a), P(c)), links = links.ToList() };
            var nk = P(Rig.NK); var hd = P(Rig.HD);
            var top = new[] { 2 * hd[0] - nk[0], 2 * hd[1] - nk[1] };
            int[] L(int a, int oid, int pi) => new[] { a, b + oid, pi };
            objs.Add(Line(4, Rig.CH, Rig.E0, back, L(0, 1, 1))); objs.Add(Line(5, Rig.E0, Rig.H0, back, L(0, 4, 1)));
            objs.Add(Line(8, Rig.HIP, Rig.K0, back, L(0, 1, 0))); objs.Add(Line(9, Rig.K0, Rig.A0, back, L(0, 8, 1))); objs.Add(Line(10, Rig.A0, Rig.T0, back, L(0, 9, 1)));
            objs.Add(Line(1, Rig.HIP, Rig.CH, col));
            objs.Add(Line(2, Rig.CH, Rig.NK, col, L(0, 1, 1)));
            objs.Add(new Obj { id = b + 3, type = 2, color = col, thick = thick, pts = K.Cat(top, nk), links = new() { new[] { 1, b + 2, 1 } } });
            objs.Add(Line(11, Rig.HIP, Rig.K1, col, L(0, 1, 0))); objs.Add(Line(12, Rig.K1, Rig.A1, col, L(0, 11, 1))); objs.Add(Line(13, Rig.A1, Rig.T1, col, L(0, 12, 1)));
            objs.Add(Line(6, Rig.CH, Rig.E1, col, L(0, 1, 1))); objs.Add(Line(7, Rig.E1, Rig.H1, col, L(0, 6, 1)));
        }

        static int Alpha(int c, float a) => (Rd(K.Clamp(a, 0f, 1f) * 255) << 24) | (c & 0xFFFFFF);

        void HitFx(Canvas cv, int n, Hit h, int k, float dx, float dy)
        {
            int l = Local(k, h.t);
            if (l < -1 || l > 8) return;
            int idb = 100000 + n * 10000;
            var r = new JRandom(seed * 7919 + n);
            var wt = World(h.att, h.t); var tip = new[] { wt[2 * h.tipJoint], wt[2 * h.tipJoint + 1] };
            var wp = World(h.att, h.t - 2); var prev = new[] { wp[2 * h.tipJoint], wp[2 * h.tipJoint + 1] };
            float vx = tip[0] - prev[0], vy = tip[1] - prev[1];
            float vl = Math.Max((float)Math.Sqrt(vx * vx + vy * vy), 1e-3f); vx /= vl; vy /= vl;
            float dirA = (float)Math.Atan2(vy, vx);
            int col = fig[h.att];

            if (l == 0 || l == 1)
            {
                float len = Math.Min(vl, 3.5f);
                float ax = tip[0] - vx * len, ay = tip[1] - vy * len;
                float side = ch.face[h.att];
                var layers = new (float bulge, int c, float a)[] { (0.36f, col, 0.22f), (0.24f, col, 0.42f), (0.12f, warm[3], 0.75f) };
                for (int m = 0; m < layers.Length; m++)
                {
                    var (bulge, c, a) = layers[m];
                    float mx = (tip[0] + ax) / 2, my = (tip[1] + ay) / 2;
                    float ox = mx - vy * len * bulge * side, oy = my + vx * len * bulge * side;
                    float ix = mx - vy * len * bulge * 0.35f * side, iy = my + vx * len * bulge * 0.35f * side;
                    var seg = new[] { ax, ay, ox, oy, tip[0], tip[1], tip[0], tip[1], ix, iy, ax, ay };
                    cv.Shape(new EffectLib.Shape(new() { seg }), idb + m * 4, Alpha(c, l == 0 ? a : a * 0.45f), (x, y) => new[] { Sx(x + dx), Sy(y + dy) });
                }
            }
            if (l >= -1 && l <= 1 && fx.wedges.Count > 0)
            {
                int c = dark ? C(0xFF9A9A9A) : C(0xFF8C8C8C);
                for (int m = 0; m < 5; m++)
                {
                    int w = (n * 5 + m) % fx.wedges.Count;
                    float off = (m - 2) * 0.45f + (r.NextFloat() - 0.5f) * 0.2f;
                    float back = 1.4f + r.NextFloat() * 1.2f + (l + 1) * 0.3f;
                    float cx = tip[0] - vx * back - vy * off, cy = tip[1] - vy * back + vx * off;
                    cv.Place(fx.wedges[w], idb + 20 + m * 400, Alpha(c, 0.5f - 0.12f * (l + 1)), cx, cy, 0.55f, dirA - wedgeAxis[w], dx, dy);
                }
            }
            if (h.kind == HitKind.WHIFF || fx.wedges.Count == 0) return;

            float big = h.kind == HitKind.BLOCK ? 0.6f : h.tier == 0 ? 0.8f : h.tier == 1 ? 1.15f : 1.6f;
            var ramp = h.kind == HitKind.BLOCK ? cool : warm;
            if (l >= 0 && l <= 2)
            {
                int rays = h.kind == HitKind.BLOCK ? 5 : h.tier == 0 ? 6 : h.tier == 1 ? 8 : 11;
                float grow = 1f + l * 0.28f, fade = 1f - l * 0.32f;
                var layers = new (float sc, int c, float a)[] { (1.35f, ramp[0], 0.32f), (1.0f, ramp[1], 0.6f), (0.62f, ramp[3], 0.9f) };
                for (int m = 0; m < rays; m++)
                {
                    float ang = (m + r.NextFloat() * 0.6f) / rays * 6.2832f;
                    int w = (n * 3 + m * 7) % fx.wedges.Count;
                    float len = (0.5f + r.NextFloat() * 0.5f) * big;
                    for (int li = 0; li < layers.Length; li++)
                    {
                        var (sc, c, a) = layers[li];
                        float s = len * sc * grow;
                        float d = 0.35f * big + s * 1.2f;
                        cv.Place(fx.wedges[w], idb + 3000 + (m * 3 + li) * 100, Alpha(c, a * fade),
                            tip[0] + (float)Math.Cos(ang) * d, tip[1] + (float)Math.Sin(ang) * d, s, ang - wedgeAxis[w], dx, dy);
                    }
                }
                if (fx.blobs.Count > 0 && l <= 1)
                {
                    var bl = fx.blobs[(n * 11) % fx.blobs.Count];
                    cv.Place(bl, idb + 2100, Alpha(ramp[1], 0.4f * fade), tip[0], tip[1], 0.9f * big * grow, r.NextFloat() * 6.28f, dx, dy);
                    cv.Place(bl, idb + 2500, Alpha(ramp[3], 0.85f * fade), tip[0], tip[1], 0.45f * big * grow, r.NextFloat() * 6.28f, dx, dy);
                }
            }
            if (h.tier < 2 || h.kind != HitKind.HIT) return;
            if (l >= 0 && l <= 6)
            {
                float rr = 0.9f + l * 0.8f;
                int segs = 14;
                for (int m = 0; m < segs; m++)
                {
                    float ang = (float)m / segs * 6.2832f;
                    int w = (m * 5 + n) % fx.wedges.Count;
                    var lay = new (float sc, int c)[] { (0.7f, ramp[1]), (0.4f, ramp[3]) };
                    for (int li = 0; li < lay.Length; li++)
                    {
                        var (sc, c) = lay[li];
                        cv.Place(fx.wedges[w], idb + 6400 + (m * 2 + li) * 100, Alpha(c, (0.55f + li * 0.3f) * (1 - l / 7f)),
                            tip[0] + (float)Math.Cos(ang) * rr, tip[1] + (float)Math.Sin(ang) * rr, sc * (1f + l * 0.12f), ang + 1.5708f - wedgeAxis[w], dx, dy);
                    }
                }
            }
        }

        void DustFx(Canvas cv, int n, Dust d, int k, float dx, float dy)
        {
            int l = Local(k, d.t);
            if (l < 0 || l > 9 || fx.blobs.Count == 0) return;
            var r = new JRandom(seed * 131 + n);
            float x = st[d.who][K.Clamp(d.t, 0, baseN - 1)].x;
            int puffs = d.big ? 7 : 4;
            int light = dark ? C(0xFF6E6258) : C(0xFFE8D9C8);
            for (int m = 0; m < puffs; m++)
            {
                float ox = (m - puffs / 2f) * (d.big ? 0.75f : 0.5f) + (r.NextFloat() - 0.5f) * 0.4f;
                float s = (0.35f + l * (d.big ? 0.09f : 0.06f)) * (0.7f + r.NextFloat() * 0.6f);
                float cy = s * 0.6f + l * 0.07f;
                var b = fx.blobs[(n * 7 + m) % fx.blobs.Count];
                float rot = r.NextFloat() * 6.28f;
                float fade = 1 - l / 10f;
                cv.Place(b, 5_000_000 + n * 3000 + m * 300, Alpha(light, 0.45f * fade), x + ox + dx, cy + dy, s * 1.3f, rot, 0f, 0f);
                cv.Place(b, 5_000_000 + n * 3000 + m * 300 + 150, Alpha(dustCol, 0.55f * fade), x + ox + dx, cy + dy, s * 0.75f, rot + 0.4f, 0f, 0f);
            }
        }

        public static float Axis(EffectLib.Shape sh)
        {
            if (sh.contours.Count == 0) return 0f;
            var c = sh.contours[0];
            float mx = 0f, my = 0f; int n = c.Length / 2;
            for (int i = 0; i < n; i++) { mx += c[2 * i]; my += -c[2 * i + 1]; }
            mx /= n; my /= n;
            float xx = 0f, yy = 0f, xy = 0f;
            for (int i = 0; i < n; i++) { float x = c[2 * i] - mx, y = -c[2 * i + 1] - my; xx += x * x; yy += y * y; xy += x * y; }
            return 0.5f * (float)Math.Atan2(2 * xy, xx - yy);
        }
    }

    /// <summary>사용자 입력. FPS 순서는 (트위닝, 재생).</summary>
    public sealed class Request { public string prompt; public int seconds, tween, play; public long seed; public bool dark; }

    public sealed class Generated
    {
        public readonly Request req; public readonly Scene scene; public readonly List<string> notes;
        public Generated(Request r, Scene s, List<string> n) { req = r; scene = s; notes = n; }
        public int FrameCount => scene.Count;
        /// <summary>5초마다 끊은 파일 구간 [시작, 끝).</summary>
        public List<(int start, int end)> Parts
        {
            get { int per = 5 * req.play; var l = new List<(int, int)>(); for (int s = 0; s < FrameCount; s += per) l.Add((s, Math.Min(s + per, FrameCount))); return l; }
        }
    }

    public static class Generator
    {
        public static readonly string[] SUPPORTED = { "1v1" };

        public static List<string> Tags(string prompt) => prompt.Split(new[] { ',', '\n' }).Select(t => t.Trim().ToLowerInvariant()).Where(t => t.Length > 0).ToList();

        public static Generated Generate(MotionLib lib, EffectLib fx, Request req)
        {
            var notes = new List<string>();
            var t = Tags(req.prompt);
            var unknown = t.Where(x => !SUPPORTED.Contains(x)).ToList();
            if (!t.Contains("1v1")) notes.Add("1v1 태그가 없어 기본(1v1)으로 만들었습니다");
            if (unknown.Count > 0) notes.Add("아직 지원하지 않는 태그는 무시했습니다: " + string.Join(", ", unknown));
            int baseN = req.seconds * 24;
            var ch = new Choreo(lib, req.seed, baseN).Run();
            return new Generated(req, new Scene(ch, fx, req.play, req.dark, req.seed), notes);
        }

        /// <summary>프레임 구간을 SFA(ZIP 안 XML 하나)로 쓴다.</summary>
        public static void WriteSfa(Generated g, int start, int end, string name, Stream outp)
        {
            using var zip = new ZipArchive(outp, ZipArchiveMode.Create, leaveOpen: true);
            var e = zip.CreateEntry(name + ".xml", CompressionLevel.Optimal);
            using var w = new StreamWriter(e.Open(), new UTF8Encoding(false));
            WriteXml(g, start, end, name, w);
        }

        /// <summary>Kotlin "%.3f"와 같은 결과: 가장 짧은 십진 표현을 소수 셋째 자리에서 반올림(중간값은 0에서 먼 쪽, Java HALF_UP).</summary>
        static string F(float v)
        {
            if (v == (int)v) return $"{(int)v}.0";
            var d = decimal.Parse(((double)v).ToString("R", CultureInfo.InvariantCulture), NumberStyles.Float, CultureInfo.InvariantCulture);
            return Math.Round(d, 3, MidpointRounding.AwayFromZero).ToString("F3", CultureInfo.InvariantCulture);
        }
        static string Esc(string s) => s.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;");

        public static void WriteXml(Generated g, int start, int end, string name, TextWriter w)
        {
            int seqBg = g.req.dark ? unchecked((int)0xFF141414) : -1;
            w.Write("<?xml version='1.0' encoding='utf-8'?>\n");
            w.Write($"<Sequence Name=\"{Esc(name)}\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" FrameCount=\"{end - start}\" BackgroundColor=\"{seqBg}\">\n");
            int ptId = 1;
            for (int k = start, pos = 0; k < end; k++, pos++)
            {
                var fr = g.scene.Frame(k);
                w.Write($"  <Frame BackgroundColor=\"{(uint)fr.bg}\" ID=\"{pos + 1}\" Position=\"{pos}\">\n");
                w.Write("    <LayerDef ID=\"0\" Name=\"Layer 1\" Visible=\"true\" Locked=\"false\" />\n");
                var ids = new Dictionary<int, int>();
                foreach (var o in fr.objs) { ids[o.id] = ptId; ptId += o.pts.Length / 2; }
                var conn = new Dictionary<int, List<int>>();
                foreach (var o in fr.objs) foreach (var l in o.links)
                    {
                        int a = ids[o.id] + l[0];
                        if (!ids.TryGetValue(l[1], out int pb)) continue;
                        int b = pb + l[2];
                        if (!conn.TryGetValue(a, out var la)) conn[a] = la = new(); la.Add(b);
                        if (!conn.TryGetValue(b, out var lb)) conn[b] = lb = new(); lb.Add(a);
                    }
                for (int order = 0; order < fr.objs.Count; order++)
                {
                    var o = fr.objs[order];
                    w.Write($"    <AO ID=\"{o.id}\" TypeId=\"{o.type}\" Color=\"{o.color}\" LayerId=\"0\" DrawOrder=\"{order + 1}\" ThicknessScale=\"{F(o.thick)}\" ObjectScale=\"1.0\" GlowRadius=\"{F(o.glowR)}\" GlowThickness=\"{F(o.glowT)}\" GlowColor=\"{(uint)o.glowColor}\" GlowAlpha=\"{F(o.glowA)}\">\n");
                    int p0 = ids[o.id];
                    for (int i = 0; i < o.pts.Length / 2; i++)
                    {
                        int id = p0 + i;
                        float x = o.pts[2 * i] / 1920f * 100f, y = o.pts[2 * i + 1] / 1080f * 100f;
                        conn.TryGetValue(id, out var c);
                        w.Write($"      <AP ID=\"{id}\" Flags=\"{(c != null ? "4" : "5")}\" Index=\"{i}\" X=\"{F(x)}\" Y=\"{F(y)}");
                        if (c == null) w.Write("\" />\n");
                        else
                        {
                            w.Write("\">\n");
                            foreach (var b in c) w.Write($"        <AC ConnPtId=\"{b}\" />\n");
                            w.Write("      </AP>\n");
                        }
                    }
                    w.Write("    </AO>\n");
                }
                foreach (var fl in fr.fills)
                {
                    w.Write($"    <FR Color=\"{fl.color}\">\n");
                    for (int ci = 0; ci < fl.contours.Count; ci++)
                        foreach (int oid in fl.contours[ci])
                        {
                            if (!ids.TryGetValue(oid, out int p0)) continue;
                            w.Write($"      <FS Kind=\"0\" ObjId=\"{oid}\" StartPtId=\"{p0}\" EndPtId=\"{p0 + 2}\" StartT=\"0.0\" EndT=\"1.0\" Contour=\"{ci}\" />\n");
                        }
                    w.Write("    </FR>\n");
                }
                w.Write("  </Frame>\n");
            }
            w.Write("</Sequence>\n");
        }
    }
}
