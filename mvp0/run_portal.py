"""파일을 고치면 포털을 저절로 껐다 켜고, 열어 둔 화면도 스스로 새로고침한다.

python3 run_portal.py  로 실행한다. (환경변수는 portal.py 와 동일)
"""
import os, signal, subprocess, sys, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
WATCH_SUFFIX = ('.py', '.js', '.sql')
IGNORE = {'run_portal.py'}
INTERVAL = 0.5


def snapshot():
    out = {}
    for p in BASE.rglob('*'):
        if p.suffix not in WATCH_SUFFIX or p.name in IGNORE:
            continue
        if any(part in ('uploads', '__pycache__', 'plans') for part in p.parts):
            continue
        try:
            out[p] = p.stat().st_mtime
        except OSError:
            pass
    return out


def start():
    env = dict(os.environ, QA_PORTAL_AUTORELOAD='1', PYTHONDONTWRITEBYTECODE='1')
    return subprocess.Popen([sys.executable, 'portal.py'], cwd=str(BASE), env=env)


def stop(proc):
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def main():
    proc = start()
    seen = snapshot()
    print('코드를 고치면 저절로 다시 켜집니다. (Ctrl+C 종료)')
    try:
        while True:
            time.sleep(INTERVAL)
            now = snapshot()
            if now != seen:
                changed = sorted({p.name for p in set(now) ^ set(seen)} |
                                 {p.name for p in set(now) & set(seen) if now[p] != seen[p]})
                seen = now
                print(f'바뀐 파일: {", ".join(changed)} → 다시 켭니다')
                stop(proc)
                proc = start()
            elif proc.poll() is not None:
                print('포털이 멈췄습니다. 파일을 고치면 다시 켭니다.')
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop(proc)


if __name__ == '__main__':
    main()
