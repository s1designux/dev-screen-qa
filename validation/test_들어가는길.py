"""들어가는 길 — 로그인 화면을 안 찍어도 로그인하고 들어가는지 본다.

무엇을 보나:
  ① 언제 지나야 하나 (고른 목록에 로그인 화면이 없고 로그인이 있는 서비스일 때만)
  ② 앱 — 묶음 대본 앞에 로그인 줄이 붙고, 그 줄은 사진으로 남지 않는가
  ③ 웹 — 찍는 그 창에서 한 번 들어가고, 못 들어가면 한 장도 찍지 않는가
"""
import os
import sys

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(뿌리, "capture-app", "lib"))

import 들어가는길  # noqa: E402
import runner  # noqa: E402
import webshot  # noqa: E402

잰것 = []


def 같나(무엇, 실제, 바람):
    잰것.append((무엇, 실제 == 바람, f"{실제!r} ≠ {바람!r}"))


def 이름표(화면들, **더):
    t = {"앱이름": "시험앱", "플랫폼": "android", "서비스코드": "TST", "앱주소": "kr.test",
         "로그인": "필요", "시험아이디": "tester", "시험비밀번호": "pw1234", "화면": 화면들}
    t.update(더)
    return t


def 화면(이름, 동작="-", 번호="001", 상태="default"):
    return {"번호": 번호, "이름": 이름, "상태": 상태, "동작": 동작,
            "누를것": "-", "이어서": "아니오"}


# ── ① 언제 지나야 하나 ──────────────────────────────────────
같나("홈만 골랐으면 지난다", 들어가는길.필요한가(이름표([화면("홈")])), True)
같나("로그인 화면이 목록에 있으면 지나지 않는다",
   들어가는길.필요한가(이름표([화면("로그인 화면"), 화면("홈", 번호="002")])), False)
같나("로그인 오류 화면만 골라도 지나지 않는다",
   들어가는길.필요한가(이름표([화면("로그인 화면_유효하지 않은 아이디")])), False)
같나("로그아웃 화면은 로그인 화면이 아니다",
   들어가는길.필요한가(이름표([화면("로그아웃 안내")])), True)
같나("로그인이 없는 서비스는 지나지 않는다",
   들어가는길.필요한가(이름표([화면("홈")], 로그인="없음")), False)
같나("계정 표식이 든 동작이 있으면 그 목록이 이미 로그인한다",
   들어가는길.필요한가(이름표([화면("첫 화면", "입력 아이디=<아이디> → 입력 비밀번호=<비번> → 탭 로그인")])),
   False)
같나("일부러 틀리는 동작은 들어가는 길이 아니다",
   들어가는길.정말들어가나("입력 아이디=<아이디> → 입력 비밀번호=<틀린비번> → 탭 로그인"), False)
같나("아이디·비번을 다 넣는 동작만 들어가는 길이다",
   들어가는길.정말들어가나("입력 아이디=<아이디> → 입력 비밀번호=<비번> → 탭 로그인"), True)

# ── ② 앱 ────────────────────────────────────────────────
길 = "입력 아이디=<아이디> → 입력 비밀번호=<비번> → 탭 로그인"
계정 = {"아이디": "tester", "비밀번호": "pw1234"}

줄, 알림 = 들어가는길.앱줄(이름표([화면("홈")], 들어가는길=길), 계정)
같나("적어 둔 길이 있으면 줄이 나온다", bool(줄), True)
같나("들어가는 길은 사진으로 남지 않는다", any("takeScreenshot" in l for l in 줄), False)
같나("적어 둔 시험 계정이 들어간다", any("tester" in l for l in 줄), True)
같나("길이 있으면 알림이 없다", 알림, "")

줄없음, 알림2 = 들어가는길.앱줄(이름표([화면("홈")]), 계정)
같나("길이 없으면 줄이 없다", 줄없음, [])
같나("길이 없으면 한 줄로 알린다", "들어가는 길" in 알림2, True)

줄3, _ = 들어가는길.앱줄(이름표([화면("로그인 화면")], 들어가는길=길), 계정)
같나("로그인 화면을 찍는 목록에는 붙이지 않는다", 줄3, [])

import tempfile  # noqa: E402

