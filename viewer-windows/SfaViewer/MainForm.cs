using System.Collections.Concurrent;
using System.Diagnostics;
using System.Drawing.Imaging;
using SfaCore;
using SkiaSharp;

namespace SfaViewer
{
    /// <summary>
    /// SFA 보기·재생·MP4 내보내기(Windows). 안드로이드 뷰어와 같은 방식:
    /// 처음 열 때 변환해 캐시(.sfab)로 저장 → 여러 스레드가 프레임을 미리 그려 JPEG로 메모리에 보관 → 재생은 시간표 fps로 보여 주기만.
    /// 시간표 (트위닝, 재생) fps는 SFA에 저장되지 않아 파일마다 기억한다(기본 24, 24). 트위닝 &gt; 재생이면 프레임 사이를 섞는다.
    /// 내보내기는 exe 옆의 ffmpeg.exe에 원시 프레임을 넘겨 H.264 MP4로 만든다.
    /// </summary>
    public sealed partial class MainForm : Form
    {
        const int PreviewW = 1280;
        int tween = 24, play = 24; Timeline tl = new(0, 24, 24);
        // 첫 화면
        readonly Panel home = new() { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Theme.Bg };
        readonly TextLabel homeTitle = new(Theme.Black(30), Theme.Orange, ContentAlignment.MiddleCenter) { Text = "SFA VIEWER" };
        readonly TextLabel homeSub = new(Theme.Regular(10), Theme.Sub, ContentAlignment.MiddleCenter) { Text = "Stick Fighter 애니메이션 만들기 · 미리보기 · 내보내기  (파일을 끌어다 놓아도 됩니다)" };
        readonly CardPanel pillBg = new() { Radius = 26 };
        readonly PillButton pill = new("최근 파일") { Fill = Color.White, Fore = Theme.Text, Cursor = Cursors.Default };
        readonly TextLabel empty = new(Theme.Regular(11), Theme.Sub, ContentAlignment.MiddleCenter) { Text = "아래 + 버튼으로 SFA 파일을 여세요" };
        readonly IconButton fab = new(IconKind.Plus) { Color = Color.White, Fill = Theme.Orange, Size = new Size(Theme.P(68), Theme.P(68)) };
        readonly PillButton makeBtn = new("1v1 만들기") { Fill = Theme.Orange, Fore = Color.White };
        readonly Control homeSpacer = new() { Size = new Size(1, 1) }; // 마지막 카드 아래 여유(+ 버튼에 가리지 않게 스크롤 범위를 늘림)
        readonly List<RecentCard> cards = new();
        // 플레이어
        readonly Panel player = new() { Dock = DockStyle.Fill, BackColor = Theme.Bg, Visible = false };
        readonly IconButton backBtn = new(IconKind.Back) { Color = Theme.Text };
        readonly IconButton openIcon = new(IconKind.Folder);
        readonly IconButton exportIcon = new(IconKind.Upload) { Enabled = false };
        readonly TextLabel title = new(Theme.Bold(15), Theme.Orange);
        readonly TextLabel status = new(Theme.Regular(9), Theme.Sub, ContentAlignment.MiddleCenter);
        readonly TextLabel frameLabel = new(Theme.Bold(12), Theme.Text);
        readonly TextLabel timeLabel = new(Theme.Bold(11), Theme.Orange, ContentAlignment.MiddleRight);
        readonly SeekBar seek = new() { Enabled = false };
        readonly IconButton playBtn = new(IconKind.Play) { Color = Theme.Orange, Enabled = false };
        readonly IconButton prevBtn = new(IconKind.Prev) { Enabled = false };
        readonly IconButton nextBtn = new(IconKind.Next) { Enabled = false };
        readonly CardPanel infoCard = new();
        readonly TextLabel infoHead = new(Theme.Bold(11), Theme.Text) { Text = "파일 정보", BackColor = Theme.Surface };
        readonly TextLabel info = new(Theme.Regular(10), Theme.Sub, ContentAlignment.TopLeft) { BackColor = Theme.Surface };
        readonly PillButton exportBtn = new("MP4 내보내기") { Enabled = false };
        readonly PillButton fpsBtn = new("24, 24") { Fill = Color.White, Fore = Theme.Text, Enabled = false };
        readonly TextLabel fpsHead = new(Theme.Regular(10), Theme.Text) { Text = "FPS (트위닝, 재생)", BackColor = Theme.Surface };
        readonly FrameView view = new();
        readonly System.Windows.Forms.Timer timer = new() { Interval = 10 };

