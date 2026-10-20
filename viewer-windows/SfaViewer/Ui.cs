using System.Drawing.Drawing2D;

namespace SfaViewer
{
    /// <summary>안드로이드 v0.4와 같은 색·모양(밝은 회색 바탕, 주황 강조, 둥근 카드).</summary>
    static class Theme
    {
        public static readonly Color Bg = Color.FromArgb(0xF9, 0xF9, 0xF9);
        public static readonly Color Surface = Color.FromArgb(0xEF, 0xEF, 0xEF);
        public static readonly Color Orange = Color.FromArgb(0xFF, 0x8C, 0x3B);
        public static readonly Color Text = Color.FromArgb(0x22, 0x22, 0x22);
        public static readonly Color Sub = Color.FromArgb(0x8A, 0x8A, 0x8A);
        public static readonly Color Icon = Color.FromArgb(0x55, 0x55, 0x55);
        public static readonly Color Track = Color.FromArgb(0xDA, 0xDD, 0xE1);

        public static Font Bold(float pt) => new("Segoe UI", pt, FontStyle.Bold);
        public static Font Regular(float pt) => new("Segoe UI", pt);
        /// <summary>가장 굵은 제목 글꼴(사용자 요청: SFA VIEWER 굵게). 없으면 Segoe UI 굵게.</summary>
        public static Font Black(float pt) { var f = new Font("Segoe UI Black", pt, FontStyle.Bold); return f.Name == "Segoe UI Black" ? f : Bold(pt); }

