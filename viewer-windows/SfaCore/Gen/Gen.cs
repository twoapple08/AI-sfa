using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Globalization;
using System.IO.Compression;
using System.Text;

// 안드로이드 크리에이터(creator-android/.../gen/*.kt)의 1v1 생성기를 C#으로 옮긴 것.
// 난수는 java.util.Random과 같은 식(JRandom)이라 같은 시드면 안드로이드판과 같은 안무가 나온다.
// 차이 1곳: 임팩트 장면 위 반대색 테두리. Kotlin판은 Int.inv()가 내장 비트 반전으로 불려 알파까지 뒤집혀 투명해졌다(의도와 다름).
// 여기서는 의도대로 알파를 유지하고 RGB만 뒤집는다(InvRgb).
namespace SfaCore.Gen
{
    /// <summary>java.util.Random과 같은 48비트 선형 합동 생성기.</summary>
    public sealed class JRandom
    {
        long seed;
        const long Mul = 0x5DEECE66DL, Mask = (1L << 48) - 1;
        public JRandom(long s) { seed = (s ^ Mul) & Mask; }
        int Next(int bits) { seed = unchecked(seed * Mul + 0xBL) & Mask; return (int)((ulong)seed >> (48 - bits)); }
        public int NextInt() => Next(32);
        public int NextInt(int bound)
        {
            if ((bound & -bound) == bound) return (int)((bound * (long)Next(31)) >> 31);
            int bits, val;
            do { bits = Next(31); val = bits % bound; } while (bits - val + (bound - 1) < 0);
            return val;
        }
        public float NextFloat() => Next(24) / (float)(1 << 24);
        public bool NextBoolean() => Next(1) != 0;
    }

    static class K
    {
        public static float Clamp(float v, float a, float b) { if (a > b) throw new ArgumentException("범위"); return v < a ? a : v > b ? b : v; }
        public static int Clamp(int v, int a, int b) { if (a > b) throw new ArgumentException("범위"); return v < a ? a : v > b ? b : v; }
        public static float[] Cat(params float[][] a) { var r = new List<float>(); foreach (var x in a) r.AddRange(x); return r.ToArray(); }
        /// <summary>Kotlin roundToInt(= Java Math.round): floor(v + 0.5).</summary>
        public static int RoundToInt(double v) => (int)Math.Floor(v + 0.5);
    }

    public static class Rig
    {
        public const float HEAD = 1f, NECK = 0.25f, SPINE = 1.6f, UA = 1.25f, FA = 1.15f, TH = 1.55f, SH = 1.5f, FOOT = 0.45f;
        public const int HIP = 0, CH = 1, NK = 2, HD = 3, E0 = 4, H0 = 5, E1 = 6, H1 = 7, K0 = 8, A0 = 9, T0 = 10, K1 = 11, A1 = 12, T1 = 13, N = 14;
    }

    /// <summary>각도 10개(도): 몸통, 목, 팔0(위·아래), 팔1(위·아래), 다리0(허벅지·정강이), 다리1. 0번 팔다리는 뒤쪽.</summary>
    public sealed class Pose
    {
        public readonly float[] a;
        public Pose(float[] a) { this.a = a; }
        public Pose Copy() => new((float[])a.Clone());
        public Pose Set(int i, float v) { a[i] = v; return this; }
        public const int SP = 0, NKA = 1, UA0 = 2, FA0 = 3, UA1 = 4, FA1 = 5, TH0 = 6, SH0 = 7, TH1 = 8, SH1 = 9;

