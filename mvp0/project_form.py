"""과제 만들기 · 과제 고치기 한 장 (river 확정 2026-09-22 — 버전 3의 첫 조각).

**과제를 먼저 만들고, 그 안에서 촬영·검수를 한다.**
지금까지는 촬영기가 접수할 때 적힌 이름으로 과제를 찾고 없으면 새로 만들었다.
그래서 이름이 한 글자만 달라도 과제가 새로 생겨 같은 것이 여럿으로 쪼개졌다.
여기서 사람이 한 번 만들어 두면 접수는 그 과제를 고르기만 한다.

받는 값 넷 — 과제 이름 · 과제 번호 · 화면 코드 · 담당자.
`project` 표에 칸이 없으면 열 때 조용히 더한다(있는 자료는 건드리지 않는다).

화면 부품은 전부 S-1 정본(`assets/css/s1-ui.css`)이다 — Input · Select · Button.
여기 CSS 에 남는 것은 **놓는 자리**뿐이고 값은 전부 토큰이다(river 지시 2026-09-22).
"""
import html
import re
import uuid as uuidmod
from datetime import date

import queries

칸들 = ("code", "service_code", "owner", "created_at")


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def 표채우기(conn):
    """`project` 에 빠진 칸만 더한다. 있는 자료는 그대로 둔다."""
    있는것 = {r["name"] for r in conn.execute("PRAGMA table_info(project)")}
    for 칸 in 칸들:
        if 칸 not in 있는것:
            conn.execute(f"ALTER TABLE project ADD COLUMN {칸} TEXT")
    conn.commit()


def 읽기(conn, project_uuid):
    표채우기(conn)
    return conn.execute(
        "SELECT uuid, name, code, service_code, owner FROM project WHERE uuid=?",
        (project_uuid,)).fetchone()


# ────────────────────────────────────────────────────── 화면
CSS = """
  /* 놓는 자리만. 부품 생김새는 s1-ui.css 가 입힌다. */
  .form-wrap { max-width:560px; margin:0 auto; padding:var(--spacing-32) var(--spacing-28) var(--spacing-64); }
  /* DESIGN_SYSTEM_GAP: Card — 가이드에 그릇 부품이 없다. 표면·테두리·모서리 토큰만 쓴다. */
  .sheet { background:var(--color-surface-raised);
    border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-12); padding:var(--spacing-28);
    display:flex; flex-direction:column; gap:var(--spacing-20); }
  .sheet .hint { margin:0; font-size:var(--font-size-12); color:var(--color-text-state-helper); }
  .sheet [data-s1-component="select"] { width:100%; }
  .acts { display:flex; justify-content:flex-end; gap:var(--spacing-8);
    padding-top:var(--spacing-4); }
  .warn { margin:0; padding:var(--spacing-12) var(--spacing-16);
    border-radius:var(--radius-8); background:var(--color-red-50);
    color:var(--color-status-error); font-size:var(--font-size-12); }
"""


def _입력(이름, 라벨, 값="", 안내="", 자리글="", 필수=False):
    필 = ' required' if 필수 else ''
    도움 = f'<p data-s1-part="message">{_esc(안내)}</p>' if 안내 else ''
    return (f'<div data-s1-component="input" data-size="xsm" data-break="pc">'
            f'<label data-s1-part="label" for="{이름}">{_esc(라벨)}</label>'
            f'<span data-s1-part="field">'
            f'<input data-s1-part="control" type="text" id="{이름}" name="{이름}"'
            f' value="{_esc(값)}" placeholder="{_esc(자리글)}"{필}></span>'
            f'{도움}</div>')


def _담당자(사람들, 고른값):
    """명단에서 고르거나 직접 적는다. 고른 값은 숨은 칸에 담겨 폼과 함께 간다."""
    보기 = [(p["name"], p["name"]) for p in 사람들]
    직접 = 고른값 and 고른값 not in [x for x, _ in 보기]
    보기.append(("__new__", "직접 적기"))

    지금 = "__new__" if 직접 else (고른값 or "")
    글 = "직접 적기" if 직접 else (고른값 or "고르세요")
    찼나 = "true" if 고른값 else "false"

    줄 = ""
    for 값, 이름 in 보기:
        고름 = "true" if 값 == 지금 else "false"
        차례 = "0" if 값 == 지금 else "-1"
        줄 += (f'<div data-s1-part="option" role="option" aria-selected="{고름}"'
               f' tabindex="{차례}" data-value="{_esc(값)}">'
               f'<span data-s1-part="option-label">{_esc(이름)}</span></div>')

    숨김 = '' if 직접 else ' hidden'
    return (
        '<div>'
        '<div data-s1-component="select" data-size="xsm" data-break="pc">'
        '<label data-s1-part="label" for="owner-trigger">담당자</label>'
        f'<button type="button" data-s1-part="trigger" id="owner-trigger"'
        f' aria-haspopup="listbox" aria-expanded="false" data-filled="{찼나}">'
        f'<span data-s1-part="value">{_esc(글)}</span>'
        '<span data-s1-part="icon" aria-hidden="true"></span></button>'
        '<div data-s1-part="panel" hidden>'
        '<div data-s1-component="dropdown" data-type="text" data-size="xsm" role="listbox"'
        ' aria-labelledby="owner-trigger">'
        f'{줄}</div></div>'
        f'<input type="hidden" name="owner" value="{_esc(지금)}">'
        '</div>'
        f'<div id="owner-new-row"{숨김} style="margin-top:var(--spacing-12)">'
        + _입력("owner_new", "담당자 이름", 고른값 if 직접 else "",
                자리글="예) 배가람")
        + '</div></div>')


