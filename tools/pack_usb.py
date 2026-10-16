#!/usr/bin/env python3
"""USB용 꾸러미: data_sakuga에서 영상·제외 클립·임시 파일을 뺀 결과만 zip 하나로 묶는다.

옮긴 PC에서는 저장소를 받고 zip을 저장소 폴더에 풀면(data_sakuga\\...) tools\\stage2_resume.ps1이
빠진 영상만 사쿠가부루에서 다시 받고(md5 확인) 이미 있는 샷·관절·motion 결과는 건너뛴다.
코드는 GitHub에 있으므로 넣지 않는다.

  .venv\\Scripts\\python tools\\pack_usb.py [data_sakuga] [--out E:\\aisfa_data.zip]
"""
import argparse
import zipfile
from pathlib import Path

SKIP_DIRS = {'excluded', 'excluded_western'}           # 기준에서 빠진 클립(영상 포함)
SKIP_SUFFIXES = {'.mp4', '.part', '.tmp'}               # 영상은 다시 받는다; 쓰다 만 파일은 버린다


def wanted(rel):
    return not (rel.parts and rel.parts[0] in SKIP_DIRS) and rel.suffix.lower() not in SKIP_SUFFIXES


def pack(data_dir, out):
    data_dir, out = Path(data_dir), Path(out)
    files = sorted(p for p in data_dir.rglob('*') if p.is_file() and wanted(p.relative_to(data_dir)))
    tmp = out.with_name(out.name + '.part')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, Path(data_dir.name, p.relative_to(data_dir)).as_posix())
    with zipfile.ZipFile(tmp) as z:                     # 다 썼는지 확인한 뒤에만 완성본 이름으로
        bad = z.testzip()
        if bad or len(z.namelist()) != len(files):
            raise RuntimeError(f'zip 검사 실패: {bad or "파일 수 불일치"}')
    tmp.replace(out)
    return len(files), out.stat().st_size


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('data_dir', nargs='?', default='data_sakuga')
    ap.add_argument('--out', default='aisfa_data.zip')
    a = ap.parse_args(argv)
    n, size = pack(a.data_dir, a.out)
    print(f'{n}개 파일, {size / 2**20:.1f} MB → {a.out}')
    print('옮긴 PC: 저장소 폴더에 풀고 powershell -ExecutionPolicy Bypass -File tools\\stage2_resume.ps1')


if __name__ == '__main__':
    main()
