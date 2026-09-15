"""
포털 MVP0 — 로컬 검수 데이터 뷰어 (파이썬 표준 http.server, 추가 설치 0).

세 화면:
  - 화면 목록      /                         : 화면별 검수 페이지 수 + 미해결 합산 + 종합 Pass/Fail
  - 화면 상세      /screen/<key>             : 그 화면의 '검수 페이지 목록' (2단 아님)
  - 페이지 상세    /screen/<key>/page/<uuid> : 좌(디자인·핀 없음)/우(개발·번호 핀) 2단 + 이슈 카드

실제본(mvp0-real.db)만 노출. 합성본(mvp0.db)은 띄우지 않는다.
핀↔카드 연동·다중 열 카드는 다음(2차) 조각.

실행: python portal.py  → http://127.0.0.1:8765
"""
import html
import os
import time
import intake_store
import intake_http
import design_plan_http
import issue_categories
import app_layout
import card_view
import comparison_view
import auto_inspect
import design_receive
import policy_ui
import policy_api
import fixdoc_http
import fixdoc_view
import page_move

import json
import uuid as uuidmod
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote, unquote

import s1_tokens
# S-1 디자인가이드 토큰 네 장 — 포털 화면이 var(--…) 로 쓸 수 있게 머리에 잇는다.
_토큰CSS = s1_tokens.링크()

import db as dbmod
import queries
from constants import UNRESOLVED_STATUSES, CLOSED_STATUSES, MAX_ROUNDS

BASE = Path(__file__).resolve().parent
import sys as _sys
if str(BASE.parent) not in _sys.path:
    _sys.path.insert(0, str(BASE.parent))
import 설정 as 설정                                    # 이 컴퓨터에서만 쓰는 값 (설정.json → 환경변수 → 기본값)

REAL_DB = 설정.자리("포털.자료함")   # 실제본만. 합성본 mvp0.db는 의도적으로 제외.
UPLOADS = 설정.자리("포털.그림보관")      # 업로드된 PNG 로컬 저장 (경로만 DB, 파일은 .gitignore)
PORT = 설정.값("포털.포트")
# 기본은 이 컴퓨터에서만. 설정.json 의 포털.동료공유 를 true 로 하면 같은 네트워크의 동료도 들어올 수 있다.
HOST = "0.0.0.0" if 설정.값("포털.동료공유") else "127.0.0.1"


def _is_private_ip(addr):
    """사무실 안에서만 쓰는 주소인지. 밖에서 온 요청은 받지 않는다."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def _lan_ip():
    """같은 네트워크에서 쓸 수 있는 이 컴퓨터의 주소."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
AUTORELOAD = os.environ.get("QA_PORTAL_AUTORELOAD") == "1"   # run_portal.py 가 켤 때만 1
BOOT_ID = str(time.time())                                    # 다시 켜지면 바뀐다 → 열어 둔 화면이 새로고침


def intake():
    return intake_store.Store(REAL_DB, UPLOADS)


def _multipart_file(body, content_type):
    """multipart/form-data에서 첫 파일 파트의 바이트를 꺼낸다 (순수 stdlib)."""
    ct = content_type or ""
    if "boundary=" not in ct:
        return None
    boundary = ct.split("boundary=", 1)[1].strip().strip('"')
    marker = b"--" + boundary.encode()
    for seg in body.split(marker):
        if b"\r\n\r\n" not in seg:
            continue
        head, data = seg.split(b"\r\n\r\n", 1)
        if b"filename=" not in head:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        return data
    return None


def _png_size(data):
    """PNG 헤더(IHDR)에서 원본 가로·세로를 읽는다. PNG 아니면 None (Pillow 등 불필요)."""
    if not data or len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def _pf_badge(v):
    v = (v or "")
    return f'<span class="pf {v.lower()}">{_esc(v.upper() if v else "미검수")}</span>'


def _upl(human_key, page_uuid, side, rnd=None):
    """PNG 업로드 컨트롤 (선택 즉시 제출 → 로컬 저장 → 표시). dev는 그 차수(run)에 저장."""
    linked = intake().page_link(page_uuid)
    if linked:
        if side == 'design':
            return '<button type="button" class="upl" onclick="document.getElementById(&quot;design-picker&quot;).showModal()">다른 시안으로 변경</button>'
        return '<span class="upl">촬영 원본 보관됨</span>'
    q = f"?side={side}" + (f"&round={rnd}" if rnd is not None else "")
    action = f"/screen/{_esc(human_key)}/page/{_esc(page_uuid)}/upload{q}"
    label = '디자인' if side == 'design' else '개발화면'
    return (
        f'<span class="upl-group">'
        f'<form class="upl" method="post" enctype="multipart/form-data" action="{action}">'
        f'<label>PNG 업로드<input type="file" name="file" accept="image/png" '
        f'onchange="this.form.submit()"></label></form></span>'
    )


def _status_class(status):
    if status in UNRESOLVED_STATUSES:
        return "open"
    if status in CLOSED_STATUSES:
        return "done"
    return "mid"


def _status_at(history, rnd):
    """이슈의 '해당 차수 시점 상태' = round<=rnd 인 마지막 history의 to_status.
    (round None은 1차로 간주). 그 차수에 아직 없던 이슈면 None."""
    eff = None
    for h in history:                       # seq 오름차순
        hr = h["round"] if h["round"] is not None else 1
        if hr <= rnd:
            eff = h["to_status"]
    return eff


def _save_upload(page_uuid, side, data, size, rnd=1):
    """PNG를 로컬 저장하고 경로만 DB에 기록. dev면 '그 차수(run)'에 저장 + 원본 크기 기록 +
    기준높이(coord_ref_h)를 이미지 비율로 산출(coord_ref_w=1920 고정) → 배율 무관 정렬."""
    with intake().connect() as check_conn:
        planned = check_conn.execute("SELECT 1 FROM sqlite_master WHERE name='design_case'").fetchone() and check_conn.execute('SELECT 1 FROM design_case WHERE page_id=?',(page_uuid,)).fetchone()
    if intake().page_link(page_uuid) or planned:
        raise ValueError('접수한 이미지는 연결 화면에서 변경해 주세요. 원본을 덮어쓰지 않습니다.')
    UPLOADS.mkdir(exist_ok=True)
    conn = dbmod.connect(REAL_DB)
    w, h = size
    if side == "dev":
        run = conn.execute(
            "SELECT uuid, coord_ref_w FROM inspection_run WHERE page_id=? AND round=?",
            (page_uuid, rnd),
        ).fetchone()
        if run is None:
            conn.close()
            return
        fname = f"{run['uuid']}_dev.png"
        (UPLOADS / fname).write_bytes(data)
        ref_w = run["coord_ref_w"] or 1920
        ref_h = round(h * ref_w / w) if w else 1080     # 업로드 이미지 비율로 기준높이 산출
        conn.execute(
            "UPDATE inspection_run SET dev_img=?, dev_img_w=?, dev_img_h=?, coord_ref_h=? WHERE uuid=?",
            (fname, w, h, ref_h, run["uuid"]),
        )
    else:
        fname = f"{page_uuid}_design.png"
        (UPLOADS / fname).write_bytes(data)
        conn.execute("UPDATE inspection_page SET design_img=? WHERE uuid=?", (fname, page_uuid))
    conn.commit()
    conn.close()


def _migrate(conn):
    """빠진 칼럼만 조용히 채운다. 기존 데이터는 건드리지 않는다."""
    have = {r["name"] for r in conn.execute("PRAGMA table_info(inspection_page)")}
    for col in ("removed_at", "removed_by", "removed_note"):
        if col not in have:
            conn.execute(f"ALTER TABLE inspection_page ADD COLUMN {col} TEXT")
    conn.commit()


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _delete_pages(page_uuids):
    """검수 페이지를 진짜로 지운다. 그 페이지에 딸린 검수 데이터(차수·지적·이력·자동 후보)도 함께 사라진다.
    되돌릴 수 없다.

    append-only 이벤트 기록(auto_candidate_event / page_design_event / intake_event)은 건드리지 않는다
    (CLAUDE.md 2번-3 · 12번: 이력 자체는 지우지 않는다). 그래서 지우는 동안만 외래키 검사를 끈다."""
    if not page_uuids:
        return 0
    conn = dbmod.connect(REAL_DB)
    conn.execute("PRAGMA foreign_keys = OFF")
    n = 0
    for u in page_uuids:
        if conn.execute("SELECT 1 FROM inspection_page WHERE uuid=?", (u,)).fetchone() is None:
            continue
        issues = [r["uuid"] for r in
                  conn.execute("SELECT uuid FROM inspection_issue WHERE page_id=?", (u,))]
        if issues:
            marks = ",".join("?" for _ in issues)
            conn.execute(f"DELETE FROM issue_history WHERE issue_id IN ({marks})", issues)
        if _table_exists(conn, "auto_candidate"):
            conn.execute(
                "DELETE FROM auto_candidate WHERE auto_run_id IN "
                "(SELECT id FROM auto_run WHERE page_id=?)", (u,))
        if _table_exists(conn, "auto_run"):
            conn.execute("DELETE FROM auto_run WHERE page_id=?", (u,))
        if _table_exists(conn, "page_design_link"):
            conn.execute("DELETE FROM page_design_link WHERE page_id=?", (u,))
        if _table_exists(conn, "intake_item"):
            conn.execute("UPDATE intake_item SET page_id=NULL, status='unlinked', "
                         "revision=revision+1 WHERE page_id=?", (u,))
        if _table_exists(conn, "design_case"):
            conn.execute("UPDATE design_case SET page_id=NULL WHERE page_id=?", (u,))
        conn.execute("DELETE FROM inspection_issue WHERE page_id=?", (u,))
        conn.execute("DELETE FROM inspection_run WHERE page_id=?", (u,))
        n += conn.execute("DELETE FROM inspection_page WHERE uuid=?", (u,)).rowcount
    conn.commit()
    conn.close()
    return n


def _purge_removed_pages(screen_uuid):
    """예전에 '목록에서 빼기'로 숨겨둔 페이지를 한꺼번에 지운다."""
    conn = dbmod.connect(REAL_DB)
    _migrate(conn)
    ids = [r["uuid"] for r in conn.execute(
        "SELECT uuid FROM inspection_page WHERE screen_id=? AND removed_at IS NOT NULL",
        (screen_uuid,))]
    conn.close()
    return _delete_pages(ids)


def _rename_screen(screen_uuid, name):
    """화면명만 고친다. 사람키(스토리보드 ID)·UUID는 그대로 → 참조 무결성 영향 없음."""
    name = (name or "").strip()
    if not name:
        return False
    conn = dbmod.connect(REAL_DB)
    conn.execute("UPDATE screen SET name=? WHERE uuid=?", (name, screen_uuid))
    conn.commit()
    conn.close()
    return True