        public float[] Joints()
        {
            var o = new float[Rig.N * 2];
            void Put(int i, float x, float y) { o[2 * i] = x; o[2 * i + 1] = y; }
            void From(int i, int src, float ang, float len)
            {
                double r = ang * Math.PI / 180.0;
                Put(i, o[2 * src] + len * (float)Math.Cos(r), o[2 * src + 1] + len * (float)Math.Sin(r));
            }
            Put(Rig.HIP, 0f, 0f);
            From(Rig.CH, Rig.HIP, a[SP], Rig.SPINE);
            From(Rig.NK, Rig.CH, a[NKA], Rig.NECK);
            From(Rig.HD, Rig.NK, a[NKA], Rig.HEAD / 2);
            From(Rig.E0, Rig.CH, a[UA0], Rig.UA); From(Rig.H0, Rig.E0, a[FA0], Rig.FA);
            From(Rig.E1, Rig.CH, a[UA1], Rig.UA); From(Rig.H1, Rig.E1, a[FA1], Rig.FA);
            From(Rig.K0, Rig.HIP, a[TH0], Rig.TH); From(Rig.A0, Rig.K0, a[SH0], Rig.SH);
            From(Rig.T0, Rig.A0, FootAngle(a[SH0]), Rig.FOOT);
            From(Rig.K1, Rig.HIP, a[TH1], Rig.TH); From(Rig.A1, Rig.K1, a[SH1], Rig.SH);
            From(Rig.T1, Rig.A1, FootAngle(a[SH1]), Rig.FOOT);
            return o;
        }

        public float Drop(float[] j = null)
        {
            j ??= Joints();
            float m = j[2 * Rig.HD + 1] + Rig.HEAD / 2;
            for (int i = 0; i < Rig.N; i++) if (i != Rig.HD) m = Math.Max(m, j[2 * i + 1]);
            return m;
        }

        public static float FootAngle(float shin) => (shin - 90f) * 0.35f;
        public static Pose Of(params float[] v) => new(v);
        public static float LerpAng(float a, float b, float t) { float d = ((b - a) % 360f + 540f) % 360f - 180f; return a + d * t; }
        public static Pose Lerp(Pose p, Pose q, float t) { var r = new float[10]; for (int i = 0; i < 10; i++) r[i] = LerpAng(p.a[i], q.a[i], t); return new Pose(r); }
    }

    public enum Ease { LINEAR, IN, OUT, IO, STEP }

    public sealed class State { public readonly Pose pose; public readonly float x, air; public State(Pose p, float x, float air) { pose = p; this.x = x; this.air = air; } }

    public sealed class Track
    {
        public sealed class Key
        {
            public readonly int t; public readonly Pose pose; public readonly float x, air; public readonly Ease ease; public readonly bool twos;
            public Key(int t, Pose p, float x, float air, Ease e, bool twos) { this.t = t; pose = p; this.x = x; this.air = air; ease = e; this.twos = twos; }
        }
        public readonly List<Key> keys = new();
        public Track(Pose start, float x) { keys.Add(new Key(0, start, x, 0f, Ease.LINEAR, false)); }
        public Key Last => keys[^1];

        public void KeyAt(int t, Pose pose, float? x = null, float air = 0f, Ease ease = Ease.IO, bool twos = false)
        {
            float xx = x ?? Last.x;
            while (keys.Count > 1 && keys[^1].t >= t) keys.RemoveAt(keys.Count - 1);
            int tt = Math.Max(t, keys[^1].t + 1);
            keys.Add(new Key(tt, pose, xx, air, ease, twos));
        }

        public void Hold(int t) { if (t > Last.t) KeyAt(t, Last.pose, Last.x, Last.air, Ease.LINEAR); }

        public State At(int f)
        {
            int k = 1;
            while (k < keys.Count && keys[k].t < f) k++;
            if (k >= keys.Count) { var l = keys[^1]; return new State(l.pose, l.x, l.air); }
            var a = keys[k - 1]; var b = keys[k];
            int ff = f;
            if (b.twos) ff = a.t + ((f - a.t) / 2) * 2;
            float u = K.Clamp((float)(ff - a.t) / (b.t - a.t), 0f, 1f);
            float e = b.ease switch
            {
                Ease.LINEAR => u,
                Ease.IN => u * u,
                Ease.OUT => 1 - (1 - u) * (1 - u),
                Ease.IO => u * u * (3 - 2 * u),
                _ => u >= 1f ? 1f : 0f,
            };
            return new State(Pose.Lerp(a.pose, b.pose, e), a.x + (b.x - a.x) * e, a.air + (b.air - a.air) * e);
        }
    }