        public static GraphicsPath Round(RectangleF r, float rad)
        {
            var p = new GraphicsPath(); float d = Math.Min(rad * 2, Math.Min(r.Width, r.Height));
            if (d <= 0) { p.AddRectangle(r); return p; }
            p.AddArc(r.X, r.Y, d, d, 180, 90); p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90); p.AddArc(r.X, r.Bottom - d, d, d, 90, 90); p.CloseFigure();
            return p;
        }
    }

    /// <summary>바탕을 직접 그리는 컨트롤의 공통(깜빡임 없음, 부모 색 바탕).</summary>
    abstract class Painted : Control
    {
        protected bool hover;
        protected Painted() { SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true); }
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
        protected Graphics Prep(PaintEventArgs e) { var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Parent?.BackColor ?? Theme.Bg); return g; }
    }

    enum IconKind { Play, Pause, Prev, Next, Back, Upload, Plus, More, Folder }

    /// <summary>단색 아이콘 버튼. Fill이 있으면 원형 바탕(+ 버튼).</summary>
    sealed class IconButton : Painted
    {
        IconKind kind; public Color Color = Theme.Icon; public Color? Fill;
        public IconButton(IconKind k) { kind = k; Cursor = Cursors.Hand; Size = new Size(44, 44); }
        public IconKind Kind { get => kind; set { if (kind != value) { kind = value; Invalidate(); } } }
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = Prep(e);
            float s = Math.Min(Width, Height);
            if (Fill is Color f) { using var b = new SolidBrush(hover ? ControlPaint.Dark(f, 0.05f) : f); g.FillEllipse(b, (Width - s) / 2 + 1, (Height - s) / 2 + 1, s - 2, s - 2); }
            else if (hover && Enabled) { using var b = new SolidBrush(Color.FromArgb(18, 0, 0, 0)); g.FillEllipse(b, (Width - s) / 2, (Height - s) / 2, s, s); }
            s *= 0.46f; float cx = Width / 2f, cy = Height / 2f, l = cx - s / 2, t = cy - s / 2;
            var col = Enabled ? Color : Color.FromArgb(90, Color);
            using var br = new SolidBrush(col); using var pen = new Pen(col, s * 0.13f) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
            PointF P(float x, float y) => new(l + s * x, t + s * y);
            switch (kind)
            {
                case IconKind.Play: g.FillPolygon(br, new[] { P(0.12f, 0), P(1, 0.5f), P(0.12f, 1) }); break;
                case IconKind.Pause: g.FillRectangle(br, l + s * 0.08f, t, s * 0.3f, s); g.FillRectangle(br, l + s * 0.62f, t, s * 0.3f, s); break;
                case IconKind.Prev: g.FillPolygon(br, new[] { P(0.75f, 0.2f), P(0.3f, 0.5f), P(0.75f, 0.8f) }); break;
                case IconKind.Next: g.FillPolygon(br, new[] { P(0.25f, 0.2f), P(0.7f, 0.5f), P(0.25f, 0.8f) }); break;
                case IconKind.Back: g.DrawLines(pen, new[] { P(0.7f, 0.05f), P(0.25f, 0.5f), P(0.7f, 0.95f) }); break;
                case IconKind.Upload:
                    g.FillPolygon(br, new[] { P(0.5f, 0), P(0.92f, 0.45f), P(0.64f, 0.45f), P(0.64f, 0.78f), P(0.36f, 0.78f), P(0.36f, 0.45f), P(0.08f, 0.45f) });
                    g.FillRectangle(br, l + s * 0.08f, t + s * 0.9f, s * 0.84f, s * 0.1f); break;
                case IconKind.Plus: g.DrawLine(pen, P(0.5f, 0.1f), P(0.5f, 0.9f)); g.DrawLine(pen, P(0.1f, 0.5f), P(0.9f, 0.5f)); break;
                case IconKind.More: for (int i = -1; i <= 1; i++) g.FillEllipse(br, cx + i * s * 0.36f - s * 0.11f, cy - s * 0.11f, s * 0.22f, s * 0.22f); break;
                case IconKind.Folder:
                    g.FillPolygon(br, new[] { P(0, 0.15f), P(0.38f, 0.15f), P(0.48f, 0.27f), P(1, 0.27f), P(1, 0.88f), P(0, 0.88f) }); break;
            }
        }
    }

    /// <summary>둥근 알약 모양 글자 버튼(주황 내보내기 등).</summary>
    sealed class PillButton : Painted
    {
        public Color Fill = Theme.Orange, Fore = Color.White;
        public PillButton(string text) { Text = text; Font = Theme.Bold(11); Cursor = Cursors.Hand; Height = 46; }
        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = Prep(e);
            var c = Enabled ? (hover ? ControlPaint.Dark(Fill, 0.05f) : Fill) : Color.FromArgb(110, Fill);
            using (var p = Theme.Round(new RectangleF(0.5f, 0.5f, Width - 1, Height - 1), Height / 2f)) using (var b = new SolidBrush(c)) g.FillPath(b, p);
            TextRenderer.DrawText(g, Text, Font, ClientRectangle, Fore, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
        }
    }

    /// <summary>둥근 카드 바탕 패널.</summary>
    sealed class CardPanel : Panel
    {
        public Color Fill = Theme.Surface; public float Radius = 22;
        public CardPanel() { DoubleBuffered = true; BackColor = Theme.Surface; }
        protected override void OnPaintBackground(PaintEventArgs e)
        {
            var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Parent?.BackColor ?? Theme.Bg);
            using var p = Theme.Round(new RectangleF(0, 0, Width - 1, Height - 1), Radius); using var b = new SolidBrush(Fill); g.FillPath(b, p);
        }
    }

    /// <summary>주황 이동 막대. 사용자가 끌면 Scrubbed가 불린다.</summary>
    sealed class SeekBar : Painted
    {
        int max, val; bool drag;
        public event Action<int> Scrubbed;
        public SeekBar() { Height = 28; Cursor = Cursors.Hand; }
        public int Maximum { get => max; set { max = Math.Max(0, value); val = Math.Min(val, max); Invalidate(); } }
        public int Value { get => val; set { int v = Math.Clamp(value, 0, max); if (v != val) { val = v; Invalidate(); } } }
        const float Pad = 10;
        float X(int v) => Pad + (Width - 2 * Pad) * (max == 0 ? 0 : (float)v / max);
        void Hit(int x) { if (!Enabled) return; int v = (int)Math.Round((x - Pad) / Math.Max(1, Width - 2 * Pad) * max); v = Math.Clamp(v, 0, max); if (v != val) { val = v; Invalidate(); Scrubbed?.Invoke(v); } }
        protected override void OnMouseDown(MouseEventArgs e) { drag = true; Hit(e.X); base.OnMouseDown(e); }
        protected override void OnMouseMove(MouseEventArgs e) { if (drag) Hit(e.X); base.OnMouseMove(e); }
        protected override void OnMouseUp(MouseEventArgs e) { drag = false; base.OnMouseUp(e); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = Prep(e); float cy = Height / 2f;
            using (var p = new Pen(Theme.Track, 4) { StartCap = LineCap.Round, EndCap = LineCap.Round }) g.DrawLine(p, Pad, cy, Width - Pad, cy);
            var oc = Enabled ? Theme.Orange : Color.FromArgb(110, Theme.Orange);
            using (var p = new Pen(oc, 4) { StartCap = LineCap.Round, EndCap = LineCap.Round }) if (val > 0) g.DrawLine(p, Pad, cy, X(val), cy);
            float r = drag || hover ? 9 : 8; using var b = new SolidBrush(oc); g.FillEllipse(b, X(val) - r, cy - r, 2 * r, 2 * r);
        }
    }

    /// <summary>바탕색을 투명하게 쓰는 라벨(부모 색).</summary>
    sealed class TextLabel : Label
    {
        public TextLabel(Font f, Color c, ContentAlignment a = ContentAlignment.MiddleLeft) { Font = f; ForeColor = c; TextAlign = a; AutoSize = false; BackColor = Color.Transparent; AutoEllipsis = true; }
    }
}