        SfaDoc doc; string fileName = "sfa", filePath, fileKey;
        byte[][] frames; int prepared; CancellationTokenSource prepCts;
        int current; bool playing; CancellationTokenSource exportCts;
        readonly Stopwatch clock = new(); int playStartFrame;

        public MainForm()
        {
            Text = "SFA 뷰어"; Width = Theme.P(1280); Height = Theme.P(860); MinimumSize = new Size(Theme.P(340), Theme.P(380)); BackColor = Theme.Bg; KeyPreview = true;
            try { Icon = new Icon(typeof(MainForm).Assembly.GetManifestResourceStream("SfaViewer.app.ico")); } catch { }
            home.Controls.AddRange(new Control[] { homeTitle, homeSub, makeBtn, pillBg, empty, homeSpacer });
            pillBg.Controls.Add(pill);
            Controls.Add(fab); Controls.Add(player); Controls.Add(home);
            player.Controls.AddRange(new Control[] { backBtn, title, openIcon, exportIcon, fpsBtn, view, frameLabel, timeLabel, seek, prevBtn, playBtn, nextBtn, status, infoCard });
            infoCard.Controls.AddRange(new Control[] { infoHead, info, fpsHead, exportBtn });
            home.Resize += (_, _) => LayoutHome();
            player.Resize += (_, _) => LayoutPlayer();

            fab.Click += (_, _) => PickFile();
            makeBtn.Click += (_, _) => AskCreate();
            openIcon.Click += (_, _) => PickFile();
            backBtn.Click += (_, _) => GoHome();
            playBtn.Click += (_, _) => TogglePlay();
            prevBtn.Click += (_, _) => Step(-1);
            nextBtn.Click += (_, _) => Step(1);
            view.Click += (_, _) => TogglePlay();
            exportBtn.Click += (_, _) => ExportOrCancel();
            exportIcon.Click += (_, _) => ExportOrCancel();
            fpsBtn.Click += (_, _) => AskFps();
            seek.Scrubbed += v => { StopPlay(); Show(v); };
            timer.Tick += (_, _) => Tick();
            AllowDrop = true;
            DragEnter += (_, e) => { if (e.Data.GetDataPresent(DataFormats.FileDrop)) e.Effect = DragDropEffects.Copy; };
            DragDrop += (_, e) => { var f = (string[])e.Data.GetData(DataFormats.FileDrop); if (f?.Length > 0) _ = LoadFile(f[0]); };
            KeyDown += (_, e) =>
            {
                if (e.KeyCode == Keys.Escape && player.Visible) { GoHome(); e.Handled = true; return; }
                if (doc == null || !player.Visible) return;
                if (e.KeyCode == Keys.Space) { TogglePlay(); e.Handled = true; }
                else if (e.KeyCode == Keys.Right) { Step(1); e.Handled = true; }
                else if (e.KeyCode == Keys.Left) { Step(-1); e.Handled = true; }
            };
            status.Text = "스페이스=재생/정지, ←/→=한 프레임, Esc=첫 화면";
            BuildCards();
            // 화면 시험용: 환경 변수 SFAVIEWER_SIZE=가로x세로 로 처음 창 크기를 정한다
            var sz = Environment.GetEnvironmentVariable("SFAVIEWER_SIZE")?.Split('x');
            if (sz?.Length == 2 && int.TryParse(sz[0], out int sw0) && int.TryParse(sz[1], out int sh0)) { StartPosition = FormStartPosition.Manual; Location = Point.Empty; Size = new Size(sw0, sh0); }
            var cmd = Environment.GetCommandLineArgs();
            if (cmd.Length > 1 && File.Exists(cmd[1])) Shown += (_, _) => _ = LoadFile(cmd[1]);
        }

        // ───────── 첫 화면 ─────────

        void PickFile() { using var dlg = new OpenFileDialog { Filter = "SFA (*.sfa)|*.sfa|모든 파일|*.*" }; if (dlg.ShowDialog(this) == DialogResult.OK) _ = LoadFile(dlg.FileName); }

        void GoHome()
        {
            if (exportCts != null) { MessageBox.Show(this, "내보내기 중입니다. 먼저 취소하세요.", "SFA 뷰어"); return; }
            StopPlay(); prepCts?.Cancel(); doc = null; frames = null; view.SetFrame(null);
            player.Visible = false; home.Visible = true; fab.Visible = true; BuildCards();
        }

        void ShowPlayer() { home.Visible = false; fab.Visible = false; player.Visible = true; LayoutPlayer(); }

