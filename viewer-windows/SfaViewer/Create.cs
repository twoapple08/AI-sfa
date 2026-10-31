using System.Diagnostics;
using SfaCore.Gen;

namespace SfaViewer
{
    /// <summary>
    /// 1v1 만들기(안드로이드 크리에이터와 같은 생성기, SfaCore/Gen). 기기 안에서만 만든다(네트워크 없음).
    /// 출력: 문서\SfaCreator\&lt;이름&gt;\&lt;이름&gt;_N.sfa, 파일 하나 = 5초. 만든 뒤 첫 파일을 (트위닝, 재생)으로 바로 연다.
    /// 학습 자료: motion_lib.txt(exe 안), 이펙트 사전 effects.txt(exe 옆 — 다른 작가 그림 유래라 저장소 밖, 없으면 이펙트 없이 만든다).
    /// </summary>
    public sealed partial class MainForm
    {
        static MotionLib motionLib;
        static EffectLib effectLib;
        static string effectNote = "";

        static void LoadLibs()
        {
            if (motionLib != null) return;
            using (var s = typeof(MainForm).Assembly.GetManifestResourceStream("motion_lib.txt"))
                motionLib = MotionLib.Read(new StreamReader(s));
            string fxPath = Path.Combine(AppContext.BaseDirectory, "effects.txt");
            if (File.Exists(fxPath)) { using var r = new StreamReader(fxPath); effectLib = EffectLib.Read(r); effectNote = $"이펙트 사전: 쐐기 {effectLib.wedges.Count} · 덩어리 {effectLib.blobs.Count} · 장면 {effectLib.scenes.Count}"; }
            else { effectLib = EffectLib.Empty; effectNote = "이펙트 사전(effects.txt)이 exe 옆에 없어 이펙트 없이 만듭니다"; }
        }

        static string OutRoot => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "SfaCreator");

        int lastSeconds = 10, lastTween = 24, lastPlay = 24; bool lastDark = false; string lastTags = "1v1";