    public enum HitKind { HIT, BLOCK, WHIFF }
    public sealed class Hit { public readonly int t, att, tipJoint, tier; public readonly HitKind kind; public Hit(int t, int att, int tip, HitKind k, int tier) { this.t = t; this.att = att; tipJoint = tip; kind = k; this.tier = tier; } }
    public sealed class Dust { public readonly int t, who; public readonly bool big; public Dust(int t, int who, bool big) { this.t = t; this.who = who; this.big = big; } }

    /// <summary>학습 자료(motion_lib.txt, tools/motion_lib.py): nian41 펀치 핵심 자세 + 나카무라 타이밍.</summary>
    public sealed class MotionLib
    {
        public sealed class Punch { public int arm; public float reach, height; public int wind; public Pose strike, follow; }
        public sealed class Timing
        {
            public int[] preHold, strike, postHold, gap; public float stillRatio;
            public static Timing Default => new() { preHold = new[] { 1, 1 }, strike = new[] { 5, 10 }, postHold = new[] { 0, 1 }, gap = new[] { 7, 11 }, stillRatio = 0.37f };
        }
        public readonly List<Punch> punches; public readonly Timing timing;
        public MotionLib(List<Punch> p, Timing t) { punches = p; timing = t; }

        static float F(string s) => float.Parse(s, CultureInfo.InvariantCulture);
        public static MotionLib Read(TextReader r)
        {
            var lines = new List<string>(); string ln;
            while ((ln = r.ReadLine()) != null) if (!string.IsNullOrWhiteSpace(ln)) lines.Add(ln);
            var timing = Timing.Default; var punches = new List<Punch>();
            Pose P(string s) => new(s.Trim().Split(' ').Select(F).ToArray());
            int[] Pair(string s) => s.Split(',').Select(int.Parse).ToArray();
            int i = 0;
            while (i < lines.Count)
            {
                var f = lines[i].Trim().Split(' ');
                if (f[0] == "T") { timing = new Timing { preHold = Pair(f[1]), strike = Pair(f[2]), postHold = Pair(f[3]), gap = Pair(f[4]), stillRatio = F(f[5]) }; i++; }
                else if (f[0] == "P") { punches.Add(new Punch { arm = int.Parse(f[1]), reach = F(f[2]), height = F(f[3]), wind = int.Parse(f[4]), strike = P(lines[i + 2]), follow = P(lines[i + 3]) }); i += 4; }
                else i++;
            }
            return new MotionLib(punches, timing);
        }
    }

    /// <summary>이펙트 사전(effects.txt): 포물선 조각 윤곽 형태(쐐기·덩어리), 나카무라 임팩트 장면, 팔레트. 다른 작가 그림 유래라 저장소에 넣지 않는다.</summary>
    public sealed class EffectLib
    {
        public sealed class Shape { public readonly List<float[]> contours; public Shape(List<float[]> c) { contours = c; } }
        public sealed class SceneFrame { public bool whiteInk; public float w; public List<Shape> groups; }
        public sealed class SceneFx { public string name; public List<SceneFrame> frames; }
        public readonly List<Shape> wedges, blobs; public readonly List<SceneFx> scenes; public readonly List<int> palette;
        public EffectLib(List<Shape> w, List<Shape> b, List<SceneFx> s, List<int> p) { wedges = w; blobs = b; scenes = s; palette = p; }
        public static EffectLib Empty => new(new(), new(), new(), new());