        void BuildCards()
        {
            foreach (var c in cards) { home.Controls.Remove(c); c.Dispose(); }
            cards.Clear();
            foreach (var r in Recent.Load())
            {
                var card = new RecentCard(r, Path.Combine(CacheDir, "thumbs", r.Key + ".jpg"));
                card.Open += () => { if (File.Exists(r.Path)) _ = LoadFile(r.Path); else { MessageBox.Show(this, "파일을 찾을 수 없습니다:\n" + r.Path, "SFA 뷰어"); Recent.Forget(r.Path); BuildCards(); } };
                card.Remove += () => { Recent.Forget(r.Path); BuildCards(); };
                cards.Add(card); home.Controls.Add(card);
            }
            empty.Visible = cards.Count == 0;
            LayoutHome();
        }

        static int P(float v) => Theme.P(v);
        bool homeCompact;

        /// <summary>
        /// 첫 화면 배치. 창 크기를 마음대로 바꿔도(작은 창·화면 반쪽 배치) 맞춘다(안드로이드 멀티윈도우 대응과 같은 방식).
        /// 카드 열 수는 창 폭으로, 창이 작으면 글자·여백을 줄인다. + 버튼은 넓은 창에서 오른쪽 아래, 좁은 창에서 가운데 아래.
        /// </summary>
        void LayoutHome()
        {
            int W = home.ClientSize.Width, H = ClientSize.Height;
            if (W <= 0) return;
            bool compact = H < P(600) || W < P(480);
            if (compact != homeCompact || homeTitle.Tag == null)
            {
                homeCompact = compact; homeTitle.Tag = 1;
                homeTitle.Font = Theme.Black(compact ? 22 : 30);
                fab.Size = new Size(P(compact ? 56 : 68), P(compact ? 56 : 68));
            }
            int y = P(compact ? 14 : 44) + home.AutoScrollPosition.Y;
            homeTitle.SetBounds(0, y, W, P(compact ? 44 : 60)); y += P(compact ? 46 : 64);
            // Visible 값은 창이 보이기 전에는 늘 false라서 따로 둔 값으로 판단한다
            bool showSub = W >= P(420);
            homeSub.Visible = showSub;
            if (showSub) { homeSub.SetBounds(0, y, W, P(24)); y += P(compact ? 30 : 46); }
            makeBtn.SetBounds((W - P(200)) / 2, y, P(200), P(46)); y += P(compact ? 58 : 66);
            pillBg.SetBounds((W - P(170)) / 2, y, P(170), P(54)); pill.SetBounds(P(5), P(5), P(160), P(44)); y += P(compact ? 66 : 78);
            empty.SetBounds(0, y + P(30), W, P(30));
            int side = P(compact ? 14 : 24), gap = P(compact ? 14 : 22);
            int cols = Math.Clamp((W - 2 * side + gap) / (P(240) + gap), 1, 6);
            int cw = (W - 2 * side - gap * (cols - 1)) / cols, ch = (int)(cw * 0.62f) + P(66);
            for (int i = 0; i < cards.Count; i++) cards[i].SetBounds(side + (i % cols) * (cw + gap), y + (i / cols) * (ch + gap), cw, ch);
            int rows = (cards.Count + cols - 1) / cols;
            homeSpacer.Location = new Point(0, y + rows * (ch + gap) + fab.Height + P(24));
            PlaceFab();
        }

        void PlaceFab()
        {
            if (fab == null) return;
            int W = ClientSize.Width, H = ClientSize.Height, m = P(homeCompact ? 14 : 24);
            bool wide = W > H * 1.2f;
            fab.Location = wide ? new Point(W - fab.Width - m - SystemInformation.VerticalScrollBarWidth, H - fab.Height - m)
                                : new Point((W - fab.Width) / 2, H - fab.Height - m - P(4));
            fab.BringToFront();
        }

        protected override void OnResize(EventArgs e) { base.OnResize(e); if (fab != null && home != null && home.Visible) LayoutHome(); }

        // ───────── 플레이어 배치: 창이 세로로 길면 세로 보기(영상 위, 조작 아래), 아니면 가로 보기 ─────────

