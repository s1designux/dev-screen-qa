"""정본 부품 마크업을 한 곳에서 짓는다 — 화면은 이것만 불러 쓴다.

**여기에 생김새를 적지 않는다.** 색·크기·모서리·상태는 전부 정본 부품 CSS
(`assets/css/s1-ui.css`, `부품받기.sh` 가 받아 둔 것)가 정한다. 이 파일이 하는 일은
정본이 정해 둔 **뼈대(data-s1-component · data-s1-part)를 그대로 짓는 것**뿐이다.

쓸 수 있는 크기·변형 이름은 정본 부품 명세(`components/*.manifest.json`)에 있는 것뿐이다:
  단추  md · xsm · xxsm · lg      / primary · secondary · blue-line
  입력  xxsm · xsm · md
  고르개 xxsm · xsm · md
  표    md · sm · xsm
  칩    sm · md                   / line · solid
  탭    md · sm · xsm
어긋난 이름을 쓰면 정본 CSS 가 붙지 않아 맨 상자로 보인다 — `scripts/부품점검.py` 가 짚는다.

한 줄자는 PC 34 다(river 확정 2026-09-21). 그래서 기본 크기는 단추·입력·고르개·표 모두 `xsm`.
"""
import html as _html

기본크기 = "xsm"


def _e(v):
    return _html.escape("" if v is None else str(v), quote=True)


def _속성(d):
    """{"name": "값"} → ' name="값"'. 값이 True 면 이름만, None·False 면 빼놓는다."""
    글 = ""
    for 이름, 값 in d.items():
        if 값 is None or 값 is False:
            continue
        이름 = 이름.rstrip("_").replace("__", "-")
        글 += " %s" % 이름 if 값 is True else ' %s="%s"' % (이름, _e(값))
    return 글


# ── 단추 ────────────────────────────────────────────────────────────────────

def 단추(글, 변형="secondary", 크기=기본크기, 종류="button", **속성):
    return ('<button type="%s" data-s1-component="button" data-variant="%s"'
            ' data-size="%s" data-break="pc"%s><span data-s1-part="label">%s</span></button>'
            % (종류, 변형, 크기, _속성(속성), _e(글)))


def 글단추(글, 변형="secondary", 종류="button", **속성):
    """테두리 없는 글자 단추(정본 Text Button)."""
    return ('<button type="%s" data-s1-component="text-button" data-variant="%s"%s>'
            '<span data-s1-part="label">%s</span></button>'
            % (종류, 변형, _속성(속성), _e(글)))


def 단추링크(글, 주소, 변형="secondary", 크기=기본크기, **속성):
    """단추처럼 보이는 링크. 정본 Button 의 뼈대를 그대로 쓰되 태그만 <a> 다."""
    return ('<a href="%s" data-s1-component="button" data-variant="%s"'
            ' data-size="%s" data-break="pc"%s><span data-s1-part="label">%s</span></a>'
            % (_e(주소), 변형, 크기, _속성(속성), _e(글)))


# ── 입력칸 ──────────────────────────────────────────────────────────────────

def 입력(이름=None, 값="", 크기=기본크기, 라벨=None, 칸id=None, 종류="text",
       자리글=None, 지우기=True, 겉속성=None, **속성):
    """정본 Input — 겉(component) → 칸(field) → 알맹이(control) 3층.

    `지우기` 는 정본이 주는 '지우개' 단추다(값이 있고 초점이 있을 때만 보인다).
    """
    속 = {"type": 종류, "name": 이름, "id": 칸id, "value": 값 or None,
         "placeholder": 자리글}
    속.update(속성)
    라벨글 = ('<label data-s1-part="label" for="%s">%s</label>' % (_e(칸id), _e(라벨))
            if (라벨 and 칸id) else "")
    지움 = ('<button type="button" data-s1-part="action" data-action="clear"'
          ' aria-label="입력 내용 지우기" hidden>'
          '<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
          if 지우기 else "")
    return ('<div data-s1-component="input" data-size="%s" data-break="pc"%s>%s'
            '<div data-s1-part="field"><input data-s1-part="control"%s>%s</div></div>'
            % (크기, _속성(겉속성 or {}), 라벨글, _속성(속), 지움))


