"""레이어 이름 보존 앱 확인용 작은 시험 SFA(2026-11-04).

중간 표현 초안(docs/SFA-INTERMEDIATE-REPRESENTATION-DRAFT-2026-11-04.md)은 요소 라벨을 LayerDef Name에
담는 방안을 제안한다. 앱이 불러오기·편집·저장 뒤에도 이름을 보존하는지 실제 앱에서 확인하기 위한 파일을 만든다.
- 3장(24,24), 레이어 4개: 영문 점·슬래시 라벨, 한글 라벨, 긴 라벨, 기본 이름 대조군
- 레이어마다 객체 하나(ID는 장끼리 같고 레이어·종류도 같음), 점 ID는 장마다 새로
사용자 확인 전에는 '앱이 보존한다'고 기록하지 않는다.
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sfa  # noqa: E402

LAYERS = [
    ('0', 'background/sky'),
    ('1', 'effect.impact/01'),
    ('2', '이펙트_타격섬광_02'),
    ('3', 'Layer 4'),
]
# (객체ID, 레이어, 종류, 색, 점들) — 2=원(중심,가장자리), 1=직선
OBJECTS = [
    ('10', '0', '1', '-16776961', [(5, 80), (95, 80)]),
    ('20', '1', '1', '-65536', [(30, 30), (70, 50)]),
    ('30', '2', '2', '-16744448', [(50, 40), (50, 25)]),
    ('40', '3', '1', '-16777216', [(20, 60), (80, 60)]),
]


def build(frames=3):
    seq = ET.Element('Sequence', {'Name': 'layer_label_probe_v1', 'HeightWidthRatio': '0.5625', 'RatioX': '16', 'RatioY': '9',
                                  'FrameCount': str(frames), 'BackgroundColor': '-1'})
    pid = 1000
    for f in range(frames):
        fr = ET.SubElement(seq, 'Frame', {'BackgroundColor': '4294967295', 'ID': str(f + 1), 'Position': str(f)})
        for lid, name in LAYERS:
            ET.SubElement(fr, 'LayerDef', {'ID': lid, 'Name': name, 'Visible': 'true', 'Locked': 'false'})
        for order, (oid, lid, kind, color, pts) in enumerate(OBJECTS):
            ao = ET.SubElement(fr, 'AO', {'ID': oid, 'TypeId': kind, 'Color': color, 'LayerId': lid, 'DrawOrder': str(order + 1),
                                          'ThicknessScale': '1.0', 'ObjectScale': '1.0', 'GlowRadius': '0', 'GlowThickness': '0',
                                          'GlowColor': '4294967295', 'GlowAlpha': '0'})
            ids = []
            for i, (x, y) in enumerate(pts):
                pid += 1
                ids.append(pid)
                flags = ('5', '5')[i] if kind == '2' else ('9', '8')[i]   # 실제 수집 파일에서 가장 흔한 단독 직선/원 조합
                ET.SubElement(ao, 'AP', {'ID': str(pid), 'Flags': flags, 'Index': str(i),
                                         'X': str(x + 2 * f), 'Y': str(y)})
    return seq


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('out')
    a = p.parse_args()
    sfa.write_sfa(build(), a.out)
    print('저장', a.out)


if __name__ == '__main__':
    main()