        /// <summary>
        /// 플레이어 배치. 창이 세로로 길고 충분히 높으면 세로 보기(영상 위, 조작·정보 카드 아래),
        /// 그 밖(가로 창, 작은 창·팝업처럼 낮은 창)은 가로 보기(영상 + 아래 조작 막대)로 모든 버튼이 보이게 한다.
        /// 좁으면 덜 중요한 글자(상태·시간)를 숨긴다.
        /// </summary>
        void LayoutPlayer()
        {
            int W = player.ClientSize.Width, H = player.ClientSize.Height;
            if (W <= 0 || H <= 0) return;
            float ratio = doc?.Ratio ?? 0.5625f;
            bool portrait = H > W && H >= P(640);
            int hb = P(48), top = P(60);
            backBtn.SetBounds(P(8), P(6), hb, hb);
            exportIcon.SetBounds(W - P(56), P(6), hb, hb);
            openIcon.SetBounds(W - P(104), P(6), hb, hb);
            if (!portrait)
            {
                if (fpsBtn.Parent != player) { infoCard.Controls.Remove(fpsBtn); player.Controls.Add(fpsBtn); }
                fpsBtn.SetBounds(openIcon.Left - P(104), P(10), P(96), P(40));
                title.TextAlign = ContentAlignment.MiddleLeft;
                int titleW = Math.Max(P(40), Math.Min(P(520), Math.Min(W / 2, fpsBtn.Left - P(68))));
                title.SetBounds(P(60), P(6), titleW, hb);
                status.Visible = fpsBtn.Left - title.Right > P(120);
                status.TextAlign = ContentAlignment.MiddleRight; status.SetBounds(title.Right + P(8), P(6), Math.Max(10, fpsBtn.Left - title.Right - P(16)), hb);
                int barH = P(64);
                view.SetBounds(0, top, W, Math.Max(P(40), H - top - barH));
                int by = H - barH + P(8);
                playBtn.SetBounds(P(16), by, hb, hb);
                bool narrow = W < P(520);
                timeLabel.Visible = !narrow;
                timeLabel.TextAlign = ContentAlignment.MiddleLeft; timeLabel.SetBounds(P(70), by, P(120), hb);
                nextBtn.SetBounds(W - P(56), by + P(2), P(44), P(44)); prevBtn.SetBounds(W - P(102), by + P(2), P(44), P(44));
                frameLabel.TextAlign = ContentAlignment.MiddleRight; frameLabel.SetBounds(W - P(210), by, P(104), hb);
                int sx = narrow ? P(70) : P(196);
                seek.SetBounds(sx, by + P(10), Math.Max(20, frameLabel.Left - sx - P(10)), P(28));
                infoCard.Visible = false;
            }
            else
            {
                status.Visible = true; timeLabel.Visible = true;
                title.TextAlign = ContentAlignment.MiddleCenter; title.SetBounds(P(60), P(6), Math.Max(10, openIcon.Left - P(64)), hb);
                int vh = (int)Math.Min(W * ratio, H * (H < P(900) ? 0.45f : 0.55f));
                view.SetBounds(0, top, W, vh);
                int y = top + vh + P(18), px = P(26);
                frameLabel.TextAlign = ContentAlignment.MiddleLeft; frameLabel.SetBounds(px, y, W / 2 - px, P(28));
                timeLabel.TextAlign = ContentAlignment.MiddleRight; timeLabel.SetBounds(W / 2, y, W / 2 - px, P(28)); y += P(34);
                seek.SetBounds(px - P(8), y, W - 2 * px + P(16), P(28)); y += P(40);
                int ps = P(H < P(900) ? 60 : 76); playBtn.SetBounds((W - ps) / 2, y, ps, ps);
                int sb = P(56); prevBtn.SetBounds(playBtn.Left - P(36) - sb, y + (ps - sb) / 2, sb, sb); nextBtn.SetBounds(playBtn.Right + P(36), y + (ps - sb) / 2, sb, sb); y += ps + P(6);
                status.TextAlign = ContentAlignment.MiddleCenter; status.SetBounds(px, y, W - 2 * px, P(22)); y += P(30);
                int ch = Math.Min(P(260), Math.Max(P(200), H - y - P(16)));
                infoCard.Visible = true; infoCard.SetBounds(px, y, W - 2 * px, ch);
                int iw = infoCard.Width - P(40);
                if (fpsBtn.Parent != infoCard) { player.Controls.Remove(fpsBtn); infoCard.Controls.Add(fpsBtn); }
                infoHead.SetBounds(P(20), P(16), iw, P(24)); info.SetBounds(P(20), P(46), iw, Math.Max(P(20), ch - P(46) - P(124)));
                fpsHead.SetBounds(P(20), ch - P(112), iw - P(110), P(40)); fpsBtn.SetBounds(P(20) + iw - P(100), ch - P(112), P(100), P(40));
                exportBtn.SetBounds(P(20), ch - P(66), iw, P(48));
            }
            infoCard.Invalidate();
        }

        void UpdateLabels(int f)
        {
            int n = doc != null ? tl.Count : 0, fps = tl.Fps;
            frameLabel.Text = n > 0 ? $"{f + 1} / {n}" : "– / –";
            string T(int fr) => $"{fr / fps / 60:00}:{fr / fps % 60:00}";
            timeLabel.Text = n > 0 ? $"{T(f)} / {T(n)}" : "";
        }