def 찾기칸(이름=None, 값="", 크기=기본크기, 자리글=None, 칸id=None, **속성):
    """정본 Search Input — Input 의 옵션(data-mode=search)이다."""
    속 = {"type": "search", "name": 이름, "id": 칸id, "value": 값 or None,
         "placeholder": 자리글}
    속.update(속성)
    return ('<div data-s1-component="input" data-mode="search" data-size="%s" data-break="pc">'
            '<div data-s1-part="field"><input data-s1-part="control"%s>'
            '<button type="button" data-s1-part="action" data-action="clear"'
            ' aria-label="입력 내용 지우기" hidden>'
            '<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
            '<button type="button" data-s1-part="action" data-action="search" aria-label="찾기">'
            '<span data-s1-part="action-icon" aria-hidden="true"></span></button>'
            '</div></div>' % (크기, _속성(속)))


def 여러줄(이름=None, 값="", 칸id=None, 자리글=None, **속성):
    속 = {"name": 이름, "id": 칸id, "placeholder": 자리글}
    속.update(속성)
    return ('<div data-s1-component="textarea" data-break="pc">'
            '<textarea data-s1-part="control"%s>%s</textarea></div>'
            % (_속성(속), _e(값)))


def 체크(이름=None, 칸id=None, 글="", 켬=False, 값=None, **속성):
    속 = {"type": "checkbox", "name": 이름, "id": 칸id, "value": 값, "checked": 켬 or None}
    속.update(속성)
    라벨 = ('<label data-s1-part="label" for="%s">%s</label>' % (_e(칸id), _e(글))
          if (글 and 칸id) else "")
    return ('<div data-s1-component="checkbox"><input data-s1-part="control"%s>%s</div>'
            % (_속성(속), 라벨))


def 라디오(이름=None, 칸id=None, 글="", 켬=False, 값=None, **속성):
    속 = {"type": "radio", "name": 이름, "id": 칸id, "value": 값, "checked": 켬 or None}
    속.update(속성)
    라벨 = ('<label data-s1-part="label" for="%s">%s</label>' % (_e(칸id), _e(글))
          if (글 and 칸id) else "")
    return ('<div data-s1-component="radio"><input data-s1-part="control"%s>%s</div>'
            % (_속성(속), 라벨))


# ── 고르개 ──────────────────────────────────────────────────────────────────

_고르개번호 = [0]


def 고르개(이름, 보기, 고른값="", 크기=기본크기, 자리글="선택", 칸id=None,
        라벨=None, 겉속성=None):
    """정본 Select Box + Dropdown.

    `보기` 는 [(값, 보일글), …]. 고른 값은 같은 상자 안 숨은 칸에 담겨 폼이 그대로 보낸다
    (값을 폼에 싣는 것은 정본 밖이라 `assets/js/s1-form.js` 가 잇는다 — gnb 선례와 같다).
    """
    _고르개번호[0] += 1
    앞 = 칸id or "s1sel%d" % _고르개번호[0]
    고른글, 찼나 = 자리글, "false"
    줄 = ""
    for 값, 보일 in 보기:
        이것 = str(값) == str(고른값)
        if 이것:
            고른글, 찼나 = 보일, "true"
        줄 += ('<div data-s1-part="option" role="option" aria-selected="%s" tabindex="%s"'
               ' data-value="%s"><span data-s1-part="option-label">%s</span></div>'
               % ("true" if 이것 else "false", "0" if 이것 else "-1", _e(값), _e(보일)))
    라벨글 = ('<label data-s1-part="label" for="%s-trigger">%s</label>' % (_e(앞), _e(라벨))
            if 라벨 else "")
    return ('<div data-s1-component="select" data-size="%s" data-break="pc"%s>%s'
            '<button type="button" data-s1-part="trigger" id="%s-trigger"'
            ' aria-haspopup="listbox" aria-expanded="false" data-filled="%s">'
            '<span data-s1-part="value">%s</span>'
            '<span data-s1-part="icon" aria-hidden="true"></span></button>'
            '<div data-s1-part="panel" hidden>'
            '<div data-s1-component="dropdown" data-type="text" data-size="%s" role="listbox"'
            ' aria-labelledby="%s-trigger">%s</div></div>'
            '<input type="hidden" name="%s" value="%s"></div>'
            % (크기, _속성(겉속성 or {}), 라벨글, _e(앞), 찼나, _e(고른글), 크기,
               _e(앞), 줄, _e(이름), _e(고른값)))


