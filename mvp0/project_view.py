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
import project_history
import queries
import s1
import s1_tokens
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
    return fixdoc_http.카드(_esc(screen["human_key"]), 셈)


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
  /* 프로젝트 목록 화면의 페이지 이름 — 여기는 왼쪽 메뉴가 없다(river 확정 2026-09-29) */
  .ptitle { margin:0 0 var(--spacing-16); font-size:var(--font-size-20);
    font-weight:var(--font-weight-bold); }
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

  /* 과제 안 — 왼쪽에 붙은 메뉴 줄 + 오른쪽 본문 (river 지시 2026-09-28)
     메뉴는 창 왼쪽 끝에 여백 없이 붙고 맨 위 줄 아래를 끝까지 채운다.
     DESIGN_SYSTEM_GAP: Navigation 이 배포본에 없어 자리만 잡고 색은 navigation 토큰을 쓴다. */
  .pshell { display:flex; align-items:stretch; min-height:calc(100vh - var(--sizing-56)); }
  /* 오른쪽은 회색 바탕이고, 볼 것은 흰 통 안에 든다 — 통은 바탕에서 일정 간격 떨어져 선다.
     (river 지시 2026-09-29 · UVIS 정산 운임표 '최고유류단가 리스트' 통과 같은 모양) */
  .pmain { flex:1; min-width:0; background:var(--color-bg-level-2);
    padding:var(--spacing-12) var(--spacing-12) var(--spacing-24); }
  .acts { display:flex; align-items:center; justify-content:flex-end; gap:var(--spacing-8);
    margin:0 0 var(--spacing-16); }
  .acts:empty { display:none; }
  /* 묶음 이름 — 단추 줄 맨 왼쪽. 두 번 누르면 고치는 칸으로 바뀐다. */
  .gname { display:flex; align-items:center; }
  .gcount { margin-right:auto; padding-left:var(--spacing-4); font-size:var(--font-size-12);
    color:var(--color-text-body-tertiary); }
  .gname .view { font-size:var(--font-size-16); font-weight:var(--font-weight-bold);
    padding:var(--spacing-2) var(--spacing-6); border-radius:var(--radius-6); cursor:text; }
  .gname .view:hover { background:var(--color-bg-level-2); }
  /* 정본 Input 은 display:inline-flex 를 스스로 달고 있어 hidden 만으로는 안 사라진다 */
  .gname .edit[hidden] { display:none; }
  .gname .edit { width:240px; }
  .warn { margin:0 0 var(--spacing-12); padding:var(--spacing-10) var(--spacing-12);
    border:var(--border-width-1) solid var(--color-border-subtle); border-radius:var(--radius-8);
    background:var(--color-surface-raised); font-size:var(--font-size-14);
    color:var(--color-status-error); }
  .lnb.flush { width:220px; flex:none; background:var(--color-navigation-bg);
    border:0; border-right:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:0; padding:0 0 var(--spacing-16); position:sticky; top:0; align-self:stretch; }
  /* 메뉴 맨 위 — 프로젝트 셀렉터. 아래 메뉴와 **다른 구역**으로 보이게 선으로 가른다.
     생김새는 정본 Select 부품이 입히고 여기서는 놓는 자리만 잡는다(river 확정 2026-09-29). */
  .lnbhead { position:relative; padding:var(--spacing-20) var(--spacing-16);
    border-bottom:var(--border-width-1) solid var(--color-border-subtle);
    margin:0 0 var(--spacing-8); }
  .lnbhead .lab { margin:0 0 var(--spacing-6); font-size:var(--font-size-12);
    color:var(--color-text-body-tertiary); }
  .lnbhead .psel { width:100%; }
  .lnbhead .psel [data-s1-part="trigger"] { width:100%; }
  /* 쪽지 자리는 정본이 이미 정해 두었다(셀렉 기준 left:0 · width:100%) — 건드리지 않는다.
     위에서 left·right 를 덮었더니 정본의 width:100% 와 겹쳐 오른쪽으로 밀렸다. */
  .lnbhead .psel [data-s1-part="panel"] { z-index:20; }
  .lnbhead [data-s1-part="option"] { text-decoration:none; }
  .lnbhead [data-s1-part="option"].all { border-top:var(--border-width-1) solid var(--color-border-subtle); }
  .lnb { background:var(--color-navigation-bg); border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-12); padding:var(--spacing-8); position:sticky; top:var(--spacing-20); }
  .lnb .t { font-size:var(--font-size-12); color:var(--color-text-body-tertiary);
    padding:var(--spacing-8) var(--spacing-10) var(--spacing-4); }
  .lnb a, .lnb .head { display:flex; align-items:center; gap:var(--spacing-8);
    height:var(--sizing-34); padding:0 var(--spacing-10); border-radius:var(--radius-8);
    text-decoration:none; color:var(--color-navigation-label-default);
    font-size:var(--font-size-14); }
  .lnb.flush > .lnb-i { height:var(--sizing-44); padding:0 var(--spacing-16); border-radius:0; }
  .lnb.flush > .head { height:var(--sizing-44); padding:0 var(--spacing-16); border-radius:0; }
  .lnb.flush a.sub { padding-left:var(--spacing-48); }
  /* 검수 줄 — 누르면 접히고 펴진다. 생김새는 다른 메뉴 줄과 같다. */
  .lnb .head { width:100%; border:0; background:none; cursor:pointer; font:inherit;
    text-align:left; color:var(--color-navigation-label-default); }
  .lnb .head:hover { background:var(--color-bg-level-2); color:var(--color-navigation-label-hover); }
  /* 접었다고 고른 표시까지 지우지 않는다 — 접힘은 보이기일 뿐이고 지금 자리는 그대로다 */
  .lnb .head.on { color:var(--color-action-primary-default); font-weight:var(--font-weight-bold); }
  .lnb .fold { margin-left:auto; width:var(--sizing-16); height:var(--sizing-16);
    color:var(--color-text-body-tertiary); transform:rotate(90deg); }
  .lnb .head[aria-expanded="true"] .fold { transform:rotate(-90deg); }
  .lnb .grp[hidden] { display:none; }
  /* 묶음 추가 — 메뉴 줄과 같은 자리에 글자만 흐리게 */
  .lnb .addg { margin:0; }
  .lnb .addrow { padding:var(--spacing-4) var(--spacing-16) var(--spacing-8) var(--spacing-48); }
  .lnb .add { display:flex; align-items:center; gap:var(--spacing-4); width:100%;
    height:var(--sizing-34); padding:0 var(--spacing-16) 0 var(--spacing-48); border:0;
    background:none; cursor:pointer; font:inherit; font-size:var(--font-size-12);
    color:var(--color-text-body-tertiary); text-align:left; }
  .lnb .add:hover { color:var(--color-action-primary-default); background:var(--color-bg-level-1); }
  /* 왼쪽 메뉴 줄은 단추가 아니라 '메뉴'다 — 정본 Button 의 칸 모양만 걷고 줄로 눕힌다.
     DESIGN_SYSTEM_GAP: 정본에 왼쪽 메뉴(LNB) 부품이 없다(GNB 만 있다). */
  .lnb [data-s1-component="button"].lnb-i,
  .lnb [data-s1-component="button"].add { min-width:0; justify-content:flex-start; }
  .lnb [data-s1-component="button"] > [data-s1-part="label"] { display:flex; align-items:center;
    gap:var(--spacing-8); width:100%; }
  /* display:flex 를 스스로 달고 있어 hidden 만으로는 안 사라진다(정본 부품과 같은 함정) */
  .lnb .add[hidden] { display:none; }
  .lnb .addrow { padding:0 var(--spacing-12) var(--spacing-8); }
  .lnb .addrow [data-s1-component="input"] { width:100%; }
  .lnb .addrow[hidden] { display:none; }
  .lnb .ic-plus { position:relative; width:var(--sizing-16); height:var(--sizing-16);
    -webkit-mask-image:none; mask-image:none; background:none; }
  .lnb .ic-plus::before, .lnb .ic-plus::after { content:""; position:absolute;
    background:currentColor; border-radius:var(--radius-full); }
  .lnb .ic-plus::before { left:var(--spacing-4); right:var(--spacing-4); top:50%;
    height:var(--border-width-1); transform:translateY(-50%); }
  .lnb .ic-plus::after { top:var(--spacing-4); bottom:var(--spacing-4); left:50%;
    width:var(--border-width-1); transform:translateX(-50%); }
  /* 아이콘 — 정본 아이콘은 /assets/icons/, 가이드에 없어 그린 둘은 /assets/img/ 에 있다.
     mask 로 깔아 글자색을 그대로 따라가게 한다(정본 부품이 아이콘을 다루는 방식과 같다). */
  .ic { flex:none; width:var(--sizing-20); height:var(--sizing-20); background:currentColor;
    -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat;
    -webkit-mask-position:center; mask-position:center;
    -webkit-mask-size:contain; mask-size:contain; }
  .ic-search { -webkit-mask-image:url('/assets/icons/search.svg'); mask-image:url('/assets/icons/search.svg'); }
  .ic-down { width:var(--sizing-16); height:var(--sizing-16);
    -webkit-mask-image:url('/assets/icons/chevron.svg'); mask-image:url('/assets/icons/chevron.svg');
    transform:rotate(90deg); }
  /* DESIGN_SYSTEM_GAP: 사진기·문서 아이콘이 정본 24개에 없어 같은 규격으로 그렸다. */
  .ic-capture { -webkit-mask-image:url('/assets/img/icon-capture.svg'); mask-image:url('/assets/img/icon-capture.svg'); }
  .ic-history { -webkit-mask-image:url('/assets/img/icon-history.svg'); mask-image:url('/assets/img/icon-history.svg'); }
  .lnb a:hover { background:var(--color-bg-level-2); color:var(--color-navigation-label-hover); }
  .lnb a.on { background:var(--color-bg-level-1);
    color:var(--color-action-primary-default); font-weight:var(--font-weight-bold); }
  .lnb a .n { margin-left:auto; font-size:var(--font-size-12); color:var(--color-text-body-tertiary); }
  .lnb a.on .n { color:inherit; }
  /* 아직 볼 것이 없어 못 누르는 칸 — 자리는 그대로 두고 흐리게만 한다 */
  .lnb .off { display:flex; align-items:center; gap:var(--spacing-8); height:var(--sizing-44);
    padding:0 var(--spacing-16); font-size:var(--font-size-14);
    color:var(--color-text-state-disabled); cursor:default; }
  /* 검수 아래 화면 목록 — 한 칸 들여 쓴다 */
  .lnb a.sub { padding-left:var(--spacing-24); font-size:var(--font-size-14); }
  .lnb a.sub .n { font-size:var(--font-size-12); }

  .body { background:var(--color-surface-raised);
    border:var(--border-width-1) solid var(--color-border-subtle);
    border-radius:var(--radius-12); padding:var(--spacing-20); min-height:var(--sizing-128); }
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
  .guide { margin:0 0 var(--spacing-16); font-size:var(--font-size-14);
    color:var(--color-text-body-secondary); }
  .framebar { display:flex; justify-content:flex-end; margin:0 0 var(--spacing-8); }
  /* 촬영 준비는 다른 포트에서 도는 사이트라 창으로 끼운다.
     DESIGN_SYSTEM_GAP: 가이드에 '끼운 창' 부품이 없다. 값은 전부 토큰이다. */
  .capframe { width:100%; height:calc(100vh - 218px); min-height:480px;
    border:var(--border-width-1) solid var(--color-border-subtle); border-radius:var(--radius-8);
    background:var(--color-surface-raised); display:block; }