        void SetEnabled(bool on) { foreach (Control c in new Control[] { playBtn, prevBtn, nextBtn, seek, exportBtn, exportIcon, fpsBtn }) c.Enabled = on; }
        void Step(int d) { if (doc == null || tl.Count == 0) return; StopPlay(); Show(Math.Clamp(current + d, 0, tl.Count - 1)); }

        /// <summary>파일 캐시 키. string.GetHashCode()는 실행마다 달라져(.NET 무작위 해시) 다시 켜면 캐시·FPS 기억을 못 찾았다 → 고정 FNV-1a.</summary>
        static string KeyOf(FileInfo fi)
        {
            uint h = 2166136261;
            foreach (char c in $"{fi.Name}_{fi.Length}_{fi.LastWriteTimeUtc.Ticks}") { h ^= c; h *= 16777619; }
            return h.ToString("x8");
        }

        static string CacheDir => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SfaViewer");

        async Task LoadFile(string path)
        {
            StopPlay(); prepCts?.Cancel(); exportCts?.Cancel();
            if (exportCts != null) return;
            SetEnabled(false); openIcon.Enabled = false;
            fileName = Path.GetFileNameWithoutExtension(path); filePath = path;
            title.Text = fileName; info.Text = ""; status.Text = "파일 여는 중…"; doc = null; view.SetFrame(null); UpdateLabels(0);
            ShowPlayer();
            var sw = Stopwatch.StartNew();
            try
            {
                var fi = new FileInfo(path);
                string key = fileKey = KeyOf(fi);
                Directory.CreateDirectory(CacheDir);
                string cache = Path.Combine(CacheDir, key + ".sfab");
                string how = "캐시";
                doc = await Task.Run(() =>
                {
                    if (File.Exists(cache)) { try { using var s = File.OpenRead(cache); var c = SfaDoc.Read(s); if (c != null) return c; } catch { } }
                    how = "변환";
                    SfaDoc d;
                    using (var s = File.OpenRead(path)) d = SfaDoc.Parse(s, n => BeginInvoke(() => status.Text = $"읽는 중… XML {n / 1_000_000} MB"));
                    BeginInvoke(() => status.Text = "캐시 저장 중…");
                    try { var tmp = cache + ".tmp"; using (var o = File.Create(tmp)) d.Write(o); File.Move(tmp, cache, true); } catch { }
                    return d;
                });
                loadMsg = $"불러오기: {how} {sw.Elapsed.TotalSeconds:F1}초";
                (tween, play) = LoadFps(key);
                SetEnabled(true);
                ApplyTimeline(0);
                Recent.Remember(new RecentItem { Path = path, Name = fileName, Frames = doc.FrameCount, Key = key });
                SaveThumb(key, frames[0], true);
            }
            catch (Exception e) { status.Text = "열기 실패: " + e.Message; title.Text = "열기 실패"; }
            finally { openIcon.Enabled = true; }
        }

        string loadMsg = "";

        // ───────── 시간표 (트위닝, 재생) ─────────

        static string FpsFile(string key) => Path.Combine(CacheDir, "fps_" + key + ".txt");
        static (int, int) LoadFps(string key)
        {
            try { var a = File.ReadAllText(FpsFile(key)).Split(','); return (Math.Clamp(int.Parse(a[0]), 1, 240), Math.Clamp(int.Parse(a[1]), 1, 240)); } catch { return (24, 24); }
        }

        /// <summary>(T, P)로 시간표를 만들고 미리 그리기·이동 막대·재생을 다시 맞춘다. pos는 0..1 위치(바꾸기 전 위치 유지).</summary>
        void ApplyTimeline(double pos)
        {
            var d = doc; if (d == null) return;
            StopPlay(); prepCts?.Cancel();
            tl = new Timeline(d.FrameCount, tween, play);
            fpsBtn.Text = $"{tween}, {play}"; fpsBtn.Invalidate();
            string how = tl.Interp ? $"보간 {tl.Fps}fps · 원본 {d.FrameCount}프레임 → {tl.Count}프레임" : $"보간 없음 · {tl.Fps}fps";
            info.Text = $"{d.FrameCount}프레임 · {d.FrameCount / (double)play:F1}초 ({how})\n1920×{(int)Math.Round(1920 * d.Ratio)} · 오브젝트 {d.ObjCount:N0}개\n{loadMsg}";
            seek.Maximum = Math.Max(tl.Count - 1, 0);
            int j = Math.Clamp((int)(pos * tl.Count), 0, Math.Max(tl.Count - 1, 0));
            LayoutPlayer();
            StartPrepare(j);
            Show(j);
        }

