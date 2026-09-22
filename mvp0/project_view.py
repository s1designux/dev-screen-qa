"""포털 첫 화면(과제 카드)과 과제 안(왼쪽 화면 목록 + 디자인 원본 카드).

river 확정 2026-09-21:
- 첫 화면은 **과제 카드**만 놓는다. 무엇을 검수했는지·몇 건인지는 올리지 않는다.
  카드 한 장 = 과제 이름 · 지금 상태 · 최근 작성(마지막 검수기록 날짜) · [검수결과서].
- 카드를 누르면 **왼쪽에 검수 화면 목록, 오른쪽에 검수 페이지 카드**가 깔린다.
  카드에는 **디자인 원본만** 보인다 — 디자인과 개발을 나란히 두면 너무 작아 안 보인다.

값은 전부 DB 에서 그때그때 센다(2번-1 데이터가 원본). 여기서 새로 저장하는 것은 없다.

**부품은 정본 배포본(s1-ui 0.8.1)을 그대로 쓴다** (river 지시 2026-09-21).
생김새를 여기서 다시 적지 않고 `data-s1-component` 만 달아 `assets/css/s1-ui.css` 가 입히게 한다.
여기 CSS 에 남는 것은 **놓는 자리(레이아웃)** 뿐이고, 값은 전부 토큰이다.

가이드에 부품이 없어 자리만 잡아 둔 곳 — 새 생김새를 지어내지 않았다:

    DESIGN_SYSTEM_GAP:
    Card (과제 카드·검수 페이지 카드를 담는 그릇)
    Navigation (왼쪽 검수 화면 목록) — 가이드 §4 Navigation 은 codeStatus: not-started 라 구현 금지
    Badge (카드 위 Pass/Fail 표시) — 칩은 누르는 것이라 가만히 있는 표시에 쓰지 않는다
"""
import html
import json
from urllib.parse import quote

import fixdoc_http
import gnb as gnb_bar
import project_form
import queries
from constants import UNRESOLVED_STATUSES


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


# ────────────────────────────────────────────────────── 상태 한 마디
def 상태(conn, screen_ids):
    """과제 카드에 적는 한 마디. 차수와 미해결만 보고 정한다.

    미해결이 남아 있으면 '진행중', 다 처리했으면 'N차 완료',
    모든 화면이 PASS 면 '검수완료', 아직 지적이 없으면 '검수준비'.
    """
    if not screen_ids:
        return "검수준비", "wait"
    ph = ",".join("?" for _ in screen_ids)
    st = ",".join("?" for _ in UNRESOLVED_STATUSES)
    미해결 = conn.execute(
        f"SELECT COUNT(*) c FROM inspection_issue WHERE screen_id IN ({ph}) AND status IN ({st})",
        (*screen_ids, *UNRESOLVED_STATUSES)).fetchone()["c"]
    전체 = conn.execute(
        f"SELECT COUNT(*) c FROM inspection_issue WHERE screen_id IN ({ph})",
        tuple(screen_ids)).fetchone()["c"]
    차수 = conn.execute(
        f"SELECT MAX(round) m FROM inspection_run WHERE screen_id IN ({ph})",
        tuple(screen_ids)).fetchone()["m"] or 1
    if 미해결:
        return f"{차수}차 진행중", "going"
    if 전체:
        판정 = [queries.screen_pass_fail(conn, sid) for sid in screen_ids]
        if 판정 and all(x == "pass" for x in 판정):
            return "검수완료", "done"
        return f"{차수}차 완료", "round"
    return "검수준비", "wait"


def 최근작성(conn, screen_ids):
    """마지막 검수기록 날짜(river 확정). 기록이 없으면 빈 칸."""
    if not screen_ids:
        return ""
    ph = ",".join("?" for _ in screen_ids)
    값 = conn.execute(
        f"SELECT MAX(created_at) m FROM inspection_run WHERE screen_id IN ({ph})",
        tuple(screen_ids)).fetchone()["m"]
    return (값 or "").replace("T", " ")[:10]


