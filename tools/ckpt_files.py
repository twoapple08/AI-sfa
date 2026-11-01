"""학습 저장본 내보내기 전 정리(GPT 재확인 R-05, 11-01).

seq_train은 본 파일(ckpt.pt)을 못 바꾸면(Windows 잠금 등) 예비 파일(ckpt.pt.fallback)에 쓰고, 이어하기 때 둘 중 새것을 읽는다.
그런데 PC 올리기·zip·Kaggle 이어하기 자료·Drive 전송은 ckpt.pt만 옮겨서, 예비 파일에만 있는 최신 학습·공식 횟수를 잃을 수 있었다.
promote(폴더): 예비 파일이 더 새것이면 본 파일 자리로 옮기고(학습이 끝난 뒤라 잠금이 풀려 있다), 낡은 예비 파일은 지운다.
전송하는 쪽은 옮기기 전에 이것을 부른다. 무거운 모듈을 쓰지 않는다(Kaggle 작업자·원격 도구에서도 가볍게).
"""
import os
import time


def promote(folder, name='ckpt.pt', tries=30, wait=2.0):
    """'promoted' | 'stale-removed' | 'none' | 'locked'(옮기지 못함 — 호출 쪽이 알리고 멈춰야 한다)."""
    main = os.path.join(folder, name)
    fb = main + '.fallback'
    if not os.path.exists(fb):
        return 'none'
    if os.path.exists(main) and os.path.getmtime(main) >= os.path.getmtime(fb):
        try:
            os.remove(fb)
            return 'stale-removed'
        except OSError:
            return 'none'
    for _ in range(tries):
        try:
            os.replace(fb, main)
            print('저장본: 예비 파일이 더 새것이라 본 파일로 옮김', flush=True)
            return 'promoted'
        except PermissionError:
            time.sleep(wait)
    print('저장본: 예비 파일을 본 파일로 옮기지 못함(잠금) — 전송하면 최신 학습을 잃는다', flush=True)
    return 'locked'


if __name__ == '__main__':
    import sys
    print(promote(sys.argv[1]))