        /// <summary>(T, P) 조정 창. 원래 앱과 같은 규칙: T &gt; P이면 프레임 사이를 섞어 T fps로, 아니면 원본을 P fps로 보여 준다.</summary>
        void AskFps()
        {
            if (doc == null || exportCts != null) return;
            using var f = new Form { Text = "FPS (트위닝, 재생)", FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false, StartPosition = FormStartPosition.CenterParent, ClientSize = new Size(380, 210), BackColor = Theme.Bg, Font = Theme.Regular(10) };
            var note = new Label { Text = "Stick Fighter에서 쓴 값을 넣으세요. SFA 파일에는 저장되지 않습니다.\n트위닝이 재생보다 크면 프레임 사이를 섞어 보여 줍니다.", ForeColor = Theme.Sub, AutoSize = false };
            note.SetBounds(16, 12, 350, 46);
            var lt = new Label { Text = "트위닝", Font = Theme.Bold(10) }; lt.SetBounds(40, 70, 120, 24);
            var lp = new Label { Text = "재생", Font = Theme.Bold(10) }; lp.SetBounds(210, 70, 120, 24);
            var nt = new NumericUpDown { Minimum = 1, Maximum = 240, Value = tween }; nt.SetBounds(40, 96, 120, 28);
            var np = new NumericUpDown { Minimum = 1, Maximum = 240, Value = play }; np.SetBounds(210, 96, 120, 28);
            var ok = new Button { Text = "적용", DialogResult = DialogResult.OK }; ok.SetBounds(196, 160, 80, 32);
            var cancel = new Button { Text = "취소", DialogResult = DialogResult.Cancel }; cancel.SetBounds(284, 160, 80, 32);
            var reset = new Button { Text = "24, 24" }; reset.SetBounds(16, 160, 80, 32);
            reset.Click += (_, _) => { nt.Value = 24; np.Value = 24; };
            f.Controls.AddRange(new Control[] { note, lt, lp, nt, np, ok, cancel, reset });
            f.AcceptButton = ok; f.CancelButton = cancel;
            if (f.ShowDialog(this) != DialogResult.OK) return;
            int t = (int)nt.Value, p = (int)np.Value;
            if (t == tween && p == play) return;
            double pos = tl.Count > 0 ? (double)current / tl.Count : 0;
            tween = t; play = p;
            try { File.WriteAllText(FpsFile(fileKey), $"{t},{p}"); } catch { }
            ApplyTimeline(pos);
        }

        /// <summary>여러 스레드로 모든 출력 프레임을 미리 그려 JPEG로 보관한다(start부터).</summary>
        void StartPrepare(int start)
        {
            prepCts = new CancellationTokenSource(); var ct = prepCts.Token; var d = doc; var tt = tl;
            var fr = frames = new byte[tt.Count][]; prepared = 0;
            int threads = Math.Max(1, Environment.ProcessorCount - 1);
            var queue = new ConcurrentQueue<int>(Enumerable.Range(0, tt.Count).Select(i => (start + i) % tt.Count));
            for (int t = 0; t < threads; t++)
                Task.Run(() =>
                {
                    var r = new FrameRenderer(d);
                    int h = Math.Max(2, (int)(PreviewW * d.Ratio));
                    using var bmp = new SKBitmap(PreviewW, h);
                    using var c = new SKCanvas(bmp);
                    while (!ct.IsCancellationRequested && queue.TryDequeue(out int f))
                    {
                        if (fr[f] != null) continue;
                        try
                        {
                            r.Render(tt, f, c, PreviewW); c.Flush();
                            using var img = SKImage.FromBitmap(bmp); using var data = img.Encode(SKEncodedImageFormat.Jpeg, 92);
                            if (ReferenceEquals(frames, fr)) { fr[f] = data.ToArray(); Interlocked.Increment(ref prepared); }
                        }
                        catch { }
                    }
                }, ct);
        }

        string PrepText() => doc == null ? "" : prepared >= tl.Count ? "미리 그리기 완료" : $"미리 그리기 {prepared}/{tl.Count}";

