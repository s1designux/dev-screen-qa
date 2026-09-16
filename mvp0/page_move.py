"""검수 페이지를 다른 화면으로 옮기기 (CLAUDE.md 21번 대기열 0-3).

화면은 스토리보드 ID 단위다. 어디서 끊을지는 사람이 안다 —
포털이 이름을 짐작해 미리 쪼개지 않고, 사람이 고른 페이지를
**새 화면으로 옮기거나 기존 화면에 합친다**(한 단추, 두 갈래).

지우는 것은 없다. `screen_id` 만 바뀌고 옮긴 사실은 `page_move_event` 에
한 줄씩 쌓인다(append-only). 후보·지적·이력·옛 회차는 page_id 로 매달려 있어
그대로 따라온다. 사람키는 라벨일 뿐이라 코드가 강제로 다시 붙이지 않는다(7번).
"""
import json
import re
import uuid as uuidmod
from datetime import datetime

EVENT_DDL = """
CREATE TABLE IF NOT EXISTS page_move_event (
  id TEXT PRIMARY KEY, page_id TEXT NOT NULL, from_screen TEXT NOT NULL,
  to_screen TEXT NOT NULL, actor TEXT, at TEXT NOT NULL, note TEXT
);
CREATE INDEX IF NOT EXISTS page_move_event_page ON page_move_event(page_id);
CREATE TRIGGER IF NOT EXISTS page_move_event_no_update BEFORE UPDATE ON page_move_event
  BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS page_move_event_no_delete BEFORE DELETE ON page_move_event
  BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


def 표만들기(c):
    c.executescript(EVENT_DDL)


def _있는표(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                     (name,)).fetchone() is not None


# ── 제안 ────────────────────────────────────────────────────────────
def 키제안(c, human_key):
    """같은 접두에서 비어 있는 다음 번호. `UVIS_USER_PC-WEB-001` → `UVIS_USER_PC-WEB-002`.

    번호가 없는 사람키(빈 값 포함)면 빈 문자열 — 사람이 직접 적는다."""
    m = re.match(r"^(.*?)(\d+)$", human_key or "")
    if not m:
        return ""
    접두, 폭 = m.group(1), len(m.group(2))
    쓰는키 = {r["human_key"] for r in c.execute("SELECT human_key FROM screen")}
    n = int(m.group(2))
    for _ in range(999):
        n += 1
        후보 = f"{접두}{n:0{폭}d}"
        if 후보 not in 쓰는키:
            return 후보
    return ""


# ── 옮기기 ──────────────────────────────────────────────────────────
def _옮긴페이지의요소(c, page_uuids):
    """옮기는 페이지의 시안에 들어 있는 요소 id 들. 시안이 안 붙은 페이지면 빈 집합."""
    if not (_있는표(c, "page_design_link") and _있는표(c, "design_elements")):
        return set()
    자리표 = ",".join("?" for _ in page_uuids)
    ids = set()
    for r in c.execute(
            f"SELECT e.elements FROM page_design_link l JOIN design_elements e ON e.design_id=l.design_id"
            f" WHERE l.page_id IN ({자리표})", page_uuids):
        try:
            for el in json.loads(r["elements"] or "[]"):
                if el.get("id"):
                    ids.add(str(el["id"]))
        except Exception:
            continue
    return ids


def _정책이어받기(c, from_screen, to_screen, actor, page_uuids, 새화면):
    """사람이 내린 제외·가변 판정이 화면을 옮겨도 잊히지 않게, 받는 화면에도 한 벌 더 쌓는다(append-only).

    요소 층은 **옮기는 페이지의 시안에 실제로 있는 요소**만 가져간다 — 남는 페이지 때문에 쌓인 규칙까지
    따라가면 받는 화면의 검수가 달라진다. 화면 층은 **새 화면일 때만** 물려준다(합치는 쪽은 자기 값이 있다).
    받는 쪽에 이미 값이 있으면 건드리지 않는다."""
    if not _있는표(c, "policy_rule"):
        return 0
    import policy
    pol = policy.Policy(None)
    옮긴수 = 0
    층 = ["element"] + (["screen"] if 새화면 else [])
    요소 = _옮긴페이지의요소(c, page_uuids) if "element" in 층 else set()
    for scope in 층:
        받는층 = pol.layer(c, scope, to_screen)
        for (rule, key), item in pol.layer(c, scope, from_screen).items():
            if (rule, key) in 받는층:
                continue
            if scope == "element" and key not in 요소:
                continue
            pol.set(c, scope, rule, item["value"], target=to_screen, key=key,
                    actor=actor, note="화면 나누기로 이어받음")
            옮긴수 += 1
    return 옮긴수


def 옮기기(conn, page_uuids, *, to_screen=None, new_key=None, new_name=None,
          actor="", note=""):
    """고른 페이지를 다른 화면으로 옮긴다.

    to_screen 이 있으면 그 화면에 합치고, 없으면 new_key·new_name 으로 새 화면을 만든다.
    돌려주는 값: {'screen': 받는화면uuid, 'human_key': …, 'name': …, 'moved': 옮긴장수}
    """
    page_uuids = [u for u in page_uuids if u]
    if not page_uuids:
        raise ValueError("옮길 검수 페이지를 먼저 고르세요.")
    새화면 = not to_screen
    표만들기(conn)

    자리표 = ",".join("?" for _ in page_uuids)
    pages = conn.execute(
        f"SELECT uuid, screen_id, seq, name FROM inspection_page WHERE uuid IN ({자리표}) ORDER BY seq, rowid",
        page_uuids).fetchall()
    if len(pages) != len(page_uuids):
        raise ValueError("없는 검수 페이지가 섞여 있습니다.")
    보낸화면 = {p["screen_id"] for p in pages}
    if len(보낸화면) != 1:
        raise ValueError("한 화면 안의 페이지만 함께 옮길 수 있습니다.")
    from_screen = pages[0]["screen_id"]
    src = conn.execute("SELECT * FROM screen WHERE uuid=?", (from_screen,)).fetchone()

    if to_screen:
        dst = conn.execute("SELECT * FROM screen WHERE uuid=? OR human_key=?",
                           (to_screen, to_screen)).fetchone()
        if dst is None:
            raise ValueError("옮길 화면을 찾지 못했습니다.")
        if dst["uuid"] == from_screen:
            raise ValueError("지금 있는 화면입니다. 다른 화면을 고르세요.")
        if dst["project_id"] != src["project_id"]:
            raise ValueError("다른 과제(프로젝트)의 화면으로는 옮길 수 없습니다.")
        to_screen = dst["uuid"]
    else:
        새키 = (new_key or "").strip()
        새이름 = (new_name or "").strip()
        if not 새키:
            raise ValueError("새 화면의 화면 ID를 적어 주세요.")
        if not 새이름:
            raise ValueError("새 화면의 이름을 적어 주세요.")
        if conn.execute("SELECT 1 FROM screen WHERE human_key=?", (새키,)).fetchone():
            raise ValueError(f"이미 쓰고 있는 화면 ID 입니다: {새키}")
        to_screen = uuidmod.uuid4().hex
        conn.execute(
            "INSERT INTO screen(uuid, project_id, human_key, name, platform, dev_keys, states, variants)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (to_screen, src["project_id"], 새키, 새이름, src["platform"],
             src["dev_keys"] or "[]", json.dumps([], ensure_ascii=False),
             src["variants"] or "[]"))
        dst = conn.execute("SELECT * FROM screen WHERE uuid=?", (to_screen,)).fetchone()

    다음순서 = (conn.execute("SELECT COALESCE(MAX(seq),0) n FROM inspection_page WHERE screen_id=?",
                          (to_screen,)).fetchone()["n"] or 0)
    때 = _now()
    for p in pages:
        다음순서 += 1
        conn.execute("UPDATE inspection_page SET screen_id=?, seq=? WHERE uuid=?",
                     (to_screen, 다음순서, p["uuid"]))
        conn.execute("UPDATE inspection_run SET screen_id=? WHERE page_id=?", (to_screen, p["uuid"]))
        conn.execute("UPDATE inspection_issue SET screen_id=? WHERE page_id=?", (to_screen, p["uuid"]))
        # rule_verdict 는 손대지 않는다 — 거기 적힌 화면은 '판정하던 그때의 사실'이고 append-only 다.
        # 규칙 성적표는 page_id 로 지금 화면을 되짚는다(rule_log._SCREEN_COND).
        # design_version · element_mapping · design_plan 도 그대로 둔다 — 페이지가 아니라 화면에 매달린 것들이다.
        conn.execute(
            "INSERT INTO page_move_event(id, page_id, from_screen, to_screen, actor, at, note)"
            " VALUES (?,?,?,?,?,?,?)",
            (uuidmod.uuid4().hex, p["uuid"], from_screen, to_screen, actor, 때, note))
    _정책이어받기(conn, from_screen, to_screen, actor, [p["uuid"] for p in pages], 새화면)
    conn.commit()
    return {"screen": to_screen, "human_key": dst["human_key"], "name": dst["name"],
            "moved": len(pages), "from_key": src["human_key"], "from_screen": from_screen}


# ── 화면(포털) ──────────────────────────────────────────────────────
CSS = """
  #page-move-dlg { width:min(560px, 92vw); }
  #page-move-dlg h2 { font-size:var(--font-size-16); margin:0 0 var(--spacing-8); }
  #page-move-dlg .picked { font-size:var(--font-size-12); color:var(--color-text-caption);
    background:var(--color-bg-subtle); border-radius:var(--radius-8);
    padding:var(--spacing-10) var(--spacing-12); margin-bottom:var(--spacing-14);
    max-height:120px; overflow:auto; }
  #page-move-dlg label.opt { display:flex; align-items:center; gap:var(--spacing-8);
    margin:var(--spacing-8) 0; font-size:var(--font-size-14); }
  #page-move-dlg fieldset { border:0; padding:0 0 0 var(--spacing-24); margin:0 0 var(--spacing-8); }
  #page-move-dlg .fld { display:block; margin:var(--spacing-8) 0 var(--spacing-4);
    font-size:var(--font-size-12); color:var(--color-text-caption); }
  #page-move-dlg input:not([type=radio]):not([type=checkbox]),
  #page-move-dlg select { width:100%; }
  #page-move-dlg .foot { display:flex; justify-content:flex-end; gap:var(--spacing-8);
    margin-top:var(--spacing-16); }
  #page-move-dlg .why { font-size:var(--font-size-12); color:var(--color-text-helper);
    margin-top:var(--spacing-12); }
