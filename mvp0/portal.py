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
import json
import uuid as uuidmod
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import groupby
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import db as dbmod
import queries
from constants import UNRESOLVED_STATUSES, CLOSED_STATUSES

BASE = Path(__file__).resolve().parent
REAL_DB = BASE / "mvp0-real.db"   # 실제본만. 합성본 mvp0.db는 의도적으로 제외.
UPLOADS = BASE / "uploads"        # 업로드된 PNG 로컬 저장 (경로만 DB, 파일은 .gitignore)
PORT = 8765


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
    return f'<span class="pf {v.lower()}">{_esc(v.upper() or "—")}</span>'


def _upl(human_key, page_uuid, side):
    """PNG 업로드 컨트롤 (선택 즉시 제출 → 로컬 저장 → 표시)."""
    action = f"/screen/{_esc(human_key)}/page/{_esc(page_uuid)}/upload?side={side}"
    return (
        f'<form class="upl" method="post" enctype="multipart/form-data" action="{action}">'
        f'<label>PNG 업로드<input type="file" name="file" accept="image/png" '
        f'onchange="this.form.submit()"></label></form>'
    )


def _status_class(status):
    if status in UNRESOLVED_STATUSES:
        return "open"
    if status in CLOSED_STATUSES:
        return "done"
    return "mid"


def _save_upload(page_uuid, side, data, size):
    """PNG를 로컬 저장하고 경로만 DB에 기록. dev면 원본 크기 기록 + 기준높이(coord_ref_h)를
    이미지 비율로 산출(coord_ref_w=1920 고정) → 어떤 배율로 올려도 핀이 안 밀림."""
    UPLOADS.mkdir(exist_ok=True)
    fname = f"{page_uuid}_{side}.png"
    (UPLOADS / fname).write_bytes(data)
    w, h = size
    conn = dbmod.connect(REAL_DB)
    if side == "dev":
        ref_w = conn.execute(
            "SELECT coord_ref_w FROM inspection_page WHERE uuid=?", (page_uuid,)
        ).fetchone()["coord_ref_w"] or 1920
        ref_h = round(h * ref_w / w) if w else 1080     # 업로드 이미지 비율로 기준높이 산출
        conn.execute(
            "UPDATE inspection_page SET dev_img=?, dev_img_w=?, dev_img_h=?, coord_ref_h=? WHERE uuid=?",
            (fname, w, h, ref_h, page_uuid),
        )
    else:
        conn.execute("UPDATE inspection_page SET design_img=? WHERE uuid=?", (fname, page_uuid))
    conn.commit()
    conn.close()


def _pass_issue(issue_uuid, actor, reason):
    """'협의통과' 처리: status만 갱신(행 삭제 없음) + issue_history에 한 줄 append(누가·언제·왜)."""
    conn = dbmod.connect(REAL_DB)
    row = conn.execute(
        "SELECT status, page_id FROM inspection_issue WHERE uuid=?", (issue_uuid,)
    ).fetchone()
    if row is None:
        conn.close()
        return
    old = row["status"]
    rr = conn.execute(
        "SELECT MAX(round) m FROM inspection_run WHERE page_id=?", (row["page_id"],)
    ).fetchone()
    resolved_round = rr["m"] if rr else None
    conn.execute(
        "UPDATE inspection_issue SET status=?, resolved_round=? WHERE uuid=?",
        ("협의통과", resolved_round, issue_uuid),
    )
    seq = conn.execute(
        "SELECT COALESCE(MAX(seq), -1) + 1 AS s FROM issue_history WHERE issue_id=?", (issue_uuid,)
    ).fetchone()["s"]
    conn.execute(
        """INSERT INTO issue_history(uuid, issue_id, from_status, to_status, actor, at, note, seq)
           VALUES (?,?,?,?,?,?,?,?)""",
        (uuidmod.uuid4().hex, issue_uuid, old, "협의통과", actor,
         datetime.now().isoformat(timespec="seconds"), reason, seq),
    )
    conn.commit()
    conn.close()


_TYPE_LABEL = {
    "typography": "텍스트", "layout": "레이아웃", "spacing": "간격",
    "color": "색상", "structure": "구조", "mixed": "복합", "missing": "누락",
}


