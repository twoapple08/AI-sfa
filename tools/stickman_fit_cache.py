"""보정 전 CPU 피팅을 입력/코드 해시로 동결해 후단 수정 때 재계산하지 않는다."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np


def cached_fit(folder, arrays, parameters, compute):
    if folder is None:
        result = compute()
        return *result[:3], dict(hit=False, enabled=False)
    code = {n: hashlib.sha256((Path(__file__).parent/n).read_bytes()).hexdigest()
            for n in ('rtmw_to_stickman_2d.py', 'rtmw_to_stickman_2d_v2.py')}
    h = hashlib.sha256(json.dumps(dict(version=1, code=code, parameters=parameters), sort_keys=True,
                                 default=lambda v: np.asarray(v).tolist()).encode())
    for name, array in sorted(arrays.items()):
        array = np.ascontiguousarray(array)
        h.update(str((name, array.shape, array.dtype.str)).encode())
        h.update(memoryview(array))
    key = h.hexdigest()
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    path = folder/(key+'.npz')
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            if str(z['key']) != key:
                raise ValueError('피팅 캐시 입력 지문 불일치')
            joints = {n[3:]: z[n].copy() for n in z.files if n.startswith('J__')}
            scale, report = z['scale'].copy(), json.loads(str(z['report']))
        return joints, scale, report, dict(hit=True, enabled=True, key=key)
    result = compute()
    joints, scale, report = result[:3]
    temp = folder/(key+f'.{os.getpid()}.tmp')
    with temp.open('wb') as f:
        np.savez_compressed(f, key=key, scale=scale,
            report=json.dumps(report, ensure_ascii=False, default=lambda v: np.asarray(v).tolist()),
            **{'J__'+n: v for n,v in joints.items()})
    os.replace(temp, path)
    return joints, scale, report, dict(hit=False, enabled=True, key=key)
