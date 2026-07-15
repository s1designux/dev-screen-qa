"""
과거/실제 검수 픽스처(fixtures/*.json)를 SQLite로 주입한다.

두 가지 픽스처 모양을 모두 받는다:
  - 합성본(cv-web-012): runs[] + element_mappings[] + issues[].history[]
  - 실제본(tb-web-001): inspection_run(단일) + design_version + issues[].properties[] + pages

검수 페이지(중간층): 화면 > 검수 페이지 > 이슈.
  - 픽스처에 pages.primary가 있으면 그 이름으로, 없으면 화면명으로 기본 페이지 1개를 만들고
    그 화면의 run과 이슈 전부를 거기 매단다. (기존 이슈는 손대지 않고 page_id만 채움)
  - pages.extra[]는 검증용 더미 페이지 — 실제 이슈와 완전히 분리해서 만든다.

핵심: 재검수(2차)는 '새 오류 행'을 만들지 않는다. dedup_key로 기존 오류를 찾아 상태만 갱신하고,
      변화는 issue_history에 append한다. (CLAUDE.md 6번 / 2번-3 이력 삭제 금지)
"""
import json
import sys
import uuid
from pathlib import Path

import db as dbmod
from constants import STATUS_ALL

BASE = Path(__file__).resolve().parent
DEFAULT_FIXTURE = BASE / "fixtures" / "cv-web-012.json"


def _uuid() -> str:
    return uuid.uuid4().hex


