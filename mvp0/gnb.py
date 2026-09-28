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


# 정본 부품 CSS 에서 GNB 칸만 잘라 둔 한 장(`부품받기.sh` 가 만든다).
# 옛 화면은 손으로 옮겨 적은 부품 CSS 를 쓰고 있어 s1-ui.css 를 통째로 이으면 단추·표까지 바뀐다.
# 이미 s1-ui.css 를 이은 화면에 이 줄이 또 와도 같은 규칙이라 달라지는 것이 없다.
_CSS링크 = "<link rel=stylesheet href='/assets/css/s1-gnb.css'>"

# 놓는 자리만 — 쪽지 생김새(바탕·그림자·줄 높이)는 위 정본 Dropdown 부품이 전부 입힌다.
# ① 유틸 칸을 기준점으로 삼아 ② 쪽지를 아이콘 바로 아래 오른쪽 끝에 맞춘다.
# ③ 정본 옵션 줄은 <div> 라 밑줄 규칙이 없다 — 우리는 <a> 로 두므로 밑줄만 거둔다.
_자리CSS = """<style>
[data-s1-component="gnb"] [data-s1-part="util"]{position:relative}
#gnb-account-menu{position:absolute;top:100%;right:0;z-index:20;margin-top:var(--spacing-4)}
/* 정본 Dropdown 은 display:flex 를 스스로 달고 있어 hidden 만으로는 안 사라진다 */
#gnb-account-menu[hidden]{display:none}
#gnb-account-menu [data-s1-part="option"]{text-decoration:none}
</style>"""

# 로고 글자는 정본 20 의 80% — 로그인 화면과 포털 안쪽이 같은 사양이다(river 지시 2026-09-28).
# 좌우 여백은 **건드리지 않는다** — 정본이 full-width 반응형에 왼 24 · 오른 20 으로 정해 두었다
# (registry gnb.json barPaddingLeft/Right · DESIGN.core "뷰포트 1280/1440/1920 은 full-width 반응형").
# 시안이 양 끝 320 안쪽인 것은 그 화면의 자리 잡기이지 부품 규정이 아니다.
# 로그인 화면은 바를 스스로 짜므로(auth._로그인줄) 이 한 장을 그쪽도 가져다 쓴다 — 값을 두 벌로 두지 않는다.
바CSS = ('<style>[data-s1-component="gnb"] [data-s1-part="logo"]'
       '{font-size:var(--font-size-16)}</style>')

_동작 = "<script src='/assets/js/gnb-account.js' defer></script>"


def 바(지금="", size="sm"):
    """맨 위 줄 한 개 — 로고와 유틸 아이콘뿐이다.

    메뉴(과제 · 가져온 기록 · 검수 규칙 · 촬영 준비)는 두지 않는다(river 지시 2026-09-28).
    `지금` 은 어느 자리인지 부르는 쪽이 알려 주던 값인데, 표시할 메뉴가 없어 지금은 쓰지 않는다 —
    부르는 곳이 많아 칸은 그대로 둔다. 로고를 누르면 과제 목록으로 간다.
    정렬은 정본 기본값인 center-between — 가운데 칸이 비어 로고와 유틸이 양 끝에 선다.
    """
    유틸, 쪽지 = _유틸()
    return (_CSS링크 + 바CSS + _자리CSS
            + f'<nav data-s1-component="gnb" data-size="{_e(size)}"'
            f' aria-label="주 메뉴">'
            f'<a data-s1-part="logo" href="/">에스원 개발화면 검수 포털</a>'
            f'<ul data-s1-part="menus"></ul>'
            f'<span data-s1-part="util">{유틸}{쪽지}</span></nav>'
            + (_동작 if 쪽지 else ""))


def _유틸():
    """유틸 아이콘 하나(사람) + 그 아래 열리는 계정 쪽지.

    들어온 사람 · 계정 관리(관리자만) · 로그아웃을 바에 늘어놓지 않고 쪽지 한 장에 담는다
    (river 지시 2026-09-28 — 개발 화면의 오른쪽 위 유틸 단추와 같은 모양).
    쪽지는 정본 Dropdown 부품이고, 여닫는 것은 `assets/js/gnb-account.js` 가 한다.
    """
    import auth
    사람 = auth.지금사람()
    if not 사람:
        return "", ""
    단추 = (f'<button type="button" data-s1-part="account" id="gnb-account"'
          f' aria-haspopup="menu" aria-expanded="false" aria-controls="gnb-account-menu"'
          f' aria-label="내 계정 · {_e(사람["name"])}">'
          f'<span data-s1-part="account-icon" aria-hidden="true"></span></button>')
    길 = [("내 계정", "/account")]
    if 사람["role"] == auth.관리자:
        길.append(("계정 관리", "/accounts"))
    길.append(("로그아웃", "/logout"))
    줄 = "".join(
        f'<a data-s1-part="option" role="menuitem" href="{_e(주소)}">'
        f'<span data-s1-part="option-label">{_e(이름)}</span></a>'
        for 이름, 주소 in 길)
    쪽지 = ('<div id="gnb-account-menu" data-s1-component="dropdown" data-type="text"'
          ' data-size="xsm" role="menu" aria-labelledby="gnb-account" hidden>'
          f'{줄}</div>')
    return 단추, 쪽지
