"""JSON 내보내기 — SQLite 원본을 사람이 읽는 JSON으로 덤프.

원본은 어디까지나 DB. 이건 river님이 눈으로 확인하기 위한 '읽기용' 출력물.
"""
import json
from pathlib import Path

import db as dbmod

BASE = Path(__file__).resolve().parent
OUT = BASE / "export.json"

TABLES = [
    "project", "screen", "element_mapping", "inspection_run",
    "inspection_issue", "issue_history", "comparison_policy",
]


def export(db_path=dbmod.DB_PATH, out_path: Path = OUT) -> Path:
    conn = dbmod.connect(db_path)
    dump = {}
    for t in TABLES:
        rows = conn.execute(f"SELECT * FROM {t}").fetchall()
        dump[t] = [dict(r) for r in rows]
    conn.close()
    out_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"내보내기 완료 → {out_path}")
    return out_path


if __name__ == "__main__":
    export()