        public static EffectLib Read(TextReader r)
        {
            var lines = new List<string>(); string ln;
            while ((ln = r.ReadLine()) != null) lines.Add(ln);
            var wedges = new List<Shape>(); var blobs = new List<Shape>(); var scenes = new List<SceneFx>(); var pal = new List<int>();
            float[] Contour(string s) => s.Trim().Split(' ').Skip(2).Select(x => float.Parse(x, CultureInfo.InvariantCulture)).ToArray();
            int i = 0;
            while (i < lines.Count)
            {
                var f = lines[i].Trim().Split(' ');
                switch (f[0])
                {
                    case "K":
                        {
                            int n = int.Parse(f[3]);
                            var sh = new Shape(Enumerable.Range(1, n).Select(k => Contour(lines[i + k])).ToList());
                            if (f[1] == "wedge") wedges.Add(sh); else if (f[1] == "blob") blobs.Add(sh);
                            i += 1 + n; break;
                        }
                    case "Q":
                        {
                            int nf = int.Parse(f[2]); i++;
                            var frames = new List<SceneFrame>();
                            for (int q = 0; q < nf; q++)
                            {
                                var h = lines[i].Trim().Split(' '); i++;
                                var groups = new List<Shape>();
                                for (int g = 0, ng = int.Parse(h[3]); g < ng; g++)
                                {
                                    int nc = int.Parse(lines[i].Trim().Split(' ')[1]); i++;
                                    groups.Add(new Shape(Enumerable.Range(0, nc).Select(k => Contour(lines[i + k])).ToList())); i += nc;
                                }
                                frames.Add(new SceneFrame { whiteInk = h[1] == "1", w = float.Parse(h[2], CultureInfo.InvariantCulture), groups = groups });
                            }
                            scenes.Add(new SceneFx { name = f[1], frames = frames });
                            break;
                        }
                    case "P": pal.Add(unchecked((int)0xFF000000) | (int.Parse(f[1]) << 16) | (int.Parse(f[2]) << 8) | int.Parse(f[3])); i++; break;
                    default: i++; break;
                }
            }
            return new EffectLib(wedges, blobs, scenes, pal);
        }
    }

    /// <summary>1v1 맨손 육탄전 안무(배경·도구 없음). 안드로이드 Choreo.kt와 같은 규칙·같은 난수 순서.</summary>
    public sealed class Choreo
    {
        readonly MotionLib lib; readonly JRandom rnd; public readonly int frames;
        public readonly float[] face = { 1f, -1f };
        public readonly Track[] tr;
        public readonly List<Hit> hits = new(); public readonly List<Dust> dusts = new();
        readonly MotionLib.Timing tm;

        public Choreo(MotionLib lib, long seed, int frames)
        {
            this.lib = lib; rnd = new JRandom(seed); this.frames = frames; tm = lib.timing;
            var t0 = new Track(Jit(STANCE), -2.9f); var t1 = new Track(Jit(STANCE), 2.9f); tr = new[] { t0, t1 };
        }

        int R(int a, int b) => a + rnd.NextInt(b - a + 1);
        float Rf(float a, float b) => a + rnd.NextFloat() * (b - a);
        Pose Jit(Pose p, float deg = 4f) { var r = new float[10]; for (int i = 0; i < 10; i++) r[i] = p.a[i] + Rf(-deg, deg); return new Pose(r); }