        /// <summary>첫 화면 카드용 미리보기(0번 프레임, 폭 480).</summary>
        static void SaveThumb(string key, byte[] jpg, bool overwrite = false)
        {
            try
            {
                string f = Path.Combine(CacheDir, "thumbs", key + ".jpg");
                if (jpg == null || (File.Exists(f) && !overwrite)) return;
                Directory.CreateDirectory(Path.GetDirectoryName(f));
                using var ms = new MemoryStream(jpg); using var src = new Bitmap(ms);
                using var t = new Bitmap(480, Math.Max(2, 480 * src.Height / src.Width));
                using (var g = Graphics.FromImage(t)) { g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic; g.DrawImage(src, 0, 0, t.Width, t.Height); }
                t.Save(f, ImageFormat.Jpeg);
            }
            catch { }
        }

        Bitmap Decode(byte[] jpg) { using var ms = new MemoryStream(jpg); return new Bitmap(ms); }

        void Show(int f)
        {
            if (doc == null) return;
            if (tl.Count == 0) return;
            current = Math.Clamp(f, 0, tl.Count - 1);
            seek.Value = current; UpdateLabels(current);
            var j = frames?[current];
            if (j != null) view.SetFrame(Decode(j));
            else
            {
                // 아직 안 그린 프레임: 바로 그려서 보여 준다(재생 중이 아닐 때)
                var r = new FrameRenderer(doc);
                int h = Math.Max(2, (int)(PreviewW * doc.Ratio));
                using var bmp = new SKBitmap(PreviewW, h); using var c = new SKCanvas(bmp);
                r.Render(tl, current, c, PreviewW); c.Flush();
                using var img = SKImage.FromBitmap(bmp); using var data = img.Encode(SKEncodedImageFormat.Jpeg, 92);
                frames[current] = data.ToArray(); view.SetFrame(Decode(frames[current]));
            }
            if (!playing && exportCts == null) status.Text = PrepText();
        }

        void TogglePlay() { if (playing) StopPlay(); else StartPlay(); }
        void StartPlay() { if (doc == null) return; playing = true; playBtn.Kind = IconKind.Pause; clock.Restart(); playStartFrame = current; timer.Start(); }
        void StopPlay() { playing = false; playBtn.Kind = IconKind.Play; timer.Stop(); }

        void Tick()
        {
            if (!playing || doc == null) return;
            int want = (int)((playStartFrame + clock.ElapsedMilliseconds * tl.Fps / 1000) % tl.Count);
            if (frames[want] == null)
            {   // 준비 안 된 프레임에서는 시간을 멈추고 기다린다
                status.Text = $"그리는 중… ({PrepText()})";
                playStartFrame = want; clock.Restart(); return;
            }
            if (want != current) { current = want; seek.Value = want; UpdateLabels(want); view.SetFrame(Decode(frames[want])); }
            status.Text = PrepText();
        }

        /// <summary>창 없이 내보낸다. 성공 0, 실패 1.</summary>
        public static int ExportCli(string input, string output, int tween = 24, int play = 24)
        {
            try
            {
                SfaDoc d; using (var s = File.OpenRead(input)) d = SfaDoc.Parse(s);
                string ff = Path.Combine(AppContext.BaseDirectory, "ffmpeg.exe");
                var sw = Stopwatch.StartNew();
                var t = new Timeline(d.FrameCount, tween, play);
                bool ok = WriteMp4(d, t, ff, output, null, CancellationToken.None, out string err);
                File.WriteAllText(output + ".log.txt", ok ? $"ok {sw.Elapsed.TotalSeconds:F1}s frames={t.Count} fps={t.Fps}" : "fail " + err);
                return ok ? 0 : 1;
            }
            catch (Exception e) { try { File.WriteAllText(output + ".log.txt", "fail " + e); } catch { } return 1; }
        }

        static bool WriteMp4(SfaDoc d, Timeline tl, string ff, string outPath, Action<int> progress, CancellationToken ct, out string error)
        {
            error = null;
            int W = 1920, H = ((int)(W * d.Ratio) + 1) & ~1;
            var psi = new ProcessStartInfo(ff, $"-y -v error -f rawvideo -pix_fmt bgra -s {W}x{H} -r {tl.Fps} -i - -c:v libx264 -preset medium -crf 16 -pix_fmt yuv420p -movflags +faststart \"{outPath}\"")
            { UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true };
            using var p = Process.Start(psi);
            var err = p.StandardError.ReadToEndAsync();
            int threads = Math.Clamp(Environment.ProcessorCount - 1, 1, 4);
            var renderers = new ThreadLocal<(FrameRenderer, SKBitmap, SKCanvas)>(() => { var b = new SKBitmap(W, H, SKColorType.Bgra8888, SKAlphaType.Premul); return (new FrameRenderer(d), b, new SKCanvas(b)); });
            var pending = new Queue<Task<byte[]>>(); int submitted = 0;
            void Fill() { while (submitted < tl.Count && pending.Count < threads + 1) { int f = submitted++; pending.Enqueue(Task.Run(() => { var (r, b, c) = renderers.Value; r.Render(tl, f, c, W); c.Flush(); return (byte[])b.Bytes.Clone(); })); } }
            var stdin = p.StandardInput.BaseStream;
            try
            {
                for (int f = 0; f < tl.Count; f++)
                {
                    if (ct.IsCancellationRequested) { try { p.Kill(); } catch { } return false; }
                    Fill(); var bytes = pending.Dequeue().Result; Fill();
                    stdin.Write(bytes, 0, bytes.Length);
                    progress?.Invoke(f + 1);
                }
                stdin.Close(); p.WaitForExit();
                if (p.ExitCode != 0) { error = err.Result; return false; }
                return true;
            }
            catch (Exception e) { error = e.Message; try { p.Kill(); } catch { } return false; }
        }