# ── 표 ──────────────────────────────────────────────────────────────────────

def 표(머리, 줄들, 크기=기본크기, 겉속성=None):
    """정본 Table. `머리` 는 [글 또는 (글, 속성dict)], `줄들` 은 [[칸, …], …].

    칸은 이미 만들어 둔 HTML 조각을 그대로 받는다(글자는 부르는 쪽에서 막아 둔다).
    """
    th = ""
    for 칸 in 머리:
        글, 속 = 칸 if isinstance(칸, tuple) else (칸, {})
        th += '<th data-s1-part="header-cell" scope="col"%s>%s</th>' % (_속성(속), 글)
    tr = ""
    for 줄 in 줄들:
        칸들 = ""
        for 칸 in 줄:
            글, 속 = 칸 if isinstance(칸, tuple) else (칸, {})
            칸들 += '<td data-s1-part="cell"%s>%s</td>' % (_속성(속), 글)
        tr += '<tr data-s1-part="row">%s</tr>' % 칸들
    return ('<div data-s1-component="table" data-size="%s"%s>'
            '<table data-s1-part="table"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>' % (크기, _속성(겉속성 or {}), th, tr))


def 표머리(머리, 크기=기본크기, 겉속성=None):
    """줄을 한 번에 만들 수 없을 때 — 여는 조각. `표꼬리()` 와 짝이다."""
    th = ""
    for 칸 in 머리:
        글, 속 = 칸 if isinstance(칸, tuple) else (칸, {})
        th += '<th data-s1-part="header-cell" scope="col"%s>%s</th>' % (_속성(속), 글)
    return ('<div data-s1-component="table" data-size="%s"%s>'
            '<table data-s1-part="table"><thead><tr>%s</tr></thead><tbody>'
            % (크기, _속성(겉속성 or {}), th))


def 표꼬리():
    return "</tbody></table></div>"


def 줄(칸들, **속성):
    글 = ""
    for 칸 in 칸들:
        내용, 속 = 칸 if isinstance(칸, tuple) else (칸, {})
        글 += '<td data-s1-part="cell"%s>%s</td>' % (_속성(속), 내용)
    return '<tr data-s1-part="row"%s>%s</tr>' % (_속성(속성), 글)


# ── 칩 · 탭 · 쪽번호 ────────────────────────────────────────────────────────

def 칩(글, 변형="line", 크기="md", 고름=False, 주소=None, **속성):
    """고르는 칩은 변형 line, 그냥 이름표는 solid 다(가이드 §4 Chip)."""
    속 = dict(속성)
    if 변형 == "line":
        속["aria-pressed"] = "true" if 고름 else "false"
    안 = '<span data-s1-part="label">%s</span>' % _e(글)
    잡 = ('data-s1-component="chip" data-variant="%s" data-size="%s" data-break="pc"%s'
         % (변형, 크기, _속성(속)))
    if 주소:
        return '<a href="%s" %s>%s</a>' % (_e(주소), 잡, 안)
    return '<button type="button" %s>%s</button>' % (잡, 안)


def 이름표(글, **속성):
    """누르지 않는 표시 — 정본 Chip Solid SM."""
    return 칩(글, 변형="solid", 크기="sm", **속성)