"""


def 막대():
    """'삭제' 와 한 줄에 나란히 서는 '옮기기' 단추. 고른 것은 '삭제'와 같은 체크박스를 읽는다(JS)."""
    return '<button type="button" id="page-move-open">페이지 옮기기</button>'



def 창(human_key_esc, 키제안값, 다른화면들, 담당자들, esc):
    """옮길 곳을 고르는 창. 페이지 목록과 **화면 이름 제안(공통 뿌리)** 은 고른 것에 맞춰 열 때 JS 가 채운다."""
    옵션 = "".join(f'<option value="{esc(s["uuid"])}">{esc(s["human_key"] or "ID 없음")} · {esc(s["name"] or "")}</option>'
                  for s in 다른화면들)
    사람 = "".join(f'<option value="{esc(p["name"])}">{esc(p["name"])}</option>' for p in 담당자들)
    합치기막음 = "" if 다른화면들 else " disabled"
    return f"""
<dialog id="page-move-dlg"><div class="s1-modal-inset">
  <h2>고른 검수 페이지 옮기기</h2>
  <div class="picked" id="page-move-picked"></div>
  <form method="post" action="/screen/{human_key_esc}/pages/move" id="page-move-form">
    <div id="page-move-ids"></div>
    <label class="opt"><input type="radio" name="dest" value="new" checked> 새 화면으로 옮기기</label>
    <fieldset id="page-move-new">
      <label class="fld" for="pm-key">새 화면 ID (스토리보드 ID)</label>
      <input id="pm-key" name="new_key" value="{esc(키제안값)}" autocomplete="off">
      <label class="fld" for="pm-name">새 화면 이름</label>
      <input id="pm-name" name="new_name" autocomplete="off">
    </fieldset>
    <label class="opt"><input type="radio" name="dest" value="exist"{합치기막음}> 이미 있는 화면에 합치기</label>
    <fieldset id="page-move-exist">
      <select name="to_screen">{옵션}</select>
    </fieldset>
    <label class="fld" for="pm-actor">누가</label>
    <select id="pm-actor" name="actor"><option value="">(고르지 않음)</option>{사람}</select>
    <label class="fld" for="pm-note">왜 (선택)</label>
    <input id="pm-note" name="note" autocomplete="off" placeholder="예: 홈 화면은 로그인과 다른 스토리보드">
    <p class="why">수정필요·후보·차수 기록은 그대로 따라갑니다.</p>
    <div class="foot">
      <button type="button" id="page-move-cancel">취소</button>
      <button type="submit" class="primary">옮기기</button>
    </div>
  </form>
