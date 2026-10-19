using System.Collections.Concurrent;
using System.Diagnostics;
using System.Drawing.Imaging;
using SfaCore;
using SkiaSharp;

namespace SfaViewer
{
    /// <summary>
    /// SFA 보기·재생·MP4 내보내기(Windows). 안드로이드 뷰어와 같은 방식:
    /// 처음 열 때 변환해 캐시(.sfab)로 저장 → 여러 스레드가 프레임을 미리 그려 JPEG로 메모리에 보관 → 재생은 24fps로 보여 주기만.
    /// 내보내기는 exe 옆의 ffmpeg.exe에 원시 프레임을 넘겨 H.264 MP4로 만든다.
    /// </summary>
    public sealed class MainForm : Form
    {
        const int Fps = 24, PreviewW = 1280;
        // 첫 화면
        readonly Panel home = new() { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Theme.Bg };
        readonly TextLabel homeTitle = new(Theme.Bold(30), Theme.Orange, ContentAlignment.MiddleCenter) { Text = "SFA VIEWER" };
        readonly TextLabel homeSub = new(Theme.Regular(10), Theme.Sub, ContentAlignment.MiddleCenter) { Text = "Stick Fighter 애니메이션 미리보기 · 내보내기  (파일을 끌어다 놓아도 됩니다)" };
        readonly CardPanel pillBg = new() { Radius = 26 };
        readonly PillButton pill = new("최근 파일") { Fill = Color.White, Fore = Theme.Text, Cursor = Cursors.Default };
        readonly TextLabel empty = new(Theme.Regular(11), Theme.Sub, ContentAlignment.MiddleCenter) { Text = "아래 + 버튼으로 SFA 파일을 여세요" };
        readonly IconButton fab = new(IconKind.Plus) { Color = Color.White, Fill = Theme.Orange, Size = new Size(68, 68) };
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
        readonly FrameView view = new();
        readonly System.Windows.Forms.Timer timer = new() { Interval = 1000 / Fps };

        SfaDoc doc; string fileName = "sfa", filePath, fileKey;
        byte[][] frames; int prepared; CancellationTokenSource prepCts;
        int current; bool playing; CancellationTokenSource exportCts;
        readonly Stopwatch clock = new(); int playStartFrame;

