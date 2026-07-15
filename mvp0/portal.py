"""
포털 MVP0 — 로컬 검수 데이터 뷰어 (파이썬 표준 http.server, 추가 설치 0).

현재 조각: 화면 목록 하나만.
  - 실제본(mvp0-real.db)만 노출. 합성본(mvp0.db)은 포털에 띄우지 않는다.
  - 메뉴(프로젝트)별 그룹핑 + 필터(미해결만 / 차수별).
  - 행: 화면명 · 스토리보드ID · Pass/Fail · 미해결 건수.

실행: python portal.py  → http://127.0.0.1:8765
"""
import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import db as dbmod
import queries
from constants import UNRESOLVED_STATUSES, CLOSED_STATUSES

BASE = Path(__file__).resolve().parent
REAL_DB = BASE / "mvp0-real.db"   # 실제본만. 합성본 mvp0.db는 의도적으로 제외.
PORT = 8765


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def render_list(unresolved_only: bool, round_filter):
    conn = dbmod.connect(REAL_DB)
    rows = queries.list_screens(conn, unresolved_only, round_filter)
    conn.close()

    # 필터 링크 상태
    def qs(un, rd):
        parts = []
        if un:
            parts.append("unresolved=1")
        if rd is not None:
            parts.append(f"round={rd}")
        return "/?" + "&".join(parts) if parts else "/"

    chip = lambda label, href, active: (
        f'<a class="chip{" on" if active else ""}" href="{href}">{label}</a>'
    )
    un_filters = (
        chip("전체", qs(False, round_filter), not unresolved_only)
        + chip("미해결만", qs(True, round_filter), unresolved_only)
    )
    round_filters = (
        chip("전체 차수", qs(unresolved_only, None), round_filter is None)
        + chip("1차", qs(unresolved_only, 1), round_filter == 1)
        + chip("2차", qs(unresolved_only, 2), round_filter == 2)
    )

    # 프로젝트(메뉴)별 그룹핑
    groups_html = ""
    if not rows:
        groups_html = '<p class="empty">조건에 맞는 화면이 없습니다.</p>'
    for project, items in groupby(rows, key=lambda r: r["project_name"]):
        items = list(items)
        trs = ""
        for r in items:
            pf = (r["pass_fail"] or "").lower()
            pf_badge = f'<span class="pf {pf}">{_esc(r["pass_fail"] or "—").upper()}</span>'
            rounds = ", ".join(f"{x}차" for x in r["rounds"]) or "—"
            unres = r["unresolved"]
            unres_cls = "num zero" if unres == 0 else "num"
            trs += f"""<tr onclick="location.href='/screen/{_esc(r['human_key'])}'">
              <td class="name">{_esc(r['name'])}</td>
              <td class="key">{_esc(r['human_key'])}</td>
              <td>{_esc(r['platform'])}</td>
              <td class="ctr">{rounds}</td>
              <td class="ctr">{pf_badge}</td>
              <td class="ctr"><span class="{unres_cls}">{unres}</span> / {r['total']}</td>
            </tr>"""
        groups_html += f"""
        <section class="group">
          <h2>{_esc(project)} <span class="muted">· 화면 {len(items)}</span></h2>
          <table>
            <thead><tr>
              <th>화면명</th><th>스토리보드 ID</th><th>플랫폼</th>
              <th class="ctr">검수 차수</th><th class="ctr">Pass/Fail</th><th class="ctr">미해결 / 전체</th>
            </tr></thead>
            <tbody>{trs}</tbody>
          </table>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수 포털 — 화면 목록</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:#1a1a1a;
         margin:0; background:#f6f7f9; }}
  header {{ background:#fff; border-bottom:1px solid #e5e7eb; padding:18px 28px; }}
  h1 {{ font-size:18px; margin:0; }}
  .sub {{ font-size:12px; color:#6b7280; margin-top:4px; }}
  .wrap {{ max-width:1040px; margin:0 auto; padding:20px 28px 60px; }}
  .filters {{ display:flex; gap:18px; align-items:center; margin:6px 0 20px; flex-wrap:wrap; }}
  .filters .lbl {{ font-size:12px; color:#6b7280; }}
  .chip {{ display:inline-block; padding:5px 12px; margin-right:6px; border:1px solid #d1d5db;
          border-radius:999px; font-size:13px; text-decoration:none; color:#374151; background:#fff; }}
  .chip.on {{ background:#111827; color:#fff; border-color:#111827; }}
  .group {{ background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:6px 14px 14px; margin-bottom:18px; }}
  h2 {{ font-size:14px; margin:14px 4px 8px; }}
  .muted {{ color:#9ca3af; font-weight:400; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ padding:10px 12px; border-bottom:1px solid #f0f1f3; text-align:left; }}
  th {{ font-size:11px; color:#6b7280; font-weight:600; }}
  tbody tr {{ cursor:pointer; }}
  tbody tr:hover {{ background:#f9fafb; }}
  .name {{ font-weight:600; }}
  .key {{ font-family:ui-monospace,monospace; color:#4b5563; }}
  .ctr {{ text-align:center; white-space:nowrap; }}
  .pf {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }}
  .pf.fail {{ background:#fef2f2; color:#b42318; }}
  .pf.pass {{ background:#ecfdf3; color:#12864e; }}
  .num {{ font-weight:700; color:#b42318; }}
  .num.zero {{ color:#12864e; }}
  .empty {{ color:#6b7280; padding:30px; text-align:center; }}
  footer {{ max-width:1040px; margin:0 auto; padding:0 28px; font-size:11px; color:#9ca3af; }}
</style></head>
<body>
  <header>
    <h1>검수 포털 <span class="muted" style="font-weight:400;font-size:13px;">· 화면 목록</span></h1>
    <div class="sub">실제 검수 데이터(mvp0-real.db) · 행 클릭 시 상세(다음 조각)</div>
  </header>
  <div class="wrap">
    <div class="filters">
      <span class="lbl">보기</span> {un_filters}
      <span class="lbl">차수</span> {round_filters}
    </div>
    {groups_html}
  </div>
  <footer>미해결 정의 = {" / ".join(UNRESOLVED_STATUSES)} · 원본 = SQLite(DB), 이 화면은 렌더링 뷰</footer>
</body></html>"""


