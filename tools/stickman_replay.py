"""보존한 입력·코드 지문으로 기존 구간을 독립 폴더에서 재생성하고 XML을 대조한다."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
import zipfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xml_sha(path):
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.endswith('.xml')]
        if len(names)!=1:raise ValueError('SFA의 XML은 하나여야 한다')
        return hashlib.sha256(z.read(names[0])).hexdigest()


def safe_relative(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('재현 묶음 경로 오류')
    return p


def replay(bundle,destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('기존 폴더를 덮지 않는다. 새 재현 폴더가 필요하다')
    repo=Path(__file__).resolve().parents[1]
    with zipfile.ZipFile(bundle) as z:
        for name in z.namelist():safe_relative(name)
        manifest=json.loads(z.read('manifest.json'))
        spec=manifest['replay']
        locked=[]
        for decision in spec.get('locked_decisions',[]):
            name=decision['path'];safe_relative(name)
            expected=manifest['files'].get(name)
            if not decision.get('kind') or expected is None or expected!=decision['sha256']:
                raise ValueError('수동 보정/추론 입력 고정 기록 불일치: '+name)
            locked.append((name,decision['kind'],expected))
        for name,digest in spec['code_sha256'].items():
            safe_relative(name)
            if sha(repo/name)!=digest:raise ValueError('재현 코드 지문 불일치: '+name)
        for name,digest in manifest['files'].items():
            safe_relative(name)
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('입력 지문 불일치: '+name)
        destination.mkdir(parents=True)
        z.extractall(destination)
    producer=destination/str(safe_relative(spec['producer']))
    output=destination/str(safe_relative(spec['output']))
    # 묶음에 든 예전 결과를 성공으로 오인하지 않도록 재생성 전에 제거한다.
    output.unlink(missing_ok=True)
    env=dict(os.environ);env['SFA_REPLAY_REPO']=str(repo)
    process=subprocess.run([sys.executable,str(producer)],cwd=producer.parent,capture_output=True,text=True,env=env)
    (destination/'replay_console.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
    if process.returncode or not output.exists():raise ValueError('재생성 실패: replay_console.txt 확인')
    actual=xml_sha(output)
    report=dict(exit_code=process.returncode,xml_sha256=actual,
        expected_xml_sha256=spec['expected_xml_sha256'],xml_identical=actual==spec['expected_xml_sha256'],
        locked_decisions_verified=len(locked),
        decision_input_sha256=hashlib.sha256(json.dumps(locked,ensure_ascii=False).encode()).hexdigest())
    (destination/'replay_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not report['xml_identical']:raise ValueError('재현 XML 불일치: replay_result.json 확인')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle');p.add_argument('--destination',required=True)
    a=p.parse_args();print(json.dumps(replay(a.bundle,a.destination),ensure_ascii=False))
