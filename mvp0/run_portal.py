"""파일을 고치면 포털을 저절로 껐다 켜고, 열어 둔 화면도 스스로 새로고침한다.

python3 run_portal.py  로 실행한다. (환경변수는 portal.py 와 동일)
맥 자동 시작(scripts/mac-autostart-on.sh)도 이것으로 켠다 — 포털은 늘 한 벌이다.
"""
import os, signal, socket, subprocess, sys, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
WATCH_SUFFIX = ('.py', '.js', '.sql')
IGNORE = {'run_portal.py'}
INTERVAL = 0.5

if str(BASE.parent) not in sys.path:
    sys.path.insert(0, str(BASE.parent))
import 설정 as 설정                        # portal.py 와 같은 포트를 본다
PORT = int(설정.값("포털.포트"))


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


def port_busy():
    """누가 이미 그 자리(포트)를 쥐고 있는지."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        return s.connect_ex(('127.0.0.1', PORT)) == 0
    finally:
        s.close()


def wait_port_free():
    """다른 포털이 자리를 쥐고 있으면 한 줄만 알리고 빌 때까지 기다린다(옛 판을 그대로 두지 않게)."""
    if not port_busy():
        return
    print(f'{PORT} 자리를 다른 포털이 쓰고 있습니다 — 그 포털이 꺼지면 이어서 켭니다.', flush=True)
    while port_busy():
        time.sleep(2)


def start():
    wait_port_free()
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


def _quit(signum, frame):
    raise SystemExit(0)   # 꺼질 때도 finally 를 거쳐 포털을 함께 끈다(홀로 남는 옛 포털을 막는다)


def main():
    signal.signal(signal.SIGTERM, _quit)
    signal.signal(signal.SIGHUP, _quit)
    proc, born = start(), time.time()
    seen = snapshot()
    told = False
    print('코드를 고치면 저절로 다시 켜집니다. (Ctrl+C 종료)', flush=True)
    try:
        while True:
            time.sleep(INTERVAL)
            now = snapshot()
            if now != seen:
                changed = sorted({p.name for p in set(now) ^ set(seen)} |
                                 {p.name for p in set(now) & set(seen) if now[p] != seen[p]})
                seen = now
                print(f'바뀐 파일: {", ".join(changed)} → 다시 켭니다', flush=True)
                stop(proc)
                proc, born, told = start(), time.time(), False
            elif proc.poll() is not None:
                if time.time() - born > 10:          # 잘 돌다 꺼졌으면 다시 켠다
                    print('포털이 멈췄습니다. 다시 켭니다.', flush=True)
                    time.sleep(1)
                    proc, born = start(), time.time()
                elif not told:                       # 켜자마자 꺼지면 코드 탓 — 고칠 때까지 기다린다
                    print('포털이 켜지자마자 멈췄습니다. 파일을 고치면 다시 켭니다.', flush=True)
                    told = True
    except KeyboardInterrupt:
        pass
    finally:
        stop(proc)


if __name__ == '__main__':
    main()
