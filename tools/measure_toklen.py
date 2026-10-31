"""장마다 정답 문장 길이·단어 종류 측정(그림 없이). 사용: python measure_toklen.py 저장소경로 출력.json"""
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from multiprocessing import Pool

REPO = sys.argv[1]
sys.path.insert(0, os.path.join(REPO, 'tools'))
import sfa_tokens as K  # noqa: E402
import vec_data as V  # noqa: E402

KINDS = ('LINE', 'CIRC', 'CURVE')


def one(rel):
    try:
        z = zipfile.ZipFile(os.path.join(V.ROOT, rel))
        root = ET.fromstring(z.read(z.namelist()[0]))
    except Exception as e:
        return rel, None, str(type(e).__name__)
    rows = []
    for fr in root.findall('Frame'):
        t, _ = K.encode(root, fr)
        nobj = sum(1 for x in t if x in (K.TOK['LINE'], K.TOK['CIRC'], K.TOK['CURVE']))
        fc = Counter()
        try:
            for f in K.fields(t):
                fc[K.FIELDS[f]] += 1
            ok = True
        except ValueError:
            ok = False
        kc = Counter(K.SPECIAL[x] for x in t if x < K.OFF and K.SPECIAL[x] in KINDS)
        rows.append(dict(n=len(t), obj=nobj, ok=ok, f=dict(fc), k=dict(kc)))
    return rel, rows, ''


if __name__ == '__main__':
    train, hold = V.file_list(), V.file_list(only='holdout')
    jobs = [(r, 'train') for r in train] + [(r, 'holdout') for r in hold]
    split = dict(jobs)
    out = {}
    with Pool(4) as p:
        for i, (rel, rows, err) in enumerate(p.imap_unordered(one, [j[0] for j in jobs])):
            out[rel] = dict(split=split[rel], rows=rows, err=err)
            if i % 50 == 0:
                print(i, len(jobs), flush=True)
    json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False)
    print('끝', len(out), flush=True)