def _단추(이름, 갈래="primary", 종류="submit", 동작=""):
    누르면 = f' onclick="{동작}"' if 동작 else ''
    return (f'<button type="{종류}" data-s1-component="button" data-variant="{갈래}"'
            f' data-size="xsm" data-break="pc"{누르면}>'
            f'<span data-s1-part="label">{_esc(이름)}</span></button>')


JS = """
(function(){
  var 숨은칸 = document.querySelector('input[type=hidden][name=owner]');
  var 줄 = document.getElementById('owner-new-row');
  if(!숨은칸 || !줄) return;
  숨은칸.addEventListener('change', function(){
    var 직접 = 숨은칸.value === '__new__';
    줄.hidden = !직접;
    if(직접){ var i = 줄.querySelector('input'); if(i) i.focus(); }
  });
})();
"""


def 그리기(conn, 토큰CSS, 과제=None, 알림="", 적은것=None):
    """만들기(과제=None)와 고치기(과제=행)를 같은 폼 한 장으로 그린다."""
    사람들 = queries.list_persons(conn, active_only=True)
    값 = dict(적은것 or {})
    if 과제 is not None and not 적은것:
        값 = {"name": 과제["name"], "code": 과제["code"],
              "service_code": 과제["service_code"], "owner": 과제["owner"]}

    고침 = 과제 is not None
    제목 = "과제 고치기" if 고침 else "과제 만들기"
    보낼곳 = f"/project/{_esc(과제['uuid'])}/edit" if 고침 else "/project/new"
    돌아갈곳 = f"/project/{_esc(과제['uuid'])}" if 고침 else "/"

    경고 = f'<p class="warn">{_esc(알림)}</p>' if 알림 else ''
    속 = f"""<div class="form-wrap"><form class="sheet" method="post" action="{보낼곳}">
      {경고}
      {_입력("name", "과제 이름", 값.get("name", ""),
             자리글="예) 삼성 통근버스 운영 시스템", 필수=True)}
      {_입력("code", "과제 번호", 값.get("code", ""),
             안내="비워 두면 '—' 로 남습니다.", 자리글="예) 2026-041")}
      {_입력("service_code", "화면 코드", 값.get("service_code", ""),
             안내="화면 이름 앞에 붙습니다. TB-WEB-012 의 TB 자리입니다.",
             자리글="예) TB")}
      {_담당자(사람들, 값.get("owner", ""))}
      <div class="acts">
        {_단추("취소", "secondary", "button", f"location.href='{돌아갈곳}'")}
        {_단추("고치기" if 고침 else "만들기")}
      </div>
    </form></div>"""
    머리 = (f'<header><a class="back" href="{돌아갈곳}">← 돌아가기</a>'
          f'<h1>{_esc(제목)}</h1></header>')
    return 머리, 속, f"<script src=\"/assets/js/s1-select.js\"></script><script>{JS}</script>"


# ────────────────────────────────────────────────────── 저장
def _다듬기(form):
    def 한개(이름):
        return (form.get(이름, [""])[0] or "").strip()
    담당 = 한개("owner")
    if 담당 == "__new__":
        담당 = 한개("owner_new")
    코드 = re.sub(r"[^A-Za-z0-9_]", "", 한개("service_code")).upper()
    return {"name": 한개("name"), "code": 한개("code"),
            "service_code": 코드, "owner": 담당}


def _담당자챙기기(conn, 이름):
    """명단에 없는 이름이면 명단에 더한다. 지우지 않는다(이력에 그 이름이 남는다)."""
    if not 이름:
        return
    있나 = conn.execute("SELECT 1 FROM person WHERE name=?", (이름,)).fetchone()
    if not 있나:
        conn.execute("INSERT INTO person (uuid, name, active) VALUES (?,?,1)",
                     (uuidmod.uuid4().hex, 이름))


def 만들기(conn, form):
    """새 과제 한 개. 되돌려 주는 것은 (과제 uuid, 막힌 까닭)."""
    표채우기(conn)
    값 = _다듬기(form)
    if not 값["name"]:
        return None, "과제 이름을 적어 주세요."
    겹침 = conn.execute("SELECT uuid FROM project WHERE name=?", (값["name"],)).fetchone()
    if 겹침:
        return None, "같은 이름의 과제가 이미 있습니다. 다른 이름을 적거나 그 과제로 들어가세요."
    pid = uuidmod.uuid4().hex
    _담당자챙기기(conn, 값["owner"])
    conn.execute(
        "INSERT INTO project (uuid, name, code, service_code, owner, created_at)"
        " VALUES (?,?,?,?,?,?)",
        (pid, 값["name"], 값["code"], 값["service_code"], 값["owner"], date.today().isoformat()))
    conn.commit()
    return pid, ""


def 고치기(conn, project_uuid, form):
    표채우기(conn)
    값 = _다듬기(form)
    if not 값["name"]:
        return False, "과제 이름을 적어 주세요."
    겹침 = conn.execute("SELECT uuid FROM project WHERE name=? AND uuid<>?",
                      (값["name"], project_uuid)).fetchone()
    if 겹침:
        return False, "같은 이름의 과제가 이미 있습니다. 다른 이름을 적어 주세요."
    _담당자챙기기(conn, 값["owner"])
    conn.execute(
        "UPDATE project SET name=?, code=?, service_code=?, owner=? WHERE uuid=?",
        (값["name"], 값["code"], 값["service_code"], 값["owner"], project_uuid))
    conn.commit()
    return True, ""
