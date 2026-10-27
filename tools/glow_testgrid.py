#!/usr/bin/env python3
"""렌더러 제약 시험표: 굵기·글로우두께·반경·알파·반투명 면을 격자로 늘어놓은 SFA 한 장 (2026-10-27).

GPT 계획(docs/GPT-FX-PLAN-2026-10-27.md) 1단계 '렌더러 제약 시험표'. 서버 렌더러(sfa_render.py)의 글로우 식
(띠 폭 = 8·굵기·글로우두께/10, 흐림 ≈ 반경)은 앱 셰이더를 정적 분석해 흉내 낸 것이라 앱 화면과 다를 수 있다.
사용자가 앱에서 이 파일을 열어 캡처/내보내기하면 칸마다 서버 렌더와 비교해 식을 보정한다.

검은 바탕, 블록마다 한 장(6장). 칸마다 가로 곡선 하나(2차 베지어, 살짝 휨).
  A 보이는 선(흰색) + 주황 글로우: 줄 = 굵기 0.1·0.3·1·3, 칸 = 글로우두께 10·50·100·300 (반경 20, 알파 255)
  B 안 보이는 선(색 알파 0) + 주황 글로우: A와 같은 격자
  C 안 보이는 선, 굵기 1·글로우두께 100: 칸 = 반경 0·5·20·50·100 (알파 255) / 줄 2 = 같은 반경, 굵기 0.3
  D 안 보이는 선, 굵기 1·두께 100·반경 20: 칸 = 글로우 알파 32·64·128·255 / 줄 2 = 글로우색 노랑·빨강·하늘·흰
  E 반투명 면: 알파 64·128·192·255 주황 사각형이 반씩 겹침 / 줄 2 = 알파 128 면 + 테두리 글로우(반경 20, 두께 100, 굵기 1)
  F 겹침: 같은 자리에 알파 64 흰 면 1·2·4·8겹
출력: <out>.sfa, <out>_server.png(서버 렌더 1920×1080), <out>_map.json(칸 → 설정)
사용: python tools/glow_testgrid.py <out 경로(확장자 없이)>
"""
import json
import os
import subprocess
import sys
import zipfile

W, H = 1920, 1080
ORANGE, YELLOW, RED, CYAN, WHITE = 0xFFFF8020, 0xFFFFE040, 0xFFFF2020, 0xFF40E0FF, 0xFFFFFFFF


class Writer:
    def __init__(self):
        self.oid, self.pid, self.out = 1, 1, []

    def curve(self, pts, color, ts, glow=(0, 0, 0xFFFFFFFF, 0), links=(None, None)):
        gr, gt, gc, ga = glow
        oid, p = self.oid, self.pid
        self.oid += 1
        self.pid += 3
        o = [f'<AO ID="{oid}" TypeId="3" Color="{color}" LayerId="0" DrawOrder="{oid}" ThicknessScale="{ts:.3f}" ObjectScale="1.0" '
             f'GlowRadius="{gr:.1f}" GlowThickness="{gt:.1f}" GlowColor="{gc}" GlowAlpha="{ga:.1f}">']
        for i, (x, y) in enumerate(pts):
            link = links[0] if i == 0 else links[1] if i == 2 else None
            ac = f'<AC ConnPtId="{link}"/>' if link else ""
            o.append(f'<AP ID="{p + i}" Flags="{8 if i == 0 else 9}" Index="{i}" X="{x / W * 100:.3f}" Y="{y / H * 100:.3f}">{ac}</AP>')
        self.out.append("".join(o) + "</AO>")
        return oid, p

    def rect_fill(self, x0, y0, x1, y1, col, glow=(0, 0, 0xFFFFFFFF, 0), ts=0.1):
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        base, fs = self.pid, []
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            links = (base + 3 * (i - 1) + 2 if i > 0 else None, base + 3 * (i + 1) if i < 3 else None)
            oid, p = self.curve([a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), b], 0, ts, glow, links)
            fs.append(f'<FS Kind="0" ObjId="{oid}" StartPtId="{p}" EndPtId="{p + 2}" StartT="0.0" EndT="1.0" Contour="0"/>')
        self.out.append(f'<FR Color="{col}">' + "".join(fs) + "</FR>")


