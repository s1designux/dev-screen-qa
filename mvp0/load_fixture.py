"""
과거 검수 1건(fixtures/cv-web-012.json)을 SQLite로 주입한다.

핵심: 2차 재검수는 '새 오류 행'을 만들지 않는다.
      dedup_key로 기존 오류를 찾아 상태만 갱신하고, 변화는 issue_history에 append한다.
      (CLAUDE.md 6번 dedup_key 규칙 / 2번-3 이력 삭제 금지)
"""
import json
import uuid
from pathlib import Path

import db as dbmod
from constants import STATUS_ALL

BASE = Path(__file__).resolve().parent
FIXTURE = BASE / "fixtures" / "cv-web-012.json"


def _uuid() -> str:
    return uuid.uuid4().hex


def load(fixture_path: Path = FIXTURE, db_path: Path = dbmod.DB_PATH) -> None:
    if db_path.exists():
        db_path.unlink()  # 데모 재현성: 매번 깨끗한 DB로 시작 (원본 이력 파괴 아님, 재생성)

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
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
        (screen_id, project_id, s["human_key"], s["name"], s["platform"],
         json.dumps(s["dev_keys"], ensure_ascii=False),
         json.dumps(s["states"], ensure_ascii=False),
         json.dumps(s["variants"], ensure_ascii=False)),
    )

    # element mappings
    for m in data["element_mappings"]:
        cur.execute(
            "INSERT INTO element_mapping(screen_uuid, design_node_id, dev_element_key) VALUES (?,?,?)",
            (screen_id, m["design_node_id"], m["dev_element_key"]),
        )

    # runs (round -> uuid 매핑 보관)
    run_id_by_round = {}
    for r in data["runs"]:
        run_id = _uuid()
        run_id_by_round[r["round"]] = run_id
        cur.execute(
            """INSERT INTO inspection_run(uuid, screen_id, round, inspector, created_at, pass_fail)
               VALUES (?,?,?,?,?,?)""",
            (run_id, screen_id, r["round"], r["inspector"], r["created_at"], r["pass_fail"]),
        )

    # issues (+ history). dedup_key로 UPSERT, 상태는 마지막 history의 to_status.
    for iss in data["issues"]:
        history = iss["history"]
        current_status = history[-1]["to_status"]
        assert current_status in STATUS_ALL, f"알 수 없는 상태: {current_status}"

        found_run_id = run_id_by_round.get(iss["found_round"])
        b = iss["box"]

        # dedup_key로 기존 오류 찾기 (있으면 상태만 갱신)
        row = cur.execute(
            "SELECT uuid FROM inspection_issue WHERE dedup_key = ?", (iss["dedup_key"],)
        ).fetchone()

        if row is None:
            issue_id = _uuid()
            cur.execute(
                """INSERT INTO inspection_issue(
                     uuid, screen_id, run_id, logical_element_key,
                     box_x, box_y, box_w, box_h,
                     category, expected, actual, description, severity,
                     status, found_round, resolved_round, dedup_key)
                   VALUES (?,?,?,?, ?,?,?,?, ?,?,?,?,?, ?,?,?,?)""",
                (issue_id, screen_id, found_run_id, iss["logical_element_key"],
                 b["x"], b["y"], b["w"], b["h"],
                 iss["category"], iss["expected"], iss["actual"],
                 iss["description"], iss["severity"],
                 current_status, iss["found_round"], iss.get("resolved_round"),
                 iss["dedup_key"]),
            )
        else:
            issue_id = row["uuid"]
            cur.execute(
                "UPDATE inspection_issue SET status=?, resolved_round=? WHERE uuid=?",
                (current_status, iss.get("resolved_round"), issue_id),
            )

        # history append (삭제/수정 없음)
        for seq, h in enumerate(history):
            cur.execute(
                """INSERT INTO issue_history(uuid, issue_id, from_status, to_status, actor, at, note, seq)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (_uuid(), issue_id, h["from_status"], h["to_status"],
                 h["actor"], h["at"], h["note"], seq),
            )

    conn.commit()
    conn.close()
    print(f"주입 완료 → {db_path}")


if __name__ == "__main__":
    load()