def _pass_issue(issue_uuid, actor, reason, rnd=1):
    """'협의통과' 처리: status만 갱신(행 삭제 없음) + issue_history에 한 줄 append(누가·언제·왜·차수)."""
    conn = dbmod.connect(REAL_DB)
    row = conn.execute(
        "SELECT status FROM inspection_issue WHERE uuid=?", (issue_uuid,)
    ).fetchone()
    if row is None:
        conn.close()
        return
    old = row["status"]
    conn.execute(
        "UPDATE inspection_issue SET status=?, resolved_round=? WHERE uuid=?",
        ("협의통과", rnd, issue_uuid),
    )
    seq = conn.execute(
        "SELECT COALESCE(MAX(seq), -1) + 1 AS s FROM issue_history WHERE issue_id=?", (issue_uuid,)
    ).fetchone()["s"]
    conn.execute(
        """INSERT INTO issue_history(uuid, issue_id, from_status, to_status, actor, at, note, seq, round)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (uuidmod.uuid4().hex, issue_uuid, old, "협의통과", actor,
         datetime.now().isoformat(timespec="seconds"), reason, seq, rnd),
    )
    conn.commit()
    conn.close()


# 단일 표시 분류: 저장된 category와 이력을 바꾸지 않고 현재 분류로 묶는다.
_type_label = issue_categories.label
_type_color = issue_categories.color


# ────────────────────────────────────────────────────────────── 화면 목록
def render_list(unresolved_only: bool, round_filter):
    conn = dbmod.connect(REAL_DB)
    rows = queries.list_screens(conn, unresolved_only, round_filter)
    conn.close()
    if round_filter is None:
        prepared = intake().screen_groups()
        represented = {sid for group in prepared for sid in group['screen_ids']}
        rows = [row for row in rows if row['uuid'] not in represented]
        for group in prepared:
            if unresolved_only and not group['unresolved']:
                continue
            rows.append(dict(group, human_key='', route_key='', route_href=group['href'],
                             preparation=f"짝 확인 {group['confirmed']}/{group['page_count']}"))
    rows.sort(key=lambda row: (row['project_name'],row['name'] or ''))

    def qs(un):
        return "/?unresolved=1" if un else "/"

    chip = lambda label, href, active: (
        f'<a class="chip{" on" if active else ""}" href="{href}">{label}</a>'
    )
    un_filters = (
        chip("전체", qs(False), not unresolved_only)
        + chip("미해결만", qs(True), unresolved_only)
    )

    groups_html = ""
    if not rows:
        groups_html = '<p class="empty">조건에 맞는 화면이 없습니다.</p>'
    for project, items in groupby(rows, key=lambda r: r["project_name"]):
        items = list(items)
        trs = ""
        for r in items:
            unres = r["unresolved"]
            unres_cls = "num zero" if unres == 0 else "num"
            href = r.get('route_href') or f"/screen/{r['route_key']}"
            trs += f"""<tr data-href="{_esc(href)}" onclick="location.href=this.dataset.href">
              <td class="name"><a style="color:inherit;text-decoration:none" href="{_esc(href)}">{_esc(r['name'])}</a></td>
              <td class="key">{_esc(r['human_key'] or '미정')}</td>
              <td>{_esc(r['platform'])}</td>
              <td class="ctr">{r['page_count']}개</td>
              <td class="ctr">{_esc(r.get('preparation') or '준비됨')}</td>
              <td class="ctr">{_pf_badge(r['pass_fail'])}</td>
              <td class="ctr"><span class="{unres_cls}">{unres}</span> / {r['total']}</td>
            </tr>"""
        groups_html += f"""
        <section class="group">
          <h2>{_esc(project)} <span class="muted">· 화면 {len(items)}</span></h2>
          <table>
            <thead><tr>
              <th>화면명</th><th>스토리보드 ID</th><th>플랫폼</th>
              <th class="ctr">검수 페이지</th><th class="ctr">촬영·짝 확인</th><th class="ctr">Pass/Fail(종합)</th><th class="ctr">미해결 / 전체</th>
            </tr></thead>
            <tbody>{trs}</tbody>
          </table>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수 포털 — 화면 목록</title>
{_토큰CSS}<style>{_LIST_CSS}</style></head>
<body>
  <header>
    <h1>검수 포털 <span class="muted" style="font-weight:var(--font-weight-regular);font-size:var(--font-size-14);">· 화면 목록</span></h1>
    <div class="sub">화면을 선택하면 검수 페이지를 볼 수 있습니다.</div>
  </header>
  <div class="wrap">
    <div class="filters"><span class="lbl">보기</span> {un_filters}</div>
    {groups_html}
  </div>
  <footer>미해결 정의 = {" / ".join(UNRESOLVED_STATUSES)} · 원본 = SQLite(DB), 이 화면은 렌더링 뷰</footer>
</body></html>"""


# ────────────────────────────────────────────────────── 화면 상세 = 페이지 목록
def render_screen(human_key: str, notice=""):
    for group in intake().screen_groups():
        if human_key in group['screen_ids']:
            return design_plan_http.ui.listing(intake(),group['href'].split('/')[-1]) if group['href'].startswith('/design/') else intake_http.ui.page_list(intake(),group['batch_id'],group['item_id'])
    conn = dbmod.connect(REAL_DB)
    _migrate(conn)
    scr = queries.get_screen(conn, human_key)
    if scr is None:
        conn.close()
        return None
    s = scr["row"]
    human_key = s["human_key"] or s["uuid"]
    pages = queries.pages_of_screen(conn, s["uuid"])
    removed = [p for p in queries.pages_of_screen(conn, s["uuid"], include_removed=True)
               if p["removed_at"]]
    agg = queries.screen_pass_fail(conn, s["uuid"])
    persons = queries.list_persons(conn, active_only=True)
    # 검수 페이지를 다른 화면으로 나누기·합치기 (CLAUDE.md 21번 0-3) — 옮길 곳 후보와 다음 번호 제안.
    page_move.표만들기(conn)
    다른화면 = conn.execute(
        "SELECT uuid, human_key, name FROM screen WHERE uuid<>? AND project_id=? ORDER BY human_key",
        (s["uuid"], s["project_id"])).fetchall()
    키제안값 = page_move.키제안(conn, s["human_key"] or "")
    conn.close()

    def dates_cell(p):
        """차수별 검수일. 아직 검수하지 않은 차수는 '—'."""
        cells = [f'<span class="rdate"><b>{d["round"]}차</b> {_esc(d["inspected_at"] or "—")}</span>'
                 for d in p["dates"] if d["round"] <= MAX_ROUNDS]
        return "".join(cells) or '<span class="rdate">—</span>'

    if pages:
        rows = ""
        for n, p in enumerate(pages, 1):
            dummy = ('<span class="dummy">더미</span>'
                     if (p["note"] or "").startswith("[더미]") else "")
            un = p["unresolved"]
            uncls = "num zero" if un == 0 else "num"
            href = f"/screen/{_esc(human_key)}/page/{p['uuid']}"
            up = _esc(p["uploaded_at"] or "—")
            rows += f"""<tr onclick="location.href='{href}'">
              <td class="ctr pick" onclick="event.stopPropagation()"><label class="pickbox"><input
                   type="checkbox" name="page" form="page-remove" value="{p['uuid']}"
                   aria-label="{_esc(p['name'])} 선택"></label></td>
              <td class="ctr">{n}</td>
              <td class="name">{_esc(p['name'])} {dummy}</td>
              <td class="ctr">{up}</td>
              <td class="ctr dates">{dates_cell(p)}</td>
              <td class="ctr">{_pf_badge(p['pass_fail'])}</td>
              <td class="ctr"><span class="{uncls}">{un}</span> / {p['total']}</td>
            </tr>"""
    else:
        rows = '<tr><td colspan="7" class="ctr">검수 페이지 없음</td></tr>'

    # 표 머리의 전체 고르기 — 낱개를 다 켜면 함께 켜지고, 하나라도 끄면 함께 꺼진다.
    # (S-1 Checkbox 에는 '일부만 골랐다' 상태가 없어 만들어 쓰지 않는다.)
    pick_all_th = ('<th class="ctr pick"><label class="pickbox"><input type="checkbox" id="pick-all"'
                   ' aria-label="검수 페이지 전체 선택"></label></th>') if pages else '<th class="ctr pick"></th>'
    pick_all_js = """<script>
      (function () {
        var 전체 = document.getElementById('pick-all');
        if (!전체) return;
        var 낱개 = Array.prototype.slice.call(document.querySelectorAll('input[name=page]'));
        전체.addEventListener('change', function () {
          낱개.forEach(function (c) { c.checked = 전체.checked; });
        });
        낱개.forEach(function (c) {
          c.addEventListener('change', function () {
            전체.checked = 낱개.every(function (x) { return x.checked; });
          });
        });
      })();
    </script>""" if pages else ""

    # 고른 것은 '삭제'와 같은 체크박스를 쓴다.
    move_bar = page_move.막대() if pages else ""
    move_dlg = page_move.창(_esc(human_key), 키제안값, 다른화면, persons, _esc) if pages else ""

    remove_bar = f"""
      <form id="page-remove" class="bulk" method="post" action="/screen/{_esc(human_key)}/pages/remove"
            onsubmit="return document.querySelector('input[name=page]:checked') ?
                      confirm('고른 검수 페이지를 지웁니다. 그 페이지의 지적·차수 기록도 함께 사라지고 되돌릴 수 없습니다. 지울까요?') :
                      (alert('지울 검수 페이지를 먼저 고르세요.'), false)">
        <button type="submit">삭제</button>
      </form>""" if pages else ""

    removed_html = ""
    if removed:
        # 예전 '목록에서 빼기'로 숨겨둔 페이지. 이제는 숨기지 않고 지우므로, 남은 것만 한 번에 정리한다.
        removed_html = f"""
    <section class="group">
      <form class="bulk" method="post" action="/screen/{_esc(human_key)}/pages/purge"
            onsubmit="return confirm('예전에 목록에서 빼둔 검수 페이지 {len(removed)}개를 완전히 지웁니다. 되돌릴 수 없습니다. 지울까요?')">
        <span class="lbl">예전에 목록에서 빼둔 검수 페이지 {len(removed)}개</span>
        <button type="submit">완전히 지우기</button>
      </form>
    </section>"""

    notice_html = f'<div class="notice">{_esc(notice)}</div>' if notice else ""

    # 검수를 시작하기 전에 개발이 먼저 고칠 것 — 값으로 딱 떨어지는 차이는 사람이 눈으로 볼 필요가 없다.
    주소 = ""
    try:
        주소 = (json.loads(s["dev_keys"] or "[]") or [""])[0]
    except Exception:
        주소 = ""
    셈 = fixdoc_http.셈하기(UPLOADS, pages, human_key, 주소, intake()) if pages else None
    warn_html = fixdoc_http.카드(_esc(human_key), 셈) if 셈 is not None else ""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(s['name'])} — 검수 페이지 목록</title>
{_토큰CSS}<style>{_LIST_CSS}{fixdoc_http.CSS}{page_move.CSS}</style></head>
<body>
  <header class="row">
    <a class="back" href="/">← 목록</a>
    <h1>{_esc(s['name'])}</h1>
    <details class="rename">
      <summary>화면명 고치기</summary>
      <form method="post" action="/screen/{_esc(human_key)}/rename">
        <input name="name" value="{_esc(s['name'])}" size="24" required>
        <button type="submit">저장</button>
      </form>
    </details>
    <span class="sub2"><span class="key">{_esc(s['human_key'] or '미정')}</span> · {_esc(s['platform'])} · 종합 {_pf_badge(agg)}</span>
    <a class="btn" href="/report/{_esc(human_key)}" target="_blank">화면 전체 A4</a>
  </header>
  <div class="wrap">
    {notice_html}
    {warn_html}
    <section class="group">
      <h2>검수 페이지 <span class="muted">· {len(pages)}개 (행 클릭 → 페이지 상세)</span></h2>
      {remove_bar}
      {move_bar}
      <table>
        <thead><tr>
          {pick_all_th}<th class="ctr">순번</th><th>검수 페이지</th>
          <th class="ctr">업로드일</th><th class="ctr">검수일 (차수)</th>
          <th class="ctr">Pass/Fail</th><th class="ctr">미해결 / 전체</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {pick_all_js}
    </section>
    {removed_html}
  </div>
  {move_dlg}
  <script>{page_move.JS}</script>
  <footer>업로드일 = 개발화면이 올라온 날 · 검수일 = 그 차수에 검수 기록이 남은 날 (최대 {MAX_ROUNDS}차) ·
  화면 종합: FAIL 우선 · 모든 페이지가 PASS일 때만 PASS · 그 외 미검수 포함</footer>
</body></html>"""


# ──────────────────────────────────────────────────────────── 페이지 상세
def _capture_picker(store, linked, page, sel_run, human_key=''):
    """'개발 화면 변경' 팝업 — 같은 접수함(또는 같은 화면 묶음)에서 찍은 사진 중 고른다(디자인 먼저 흐름의 팝업과 같은 모양·추천).
    접수함에 연결된 페이지는 /intake/<batch>/capture 로, 촬영기가 바로 넣은 페이지는 /screen/…/page/…/capture 로 보낸다."""
    ui = intake_http.ui
    current = sel_run['dev_img'] if sel_run else None
    rows = []
    if linked:
        for cap in store.captures_of_batch(linked['batch_id']):
            name = f"{cap['screen_name']} · {cap['state_name']}" + (' (보류)' if cap['status'] == 'held' else ' (제외)' if cap['status'] == 'excluded' else '')
            rows.append((cap['seq'], cap['id'], cap['filename'], name))
        action = f'/intake/{linked["batch_id"]}/capture'
        controls = ui.hidden('item', linked['id']) + ui.hidden('revision', linked['revision'])
    else:
        for i, cap in enumerate(design_receive.Receiver(store).sibling_captures(page['uuid'])):
            rows.append((i, cap['filename'], cap['filename'], f"{cap['page_name']} · {cap['round']}차"))
        action = f"/screen/{_esc(human_key)}/page/{_esc(page['uuid'])}/capture"
        controls = ''
    caps = rows
    options = ''
    for seq, value, filename, name in sorted(rows, key=lambda x: (x[2] != current, x[0])):
        options += (f'<label class="cap-option"><input type="radio" name="capture" value="{_esc(value)}" data-src="/uploads/{_esc(filename)}" '
                    f'data-name="{_esc(name)}" {"checked" if filename == current else ""}><span class="rank">비교 중</span><span>{_esc(name)}</span></label>')
    pic = f'<img id="plan-capture-preview" src="/uploads/{_esc(current)}" alt="선택한 개발 캡처">' if current else '<img id="plan-capture-preview" alt="아래에서 개발 캡처를 선택하세요.">'
    design = f'<img class="design-original" src="/uploads/{_esc(page["design_img"])}" alt="디자인 원본">' if page.get('design_img') else '<span class="ph">디자인 없음</span>'
    comparison = (f'<div class="capture-layout"><div class="capture-pair"><section><h3>디자인 원본</h3><div class="capture-image">{design}</div></section>'
                  f'<section><h3>개발 화면</h3><div class="capture-image">{pic}</div></section></div>'
                  f'<aside class="capture-list"><b>{"같은 접수함에서 찍은 사진" if linked else "같은 화면에서 찍은 사진"}</b><div class="capture-options">{options}</div></aside></div>')
    return (f'<dialog id="capture-picker"><div class="s1-modal-inset"><div class="dialog-head"><h2>개발 화면 바꾸기</h2><button type="button" onclick="document.getElementById(\'capture-picker\').close()">닫기</button></div>'
            f'<p class="recommendation-status" role="status">유사한 개발 캡처를 찾고 있습니다…</p>'
            + ui.form(action, controls + comparison + f'<div class="capture-footer"><button {"disabled" if not caps else ""}>이 개발 화면으로 변경</button></div>')
            + f'</div></dialog><script>{(BASE / "capture_recommendation.js").read_text()}</script>')


def render_page(page_uuid: str, sel_round=None, open_design=False, notice="", *, draft=None, store=None, workflow=None):
    store = store or intake()
    conn = dbmod.connect(store.database)
    siblings = []
    if draft:
        batch, item = draft
        page = {'uuid': item['id'], 'name': item['state_name'], 'design_img': item['design_file']}
        s = {'uuid': batch['id'], 'human_key': '', 'name': item['screen_name'], 'platform': batch['platform']}
        linked = item
        all_issues, hist_by_issue, runs = [], {}, []
    else:
        pg = queries.get_page(conn, page_uuid)
        if pg is None:
            conn.close()
            return None
        page, s = dict(pg['page']), pg['screen']
        linked = store.page_link(page_uuid)
        all_issues = queries.issues_of_page(conn, page_uuid)
        hist_by_issue = {i['uuid']: queries.history_of_issue(conn, i['uuid']) for i in all_issues}
        runs = queries.runs_of_page(conn, page_uuid)
        siblings = queries.pages_of_screen(conn, s['uuid'])
    persons = queries.list_persons(conn, active_only=True)
    roster = queries.roster_names(conn)
    conn.close()
    if workflow:
        linked = workflow['row']
        page['design_img'] = linked['design_file']
    imported_item = workflow['row'] if workflow else None
    if linked and not workflow:
        _, imported_items, _ = store.batch(linked['batch_id'])
        imported_item = next(r for r in imported_items if r['id'] == linked['id'])
        page['design_img'] = imported_item['design_file']
    # 같은 Figma 프레임이면 늘 최신 판을 본다 (옛 판은 지우지 않는다)
    design_now = None if draft else store.page_design(page_uuid)
    if design_now and design_now['design_file']:
        page['design_img'] = design_now['design_file']
    human_key = s['human_key'] or s['uuid']
    def upload_control(side):
        if workflow:
            if side=='design':return '<span class="upl">디자인 원본 기준</span>'
            return '<button type="button" class="upl" onclick="document.getElementById(&quot;capture-picker&quot;).showModal()">개발 화면 변경</button>'
        if linked:
            if side == 'design':
                return '<button type="button" class="upl" onclick="document.getElementById(&quot;design-picker&quot;).showModal()">'+('다른 시안으로 변경' if imported_item['design_id'] else 'Figma 연결')+'</button>'
            if linked['page_id'] and not all_issues:
                return '<button type="button" class="upl" onclick="document.getElementById(&quot;capture-picker&quot;).showModal()">개발 화면 변경</button>'
            return '<span class="upl">촬영 원본 보관됨' + (' · 바꾸려면 새 차수' if all_issues else '') + '</span>'
        extra = ''
        if side == 'dev' and sel_run and not all_issues and len(sibling_caps) > 1:
            extra = '<button type="button" class="upl" onclick="document.getElementById(&quot;capture-picker&quot;).showModal()">개발 화면 변경</button> '
        return extra + _upl(human_key, page_uuid, side, sel if side == 'dev' else None)

    # 차수 선택: ?round=N (없으면 최신). 그 차수 시점의 상태로 화면을 구성한다.
    rounds = [r["round"] for r in runs]
    sel = sel_round if sel_round in rounds else (max(rounds) if rounds else 1)
    sel_run = next((r for r in runs if r["round"] == sel), None)
    sibling_caps = design_receive.Receiver(store).sibling_captures(page_uuid) if (sel_run and not linked and not draft) else []
    # 자동 검수 후보(그 차수). 결과가 없으면 '대기'로 만들어 두고, 페이지 JS가 엔진을 돌려 저장한다.
    auto_view = auto_inspect.Auto(store).view(page_uuid, sel_run) if (sel_run and not draft) else None

    number = {i["rid"]: n + 1 for n, i in enumerate(all_issues)}  # 페이지 안 순번 1..N (전체 고정)
    # 각 이슈의 '그 차수 시점 상태'(history.round로 재구성). 그 차수에 아직 없던 이슈는 제외.
    st = {i["uuid"]: _status_at(hist_by_issue[i["uuid"]], sel) for i in all_issues}
    issues = [i for i in all_issues if st[i["uuid"]] is not None]
    unresolved = [i for i in issues if st[i["uuid"]] in UNRESOLVED_STATUSES]
    resolved = [i for i in issues if st[i["uuid"]] in CLOSED_STATUSES]
    waiting = [i for i in issues if st[i['uuid']] not in UNRESOLVED_STATUSES and st[i['uuid']] not in CLOSED_STATUSES]

    # 우측(개발) 핀 오버레이 — 핀은 '전체' 이슈(미해결+처리됨) 다 표시. 좌측 디자인엔 핀 없음.
    # 핀을 박스 '위쪽 바깥'에 둔다(내용 위를 안 덮게). 겹치면 위아래로 길게 밀지 말고 옆으로만.
    MIN, STEP, R = 72, 74, 26    # 최소 간격 / 옆 간격 / 핀 반지름 (viewBox 단위)
    placed = []
    layout = []
    for i in issues:
        x, y, w, h = i["box_x"] or 0, i["box_y"] or 0, i["box_w"] or 0, i["box_h"] or 0
        base = x + 30
        px = base
        py = max(R + 4, y - R - 4)            # 박스 상단선 위(바깥)
        guard = 0
        while any((px - qx) ** 2 + (py - qy) ** 2 < MIN * MIN for qx, qy in placed) and guard < 90:
            px += STEP                        # 옆으로만
            if px > 1890:
                px = base
                py = max(R + 4, py - 64)
            guard += 1
        placed.append((px, py))
        draw_leader = py < y - 4              # 핀이 박스 위에 떠 있으면 짧은 선으로 연결
        tx = min(max(px, x), x + w)
        layout.append((i, px, py, tx, y, draw_leader))

    # 레이어 3개: (1) 박스 rect [클릭] → (2) 짧은 리더 [클릭 통과] → (3) 핀 dot [클릭, 항상 맨 위]
    boxes = leaders = dots = ""
    for i, px, py, tx, ty, draw_leader in layout:
        n = number[i["rid"]]
        uid = i["uuid"]
        x, y, w, h = i["box_x"] or 0, i["box_y"] or 0, i["box_w"] or 0, i["box_h"] or 0
        c = _type_color(i["category"])        # 핀·박스 색 = 오류 유형색
        fd = " faded" if st[i["uuid"]] in CLOSED_STATUSES else ""   # 그 차수에 처리된 건 흐리게
        boxes += (
            f'<g class="box{fd}" id="box-{uid}" onclick="focusCard(\'{uid}\')">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" style="fill:{c};stroke:{c}"/></g>'
        )
        if draw_leader:
            leaders += f'<line class="leader{fd}" x1="{px}" y1="{py + R}" x2="{tx}" y2="{ty}" style="stroke:{c}"/>'
        dots += (
            f'<g class="pin clickable{fd}" id="pin-{uid}" data-issue="{uid}" '
            f'onclick="focusCard(\'{uid}\')">'
            f'<g transform="translate({px},{py})"><g class="pinmark">'
            f'<circle class="hit" r="42"/>'
            f'<circle class="dot" r="{R}" style="fill:{c}"/>'
            f'<text y="9" text-anchor="middle">{n}</text>'
            f"</g></g></g>"
        )
    # 개발 이미지·기준크기는 '선택한 차수(run)'에서 가져온다. 디자인은 page(차수 공통).
    dev_img = sel_run["dev_img"] if sel_run else (imported_item["filename"] if imported_item else None)
    design_img = page["design_img"]
    vb_w = (sel_run["coord_ref_w"] if sel_run else None) or (imported_item["width"] if imported_item else None) or 1920
    vb_h = (sel_run["coord_ref_h"] if sel_run else None) or (imported_item["height"] if imported_item else None) or 1080
    # 고정 틀(canvas) 안에 이미지도 오버레이도 같은 'meet'로 비율 맞춤 → 틀이 안 흔들리고 핀 정렬 유지.
    # (coord_ref 비율 = 이미지 비율이라, object-fit:contain과 SVG meet가 같은 자리에 레터박스됨.)
    overlay = (
        f'<svg viewBox="0 0 {vb_w} {vb_h}" preserveAspectRatio="xMidYMid meet" class="overlay">'
        f'<g class="boxes">{boxes}</g>'
        f'<g class="leaders">{leaders}</g>'
        f'<g class="pins">{dots}</g>'
        f"</svg>"
    )

    # 좌: 디자인 이미지(핀 없음) / 우: 개발 이미지 + 핀 오버레이. 없으면 자리표시 유지.
    if design_img:
        left_body = f'<img class="capimg" src="/uploads/{_esc(design_img)}" alt="디자인">'
    else:
        left_body = '<span class="ph">Figma 디자인을 연결해 주세요.</span>'
    auto_overlay = (f'<svg viewBox="0 0 {vb_w} {vb_h}" preserveAspectRatio="xMidYMid meet" class="overlay auto-overlay"></svg>'
                    if auto_view and auto_view['candidates'] else '')
    if dev_img:
        right_body = f'<img class="capimg" src="/uploads/{_esc(dev_img)}" alt="개발화면">{overlay}{auto_overlay}'  # 후보 층은 핀 층 위(번호를 누를 수 있게)
    else:
        right_body = f'<span class="ph">{"디자인 시안과 같은 상태의 개발 화면을 등록해 주세요." if workflow else "개발 이미지 자리표시"}</span>{overlay}'

    person_options = "".join(f'<option value="{_esc(p["name"])}">{_esc(p["name"])}</option>' for p in persons)

    def issue_card(i):
        n = number[i["rid"]]
        s_eff = st[i["uuid"]]                 # 그 차수 시점 상태
        cls = _status_class(s_eff)
        unres = s_eff in UNRESOLVED_STATUSES
        props = json.loads(i["properties"]) if i["properties"] else []
        props_html = "".join(f'<span class="tag">{_esc(p)}</span>' for p in props)
        loc = f'({i["box_x"]},{i["box_y"]}) {i["box_w"]}×{i["box_h"]}'
        sev_html = f'<span class="sev">{_esc(i["severity"])}</span>' if i["severity"] else ""
        type_color = _type_color(i["category"])
        state_label = "미해결" if unres else s_eff   # 처리됨은 실제 상태(협의통과/검수완료/오류아님)
        rows = ""
        for h in hist_by_issue[i["uuid"]]:
            actor = h["actor"]
            actor_html = (
                f'<span class="actor">{_esc(actor)}</span>' if actor in roster
                else f'<span class="actor off" title="담당자 명단에 없음">{_esc(actor or "미지정")} ⚠</span>'
            )
            rlab = f'<span class="rnd">{h["round"]}차</span> ' if h["round"] else ""
            change = f'{_esc(h["from_status"] or "(신규)")} → {_esc(h["to_status"])}'
            note = f' <span class="note">— {_esc(h["note"])}</span>' if h["note"] else ""
            rows += (f'<li>{rlab}{actor_html} · <span class="at">{_esc(h["at"] or "시각 없음")}</span> · '
                     f'{change}{note}</li>')
        # 미해결 카드에만 통과 처리 폼(담당자 선택 + 사유 필수). 처리됨 카드는 사유·이력만.
        if unres:
            action = f"/screen/{_esc(human_key)}/page/{_esc(page_uuid)}/pass"
            foot = (
                f'<form class="passform" method="post" action="{action}" '
                f'onsubmit="return _confirmPass(this)" onclick="event.stopPropagation()">'
                f'<input type="hidden" name="issue" value="{i["uuid"]}">'
                f'<input type="hidden" name="round" value="{sel}">'
                f'<select name="actor" required>{person_options}</select>'
                f'<input name="reason" maxlength="200" required placeholder="통과 사유 (필수)">'
                f'<button type="submit">통과 처리</button>'
                f"</form>"
            )
        else:
            foot = '<div class="passed">✓ 처리됨 (이력·사유는 위 참조)</div>' if s_eff in CLOSED_STATUSES else '<div class="loc">확인·판단 대기 중 · 이력 유지</div>'
        return f"""<div class="issue {cls}" id="issue-{i['uuid']}" data-issue="{i['uuid']}" data-types="{_esc(issue_categories.label(i['category']))}" onclick="focusPin('{i['uuid']}')">
          <div class="ihead">
            <span class="pinno" style="background:{type_color}">{n}</span>
            <span class="state {cls}">{_esc(state_label)}</span>
            {sev_html}
            <b>{_esc(i['logical_element_key'])}</b>
          </div>
          <div class="props">{props_html}</div>
          <div class="loc">위치 {loc}</div>
          <ul class="hist">{rows}</ul>
          {foot}
        </div>"""

    # 탭은 세 칸: 수정필요(기본) · 처리됨 · 제외.
    # '수정필요' = 자동으로 찾은 것(제외 안 한 것) + 사람이 넣은 미해결·대기 지적.
    fix_items = unresolved + waiting
    fix_cards = "".join(issue_card(i) for i in fix_items)
    fix_n = len(fix_items)
    excluded_body, excluded_n = '<p class="empty">항목 없음</p>', 0
    if auto_view:
        fix_n += sum(1 for k in auto_view['candidates'] if k['status'] == 'open' and not k['issue_id'])
        excluded_n = sum(1 for k in auto_view['candidates'] if k['status'] != 'open')
        excluded_body = auto_inspect.panel_html(auto_view, page_uuid, person_options, 'excluded')
        fix_body = (auto_inspect.panel_html(auto_view, page_uuid, person_options, 'open')
                    + (f'<div class="grid">{fix_cards}</div>' if fix_cards else ''))
    else:
        fix_body = f'<div class="grid">{fix_cards}</div>' if fix_cards else '<p class="empty">항목 없음</p>'
    done_cards = "".join(issue_card(i) for i in resolved) or '<p class="empty">항목 없음</p>'
    tab_defs = [
        ("수정필요", "var(--color-action-primary-default)", fix_n, fix_body),
        ("처리됨", "var(--color-text-helper)", len(resolved), f'<div class="grid">{done_cards}</div>'),
        ("제외", "var(--color-text-caption)", excluded_n, excluded_body),
    ]

    tabbar = panels = ""
    for gi, tdef in enumerate(tab_defs):
        lbl, col = tdef[0], tdef[1]
        if len(tdef) == 4:
            count, body = tdef[2], tdef[3]
        else:
            items = tdef[2]
            count = len(items)
            cards = "".join(issue_card(i) for i in items) or '<p class="empty">항목 없음</p>'
            body = f'<div class="grid">{cards}</div>'
        tabbar += (
            f'<button class="tab{" on" if gi == 0 else ""}" data-idx="{gi}" onclick="showTab(\'{gi}\')">'
            f'<span class="sw" style="background:{col}"></span>{_esc(lbl)} '
            f'<span class="cnt">{count}</span></button>'
        )
        panels += (
            f'<div class="panel" id="panel-{gi}"{"" if gi == 0 else " hidden"}>'
            f'{body}</div>'
        )
    # 성질 거르개 — 탭과 같은 줄 오른쪽. 생김새(밑줄 탭 ↔ 알약 칩)가 달라 헷갈리지 않는다.
    성질 = []
    for src in ([k for k in (auto_view or {}).get('candidates', []) if k['status'] == 'open'] if auto_view else []):
        lb = issue_categories.label(auto_inspect.candidate_category(src))
        if lb not in 성질:
            성질.append(lb)
    for i in fix_items:
        lb = issue_categories.label(i['category'])
        if lb not in 성질:
            성질.append(lb)
    filterbar = ''
    if len(성질) > 1:
        칩 = ''.join(f'<button type="button" class="fchip" data-type="{_esc(x)}" onclick="filterType(this)">{_esc(x)}</button>'
                    for x in 성질)
        filterbar = ('<span class="fbar"><span class="flbl">성질</span>'
                     '<button type="button" class="fchip on" data-type="" onclick="filterType(this)">전체</button>'
                     + 칩 + '</span>')

    auto_extra = (f'<script id="auto-data" type="application/json">{auto_inspect.overlay_json(auto_view)}</script>'
                  f'<script>{auto_inspect.JS}</script>') if auto_view else ''
    issues_html = panels
    if not all_issues and linked and linked['status'] != 'confirmed':
        issues_html = '<p class="empty">아직 등록된 검수 내용이 없습니다. 시안을 연결하고 짝을 확인한 뒤 이곳에서 검수를 이어갑니다.</p>'

    roster_html = "".join(
        f'<span class="person">{_esc(p["name"])}'
        f'{" · " + _esc(p["affiliation"]) if p["affiliation"] else ""}</span>'
        for p in persons
    ) or '<span class="muted">명단 비어있음</span>'

    # 차수 선택 (선택 차수의 개발 이미지·상태를 보여줌)
    base = f"/screen/{_esc(human_key)}/page/{_esc(page_uuid)}"
    round_sel = ""
    if rounds:
        chips = "".join(
            f'<a class="chip{" on" if r == sel else ""}" href="{base}?round={r}">{r}차</a>'
            for r in rounds
        )
        pf_r = _pf_badge(sel_run["pass_fail"]) if sel_run else ""
        round_sel = f'<span class="rounds"><span class="rlbl">차수</span>{chips} {pf_r}</span>'

    design_dialog = ''
    connection_controls = ''
    if linked and not workflow:
        ui = intake_http.ui
        design_dialog = ui.design_dialog(store,linked['batch_id'],imported_item)
        recommendation = store.recommendation(linked['id']) if linked['status']=='pending' else ''
        label = '추천 연결 · 확인 대기' if recommendation else ui.STATUS[linked['status']]
        connection_controls = '<div class="connection-controls"><span class="chip">'+_esc(label)+'</span>'
        controls = ui.hidden('item',linked['id']) + ui.hidden('revision',linked['revision'])
        if linked['status'] == 'pending':
            connection_controls += ui.form('/intake/'+linked['batch_id']+'/confirm', controls+'<button>이 짝으로 확인</button>')
            connection_controls += '<span>두 이미지가 같은 상태인지 확인하세요. 확인 후에도 이 화면에서 이어집니다.</span>'
        elif linked['status'] == 'unlinked':
            connection_controls += '<span>왼쪽에서 Figma 시안을 연결해 주세요.</span>'
        elif linked['status'] == 'confirmed' and not linked['page_id']:
            connection_controls += ui.form('/intake/'+linked['batch_id']+'/start', controls+'<button>확인한 페이지 검수 열기</button>')
        if linked['status'] in ('unlinked','pending','held','excluded'):
            connection_controls += '<a href="/intake/'+linked['batch_id']+'">촬영본 관리·보류</a>'
        if recommendation:
            connection_controls += '<span class="recommendation-note">'+_esc(recommendation)+'</span>'
        connection_controls += '</div>'
        if open_design:
            design_dialog += '<script>document.getElementById("design-picker").showModal()</script>'
    if linked and not workflow and linked['page_id'] and not all_issues:
        design_dialog += _capture_picker(store, linked, page, sel_run)
    elif not linked and not workflow and not draft and sel_run and not all_issues and len(sibling_caps) > 1:
        design_dialog += _capture_picker(store, None, page, sel_run, human_key)
    if workflow:
        design_dialog=workflow['dialog']
        connection_controls=workflow['controls']
        issues_html=workflow['sidebar']+issues_html.replace('시안을 연결하고 짝을 확인한 뒤','개발 화면을 등록하고 짝을 확인한 뒤')
    design_mark = ''
    if design_now and design_now['changed']:
        design_mark = ('<span class="fresh" title="처음 받은 판: '
                       + _esc((design_now['orig_at'] or '')[:10]) + '">시안 새 판 · '
                       + _esc((design_now['fetched_at'] or '')[:10]) + '</span>')
    native_app = app_layout.is_app(s['platform'])
    parent_href = f"/intake/{linked['batch_id']}/screen/{linked['id']}" if linked else f"/screen/{human_key}"
    if workflow:parent_href=workflow["parent"]
    navigation = workflow.get("navigation", "") if workflow else ""
    if not navigation and len(siblings) > 1:
        idx = next((i for i, p_ in enumerate(siblings) if p_["uuid"] == page_uuid), None)
        if idx is not None:
            def _step(offset, label):
                t = idx + offset
                if not 0 <= t < len(siblings):
                    return f'<span class="page-step disabled" aria-disabled="true">{label}</span>'
                nxt = siblings[t]
                return (f'<a class="page-step" href="/screen/{_esc(human_key)}/page/{_esc(nxt["uuid"])}"'
                        f' title="{_esc(nxt["name"])}">{label}</a>')
            navigation = ('<nav class="page-navigation" aria-label="검수 페이지 이동">'
                          + _step(-1, "← 이전")
                          + f'<span>{idx + 1} / {len(siblings)}</span>'
                          + _step(1, "다음 →") + '</nav>')
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page['name'])} — 페이지 상세</title>
{_토큰CSS}<style>{_PAGE_CSS}{_DIALOG_CSS}{comparison_view.CSS}{auto_inspect.CSS}{card_view.CSS}{app_layout.CSS if native_app else ""}</style></head>
<body class="{'app-view' if native_app else 'web-view'}">
  <header>
    <div class="head-left">
      <a class="back" href="{_esc(parent_href)}">← 검수 페이지 목록</a>
      <h1>{_esc(page['name'])}</h1>
      <span class="meta">{_esc(s['name'])} · <span class="key">{_esc(s["human_key"] or "미정")}</span></span>
    </div>
    {navigation or '<span></span>'}
    {round_sel or '<span class="rounds"><span class="pf">미검수</span></span>'}
  </header>
  <div class="wrap">

    {('<p role="status">'+_esc(notice)+'</p>') if notice else ''}

    {connection_controls if not workflow else ""}
    {'<div class="app-workspace">' if native_app else ''}
    <div class="cols">
      <div class="pane">
        <h3>좌 · 디자인 (정답 모습 — 핀 없음) {design_mark}{upload_control('design')}</h3>
        <div class="canvas">{left_body}</div>
      </div>
      <div class="pane">
        <h3>우 · 개발 ({str(sel)+"차 · 핀 = 발견 위치" if runs else "촬영본 · 미검수"}) {upload_control('dev')}</h3>
        <div class="canvas">{right_body}</div>
      </div>
    </div>

    {'<aside class="app-sidebar">' if native_app else ''}
    <div class="tabbar">{tabbar}{filterbar}</div>
    <div class="cards" id="cards">{issues_html}</div>
    {'</aside></div>' if native_app else ''}
  </div>
  {design_dialog}
  <script>{_PAGE_JS}</script><script>{comparison_view.JS}</script>{auto_extra}
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        path = parsed.path
        unresolved_only = q.get("unresolved", ["0"])[0] == "1"

        if not self._local_host():
            self.send_error(403)
            return
        if path == "/__rev":
            data = BOOT_ID.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if auto_inspect.get(self, intake(), path, q):
            return
        if path == '/policy' or path.startswith('/policy/'):
            conn = dbmod.connect(REAL_DB)
            persons = queries.list_persons(conn, active_only=True)
            conn.close()
            policy_ui.get(self, intake(), path, "".join(f'<option value="{_esc(p["name"])}">{_esc(p["name"])}</option>' for p in persons))
            return
        if path.startswith('/design'):
            design_plan_http.get(self, intake(), path)
        elif path.startswith('/intake'):
            intake_http.get(self, intake(), path, q)
        elif path == "/":
            round_filter = int(q["round"][0]) if "round" in q else None
            self._html(render_list(unresolved_only, round_filter))
        elif "/page/" in path and path.startswith("/screen/"):
            page_uuid = path.rsplit("/page/", 1)[1]
            rnd = int(q["round"][0]) if "round" in q else None
            from design_plan import Plans
            case_ref=None
            with intake().connect() as c:
                case_ref=c.execute('SELECT plan_id,id FROM design_case WHERE page_id=?',(page_uuid,)).fetchone()
            page = design_plan_http.ui.detail(intake(),case_ref['plan_id'],case_ref['id'],q.get('notice',[''])[0],rnd) if case_ref else render_page(page_uuid, rnd, q.get('designs',[''])[0]=='1',q.get('notice',[''])[0])
            self._html(page if page else self._nf("페이지 없음"), 200 if page else 404)
        elif path.startswith("/screen/") and unquote(path).endswith(("/수정요청.md", "/수정요청.html")):
            # 한글 주소는 브라우저가 %xx 로 싸서 보낸다 — 풀어서 견준다.
            푼길 = unquote(path)
            보기 = 푼길.endswith(".html")
            꼬리 = "/수정요청.html" if 보기 else "/수정요청.md"
            self._수정요청(푼길[len("/screen/"):-len(꼬리)], 보기)
        elif path.startswith("/screen/"):
            human_key = path[len("/screen/"):]
            page = render_screen(human_key, q.get("notice", [""])[0])
            self._html(page if page else self._nf(f"화면 없음: {human_key}"), 200 if page else 404)
        elif path.startswith("/assets/css/") and path.endswith(".css"):
            # S-1 디자인가이드 토큰 네 장. `가이드받기.sh --내려두기` 로 받아 둔 것을 그대로 내보낸다.
            fp = BASE / "assets" / "css" / Path(path[len("/assets/css/"):]).name
            if fp.exists():
                data = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
        elif path.startswith("/uploads/"):
            fp = UPLOADS / Path(path[len("/uploads/"):]).name   # basename만 → 경로 탈출 방지
            if fp.exists() and fp.suffix == ".png":
                data = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()
        elif path.startswith("/report/"):
            # A4 반출은 park(나중 조각). report.py는 손대지 않음.
            self._html("<p style='font-family:sans-serif;padding:var(--spacing-40)'>화면 전체 A4 반출은 다음 조각입니다. "
                       "<a href='javascript:history.back()'>← 뒤로</a></p>")
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        # Figma 플러그인 창(origin null)이 /api/… 로 보내기 전에 미리 묻는다. 내 PC 안에서만.
        if not self._local_host() or not design_receive.options(self, urlparse(self.path).path):
            self.send_error(403)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._local_host():
            self.send_error(403)
            return
        if design_receive.post(self, intake(), path):
            return
        if path.startswith('/design'):
            design_plan_http.post(self, intake(), path)
            return
        if path.startswith('/intake'):
            intake_http.post(self, intake(), path)
            return
        if auto_inspect.post(self, intake(), path):
            return
        if policy_api.post(self, intake(), path):   # 검수기 플러그인 ↔ 포털 규칙 배선
            return
        if policy_ui.post(self, intake(), path):
            return
        length = int(self.headers.get("Content-Length", 0))
        if path.startswith("/screen/") and path.endswith("/pages/move"):
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            key = unquote(path[len("/screen/"):-len("/pages/move")])
            conn = dbmod.connect(REAL_DB)
            try:
                got = page_move.옮기기(
                    conn, form.get("page", []),
                    to_screen=(form.get("to_screen", [""])[0]
                               if form.get("dest", ["new"])[0] == "exist" else None),
                    new_key=form.get("new_key", [""])[0],
                    new_name=form.get("new_name", [""])[0],
                    actor=form.get("actor", [""])[0].strip(),
                    note=form.get("note", [""])[0].strip())
                갈곳 = got["human_key"] or got["screen"]
                notice = f"검수 페이지 {got['moved']}장을 '{got['name']}'(으)로 옮겼습니다."
            except ValueError as ex:                 # 사람에게 그대로 보여 줄 안내
                conn.rollback()
                갈곳, notice = key, str(ex)
            except Exception as ex:                  # 뜻밖의 일도 화면에 말해 준다(조용히 끊기지 않게)
                conn.rollback()
                갈곳, notice = key, f"옮기지 못했습니다 — {ex}"
            finally:
                conn.close()
            self.send_response(303)
            self.send_header("Location", f"/screen/{quote(갈곳)}?notice={quote(notice)}")
            self.end_headers()
            return
        if path.startswith("/screen/") and path.endswith(("/pages/remove", "/pages/purge", "/rename")):
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            action = path.rsplit("/", 1)[1]
            suffix = "/rename" if action == "rename" else "/pages/" + action
            key = path[len("/screen/"):-len(suffix)]
            conn = dbmod.connect(REAL_DB)
            scr = queries.get_screen(conn, key)
            conn.close()
            if scr is None:
                self._html(self._nf(f"화면 없음: {key}"), 404)
                return
            if action == "rename":
                _rename_screen(scr["row"]["uuid"], form.get("name", [""])[0])
                notice = "화면명을 바꿨습니다."
            elif action == "remove":
                n = _delete_pages(form.get("page", []))
                notice = f"검수 페이지 {n}개를 지웠습니다."
            else:
                n = _purge_removed_pages(scr["row"]["uuid"])
                notice = f"예전에 빼둔 검수 페이지 {n}개를 지웠습니다."
            self.send_response(303)
            self.send_header("Location", f"/screen/{key}?notice={quote(notice)}")
            self.end_headers()
            return
        if path.startswith("/screen/") and "/page/" in path and path.endswith("/capture"):
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            page_uuid = path[:-len("/capture")].rsplit("/page/", 1)[1]
            try:
                design_receive.Receiver(intake()).replace_capture(page_uuid, form.get("capture", [""])[0])
                notice = "개발 화면을 바꿨습니다."
            except ValueError as ex:
                notice = str(ex)
            self.send_response(303)
            self.send_header("Location", path[:-len("/capture")] + "?notice=" + quote(notice))
            self.end_headers()
        elif path.startswith("/screen/") and "/page/" in path and path.endswith("/pass"):
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            issue = form.get("issue", [""])[0]
            actor = form.get("actor", [""])[0].strip()
            reason = form.get("reason", [""])[0].strip()
            rnd = int(form.get("round", ["1"])[0] or 1)
            if issue and reason:                       # 사유 필수 — 빈 사유는 무시
                _pass_issue(issue, actor, reason, rnd)
            self.send_response(303)                    # 처리 후 페이지 상세로 리다이렉트
            self.send_header("Location", path[:-len("/pass")])
            self.end_headers()
        elif path.startswith("/screen/") and "/page/" in path and path.endswith("/upload"):
            uq = parse_qs(parsed.query)
            side = uq.get("side", [""])[0]
            rnd = int(uq.get("round", ["1"])[0] or 1)
            page_uuid = path[:-len("/upload")].rsplit("/page/", 1)[1]
            body = self.rfile.read(length)
            data = _multipart_file(body, self.headers.get("Content-Type", ""))
            size = _png_size(data)                     # PNG만 허용(아니면 무시)
            if data and size and side in ("design", "dev"):
                try:
                    _save_upload(page_uuid, side, data, size, rnd)
                except ValueError as ex:
                    self._html(self._nf(str(ex)), 400)
                    return
            self.send_response(303)
            self.send_header("Location", path[:-len("/upload")])
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _수정요청(self, human_key, 보기=False):
        """개발·퍼블리셔에게 그대로 넘기는 수정 요청 한 장.

        `보기`면 같은 글을 A4 모양 화면으로 그려 준다(인쇄창에서 PDF 로 저장). 글은 다시 만들지 않는다.
        """
        conn = dbmod.connect(REAL_DB)
        scr = queries.get_screen(conn, human_key)
        if scr is None:
            conn.close()
            self._html(self._nf(f"화면 없음: {human_key}"), 404)
            return
        row = scr["row"]
        pages = queries.pages_of_screen(conn, row["uuid"])
        conn.close()
        try:
            주소 = (json.loads(row["dev_keys"] or "[]") or [""])[0]
        except Exception:
            주소 = ""
        try:
            글 = fixdoc_http.문서만들기(UPLOADS, pages, human_key, row["name"], 주소, intake())
        except Exception as e:
            self._html(f"<p style='font-family:sans-serif;padding:var(--spacing-40)'>수정요청서를 만들지 못했습니다 — {_esc(str(e))}</p>", 500)
            return
        if not 글:
            self._html("<p style='font-family:sans-serif;padding:var(--spacing-40)'>이 화면에는 잰 값이 없어 "
                       "수정요청서를 만들 수 없습니다. 촬영기로 다시 보내 주세요.</p>", 404)
            return
        if 보기:
            제목 = f"개발화면 수정 요청 — {row['name']}"
            md주소 = "/screen/" + quote(human_key) + "/" + quote("수정요청.md")
            self._html(fixdoc_view.한장(글, 제목, md주소))
            return
        data = 글.encode("utf-8")
        이름 = quote(f"수정요청-{row['name']}.md")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{이름}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _local_host(self):
        host = self.headers.get('Host', '')
        if host in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            return True
        # 동료 공유를 켜면 같은 사무실 네트워크(사설 IP)에서 들어오는 것도 받는다.
        if HOST != "0.0.0.0":
            return False
        name = host.rsplit(':', 1)
        if len(name) != 2 or name[1] != str(PORT):
            return False
        return _is_private_ip(name[0])

    @staticmethod
    def _nf(msg):
        return f"<p style='font-family:sans-serif;padding:var(--spacing-40)'>{_esc(msg)} <a href='/'>← 목록</a></p>"

    def _html(self, body, code=200):
        body = intake_http.decorate(body)
        if AUTORELOAD:
            body = body.replace("</body>", _RELOAD_JS + "</body>", 1)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # 콘솔 조용히