def load(fixture_path: Path = DEFAULT_FIXTURE, db_path: Path = dbmod.DB_PATH) -> None:
    if db_path.exists():
        db_path.unlink()  # 데모 재현성: 매번 깨끗한 DB로 시작 (원본 파괴 아님, 재생성)

    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    conn = dbmod.connect(db_path)
    dbmod.init_schema(conn)
    cur = conn.cursor()

    # project
    project_id = _uuid()
    cur.execute("INSERT INTO project(uuid, name) VALUES (?,?)",
                (project_id, data["project"]["name"]))

    # screen
    s = data["screen"]
    screen_id = _uuid()
    cur.execute(
        """INSERT INTO screen(uuid, project_id, human_key, name, platform, dev_keys, states, variants)
           VALUES (?,?,?,?,?,?,?,?)""",
        (screen_id, project_id, s["human_key"], s.get("name"), s.get("platform"),
         json.dumps(s.get("dev_keys", []), ensure_ascii=False),
         json.dumps(s.get("states", []), ensure_ascii=False),
         json.dumps(s.get("variants", []), ensure_ascii=False)),
    )

    # design_version 스텁 — figma 참조 3개 값만 담는다 (있을 때만)
    dv = data.get("design_version")
    if dv:
        cur.execute(
            """INSERT INTO design_version(uuid, screen_id, file_key, node_id, dev_capture_node_id)
               VALUES (?,?,?,?,?)""",
            (_uuid(), screen_id, dv.get("file_key"), dv.get("node_id"),
             dv.get("dev_capture_node_id")),
        )

    # 검수 페이지(중간층) — primary 1개. 실제 run/이슈가 여기 매달린다.
    pages_spec = data.get("pages", {})
    primary_spec = pages_spec.get("primary", {})
    primary_page_id = _uuid()
    cur.execute(
        "INSERT INTO inspection_page(uuid, screen_id, seq, name, note) VALUES (?,?,?,?,?)",
        (primary_page_id, screen_id, primary_spec.get("seq", 1),
         primary_spec.get("name") or s.get("name") or "기본 페이지", None),
    )

    # element mappings (없으면 건너뜀)
    for m in data.get("element_mappings", []):
        cur.execute(
            "INSERT INTO element_mapping(screen_uuid, design_node_id, dev_element_key) VALUES (?,?,?)",
            (screen_id, m["design_node_id"], m["dev_element_key"]),
        )

    # runs 정규화: runs[] 또는 inspection_run(단일) 둘 다 허용. 전부 primary 페이지에 매단다.
    runs = data.get("runs")
    if runs is None and "inspection_run" in data:
        runs = [data["inspection_run"]]
    runs = runs or []

    run_id_by_round = {}
    default_inspector = runs[0].get("inspector") if runs else None
    default_at = runs[0].get("created_at") if runs else None
    for r in runs:
        run_id = _uuid()
        run_id_by_round[r["round"]] = run_id
        cur.execute(
            """INSERT INTO inspection_run(uuid, screen_id, page_id, round, inspector, created_at, pass_fail)
               VALUES (?,?,?,?,?,?,?)""",
            (run_id, screen_id, primary_page_id, r["round"], r.get("inspector"),
             r.get("created_at"), r.get("pass_fail")),
        )

    # issues (+ history). dedup_key로 UPSERT, 상태는 마지막 history의 to_status. 전부 primary 페이지.
    for iss in data["issues"]:
        history = iss.get("history")
        if not history:
            history = [{
                "from_status": None, "to_status": iss["status"],
                "actor": default_inspector, "at": default_at,
                "note": "1차 검수에서 발견",
            }]
        current_status = history[-1]["to_status"]
        assert current_status in STATUS_ALL, f"알 수 없는 상태: {current_status}"

        found_run_id = run_id_by_round.get(iss.get("found_round"))
        b = iss.get("box") or {}
        properties = iss.get("properties")
        props_json = json.dumps(properties, ensure_ascii=False) if properties else None
        logical_key = iss.get("logical_element_key") or iss.get("element")

        row = cur.execute(
            "SELECT uuid FROM inspection_issue WHERE dedup_key = ?", (iss["dedup_key"],)
        ).fetchone()

        if row is None:
            issue_id = _uuid()
            cur.execute(
                """INSERT INTO inspection_issue(
                     uuid, screen_id, page_id, run_id, logical_element_key,
                     box_x, box_y, box_w, box_h,
                     category, expected, actual, description, severity,
                     status, found_round, resolved_round, dedup_key, properties)
                   VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?,?,?)""",
                (issue_id, screen_id, primary_page_id, found_run_id, logical_key,
                 b.get("x"), b.get("y"), b.get("w"), b.get("h"),
                 iss.get("category"), iss.get("expected"), iss.get("actual"),
                 iss.get("description"), iss.get("severity"),
                 current_status, iss.get("found_round"), iss.get("resolved_round"),
                 iss["dedup_key"], props_json),
            )
        else:
            issue_id = row["uuid"]
            cur.execute(
                "UPDATE inspection_issue SET status=?, resolved_round=? WHERE uuid=?",
                (current_status, iss.get("resolved_round"), issue_id),
            )

        for seq, h in enumerate(history):
            cur.execute(
                """INSERT INTO issue_history(uuid, issue_id, from_status, to_status, actor, at, note, seq)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (_uuid(), issue_id, h["from_status"], h["to_status"],
                 h.get("actor"), h.get("at"), h.get("note"), seq),
            )

    # 검증용 더미 페이지(extra) — 실제 이슈와 완전히 분리해서 별도 페이지/ run/ 이슈로 만든다.
    dummy_pages = dummy_issues = 0
    for ep in pages_spec.get("extra", []):
        page_id = _uuid()
        dummy_pages += 1
        cur.execute(
            "INSERT INTO inspection_page(uuid, screen_id, seq, name, note) VALUES (?,?,?,?,?)",
            (page_id, screen_id, ep.get("seq"), ep.get("name"), "[더미] 검증용"),
        )
        dummy_run_id = _uuid()
        rnd = ep.get("round", 1)
        cur.execute(
            """INSERT INTO inspection_run(uuid, screen_id, page_id, round, inspector, created_at, pass_fail)
               VALUES (?,?,?,?,?,?,?)""",
            (dummy_run_id, screen_id, page_id, rnd, "[더미]", None, ep.get("pass_fail")),
        )
        for di in ep.get("dummy_issues", []):
            issue_id = _uuid()
            dummy_issues += 1
            db_box = di.get("box") or {}
            props = di.get("properties")
            cur.execute(
                """INSERT INTO inspection_issue(
                     uuid, screen_id, page_id, run_id, logical_element_key,
                     box_x, box_y, box_w, box_h,
                     category, expected, actual, description, severity,
                     status, found_round, resolved_round, dedup_key, properties)
                   VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?,?,?)""",
                (issue_id, screen_id, page_id, dummy_run_id, di.get("element"),
                 db_box.get("x"), db_box.get("y"), db_box.get("w"), db_box.get("h"),
                 di.get("category"), None, None, di.get("description"), di.get("severity"),
                 di.get("status", "발견"), rnd, None, di["dedup_key"],
                 json.dumps(props, ensure_ascii=False) if props else None),
            )
            cur.execute(
                """INSERT INTO issue_history(uuid, issue_id, from_status, to_status, actor, at, note, seq)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (_uuid(), issue_id, None, di.get("status", "발견"), "[더미]", None, "더미 발견", 0),
            )

    # 담당자 명단 시드 (예시 이름 2명 — 포털 관리 화면에서 이름 수정·비활성 가능).
    seed_people = [
        ("배수현", "디자인팀(검수)"),
        ("김도현", "개발팀"),
    ]
    for name, aff in seed_people:
        cur.execute("INSERT INTO person(uuid, name, affiliation, active) VALUES (?,?,?,1)",
                    (_uuid(), name, aff))

    conn.commit()
    conn.close()
    print(f"주입 완료 → {db_path}  (픽스처: {Path(fixture_path).name}, "
          f"더미 페이지 {dummy_pages}·더미 이슈 {dummy_issues}, 담당자 {len(seed_people)}명)")


if __name__ == "__main__":
    fx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    dbp = Path(sys.argv[2]) if len(sys.argv) > 2 else dbmod.DB_PATH
    load(fx, dbp)