def _type_label(category):
    """오류 유형(category)을 한국어 라벨로. 'typography-font-size'처럼 접두어만 봐도 매핑."""
    if not category:
        return "기타"
    key = category.split("-")[0]
    return _TYPE_LABEL.get(key, category)


# 유형별 색 — 핀 색 = 그 유형 섹션 색(같은 기준). 유형끼리 충분히 구분되게.
_TYPE_COLOR = {
    "typography": "#2563eb",  # 텍스트 · 파랑
    "layout": "#7c3aed",      # 레이아웃 · 보라
    "spacing": "#0d9488",     # 간격 · 청록
    "color": "#db2777",       # 색상 · 분홍
    "structure": "#d97706",   # 구조 · 주황
    "mixed": "#334155",       # 복합 · 진회색
    "missing": "#dc2626",     # 누락 · 빨강
}


def _type_color(category):
    if not category:
        return "#6b7280"
    return _TYPE_COLOR.get(category.split("-")[0], "#6b7280")


# ────────────────────────────────────────────────────────────── 화면 목록
def render_list(unresolved_only: bool, round_filter):
    conn = dbmod.connect(REAL_DB)
    rows = queries.list_screens(conn, unresolved_only, round_filter)
    conn.close()

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
            trs += f"""<tr onclick="location.href='/screen/{_esc(r['human_key'])}'">
              <td class="name">{_esc(r['name'])}</td>
              <td class="key">{_esc(r['human_key'])}</td>
              <td>{_esc(r['platform'])}</td>
              <td class="ctr">{r['page_count']}개</td>
              <td class="ctr">{_pf_badge(r['pass_fail'])}</td>
              <td class="ctr"><span class="{unres_cls}">{unres}</span> / {r['total']}</td>
            </tr>"""
        groups_html += f"""
        <section class="group">
          <h2>{_esc(project)} <span class="muted">· 화면 {len(items)}</span></h2>
          <table>
            <thead><tr>
              <th>화면명</th><th>스토리보드 ID</th><th>플랫폼</th>
              <th class="ctr">검수 페이지</th><th class="ctr">Pass/Fail(종합)</th><th class="ctr">미해결 / 전체</th>
            </tr></thead>
            <tbody>{trs}</tbody>
          </table>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수 포털 — 화면 목록</title>
<style>{_LIST_CSS}</style></head>
<body>
  <header>
    <h1>검수 포털 <span class="muted" style="font-weight:400;font-size:13px;">· 화면 목록</span></h1>
    <div class="sub">실제 검수 데이터(mvp0-real.db) · 행 클릭 → 화면 상세(검수 페이지 목록)</div>
  </header>
  <div class="wrap">
    <div class="filters"><span class="lbl">보기</span> {un_filters}</div>
    {groups_html}
  </div>
  <footer>미해결 정의 = {" / ".join(UNRESOLVED_STATUSES)} · 원본 = SQLite(DB), 이 화면은 렌더링 뷰</footer>
</body></html>"""


# ────────────────────────────────────────────────────── 화면 상세 = 페이지 목록
def render_screen(human_key: str):
    conn = dbmod.connect(REAL_DB)
    scr = queries.get_screen(conn, human_key)
    if scr is None:
        conn.close()
        return None
    s = scr["row"]
    pages = queries.pages_of_screen(conn, s["uuid"])
    agg = queries.screen_pass_fail(conn, s["uuid"])
    conn.close()

    if pages:
        rows = ""
        for p in pages:
            dummy = '<span class="dummy">더미</span>' if p["note"] else ""
            un = p["unresolved"]
            uncls = "num zero" if un == 0 else "num"
            rows += f"""<tr onclick="location.href='/screen/{_esc(human_key)}/page/{p['uuid']}'">
              <td class="ctr">{p['seq']}</td>
              <td class="name">{_esc(p['name'])} {dummy}</td>
              <td class="ctr">{_pf_badge(p['pass_fail'])}</td>
              <td class="ctr"><span class="{uncls}">{un}</span> / {p['total']}</td>
            </tr>"""
    else:
        rows = '<tr><td colspan="4" class="ctr">검수 페이지 없음</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(s['name'])} — 검수 페이지 목록</title>
