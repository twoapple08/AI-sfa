using System.Drawing.Drawing2D;
using System.Text.Json;

namespace SfaViewer
{
    public sealed class RecentItem { public string Path { get; set; } public string Name { get; set; } public int Frames { get; set; } public string Key { get; set; } }

    /// <summary>최근 연 파일 목록(%LOCALAPPDATA%\SfaViewer\recent.json, 최대 24개).</summary>
    static class Recent
    {
        static string FilePath => System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SfaViewer", "recent.json");
        public static List<RecentItem> Load() { try { return JsonSerializer.Deserialize<List<RecentItem>>(File.ReadAllText(FilePath)) ?? new(); } catch { return new(); } }
        static void Save(List<RecentItem> l) { try { Directory.CreateDirectory(System.IO.Path.GetDirectoryName(FilePath)); File.WriteAllText(FilePath, JsonSerializer.Serialize(l.Take(24).ToList())); } catch { } }
        public static void Remember(RecentItem r) { var l = Load(); l.RemoveAll(x => string.Equals(x.Path, r.Path, StringComparison.OrdinalIgnoreCase)); l.Insert(0, r); Save(l); }
        public static void Forget(string path) { var l = Load(); l.RemoveAll(x => string.Equals(x.Path, path, StringComparison.OrdinalIgnoreCase)); Save(l); }
    }

    /// <summary>첫 화면 카드: 둥근 미리보기 + 이름 + 프레임 수 + ⋯(목록에서 지우기).</summary>
    sealed class RecentCard : Control
    {
        readonly RecentItem item; readonly Image thumb; bool hover;
        public event Action Open, Remove;
        public RecentCard(RecentItem r, string thumbPath)
        {
            item = r; Cursor = Cursors.Hand;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            try { if (File.Exists(thumbPath)) using (var ms = new MemoryStream(File.ReadAllBytes(thumbPath))) thumb = new Bitmap(ms); } catch { }
            var menu = new ContextMenuStrip(); menu.Items.Add("목록에서 지우기", null, (_, _) => Remove?.Invoke());
            ContextMenuStrip = menu;
        }
        static int P(float v) => Theme.P(v);
        Rectangle MoreRect => new(Width - P(40), Height - P(58), P(40), P(40));
        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseClick(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            if (MoreRect.Contains(e.Location)) ContextMenuStrip.Show(this, e.Location); else Open?.Invoke();
        }
        protected override void Dispose(bool d) { if (d) thumb?.Dispose(); base.Dispose(d); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Theme.Bg);
            int th = Height - P(66);
            using (var p = Theme.Round(new RectangleF(0, 0, Width - 1, th), 22 * Theme.S))
            {
                using (var b = new SolidBrush(Theme.Surface)) g.FillPath(b, p);
                if (thumb != null)
                {
                    var st = g.Save(); g.SetClip(p); g.InterpolationMode = InterpolationMode.HighQualityBilinear;
                    float s = Math.Max((float)Width / thumb.Width, (float)th / thumb.Height), w = thumb.Width * s, h = thumb.Height * s;
                    g.DrawImage(thumb, (Width - w) / 2, (th - h) / 2, w, h); g.Restore(st);
                }
                if (hover) using (var b = new SolidBrush(Color.FromArgb(25, 0, 0, 0))) g.FillPath(b, p);
            }
            using var fn = Theme.Bold(12); using var fs = Theme.Regular(10);
            TextRenderer.DrawText(g, item.Name, fn, new Rectangle(2, th + P(12), Width - P(46), P(26)), Theme.Text, TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
            TextRenderer.DrawText(g, $"{item.Frames} frames", fs, new Rectangle(2, th + P(40), Width - P(46), P(22)), Theme.Sub, TextFormatFlags.NoPadding);
            var m = MoreRect; using var br = new SolidBrush(Theme.Text); float S = Theme.S;
            for (int i = -1; i <= 1; i++) g.FillEllipse(br, m.X + m.Width / 2 + i * 7 * S - 2.5f * S, m.Y + m.Height / 2 - 2.5f * S, 5 * S, 5 * S);
        }
    }
}
