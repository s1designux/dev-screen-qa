"""과제 하나에서 일어난 일을 한 줄씩 시간순으로 모은다 (이력관리).

그동안 표마다 따로 쌓기만 하고 볼 자리가 없던 기록들을 한 곳에 편다.
여기서 **새로 쓰는 것은 없다** — 이미 쌓인 append-only 표를 읽어 줄로 세울 뿐이다
(CLAUDE.md 2번-1 데이터가 원본 · 2번-3 이력은 지우지 않는다).

읽는 표 여섯:
    intake_event          촬영 접수함에서 한 일
    page_design_event     시안을 갈아끼운 일
    page_capture_event    개발 사진을 바꾼 일
    page_move_event       페이지를 다른 화면으로 옮긴 일
    auto_candidate_event  후보를 제외·가변으로 내리거나 되돌린 일
    issue_history         수정필요의 상태가 바뀐 일

표가 아직 없는 자료함도 있어(옛 자료) 읽기는 전부 조용히 넘어간다.
"""
import html

_갈래이름 = {
    "intake": "접수",
    "design": "시안",
    "capture": "개발 사진",
    "move": "페이지 옮김",
    "candidate": "후보",
    "issue": "수정필요",
}


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def _표있나(conn, 이름):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (이름,)).fetchone() is not None


def _줄읽기(conn, sql, args=()):
    try:
        return list(conn.execute(sql, args))
    except Exception:
        return []


def 모으기(conn, store, project_uuid, 최대=300):
    """그 과제의 기록을 최신순으로 모은다. 한 줄 = dict."""
    화면 = {r["uuid"]: {"human_key": r["human_key"], "name": r["name"]} for r in conn.execute(
        "SELECT uuid, human_key, name FROM screen WHERE project_id=?", (project_uuid,))}
    if not 화면:
        페이지 = {}
    else:
        페이지 = {}
        for sid in 화면:
            for r in conn.execute(
                    "SELECT uuid, name, screen_id FROM inspection_page WHERE screen_id=?", (sid,)):
                페이지[r["uuid"]] = {"name": r["name"], "screen_id": r["screen_id"]}

    def 자리(page_id):
        p = 페이지.get(page_id)
        if not p:
            return "", ""
        s = 화면.get(p["screen_id"]) or {}
        key = s["human_key"] if s else ""
        주소 = f"/screen/{key}/page/{page_id}" if key else ""
        이름 = f'{s["name"]} · {p["name"]}' if s else p["name"]
        return 이름, 주소

    줄 = []

    # ── 접수함에서 한 일
    if _표있나(conn, "intake_event"):
        묶음 = [r["id"] for r in _줄읽기(
            conn, "SELECT id FROM intake_batch WHERE project_id=?", (project_uuid,))]
        if 묶음:
            묶음 = set(묶음)
            for r in _줄읽기(conn, "SELECT batch_id, action, detail, actor, at FROM intake_event"):
                if r["batch_id"] not in 묶음:
                    continue
                줄.append({"at": r["at"], "갈래": "intake", "무엇": r["action"] or "접수",
                           "어디": "", "주소": f"/intake/{r['batch_id']}",
                           "누가": r["actor"] or "", "메모": r["detail"] or ""})

    # ── 시안을 갈아끼운 일
    if _표있나(conn, "page_design_event"):
        for r in _줄읽기(conn, "SELECT page_id, from_img, to_img, at, source, note FROM page_design_event"):
            if r["page_id"] not in 페이지:
                continue
            이름, 주소 = 자리(r["page_id"])
            무엇 = "시안을 바꿨습니다" if r["from_img"] else "시안이 들어왔습니다"
            줄.append({"at": r["at"], "갈래": "design", "무엇": 무엇, "어디": 이름, "주소": 주소,
                       "누가": r["source"] or "", "메모": r["note"] or ""})

    # ── 개발 사진을 바꾼 일
    if _표있나(conn, "page_capture_event"):
        for r in _줄읽기(conn, "SELECT page_id, from_img, to_img, at, note FROM page_capture_event"):
            if r["page_id"] not in 페이지:
                continue
            이름, 주소 = 자리(r["page_id"])
            무엇 = "개발 사진을 바꿨습니다" if r["from_img"] else "개발 사진이 들어왔습니다"
            줄.append({"at": r["at"], "갈래": "capture", "무엇": 무엇, "어디": 이름, "주소": 주소,
                       "누가": "", "메모": r["note"] or ""})

    # ── 페이지를 다른 화면으로 옮긴 일
    if _표있나(conn, "page_move_event"):
        for r in _줄읽기(conn, "SELECT page_id, from_screen, to_screen, actor, at, note FROM page_move_event"):
            if r["page_id"] not in 페이지:
                continue
            이름, 주소 = 자리(r["page_id"])
            간곳 = (화면.get(r["to_screen"]) or {}).get("name", "")
            줄.append({"at": r["at"], "갈래": "move",
                       "무엇": f"{간곳} 으로 옮겼습니다" if 간곳 else "다른 화면으로 옮겼습니다",
                       "어디": 이름, "주소": 주소,
                       "누가": r["actor"] or "", "메모": r["note"] or ""})

    # ── 후보 판정
    if _표있나(conn, "auto_candidate_event") and _표있나(conn, "auto_candidate"):
        후보 = {}
        for r in _줄읽기(conn, "SELECT c.id id, c.no no, c.label label, r.page_id page_id"
                             " FROM auto_candidate c JOIN auto_run r ON r.id=c.auto_run_id"):
            if r["page_id"] in 페이지:
                후보[r["id"]] = r
        for r in _줄읽기(conn, "SELECT candidate_id, from_status, to_status, actor, at, note"
                             " FROM auto_candidate_event"):
            c = 후보.get(r["candidate_id"])
            if not c:
                continue
            이름, 주소 = 자리(c["page_id"])
            말 = {"open": "볼 것", "excluded": "제외", "variable": "가변"}
            줄.append({"at": r["at"], "갈래": "candidate",
                       "무엇": f'{말.get(r["from_status"], r["from_status"])}'
                             f' → {말.get(r["to_status"], r["to_status"])}',
                       "어디": f'{이름} · {c["no"]}번 {c["label"]}'.strip(" ·"), "주소": 주소,
                       "누가": r["actor"] or "", "메모": r["note"] or ""})

    # ── 수정필요의 상태가 바뀐 일
    if _표있나(conn, "issue_history"):
        지적 = {}
        for sid in 화면:
            for r in conn.execute(
                    "SELECT uuid, screen_id, description FROM inspection_issue WHERE screen_id=?", (sid,)):
                지적[r["uuid"]] = {"screen_id": r["screen_id"], "description": r["description"]}
        if 지적:
            for r in _줄읽기(conn, "SELECT issue_id, from_status, to_status, actor, at, note, round"
                                 " FROM issue_history"):
                i = 지적.get(r["issue_id"])
                if not i:
                    continue
                s = 화면.get(i["screen_id"]) or {}
                차 = f'{r["round"]}차 · ' if r["round"] else ""
                줄.append({"at": r["at"], "갈래": "issue",
                           "무엇": f'{r["from_status"] or "신규"} → {r["to_status"]}',
                           "어디": f'{차}{s.get("name", "")} · {(i["description"] or "")[:40]}'.strip(" ·"),
                           "주소": f'/screen/{s.get("human_key", "")}' if s else "",
                           "누가": r["actor"] or "", "메모": r["note"] or ""})

    줄.sort(key=lambda x: (x["at"] or ""), reverse=True)
    return 줄[:최대]