"""


def _문서(제목, 머리, 속, 토큰CSS, 꼬리=""):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(제목)}</title>
{토큰CSS}<style>{CSS}{project_history.CSS}{fixdoc_http.CSS}{project_form.CSS}</style>{s1_tokens.동작()}</head>
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
          <a class="go" href="/project/new" data-s1-modal-open="과제만들기">
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
    속 = (f'<div class="wrap"><h1 class="ptitle">프로젝트</h1>'
         f'<div class="filters">{칩}</div><div class="cards">{칸}</div></div>')
    return _문서("검수 포털", "", 속, 토큰CSS, project_form.모달(conn))


# ────────────────────────────────────────────────────── 과제 안
def render_project(conn, store, project_uuid, screen_uuid, 토큰CSS, uploads=None, 메뉴="", 알림=""):
    """과제 안 — 왼쪽 메뉴 셋(개발화면 촬영 · 검수 · 이력관리) + 오른쪽 본문.

    아직 찍은 것이 없는 과제는 **촬영만 열린다**(river 지시 2026-09-28).
    검수·이력관리는 볼 것이 없으므로 눌리지 않고, 본문이 캡쳐부터 하라고 안내한다.
    자료가 있으면 처음 여는 자리는 **검수**다.
    """
    project_form.표채우기(conn)
    p = conn.execute("SELECT uuid, name, service_code FROM project WHERE uuid=?",
                     (project_uuid,)).fetchone()
    if not p:
        return None
    목록 = 화면들(conn, store, project_uuid)
    sids = [s["uuid"] for s in 목록 if s["kind"] == "screen"]
    자료있나 = bool(목록)
    메뉴 = 메뉴 if 메뉴 in ("capture", "inspect", "history") else ""
    if screen_uuid and not 메뉴:
        메뉴 = "inspect"
    if not 메뉴:
        메뉴 = "inspect" if 자료있나 else "capture"
    if not 자료있나:
        메뉴 = "capture"      # 볼 것이 없으면 캡쳐 말고는 열지 않는다

    고른 = next((s for s in 목록 if s["uuid"] == screen_uuid), None)
    if 고른 is None:   # 처음 열 때는 시안이 들어 있는 첫 화면을 편다(빈 화면이 먼저 잡히지 않게)
        고른 = (next((s for s in 목록 if s["kind"] == "screen" and s["count"]), None)
              or next((s for s in 목록 if s["kind"] == "screen"), None))

    # ── 왼쪽 메뉴 셋 (아이콘 + 메뉴 이름)
    def 칸(이름, 값, 아이콘, 속=""):
        표 = f'<span class="ic ic-{아이콘}" aria-hidden="true"></span>'
        if not 자료있나 and 값 != "capture":
            return f'<span class="lnb-i off" aria-disabled="true">{표}{_esc(이름)}</span>'
        on = " on" if 메뉴 == 값 else ""
        return (f'<a class="lnb-i{on}" href="/project/{_esc(project_uuid)}?메뉴={값}">'
                f'{표}{_esc(이름)}{속}</a>')

    lnb = _프로젝트셀렉터(conn, project_uuid, p["name"])
    lnb += 칸("개발화면 촬영", "capture", "capture")
    lnb += _검수묶음들(conn, project_uuid, 목록, 고른, 메뉴 == "inspect", 자료있나)
    lnb += 칸("이력관리", "history", "history")

    # ── 오른쪽 본문
    if 메뉴 == "capture":
        본문 = _캡쳐(project_uuid, p, 자료있나)
    elif 메뉴 == "history":
        본문 = project_history.그리기(conn, store, project_uuid)
    elif 고른 and 고른["kind"] == "screen":
        판 = 페이지카드들(conn, 고른)
        본문 = (수정요청알림(conn, 고른, uploads, store)
              + (f'<div class="shelf">{판}</div>' if 판
                 else '<p class="empty">검수 페이지가 없습니다.</p>'))
    else:
        본문 = '<p class="empty">왼쪽에서 검수 화면을 고르세요.</p>'

    표로 = (f'<button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"'
          f' onclick="location.href=\'/screen/{_esc(고른["human_key"])}\'">'
          f'<span data-s1-part="label">표로 보기</span></button>'
          if 메뉴 == "inspect" and 고른 and 고른["kind"] == "screen" and 고른["human_key"] else "")
    결과서 = (f'<button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"'
           f' onclick="window.open(\'/result/{_esc(project_uuid)}?scope=all\',\'_blank\')">'
           f'<span data-s1-part="label">검수결과서</span></button>' if 자료있나 else "")
    # 헤더를 없앴으니 과제 단추는 본문 오른쪽 위로 온다. 돌아가는 길과 과제 이름은 왼쪽 메뉴 맨 위에 있다.
    묶음이름 = _묶음이름(project_uuid, 고른) if 메뉴 == "inspect" else ""
    단추줄 = f"""<div class="acts">{묶음이름}{표로}
        <button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"
          onclick="location.href='/project/{_esc(project_uuid)}/edit'">
          <span data-s1-part="label">과제 고치기</span></button>
        {결과서}</div>"""
    쪽지 = f'<p class="warn">{_esc(알림)}</p>' if 알림 else ""
    속 = (f'<div class="pshell"><nav class="lnb flush">{lnb}</nav>'
         f'<div class="pmain">{쪽지}<div class="body">{단추줄}{본문}</div></div></div>')
    return _문서(f"{p['name']} — 검수 화면", "", 속, 토큰CSS)


def _묶음이름(project_uuid, 고른):
    """단추 줄 맨 왼쪽의 묶음 이름 — 두 번 누르면 고치는 칸이 된다.

    포털에 묶음 이름을 고치는 자리가 따로 없어 여기서 고친다(river 지시 2026-09-29).
    보내는 곳은 이미 있는 화면명 고치기 길이고, `next` 로 이 자리로 되돌아온다.
    """
    if not (고른 and 고른["kind"] == "screen" and 고른.get("human_key")):
        return ""
    되돌아올곳 = f'/project/{project_uuid}?메뉴=inspect&screen={고른["uuid"]}'
    return (f'<form class="gname" method="post" id="gname-form"'
            f' action="/screen/{_esc(고른["human_key"])}/rename">'
            f'<input type="hidden" name="next" value="{_esc(되돌아올곳)}">'
            f'<span class="view" id="gname-view" tabindex="0" role="button"'
            f' title="두 번 누르면 이름을 고칩니다">{_esc(고른["name"])}</span>'
            + s1.입력('name', 고른["name"], 칸id='gname-input', maxlength='40',
                      required=True, 겉속성={"class": "edit", "id": "gname-edit",
                                          "hidden": True},
                      **{"aria-label": "묶음 이름"})
            + '</form>'
            f'<span class="gcount">· {고른["count"]}장</span>')


def _검수묶음들(conn, project_uuid, 목록, 고른, 폄, 자료있나):
    """검수 줄과 그 안에 드는 **묶음 이름들**(로그인 · 공통 · 대시보드 …).

    층은 셋이다 — 검수(메뉴) → 묶음(사람이 나눈 큰 갈래) → 그 안의 화면들.
    맨 아래 층은 왼쪽 메뉴에 늘어놓지 않고 **오른쪽에 카드로** 편다(river 확정 2026-09-29).
    검수 줄을 누르면 접히고 펴진다. 묶음을 누르면 그 묶음의 카드가 오른쪽에 깔린다.
    """
    표 = '<span class="ic ic-search" aria-hidden="true"></span>'
    화살 = '<span class="ic ic-down fold" aria-hidden="true"></span>'
    if not 자료있나:
        return f'<span class="lnb-i off" aria-disabled="true">{표}검수</span>'

    머리 = (f'<button type="button" data-s1-component="button" data-variant="secondary"'
          f' data-size="xsm" data-break="pc" class="lnb-i head{" on" if 폄 else ""}"'
          f' id="lnb-inspect" aria-expanded="{"true" if 폄 else "false"}"'
          f' aria-controls="lnb-groups">'
          f'<span data-s1-part="label">{표}검수{화살}</span></button>')

    칸 = ""
    for x in 목록:
        href = (f"/project/{project_uuid}?메뉴=inspect&screen={x['uuid']}"
                if x["kind"] == "screen" else x["href"])
        on = " on" if 폄 and 고른 and x["uuid"] == 고른["uuid"] and x["kind"] == "screen" else ""
        칸 += (f'<a class="lnb-i sub{on}" href="{_esc(href)}">{_esc(x["name"])}'
               f'<span class="n">{x["count"]}</span></a>')
    더하기 = ('<span class="ic ic-plus" aria-hidden="true"></span>검수 묶음 추가')
    칸 += (f'<form class="addg" method="post" action="/project/{_esc(project_uuid)}/screen/new">'
           f'<button type="button" data-s1-component="button" data-variant="secondary"'
           f' data-size="xsm" data-break="pc" class="add" id="lnb-add-group">'
           f'<span data-s1-part="label">{더하기}</span></button>'
           f'<div class="addrow" id="lnb-add-row" hidden>'
           + s1.입력('이름', '', 칸id='lnb-add-input', maxlength='40', required=True,
                    자리글='묶음 이름', **{"aria-label": "새 검수 묶음 이름"})
           + '</div></form>')

    접 = "" if 폄 else " hidden"
    return f'{머리}<div class="grp" id="lnb-groups"{접}>{칸}</div>'


def _프로젝트셀렉터(conn, project_uuid, 이름):
    """왼쪽 메뉴 맨 위 — 지금 어느 프로젝트인지, 그리고 다른 프로젝트로 바꾸는 자리.

    큰 제목으로 두면 맨 위 줄의 서비스 이름과 다툰다(river 2026-09-29). 그래서
    **고르는 칸**(정본 Select 부품)으로 둔다 — 테두리가 있어 아래 메뉴와도 구역이 갈린다.
    누르면 다른 프로젝트와 '프로젝트 목록 전체 보기'가 펼쳐진다.

    정본 Select 는 값을 고르는 부품이고 여기 옵션은 **가는 길**이라, 안쪽은 링크에
    role="menu" 를 준다(생김새는 정본 그대로, 뜻만 길로 읽힌다). 여닫기는
    `assets/js/lnb-project.js` 가 한다 — 정본 select.js 도 함께 돌지만 값 배선이 없어 서로 다투지 않는다.
    """
    줄 = ""
    for r in conn.execute("SELECT uuid, name FROM project ORDER BY name"):
        if r["uuid"] == project_uuid:
            continue
        줄 += (f'<a data-s1-part="option" role="menuitem" href="/project/{_esc(r["uuid"])}">'
               f'<span data-s1-part="option-label">{_esc(r["name"])}</span></a>')
    줄 += ('<a data-s1-part="option" role="menuitem" class="all" href="/">'
           '<span data-s1-part="option-label">프로젝트 목록 전체 보기</span></a>')
    return f"""<div class="lnbhead">
      <div class="lab" id="lnb-project-label">프로젝트</div>
      <div class="psel" data-s1-component="select" data-size="xsm" data-break="pc">
        <button type="button" data-s1-part="trigger" id="lnb-project"
          aria-haspopup="menu" aria-expanded="false" aria-labelledby="lnb-project-label lnb-project">
          <span data-s1-part="value">{_esc(이름)}</span>
          <span data-s1-part="icon" aria-hidden="true"></span>
        </button>
        <div data-s1-part="panel" id="lnb-project-menu" hidden>
          <div data-s1-component="dropdown" data-type="text" data-size="xsm" role="menu"
            aria-labelledby="lnb-project">{줄}</div>
        </div>
      </div>
    </div>
    <script src="/assets/js/lnb-project.js" defer></script>"""


def _캡쳐(project_uuid, p, 자료있나):
    """개발화면 촬영 — 촬영 준비 화면을 이 자리에 그대로 끼워 넣는다.

    촬영 준비는 다른 포트에서 도는 사이트라 창으로 끼운다. 과제는 주소에 달려 가므로
    거기서 다시 고르지 않는다. 끼운 창이 막히는 자리를 위해 새 창으로 여는 길도 함께 둔다.
    """
    주소 = gnb_bar.촬영시작주소(project_uuid, p["name"], p["service_code"])
    안내 = ('<p class="guide">먼저 개발화면을 찍어 주세요. 찍은 것이 들어오면 검수와 이력관리가 열립니다.</p>'
          if not 자료있나 else "")
    return (f'<h2>개발화면 촬영</h2>{안내}'
            f'<div class="framebar">'
            f'<button type="button" data-s1-component="button" data-variant="secondary" data-size="xsm"'
            f' onclick="window.open(\'{주소}\',\'_blank\')">'
            f'<span data-s1-part="label">새 창으로 열기</span></button></div>'
            f'<iframe class="capframe" src="{_esc(주소)}" title="촬영 준비"></iframe>')


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
