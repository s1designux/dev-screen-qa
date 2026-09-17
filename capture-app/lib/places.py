"""눌렀던 자리를 기억한다 — 같은 글자를 다음부터는 자리(좌표)로 바로 누르기 위해.

왜 필요한가
    글자를 찾아서 누르면 촬영 도구가 폰 화면 목록을 통째로 읽어 온다. 실제 폰에서
    한 번에 4.7초가 걸린다. 같은 자리를 좌표로 누르면 1.5초다. 화면마다 두세 번씩
    누르니 한 바퀴에서 이 차이가 가장 크다.

어떻게 하는가
    **따로 익히러 다니지 않는다.** 찍고 나면 촬영 도구가 남긴 기록에 '어디를 눌렀는지'가
    적혀 있다(`Tapping at (540, 794)`). 그것을 읽어 사전에 적어 둔다 — 첫 촬영은 예전과
    같은 시간이 걸리고, 그다음 촬영부터 그 자리를 바로 누른다.
    자리는 폰 크기가 달라도 맞도록 % 로 적는다.

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


# ── 찍고 난 뒤 기록에서 자리 읽기 ────────────────────────────────
# 촬영 도구는 누를 때마다 기록에 두 줄을 남긴다:
#     Tap on "로그인" RUNNING          ← 무엇을 눌렀나
#     Tapping at (540, 794)           ← 실제로 어디를 눌렀나 (폰 픽셀)
# 자리(point)로 누른 것은 첫 줄이 `Tap on point (…)` 이라 글자와 짝지어지지 않는다.
_글자탭 = re.compile(r'Tap on "(.*?)" RUNNING')
_자리탭 = re.compile(r"Tap on point ")
_누른자리 = re.compile(r"Tapping at \((\d+), (\d+)\)")


def 기록읽기(로그글):
    """대본 하나의 기록에서 [누른 글자, 가로px, 세로px] 를 나온 차례대로 뽑는다."""
    나온것 = []
    기다리는글자 = None
    for 줄 in (로그글 or "").splitlines():
        if _자리탭.search(줄):
            기다리는글자 = None
            continue
        m = _글자탭.search(줄)
        if m:
            기다리는글자 = m.group(1)
            continue
        m = _누른자리.search(줄)
        if m and 기다리는글자 is not None:
            나온것.append((기다리는글자, int(m.group(1)), int(m.group(2))))
            기다리는글자 = None
    return 나온것


def 기록에서익히기(앱주소, 기록들, 대본차례):
    """찍고 난 기록을 읽어 '이 화면의 이 글자는 여기' 를 적어 둔다.

    기록들: {대본이름: 그 대본의 기록 글}
    대본차례: {대본이름: [(글자, 화면번호 또는 None), …]} — 대본에 글자로 적은 누르기가
    나온 차례. 있으면탭처럼 눌릴 수도 안 눌릴 수도 있는 것은 화면번호를 None 으로 둬
    자리를 외우지 않는다(차례만 맞춘다).
    돌려주는 것: 새로 적어 둔 자리 개수.
    """
    폭, 높이 = 화면크기()
    if not 폭 or not 높이:
        return 0
    이미있는것 = 읽기(앱주소)
    새로적은것 = 0
    for 대본이름, 로그글 in (기록들 or {}).items():
        차례 = list((대본차례 or {}).get(대본이름) or [])
        for 글자, x, y in 기록읽기(로그글):
            자리 = next((i for i, (g, _) in enumerate(차례) if g == 글자), None)
            if 자리 is None:
                continue                  # 대본에 없는 누르기 — 짝을 못 지었으니 건너뛴다
            _글자, 화면번호 = 차례[자리]
            del 차례[:자리 + 1]
            if not 화면번호:
                continue
            열 = 열쇠(화면번호, 글자)
            가로, 세로 = x * 100 / 폭, y * 100 / 높이
            if 이미있는것.get(열) == [int(round(가로)), int(round(세로))]:
                continue
            적어두기(앱주소, 열, 가로, 세로)
            새로적은것 += 1
    return 새로적은것
