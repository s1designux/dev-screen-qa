"""눌렀던 자리를 기억한다 — 같은 글자를 다음부터는 자리(좌표)로 바로 누르기 위해.

왜 필요한가
    글자를 찾아서 누르면 촬영 도구가 폰 화면 목록을 통째로 읽어 온다. 실제 폰에서
    한 번에 4.7초가 걸린다. 같은 자리를 좌표로 누르면 1.5초다. 화면마다 두세 번씩
    누르니 한 바퀴에서 이 차이가 가장 크다.

어떻게 하는가
    처음 한 번은 글자로 찾는다(lib/learn.py). 찾은 자리를 여기 사전에 적어 두고,
    다음부터는 그 자리를 바로 누른다. 자리는 폰 크기가 달라도 맞도록 % 로 적는다.

    자리가 어긋나면(앱이 바뀌어 단추가 옮겨갔다면) 아무 일도 일어나지 않아
    앞 장과 똑같은 사진이 찍힌다. 그것을 runner.py 가 알아채고 그 묶음의 자리를
    지운 뒤 예전처럼 글자로 다시 찍는다.

바깥 라이브러리를 쓰지 않는다(설치 묶음 배포 때 파이썬만 있으면 돌아가게).
"""
import json
import os
import re
import shutil
import subprocess

여기 = os.path.dirname(os.path.abspath(__file__))
뿌리 = os.path.dirname(여기)
사전파일 = os.path.join(뿌리, "apps", "자리사전.json")


def adb():
    """어느 PC에서든 adb 를 찾아 쓴다."""
    찾은것 = shutil.which("adb")
    if 찾은것:
        return 찾은것
    자리 = os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
    return 자리 if os.path.exists(자리) else "adb"


def _전체읽기():
    if not os.path.exists(사전파일):
        return {}
    try:
        with open(사전파일, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _전체쓰기(사전):
    os.makedirs(os.path.dirname(사전파일), exist_ok=True)
    with open(사전파일, "w", encoding="utf-8") as f:
        json.dump(사전, f, ensure_ascii=False, indent=2)


def 열쇠(화면번호, 글자):
    """어느 화면의 어느 글자인지 — 같은 글자라도 화면마다 자리가 다르다."""
    return f"{화면번호}|{글자}"


def 읽기(앱주소):
    return dict(_전체읽기().get(앱주소, {}))


def 적어두기(앱주소, 키, 가로, 세로):
    """자리는 정수 % 로 적는다 — 촬영 도구가 소수점을 받지 않는다."""
    사전 = _전체읽기()
    사전.setdefault(앱주소, {})[키] = [int(round(가로)), int(round(세로))]
    _전체쓰기(사전)


def 지우기(앱주소, 키들):
    """자리가 어긋난 묶음의 기억을 지운다 — 다음번에 다시 글자로 찾게."""
    사전 = _전체읽기()
    한앱 = 사전.get(앱주소)
    if not 한앱:
        return
    for k in 키들:
        한앱.pop(k, None)
    _전체쓰기(사전)


def 화면크기():
    try:
        out = subprocess.run([adb(), "shell", "wm", "size"],
                             capture_output=True, text=True, timeout=10).stdout
        수 = re.findall(r"(\d+)x(\d+)", out)
        if 수:
            return int(수[-1][0]), int(수[-1][1])
    except Exception:
        pass
    return 0, 0


_노드 = re.compile(r"<node[^>]*>")


def _칸(노드, 이름):
    m = re.search(r'%s="([^"]*)"' % 이름, 노드)
    return m.group(1) if m else ""


def 촬영도구깨우기():
    """폰 안의 촬영 도구를 한 번 껐다 켜지게 한다.

    화면 목록을 읽는 일(uiautomator)과 촬영 도구는 폰 안에서 같은 통로를 쓴다.
    번갈아 쓰면 촬영 도구가 먼저 죽어 다음 대본이 곧바로 실패한다. 그래서 목록을
    읽고 난 뒤에는 촬영 도구를 껐다 — 다음에 쓸 때 저절로 새로 켜진다.
    """
    for 꾸러미 in ("dev.mobile.maestro", "dev.mobile.maestro.test"):
        try:
            subprocess.run([adb(), "shell", "am", "force-stop", 꾸러미],
                           capture_output=True, text=True, timeout=15)
        except Exception:
            pass


def 지금화면에서찾기(글자):
    """지금 폰에 떠 있는 화면에서 그 글자의 한가운데 자리를 (가로%, 세로%) 로 돌려준다.

    없으면 None. 글자가 그대로 있는 것을 먼저 보고, 없으면 아이콘 설명(content-desc),
    그래도 없으면 글자가 들어 있는 것을 본다(촬영 도구가 찾는 방식과 같은 순서).
    """
    폭, 높이 = 화면크기()
    if not 폭:
        return None
    try:
        xml = subprocess.run([adb(), "exec-out", "uiautomator", "dump", "/dev/tty"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return None
    노드들 = _노드.findall(xml)

    def 자리(노드):
        m = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', 노드)
        if not m:
            return None
        x1, y1, x2, y2 = (int(v) for v in m.groups())
        if x2 <= x1 or y2 <= y1:
            return None
        return ((x1 + x2) / 2 * 100 / 폭, (y1 + y2) / 2 * 100 / 높이)

    for 고르기 in (lambda n: _칸(n, "text") == 글자,
                lambda n: _칸(n, "content-desc") == 글자,
                lambda n: 글자 in _칸(n, "text") or 글자 in _칸(n, "content-desc")):
        for n in 노드들:
            if 고르기(n):
                찾은자리 = 자리(n)
                if 찾은자리:
                    return 찾은자리
    return None
