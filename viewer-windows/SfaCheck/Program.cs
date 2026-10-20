// 서버(리눅스)에서 SfaCore를 검사한다: 읽기 시간·캐시 왕복·지정 프레임 PNG.
// 사용: SfaCheck <file.sfa> <out_dir> 0,30,60 [트위닝,재생]  (넷째 인수가 있으면 프레임 번호를 그 시간표의 출력 번호로 본다)
using System.Diagnostics;
using SfaCore;
using SkiaSharp;

var sw = Stopwatch.StartNew();
SfaDoc d;
using (var f = File.OpenRead(args[0])) d = SfaDoc.Parse(f);
Console.WriteLine($"parse {sw.ElapsedMilliseconds}ms frames={d.FrameCount} AO={d.ObjCount} FR={d.FillCount}");
var ms = new MemoryStream(); d.Write(ms); ms.Position = 0;
sw.Restart(); var d2 = SfaDoc.Read(ms); Console.WriteLine($"cache {ms.Length / 1e6:F1}MB read {sw.ElapsedMilliseconds}ms ok={d2.ObjCount == d.ObjCount}");
Directory.CreateDirectory(args[1]);
var r = new FrameRenderer(d2);
var fps = args.Length > 3 ? args[3].Split(',').Select(int.Parse).ToArray() : null;
var tl = fps != null ? new Timeline(d2.FrameCount, fps[0], fps[1]) : null;
if (tl != null) Console.WriteLine($"timeline {tl.Count} frames {tl.Fps}fps interp={tl.Interp}");
using var bmp = new SKBitmap(1920, (int)r.BaseH);
using var c = new SKCanvas(bmp);
foreach (var s in args[2].Split(','))
{
    int f = int.Parse(s); sw.Restart();
    if (tl != null) r.Render(tl, f, c, 1920); else r.Render(f, c, 1920);
    c.Flush();
    Console.WriteLine($"render {f} {sw.ElapsedMilliseconds}ms");
    using var img = SKImage.FromBitmap(bmp); using var data = img.Encode(SKEncodedImageFormat.Png, 100);
    using var o = File.Create(Path.Combine(args[1], $"f{f}.png")); data.SaveTo(o);
}