        public Choreo Run()
        {
            int now = R(3, 8);
            int att = rnd.NextInt(2);
            while (now < frames)
            {
                Neutral(now, R(4, 10));
                now = Math.Max(tr[0].Last.t, tr[1].Last.t);
                if (rnd.NextFloat() < 0.6f) att = 1 - att;
                int combo = R(1, 3);
                for (int c = 0; c < combo; c++)
                {
                    bool lastOne = c == combo - 1;
                    int tier;
                    if (lastOne && combo >= 2 && rnd.NextFloat() < 0.5f) tier = 2;
                    else if (lastOne && rnd.NextFloat() < 0.12f) tier = 2;
                    else if (c >= 1 || rnd.NextFloat() < 0.3f) tier = 1;
                    else tier = 0;
                    HitKind kind;
                    if (tier == 2) kind = HitKind.HIT;
                    else
                    {
                        float v = rnd.NextFloat();
                        kind = v >= 0f && v <= 0.55f ? HitKind.HIT : v >= 0.55f && v <= 0.85f ? HitKind.BLOCK : HitKind.WHIFF;
                    }
                    now = Strike(att, now, tier, kind, combo: !lastOne);
                    if (now >= frames) break;
                }
                now = Math.Max(tr[0].Last.t, tr[1].Last.t) + 1;
            }
            foreach (var t in tr) t.Hold(frames);
            return this;
        }

        void Neutral(int t0, int n)
        {
            float mid = (tr[0].Last.x + tr[1].Last.x) / 2;
            float gap = tr[1].Last.x - tr[0].Last.x;
            float wantGap = Rf(4.8f, 6.2f);
            float shift = K.Clamp(-mid, -1.2f, 1.2f);
            float half = (wantGap - gap) / 2;
            for (int i = 0; i <= 1; i++)
            {
                var t = tr[i];
                int start = Math.Max(t0, t.Last.t);
                float x1 = t.Last.x + shift - face[i] * K.Clamp(half, -1.2f, 1.2f);
                bool step = Math.Abs(x1 - t.Last.x) > 0.25f;
                var bob = Jit(STANCE, 3f); bob.a[Pose.TH0] += 6f; bob.a[Pose.TH1] -= 6f; bob.a[Pose.SP] += 2f;
                // Kotlin과 같은 난수 순서: bob을 먼저 만들고, 걸음이면 그다음 STEP_MID를 흔든다
                t.KeyAt(start + n / 2, step ? Jit(STEP_MID, 3f) : bob, (t.Last.x + x1) / 2, step ? 0.12f : 0f, Ease.IO, twos: true);
                t.KeyAt(start + n, Jit(STANCE, 3f), x1, 0f, Ease.IO, twos: true);
            }
        }

