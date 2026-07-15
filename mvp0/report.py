"""
DoD④ — DB 데이터로 '가로 A4' 검수결과서(HTML)를 재생성한다.
DoD② — 해결된 오류(검수완료/오류아님)는 기본 '숨김'. 단 데이터는 그대로 두고 화면에서만 감춘다.

원본은 DB. 이 HTML은 특정 시점 스냅샷(렌더링 출력물)일 뿐이다 (CLAUDE.md 2번-1).
"""
import json
import html
from pathlib import Path

import db as dbmod
from constants import UNRESOLVED_STATUSES, CLOSED_STATUSES

BASE = Path(__file__).resolve().parent
OUT = BASE / "report.html"


def _esc(v):
    return html.escape(str(v)) if v is not None else ""


def build(db_path=dbmod.DB_PATH, out_path: Path = OUT, show_resolved: bool = False) -> Path:
    conn = dbmod.connect(db_path)
    screen = conn.execute("SELECT * FROM screen LIMIT 1").fetchone()
    project = conn.execute("SELECT * FROM project LIMIT 1").fetchone()
    issues = conn.execute(
        "SELECT * FROM inspection_issue ORDER BY severity DESC, dedup_key"
    ).fetchall()
    conn.close()

    unresolved = [i for i in issues if i["status"] in UNRESOLVED_STATUSES]
    resolved = [i for i in issues if i["status"] in CLOSED_STATUSES]

    def row(iss):
        return f"""<tr class="sev-{_esc(iss['severity'])}">
          <td class="st">{_esc(iss['status'])}</td>
          <td>{_esc(iss['description'])}<br><span class="key">{_esc(iss['logical_element_key'])}</span></td>
          <td>{_esc(iss['category'])}</td>
          <td class="exp">{_esc(iss['expected'])}</td>
          <td class="act">{_esc(iss['actual'])}</td>
          <td class="ctr">{_esc(iss['severity'])}</td>
          <td class="ctr">{_esc(iss['found_round'])}차</td>
          <td class="ctr">{('—' if iss['resolved_round'] is None else str(iss['resolved_round'])+'차')}</td>
        </tr>"""

    dev_keys = ", ".join(json.loads(screen["dev_keys"] or "[]"))
    variants = ", ".join(json.loads(screen["variants"] or "[]"))

    unresolved_rows = "\n".join(row(i) for i in unresolved) or \
        '<tr><td colspan="8" class="ctr">미해결 오류 없음</td></tr>'
    resolved_block = ""
    if show_resolved:
        resolved_rows = "\n".join(row(i) for i in resolved) or \
            '<tr><td colspan="8" class="ctr">없음</td></tr>'
        resolved_block = f"""
        <h2>해결·종결 오류 <span class="muted">({len(resolved)}건)</span></h2>
        <table><thead>{_thead()}</thead><tbody>{resolved_rows}</tbody></table>"""
    else:
        resolved_block = f"""
        <p class="hidden-note">🔒 해결·종결 오류 <b>{len(resolved)}건</b>은 화면에서 숨김
        (데이터는 DB에 그대로 보존 — show_resolved=True로 다시 표시 가능)</p>"""

    doc = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<title>검수결과서 {_esc(screen['human_key'])}</title>
<style>
  @page {{ size: A4 landscape; margin: 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Apple SD Gothic Neo", sans-serif; color:#1a1a1a; margin:0; padding:10mm; }}
  .sheet {{ width: 277mm; }}
  header {{ display:flex; justify-content:space-between; align-items:flex-end; border-bottom:2px solid #1a1a1a; padding-bottom:8px; }}
  h1 {{ font-size:20px; margin:0; }}
  .meta {{ font-size:12px; color:#555; text-align:right; }}
  .summary {{ display:flex; gap:10px; margin:12px 0; }}
  .chip {{ border:1px solid #ddd; border-radius:8px; padding:8px 14px; font-size:13px; }}
  .chip b {{ font-size:20px; display:block; }}
  .chip.open b {{ color:#d92d20; }}
  .chip.done b {{ color:#12864e; }}
  h2 {{ font-size:14px; margin:16px 0 6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:11px; }}
  th, td {{ border:1px solid #ddd; padding:5px 7px; vertical-align:top; text-align:left; }}
  th {{ background:#f4f4f5; font-size:11px; }}
  .ctr {{ text-align:center; white-space:nowrap; }}
  .st {{ font-weight:700; white-space:nowrap; }}
  .key {{ color:#888; font-size:10px; }}
  .exp {{ color:#12864e; }} .act {{ color:#d92d20; }}
  tr.sev-critical .st {{ color:#b42318; }}
  .hidden-note {{ background:#fafafa; border:1px dashed #ccc; border-radius:8px; padding:10px; font-size:12px; color:#555; }}
  .muted {{ color:#888; font-weight:400; }}
  footer {{ margin-top:14px; font-size:10px; color:#999; border-top:1px solid #eee; padding-top:6px; }}
</style></head>
<body><div class="sheet">
  <header>
    <div>
      <h1>검수결과서 — {_esc(screen['name'])}</h1>
      <div style="font-size:12px;color:#555;margin-top:4px;">
        {_esc(project['name'])} · 화면키 <b>{_esc(screen['human_key'])}</b> · {_esc(screen['platform'])} · {_esc(variants)}
      </div>
    </div>
    <div class="meta">개발 실행키: {_esc(dev_keys)}<br>원본: SQLite (이 문서는 렌더링 스냅샷)</div>
  </header>

  <div class="summary">
    <div class="chip"><b>{len(issues)}</b>전체 오류</div>
    <div class="chip open"><b>{len(unresolved)}</b>미해결</div>
    <div class="chip done"><b>{len(resolved)}</b>해결·종결</div>
  </div>

  <h2>미해결 오류 <span class="muted">({len(unresolved)}건 — 조치 필요)</span></h2>
  <table><thead>{_thead()}</thead><tbody>
    {unresolved_rows}
  </tbody></table>
  {resolved_block}

  <footer>미해결 정의 = {" / ".join(UNRESOLVED_STATUSES)} · 이력은 삭제 없이 보존(append-only)</footer>
</div></body></html>"""

    out_path.write_text(doc, encoding="utf-8")
    print(f"결과서 생성 완료 → {out_path}  (미해결 {len(unresolved)} / 숨김 {len(resolved)})")
    return out_path


def _thead():
    return ("<tr><th>상태</th><th>내용 / 요소</th><th>구분</th><th>기대값</th>"
            "<th>실제값</th><th>심각도</th><th>발견</th><th>해결</th></tr>")


if __name__ == "__main__":
    build()