def 과제번호(conn, project_uuid, 적힌번호=None):
    """과제 카드에 적는 번호.

    과제를 만들 때 사람이 적은 번호가 있으면 그것을 쓴다(river 확정 2026-09-22).
    없으면 예전처럼 화면 사람키의 앞머리({SERVICE}-{PLATFORM}-{NNN} 의 SERVICE, 7번)를 모아 보인다.
    """
    if (적힌번호 or "").strip():
        return 적힌번호.strip()
    앞 = []
    for r in conn.execute("SELECT human_key FROM screen WHERE project_id=?", (project_uuid,)):
        코드 = (r["human_key"] or "").split("-")[0]
        if 코드 and 코드 not in 앞:
            앞.append(코드)
    return " · ".join(앞)


def 차수이력(conn, screen_ids):
    """차수마다 [fail 페이지 / 전체 페이지]. 카드에 두 줄까지만 보인다.

    판정은 그 차수의 검수 기록(inspection_run)에 남은 것을 그대로 센다.
    """
    if not screen_ids:
        return []
    ph = ",".join("?" for _ in screen_ids)
    쪽수 = conn.execute(
        f"SELECT COUNT(*) c FROM inspection_page WHERE screen_id IN ({ph}) AND removed_at IS NULL",
        tuple(screen_ids)).fetchone()["c"]
    줄 = []
    for r in conn.execute(
            f"""SELECT round, SUM(pass_fail='fail') f FROM inspection_run
                WHERE screen_id IN ({ph}) GROUP BY round ORDER BY round""", tuple(screen_ids)):
        줄.append((f"{r['round']}차", f"{r['f'] or 0} / {쪽수}p fail"))
    return 줄


# ────────────────────────────────────────────────────── 과제 안의 화면 목록
def 화면들(conn, store, project_uuid):
    """그 과제의 검수 화면 + 아직 화면이 되지 않은 촬영 묶음.

    첫 화면이 쓰던 규칙 그대로다 — 촬영 묶음이 이미 화면으로 들어왔으면 화면 쪽만 남긴다.
    """
    쓴것 = []
    for r in conn.execute(
            "SELECT uuid, human_key, name, platform FROM screen WHERE project_id=? ORDER BY human_key",
            (project_uuid,)):
        쓴것.append({"uuid": r["uuid"], "name": r["name"], "platform": r["platform"],
                    "href": f"?screen={r['uuid']}", "kind": "screen",
                    "count": len(queries.pages_of_screen(conn, r["uuid"])),
                    "human_key": r["human_key"]})
    묶음 = [g for g in store.screen_groups() if g.get("project_id") == project_uuid]
    담긴화면 = {sid for g in 묶음 for sid in g["screen_ids"]}
    쓴것 = [s for s in 쓴것 if s["uuid"] not in 담긴화면]
    for g in 묶음:
        쓴것.append({"uuid": g.get("item_id"), "name": g["name"], "platform": g["platform"],
                    "href": g["href"], "kind": "batch", "count": g["page_count"],
                    "human_key": ""})
    return 쓴것


def 페이지카드들(conn, screen):
    """검수 페이지 카드 — 디자인 원본·이름·Pass/Fail 표시(오른쪽 위).

    지적 수는 올리지 않는다(river). 판정만 한눈에 보이면 된다.
    """
    pages = queries.pages_of_screen(conn, screen["uuid"])
    그림 = {r["uuid"]: r["design_img"] for r in conn.execute(
        "SELECT uuid, design_img FROM inspection_page WHERE screen_id=?", (screen["uuid"],))}
    칸 = ""
    for p in pages:
        img = 그림.get(p["uuid"])
        속 = (f'<img src="/uploads/{_esc(img)}" alt="" loading="lazy">' if img
              else '<span class="noimg">시안 없음</span>')
        판 = p["pass_fail"]
        표 = (f'<span class="pf {판}">{"FAIL" if 판 == "fail" else "PASS"}</span>' if 판
              else '<span class="pf none">미검수</span>')
        칸 += (f'<a class="pcard" href="/screen/{_esc(screen["human_key"])}/page/{_esc(p["uuid"])}">'
               f'<span class="shot">{속}{표}</span>'
               f'<span class="pname">{_esc(p["name"])}</span></a>')
    return 칸