_LIST_CSS = """
  * { box-sizing: border-box; }
  body { font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:var(--color-text-primary); margin:0; background:var(--color-bg-subtle); }
  header { background:var(--color-surface-default); border-bottom:1px solid var(--color-border-subtle); padding:var(--spacing-16) var(--spacing-28); }
  header.row { display:flex; align-items:center; gap:var(--spacing-14); flex-wrap:wrap; padding:var(--spacing-14) var(--spacing-28); }
  h1 { font-size:var(--font-size-18); margin:0; }
  .back { text-decoration:none; color:var(--color-text-caption); font-size:var(--font-size-14); }
  .sub { font-size:var(--font-size-12); color:var(--color-text-caption); margin-top:var(--spacing-4); }
  .sub2 { font-size:var(--font-size-12); color:var(--color-text-caption); }
  .btn { margin-left:auto; }   /* 모양은 코어 Button(s1_components) */
  .wrap { max-width:1040px; margin:0 auto; padding:var(--spacing-20) var(--spacing-28) var(--spacing-64); }
  .filters { display:flex; gap:var(--spacing-10); align-items:center; margin:var(--spacing-6) 0 var(--spacing-20); flex-wrap:wrap; }
  .filters .lbl { font-size:var(--font-size-12); color:var(--color-text-caption); }
  .chip { margin-right:var(--spacing-6); }   /* 모양은 코어 Chip(line) */
  .group { background:var(--color-surface-default); border:1px solid var(--color-border-subtle); border-radius:var(--radius-12); padding:var(--spacing-6) var(--spacing-14) var(--spacing-14); margin-bottom:var(--spacing-16); }
  h2 { font-size:var(--font-size-14); margin:var(--spacing-14) var(--spacing-4) var(--spacing-8); }
  .muted { color:var(--color-text-helper); font-weight:var(--font-weight-regular); }
  tbody tr { cursor:pointer; }   /* 표 모양은 코어 Table(s1_components) */
  .name { font-weight:var(--font-weight-bold); }
  .key { font-family:ui-monospace,monospace; color:var(--color-text-tertiary); }
  .ctr { text-align:center; white-space:nowrap; }
  .pf { font-size:var(--font-size-12); font-weight:var(--font-weight-bold); padding:var(--spacing-2) var(--spacing-8); border-radius:var(--radius-6); }
  .pf.fail { background:var(--color-red-50); color:var(--color-red-500); }
  .pf.pass { background:var(--color-action-primary-subtle); color:var(--color-action-primary-pressed); }
  .dummy { font-size:var(--font-size-10); color:var(--color-text-helper); border:1px solid var(--color-border-subtle); border-radius:var(--radius-4); padding:var(--spacing-2) var(--spacing-4); margin-left:var(--spacing-4); }
  .num { font-weight:var(--font-weight-bold); color:var(--color-text-danger); }
  .num.zero { color:var(--color-status-success); }
  .empty { color:var(--color-text-caption); padding:var(--spacing-32); text-align:center; }
  .notice { background:var(--color-action-primary-subtle); color:var(--color-action-primary-pressed); border-radius:var(--radius-8); padding:var(--spacing-12) var(--spacing-16); margin-bottom:var(--spacing-16); font-size:var(--font-size-14); }
  .rename { font-size:var(--font-size-12); color:var(--color-text-caption); }
  .rename summary { cursor:pointer; }
  .rename form { display:inline-flex; gap:var(--spacing-6); margin-top:var(--spacing-8); }
  .bulk { display:flex; gap:var(--spacing-8); align-items:center; flex-wrap:wrap; margin:var(--spacing-4) var(--spacing-4) var(--spacing-12); }
  /* 검수 페이지 지우기 — 단추 하나만 오른쪽 끝에. 되돌릴 수 없다는 말은 누를 때 물어보는 창에서 한다. */
  #page-remove { justify-content:flex-end; }
  .bulk .lbl { font-size:var(--font-size-12); color:var(--color-text-caption); }
  .bulk .hint { font-size:var(--font-size-12); color:var(--color-text-helper); }
  td.pick, th.pick { width:32px; padding:0; }
  td.pick .pickbox, th.pick .pickbox { display:flex; align-items:center; justify-content:center;
    min-height:38px; padding:0 var(--spacing-6); cursor:default; }
  .dates { line-height:1.7; }
  .rdate { display:inline-block; font-size:var(--font-size-12); color:var(--color-text-tertiary); background:var(--color-bg-subtle); border-radius:var(--radius-4); padding:var(--spacing-2) var(--spacing-6); margin:0 var(--spacing-2); }
  .rdate b { color:var(--color-text-primary); font-weight:var(--font-weight-bold); margin-right:var(--spacing-4); }
  details summary { cursor:pointer; font-size:var(--font-size-14); color:var(--color-text-tertiary); padding:var(--spacing-10) var(--spacing-4); }
  footer { max-width:1040px; margin:0 auto; padding:0 var(--spacing-28); font-size:var(--font-size-12); color:var(--color-text-helper); }
"""

