"""검수 묶음(화면) 한 개를 빈 채로 만든다 — 왼쪽 메뉴의 '+ 검수 묶음 추가'.

검수 아래에 서는 것은 **사람이 이름 지은 묶음**이다(로그인 · 공통 · 각 메뉴 …).
표는 이미 있는 `screen` 을 그대로 쓴다 — 새 표를 만들지 않는다(CLAUDE.md 6번).
페이지를 그 묶음으로 옮기는 것은 이미 있는 '고른 페이지 옮기기'(`page_move.py`)가 한다.

여기서 하는 일은 **빈 묶음 한 줄 세우기**뿐이고, 지우는 길은 두지 않는다(2번-3).
"""
import json
import re
import uuid as uuidmod
from datetime import datetime

import page_move


def _번호붙은키(conn, project_uuid, service_code, platform):
    """같은 과제에서 쓰던 사람키의 다음 번호. 처음이면 서비스 코드로 첫 줄을 짓는다."""
    마지막 = conn.execute(
        "SELECT human_key FROM screen WHERE project_id=? ORDER BY human_key DESC LIMIT 1",
        (project_uuid,)).fetchone()
    if 마지막 and 마지막["human_key"]:
        후보 = page_move.키제안(conn, 마지막["human_key"])
        if 후보:
            return 후보
    바탕 = re.sub(r"[^A-Za-z0-9_]+", "", (service_code or "").upper()) or "PRJ"
    자리 = {"android": "AND", "ios": "APP"}.get((platform or "").lower(), "WEB")
    쓰는키 = {r["human_key"] for r in conn.execute("SELECT human_key FROM screen")}
    for n in range(1, 1000):
        후보 = f"{바탕}-{자리}-{n:03d}"
        if 후보 not in 쓰는키:
            return 후보
    return ""


def 만들기(conn, project_uuid, 이름):
    """빈 검수 묶음 한 개. 돌려주는 값은 새 screen 의 uuid.

    이름이 비어 있거나 같은 과제에 같은 이름이 이미 있으면 ValueError 를 낸다.
    """
    이름 = (이름 or "").strip()
    if not 이름:
        raise ValueError("묶음 이름을 적어 주세요.")
    p = conn.execute("SELECT uuid, service_code FROM project WHERE uuid=?",
                     (project_uuid,)).fetchone()
    if not p:
        raise ValueError("없는 과제입니다.")
    if conn.execute("SELECT 1 FROM screen WHERE project_id=? AND name=?",
                    (project_uuid, 이름)).fetchone():
        raise ValueError(f"이미 있는 묶음 이름입니다: {이름}")

    본 = conn.execute(
        "SELECT platform, dev_keys, variants FROM screen WHERE project_id=? LIMIT 1",
        (project_uuid,)).fetchone()
    platform = (본["platform"] if 본 else None) or "web"
    키 = _번호붙은키(conn, project_uuid, p["service_code"], platform)
    if not 키:
        raise ValueError("화면 ID 를 지을 수 없습니다.")

    sid = uuidmod.uuid4().hex
    conn.execute(
        "INSERT INTO screen(uuid, project_id, human_key, name, platform, dev_keys, states, variants)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (sid, project_uuid, 키, 이름, platform,
         (본["dev_keys"] if 본 else None) or "[]",
         json.dumps([], ensure_ascii=False),
         (본["variants"] if 본 else None) or "[]"))
    conn.commit()
    return sid


def 페이지만들기(conn, screen_uuid, 이름, project_uuid=None):
    """촬영기를 거치지 않는 검수 페이지 한 장 — 시안·개발 그림은 사람이 직접 붙여 넣는다.

    자동 촬영이 안 되는 과제를 위한 길이다(river 확정 2026-10-30, C안).
    시안은 피그마 플러그인으로 보내거나(부품 정보까지 와서 지금 검수기 그대로) 그림만 붙여 넣는다
    (그림끼리 견주는 비교로 돈다). 개발 화면은 캡처를 붙여 넣는다.
    1차 차수(run)를 빈 채로 함께 세워 둔다 — 개발 그림을 붙일 자리다.
    돌려주는 값은 (화면 사람키, 새 페이지 uuid).
    """
    이름 = (이름 or "").strip()
    if not 이름:
        raise ValueError("페이지 이름을 적어 주세요.")
    s = conn.execute("SELECT uuid, human_key, project_id FROM screen WHERE uuid=?", (screen_uuid,)).fetchone()
    if not s or (project_uuid and s["project_id"] != project_uuid):
        raise ValueError("없는 검수 묶음입니다.")
    if conn.execute("SELECT 1 FROM inspection_page WHERE screen_id=? AND name=?",
                    (screen_uuid, 이름)).fetchone():
        raise ValueError(f"이미 있는 페이지 이름입니다: {이름}")
    seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 n FROM inspection_page WHERE screen_id=?",
                       (screen_uuid,)).fetchone()["n"]
    pid = uuidmod.uuid4().hex
    conn.execute("INSERT INTO inspection_page(uuid, screen_id, seq, name) VALUES (?,?,?,?)",
                 (pid, screen_uuid, seq, 이름))
    # 좌표 기준(coord_ref)은 비워 둔다 — 개발 그림이 붙을 때 그 그림 크기로 채운다(촬영기 접수와 같은 자).
    conn.execute("INSERT INTO inspection_run(uuid, screen_id, page_id, round, created_at) VALUES (?,?,?,?,?)",
                 (uuidmod.uuid4().hex, screen_uuid, pid, 1, datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    return (s["human_key"] or s["uuid"]), pid