def 수정요청알림(conn, screen, uploads, store):
    """수정요청서가 만들어져 있으면 시안 카드 위에 한 줄 알린다.

    숫자·말·모양은 옛 표 목록의 주의 칸과 같은 것을 쓴다(사람이 보는 말이 두 곳에서 같아야 한다).
    자료가 없으면 아무것도 내지 않는다.
    """
    if not uploads or not screen.get("human_key"):
        return ""
    pages = queries.pages_of_screen(conn, screen["uuid"])
    if not pages:
        return ""
    row = conn.execute("SELECT dev_keys FROM screen WHERE uuid=?", (screen["uuid"],)).fetchone()
    try:
        주소 = (json.loads((row["dev_keys"] if row else None) or "[]") or [""])[0]
    except Exception:
        주소 = ""
    셈 = fixdoc_http.셈하기(uploads, pages, screen["human_key"], 주소, store)
    if 셈 is None:
        return ""
    return fixdoc_http.카드(_esc(screen["human_key"]), 셈, 부품=True)


# ────────────────────────────────────────────────────── 겉모습
CSS = """
  /* 여기에는 **놓는 자리**만 적는다. 부품 생김새는 s1-ui.css 가 입힌다.
     값은 전부 토큰이다(원시 px·헥사 없음). */
  * { box-sizing:border-box; }
  body { font-family:Pretendard,-apple-system,"Apple SD Gothic Neo",sans-serif;
    color:var(--color-text-title-primary); margin:0; background:var(--color-bg-level-1);
    font-size:var(--font-size-14); }
  header { background:var(--color-surface-raised); border-bottom:var(--border-width-1) solid var(--color-border-subtle);
    padding:var(--spacing-16) var(--spacing-28); display:flex; align-items:center;
    gap:var(--spacing-12); flex-wrap:wrap; }
  h1 { font-size:var(--font-size-18); margin:0; }
  .sub { font-size:var(--font-size-12); color:var(--color-text-body-tertiary); }
  .back { font-size:var(--font-size-12); color:var(--color-text-body-tertiary); text-decoration:none; }
  .right { margin-left:auto; display:flex; align-items:center; gap:var(--spacing-8); }
  .wrap { max-width:1180px; margin:0 auto; padding:var(--spacing-24) var(--spacing-28) var(--spacing-64); }
  .filters { display:flex; gap:var(--spacing-6); flex-wrap:wrap; margin:0 0 var(--spacing-20); }

  /* DESIGN_SYSTEM_GAP: Card — 가이드에 그릇 부품이 없다. 표면·테두리·모서리 토큰만 쓴다. */
  .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
    gap:var(--spacing-16); grid-auto-rows:1fr; }
  .pj { height:100%; position:relative; display:flex; flex-direction:column; gap:var(--spacing-16);
    padding:var(--spacing-20); background:var(--color-surface-raised);
    border:var(--border-width-1) solid var(--color-border-subtle); border-radius:var(--radius-12); }
  .pj:hover { border-color:var(--color-border-focus); box-shadow:var(--shadow-dropdown); }
  .pj .head { display:flex; align-items:flex-start; gap:var(--spacing-10); }
  .pj .go { text-decoration:none; color:inherit; }
  .pj .go::after { content:""; position:absolute; inset:0; border-radius:var(--radius-12); }
  .pj .nm { font-size:var(--font-size-16); font-weight:var(--font-weight-bold); word-break:keep-all; }
  .pj .head .st { margin-left:auto; }   /* 카드에서는 오른쪽 위에 붙는다 */
  .pj .foot { margin-top:auto; display:flex; justify-content:flex-end; position:relative; z-index:1; }

  /* '과제 만들기' 카드 — 다른 카드와 같은 그릇에 가운데 정렬만 다르다.
     DESIGN_SYSTEM_GAP: 가이드에 '새로 만들기 카드' 부품이 없다. 값은 전부 토큰이다. */
  .pj.new { align-items:center; justify-content:center; border-style:dashed;
    background:var(--color-bg-level-1); min-height:var(--sizing-128); }
  .pj.new .go { display:flex; flex-direction:column; align-items:center;
    gap:var(--spacing-10); color:var(--color-text-body-tertiary); }
  .pj.new:hover .go { color:var(--color-action-primary-default); }
  .pj.new .nm { font-size:var(--font-size-14); font-weight:var(--font-weight-medium); }
  /* 더하기 표 — 가로선·세로선 둘로 그린다(아이콘 목록에 '더하기'가 없다). */
  .pj.new .plus { position:relative; width:var(--sizing-24); height:var(--sizing-24); }
  .pj.new .plus::before, .pj.new .plus::after { content:""; position:absolute;
    background:currentColor; border-radius:var(--radius-full); }
  .pj.new .plus::before { left:0; right:0; top:50%; height:var(--border-width-2);
    transform:translateY(-50%); }
  .pj.new .plus::after { top:0; bottom:0; left:50%; width:var(--border-width-2);
    transform:translateX(-50%); }

  /* 상태 한 마디 — 글자와 점만. 색은 역할 토큰에서 온다. */
  .st { display:inline-flex; align-items:center; gap:var(--spacing-6); flex:none;
    font-size:var(--font-size-12); font-weight:var(--font-weight-medium);
    color:var(--color-text-body-tertiary); white-space:nowrap; }
  .st::before { content:""; flex:none; width:var(--spacing-8); height:var(--spacing-8);
    border-radius:var(--radius-full); background:var(--color-text-state-disabled); }
  .st.going { color:var(--color-text-state-accent); }
  .st.going::before { background:var(--color-text-state-accent); }
  .st.done { color:var(--color-status-success); }
  .st.done::before { background:var(--color-status-success); }
  .st.round::before { background:var(--color-text-state-caption); }

  /* 간단 이력 — 이름과 값 두 칸 */
  .hist { margin:0; display:grid; gap:var(--spacing-6); font-size:var(--font-size-12); }
  .hist .row { display:flex; gap:var(--spacing-10); }
  .hist dt { flex:0 0 64px; color:var(--color-text-body-tertiary); }
  .hist dd { margin:0; color:var(--color-text-body-secondary); }

  /* 과제 안 — 왼쪽 목록 + 오른쪽 시안 카드
     DESIGN_SYSTEM_GAP: Navigation 이 배포본에 없어 자리만 잡고 색은 navigation 토큰을 쓴다. */
  .split { display:grid; grid-template-columns:220px minmax(0,1fr); gap:var(--spacing-20); align-items:start; }
  .lnb { background:var(--color-navigation-bg); border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-12); padding:var(--spacing-8); position:sticky; top:var(--spacing-20); }
  .lnb .t { font-size:var(--font-size-12); color:var(--color-text-body-tertiary);
    padding:var(--spacing-8) var(--spacing-10) var(--spacing-4); }
  .lnb a { display:flex; align-items:center; gap:var(--spacing-8); height:var(--sizing-34);
    padding:0 var(--spacing-10); border-radius:var(--radius-8); text-decoration:none;
    color:var(--color-navigation-label-default); font-size:var(--font-size-14); }
  .lnb a:hover { background:var(--color-bg-level-2); color:var(--color-navigation-label-hover); }
  .lnb a.on { background:var(--color-action-primary-subtle);
    color:var(--color-navigation-label-selected); font-weight:var(--font-weight-bold); }
  .lnb a .n { margin-left:auto; font-size:var(--font-size-12); color:var(--color-text-body-tertiary); }
  .lnb a.on .n { color:inherit; }

  .body { background:var(--color-surface-raised); border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-12); padding:var(--spacing-20); }
  .body h2 { font-size:var(--font-size-14); margin:0 0 var(--spacing-16); }
  .body h2 .muted { color:var(--color-text-body-tertiary); font-weight:var(--font-weight-regular); }
  .shelf { display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr));
    gap:var(--spacing-16); grid-auto-rows:1fr; }
  .pcard { height:100%; display:flex; flex-direction:column; gap:var(--spacing-8);
    text-decoration:none; color:inherit; }
  .pcard .shot { display:flex; align-items:center; justify-content:center; height:170px; overflow:hidden;
    background:var(--color-bg-level-2); border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-8); }
  .pcard:hover .shot { border-color:var(--color-border-focus); }
  .pcard img { max-width:100%; max-height:100%; object-fit:contain; display:block; }
  .pcard .noimg { font-size:var(--font-size-12); color:var(--color-text-state-helper); }
  /* DESIGN_SYSTEM_GAP: Badge — 가만히 있는 Pass/Fail 표시. 색·크기는 토큰만 쓴다. */
  .pcard .shot { position:relative; }
  .pf { position:absolute; top:var(--spacing-6); right:var(--spacing-6);
    padding:var(--spacing-2) var(--spacing-8); border-radius:var(--radius-6);
    font-size:var(--font-size-10); font-weight:var(--font-weight-bold); line-height:normal; }
  .pf.fail { background:var(--color-red-50); color:var(--color-red-500); }
  .pf.pass { background:var(--color-action-primary-subtle); color:var(--color-action-primary-pressed); }
  .pf.none { background:var(--color-bg-level-2); color:var(--color-text-body-tertiary); }
  .pcard .pname { font-size:var(--font-size-12); color:var(--color-text-body-secondary);
    line-height:1.5; word-break:keep-all; }
  .empty { color:var(--color-text-body-tertiary); padding:var(--spacing-32); text-align:center; }
"""


