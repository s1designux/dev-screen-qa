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


def list_screens(conn, unresolved_only=False, round_filter=None):
    """포털 화면 목록용. 화면마다 프로젝트(메뉴)·스토리보드ID·Pass/Fail·미해결 건수.

    unresolved_only: 미해결이 1건 이상인 화면만.
    round_filter: 해당 차수가 있는 화면만, 카운트/Pass·Fail도 그 차수 기준.
    미해결 판정은 constants.UNRESOLVED_STATUSES 그대로 참조.
    """
    ph = ",".join("?" for _ in UNRESOLVED_STATUSES)
    screens = conn.execute(
        """SELECT s.uuid, s.human_key, s.name, s.platform, p.name AS project_name
           FROM screen s JOIN project p ON p.uuid = s.project_id
           ORDER BY p.name, s.human_key"""
    ).fetchall()

    out = []
    for s in screens:
        runs = conn.execute(
            "SELECT round, pass_fail FROM inspection_run WHERE screen_id=? ORDER BY round",
            (s["uuid"],),
        ).fetchall()
        rounds = [r["round"] for r in runs]

        if round_filter is not None and round_filter not in rounds:
            continue  # 이 차수가 없는 화면은 제외

        if round_filter is not None:
            pass_fail = next((r["pass_fail"] for r in runs if r["round"] == round_filter), None)
        else:
            pass_fail = runs[-1]["pass_fail"] if runs else None

        params = [s["uuid"], *UNRESOLVED_STATUSES]
        q_un = f"SELECT COUNT(*) c FROM inspection_issue WHERE screen_id=? AND status IN ({ph})"
        q_all = "SELECT COUNT(*) c FROM inspection_issue WHERE screen_id=?"
        p_all = [s["uuid"]]
        if round_filter is not None:
            q_un += " AND found_round=?"
            q_all += " AND found_round=?"
            params.append(round_filter)
            p_all.append(round_filter)
        unresolved = conn.execute(q_un, params).fetchone()["c"]
        total = conn.execute(q_all, p_all).fetchone()["c"]

        if unresolved_only and unresolved == 0:
            continue

        out.append({
            "human_key": s["human_key"],
            "name": s["name"],
            "platform": s["platform"],
            "project_name": s["project_name"],
            "pass_fail": pass_fail,
            "rounds": rounds,
            "unresolved": unresolved,
            "total": total,
        })
    return out


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