_DIALOG_CSS = """
  dialog{max-width:1040px;width:90vw;max-height:85vh}   /* 모양은 코어 Modal */
  dialog::backdrop{background:var(--color-overlay)}dialog .dialog-head{display:flex;justify-content:space-between;align-items:center;position:sticky;top:-22px;background:var(--color-bg-subtle);padding:var(--spacing-10) 0;z-index:2}
  dialog .designs{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:var(--spacing-12)}dialog .designs form,dialog .card{border:1px solid var(--color-border-subtle);border-radius:var(--radius-8);background:var(--color-surface-default);padding:var(--spacing-12);margin:var(--spacing-12) 0}
  dialog .designs img{width:100%;height:170px;object-fit:contain}dialog .designs p{font-size:var(--font-size-12);min-height:34px}dialog .row{display:flex;gap:var(--spacing-10);align-items:center}dialog label{display:block;margin:var(--spacing-12) 0 var(--spacing-6)}
  dialog input:not([type=hidden]):not([type=checkbox]):not([type=radio]){width:100%}
  dialog small,dialog .muted{color:var(--color-text-caption)}dialog details{margin:var(--spacing-12) 0}dialog h2{font-size:var(--font-size-16)}dialog button:disabled{opacity:.45}
.fresh{display:inline-block;margin-right:var(--spacing-8);padding:var(--spacing-2) var(--spacing-8);border-radius:var(--radius-full);background:var(--color-action-primary-subtle);border:1px solid var(--color-border-focus);color:var(--color-action-primary-default);font-size:var(--font-size-12);font-weight:var(--font-weight-bold)}
button.upl.armed{border-color:var(--color-action-primary-default);color:var(--color-action-primary-default);background:var(--color-action-primary-subtle)}
"""