</div></dialog>"""


JS = """
(function () {
  var 창 = document.getElementById('page-move-dlg');
  var 열기 = document.getElementById('page-move-open');
  if (!창 || !열기) return;
  var 매체말 = ['웹','앱','모바일웹','모바일','PC','AND','APP','IOS','WEB'];
  function 고른것() {
    return Array.prototype.slice.call(document.querySelectorAll('input[name=page]:checked'));
  }
  function 이름제안(이름들) {
    var 쪼갠것 = 이름들.map(function (n) { return n.split('_'); });
    if (!쪼갠것.length) return '';
    var 최소 = Math.min.apply(null, 쪼갠것.map(function (x) { return x.length; }));
    var 공통 = [];
    for (var i = 0; i < 최소; i++) {
      var 토막 = 쪼갠것[0][i];
      if (쪼갠것.every(function (x) { return x[i] === 토막; })) 공통.push(토막); else break;
    }
    while (공통.length && 매체말.indexOf(공통[0].trim()) >= 0) 공통.shift();
    if (!공통.length) return 이름들[0];
    return 공통.map(function (t) { return t.trim(); }).filter(Boolean).join(' ');
  }
  function 갈래맞추기() {
    var 새로 = 창.querySelector('input[name=dest][value=new]').checked;
    창.querySelector('#page-move-new').hidden = !새로;
    창.querySelector('#page-move-exist').hidden = 새로;
    창.querySelector('#pm-key').required = 새로;
    창.querySelector('#pm-name').required = 새로;
  }
  열기.addEventListener('click', function () {
    var 고름 = 고른것();
    if (!고름.length) { alert('옮길 검수 페이지를 먼저 고르세요.'); return; }
    var 이름들 = 고름.map(function (c) {
      var 칸 = c.closest('tr').querySelector('td.name');
      return 칸 ? 칸.textContent.replace('더미', '').trim() : '';
    });
    창.querySelector('#page-move-picked').textContent = '옮길 ' + 고름.length + '장 · ' + 이름들.join(' / ');
    창.querySelector('#page-move-ids').innerHTML = 고름.map(function (c) {
      return '<input type="hidden" name="page" value="' + c.value + '">';
    }).join('');
    var 이름칸 = 창.querySelector('#pm-name');
    if (!이름칸.value || 이름칸.dataset.auto === '1') { 이름칸.value = 이름제안(이름들); 이름칸.dataset.auto = '1'; }
    갈래맞추기();
    창.showModal();
  });
  창.querySelector('#pm-name').addEventListener('input', function () { this.dataset.auto = '0'; });
  Array.prototype.forEach.call(창.querySelectorAll('input[name=dest]'), function (r) {
    r.addEventListener('change', 갈래맞추기);
  });
  창.querySelector('#page-move-cancel').addEventListener('click', function () { 창.close(); });
})();
"""