def _status_class(status):
    if status in UNRESOLVED_STATUSES:
        return "open"
    if status in CLOSED_STATUSES:
        return "done"
    return "mid"


def render_detail(human_key: str, unresolved_only: bool):
    conn = dbmod.connect(REAL_DB)
    scr = queries.get_screen(conn, human_key)
    if scr is None:
        conn.close()
        return None
    s = scr["row"]
    runs = scr["runs"]
    issues = queries.issues_of_screen(conn, s["uuid"])   # 전체(번호 고정용)
    persons = queries.list_persons(conn, active_only=True)
    roster = queries.roster_names(conn)
    hist_by_issue = {i["uuid"]: queries.history_of_issue(conn, i["uuid"]) for i in issues}
    conn.close()

    # 1..N 번호를 전체 이슈에 고정 부여
    number = {i["rid"]: n + 1 for n, i in enumerate(issues)}
    shown = issues if not unresolved_only else [i for i in issues if i["status"] in UNRESOLVED_STATUSES]

    # 헤더 메타
    rounds = ", ".join(f"{r['round']}차" for r in runs) or "—"
    pf = (runs[-1]["pass_fail"] if runs else "") or ""
    pf_badge = f'<span class="pf {pf.lower()}">{_esc(pf.upper() or "—")}</span>'

    # 우측(개발) 핀 오버레이 — 좌표(box)는 개발 캡처 기준. 좌측 디자인엔 핀 없음.
    pins = ""
    for i in shown:
        n = number[i["rid"]]
        x, y, w, h = i["box_x"] or 0, i["box_y"] or 0, i["box_w"] or 0, i["box_h"] or 0
        cls = _status_class(i["status"])
        pins += (
            f'<g class="pin {cls}">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4"/>'
            f'<circle cx="{x+14}" cy="{y+14}" r="13"/>'
            f'<text x="{x+14}" y="{y+19}" text-anchor="middle">{n}</text>'
            f"</g>"
        )
    overlay = (
        f'<svg viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMin meet" class="overlay">{pins}</svg>'
    )

    # 이슈 리스트
    def issue_card(i):
        n = number[i["rid"]]
        cls = _status_class(i["status"])
        props = json.loads(i["properties"]) if i["properties"] else []
        props_html = "".join(f'<span class="tag">{_esc(p)}</span>' for p in props)
        loc = f'({i["box_x"]},{i["box_y"]}) {i["box_w"]}×{i["box_h"]}'
        # 이력: 누가·언제·무엇을 (actor가 명단에 없으면 회색+표식)
        rows = ""
        for h in hist_by_issue[i["uuid"]]:
            actor = h["actor"]
            in_roster = actor in roster
            actor_html = (
                f'<span class="actor">{_esc(actor)}</span>' if in_roster
                else f'<span class="actor off" title="담당자 명단에 없음">{_esc(actor or "미지정")} ⚠</span>'
            )
            change = f'{_esc(h["from_status"] or "(신규)")} → {_esc(h["to_status"])}'
            rows += f'<li>{actor_html} · <span class="at">{_esc(h["at"] or "시각 없음")}</span> · {change}</li>'
        return f"""<div class="issue {cls}">
          <div class="ihead">
            <span class="pinno {cls}">{n}</span>
            <span class="badge {cls}">{_esc(i['status'])}</span>
            <b>{_esc(i['logical_element_key'])}</b>
            <span class="cat">{_esc(i['category'])}</span>
          </div>
          <div class="props">{props_html}</div>
          <div class="loc">위치 {loc}</div>
          <ul class="hist">{rows}</ul>
        </div>"""

    issues_html = "".join(issue_card(i) for i in shown) or '<p class="empty">표시할 이슈 없음</p>'

    # 담당자 명단
    roster_html = "".join(
        f'<span class="person">{_esc(p["name"])}'
        f'{" · " + _esc(p["affiliation"]) if p["affiliation"] else ""}</span>'
        for p in persons
    ) or '<span class="muted">명단 비어있음</span>'

    toggle_all = "on" if not unresolved_only else ""
    toggle_un = "on" if unresolved_only else ""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(s['name'])} — 검수 상세</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:#1a1a1a; margin:0; background:#f6f7f9; }}
  header {{ background:#fff; border-bottom:1px solid #e5e7eb; padding:14px 28px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; }}
  header .back {{ text-decoration:none; color:#6b7280; font-size:13px; }}
  header h1 {{ font-size:16px; margin:0; }}
  header .meta {{ font-size:12px; color:#6b7280; }}
  .key {{ font-family:ui-monospace,monospace; }}
  .pf {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }}
  .pf.fail {{ background:#fef2f2; color:#b42318; }} .pf.pass {{ background:#ecfdf3; color:#12864e; }}
  .btn {{ margin-left:auto; font-size:13px; padding:7px 14px; border:1px solid #d1d5db; border-radius:8px; background:#fff; color:#374151; text-decoration:none; }}
  .wrap {{ max-width:1200px; margin:0 auto; padding:20px 28px 60px; }}
  .roster {{ font-size:12px; color:#374151; margin-bottom:14px; }}
  .roster .lbl {{ color:#6b7280; margin-right:8px; }}
  .person {{ display:inline-block; background:#eef2ff; color:#3730a3; border-radius:999px; padding:3px 10px; margin-right:6px; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:22px; }}
  .pane {{ background:#fff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden; }}
  .pane h3 {{ font-size:12px; margin:0; padding:10px 14px; border-bottom:1px solid #f0f1f3; color:#6b7280; }}
  .canvas {{ position:relative; background:repeating-linear-gradient(45deg,#fafafa,#fafafa 10px,#f3f4f6 10px,#f3f4f6 20px); aspect-ratio:16/9; display:flex; align-items:center; justify-content:center; }}
  .canvas .ph {{ color:#9ca3af; font-size:13px; }}
  .overlay {{ position:absolute; inset:0; width:100%; height:100%; }}
  .pin rect {{ fill:rgba(180,35,24,.08); stroke:#b42318; stroke-width:3; }}
  .pin.done rect {{ fill:rgba(18,134,78,.08); stroke:#12864e; }}
  .pin.mid rect {{ fill:rgba(107,114,128,.08); stroke:#6b7280; }}
  .pin circle {{ fill:#b42318; }} .pin.done circle {{ fill:#12864e; }} .pin.mid circle {{ fill:#6b7280; }}
  .pin text {{ fill:#fff; font-size:15px; font-weight:700; }}
  .filters {{ margin:2px 0 12px; }}
  .chip {{ display:inline-block; padding:4px 12px; margin-right:6px; border:1px solid #d1d5db; border-radius:999px; font-size:13px; text-decoration:none; color:#374151; background:#fff; }}
  .chip.on {{ background:#111827; color:#fff; border-color:#111827; }}
  .issue {{ background:#fff; border:1px solid #e5e7eb; border-left-width:4px; border-radius:10px; padding:12px 14px; margin-bottom:10px; }}
  .issue.open {{ border-left-color:#b42318; }} .issue.done {{ border-left-color:#12864e; }} .issue.mid {{ border-left-color:#6b7280; }}
  .ihead {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }}
  .pinno {{ width:22px; height:22px; border-radius:50%; color:#fff; font-size:12px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; background:#b42318; }}
  .pinno.done {{ background:#12864e; }} .pinno.mid {{ background:#6b7280; }}
  .badge {{ font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; background:#fef2f2; color:#b42318; }}
  .badge.done {{ background:#ecfdf3; color:#12864e; }} .badge.mid {{ background:#f3f4f6; color:#374151; }}
  .cat {{ font-size:11px; color:#6b7280; }}
  .props {{ margin:8px 0 4px; }}
  .tag {{ display:inline-block; font-size:11px; background:#f3f4f6; color:#374151; border-radius:6px; padding:2px 8px; margin:0 5px 5px 0; }}
  .loc {{ font-size:11px; color:#9ca3af; font-family:ui-monospace,monospace; }}
  .hist {{ list-style:none; margin:8px 0 0; padding:8px 0 0; border-top:1px dashed #eee; font-size:12px; color:#4b5563; }}
  .hist li {{ margin:2px 0; }}
  .actor {{ font-weight:600; color:#111827; }}
  .actor.off {{ color:#9ca3af; font-weight:400; }}
  .at {{ color:#9ca3af; }}
  .muted {{ color:#9ca3af; }}
  .empty {{ color:#6b7280; padding:20px; }}
</style></head>
<body>
  <header>
    <a class="back" href="/">← 목록</a>
    <h1>{_esc(s['name'])}</h1>
    <span class="meta"><span class="key">{_esc(s['human_key'])}</span> · {_esc(s['platform'])} · {rounds} · {pf_badge}</span>
    <a class="btn" href="/report/{_esc(human_key)}" target="_blank">A4 반출 (미리보기)</a>
  </header>
  <div class="wrap">
    <div class="roster"><span class="lbl">담당자 명단</span>{roster_html}</div>

    <div class="cols">
      <div class="pane">
        <h3>좌 · 디자인 (정답 모습 — 핀 없음)</h3>
        <div class="canvas"><span class="ph">디자인 이미지 자리표시 (실제 연동은 다음 조각)</span></div>
      </div>
      <div class="pane">
        <h3>우 · 개발 (핀 = 발견 위치)</h3>
        <div class="canvas"><span class="ph">개발 이미지 자리표시</span>{overlay}</div>
      </div>
    </div>

    <div class="filters">
      <a class="chip {toggle_all}" href="/screen/{_esc(human_key)}">전체 {len(issues)}</a>
      <a class="chip {toggle_un}" href="/screen/{_esc(human_key)}?unresolved=1">미해결만</a>
    </div>
    {issues_html}
  </div>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        if parsed.path == "/":
            unresolved_only = q.get("unresolved", ["0"])[0] == "1"
            round_filter = int(q["round"][0]) if "round" in q else None
            self._html(render_list(unresolved_only, round_filter))
        elif parsed.path.startswith("/screen/"):
            human_key = parsed.path[len("/screen/"):]
            unresolved_only = q.get("unresolved", ["0"])[0] == "1"
            page = render_detail(human_key, unresolved_only)
            if page is None:
                self._html(f"<p style='font-family:sans-serif;padding:40px'>화면 없음: {_esc(human_key)} "
                           "<a href='/'>← 목록</a></p>", code=404)
            else:
                self._html(page)
        elif parsed.path.startswith("/report/"):
            # A4 반출은 4단계 조각. 지금은 안내만.
            self._html("<p style='font-family:sans-serif;padding:40px'>A4 반출은 다음 조각(4단계)입니다. "
                       "<a href='javascript:history.back()'>← 뒤로</a></p>")
        else:
            self.send_response(404)
            self.end_headers()

    def _html(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # 콘솔 조용히


def main():
    if not REAL_DB.exists():
        raise SystemExit(
            f"{REAL_DB} 없음. 먼저: python load_fixture.py fixtures/tb-web-001.json mvp0-real.db"
        )
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"포털 실행 → http://127.0.0.1:{PORT}  (Ctrl+C 종료)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