        public MainForm()
        {
            Text = "SFA 뷰어"; Width = 1280; Height = 860; MinimumSize = new Size(420, 560); BackColor = Theme.Bg; KeyPreview = true;
            try { Icon = new Icon(typeof(MainForm).Assembly.GetManifestResourceStream("SfaViewer.app.ico")); } catch { }
            home.Controls.AddRange(new Control[] { homeTitle, homeSub, pillBg, empty });
            pillBg.Controls.Add(pill);
            Controls.Add(fab); Controls.Add(player); Controls.Add(home);
            player.Controls.AddRange(new Control[] { backBtn, title, openIcon, exportIcon, view, frameLabel, timeLabel, seek, prevBtn, playBtn, nextBtn, status, infoCard });
            infoCard.Controls.AddRange(new Control[] { infoHead, info, exportBtn });
            home.Resize += (_, _) => LayoutHome();
            player.Resize += (_, _) => LayoutPlayer();

            fab.Click += (_, _) => PickFile();
            openIcon.Click += (_, _) => PickFile();
            backBtn.Click += (_, _) => GoHome();
            playBtn.Click += (_, _) => TogglePlay();
            prevBtn.Click += (_, _) => Step(-1);
            nextBtn.Click += (_, _) => Step(1);
            view.Click += (_, _) => TogglePlay();
            exportBtn.Click += (_, _) => ExportOrCancel();
            exportIcon.Click += (_, _) => ExportOrCancel();
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

        void LayoutHome()
        {
            int W = home.ClientSize.Width, y = 44 - (home.AutoScrollPosition.Y < 0 ? -home.AutoScrollPosition.Y : 0);
            homeTitle.SetBounds(0, y, W, 60); y += 64;
            homeSub.SetBounds(0, y, W, 24); y += 46;
            pillBg.SetBounds((W - 170) / 2, y, 170, 54); pill.SetBounds(5, 5, 160, 44); y += 78;
            empty.SetBounds(0, y + 30, W, 30);
            int cols = Math.Max(2, (W - 32) / 280), gap = 22, cw = (W - 48 - gap * (cols - 1)) / cols, ch = (int)(cw * 0.62f) + 66;
            for (int i = 0; i < cards.Count; i++) cards[i].SetBounds(24 + (i % cols) * (cw + gap), y + (i / cols) * (ch + gap), cw, ch);
            fab.Location = new Point((ClientSize.Width - fab.Width) / 2, ClientSize.Height - fab.Height - 28);
            fab.BringToFront();
        }

        protected override void OnResize(EventArgs e) { base.OnResize(e); if (fab != null) fab.Location = new Point((ClientSize.Width - fab.Width) / 2, ClientSize.Height - fab.Height - 28); }

        // ───────── 플레이어 배치: 창이 세로로 길면 세로 보기(영상 위, 조작 아래), 아니면 가로 보기 ─────────

        void LayoutPlayer()
        {
            int W = player.ClientSize.Width, H = player.ClientSize.Height;
            if (W <= 0 || H <= 0) return;
            float ratio = doc?.Ratio ?? 0.5625f;
            bool portrait = H > W;
            backBtn.SetBounds(8, 6, 48, 48);
            exportIcon.SetBounds(W - 56, 6, 48, 48);
            openIcon.SetBounds(W - 104, 6, 48, 48);
            if (!portrait)
            {
                title.TextAlign = ContentAlignment.MiddleLeft; title.SetBounds(60, 6, Math.Min(520, W / 2), 48);
                status.TextAlign = ContentAlignment.MiddleRight; status.SetBounds(title.Right + 8, 6, Math.Max(10, openIcon.Left - title.Right - 16), 48);
                int barH = 64, top = 60;
                view.SetBounds(0, top, W, H - top - barH);
                int by = H - barH + 8;
                playBtn.SetBounds(16, by, 48, 48);
                timeLabel.TextAlign = ContentAlignment.MiddleLeft; timeLabel.SetBounds(70, by, 120, 48);
                nextBtn.SetBounds(W - 56, by + 2, 44, 44); prevBtn.SetBounds(W - 102, by + 2, 44, 44);
                frameLabel.TextAlign = ContentAlignment.MiddleRight; frameLabel.SetBounds(W - 210, by, 104, 48);
                seek.SetBounds(196, by + 10, Math.Max(20, frameLabel.Left - 206), 28);
                infoCard.Visible = false;
            }
            else
            {
                title.TextAlign = ContentAlignment.MiddleCenter; title.SetBounds(60, 6, Math.Max(10, openIcon.Left - 64), 48);
                int top = 60, vh = (int)Math.Min(W * ratio, H * 0.55f);
                view.SetBounds(0, top, W, vh);
                int y = top + vh + 18, px = 26;
                frameLabel.TextAlign = ContentAlignment.MiddleLeft; frameLabel.SetBounds(px, y, W / 2 - px, 28);
                timeLabel.TextAlign = ContentAlignment.MiddleRight; timeLabel.SetBounds(W / 2, y, W / 2 - px, 28); y += 34;
                seek.SetBounds(px - 8, y, W - 2 * px + 16, 28); y += 40;
                int ps = 76; playBtn.SetBounds((W - ps) / 2, y, ps, ps);
                prevBtn.SetBounds(playBtn.Left - 36 - 56, y + 10, 56, 56); nextBtn.SetBounds(playBtn.Right + 36, y + 10, 56, 56); y += ps + 6;
                status.TextAlign = ContentAlignment.MiddleCenter; status.SetBounds(px, y, W - 2 * px, 22); y += 36;
                int ch = Math.Min(210, Math.Max(150, H - y - 20));
                infoCard.Visible = true; infoCard.SetBounds(px, y, W - 2 * px, ch);
                int iw = infoCard.Width - 40;
                infoHead.SetBounds(20, 16, iw, 24); info.SetBounds(20, 46, iw, ch - 46 - 72); exportBtn.SetBounds(20, ch - 66, iw, 48);
            }
            infoCard.Invalidate();
        }

        void UpdateLabels(int f)
        {
            int n = doc?.FrameCount ?? 0;
            frameLabel.Text = n > 0 ? $"{f + 1} / {n}" : "– / –";
            string T(int fr) => $"{fr / Fps / 60:00}:{fr / Fps % 60:00}";
            timeLabel.Text = n > 0 ? $"{T(f)} / {T(n)}" : "";
        }

        void SetEnabled(bool on) { foreach (Control c in new Control[] { playBtn, prevBtn, nextBtn, seek, exportBtn, exportIcon }) c.Enabled = on; }
        void Step(int d) { if (doc == null) return; StopPlay(); Show(Math.Clamp(current + d, 0, doc.FrameCount - 1)); }

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
                string key = fileKey = $"{fi.Name}_{fi.Length}_{fi.LastWriteTimeUtc.Ticks}".GetHashCode().ToString("x8");
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
                info.Text = $"{doc.FrameCount}프레임 · {doc.FrameCount / (double)Fps:F1}초 (24fps)\n1920×{(int)Math.Round(1920 * doc.Ratio)} · 오브젝트 {doc.ObjCount:N0}개\n불러오기: {how} {sw.Elapsed.TotalSeconds:F1}초";
                seek.Maximum = Math.Max(doc.FrameCount - 1, 0); seek.Value = 0;
                SetEnabled(true);
                LayoutPlayer();
                StartPrepare();
                Show(0);
                Recent.Remember(new RecentItem { Path = path, Name = fileName, Frames = doc.FrameCount, Key = key });
                SaveThumb(key, frames[0]);
            }
            catch (Exception e) { status.Text = "열기 실패: " + e.Message; title.Text = "열기 실패"; }
            finally { openIcon.Enabled = true; }
        }