_PAGE_CSS = """
  * { box-sizing:border-box; }
  html, body { height:100%; }
  /* 페이지 상세만 풀 너비 + 위 고정 / 카드만 스크롤 */
  body { font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:var(--color-text-primary); margin:0; background:var(--color-bg-subtle); display:flex; flex-direction:column; overflow:hidden; }
  /* 헤더 세 칸: 왼쪽 제목 · 가운데 이전·다음 · 오른쪽 차수 */
  header { background:var(--color-surface-default); border-bottom:1px solid var(--color-border-subtle); padding:var(--spacing-12) var(--spacing-24); display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:var(--spacing-14); flex-shrink:0; }
  .head-left { display:flex; align-items:center; gap:var(--spacing-14); min-width:0; }
  .head-left .back { white-space:nowrap; flex-shrink:0; }
  .head-left h1 { flex-shrink:0; }
  .head-left h1, .head-left .meta { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .page-navigation {justify-self:center;display:flex;align-items:center;gap:var(--spacing-10);font-size:var(--font-size-12);color:var(--color-text-caption);white-space:nowrap;}
  /* 쪽 이동 모양은 코어 Pagination(s1_components) */
  header .back { text-decoration:none; color:var(--color-text-caption); font-size:var(--font-size-14); }
  header h1 { font-size:var(--font-size-16); margin:0; }
  header .meta { font-size:var(--font-size-12); color:var(--color-text-caption); }
  .key { font-family:ui-monospace,monospace; }
  .pf { font-size:var(--font-size-12); font-weight:var(--font-weight-bold); padding:var(--spacing-2) var(--spacing-8); border-radius:var(--radius-6); }
  .pf.fail { background:var(--color-red-50); color:var(--color-red-500); } .pf.pass { background:var(--color-action-primary-subtle); color:var(--color-action-primary-pressed); }
  .rounds { justify-self:end; display:flex; align-items:center; gap:var(--spacing-6); }
  .rlbl { font-size:var(--font-size-12); color:var(--color-text-caption); }
  /* 차수 칩 모양은 코어 Chip(s1_components) — 검정 칩은 가이드에 없다 */
  .rnd { font-size:var(--font-size-10); font-weight:var(--font-weight-bold); color:var(--color-purple-400); background:var(--color-purple-50); border-radius:var(--radius-4); padding:var(--spacing-2) var(--spacing-4); margin-right:var(--spacing-2); }
  #capture-picker{box-sizing:border-box;width:calc(100vw - 32px);max-width:1500px;height:92dvh;max-height:92dvh;overflow:hidden}
  #capture-picker[open]{display:flex;flex-direction:column}
  #capture-picker .s1-modal-inset{flex:1;min-height:0;display:flex;flex-direction:column;gap:var(--spacing-12)}
  #capture-picker .dialog-head{position:static;flex:none;padding:0;gap:var(--spacing-12)}
  #capture-picker h2,#capture-picker h3,#capture-picker p{margin:0}
  #capture-picker form{flex:1;min-height:0;margin:0;display:flex;flex-direction:column;gap:var(--spacing-12)}
  #capture-picker .capture-layout{display:grid;grid-template-columns:minmax(0,1fr) 235px;gap:var(--spacing-16);flex:1;min-height:0}
  #capture-picker .capture-pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--spacing-12);min-height:0;min-width:0}
  #capture-picker .capture-pair section{min-width:0;min-height:0;display:flex;flex-direction:column;background:var(--color-surface-default);border:1px solid var(--color-border-subtle);border-radius:var(--radius-10);overflow:hidden}
  #capture-picker .capture-pair h3{font-size:var(--font-size-12);padding:var(--spacing-12);flex:none}
  #capture-picker .capture-image{flex:1;min-height:0;display:flex;justify-content:center}
  #capture-picker .capture-pair img{width:100%;height:100%;min-width:0;object-fit:contain}
  #capture-picker .capture-list{overflow:auto;min-height:0;font-size:var(--font-size-12)}
  #capture-picker .capture-options{display:flex;flex-direction:column;gap:var(--spacing-4);margin-top:var(--spacing-12)}
  #capture-picker .cap-option{display:flex;align-items:center;gap:var(--spacing-6);margin:0;padding:var(--spacing-10);border:1px solid var(--color-border-default);background:var(--color-surface-default);border-radius:var(--radius-8);cursor:pointer;overflow-wrap:anywhere}
  #capture-picker .cap-option:has(input:checked){border-color:var(--color-action-primary-default);background:var(--color-action-primary-subtle)}
  #capture-picker .cap-option:has(input:focus-visible){outline:2px solid var(--color-border-focus);outline-offset:2px}
  #capture-picker input[type=radio]{position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;opacity:0;clip-path:inset(50%);overflow:hidden}
  #capture-picker .rank{font-size:var(--font-size-12);color:var(--color-text-caption);white-space:nowrap}
  #capture-picker .capture-footer{flex:none;display:flex;justify-content:flex-end}
  .app-view #capture-picker{width:min(calc(100vw - 32px),calc(72dvh + 330px))}
  @media(max-width:700px){#capture-picker .capture-layout{grid-template-columns:1fr;grid-template-rows:minmax(0,1fr) 130px}}
  .cards details{margin:var(--spacing-12) 0}.cards label{display:block;margin:var(--spacing-8) 0}
  .capture-suggestion{font-size:var(--font-size-12);color:var(--color-text-caption);margin:var(--spacing-4) var(--spacing-12);}

  .connection-controls{display:flex;align-items:center;gap:var(--spacing-10);flex-wrap:wrap;font-size:var(--font-size-12);color:var(--color-text-caption);margin-bottom:var(--spacing-10);flex-shrink:0}.connection-controls form{margin:0}
  .wrap { flex:1; min-height:0; display:flex; flex-direction:column; width:100%; padding:var(--spacing-14) var(--spacing-24) 0; }
  .roster { font-size:var(--font-size-12); color:var(--color-text-secondary); margin-bottom:var(--spacing-10); flex-shrink:0; }
  .roster .lbl { color:var(--color-text-caption); margin-right:var(--spacing-8); }
  .person { display:inline-block; background:var(--color-purple-50); color:var(--color-purple-400); border-radius:var(--radius-full); padding:var(--spacing-4) var(--spacing-10); margin-right:var(--spacing-6); }
  /* 비교 영역: 위에 고정, 스크롤에 안 밀림 */
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:var(--spacing-14); flex-shrink:0; height:46vh; margin-bottom:var(--spacing-12); }
  .pane { background:var(--color-surface-default); border:1px solid var(--color-border-subtle); border-radius:var(--radius-12); overflow:hidden; display:flex; flex-direction:column; }
  .pane h3 { box-sizing:border-box; height:44px; font-size:var(--font-size-12); margin:0; padding:var(--spacing-8) var(--spacing-14); border-bottom:1px solid var(--color-bg-subtle); color:var(--color-text-caption); flex-shrink:0; display:flex; align-items:center; gap:var(--spacing-8); }
  /* 비교 헤더 오른쪽 컨트롤 — 단추·라벨 모두 같은 모양(높이·글꼴·테두리) */
  .upl, .upl-group { display:inline-flex; align-items:center; gap:var(--spacing-6); }
  /* 오른쪽으로 몰되, 컨트롤끼리는 붙여 둔다(첫 컨트롤만 빈칸을 먹는다) */
  .pane h3 > .upl, .pane h3 > .upl-group { margin-left:auto; }
  .pane h3 > .upl ~ .upl, .pane h3 > .upl ~ .upl-group,
  .pane h3 > .upl-group ~ .upl, .pane h3 > .upl-group ~ .upl-group { margin-left:0; }
  .upl-group .upl { margin-left:0; }
  .pane h3 button.upl, .upl label, .upl-group label {
    font:inherit; font-size:var(--font-size-12); font-weight:var(--font-weight-bold); line-height:1; color:var(--color-text-secondary);
    height:26px; padding:0 var(--spacing-10); display:inline-flex; align-items:center;
    border:1px solid var(--color-border-default); border-radius:var(--radius-6); background:var(--color-surface-default); cursor:pointer; white-space:nowrap; }
  .pane h3 span.upl { font-size:var(--font-size-12); font-weight:var(--font-weight-medium); color:var(--color-text-caption); }
  .upl input { display:none; }
  .canvas { position:relative; flex:1; min-height:0; background:repeating-linear-gradient(45deg,var(--color-bg-default),var(--color-bg-default) 10px,var(--color-bg-subtle) 10px,var(--color-bg-subtle) 20px); display:flex; align-items:center; justify-content:center; }
  .canvas .ph { color:var(--color-text-helper); font-size:var(--font-size-14); }
  /* 이미지·오버레이 모두 고정 틀(canvas)을 꽉 채우되 비율 유지(contain/meet) → 틀 폭이 안 흔들림 */
  .capimg { display:block; width:100%; height:100%; object-fit:contain; }
  .overlay { position:absolute; inset:0; width:100%; height:100%; }
  /* (1) 박스 레이어 — 클릭 가능. 색은 유형색(인라인 style) */
  .box rect { fill-opacity:.05; stroke-width:4; cursor:pointer; }
  .box:hover rect { fill-opacity:.16; }
  /* 처리된 것: 흐리게(지우지 않음) — 미해결과 한눈에 구분. 클릭은 유지 */
  .box.faded rect { stroke-opacity:.35; fill-opacity:.02; stroke-dasharray:9 7; }
  .box.faded:hover rect { stroke-opacity:.7; }
  .leader.faded { opacity:.25; }
  /* (2) 리더 라인 — 짧게만, 클릭 통과 */
  .leaders { pointer-events:none; }
  .leader { stroke-width:3; opacity:.7; }
  /* (3) 핀 레이어 — 항상 맨 위. 큰 투명 원(.hit)으로 클릭 쉽게. dot 색=유형색(인라인) */
  .pin .hit { fill:transparent; }
  .pin .dot { stroke:var(--color-surface-default); stroke-width:3; }
  .pin text { fill:var(--color-surface-default); font-size:var(--font-size-32); font-weight:var(--font-weight-bold); pointer-events:none; }
  .pin.clickable { cursor:pointer; }
  /* 처리된 핀: 흐리게(반투명+회색끼) 남김. hover하면 잠깐 또렷 */
  .pin.faded { opacity:.35; filter:grayscale(.6); transition:opacity .12s ease, filter .12s ease; }
  .pin.faded:hover, .pin.faded.sel { opacity:.9; filter:grayscale(0); }
  .pinmark { transform-box:fill-box; transform-origin:center; transition:transform .12s ease; }
  .pin:hover .pinmark, .pin.sel .pinmark { transform:scale(1.5); }
  @keyframes pinflash { 0%,100% { opacity:1; } 50% { opacity:.15; } }
  .pin.flash .dot { animation:pinflash .35s ease-in-out 3; }
  .filters { margin:0 0 var(--spacing-10); flex-shrink:0; }
  .chip { margin-right:var(--spacing-6); }   /* 모양은 코어 Chip(line) */
  .hint { font-size:var(--font-size-12); color:var(--color-text-helper); margin-left:var(--spacing-6); }
  /* 카드 영역만 자체 스크롤. 안에 유형별 섹션 → 각 섹션은 여러 열 그리드 */
  .cards { flex:1; min-height:0; overflow-y:auto; position:relative; padding:0 var(--spacing-10) var(--spacing-32) 0; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(350px,1fr)); gap:var(--spacing-16); align-items:start; }
  /* 유형 탭 바 (고정 영역) */
  .tabbar { flex-shrink:0; margin:var(--spacing-2) 0 var(--spacing-12); }   /* 모양은 코어 Line Tab */
  /* 성질 거르개 — 탭과 같은 줄 오른쪽 끝. 탭은 밑줄, 거르개는 알약이라 섞이지 않는다. */
  .fbar { margin-left:auto; display:inline-flex; align-items:center; gap:var(--spacing-6); flex-wrap:wrap; align-self:center; }
  .flbl { font-size:var(--font-size-12); color:var(--color-text-caption); margin-right:var(--spacing-2); }
  .fchip { height:var(--sizing-28); padding:0 var(--spacing-16); border-radius:var(--radius-full);
    border:var(--border-width-1) solid var(--color-chip-line-border-default);
    background:var(--color-chip-line-bg-default); color:var(--color-chip-line-label-default);
    font-size:var(--font-size-12); font-weight:var(--font-weight-medium); line-height:1; cursor:pointer; }
  .fchip:hover { background:var(--color-chip-line-bg-hover); }
  .fchip.on { border-color:var(--color-chip-line-border-selected); color:var(--color-chip-line-label-selected); }
  .auto-part.off { opacity:.35; }
  .tab .sw { display:inline-block; width:var(--spacing-10); height:var(--spacing-10); border-radius:var(--radius-2); margin-right:var(--spacing-8); }
  .tab .cnt { margin-left:var(--spacing-6); font-size:var(--font-size-12); color:var(--color-text-caption); }
  .tab.on .cnt { color:var(--color-navigation-label-selected); }
  /* 카드는 차분하게 + 여백 넉넉히 — 왼쪽 빨간 줄 없음, 유형/상태는 카드 안 태그로 */
  .issue { background:var(--color-surface-default); border:1px solid var(--color-border-subtle); border-radius:var(--radius-12); padding:var(--spacing-16) var(--spacing-16); cursor:pointer; transition:box-shadow .15s, border-color .15s; }
  .issue.hl { border-color:var(--color-status-warning); box-shadow:var(--shadow-raised); }
  .ihead { display:flex; align-items:center; gap:var(--spacing-8); flex-wrap:wrap; }
  /* 성질·출처는 제목 옆 작은 글씨로 — 칩 한 줄을 두지 않아 카드가 커지지 않는다 */
  .ihead .meta { font-size:var(--font-size-12); font-weight:var(--font-weight-regular); color:var(--color-text-caption); margin-left:calc(-1 * var(--spacing-4)); }
  .pinno { width:24px; height:24px; border-radius:50%; color:var(--color-surface-default); font-size:var(--font-size-14); font-weight:var(--font-weight-bold); display:inline-flex; align-items:center; justify-content:center; background:var(--color-text-danger); flex-shrink:0; }
  .pinno.done { background:var(--color-status-success); } .pinno.mid { background:var(--color-text-caption); }
  .type { font-size:var(--font-size-12); font-weight:var(--font-weight-bold); padding:var(--spacing-4) var(--spacing-10); border-radius:var(--radius-6); background:var(--color-purple-50); color:var(--color-purple-400); }
  .state { font-size:var(--font-size-12); font-weight:var(--font-weight-bold); padding:var(--spacing-2) var(--spacing-8); border-radius:var(--radius-6); background:var(--color-red-50); color:var(--color-text-danger); }
  .state.done { background:var(--color-action-primary-subtle); color:var(--color-status-success); } .state.mid { background:var(--color-bg-subtle); color:var(--color-text-secondary); }
  /* 신뢰도는 주의가 아니라 정보다 — 코어 Chip(solid)의 회색을 쓴다 (river 확정 2026-09-14) */
  .sev { font-size:var(--font-size-12); font-weight:var(--font-weight-medium); padding:var(--spacing-2) var(--spacing-8); border-radius:var(--radius-full); background:var(--chip-solid-default-bg); color:var(--chip-solid-default-text); border:var(--border-width-1) solid var(--chip-solid-default-border); }
  .props { margin:var(--spacing-10) 0 var(--spacing-6); }
  .tag { margin:0 var(--spacing-4) var(--spacing-4) 0; }   /* 모양은 코어 Chip(solid) */
  .loc { font-size:var(--font-size-12); color:var(--color-text-helper); font-family:ui-monospace,monospace; }
  .hist { list-style:none; margin:var(--spacing-8) 0 0; padding:var(--spacing-8) 0 0; border-top:1px dashed var(--color-border-subtle); font-size:var(--font-size-12); color:var(--color-text-tertiary); }
  .hist li { margin:var(--spacing-2) 0; }
  .actor { font-weight:var(--font-weight-bold); color:var(--color-text-primary); }
  .actor.off { color:var(--color-text-helper); font-weight:var(--font-weight-regular); }
  .at { color:var(--color-text-helper); }
  .note { color:var(--color-text-state-caution); }
  .passform { display:flex; gap:var(--spacing-6); margin-top:var(--spacing-10); padding-top:var(--spacing-10); border-top:1px dashed var(--color-border-subtle); flex-wrap:wrap; }
  .passform input { flex:1; min-width:110px; }
  .passed { margin-top:var(--spacing-10); padding-top:var(--spacing-8); border-top:1px dashed var(--color-border-subtle); font-size:var(--font-size-12); font-weight:var(--font-weight-bold); color:var(--color-status-success); }
  .muted { color:var(--color-text-helper); }
  .empty { color:var(--color-text-caption); padding:var(--spacing-20); }
"""


