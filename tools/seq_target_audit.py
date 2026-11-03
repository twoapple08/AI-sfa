"""원본 길이·기능과 실제 출제 정답의 종료 비중을 CPU로 점검한다. 학습하지 않는다."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import numpy as np

import sfa_tokens as K
import vec_data as V
from seq_objective import metadata


def features(tokens):
    result = ['all']
    for name, token in [('curve', 'CURVE'), ('fill', 'FILL'), ('glow', 'GLOW'), ('layer_opacity', 'LOPAC')]:
        if K.TOK[token] in tokens:
            result.append(name)
    # 정답은 BOS BG A R G B로 시작한다. 의미상 배경/이펙트의 작가 판정과는 구분한다.
    if tokens[2:6] != [K.n(255)]*4:
        result.append('nonwhite_background')
    return result


def audit_sources(maxlen=2048):
    counts = defaultdict(lambda: dict(total=0, fits=0, over_length=0, samples=[], over_samples=[]))
    errors, lengths = [], []
    files = V.file_list()
    for number, rel in enumerate(files):
        try:
            with zipfile.ZipFile(Path(V.ROOT)/rel) as archive:
                root = ET.fromstring(archive.read(archive.namelist()[0]))
            for frame in root.findall('Frame'):
                tokens, _ = K.encode(root, frame)
                lengths.append(len(tokens))
                for kind in features(tokens):
                    row = counts[kind]
                    row['total'] += 1
                    fits = len(tokens) <= maxlen
                    row['fits' if fits else 'over_length'] += 1
                    samples = row['samples' if fits else 'over_samples']
                    if len(samples) < 3:
                        samples.append(dict(file=rel, position=int(frame.get('Position', 0)), tokens=len(tokens)))
        except Exception as exc:
            errors.append(dict(file=rel, error=f'{type(exc).__name__}: {exc}'))
        if (number+1) % 50 == 0:
            print(f'원본 {number+1}/{len(files)}파일 점검', flush=True)
    return dict(scope='학습용 원본의 길이/기능 통계. 큰 실제 장은 real_crop 부분 문제로 사용될 수 있으므로 학습 누락률이 아니다. 실제 조합·증강 npz의 노출 분포와 구분한다.',
                files=len(files), maxlen=maxlen, counts=dict(counts), errors=errors,
                token_length_quantiles=np.quantile(lengths, [0, .5, .9, .99, 1]).tolist() if lengths else [])


def audit_npz(path):
    with np.load(path, allow_pickle=False) as archive:
        tokens, offsets = archive['tok'], archive['off']
        rows, kinds = [], defaultdict(int)
        for begin, end in zip(offsets[:-1], offsets[1:]):
            target = tuple(map(int, tokens[begin:end]))
            stops, first, fields = metadata(target)
            if list(fields) != K.fields(target):
                raise ValueError('문법 칸 번호가 다르다')
            for kind in features(list(target)):
                kinds[kind] += 1
            rows.append(dict(tokens=len(target), eos_count=target.count(K.TOK['EOS']),
                             token_mean_eos_fraction=1/(len(target)-1), legal_continue_positions=sum(not s[-1] for s in stops)))
    return dict(scope='지정 npz 전체 정답. 학습 목록인지 판정 목록인지 호출자가 구분해야 한다.', sequences=len(rows),
                eos_positive=sum(r['eos_count'] for r in rows), legal_continue_positions=sum(r['legal_continue_positions'] for r in rows),
                eos_fraction_median=float(np.median([r['token_mean_eos_fraction'] for r in rows])),
                strict_grammar_and_fields_ok=True, feature_counts=dict(kinds))


def audit_folder(folder):
    paths = sorted(Path(folder).glob('*.npz'))
    if not paths:
        raise ValueError('감사할 출제 npz가 없다')
    reports = {p.name: audit_npz(p) for p in paths}
    return dict(scope='지정 폴더에 실제로 있는 출제 npz만 감사한다. 일부 내려받은 파일이면 전체 출제 분포가 아니다.',
                files=len(paths), sequences=sum(r['sequences'] for r in reports.values()), reports=reports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--maxlen', type=int, default=2048)
    parser.add_argument('--npz')
    parser.add_argument('--folder')
    parser.add_argument('--sources', action='store_true')
    args = parser.parse_args()
    if not args.npz and not args.sources and not args.folder:
        parser.error('--npz·--folder·--sources 중 하나가 필요하다')
    result = {}
    if args.npz:
        result['npz'] = audit_npz(args.npz)
    if args.sources:
        result['sources'] = audit_sources(args.maxlen)
    if args.folder:
        result['problems'] = audit_folder(args.folder)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('정답/길이 감사 저장 완료', flush=True)


if __name__ == '__main__':
    main()