CSS = """
  /* 이력관리 — 시간순 한 줄씩. DESIGN_SYSTEM_GAP: 가이드에 Timeline 부품이 없어 자리만 잡는다. */
  .log { display:grid; gap:var(--spacing-2); }
  .log .l { display:grid; grid-template-columns:132px 72px minmax(0,1fr); gap:var(--spacing-12);
    align-items:baseline; padding:var(--spacing-10) var(--spacing-8);
    border-bottom:var(--border-width-1) solid var(--color-border-subtle); }
  .log .l:hover { background:var(--color-bg-level-1); }
  .log .when { font-size:var(--font-size-12); color:var(--color-text-body-tertiary); white-space:nowrap; }
  .log .kind { font-size:var(--font-size-12); color:var(--color-text-state-caption); white-space:nowrap; }
  .log .what { font-size:var(--font-size-14); color:var(--color-text-body-primary); word-break:keep-all; }
  .log .where { display:block; font-size:var(--font-size-12); color:var(--color-text-body-tertiary);
    text-decoration:none; margin-top:var(--spacing-2); }
  .log a.where:hover { color:var(--color-action-primary-default); text-decoration:underline; }
  .log .who { color:var(--color-text-body-tertiary); }
"""


def 그리기(conn, store, project_uuid):
    """이력 목록과 **제목 옆에 붙일 꼬리말** 두 벌을 돌려준다.

    제목('이력관리')은 화면 맨 위 단추 줄이 한 번만 적는다(docs/화면글쓰기규칙.md).
    """
    줄 = 모으기(conn, store, project_uuid)
    if not 줄:
        return '<p class="empty">아직 쌓인 기록이 없습니다.</p>', ""
    칸 = ""
    for x in 줄:
        때 = (x["at"] or "").replace("T", " ")[:16]
        어디 = _esc(x["어디"])
        if 어디 and x["주소"]:
            어디 = f'<a class="where" href="{_esc(x["주소"])}">{어디}</a>'
        elif 어디:
            어디 = f'<span class="where">{어디}</span>'
        누가 = f' <span class="who">— {_esc(x["누가"])}</span>' if x["누가"] else ""
        칸 += (f'<div class="l"><span class="when">{_esc(때)}</span>'
               f'<span class="kind">{_esc(_갈래이름.get(x["갈래"], x["갈래"]))}</span>'
               f'<span class="what">{_esc(x["무엇"])}{누가}{어디}</span></div>')
    return (f'<div class="log">{칸}</div>',
            f' <span class="muted">· 최근 {len(줄)}줄</span>')