        /// <summary>여러 스레드로 모든 프레임을 미리 그려 JPEG로 보관한다(현재 위치부터).</summary>
        void StartPrepare()
        {
            prepCts = new CancellationTokenSource(); var ct = prepCts.Token; var d = doc;
            frames = new byte[d.FrameCount][]; prepared = 0;
            int threads = Math.Max(1, Environment.ProcessorCount - 1);
            var queue = new ConcurrentQueue<int>(Enumerable.Range(0, d.FrameCount));
            for (int t = 0; t < threads; t++)
                Task.Run(() =>
                {
                    var r = new FrameRenderer(d);
                    int h = Math.Max(2, (int)(PreviewW * d.Ratio));
                    using var bmp = new SKBitmap(PreviewW, h);
                    using var c = new SKCanvas(bmp);
                    while (!ct.IsCancellationRequested && queue.TryDequeue(out int f))
                    {
                        if (frames[f] != null) continue;
                        try
                        {
                            r.Render(f, c, PreviewW); c.Flush();
                            using var img = SKImage.FromBitmap(bmp); using var data = img.Encode(SKEncodedImageFormat.Jpeg, 92);
                            frames[f] = data.ToArray(); Interlocked.Increment(ref prepared);
                        }
                        catch { }
                    }
                }, ct);
        }

        string PrepText() => doc == null ? "" : prepared >= doc.FrameCount ? "미리 그리기 완료" : $"미리 그리기 {prepared}/{doc.FrameCount}";