def main():
    out = sys.argv[1]
    frames, cells = [], []  # 블록마다 한 장(1장에 모았더니 큰 글로우가 화면 전체를 덮었다)

    def frame():  # 오브젝트·점 번호는 장을 넘어 이어진다(겹치지 않게)
        w = Writer()
        if frames:
            w.oid, w.pid = frames[-1].oid, frames[-1].pid
        frames.append(w)
        return w

    def grid(wr, nr, nc, r, c, color, ts, glow, label, fi):
        cw, ch = W / nc, H / nr
        cx, cy = (c + 0.5) * cw, (r + 0.5) * ch
        L = min(cw * 0.45, 300)
        wr.curve([(cx - L / 2, cy), (cx, cy - ch * 0.12), (cx + L / 2, cy)], color, ts, glow)
        cells.append(dict(label, 장=fi + 1, x=round(cx), y=round(cy)))

    tss, gts = [0.1, 0.3, 1.0, 3.0], [10, 30, 100]
    for vis in (True, False):  # 1장 A 보이는 선, 2장 B 안 보이는 선
        wr = frame()
        for r, ts in enumerate(tss):
            for c, gt in enumerate(gts):
                grid(wr, 4, 3, r, c, WHITE if vis else 0, ts, (10, gt, ORANGE, 255),
                     dict(block="A" if vis else "B", 굵기=ts, 글로우두께=gt, 반경=10, 알파=255, 선="보임" if vis else "안 보임"), len(frames) - 1)
    wr = frame()  # 3장 C 반경
    for c, gr in enumerate([0, 5, 20, 50, 100]):
        for r, ts in enumerate([1.0, 0.3]):
            grid(wr, 2, 5, r, c, 0, ts, (gr, 100, ORANGE, 255), dict(block="C", 굵기=ts, 글로우두께=100, 반경=gr, 알파=255), 2)
    wr = frame()  # 4장 D 알파·색
    for c, ga in enumerate([32, 64, 128, 255]):
        grid(wr, 2, 4, 0, c, 0, 1.0, (20, 100, ORANGE, ga), dict(block="D", 굵기=1.0, 글로우두께=100, 반경=20, 알파=ga, 색="주황"), 3)
    for c, (gc, nm) in enumerate(((YELLOW, "노랑"), (RED, "빨강"), (CYAN, "하늘"), (WHITE, "흰"))):
        grid(wr, 2, 4, 1, c, 0, 1.0, (20, 100, gc, 255), dict(block="D", 굵기=1.0, 글로우두께=100, 반경=20, 알파=255, 색=nm), 3)
    wr = frame()  # 5장 E 반투명 면 + 테두리 글로우
    for c, a in enumerate([64, 128, 192, 255]):
        x0 = 160 + c * 300
        wr.rect_fill(x0, 120, x0 + 420, 420, (a << 24) | 0xFF8020)
        cells.append(dict(block="E", 장=5, 면알파=a, x=round(x0 + 210), y=270))
    for c, (gt, ts) in enumerate(((30, 1.0), (100, 1.0), (100, 0.3))):
        x0 = 140 + c * 600
        wr.rect_fill(x0, 640, x0 + 400, 900, (128 << 24) | 0xFF8020, glow=(20, gt, ORANGE, 255), ts=ts)
        cells.append(dict(block="E", 장=5, 면알파=128, 테두리글로우=f"반경 20·두께 {gt}·굵기 {ts}", x=round(x0 + 200), y=770))
    wr = frame()  # 6장 F 흰 면 겹침 + 아주 큰 글로우 하나
    for c, n in enumerate([1, 2, 4, 8]):
        x0 = 120 + c * 230
        for _ in range(n):
            wr.rect_fill(x0, 200, x0 + 170, 600, (64 << 24) | 0xFFFFFF)
        cells.append(dict(block="F", 장=6, 흰면알파=64, 겹=n, x=round(x0 + 85), y=400))
    wr.curve([(1300, 540), (1500, 480), (1700, 540)], 0, 1.0, (40, 300, ORANGE, 255))
    cells.append(dict(block="F", 장=6, 굵기=1.0, 글로우두께=300, 반경=40, 알파=255, 설명="'배' 파일급 큰 글로우", x=1500, y=530))
    body = [f'<Frame BackgroundColor="4278190080" ID="{fi + 1}" Position="{fi}">'
            '<LayerDef ID="0" Name="시험표" Visible="true" Locked="false"/>\n' + "\n".join(wr.out) + "\n</Frame>" for fi, wr in enumerate(frames)]
    oid = frames[-1].oid
    name = os.path.basename(out)
    xml = (f"<?xml version='1.0' encoding='utf-8'?>\n<Sequence Name=\"{name}\" HeightWidthRatio=\"0.5625\" RatioX=\"16\" RatioY=\"9\" "
           f"FrameCount=\"{len(frames)}\" BackgroundColor=\"4278190080\">\n" + "\n".join(body) + "\n</Sequence>\n")
    with zipfile.ZipFile(out + ".sfa", "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name + ".xml", xml)
    json.dump(cells, open(out + "_map.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tmp = out + "_r"
    os.makedirs(tmp, exist_ok=True)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfa_render.py"), out + ".sfa", tmp,
                    "--frames", ",".join(str(i) for i in range(len(frames))), "--size", f"{W}x{H}"], check=True, capture_output=True)
    print("장", len(frames), "AO", oid - 1, "칸", len(cells), "렌더", sorted(os.listdir(tmp)))


if __name__ == "__main__":
    main()
