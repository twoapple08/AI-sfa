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
        readonly Label status = new() { AutoSize = false, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft, ForeColor = Color.White };
        readonly Button openBtn = new() { Text = "열기", Width = 70, Height = 30 };
        readonly Button exportBtn = new() { Text = "MP4 내보내기", Width = 110, Height = 30, Enabled = false };
        readonly Button playBtn = new() { Text = "재생", Width = 70, Height = 30, Enabled = false };
        readonly TrackBar seek = new() { Dock = DockStyle.Fill, TickStyle = TickStyle.None, Enabled = false };
        readonly FrameView view = new() { Dock = DockStyle.Fill };
        readonly System.Windows.Forms.Timer timer = new() { Interval = 1000 / Fps };

        SfaDoc doc; string fileName = "sfa";
        byte[][] frames; int prepared; CancellationTokenSource prepCts;
        int current; bool playing; CancellationTokenSource exportCts;
        readonly Stopwatch clock = new(); int playStartFrame;

        public MainForm()
        {
            Text = "SFA 뷰어"; Width = 1400; Height = 900; BackColor = Color.Black; KeyPreview = true;
            try { Icon = new Icon(typeof(MainForm).Assembly.GetManifestResourceStream("SfaViewer.app.ico")); } catch { }
            var top = new TableLayoutPanel { Dock = DockStyle.Top, Height = 38, ColumnCount = 3, BackColor = Color.FromArgb(32, 32, 32) };
            top.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); top.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            top.Controls.Add(openBtn, 0, 0); top.Controls.Add(status, 1, 0); top.Controls.Add(exportBtn, 2, 0);
            var bottom = new TableLayoutPanel { Dock = DockStyle.Bottom, Height = 40, ColumnCount = 2, BackColor = Color.FromArgb(32, 32, 32) };
            bottom.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); bottom.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            bottom.Controls.Add(playBtn, 0, 0); bottom.Controls.Add(seek, 1, 0);
            foreach (var b in new[] { openBtn, exportBtn, playBtn }) { b.ForeColor = Color.White; b.FlatStyle = FlatStyle.Flat; }
            Controls.Add(view); Controls.Add(top); Controls.Add(bottom);
            status.Text = "SFA 파일을 여세요(끌어다 놓기도 됩니다). 스페이스=재생, ←/→=한 프레임";

            openBtn.Click += (_, _) => { using var dlg = new OpenFileDialog { Filter = "SFA (*.sfa)|*.sfa|모든 파일|*.*" }; if (dlg.ShowDialog(this) == DialogResult.OK) _ = LoadFile(dlg.FileName); };
            playBtn.Click += (_, _) => TogglePlay();
            exportBtn.Click += (_, _) => ExportOrCancel();
            seek.Scroll += (_, _) => { StopPlay(); Show(seek.Value); };
            timer.Tick += (_, _) => Tick();
            AllowDrop = true;
            DragEnter += (_, e) => { if (e.Data.GetDataPresent(DataFormats.FileDrop)) e.Effect = DragDropEffects.Copy; };
            DragDrop += (_, e) => { var f = (string[])e.Data.GetData(DataFormats.FileDrop); if (f?.Length > 0) _ = LoadFile(f[0]); };
            KeyDown += (_, e) =>
            {
                if (doc == null) return;
                if (e.KeyCode == Keys.Space) { TogglePlay(); e.Handled = true; }
                else if (e.KeyCode == Keys.Right) { StopPlay(); Show(Math.Min(current + 1, doc.FrameCount - 1)); e.Handled = true; }
                else if (e.KeyCode == Keys.Left) { StopPlay(); Show(Math.Max(current - 1, 0)); e.Handled = true; }
            };
            var cmd = Environment.GetCommandLineArgs();
            if (cmd.Length > 1 && File.Exists(cmd[1])) Shown += (_, _) => _ = LoadFile(cmd[1]);
        }

        static string CacheDir => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SfaViewer");

        async Task LoadFile(string path)
        {
            StopPlay(); prepCts?.Cancel(); exportCts?.Cancel();
            openBtn.Enabled = exportBtn.Enabled = playBtn.Enabled = seek.Enabled = false;
            fileName = Path.GetFileNameWithoutExtension(path);
            var sw = Stopwatch.StartNew();
            try
            {
                var fi = new FileInfo(path);
                string key = $"{fi.Name}_{fi.Length}_{fi.LastWriteTimeUtc.Ticks}".GetHashCode().ToString("x8");
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
                status.Text = $"{fi.Name} · {doc.FrameCount}프레임 · 오브젝트 {doc.ObjCount} · {how} {sw.Elapsed.TotalSeconds:F1}초";
                seek.Maximum = Math.Max(doc.FrameCount - 1, 0); seek.Value = 0;
                playBtn.Enabled = exportBtn.Enabled = seek.Enabled = true;
                StartPrepare();
                Show(0);
            }
            catch (Exception e) { status.Text = "열기 실패: " + e.Message; }
            finally { openBtn.Enabled = true; }
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

        Bitmap Decode(byte[] jpg) { using var ms = new MemoryStream(jpg); return new Bitmap(ms); }

        void Show(int f)
        {
            if (doc == null) return;
            current = Math.Clamp(f, 0, doc.FrameCount - 1);
            if (seek.Value != current) seek.Value = current;
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
            if (!playing) status.Text = $"{current + 1}/{doc.FrameCount} · 미리 그리기 {prepared}/{doc.FrameCount}";
        }

        void TogglePlay() { if (playing) StopPlay(); else StartPlay(); }
        void StartPlay() { if (doc == null) return; playing = true; playBtn.Text = "정지"; clock.Restart(); playStartFrame = current; timer.Start(); }
        void StopPlay() { playing = false; playBtn.Text = "재생"; timer.Stop(); }

        void Tick()
        {
            if (!playing || doc == null) return;
            int want = (playStartFrame + (int)(clock.ElapsedMilliseconds * Fps / 1000)) % doc.FrameCount;
            if (frames[want] == null)
            {   // 준비 안 된 프레임에서는 시간을 멈추고 기다린다
                status.Text = $"{want + 1}/{doc.FrameCount} · 그리는 중… (미리 그리기 {prepared}/{doc.FrameCount})";
                playStartFrame = want; clock.Restart(); return;
            }
            if (want != current) { current = want; seek.Value = want; view.SetFrame(Decode(frames[want])); }
            status.Text = $"{current + 1}/{doc.FrameCount} · 미리 그리기 {prepared}/{doc.FrameCount}";
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
            exportBtn.Text = "취소"; openBtn.Enabled = false;
            var sw = Stopwatch.StartNew();
            Task.Run(() =>
            {
                bool ok = WriteMp4(d, ff, outPath, n => BeginInvoke(() => status.Text = $"내보내는 중 {n}/{d.FrameCount}"), ct, out string error);
                if (!ok) { try { File.Delete(outPath); } catch { } }
                double sec = sw.Elapsed.TotalSeconds;
                BeginInvoke(() =>
                {
                    if (ok) status.Text = $"저장됨: {outPath} ({sec:F1}초)";
                    else status.Text = ct.IsCancellationRequested ? "내보내기 취소됨" : "내보내기 실패: " + error;
                    exportBtn.Text = "MP4 내보내기"; openBtn.Enabled = true; exportCts = null;
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