        void AskCreate()
        {
            using var f = new Form { Text = "1v1 만들기", FormBorderStyle = FormBorderStyle.FixedDialog, MaximizeBox = false, MinimizeBox = false, StartPosition = FormStartPosition.CenterParent, ClientSize = new Size(P(440), P(400)), BackColor = Theme.Bg, Font = Theme.Regular(10) };
            Label L(string t, int x, int y, int w = 180, bool bold = true) { var l = new Label { Text = t, Font = bold ? Theme.Bold(10) : Theme.Regular(9), ForeColor = bold ? Theme.Text : Theme.Sub, AutoSize = false }; l.SetBounds(P(x), P(y), P(w), P(24)); f.Controls.Add(l); return l; }
            L("태그(쉼표로 구분)", 20, 14);
            var tags = new TextBox { Text = lastTags }; tags.SetBounds(P(20), P(40), P(400), P(28)); f.Controls.Add(tags);
            L("지금은 1v1(맨손 둘, 도구·배경 없음)만 만듭니다", 20, 70, 400, false);
            L("길이(초)", 20, 104);
            var secs = new NumericUpDown { Minimum = 1, Maximum = 120, Value = lastSeconds }; secs.SetBounds(P(20), P(130), P(120), P(28)); f.Controls.Add(secs);
            L("배경", 230, 104);
            var bg = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList }; bg.Items.AddRange(new object[] { "흰색", "검정" }); bg.SelectedIndex = lastDark ? 1 : 0; bg.SetBounds(P(230), P(130), P(120), P(28)); f.Controls.Add(bg);
            L("트위닝 FPS", 20, 170); L("재생 FPS", 230, 170);
            var nt = new NumericUpDown { Minimum = 1, Maximum = 120, Value = lastTween }; nt.SetBounds(P(20), P(196), P(120), P(28)); f.Controls.Add(nt);
            var np = new NumericUpDown { Minimum = 1, Maximum = 120, Value = lastPlay }; np.SetBounds(P(230), P(196), P(120), P(28)); f.Controls.Add(np);
            L("시드(같은 값이면 같은 결과)", 20, 236, 300);
            var seed = new NumericUpDown { Minimum = 0, Maximum = 999999999, Value = Random.Shared.Next(1, 999999999) }; seed.SetBounds(P(20), P(262), P(200), P(28)); f.Controls.Add(seed);
            var dice = new Button { Text = "새 시드" }; dice.SetBounds(P(230), P(261), P(100), P(30)); dice.Click += (_, _) => seed.Value = Random.Shared.Next(1, 999999999); f.Controls.Add(dice);
            L("파일은 5초마다 나뉘어 문서\\SfaCreator 에 저장됩니다", 20, 304, 400, false);
            var ok = new Button { Text = "만들기", DialogResult = DialogResult.OK }; ok.SetBounds(P(236), P(350), P(90), P(34));
            var cancel = new Button { Text = "취소", DialogResult = DialogResult.Cancel }; cancel.SetBounds(P(332), P(350), P(90), P(34));
            f.Controls.AddRange(new Control[] { ok, cancel }); f.AcceptButton = ok; f.CancelButton = cancel;
            if (f.ShowDialog(this) != DialogResult.OK) return;
            lastTags = tags.Text; lastSeconds = (int)secs.Value; lastTween = (int)nt.Value; lastPlay = (int)np.Value; lastDark = bg.SelectedIndex == 1;
            _ = Create(new Request { prompt = lastTags, seconds = lastSeconds, tween = lastTween, play = lastPlay, seed = (long)seed.Value, dark = lastDark });
        }

        async Task Create(Request req)
        {
            if (exportCts != null) return;
            makeBtn.Enabled = false; fab.Enabled = false;
            string name = $"1v1_{DateTime.Now:yyyyMMdd_HHmmss}";
            string dir = Path.Combine(OutRoot, name);
            homeSub.Text = "만드는 중…";
            var sw = Stopwatch.StartNew();
            try
            {
                var (files, counts, notes) = await Task.Run(() =>
                {
                    LoadLibs();
                    var g = SfaCore.Gen.Generator.Generate(motionLib, effectLib, req);
                    Directory.CreateDirectory(dir);
                    var list = new List<string>(); var counts = new List<int>();
                    var parts = g.Parts;
                    for (int i = 0; i < parts.Count; i++)
                    {
                        string nm = $"{name}_{i + 1}";
                        string p = Path.Combine(dir, nm + ".sfa");
                        using (var o = File.Create(p)) SfaCore.Gen.Generator.WriteSfa(g, parts[i].start, parts[i].end, nm, o);
                        list.Add(p); counts.Add(parts[i].end - parts[i].start);
                        BeginInvoke(() => homeSub.Text = $"만드는 중… 파일 {i + 1}/{parts.Count}");
                    }
                    // 영문 파일 이름(wine 시험에서 한글 이름 파일 쓰기가 실패했다). 실패해도 만들기는 계속한다
                    try { File.WriteAllText(Path.Combine(dir, "settings.txt"),
                        $"태그: {req.prompt}\n길이: {req.seconds}초\nFPS (트위닝, 재생): ({req.tween}, {req.play})\n배경: {(req.dark ? "검정" : "흰색")}\n시드: {req.seed}\n{effectNote}\n" + string.Join("\n", g.notes)); } catch { }
                    return (list, counts, g.notes);
                });
                // 만든 파일마다 (트위닝, 재생)을 기억해 두고 최근 목록에 올린다(뷰어는 SFA에 FPS가 없어 파일별로 기억한다)
                foreach (var p in files)
                {
                    string key = KeyOf(new FileInfo(p));
                    try { Directory.CreateDirectory(CacheDir); File.WriteAllText(FpsFile(key), $"{req.tween},{req.play}"); } catch { }
                }
                for (int i = files.Count - 1; i >= 1; i--) Recent.Remember(new RecentItem { Path = files[i], Name = Path.GetFileNameWithoutExtension(files[i]), Frames = counts[i], Key = KeyOf(new FileInfo(files[i])) });
                homeSub.Text = $"만들기 완료: {files.Count}개 파일, {sw.Elapsed.TotalSeconds:F1}초 · {dir}";
                if (notes.Count > 0 || effectLib.wedges.Count == 0) MessageBox.Show(this, string.Join("\n", notes.Append(effectNote)), "1v1 만들기");
                await LoadFile(files[0]);
            }
            catch (Exception e) { homeSub.Text = "만들기 실패: " + e.Message; }
            finally { makeBtn.Enabled = true; fab.Enabled = true; }
        }
    }
}
