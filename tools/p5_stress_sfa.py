"""P5 SFA 출력 시험: 생성기가 쓸 규모·표현을 앱이 받아들이는지 보는 시험 SFA를 만든다(앱 확인 전, 추정 형식 포함).

사용: python tools/p5_stress_sfa.py [출력 폴더(기본 examples/p5)]
확인 대상(지금까지 앱에서 본 것은 도형 수 개·직선 경계 삼각형 채우기뿐 — docs/APP-VERIFICATION.md):
- 곡선(TypeId 3) 여러 개를 AC로 이은 닫힌 경계의 채우기(FS Kind 0, StartT 0 → EndT 1). 곡선 경계 채우기는 AOT 경로
  (quadraticBezierTo)로만 추정했고 앱 출력은 미확인.
- 반투명 채우기 여러 겹(바깥 넓고 옅게 → 안쪽 좁고 진하게, AGENTS.md 이펙트 원칙), 검은 바탕.
- 한 프레임 도형 수: a = 약 600개, b = 약 2,500개(반투명 짧은 곡선 획 다수).
- 48프레임 동안 폭발 모양이 커지고 옅어진다(같은 AO ID를 프레임마다 유지, 점 ID는 시퀀스 전체에서 고유).
도형은 수식으로 만든 단순 시험 모양이다(다른 작가 그림에서 딴 형태 아님).
"""
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sfa  # noqa: E402
from build_feature_probes import argb  # noqa: E402

N = 48
CX, CY = 50.0, 50.0  # 화면 가운데(가로·세로 모두 0~100 정규화; x에 9/16을 곱해 원이 둥글게)
RATIO = 9 / 16


def curve(oid, pts, color, apid, layer=0, thick=1.0):
    o = ET.Element("AO", {"ID": str(oid), "TypeId": "3", "Color": color, "LayerId": str(layer),
                          "DrawOrder": str(oid), "ThicknessScale": str(thick), "ObjectScale": "1.0",
                          "GlowRadius": "0", "GlowThickness": "20", "GlowColor": "4294967295", "GlowAlpha": "0"})
    aps = []
    for i, (x, y) in enumerate(pts):
        aps.append(ET.SubElement(o, "AP", {"ID": str(apid + i), "Flags": "3" if i == 0 else "9", "Index": str(i),
                                           "X": f"{x:.3f}", "Y": f"{y:.3f}"}))
    return o, aps