폴더 = tempfile.mkdtemp()
tag = 이름표([화면("홈")], 들어가는길=길)
경로 = runner.대본쓰기(tag, [화면("홈")], ["TST-AND-001@default.png"], 폴더, 1, 계정, None, 줄)
대본 = open(경로, encoding="utf-8").read()
같나("대본에 로그인 줄이 들어간다", "tester" in 대본, True)
같나("로그인은 앱을 켠 뒤·찍기 전에 지난다",
   대본.index("tester") < 대본.index("takeScreenshot"), True)
스플 = {"번호": "001", "이름": "00Splash_long", "상태": "long", "동작": "-",
      "누를것": "-", "이어서": "아니오"}
스플대본 = open(runner.대본쓰기(tag, [스플], ["TST-AND-001@long.png"], 폴더, 2, 계정, None, 줄),
            encoding="utf-8").read()
같나("스플래시에는 붙이지 않는다", "tester" in 스플대본, False)


# ── ③ 웹 ────────────────────────────────────────────────
class 가짜쪽:
    def __init__(self):
        self.연것 = []

    def goto(self, 주소, **_):
        self.연것.append(주소)

    def wait_for_timeout(self, _):
        pass

    def screenshot(self, path=None, **_):
        open(path, "wb").write(b"png")

    def evaluate(self, *a, **k):
        return None

    def mouse(self):
        return None


class 가짜칸:
    def __init__(self, 쪽):
        self._쪽 = 쪽

    def new_page(self):
        return self._쪽


class 가짜브라우저:
    def __init__(self, 쪽):
        self._쪽 = 쪽
        self.꺼짐 = False

    def new_context(self, **_):
        return 가짜칸(self._쪽)

    def close(self):
        self.꺼짐 = True

    @property
    def contexts(self):
        return [1]


class 가짜연장:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def 웹시험(들머리결과):
    쪽 = 가짜쪽()
    브 = 가짜브라우저(쪽)
    본래 = (webshot.연장가져오기, webshot.브라우저켜기, webshot.브라우저끄기,
          webshot.커서.치우기, webshot.webvalue.긁기, webshot.webvalue.쓰기,
          webshot._살아있나, 들어가는길.웹으로)
    부른것 = []
    webshot.연장가져오기 = lambda: (lambda: 가짜연장())
    webshot.브라우저켜기 = lambda 연장, 보이기=None: (브, "가짜")
    webshot.브라우저끄기 = lambda b: None
    webshot.커서.치우기 = lambda 쪽: None
    webshot.webvalue.긁기 = lambda 쪽, 이름: {"elements": []}
    webshot.webvalue.쓰기 = lambda 길, 값: open(길, "w").write("{}")
    webshot._살아있나 = lambda b, p: True
    def 가짜들머리(쪽, tag, 기다림=0.6):
        부른것.append(tag.get("앱이름"))
        return 들머리결과
    들어가는길.웹으로 = 가짜들머리
    webshot.들어가는길.웹으로 = 가짜들머리
    try:
        폴더 = tempfile.mkdtemp()
        tag = 이름표([화면("홈", 번호="010")], 플랫폼="web", 유형="web",
                  기본주소="https://example.test", 앱주소=None)
        목록 = webshot.찍기(tag, 폴더)
        return 목록, 부른것
    finally:
        (webshot.연장가져오기, webshot.브라우저켜기, webshot.브라우저끄기,
         webshot.커서.치우기, webshot.webvalue.긁기, webshot.webvalue.쓰기,
         webshot._살아있나, 들어가는길.웹으로) = 본래
        webshot.들어가는길.웹으로 = 본래[-1]


목록, 부른것 = 웹시험({"됨": True, "까닭": "", "잠김": False})
같나("웹은 찍기 전에 한 번 들어간다", 부른것, ["시험앱"])
같나("들어간 뒤에는 그대로 찍는다", len(목록["찍힌것"]), 1)

목록2, _ = 웹시험({"됨": False, "까닭": "아이디나 비밀번호가 맞지 않습니다.", "잠김": False})
같나("못 들어가면 한 장도 안 찍는다", len(목록2["찍힌것"]), 0)
같나("못 들어간 까닭을 남긴다", len(목록2["못찍은것"]), 1)


# ── 결과 ────────────────────────────────────────────────
틀린것 = [(무엇, 말) for 무엇, 됐나, 말 in 잰것 if not 됐나]
for 무엇, 됐나, 말 in 잰것:
    print(("  ✓ " if 됐나 else "  ✗ ") + 무엇 + ("" if 됐나 else f" — {말}"))
print(f"\n{len(잰것) - len(틀린것)}/{len(잰것)} 통과")
sys.exit(1 if 틀린것 else 0)
