"""조회 함수. DoD①②③을 실제 출력으로 보여주는 데 쓰인다."""
import db as dbmod
from constants import UNRESOLVED_STATUSES


def all_issues(conn):
    return conn.execute(
        "SELECT * FROM inspection_issue ORDER BY found_round, dedup_key"
    ).fetchall()


def issue_history(conn, issue_uuid):
    return conn.execute(
        "SELECT * FROM issue_history WHERE issue_id=? ORDER BY seq", (issue_uuid,)
    ).fetchall()


def unresolved_issues(conn):
    """DoD③ — '현재 미해결 오류만'. 정의는 constants.UNRESOLVED_STATUSES 참조."""
    placeholders = ",".join("?" for _ in UNRESOLVED_STATUSES)
    return conn.execute(
        f"SELECT * FROM inspection_issue WHERE status IN ({placeholders}) "
        f"ORDER BY severity DESC, dedup_key",
        UNRESOLVED_STATUSES,
    ).fetchall()


def _print_issue_line(iss):
    print(f"  [{iss['status']:<7}] {iss['description']} "
          f"(dedup={iss['dedup_key']}, found_r={iss['found_round']}, "
          f"resolved_r={iss['resolved_round']})")


if __name__ == "__main__":
    conn = dbmod.connect()

    print("=" * 78)
    print("DoD① — dedup_key로 1·2차 연결 (오류 행은 4개, 각 오류의 이력이 회차를 가로지름)")
    print("=" * 78)
    issues = all_issues(conn)
    print(f"총 오류 행 수: {len(issues)}개 (2차에서 새 행을 만들지 않음)\n")
    for iss in issues:
        _print_issue_line(iss)
        for h in issue_history(conn, iss["uuid"]):
            arrow = f"{h['from_status'] or '(신규)'} → {h['to_status']}"
            print(f"        · {h['at'][:10]} {arrow:<20} by {h['actor']}  ({h['note']})")
        print()

    print("=" * 78)
    print("DoD③ — 현재 미해결 오류만 (정의: constants.UNRESOLVED_STATUSES)")
    print(f"미해결 집합 = {UNRESOLVED_STATUSES}")
    print("=" * 78)
    for iss in unresolved_issues(conn):
        _print_issue_line(iss)

    conn.close()
