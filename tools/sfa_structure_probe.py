#!/usr/bin/env python3
"""SFA 구조/어휘 조사용 CPU 반례. 합성 곡선과 합성 XML만 사용한다.

기존 변환기·기본 생성 경로·사용자 파일을 변경하지 않는다.
실행: python tools/sfa_structure_probe.py --out data/research/sfa_structure_probe_2026-11-06.json
필요: numpy, fonttools. 측정 오차는 동일 매개변수에서 표본화한 오차이며 앱/픽셀 검증이 아니다.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def legacy_converter():
    """추적기 의존성 없이 현재 저장소의 실제 두 함수만 읽어 비교한다."""
    path = ROOT / 'tools/potrace_lines.py'
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name in ('pt', 'cubic_to_quads')]
    if len(selected) != 2:
        raise RuntimeError('기존 비교 함수 구성이 달라졌다')
    ns = {'np': np}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), ns)
    return ns['cubic_to_quads'], hashlib.sha256(source.encode()).hexdigest()


def explicit_quads(spline):
    """폰트 spline의 암시적 가운데 끝점을 실제 2차 조각으로 펼친다."""
    points = np.asarray(spline, dtype=float)
    controls = points[1:-1]
    start, out = points[0], []
    for i, control in enumerate(controls):
        end = (control + controls[i + 1]) / 2 if i + 1 < len(controls) else points[-1]
        out.append(np.stack([start, control, end]))
        start = end
    return out


def cubic_samples(curve, ts):
    p = np.asarray(curve, dtype=float)
    t = ts[:, None]
    return (1-t)**3*p[0] + 3*(1-t)**2*t*p[1] + 3*(1-t)*t*t*p[2] + t**3*p[3]


def sampled_error(curve, quads, samples=4001):
    ts = np.linspace(0, 1, samples)
    seg = np.minimum((ts * len(quads)).astype(int), len(quads) - 1)
    u = (ts * len(quads) - seg)[:, None]
    q = np.asarray(quads)[seg]
    approx = (1-u)**2*q[:, 0] + 2*(1-u)*u*q[:, 1] + u**2*q[:, 2]
    return float(np.linalg.norm(cubic_samples(curve, ts) - approx, axis=1).max())


def connected(quads):
    return all(np.linalg.norm(a[2] - b[0]) < 1e-10 for a, b in zip(quads, quads[1:]))


def words_probe():
    import sfa_tokens as K
    root = ET.Element('Sequence', FrameCount='1', RatioX='16', RatioY='9',
                      HeightWidthRatio='0.5625', BackgroundColor='-1')
    frame = ET.SubElement(root, 'Frame', ID='1', Position='0', BackgroundColor='-1')
    ET.SubElement(frame, 'LayerDef', ID='0', Name='합성 시험', Visible='true', Locked='false')
    for oid, points in [(1, [(1, 3, 10, 10), (2, 33, 50, 50)]),
                        (2, [(3, 8, 50, 50), (4, 9, 90, 10)])]:
        obj = ET.SubElement(frame, 'AO', ID=str(oid), TypeId='1', LayerId='0',
                            Color='-16777216', ThicknessScale='1', ObjectScale='1',
                            DrawOrder=str(oid), GlowRadius='0', GlowThickness='0',
                            GlowAlpha='0', GlowColor='4294967295')
        for index, (pid, flags, x, y) in enumerate(points):
            point = ET.SubElement(obj, 'AP', ID=str(pid), Flags=str(flags),
                                  Index=str(index), X=str(x), Y=str(y))
            if pid in (2, 3):
                ET.SubElement(point, 'AC', ConnPtId='3' if pid == 2 else '2')
    tokens, _ = K.encode(root, frame)
    restored = K.decode(tokens)
    if isinstance(restored, tuple):
        raise RuntimeError('decode 반환 형식이 달라졌다')
    count = lambda fr: sum((int(p.get('Flags')) & 0x2f) == 0x21 for p in fr.iter('AP'))
    before, after = count(frame), count(restored)
    assert len(frame.findall('AO')) == len(restored.findall('AO')) == 2
    assert len(list(frame.iter('AP'))) == len(list(restored.iter('AP'))) == 4
    before_xy = sorted((float(p.get('X')), float(p.get('Y'))) for p in frame.iter('AP'))
    after_xy = sorted((float(p.get('X')), float(p.get('Y'))) for p in restored.iter('AP'))
    assert np.allclose(before_xy, after_xy)
    assert len(list(frame.iter('AC'))) == len(list(restored.iter('AC'))) == 2
    assert before == 1 and after == 0
    return dict(input_orange_role_points=before, output_orange_role_points=after,
                tokens=len(tokens), input_objects=2, output_objects=2,
                input_points=4, output_points=4, same_coordinate_multiset=True,
                input_connections=2, output_connections=2,
                meaning='현재 한 장 렌더용 어휘는 Flags의 편집 역할을 보존하지 않는다. 설계 범위의 반례이며 새 앱 시험이 아니다.')


def run():
    import fontTools
    from fontTools.cu2qu import curve_to_quadratic, curves_to_quadratic

    curves = {
        'arch': [(0, 0), (0, 100), (100, 100), (100, 0)],
        's_curve': [(0, 0), (35, 150), (65, -150), (100, 0)],
        'loop': [(0, 0), (160, 180), (-60, 180), (100, 0)],
        'near_line': [(0, 0), (30, 1), (70, -1), (100, 0)],
        'elevated_quadratic': [(0, 0), (100/3, 200/3), (200/3, 200/3), (100, 0)],
        'point': [(10, 10)] * 4,
    }
    tolerance = 0.1
    legacy, source_sha = legacy_converter()
    rows = []
    for name, curve in curves.items():
        old = [np.asarray(q).reshape(3, 2) for q in legacy(*curve)]
        new = explicit_quads(curve_to_quadratic(curve, tolerance, all_quadratic=True))
        error = sampled_error(curve, new)
        assert connected(new) and np.allclose(new[0][0], curve[0]) and np.allclose(new[-1][2], curve[-1])
        assert error <= tolerance + 1e-8
        rows.append(dict(name=name, legacy_segments=len(old),
                         legacy_sampled_max_error=round(sampled_error(curve, old), 8),
                         adaptive_segments=len(new), adaptive_sampled_max_error=round(error, 8)))
    pair = [curves['arch'], curves['loop']]
    individual = [len(curve_to_quadratic(c, tolerance)) - 2 for c in pair]
    joint = curves_to_quadratic(pair, [tolerance] * 2, all_quadratic=True)
    counts = [len(q) - 2 for q in joint]
    assert len(set(counts)) == 1
    return dict(schema='sfa-structure-probe/1', date='2026-11-06', synthetic_only=True,
                fonttools_version=fontTools.__version__,
                legacy_source='tools/potrace_lines.py', legacy_source_sha256=source_sha,
                tolerance=tolerance, units='합성 곡선의 좌표 단위; 앱 픽셀/화면 백분율이 아님',
                metric='각 2차 조각을 같은 길이의 t 구간으로 놓고 원래 3차와 같은 t에서 4001개 표본 비교',
                rows=rows, compatible_pair=dict(individual_segments=individual, joint_segments=counts),
                vocabulary=words_probe(),
                limits=['수치 표본 검사이며 연속 전 구간의 독립 오차 증명은 아님',
                        '곡선 수 통일은 신체 의미·FR 구간·점 역할·장간 객체 대응을 자동 복원하지 않음',
                        '실제 앱·실제 원본·학습 품질 검증 아님; 기본 코드 변경 없음'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = run()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