def 탭(칸들, 크기="md", 이름표글="보기 고르기", **속성):
    """`칸들` 은 [(값, 글, 고름, 주소 또는 None), …]."""
    안 = ""
    for 값, 글, 고름, 주소 in 칸들:
        잡 = ('data-s1-part="tab" role="tab" aria-selected="%s" data-value="%s"'
             % ("true" if 고름 else "false", _e(값)))
        안 += ('<a href="%s" %s>%s</a>' % (_e(주소), 잡, _e(글)) if 주소
               else '<button type="button" %s>%s</button>' % (잡, _e(글)))
    return ('<div data-s1-component="tab" data-size="%s" data-break="pc" role="tablist"'
            ' aria-label="%s"%s>%s</div>' % (크기, _e(이름표글), _속성(속성), 안))


def 쪽번호(지금, 모두, 주소짓기, 이름표글="페이지 넘기기"):
    """정본 Pagination. `주소짓기(n)` 이 그 쪽의 주소를 돌려준다."""
    def 칸(동작, 글자, 갈곳, 꺼짐):
        if 꺼짐:
            return ('<button type="button" data-s1-action="%s" aria-label="%s" disabled>'
                    '<span data-s1-part="icon" data-icon="%s" aria-hidden="true"></span></button>'
                    % (동작, _e(글자), "edge" if 동작 in ("first", "last") else "chevron"))
        return ('<a href="%s" data-s1-action="%s" aria-label="%s">'
                '<span data-s1-part="icon" data-icon="%s" aria-hidden="true"></span></a>'
                % (_e(갈곳), 동작, _e(글자), "edge" if 동작 in ("first", "last") else "chevron"))
    쪽 = ""
    for n in range(1, 모두 + 1):
        지금인가 = ' aria-current="page"' if n == 지금 else ""
        쪽 += ('<a href="%s" data-s1-part="page" data-page="%d"%s>%d</a>'
               % (_e(주소짓기(n)), n, 지금인가, n))
    앞 = (칸("first", "첫 쪽", 주소짓기(1), 지금 <= 1)
          + 칸("previous", "이전 쪽", 주소짓기(max(1, 지금 - 1)), 지금 <= 1))
    뒤 = (칸("next", "다음 쪽", 주소짓기(min(모두, 지금 + 1)), 지금 >= 모두)
          + 칸("last", "마지막 쪽", 주소짓기(모두), 지금 >= 모두))
    return ('<nav data-s1-component="pagination" data-total-pages="%d" data-page="%d"'
            ' aria-label="%s"><span data-s1-part="arrow-group">%s</span>'
            '<span data-s1-part="pages">%s</span>'
            '<span data-s1-part="arrow-group">%s</span></nav>'
            % (모두, 지금, _e(이름표글), 앞, 쪽, 뒤))


# ── 대화창 ──────────────────────────────────────────────────────────────────

def 대화창(칸id, 제목, 속, 단추들="", 겉속성=None, 열림=False):
    """정본 Modal. 여는 쪽은 `data-s1-modal-open="<칸id>"` 를 달면 된다.

    `속` 은 본문 HTML, `단추들` 은 아래 단추 줄 HTML(없으면 발 자리를 두지 않는다).
    """
    발 = '<div data-s1-part="footer">%s</div>' % 단추들 if 단추들 else ""
    갈래 = "dual" if 단추들.count("<button") + 단추들.count("<a ") > 1 else "single"
    return ('<div id="%s" data-s1-component="modal" data-break="pc" data-footer="%s"%s%s>'
            '<div data-s1-part="overlay"></div>'
            '<div data-s1-part="panel" role="dialog" aria-modal="true"'
            ' aria-labelledby="%s-title" tabindex="-1">'
            '<div data-s1-part="content">'
            '<div data-s1-part="header">'
            '<h2 data-s1-part="title" id="%s-title">%s</h2>'
            '<button type="button" data-s1-part="close" aria-label="닫기"></button></div>'
            '<div data-s1-part="body">%s</div></div>%s</div></div>'
            % (_e(칸id), 갈래, _속성(겉속성 or {}), "" if 열림 else " hidden",
               _e(칸id), _e(칸id), _e(제목), 속, 발))


def 닫기단추(글="취소", 변형="secondary", 크기=기본크기):
    return 단추(글, 변형=변형, 크기=크기, **{"data-s1-modal-close": True})