        /// <summary>첫 화면 카드용 미리보기(0번 프레임, 폭 480).</summary>
        static void SaveThumb(string key, byte[] jpg)
        {
            try
            {
                string f = Path.Combine(CacheDir, "thumbs", key + ".jpg");
                if (jpg == null || File.Exists(f)) return;
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
            current = Math.Clamp(f, 0, doc.FrameCount - 1);
            seek.Value = current; UpdateLabels(current);
            var j = frames?[current];
            if (j != null) view.SetFrame(Decode(j));
            else
            {
                // 아직 안 그린 프레임: 바로 그려서 보여 준다(재생 중이 아닐 때)
                var r = new FrameRenderer(doc);
                int h = Math.Max(2, (int)(PreviewW * doc.Ratio));
                using var bmp = new SKBitmap(PreviewW, h); using var c = new SKCanvas(bmp);
                r.Render(current, c, PreviewW); c.Flush();
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
            int want = (playStartFrame + (int)(clock.ElapsedMilliseconds * Fps / 1000)) % doc.FrameCount;
            if (frames[want] == null)
            {   // 준비 안 된 프레임에서는 시간을 멈추고 기다린다
                status.Text = $"그리는 중… ({PrepText()})";
                playStartFrame = want; clock.Restart(); return;
            }
            if (want != current) { current = want; seek.Value = want; UpdateLabels(want); view.SetFrame(Decode(frames[want])); }
            status.Text = PrepText();
        }

        /// <summary>창 없이 내보낸다. 성공 0, 실패 1.</summary>
        public static int ExportCli(string input, string output)
        {
            try
            {
                SfaDoc d; using (var s = File.OpenRead(input)) d = SfaDoc.Parse(s);
                string ff = Path.Combine(AppContext.BaseDirectory, "ffmpeg.exe");
                var sw = Stopwatch.StartNew();
                bool ok = WriteMp4(d, ff, output, null, CancellationToken.None, out string err);
                File.WriteAllText(output + ".log.txt", ok ? $"ok {sw.Elapsed.TotalSeconds:F1}s frames={d.FrameCount}" : "fail " + err);
                return ok ? 0 : 1;
            }
            catch (Exception e) { try { File.WriteAllText(output + ".log.txt", "fail " + e); } catch { } return 1; }
        }

        static bool WriteMp4(SfaDoc d, string ff, string outPath, Action<int> progress, CancellationToken ct, out string error)
        {
            error = null;
            int W = 1920, H = ((int)(W * d.Ratio) + 1) & ~1;
            var psi = new ProcessStartInfo(ff, $"-y -v error -f rawvideo -pix_fmt bgra -s {W}x{H} -r {Fps} -i - -c:v libx264 -preset medium -crf 16 -pix_fmt yuv420p -movflags +faststart \"{outPath}\"")
            { UseShellExecute = false, RedirectStandardInput = true, RedirectStandardError = true, CreateNoWindow = true };
            using var p = Process.Start(psi);
            var err = p.StandardError.ReadToEndAsync();
            int threads = Math.Clamp(Environment.ProcessorCount - 1, 1, 4);
            var renderers = new ThreadLocal<(FrameRenderer, SKBitmap, SKCanvas)>(() => { var b = new SKBitmap(W, H, SKColorType.Bgra8888, SKAlphaType.Premul); return (new FrameRenderer(d), b, new SKCanvas(b)); });
            var pending = new Queue<Task<byte[]>>(); int submitted = 0;
            void Fill() { while (submitted < d.FrameCount && pending.Count < threads + 1) { int f = submitted++; pending.Enqueue(Task.Run(() => { var (r, b, c) = renderers.Value; r.Render(f, c, W); c.Flush(); return (byte[])b.Bytes.Clone(); })); } }
            var stdin = p.StandardInput.BaseStream;
            try
            {
                for (int f = 0; f < d.FrameCount; f++)
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
            exportCts = new CancellationTokenSource(); var ct = exportCts.Token; var d = doc; string outPath = dlg.FileName;
            exportBtn.Text = "취소"; exportIcon.Color = Theme.Orange; exportIcon.Invalidate(); openIcon.Enabled = false;
            var sw = Stopwatch.StartNew();
            Task.Run(() =>
            {
                bool ok = WriteMp4(d, ff, outPath, n => BeginInvoke(() => { status.Text = $"MP4 내보내는 중 {n}/{d.FrameCount}"; exportBtn.Text = $"취소 ({n}/{d.FrameCount})"; }), ct, out string error);
                if (!ok) { try { File.Delete(outPath); } catch { } }
                double sec = sw.Elapsed.TotalSeconds;
                BeginInvoke(() =>
                {
                    if (ok) status.Text = $"저장됨: {outPath} ({sec:F1}초)";
                    else status.Text = ct.IsCancellationRequested ? "내보내기 취소됨" : "내보내기 실패: " + error;
                    exportBtn.Text = "MP4 내보내기"; exportIcon.Color = Theme.Icon; exportIcon.Invalidate(); openIcon.Enabled = true; exportCts = null;
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
            // 명령줄 내보내기: SfaViewer.exe --export <입력.sfa> <출력.mp4>
            if (args.Length == 3 && args[0] == "--export") { Environment.Exit(MainForm.ExportCli(args[1], args[2])); return; }
            ApplicationConfiguration.Initialize(); Application.Run(new MainForm());
        }
    }
}
