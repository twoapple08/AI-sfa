"""고정 코드·자료·가중치로 비공개 Kaggle 비교 작업을 준비/실행한다. 기존 학습 커널은 덮지 않는다."""
import argparse
import inspect
import json
from pathlib import Path

import kaggle_seq_remote as remote


def worker(config):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys
    import time
    import traceback
    started = time.time()
    work = Path('/kaggle/working')
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'skia-python'], check=True)
        repo = Path('/kaggle/tmp/AI-sfa-refine')
        subprocess.run(['git', 'clone', '--quiet', '--depth', '1', '--single-branch', '--branch', config['branch'],
                        'https://github.com/twoapple08/AI-sfa', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'fetch', '--quiet', '--depth', '1', 'origin', config['commit']], check=True)
        subprocess.run(['git', '-C', str(repo), 'checkout', '--quiet', '--detach', config['commit']], check=True)
        got = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if got != config['commit']:
            raise RuntimeError('실행 코드 커밋 불일치')
        infos = list(Path('/kaggle/input').rglob('data_info.json'))
        matching = [(p, json.loads(p.read_text())) for p in infos if json.loads(p.read_text()).get('commit') == config['data_commit']]
        if len(matching) != 1:
            raise RuntimeError('기존 출제 자료 커밋을 하나로 식별하지 못함')
        info_path, info = matching[0]
        for name, expected in info['code'].items():
            if hashlib.sha256((repo/'tools'/name).read_bytes()).hexdigest()[:16] != expected:
                raise RuntimeError('출제 코드/미리 만든 자료 불일치: '+name)
        data_root = info_path.parent
        for split in ('sd', 'sv'):
            done = json.loads((data_root/split/'done.json').read_text())
            if done['version'] != 10 or done['maxlen'] != 2048:
                raise RuntimeError('출제 자료 판/문맥 불일치')
        parent = None
        for path in Path('/kaggle/input').rglob('best.pt'):
            with path.open('rb') as fh:
                sha = hashlib.file_digest(fh, 'sha256').hexdigest()
            if sha == config['parent_sha256']:
                if parent is not None:
                    raise RuntimeError('같은 입력 가중치가 여러 개라 식별 불가')
                parent = path
        if parent is None:
            raise RuntimeError('승인된2회차 best.pt 해시를 찾지 못함')
        (work/'pinned_inputs.json').write_text(json.dumps(dict(config, data_root=str(data_root), parent=str(parent)), ensure_ascii=False, indent=2))
        command = [sys.executable, '-u', str(repo/'tools/seq_refine.py'), str(parent), str(data_root/'sd'), str(data_root/'sv'),
                   str(work/'comparison'), '--profile', str(repo/'profiles/seq_refinement_balanced_v1.json'), '--run-gpu']
        with (work/'refinement_console.txt').open('w') as console:
            result = subprocess.run(command, stdout=console, stderr=subprocess.STDOUT, timeout=75*60)
        rc = result.returncode
        status = dict(config, rc=rc, wall_seconds=time.time()-started)
    except Exception as exc:
        status = dict(config, rc=1, wall_seconds=time.time()-started, error=f'{type(exc).__name__}: {exc}', traceback=traceback.format_exc())
    (work/'refinement_run.json').write_text(json.dumps(status, ensure_ascii=False, indent=2))
    print('비교 작업 종료', status['rc'], flush=True)
    if status['rc']:
        raise SystemExit(status.get('error', '학습/진단 실패: refinement_console.txt 확인'))


def prepare_kernel(out, commit, parent_sha256, data_commit, account):
    if not all(len(v) == n and all(c in '0123456789abcdef' for c in v) for v, n in ((commit, 40), (data_commit, 40), (parent_sha256, 64))):
        raise ValueError('코드/자료 커밋과 입력 가중치 해시는 전체 길이가 필요하다')
    config = dict(branch='claude/new-session-gknz4t', commit=commit, data_commit=data_commit, parent_sha256=parent_sha256,
                  experiment=True, official=False, stages='기본640폭·기존 출제 자료 유지', maximum_training_minutes=40)
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    source = inspect.getsource(worker)+'\nworker('+repr(config)+')\n'
    compile(source, 'kernel.py', 'exec')
    (output/'kernel.py').write_text(source, encoding='utf-8')
    meta = remote.kernel_meta(account, 'aisfa-seq-refine-ab-v1', True)
    meta.update(machine_shape='NvidiaTeslaT4', dataset_sources=[f'{account}/{remote.CKPT}'], kernel_sources=[f'{account}/{remote.DATA_KERNEL}'])
    (output/'kernel-metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--parent-sha256', required=True)
    parser.add_argument('--data-commit', required=True)
    parser.add_argument('--push', action='store_true')
    parser.add_argument('--gpu-ok', action='store_true', help='사용자 GPU 실행 지시가 있는 경우에만 지정')
    args = parser.parse_args()
    if args.push and not args.gpu_ok:
        parser.error('GPU 실행 지시가 필요하다. 준비만 하려면 --push를 생략한다')
    meta = prepare_kernel(args.out, args.commit, args.parent_sha256, args.data_commit, remote.user())
    print('비공개 비교 작업 준비', meta['id'])
    if args.push:
        result = remote.kg('kernels', 'push', '-p', args.out)
        if 'successfully pushed' not in result.lower():
            raise SystemExit('Kaggle 실행 요청 실패: '+result[-700:])
        print(result.strip())


if __name__ == '__main__':
    main()