_PAGE_JS = """
// ── 복사한 그림 붙여넣기 (Figma에서 프레임을 Copy as PNG 로 복사 → 여기서 ⌘V)
var _pasteTarget = null;
function qaPasteArm(btn){
  if(_pasteTarget && _pasteTarget.btn === btn){ qaPasteCancel(); return; }
  qaPasteCancel();
  _pasteTarget = { btn: btn, action: btn.dataset.action };
  btn.classList.add('armed');
  btn.textContent = '붙여넣기 기다리는 중 · ⌘V';
  window.focus();
}
function qaPasteCancel(){
  if(!_pasteTarget){ return; }
  _pasteTarget.btn.classList.remove('armed');
  _pasteTarget.btn.textContent = '붙여넣기';
  _pasteTarget = null;
}
document.addEventListener('keydown', function(ev){ if(ev.key === 'Escape'){ qaPasteCancel(); } });
document.addEventListener('paste', function(ev){
  if(!_pasteTarget){ return; }
  var items = (ev.clipboardData && ev.clipboardData.items) || [];
  var file = null;
  for(var i = 0; i < items.length; i++){
    if(items[i].type === 'image/png'){ file = items[i].getAsFile(); break; }
  }
  if(!file){
    alert('복사한 그림이 없습니다. Figma에서 프레임을 고른 뒤 ⇧⌘C(Copy as PNG)로 복사하고 다시 붙여넣어 주세요.');
    return;
  }
  ev.preventDefault();
  var target = _pasteTarget;
  target.btn.textContent = '올리는 중…';
  var fd = new FormData();
  fd.append('file', file, 'pasted.png');
  fetch(target.action, { method: 'POST', body: fd })
    .then(function(r){
      if(!r.ok){ throw new Error('업로드 실패'); }
      location.reload();
    })
    .catch(function(){
      alert('붙여넣은 그림을 올리지 못했습니다. 다시 시도해 주세요.');
      qaPasteCancel();
    });
});
function _clearHL(){
  document.querySelectorAll('.issue.hl').forEach(function(e){ e.classList.remove('hl'); });
  document.querySelectorAll('.pin.flash').forEach(function(e){ e.classList.remove('flash'); });
  document.querySelectorAll('.pin.sel').forEach(function(e){ e.classList.remove('sel'); });
}
// 겹친 핀은 맨 뒤에 있으면 안 잡히므로, 마우스 올리면 DOM 맨 끝으로 옮겨 맨 앞에 그린다
function bringFront(g){ g.parentNode.appendChild(g); }
// 카드 박스 안에서만 스크롤. box.scrollTop 직접 지정이라 어떤 환경에서도 확실히 이동한다.
// (네이티브 smooth/ rAF는 탭이 그리지 않는 환경에선 멈춰서 안 먹는다 → 직접 지정으로 보장)
function _scrollBox(box, target){
  var max = box.scrollHeight - box.clientHeight;
  target = Math.max(0, Math.min(target, max));
  try { box.scrollTo({ top: target, behavior: 'smooth' }); } catch(e) {}  // 지원되면 부드럽게
  box.scrollTop = target;  // 항상 확실히 착지
}
// 핀 클릭 → '카드 박스 안에서만' 해당 카드로 스크롤 + 하이라이트.
// 페이지 전체는 안 밀린다(개발화면을 계속 보면서 카드만 이동). 여러 열이어도 id로 정확히 찾음.
function _selPin(uuid){
  var p = document.getElementById('pin-' + uuid);
  if(!p){ return; }
  p.classList.add('sel');   // 그 핀만 커지고
  bringFront(p);            // 맨 앞으로
}
// 유형 탭 전환 (그 그룹 카드만 보이게)
// ── 성질 거르개: 고른 성질을 품은 카드만 남기고, 카드 안에서도 그 줄만 진하게 ──
function filterType(btn){
  var t = btn.getAttribute('data-type') || '';
  document.querySelectorAll('.fchip').forEach(function(c){ c.classList.toggle('on', c === btn); });
  document.querySelectorAll('.issue').forEach(function(card){
    var have = (card.getAttribute('data-types') || '').split(',').filter(Boolean);
    card.hidden = !!t && have.indexOf(t) < 0;
  });
  document.querySelectorAll('.auto-part').forEach(function(part){
    part.classList.toggle('off', !!t && part.getAttribute('data-type') !== t);
  });
  var box = document.getElementById('cards'); if(box){ box.scrollTop = 0; }
}
function showTab(gi){
  gi = String(gi);
  document.querySelectorAll('.panel').forEach(function(p){ p.hidden = (p.id !== 'panel-' + gi); });
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('on', t.getAttribute('data-idx') === gi); });
  var box = document.getElementById('cards'); if(box){ box.scrollTop = 0; }
}
function focusCard(uuid){
  _clearHL();
  var c = document.getElementById('issue-' + uuid);
  var box = document.getElementById('cards');
  if(!c || !box){ return; }
  var panel = c.closest('.panel');        // 그 카드가 속한 탭으로 먼저 전환
  if(panel){ showTab(panel.id.replace('panel-', '')); }
  c.classList.add('hl');
  _selPin(uuid);
  if(window.qaCompareIssue) window.qaCompareIssue(uuid);
  _scrollBox(box, c.offsetTop - (box.clientHeight - c.offsetHeight) / 2);
}
// 통과 처리 제출 전 확인(사유 필수)
function _confirmPass(f){
  var r = (f.reason.value || '').trim();
  if(!r){ alert('통과 사유를 입력하세요.'); return false; }
  return confirm('이 이슈를 「협의통과」로 처리할까요?\\n사유: ' + r);
}
// 카드 클릭 → 같은 uuid 핀이 커지고 맨 앞으로(+깜빡). 개발화면은 상단 고정이라 스크롤 불필요.
function focusPin(uuid){
  _clearHL();
  var p = document.getElementById('pin-' + uuid);
  if(!p){ return; }
  var c = document.getElementById('issue-' + uuid);
  if(c){ c.classList.add('hl'); }
  void p.getBoundingClientRect();
  p.classList.add('flash');
  _selPin(uuid);
  if(window.qaCompareIssue) window.qaCompareIssue(uuid);
}
"""


# 코드를 고쳐 포털이 다시 켜지면, 열어 둔 화면도 스스로 새로고침한다. (run_portal.py 로 켤 때만 붙는다)
_RELOAD_JS = """<script>
(function(){
  var boot=null;
  function tick(){
    fetch('/__rev',{cache:'no-store'}).then(function(r){return r.text()}).then(function(v){
      if(boot===null){boot=v}
      else if(v!==boot){location.reload()}
    }).catch(function(){});
  }
  setInterval(tick,1000); tick();
})();
</script>"""

def main():
    if not REAL_DB.exists():
        raise SystemExit(
            f"{REAL_DB} 없음. 먼저: python load_fixture.py fixtures/tb-web-001.json mvp0-real.db"
        )
    intake().init()
    srv = HTTPServer((HOST, PORT), Handler)
    if HOST == "127.0.0.1":
        print(f"포털 실행 → http://127.0.0.1:{PORT}  (이 컴퓨터에서만, Ctrl+C 종료)")
    else:
        print(f"포털 실행 → http://{_lan_ip()}:{PORT}  (같은 사무실 네트워크에서 접속, Ctrl+C 종료)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
