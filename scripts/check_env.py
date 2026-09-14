"""이 PC 에서 검수기가 돌 준비가 됐는지 한 줄씩 본다.

    python scripts/check_env.py

무엇이 되고 무엇이 안 되는지만 보여 준다. **아무것도 고치지 않고, 아무 자료도 건드리지 않는다.**
안 되는 줄에는 '무엇이 막혔는지'와 '무엇을 하면 되는지'를 한 줄로 적는다.

윈도우에서는 `점검-윈도우.bat` 을 두 번 누르면 이 파일이 돈다.
"""
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(뿌리))          # valueqa 를 저장소 자리에서 읽는다(따로 깔지 않는다)
너비 = 16


def _채움(s):
    """한글은 창에서 두 칸으로 보인다 — 눈에 보이는 폭으로 칸을 맞춘다."""
    폭 = sum(2 if ord(ch) > 0x1100 else 1 for ch in s)
    return s + " " * max(1, 너비 - 폭)


def 줄(이름, 됨, 말, 할일=""):
    print("%s %s %s" % (_채움(이름), "OK  " if 됨 else "안됨", 말))
    if not 됨 and 할일:
        print("%s      → %s" % (" " * 너비, 할일))
    return 됨


def 파이썬():
    v = sys.version_info
    됨 = v >= (3, 9)
    return 줄("파이썬", 됨, "%d.%d.%d" % (v.major, v.minor, v.micro),
             "파이썬 3.9 이상을 깔아 주세요 (python.org). 깔 때 'Add to PATH' 를 켜 주세요.")


def 크롬():
    """값을 재려면 크롬(또는 엣지)이 있어야 한다. 웹 화면을 열어 색·크기를 읽는 데 쓴다."""
    자리 = []
    if platform.system() == "Windows":
        자리 = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
    else:
        자리 = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for p in 자리:
        if os.path.exists(p):
            return 줄("크롬", True, Path(p).name)
    for 이름 in ("chrome", "msedge", "google-chrome"):
        p = shutil.which(이름)
        if p:
            return 줄("크롬", True, p)
    return 줄("크롬", False, "못 찾았습니다",
             "크롬을 깔아 주세요. 웹 화면의 값을 재는 데 씁니다.")


def 플레이라이트():
    """화면을 저절로 열어 값을 재는 연장. 없어도 포털·검사는 돌지만, 자동 캡쳐는 못 한다."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        return 줄("자동 캡쳐 연장", False, "아직 없습니다",
                 "명령창에 치세요:  python -m pip install playwright")
    return 줄("자동 캡쳐 연장", True, "있음")


def 닿나(주소, 시간=15):
    try:
        req = urllib.request.Request(주소, headers={"User-Agent": "check-env"})
        with urllib.request.urlopen(req, timeout=시간) as r:
            return True, r.status
    except Exception as e:
        return False, e


def 정본():
    """회사 규정(토큰·컴포넌트)의 정본을 깃허브에서 받아올 수 있나.
    깃허브 화면은 열려도 '파일 받는 주소'만 따로 막혀 있는 경우가 있어 따로 본다."""
    try:
        import valueqa.registry as reg
    except ImportError as e:
        return 줄("회사 규정 정본", False, "프로그램 파일을 못 읽었습니다 (%s)" % e,
                 "깃허브에서 다시 내려받아 주세요 (동료공유-읽어보기.md 1단계).")
    됨, 무엇 = 닿나(reg.판주소)
    if not 됨:
        return 줄("회사 규정 정본", False, "못 받았습니다 (%s)" % 무엇,
                 "깃허브 파일 주소가 막혀 있습니다. 전산팀에 api.github.com · codeload.github.com 을 열어 달라고 해 주세요.")
    됨2, 무엇2 = 닿나(reg.받는주소, 60)
    if not 됨2:
        return 줄("회사 규정 정본", False, "목록은 보이는데 파일을 못 받습니다 (%s)" % 무엇2,
                 "codeload.github.com 이 막혀 있습니다. 전산팀에 열어 달라고 해 주세요.")
    return 줄("회사 규정 정본", True, "받아집니다")


def 검수자료():
    db = 뿌리 / "mvp0" / "mvp0-real.db"
    if db.exists():
        크기 = db.stat().st_size // 1024
        return 줄("검수 자료", True, "mvp0-real.db (%d KB)" % 크기)
    return 줄("검수 자료", False, "mvp0-real.db 가 없습니다",
             "따로 받은 mvp0-real.db 와 uploads 폴더를 mvp0 안에 넣어 주세요 (동료공유-읽어보기.md 2단계).")


def 포털파일():
    빠진것 = [p for p in ("mvp0/portal.py", "engine/ui.html", "valueqa/rules.py") if not (뿌리 / p).exists()]
    if 빠진것:
        return 줄("프로그램 파일", False, "빠진 파일: %s" % ", ".join(빠진것),
                 "깃허브에서 다시 내려받아 주세요 (동료공유-읽어보기.md 1단계).")
    return 줄("프로그램 파일", True, "다 있습니다")


def 검사():
    """만든 것이 이 PC 에서도 같은 답을 내는지 — 값 대조·규정 대조 자가검사."""
    try:
        p = subprocess.run([sys.executable, "-m", "valueqa.selftest"], cwd=str(뿌리),
                           capture_output=True, text=True, timeout=180)
    except Exception as e:
        return 줄("검사", False, "돌리지 못했습니다 (%s)" % e, "위의 '파이썬' 줄을 먼저 봐 주세요.")
    if p.returncode == 0:
        마지막 = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
        return 줄("검사", True, 마지막[-1][:60] if 마지막 else "통과")
    탈 = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()
    return 줄("검사", False, (탈[-1][:70] if 탈 else "실패"),
             "이 창에 보이는 글을 그대로 보여 주시면 고쳐 드립니다.")


def main():
    print()
    print("검수기가 돌 준비가 됐는지 봅니다 — %s" % 뿌리)
    print("(아무것도 고치지 않고 보기만 합니다)")
    print()
    결과 = [파이썬(), 포털파일(), 검수자료(), 크롬(), 플레이라이트(), 정본(), 검사()]
    print()
    안된수 = 결과.count(False)
    if 안된수 == 0:
        if platform.system() == "Windows":
            print("다 됐습니다. 포털-켜기-윈도우.bat 을 누르면 됩니다.")
        else:
            print("다 됐습니다.")
    else:
        print("안 되는 것이 %d 가지 있습니다. 위의 → 줄대로 하시거나," % 안된수)
        print("이 창을 그대로 보여 주시면 고쳐 드립니다.")
    print()
    return 0 if 안된수 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