def burst_contour(k, r_out, r_in, phase):
    """뾰족한 섬광 윤곽: 바깥 꼭짓점과 안쪽 골을 잇는 이차 곡선 2k개. 제어점을 안쪽으로 당겨 오목한 변·날카로운 가시를 만든다.
    가시 길이는 꼭짓점마다 다르게(1, 0.7, 0.85 …) 해 규칙적인 꽃 모양을 피한다."""
    segs = []
    for i in range(2 * k):
        a0 = phase + math.pi * i / k
        a1 = phase + math.pi * (i + 1) / k
        spike = lambda j: r_out * (1.0, 0.7, 0.85, 0.6, 0.95)[(j // 2) % 5]  # noqa: E731
        r0 = spike(i) if i % 2 == 0 else r_in
        r1 = r_in if i % 2 == 0 else spike(i + 1)
        am = (a0 + a1) / 2
        rm = (r0 + r1) / 2 * 0.62
        p = lambda r, a: (CX + r * math.cos(a) * RATIO, CY + r * math.sin(a))  # noqa: E731
        segs.append([p(r0, a0), p(rm, am), p(r1, a1)])
    return segs


def frame(idx, n_strokes):
    t = idx / (N - 1)
    fr = ET.Element("Frame", {"BackgroundColor": argb(255, 0, 0, 0), "ID": str(500000 + idx), "Position": str(idx)})
    ET.SubElement(fr, "LayerDef", {"ID": "0", "Name": "배경획", "Visible": "true", "Locked": "false"})
    ET.SubElement(fr, "LayerDef", {"ID": "1", "Name": "명암", "Visible": "true", "Locked": "false"})
    ET.SubElement(fr, "LayerDef", {"ID": "2", "Name": "선", "Visible": "true", "Locked": "false"})
    apid = 10_000_000 + idx * 10_000
    oid = 1
    grow = 0.35 + 0.65 * math.sin(math.pi / 2 * t)
    fade = 1.0 - 0.7 * t
    # 1) 반투명 짧은 곡선 획(배경 번짐): 방사형, 바깥 옅게
    rng = __import__("random").Random(7)
    for s in range(n_strokes):
        a = rng.uniform(0, math.tau)
        r0 = rng.uniform(6, 50) * grow
        L = rng.uniform(1.5, 6)
        bend = rng.uniform(-0.15, 0.15)
        pts = [(CX + r0 * math.cos(a) * RATIO, CY + r0 * math.sin(a)),
               (CX + (r0 + L / 2) * math.cos(a + bend) * RATIO, CY + (r0 + L / 2) * math.sin(a + bend)),
               (CX + (r0 + L) * math.cos(a) * RATIO, CY + (r0 + L) * math.sin(a))]
        al = int(max(10, min(160, 160 * (1 - r0 / 55) * fade)))
        o, _ = curve(oid, pts, argb(al, 255, 200 + (s % 40), 120), apid, 0, 0.6)
        fr.append(o)
        oid += 1
        apid += 3
    # 2) 반투명 채우기 6겹(바깥 넓고 옅게 → 안쪽 좁고 진하게) + 3) 가장 바깥 겹만 선
    layers = [(1.00, 40, (255, 90, 20)), (0.85, 60, (255, 130, 30)), (0.70, 90, (255, 170, 50)),
              (0.55, 120, (255, 210, 90)), (0.40, 170, (255, 240, 160)), (0.25, 230, (255, 255, 235))]
    k = 16
    for li, (sc, al, (r, g, b)) in enumerate(layers):
        segs = burst_contour(k, 45 * sc * grow, 12 * sc * grow, 0.6 * t)
        is_line = li == 0
        objs = []
        for sg in segs:
            o, aps = curve(oid, sg, argb(int(255 * fade), 255, 120, 40) if is_line else argb(0, 0, 0, 0), apid,
                           2 if is_line else 1, 1.4 if is_line else 0.01)
            objs.append((o, aps))
            fr.append(o)
            oid += 1
            apid += 3
        for i in range(len(objs)):  # 닫힌 경계: 각 곡선 끝점과 다음 곡선 시작점을 서로 잇는다
            end, start = objs[i][1][-1], objs[(i + 1) % len(objs)][1][0]
            ET.SubElement(end, "AC", {"ConnPtId": start.get("ID")})
            ET.SubElement(start, "AC", {"ConnPtId": end.get("ID")})
        fill = ET.SubElement(fr, "FR", {"Color": argb(int(al * fade), r, g, b)})
        for o, aps in objs:
            ET.SubElement(fill, "FS", {"Kind": "0", "ObjId": o.get("ID"), "StartPtId": aps[0].get("ID"),
                                       "EndPtId": aps[-1].get("ID"), "StartT": "0.0", "EndT": "1.0"})
    return fr


def build(out, name, n_strokes):
    seq = ET.Element("Sequence", {"Name": name, "HeightWidthRatio": "0.5625", "RatioX": "16", "RatioY": "9",
                                  "FrameCount": str(N), "BackgroundColor": argb(255, 0, 0, 0)})
    for i in range(N):
        seq.append(frame(i, n_strokes))
    sfa.write_sfa(seq, out / f"{name}.sfa")
    f0 = seq.find("Frame")
    return {"name": name, "frames": N, "AO_per_frame": len(f0.findall("AO")), "FR_per_frame": len(f0.findall("FR")),
            "bytes": (out / f"{name}.sfa").stat().st_size}


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "examples/p5")
    out.mkdir(parents=True, exist_ok=True)
    for name, n in (("p5_a_600", 400), ("p5_b_2500", 2300)):
        print(build(out, name, n))


if __name__ == "__main__":
    main()
