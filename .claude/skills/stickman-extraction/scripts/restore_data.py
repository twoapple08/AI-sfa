"""내려받은 인계 파일을 SHA256으로 확인해 스킬의 비공개 자료 위치에 복원한다.

네트워크 접속, 인증 정보 읽기, 코드 실행, 학습을 하지 않는다.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile


SKILL = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('허용하지 않는 상대 경로: ' + name)
    return Path(*path.parts)


def target(root, name):
    root = Path(root).resolve()
    path = root / relative(name)
    if not path.resolve().is_relative_to(root):
        raise ValueError('복원 위치 밖을 가리키는 경로: ' + name)
    return path


def inventory(manifest, root):
    rows = []
    for item in manifest['artifacts']:
        path = target(root, item['local_path'])
        state = 'missing'
        if path.is_file():
            state = 'verified' if path.stat().st_size == item['bytes'] and digest(path) == item['sha256'] else 'mismatch'
        rows.append(dict(id=item['id'], state=state, required=item.get('required', False),
                         path=str(path), drive_id=item.get('drive_id')))
    return rows


def import_files(manifest, root, inputs):
    by_size = {}
    for entry in inputs:
        path = Path(entry)
        if not path.exists():
            raise ValueError('내려받은 파일/폴더가 없다: ' + str(path))
        candidates = path.rglob('*') if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_file() and not candidate.is_symlink():
                by_size.setdefault(candidate.stat().st_size, []).append(candidate)
    copied = []
    for item in manifest['artifacts']:
        destination = target(root, item['local_path'])
        if destination.exists():
            if destination.is_file() and digest(destination) == item['sha256']:
                continue
            raise ValueError('기존 파일이 달라 덮어쓰지 않는다: ' + str(destination))
        for candidate in by_size.get(item['bytes'], []):
            if digest(candidate) != item['sha256']:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with candidate.open('rb') as source, destination.open('xb') as output:
                shutil.copyfileobj(source, output)
            if digest(destination) != item['sha256']:
                destination.unlink()
                raise ValueError('복사 뒤 지문 불일치')
            copied.append(item['id'])
            break
    return copied


def extract_verified_zip(archive, expected_sha, destination):
    """전체 경로를 사전 검증하고 새 폴더로만 추출한다. 묶음 속 코드는 실행 안 함."""
    archive, destination = Path(archive), Path(destination).resolve()
    if digest(archive) != expected_sha:
        raise ValueError('묶음 지문 불일치')
    if destination.exists():
        raise ValueError('새 추출 폴더가 필요하다')
    with zipfile.ZipFile(archive) as bundle:
        seen = set()
        for item in bundle.infolist():
            path = relative(item.filename.rstrip('/'))
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or path in seen:
                raise ValueError('링크 또는 중복 ZIP 경로')
            seen.add(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix='.인계복원-', dir=destination.parent))
        try:
            bundle.extractall(temporary)
            temporary.rename(destination)
        except BaseException:
            shutil.rmtree(temporary)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=SKILL/'data/artifact_manifest.json')
    parser.add_argument('--root', type=Path, default=SKILL/'private-data')
    parser.add_argument('--import-path', action='append', default=[])
    parser.add_argument('--extract-replay', type=Path)
    parser.add_argument('--expand-cache', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    copied = import_files(manifest, args.root, args.import_path) if args.import_path else []
    for item_id, destination in [('latest_replay', args.extract_replay), ('working_cache', args.expand_cache)]:
        if destination:
            item = next(x for x in manifest['artifacts'] if x['id'] == item_id)
            extract_verified_zip(target(args.root, item['local_path']), item['sha256'], destination)
    rows = inventory(manifest, args.root)
    ready = all(x['state'] == 'verified' for x in rows if x['required'])
    print(json.dumps(dict(required_ready=ready, copied=copied, artifacts=rows), ensure_ascii=False, indent=2))
    return 0 if ready else 2


if __name__ == '__main__':
    raise SystemExit(main())
