"""DB 열기/초기화 최소 헬퍼."""
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "mvp0.db"
SCHEMA_PATH = BASE / "schema.sql"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    # 여럿이 한 자료함을 함께 쓴다(공용 PC 서버). 쓰는 사람이 있어도 읽기는 막히지 않고,
    # 두 사람이 같은 순간에 쓰면 뒤 사람이 잠깐 기다렸다 쓴다 — 바로 실패하지 않게.
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
