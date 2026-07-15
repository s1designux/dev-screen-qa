"""
포털 MVP0 — 로컬 검수 데이터 뷰어 (파이썬 표준 http.server, 추가 설치 0).

현재 조각: 화면 목록 하나만.
  - 실제본(mvp0-real.db)만 노출. 합성본(mvp0.db)은 포털에 띄우지 않는다.
  - 메뉴(프로젝트)별 그룹핑 + 필터(미해결만 / 차수별).
  - 행: 화면명 · 스토리보드ID · Pass/Fail · 미해결 건수.

실행: python portal.py  → http://127.0.0.1:8765
"""
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import db as dbmod
import queries
from constants import UNRESOLVED_STATUSES

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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            q = parse_qs(parsed.query)
            unresolved_only = q.get("unresolved", ["0"])[0] == "1"
            round_filter = int(q["round"][0]) if "round" in q else None
            body = render_list(unresolved_only, round_filter).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path.startswith("/screen/"):
            # 상세는 다음 조각. 지금은 안내만.
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<p style='font-family:sans-serif;padding:40px'>화면 상세는 다음 조각입니다. "
                "<a href='/'>← 목록으로</a></p>".encode("utf-8")
            )
        else:
            self.send_response(404)
            self.end_headers()

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