        int Strike(int a, int t0, int tier, HitKind kind, bool combo)
        {
            int d = 1 - a; float f = face[a];
            var ta = tr[a]; var td = tr[d];
            bool kick = rnd.NextFloat() < (tier >= 1 ? 0.35f : 0.2f);
            Pose windup, hit, follow; int tipJ;
            if (kick)
            {
                bool high = rnd.NextBoolean();
                windup = Jit(KICK_CH); hit = Jit(high ? KICK_HI : KICK_EX); follow = Pose.Lerp(hit, KICK_CH, 0.5f); tipJ = Rig.A1;
            }
            else
            {
                var p = lib.punches[rnd.NextInt(lib.punches.Count)];
                hit = Jit(p.strike, 3f);
                int k = p.arm;
                int ua = k == 0 ? Pose.UA0 : Pose.UA1;
                float w1 = 118f + Rf(-8f, 8f); float w2 = -35f + Rf(-10f, 10f);
                windup = hit.Copy().Set(ua, w1).Set(ua + 1, w2).Set(Pose.SP, hit.a[Pose.SP] - 8f).Set(Pose.NKA, hit.a[Pose.NKA] - 4f);
                follow = Pose.Lerp(p.follow, STANCE, 0.3f);
                tipJ = k == 0 ? Rig.H0 : Rig.H1;
            }
            var j = hit.Joints();
            float tipX = j[2 * tipJ];
            float xd = td.Last.x;
            float xHit0 = xd - f * (0.35f + tipX);
            float xHit = f > 0 ? Math.Min(xHit0, xd - 1.3f) : Math.Max(xHit0, xd + 1.3f);
            float lunge = kick ? 0.35f : 0.7f;
            float xReady = xHit - f * lunge;
            int t = Math.Max(t0, ta.Last.t);
            if (!combo || Math.Abs(ta.Last.x - xReady) > 0.5f)
            {
                float dist = Math.Abs(ta.Last.x - xReady);
                if (dist > 0.3f)
                {
                    int n = K.Clamp(K.RoundToInt(dist / 0.38f), 3, 10);
                    ta.KeyAt(t + n / 2, Jit(STEP_MID), (ta.Last.x + xReady) / 2, 0.15f, Ease.LINEAR);
                    ta.KeyAt(t + n, Jit(STANCE), xReady, 0f, Ease.OUT);
                    t += n;
                }
            }
            int nw = R(3, 5);
            int pre = Math.Max(R(tm.preHold[0], Math.Max(tm.preHold[0], tm.preHold[1])), 1);
            int ns = tier == 2 ? 1 : R(1, 2);
            ta.KeyAt(t + nw, windup, xReady - f * 0.1f, 0f, Ease.IO);
            ta.Hold(t + nw + pre);
            int ti = t + nw + pre + ns;
            ta.KeyAt(ti, hit, xHit, kick ? 0.05f : 0f, Ease.OUT);
            int post = new[] { 1, 2, 3 }[tier] + R(tm.postHold[0], tm.postHold[1]);
            ta.Hold(ti + post);
            hits.Add(new Hit(ti, a, tipJ, kind, tier));
            React(d, ti, tier, kind, high: (hit.Drop() - j[2 * tipJ + 1]) > 4.6f, push: f);
            if (combo)
            {
                int gap = R(tm.gap[0], tm.gap[1]);
                ta.KeyAt(ti + post + 2, follow, xHit - f * 0.2f, 0f, Ease.OUT);
                return Math.Max(ti + post + 2, ti + gap - 6);
            }
            ta.KeyAt(ti + post + 3, follow, xHit - f * 0.25f, 0f, Ease.OUT);
            ta.KeyAt(ti + post + 9, Jit(STANCE), xHit - f * 0.6f, 0f, Ease.IO, twos: true);
            return ti + post + 9;
        }

        void React(int d, int ti, int tier, HitKind kind, bool high, float push)
        {
            var t = tr[d];
            float x0 = t.Last.x;
            float ClampX(float x) => K.Clamp(x, -10.5f, 10.5f);
            switch (kind)
            {
                case HitKind.BLOCK:
                    t.KeyAt(ti - 3, Jit(GUARD), x0, 0f, Ease.OUT);
                    { var g = Jit(GUARD, 2f); g.a[Pose.SP] -= 5f; t.KeyAt(ti, g, ClampX(x0 + push * 0.35f), 0f, Ease.STEP); }
                    t.KeyAt(ti + 3, Jit(GUARD), ClampX(x0 + push * 0.5f), 0f, Ease.OUT);
                    t.KeyAt(ti + 9, Jit(STANCE), ClampX(x0 + push * 0.5f), 0f, Ease.IO, twos: true);
                    break;
                case HitKind.WHIFF:
                    {
                        var dodge = high ? Jit(DUCK) : Jit(SWAY);
                        t.KeyAt(ti - 2, dodge, ClampX(x0 + push * 0.5f), 0f, Ease.OUT);
                        t.Hold(ti + 3);
                        t.KeyAt(ti + 9, Jit(STANCE), ClampX(x0 + push * 0.6f), 0f, Ease.IO, twos: true);
                        break;
                    }
                default:
                    if (tier < 2)
                    {
                        float kb = tier == 0 ? 0.5f : 1.2f;
                        t.KeyAt(ti, Jit(high ? HIT_HEAD : HIT_BODY, 6f), ClampX(x0 + push * kb * 0.5f), 0f, Ease.STEP);
                        t.KeyAt(ti + 2 + tier, Jit(high ? HIT_HEAD : HIT_BODY, 3f), ClampX(x0 + push * kb), 0f, Ease.OUT);
                        t.KeyAt(ti + 10 + tier * 2, Jit(STANCE), ClampX(x0 + push * kb * 1.1f), 0f, Ease.IO, twos: true);
                        if (tier == 1) dusts.Add(new Dust(ti + 1, d, false));
                    }
                    else
                    {
                        float far = K.Clamp(x0 + push * Rf(4.5f, 6f), -8f, 8f);
                        t.KeyAt(ti, Jit(HIT_HEAD, 4f), ClampX(x0 + push * 0.4f), 0f, Ease.STEP);
                        t.KeyAt(ti + 3, Jit(FLY), ClampX(x0 + push * 2.2f), 1.4f, Ease.OUT);
                        { var fl = Jit(FLY, 2f); fl.a[Pose.SP] += 8f; t.KeyAt(ti + 8, fl, (far + ClampX(x0 + push * 2.2f)) / 2 + push * 1f, 0.6f, Ease.LINEAR); }
                        t.KeyAt(ti + 11, Jit(LIE, 2f), far, 0f, Ease.IN);
                        t.KeyAt(ti + 14, Jit(LIE, 1f), ClampX(far + push * 0.5f), 0f, Ease.OUT);
                        t.Hold(ti + 22);
                        t.KeyAt(ti + 30, Jit(CROUCH), ClampX(far + push * 0.5f), 0f, Ease.IO, twos: true);
                        t.KeyAt(ti + 38, Jit(STANCE), ClampX(far + push * 0.5f), 0f, Ease.IO, twos: true);
                        dusts.Add(new Dust(ti + 11, d, true));
                    }
                    break;
            }
        }