def _문서(제목, 머리, 속, 토큰CSS, 꼬리=""):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(제목)}</title>
{토큰CSS}<style>{CSS}{fixdoc_http.CSS}{project_form.CSS}</style></head>
<body data-s1-break="pc">{gnb_bar.바("project")}{머리}{속}{꼬리}</body></html>"""


# ────────────────────────────────────────────────────── 첫 화면 = 과제 카드
# 칩으로 고르는 묶음. 카드의 상태 한 마디를 셋으로 모아 놓은 것이다.
묶음 = {"wait": "검수준비", "going": "진행중", "round": "진행중", "done": "검수완료"}
칩차례 = ("전체", "검수준비", "진행중", "검수완료")


def render_home(conn, 고른묶음, 토큰CSS):
    project_form.표채우기(conn)
    과제 = []
    for p in conn.execute(
            "SELECT uuid, name, code, owner FROM project ORDER BY name"):
        sids = [r["uuid"] for r in conn.execute(
            "SELECT uuid FROM screen WHERE project_id=?", (p["uuid"],))]
        말, 갈래 = 상태(conn, sids)
        과제.append({"uuid": p["uuid"], "name": p["name"], "말": 말, "갈래": 갈래,
                   "묶음": 묶음[갈래], "번호": 과제번호(conn, p["uuid"], p["code"]),
                   "담당": p["owner"] or "", "날": 최근작성(conn, sids),
                   "이력": 차수이력(conn, sids)})

    센것 = {이름: sum(1 for x in 과제 if x["묶음"] == 이름) for 이름 in 칩차례[1:]}
    센것["전체"] = len(과제)
    고른묶음 = 고른묶음 if 고른묶음 in 칩차례 else "전체"
    칩 = ""
    for 이름 in 칩차례:
        주소 = "/" if 이름 == "전체" else "/?상태=" + quote(이름)
        고름 = "true" if 이름 == 고른묶음 else "false"
        칩 += (f'<button type="button" data-s1-component="chip" data-variant="line"'
               f' data-size="md" data-break="pc" aria-pressed="{고름}"'
               f' onclick="location.href=\'{주소}\'">'
               f'<span data-s1-part="label">{_esc(이름)} {센것[이름]}</span></button>')

    보일것 = [x for x in 과제 if 고른묶음 == "전체" or x["묶음"] == 고른묶음]
    칸 = """
        <div class="pj new">
          <a class="go" href="/project/new">
            <span class="plus" aria-hidden="true"></span>
            <span class="nm">과제 만들기</span>
          </a>
        </div>"""
    for x in 보일것:
        줄 = f'<div class="row"><dt>과제번호</dt><dd>{_esc(x["번호"]) or "—"}</dd></div>'
        줄 += f'<div class="row"><dt>담당자</dt><dd>{_esc(x["담당"]) or "—"}</dd></div>'
        줄 += f'<div class="row"><dt>최근 작성</dt><dd>{_esc(x["날"]) or "—"}</dd></div>'
        for 차, 값 in x["이력"]:
            줄 += f'<div class="row"><dt>{_esc(차)}</dt><dd>{_esc(값)}</dd></div>'
        # 카드 전체가 누르는 자리다. 안에 또 누를 것(검수결과서)을 겹치지 않으려고
        # 링크를 카드 위에 깔고(::after) 단추는 그 위에 올린다 — a 안에 a 를 넣지 않는다.
        칸 += f"""
        <div class="pj">
          <div class="head">
            <a class="go" href="/project/{_esc(x['uuid'])}"><span class="nm">{_esc(x['name'])}</span></a>
            <span class="st {x['갈래']}">{_esc(x['말'])}</span>
          </div>
          <dl class="hist">{줄}</dl>
          <span class="foot">
            <button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"
              onclick="window.open('/result/{_esc(x['uuid'])}?scope=all','_blank')">
              <span data-s1-part="label">검수결과서</span></button>
          </span>
        </div>"""
    속 = f'<div class="wrap"><div class="filters">{칩}</div><div class="cards">{칸}</div></div>'
    return _문서("검수 포털", "", 속, 토큰CSS)


# ────────────────────────────────────────────────────── 과제 안
def render_project(conn, store, project_uuid, screen_uuid, 토큰CSS, uploads=None):
    p = conn.execute("SELECT uuid, name FROM project WHERE uuid=?", (project_uuid,)).fetchone()
    if not p:
        return None
    목록 = 화면들(conn, store, project_uuid)
    sids = [s["uuid"] for s in 목록 if s["kind"] == "screen"]
    말, 갈래 = 상태(conn, sids)

    고른 = next((s for s in 목록 if s["uuid"] == screen_uuid), None)
    if 고른 is None:   # 처음 열 때는 시안이 들어 있는 첫 화면을 편다(빈 화면이 먼저 잡히지 않게)
        고른 = (next((s for s in 목록 if s["kind"] == "screen" and s["count"]), None)
              or next((s for s in 목록 if s["kind"] == "screen"), None))

    lnb = '<div class="t">검수 화면</div>'
    for s in 목록:
        href = (f"/project/{project_uuid}?screen={s['uuid']}" if s["kind"] == "screen" else s["href"])
        on = " on" if 고른 and s["uuid"] == 고른["uuid"] and s["kind"] == "screen" else ""
        lnb += (f'<a class="lnb-i{on}" href="{_esc(href)}">{_esc(s["name"])}'
                f'<span class="n">{s["count"]}</span></a>')

    if 고른 and 고른["kind"] == "screen":
        칸 = 페이지카드들(conn, 고른)
        본문 = (수정요청알림(conn, 고른, uploads, store)
              + f'<h2>{_esc(고른["name"])} <span class="muted">· {고른["count"]}장</span></h2>'
              + (f'<div class="shelf">{칸}</div>' if 칸
                 else '<p class="empty">검수 페이지가 없습니다.</p>'))
    else:
        본문 = '<p class="empty">왼쪽에서 검수 화면을 고르세요.</p>'

    표로 = (f'<button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"'
          f' onclick="location.href=\'/screen/{_esc(고른["human_key"])}\'">'
          f'<span data-s1-part="label">표로 보기</span></button>'
          if 고른 and 고른["kind"] == "screen" and 고른["human_key"] else "")
    머리 = f"""<header>
      <a class="back" href="/">← 과제 목록</a>
      <h1>{_esc(p['name'])}</h1>
      <span class="st {갈래}">{_esc(말)}</span>
      <span class="right">{표로}
        <button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"
          onclick="location.href='/project/{_esc(project_uuid)}/edit'">
          <span data-s1-part="label">과제 고치기</span></button>
        <button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"
          onclick="window.open('/result/{_esc(project_uuid)}?scope=all','_blank')">
          <span data-s1-part="label">검수결과서</span></button></span>
    </header>"""
    속 = f'<div class="wrap"><div class="split"><nav class="lnb">{lnb}</nav><div class="body">{본문}</div></div></div>'
    return _문서(f"{p['name']} — 검수 화면", 머리, 속, 토큰CSS)


# ────────────────────────────────────────────────────── 과제 만들기 · 고치기
def render_project_form(conn, 토큰CSS, project_uuid=None, 알림="", 적은것=None):
    """과제 한 개를 만들거나 고치는 화면. 없는 과제면 None."""
    과제 = None
    if project_uuid:
        과제 = project_form.읽기(conn, project_uuid)
        if 과제 is None:
            return None
    머리, 속, 꼬리 = project_form.그리기(conn, 토큰CSS, 과제, 알림, 적은것)
    제목 = "과제 고치기" if 과제 is not None else "과제 만들기"
    return _문서(제목, 머리, 속, 토큰CSS, 꼬리)