<style>{_LIST_CSS}</style></head>
<body>
  <header class="row">
    <a class="back" href="/">← 목록</a>
    <h1>{_esc(s['name'])}</h1>
    <span class="sub2"><span class="key">{_esc(s['human_key'])}</span> · {_esc(s['platform'])} · 종합 {_pf_badge(agg)}</span>
    <a class="btn" href="/report/{_esc(human_key)}" target="_blank">화면 전체 A4</a>
  </header>
  <div class="wrap">
    <section class="group">
      <h2>검수 페이지 <span class="muted">· {len(pages)}개 (행 클릭 → 페이지 상세)</span></h2>
      <table>
        <thead><tr>
          <th class="ctr">순번</th><th>검수 페이지</th><th class="ctr">Pass/Fail</th><th class="ctr">미해결 / 전체</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
  </div>
  <footer>화면 종합 Pass/Fail = 페이지 중 하나라도 FAIL이면 FAIL · 원본 = SQLite(DB)</footer>
</body></html>"""


# ──────────────────────────────────────────────────────────── 페이지 상세
def render_page(page_uuid: str):
    conn = dbmod.connect(REAL_DB)
    pg = queries.get_page(conn, page_uuid)
    if pg is None:
        conn.close()
        return None
    page, s = pg["page"], pg["screen"]
    human_key = s["human_key"]
    issues = queries.issues_of_page(conn, page_uuid)          # 전체(번호 고정용)
    persons = queries.list_persons(conn, active_only=True)
    roster = queries.roster_names(conn)
    hist_by_issue = {i["uuid"]: queries.history_of_issue(conn, i["uuid"]) for i in issues}
    conn.close()

    number = {i["rid"]: n + 1 for n, i in enumerate(issues)}  # 페이지 안 순번 1..N
    # 미해결 = 유형 탭 / 처리됨(검수완료·오류아님·협의통과) = '처리됨' 탭
    unresolved = [i for i in issues if i["status"] in UNRESOLVED_STATUSES]
    resolved = [i for i in issues if i["status"] in CLOSED_STATUSES]

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
        fd = " faded" if i["status"] in CLOSED_STATUSES else ""   # 처리된 것은 흐리게(지우지 않음)
        boxes += (
            f'<g class="box{fd}" onclick="focusCard(\'{uid}\')">'
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
    # 핀 비율(%)의 분모 = coord_ref(캡처 기준 크기). SVG viewBox를 그 크기로 두면
    # box 좌표가 자동으로 '기준 대비 비율'로 렌더 → 올린 이미지 배율이 달라도 안 밀림.
    dev_img = page["dev_img"]
    design_img = page["design_img"]
    vb_w = page["coord_ref_w"] or 1920
    vb_h = page["coord_ref_h"] or 1080
    par = "none" if dev_img else "xMidYMin meet"   # 이미지 위엔 정확 매핑, 자리표시엔 비율 유지
    overlay = (
        f'<svg viewBox="0 0 {vb_w} {vb_h}" preserveAspectRatio="{par}" class="overlay">'
        f'<g class="boxes">{boxes}</g>'
        f'<g class="leaders">{leaders}</g>'
        f'<g class="pins">{dots}</g>'
        f"</svg>"
    )

    # 좌: 디자인 이미지(핀 없음) / 우: 개발 이미지 + 핀 오버레이. 없으면 자리표시 유지.
    if design_img:
        left_body = f'<div class="imgwrap"><img class="capimg" src="/uploads/{_esc(design_img)}" alt="디자인"></div>'
    else:
        left_body = '<span class="ph">디자인 이미지 자리표시</span>'
    if dev_img:
        right_body = f'<div class="imgwrap"><img class="capimg" src="/uploads/{_esc(dev_img)}" alt="개발화면">{overlay}</div>'
    else:
        right_body = f'<span class="ph">개발 이미지 자리표시</span>{overlay}'

    person_options = "".join(f'<option value="{_esc(p["name"])}">{_esc(p["name"])}</option>' for p in persons)

    def issue_card(i):
        n = number[i["rid"]]
        cls = _status_class(i["status"])
        unres = i["status"] in UNRESOLVED_STATUSES
        props = json.loads(i["properties"]) if i["properties"] else []
        props_html = "".join(f'<span class="tag">{_esc(p)}</span>' for p in props)
        loc = f'({i["box_x"]},{i["box_y"]}) {i["box_w"]}×{i["box_h"]}'
        sev_html = f'<span class="sev">{_esc(i["severity"])}</span>' if i["severity"] else ""
        type_color = _type_color(i["category"])
        state_label = "미해결" if unres else i["status"]   # 처리됨은 실제 상태(협의통과/검수완료/오류아님) 그대로
        rows = ""
        for h in hist_by_issue[i["uuid"]]:
            actor = h["actor"]
            actor_html = (
                f'<span class="actor">{_esc(actor)}</span>' if actor in roster
                else f'<span class="actor off" title="담당자 명단에 없음">{_esc(actor or "미지정")} ⚠</span>'
            )
            change = f'{_esc(h["from_status"] or "(신규)")} → {_esc(h["to_status"])}'
            note = f' <span class="note">— {_esc(h["note"])}</span>' if h["note"] else ""
            rows += (f'<li>{actor_html} · <span class="at">{_esc(h["at"] or "시각 없음")}</span> · '
                     f'{change}{note}</li>')
        # 미해결 카드에만 통과 처리 폼(담당자 선택 + 사유 필수). 처리됨 카드는 사유·이력만.
        if unres:
            action = f"/screen/{_esc(human_key)}/page/{_esc(page_uuid)}/pass"
            foot = (
                f'<form class="passform" method="post" action="{action}" '
                f'onsubmit="return _confirmPass(this)" onclick="event.stopPropagation()">'
                f'<input type="hidden" name="issue" value="{i["uuid"]}">'
                f'<select name="actor" required>{person_options}</select>'
                f'<input name="reason" maxlength="200" required placeholder="통과 사유 (필수)">'
                f'<button type="submit">통과 처리</button>'
                f"</form>"
            )
        else:
            foot = '<div class="passed">✓ 처리됨 (이력·사유는 위 참조)</div>'
        return f"""<div class="issue {cls}" id="issue-{i['uuid']}" data-issue="{i['uuid']}" onclick="focusPin('{i['uuid']}')">
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

    # 미해결을 오류 유형별 그룹 → '탭'. 맨 끝에 '처리됨' 탭 추가.
    groups, gcat = {}, {}
    for i in unresolved:
        lbl = _type_label(i["category"])
        groups.setdefault(lbl, []).append(i)
        gcat[lbl] = i["category"]
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    # (라벨, 색, 아이템들) 순서: 유형 탭들 + 처리됨 탭
    tab_defs = [(lbl, _type_color(gcat[lbl]), items) for lbl, items in ordered]
    tab_defs.append(("처리됨", "#9ca3af", resolved))

    tabbar = panels = ""
    for gi, (lbl, col, items) in enumerate(tab_defs):
        tabbar += (
            f'<button class="tab{" on" if gi == 0 else ""}" data-idx="{gi}" onclick="showTab(\'{gi}\')">'
            f'<span class="sw" style="background:{col}"></span>{_esc(lbl)} '
            f'<span class="cnt">{len(items)}</span></button>'
        )
        cards = "".join(issue_card(i) for i in items) or '<p class="empty">항목 없음</p>'
        panels += (
            f'<div class="panel" id="panel-{gi}"{"" if gi == 0 else " hidden"}>'
            f'<div class="grid">{cards}</div></div>'
        )
    issues_html = panels

    roster_html = "".join(
        f'<span class="person">{_esc(p["name"])}'
        f'{" · " + _esc(p["affiliation"]) if p["affiliation"] else ""}</span>'
        for p in persons
    ) or '<span class="muted">명단 비어있음</span>'

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(page['name'])} — 페이지 상세</title>
<style>{_PAGE_CSS}</style></head>
<body>
  <header>
    <a class="back" href="/screen/{_esc(human_key)}">← 검수 페이지 목록</a>
    <h1>{_esc(page['name'])}</h1>
    <span class="meta">{_esc(s['name'])} · <span class="key">{_esc(human_key)}</span> · 페이지 {_pf_badge(pg['pass_fail'])}</span>
  </header>
  <div class="wrap">
    <div class="roster"><span class="lbl">담당자 명단</span>{roster_html}</div>

    <div class="cols">
      <div class="pane">
        <h3>좌 · 디자인 (정답 모습 — 핀 없음) {_upl(human_key, page_uuid, "design")}</h3>
        <div class="canvas">{left_body}</div>
      </div>
      <div class="pane">
        <h3>우 · 개발 (핀 = 발견 위치) {_upl(human_key, page_uuid, "dev")}</h3>
        <div class="canvas">{right_body}</div>
      </div>
    </div>

    <div class="filters"><span class="hint">미해결은 유형 탭 · 처리된 건 '처리됨' 탭 · 핀 클릭 → 그 탭으로 이동 + 카드 강조</span></div>
    <div class="tabbar">{tabbar}</div>
    <div class="cards" id="cards">{issues_html}</div>
  </div>
  <script>{_PAGE_JS}</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        path = parsed.path
        unresolved_only = q.get("unresolved", ["0"])[0] == "1"

        if path == "/":
            round_filter = int(q["round"][0]) if "round" in q else None
            self._html(render_list(unresolved_only, round_filter))
        elif "/page/" in path and path.startswith("/screen/"):
            page_uuid = path.rsplit("/page/", 1)[1]
            page = render_page(page_uuid)
            self._html(page if page else self._nf("페이지 없음"), 200 if page else 404)
        elif path.startswith("/screen/"):
            human_key = path[len("/screen/"):]
            page = render_screen(human_key)
            self._html(page if page else self._nf(f"화면 없음: {human_key}"), 200 if page else 404)
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
            self._html("<p style='font-family:sans-serif;padding:40px'>화면 전체 A4 반출은 다음 조각입니다. "
                       "<a href='javascript:history.back()'>← 뒤로</a></p>")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        if path.startswith("/screen/") and "/page/" in path and path.endswith("/pass"):
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            issue = form.get("issue", [""])[0]
            actor = form.get("actor", [""])[0].strip()
            reason = form.get("reason", [""])[0].strip()
            if issue and reason:                       # 사유 필수 — 빈 사유는 무시
                _pass_issue(issue, actor, reason)
            self.send_response(303)                    # 처리 후 페이지 상세로 리다이렉트
            self.send_header("Location", path[:-len("/pass")])
            self.end_headers()
        elif path.startswith("/screen/") and "/page/" in path and path.endswith("/upload"):
            side = parse_qs(parsed.query).get("side", [""])[0]
            page_uuid = path[:-len("/upload")].rsplit("/page/", 1)[1]
            body = self.rfile.read(length)
            data = _multipart_file(body, self.headers.get("Content-Type", ""))
            size = _png_size(data)                     # PNG만 허용(아니면 무시)
            if data and size and side in ("design", "dev"):
                _save_upload(page_uuid, side, data, size)
            self.send_response(303)
            self.send_header("Location", path[:-len("/upload")])
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    @staticmethod
    def _nf(msg):
        return f"<p style='font-family:sans-serif;padding:40px'>{_esc(msg)} <a href='/'>← 목록</a></p>"

    def _html(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # 콘솔 조용히


_LIST_CSS = """
  * { box-sizing: border-box; }
  body { font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:#1a1a1a; margin:0; background:#f6f7f9; }
  header { background:#fff; border-bottom:1px solid #e5e7eb; padding:18px 28px; }
  header.row { display:flex; align-items:center; gap:14px; flex-wrap:wrap; padding:14px 28px; }
  h1 { font-size:18px; margin:0; }
  .back { text-decoration:none; color:#6b7280; font-size:13px; }
  .sub { font-size:12px; color:#6b7280; margin-top:4px; }
  .sub2 { font-size:12px; color:#6b7280; }
  .btn { margin-left:auto; font-size:13px; padding:7px 14px; border:1px solid #d1d5db; border-radius:8px; background:#fff; color:#374151; text-decoration:none; }
  .wrap { max-width:1040px; margin:0 auto; padding:20px 28px 60px; }
  .filters { display:flex; gap:10px; align-items:center; margin:6px 0 20px; flex-wrap:wrap; }
  .filters .lbl { font-size:12px; color:#6b7280; }
  .chip { display:inline-block; padding:5px 12px; margin-right:6px; border:1px solid #d1d5db; border-radius:999px; font-size:13px; text-decoration:none; color:#374151; background:#fff; }
  .chip.on { background:#111827; color:#fff; border-color:#111827; }
  .group { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:6px 14px 14px; margin-bottom:18px; }
  h2 { font-size:14px; margin:14px 4px 8px; }
  .muted { color:#9ca3af; font-weight:400; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:10px 12px; border-bottom:1px solid #f0f1f3; text-align:left; }
  th { font-size:11px; color:#6b7280; font-weight:600; }
  tbody tr { cursor:pointer; }
  tbody tr:hover { background:#f9fafb; }
  .name { font-weight:600; }
  .key { font-family:ui-monospace,monospace; color:#4b5563; }
  .ctr { text-align:center; white-space:nowrap; }
  .pf { font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }
  .pf.fail { background:#fef2f2; color:#b42318; }
  .pf.pass { background:#ecfdf3; color:#12864e; }
  .dummy { font-size:10px; color:#9ca3af; border:1px solid #e5e7eb; border-radius:5px; padding:1px 5px; margin-left:4px; }
  .num { font-weight:700; color:#b42318; }
  .num.zero { color:#12864e; }
  .empty { color:#6b7280; padding:30px; text-align:center; }
  footer { max-width:1040px; margin:0 auto; padding:0 28px; font-size:11px; color:#9ca3af; }
"""

_PAGE_CSS = """
  * { box-sizing:border-box; }
  html, body { height:100%; }
  /* 페이지 상세만 풀 너비 + 위 고정 / 카드만 스크롤 */
  body { font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; color:#1a1a1a; margin:0; background:#f6f7f9; display:flex; flex-direction:column; overflow:hidden; }
  header { background:#fff; border-bottom:1px solid #e5e7eb; padding:12px 24px; display:flex; align-items:center; gap:14px; flex-wrap:wrap; flex-shrink:0; }
  header .back { text-decoration:none; color:#6b7280; font-size:13px; }
  header h1 { font-size:16px; margin:0; }
  header .meta { font-size:12px; color:#6b7280; }
  .key { font-family:ui-monospace,monospace; }
  .pf { font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }
  .pf.fail { background:#fef2f2; color:#b42318; } .pf.pass { background:#ecfdf3; color:#12864e; }
  .wrap { flex:1; min-height:0; display:flex; flex-direction:column; width:100%; padding:14px 24px 0; }
  .roster { font-size:12px; color:#374151; margin-bottom:10px; flex-shrink:0; }
  .roster .lbl { color:#6b7280; margin-right:8px; }
  .person { display:inline-block; background:#eef2ff; color:#3730a3; border-radius:999px; padding:3px 10px; margin-right:6px; }
  /* 비교 영역: 위에 고정, 스크롤에 안 밀림 */
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:14px; flex-shrink:0; height:46vh; margin-bottom:12px; }
  .pane { background:#fff; border:1px solid #e5e7eb; border-radius:12px; overflow:hidden; display:flex; flex-direction:column; }
  .pane h3 { font-size:12px; margin:0; padding:9px 14px; border-bottom:1px solid #f0f1f3; color:#6b7280; flex-shrink:0; display:flex; align-items:center; gap:8px; }
  .upl { margin-left:auto; }
  .upl label { font-size:11px; font-weight:600; color:#374151; border:1px solid #d1d5db; border-radius:6px; padding:2px 9px; background:#fff; cursor:pointer; }
  .upl input { display:none; }
  .canvas { position:relative; flex:1; min-height:0; background:repeating-linear-gradient(45deg,#fafafa,#fafafa 10px,#f3f4f6 10px,#f3f4f6 20px); display:flex; align-items:center; justify-content:center; }
  .canvas .ph { color:#9ca3af; font-size:13px; }
  /* 이미지 래퍼가 이미지 크기에 딱 맞고, 오버레이는 그 위에 inset:0 → 핀이 이미지에 정확히 정렬 */
  .imgwrap { position:relative; display:inline-flex; max-width:100%; max-height:100%; }
  .capimg { display:block; max-width:100%; max-height:100%; object-fit:contain; }
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
  .pin .dot { stroke:#fff; stroke-width:3; }
  .pin text { fill:#fff; font-size:34px; font-weight:800; pointer-events:none; }
  .pin.clickable { cursor:pointer; }
  /* 처리된 핀: 흐리게(반투명+회색끼) 남김. hover하면 잠깐 또렷 */
  .pin.faded { opacity:.35; filter:grayscale(.6); transition:opacity .12s ease, filter .12s ease; }
  .pin.faded:hover, .pin.faded.sel { opacity:.9; filter:grayscale(0); }
  .pinmark { transform-box:fill-box; transform-origin:center; transition:transform .12s ease; }
  .pin:hover .pinmark, .pin.sel .pinmark { transform:scale(1.5); }
  @keyframes pinflash { 0%,100% { opacity:1; } 50% { opacity:.15; } }
  .pin.flash .dot { animation:pinflash .35s ease-in-out 3; }
  .filters { margin:0 0 10px; flex-shrink:0; }
  .chip { display:inline-block; padding:4px 12px; margin-right:6px; border:1px solid #d1d5db; border-radius:999px; font-size:13px; text-decoration:none; color:#374151; background:#fff; }
  .chip.on { background:#111827; color:#fff; border-color:#111827; }
  .hint { font-size:11px; color:#9ca3af; margin-left:6px; }
  /* 카드 영역만 자체 스크롤. 안에 유형별 섹션 → 각 섹션은 여러 열 그리드 */
  .cards { flex:1; min-height:0; overflow-y:auto; position:relative; padding:0 10px 30px 0; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(350px,1fr)); gap:18px; align-items:start; }
  /* 유형 탭 바 (고정 영역) */
  .tabbar { flex-shrink:0; display:flex; gap:8px; flex-wrap:wrap; margin:2px 0 12px; }
  .tab { display:inline-flex; align-items:center; font-size:13px; font-weight:700; color:#374151; background:#fff; border:1px solid #d1d5db; border-radius:999px; padding:6px 14px; cursor:pointer; }
  .tab .sw { display:inline-block; width:11px; height:11px; border-radius:3px; margin-right:7px; }
  .tab .cnt { margin-left:6px; font-size:12px; font-weight:700; color:#6b7280; }
  .tab.on { background:#111827; color:#fff; border-color:#111827; }
  .tab.on .cnt { color:#d1d5db; }
  /* 카드는 차분하게 + 여백 넉넉히 — 왼쪽 빨간 줄 없음, 유형/상태는 카드 안 태그로 */
  .issue { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:16px 18px; cursor:pointer; transition:box-shadow .15s, border-color .15s; }
  .issue.hl { border-color:#f59e0b; box-shadow:0 0 0 3px rgba(245,158,11,.55); }
  .ihead { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .pinno { width:24px; height:24px; border-radius:50%; color:#fff; font-size:13px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; background:#b42318; flex-shrink:0; }
  .pinno.done { background:#12864e; } .pinno.mid { background:#6b7280; }
  .type { font-size:12px; font-weight:700; padding:3px 10px; border-radius:6px; background:#eef2ff; color:#3730a3; }
  .state { font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; background:#fef2f2; color:#b42318; }
  .state.done { background:#ecfdf3; color:#12864e; } .state.mid { background:#f3f4f6; color:#374151; }
  .sev { font-size:10px; font-weight:700; padding:2px 7px; border-radius:6px; background:#fff7ed; color:#c2410c; border:1px solid #fed7aa; }
  .props { margin:10px 0 6px; }
  .tag { display:inline-block; font-size:11px; background:#f3f4f6; color:#374151; border-radius:6px; padding:2px 8px; margin:0 5px 5px 0; }
  .loc { font-size:11px; color:#9ca3af; font-family:ui-monospace,monospace; }
  .hist { list-style:none; margin:8px 0 0; padding:8px 0 0; border-top:1px dashed #eee; font-size:12px; color:#4b5563; }
  .hist li { margin:2px 0; }
  .actor { font-weight:600; color:#111827; }
  .actor.off { color:#9ca3af; font-weight:400; }
  .at { color:#9ca3af; }
  .note { color:#b45309; }
  .passform { display:flex; gap:6px; margin-top:10px; padding-top:10px; border-top:1px dashed #eee; flex-wrap:wrap; }
  .passform select, .passform input { font-size:12px; padding:5px 8px; border:1px solid #d1d5db; border-radius:6px; background:#fff; }
  .passform input { flex:1; min-width:110px; }
  .passform button { font-size:12px; font-weight:700; padding:5px 12px; border:1px solid #111827; background:#111827; color:#fff; border-radius:6px; cursor:pointer; }
  .passed { margin-top:10px; padding-top:8px; border-top:1px dashed #eee; font-size:12px; font-weight:700; color:#12864e; }
  .muted { color:#9ca3af; }
  .empty { color:#6b7280; padding:20px; }
"""


_PAGE_JS = """
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
}
"""


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