        public State[][] Bake() { var r = new State[2][]; for (int i = 0; i < 2; i++) { r[i] = new State[frames]; for (int f = 0; f < frames; f++) r[i][f] = tr[i].At(f); } return r; }

        public static readonly Pose STANCE = Pose.Of(-84f, -80f, 100f, -75f, 65f, -70f, 112f, 100f, 68f, 92f);
        public static readonly Pose STEP_MID = Pose.Of(-86f, -82f, 95f, -70f, 70f, -65f, 96f, 98f, 84f, 100f);
        public static readonly Pose GUARD = Pose.Of(-96f, -72f, 40f, -95f, 30f, -85f, 120f, 104f, 62f, 88f);
        public static readonly Pose HIT_HEAD = Pose.Of(-114f, -138f, 160f, 175f, 128f, 165f, 108f, 100f, 72f, 82f);
        public static readonly Pose HIT_BODY = Pose.Of(-58f, -38f, 70f, 120f, 50f, 110f, 104f, 95f, 76f, 102f);
        public static readonly Pose SWAY = Pose.Of(-126f, -124f, 110f, -60f, 80f, -60f, 124f, 95f, 70f, 80f);
        public static readonly Pose DUCK = Pose.Of(-48f, -35f, 60f, -40f, 40f, -50f, 25f, 118f, 62f, 128f);
        public static readonly Pose FLY = Pose.Of(-162f, -172f, -150f, -160f, -138f, -128f, -14f, 10f, 12f, 22f);
        public static readonly Pose LIE = Pose.Of(178f, 178f, 168f, 176f, 150f, 162f, -2f, 2f, 8f, -4f);
        public static readonly Pose CROUCH = Pose.Of(-58f, -62f, 82f, 62f, 58f, 82f, 92f, 172f, 8f, 95f);
        public static readonly Pose KICK_CH = Pose.Of(-100f, -95f, 120f, -60f, 40f, -80f, 96f, 92f, -25f, 95f);
        public static readonly Pose KICK_EX = Pose.Of(-112f, -100f, 125f, -55f, 45f, -75f, 98f, 92f, -8f, -5f);
        public static readonly Pose KICK_HI = Pose.Of(-130f, -112f, 140f, 160f, 70f, -60f, 100f, 95f, -45f, -50f);
    }
}