        void ExportOrCancel()
        {
            if (exportCts != null) { exportCts.Cancel(); return; }
            string ff = Path.Combine(AppContext.BaseDirectory, "ffmpeg.exe");
            if (!File.Exists(ff)) { MessageBox.Show(this, "SfaViewer.exe와 같은 폴더에 ffmpeg.exe가 있어야 내보낼 수 있습니다.", "SFA 뷰어"); return; }
            using var dlg = new SaveFileDialog { Filter = "MP4 (*.mp4)|*.mp4", FileName = fileName + ".mp4" };
            if (dlg.ShowDialog(this) != DialogResult.OK) return;
            StopPlay();
            exportCts = new CancellationTokenSource(); var ct = exportCts.Token; var d = doc; var t = tl; string outPath = dlg.FileName;
            fpsBtn.Enabled = false;
            exportBtn.Text = "취소"; exportIcon.Color = Theme.Orange; exportIcon.Invalidate(); openIcon.Enabled = false;
            var sw = Stopwatch.StartNew();
            Task.Run(() =>
            {
                bool ok = WriteMp4(d, t, ff, outPath, n => BeginInvoke(() => { status.Text = $"MP4 내보내는 중 {n}/{t.Count}"; exportBtn.Text = $"취소 ({n}/{t.Count})"; }), ct, out string error);
                if (!ok) { try { File.Delete(outPath); } catch { } }
                double sec = sw.Elapsed.TotalSeconds;
                BeginInvoke(() =>
                {
                    if (ok) status.Text = $"저장됨: {outPath} ({sec:F1}초)";
                    else status.Text = ct.IsCancellationRequested ? "내보내기 취소됨" : "내보내기 실패: " + error;
                    exportBtn.Text = "MP4 내보내기"; exportIcon.Color = Theme.Icon; exportIcon.Invalidate(); openIcon.Enabled = true; fpsBtn.Enabled = true; exportCts = null;
                });
            });
        }

        protected override void OnFormClosing(FormClosingEventArgs e) { prepCts?.Cancel(); exportCts?.Cancel(); base.OnFormClosing(e); }
    }

    /// <summary>현재 프레임을 비율 유지해 가운데에 그린다(깜빡임 없이).</summary>
    sealed class FrameView : Control
    {
        Bitmap bmp;
        public FrameView() { DoubleBuffered = true; BackColor = Color.Black; SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true); }
        public void SetFrame(Bitmap b) { var old = bmp; bmp = b; old?.Dispose(); Invalidate(); }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.Clear(Color.Black);
            if (bmp == null) return;
            float s = Math.Min((float)Width / bmp.Width, (float)Height / bmp.Height);
            float w = bmp.Width * s, h = bmp.Height * s;
            e.Graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBilinear;
            e.Graphics.DrawImage(bmp, (Width - w) / 2, (Height - h) / 2, w, h);
        }
    }

    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            // 명령줄 내보내기: SfaViewer.exe --export <입력.sfa> <출력.mp4> [트위닝,재생]
            if ((args.Length == 3 || args.Length == 4) && args[0] == "--export")
            {
                int t = 24, p = 24;
                if (args.Length == 4) { var a = args[3].Split(','); t = int.Parse(a[0]); p = int.Parse(a[1]); }
                Environment.Exit(MainForm.ExportCli(args[1], args[2], t, p)); return;
            }
            ApplicationConfiguration.Initialize();
            // 화면 배율(시스템 DPI)을 읽어 위치·크기 계산에 쓴다. 글꼴(pt)은 Windows가 배율대로 키운다
            try { using var g = Graphics.FromHwnd(IntPtr.Zero); Theme.S = Math.Max(1f, g.DpiX / 96f); } catch { }
            Application.Run(new MainForm());
        }
    }
}
