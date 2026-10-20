using System;

namespace SfaCore
{
    /// <summary>
    /// 원래 앱의 내보내기 시간축(docs/NATIVE-TWEEN-FINDINGS.md, native_timing.py, 안드로이드 Timeline.kt). (T, P) = (트위닝 fps, 재생 fps).
    /// T &gt; P이면 보간: 출력 fps T, 출력 개수 round(N×T/P), 출력 j의 원본 위치 j×P/T. 아니면 원본을 P fps로.
    /// SFA 파일에는 이 값이 저장되지 않아 사용자가 정한다.
    /// </summary>
    public sealed class Timeline
    {
        public readonly int Src, Tween, Play, Fps, Count;
        public readonly bool Interp;
        public Timeline(int src, int tween, int play)
        {
            Src = src; Tween = tween; Play = play; Interp = tween > play;
            Fps = Interp ? tween : play;
            Count = Interp ? Math.Max(1, (int)((2L * src * tween + play) / (2L * play))) : src;
        }
        /// <summary>캐시 폴더 이름에 붙인다. 보간하지 않으면 재생 fps와 관계없이 같은 그림이다.</summary>
        public string Key => Interp ? $"t{Tween}p{Play}" : "src";
        public int A(int j) => !Interp ? j : (int)Math.Min((long)j * Play / Tween, Src - 1);
        public int B(int j) => Math.Min(A(j) + 1, Src - 1);
        public float T(int j) => !Interp || A(j) == B(j) ? 0f : (float)((long)j * Play % Tween) / Tween;
    }
}
