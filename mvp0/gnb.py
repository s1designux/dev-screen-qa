"""포털 맨 위 메뉴 줄 (S-1 정본 GNB · river 지시 2026-09-22).

생김새는 `assets/css/s1-ui.css` 가 전부 입힌다 — 여기서는 **어떤 메뉴를 어떤 차례로 두는지**만 정한다.
가이드 §4 GNB 를 그대로 따른다:
  · 바 전체를 `<nav aria-label>` 로 감싼다
  · 메뉴 목록은 `<ul>/<li>` + `<a href>`
  · 지금 있는 자리에만 `aria-current="page"` 를 준다 (Selected 는 눈에 보이는 표현, 자리 알림은 aria-current)
  · 하위메뉴는 두지 않는다 — 그래서 이 줄에는 딸린 동작(JS)이 없다

'촬영 준비'는 아직 다른 자리에서 도는 사이트라 새 창으로 연다.
꺼져 있을 수도 있으므로 이 줄이 그 사이트를 확인하지는 않는다.
"""
import html
import sys
from urllib.parse import urlencode
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import 설정  # noqa: E402  (이 컴퓨터에서만 쓰는 값 — 촬영 준비 포트)


def _e(v):
    return html.escape(str(v)) if v is not None else ""


def _촬영주소():
    return f"http://127.0.0.1:{설정.값('촬영준비.포트')}/"


def 촬영시작주소(project_uuid, 이름, 화면코드=""):
    """이 과제를 달고 촬영 준비로 간다.

    과제를 달고 가야 접수할 때 그 과제 아래로 들어간다. 달지 않으면 촬영기가
    적힌 이름으로 과제를 찾고 없으면 새로 만들어, 이름이 한 글자만 달라도 쪼개진다.
    """
    값 = urlencode({"과제": project_uuid, "이름": 이름 or "",
                   "코드": 화면코드 or ""})
    return f"{_촬영주소()}과제시작?{값}"


#  (열쇠, 보이는 이름, 주소, 새 창으로 열까)
def 메뉴들():
    return [
        ("project", "과제", "/", False),
        ("intake", "가져온 기록", "/intake", False),
        ("policy", "검수 규칙", "/policy", False),
        ("capture", "촬영 준비", _촬영주소(), True),
    ]


# 정본 부품 CSS 에서 GNB 칸만 잘라 둔 한 장(`부품받기.sh` 가 만든다).
# 옛 화면은 손으로 옮겨 적은 부품 CSS 를 쓰고 있어 s1-ui.css 를 통째로 이으면 단추·표까지 바뀐다.
# 이미 s1-ui.css 를 이은 화면에 이 줄이 또 와도 같은 규칙이라 달라지는 것이 없다.
_CSS링크 = "<link rel=stylesheet href='/assets/css/s1-gnb.css'>"


def 바(지금="", size="sm"):
    """맨 위 메뉴 줄 한 개. `지금` 은 메뉴 열쇠(project·intake·policy·capture).

    정렬은 정본 기본값인 center-between — [로고 | 메뉴 | 유틸] 3분할이라 메뉴가 가운데 온다.
    """
    줄 = ""
    for 열쇠, 이름, 주소, 새창 in 메뉴들():
        여기 = ' aria-current="page"' if 열쇠 == 지금 else ""
        창 = ' target="_blank" rel="noopener"' if 새창 else ""
        줄 += (f'<li><a data-s1-part="menu" href="{_e(주소)}"{창}{여기}>'
               f'{_e(이름)}</a></li>')
    # 유틸(언어·계정·메뉴) 자리는 비워 둔다 — 포털은 로그인도 언어 고르기도 없다.
    # 3분할이라 이 빈 자리가 있어야 메뉴가 가운데에 선다.
    return (_CSS링크
            + f'<nav data-s1-component="gnb" data-size="{_e(size)}"'
            f' aria-label="주 메뉴">'
            f'<a data-s1-part="logo" href="/">검수 포털</a>'
            f'<ul data-s1-part="menus">{줄}</ul>'
            f'<span data-s1-part="util"></span></nav>')
