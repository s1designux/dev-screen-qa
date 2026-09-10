"""포털 자동 검수(후보 찾기) — 페이지 상세를 열면 저장된 후보가 바로 보이게 한다.

원칙(CLAUDE.md 2번): 자동 검수는 '후보'만 만든다. 확정(지적 등록)은 사람이 누른다.
엔진은 plugin-image-qa/ui.html 한 벌을 그대로 쓴다(복사하지 않는다). 포털은 그 파일을
/engine/ui.html 로 내보내며 맨 끝 시작 줄만 포털용 손잡이(harness)로 바꿔 끼운다.

흐름: 페이지 상세 열림 → (그 차수에 결과가 없으면) 브라우저가 숨은 iframe에서 엔진을 돌려
결과를 POST → 저장 → 다시 열면 저장본이 바로 표시. 후보·판정·등록 이력은 지우지 않는다.
"""
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import figma_elements
import figma_reader
import issue_categories

PLUGIN_UI = Path(__file__).resolve().parents[1] / 'plugin-image-qa' / 'ui.html'
ENGINE_MARKER = 'if(location.search.indexOf("selftest=1")>=0)runSelfTest();else post({type:"request-selection-status"});'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS design_elements (
 design_id TEXT PRIMARY KEY REFERENCES intake_design(id), fetched_at TEXT NOT NULL, source_version TEXT,
 frame TEXT NOT NULL, elements TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auto_run (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES inspection_page(uuid), run_id TEXT NOT NULL REFERENCES inspection_run(uuid),
 status TEXT NOT NULL CHECK(status IN ('pending','done','failed')), engine TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, finished_at TEXT, error TEXT NOT NULL DEFAULT '',
 alignment TEXT NOT NULL DEFAULT '', range TEXT NOT NULL DEFAULT '', notices TEXT NOT NULL DEFAULT '[]',
 capture_w INTEGER, capture_h INTEGER, design_id TEXT NOT NULL DEFAULT '', UNIQUE(run_id, design_id)
);
CREATE TABLE IF NOT EXISTS auto_candidate (
 id TEXT PRIMARY KEY, auto_run_id TEXT NOT NULL REFERENCES auto_run(id), no INTEGER NOT NULL,
 kind TEXT NOT NULL, label TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', confidence INTEGER,
 status TEXT NOT NULL CHECK(status IN ('open','excluded','variable')), engine_status TEXT NOT NULL,
 policy TEXT NOT NULL DEFAULT '', box_x REAL, box_y REAL, box_w REAL, box_h REAL,
 design_box TEXT NOT NULL DEFAULT '', design_node_ids TEXT NOT NULL DEFAULT '[]', design_values TEXT NOT NULL DEFAULT '',
 issue_id TEXT REFERENCES inspection_issue(uuid)
);
CREATE TABLE IF NOT EXISTS auto_candidate_event (
 id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES auto_candidate(id),
 from_status TEXT NOT NULL, to_status TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS auto_candidate_event_no_update BEFORE UPDATE ON auto_candidate_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS auto_candidate_event_no_delete BEFORE DELETE ON auto_candidate_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''

STATUS_LABEL = {'open': '후보', 'excluded': '제외(오류 아님)', 'variable': '가변 글자·요소'}
ENGINE_STATUS = {'confirmed': 'open', 'excluded': 'excluded', 'variable': 'variable'}
# 후보 종류 → 포털 이슈 분류(issue_categories.ALIASES 키)
KIND_CATEGORY = {'text': 'text', 'fixed': 'text', 'variable': 'text', 'missing': 'missing', 'area': 'mixed',
                 'position': 'position', 'icon': 'icon', 'image': 'image', 'shape': 'appearance', 'spacing': 'spacing'}


def uid():
    return uuid.uuid4().hex


def migrate(c):
    """auto_run이 시안별(run_id+design_id)이 되기 전 표를 만난 경우 — 행은 남기고 모양만 바꾼다.
    이름을 바꿀 때 다른 표의 참조가 따라 바뀌지 않게(legacy_alter_table) 한다. 참조가 이미 틀어진 표는 다시 세운다."""
    cols = [r[1] for r in c.execute('PRAGMA table_info(auto_run)')]
    if cols and 'design_id' not in cols:
        c.execute('PRAGMA legacy_alter_table=ON')
        c.execute('ALTER TABLE auto_run RENAME TO auto_run_v0')
        c.executescript(SCHEMA)
        c.execute("""INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,finished_at,error,alignment,range,notices,capture_w,capture_h,design_id)
                     SELECT id,page_id,run_id,status,engine,created_at,finished_at,error,alignment,range,notices,capture_w,capture_h,'' FROM auto_run_v0""")
        c.execute('PRAGMA legacy_alter_table=OFF')
    sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='auto_candidate'").fetchone()
    if sql and 'auto_run_v0' in sql[0]:
        c.execute('PRAGMA legacy_alter_table=ON')
        c.execute('ALTER TABLE auto_candidate RENAME TO auto_candidate_v0')
        c.executescript(SCHEMA)
        c.execute('INSERT INTO auto_candidate SELECT * FROM auto_candidate_v0')
        c.execute('DROP TABLE auto_candidate_v0')
        c.execute('PRAGMA legacy_alter_table=OFF')


def now():
    return datetime.now().isoformat(timespec='seconds')


def engine_html():
    """플러그인 ui.html + 포털용 손잡이. 파일을 복사하지 않고 매 요청마다 읽는다(규칙을 고치면 바로 반영)."""
    src = PLUGIN_UI.read_text(encoding='utf-8')
    if ENGINE_MARKER not in src:
        raise RuntimeError('검수기 시작 줄을 찾지 못했습니다(plugin-image-qa/ui.html).')
    return src.replace(ENGINE_MARKER, HARNESS_JS, 1)


def engine_rev():
    try:
        return hashlib.sha1(PLUGIN_UI.read_bytes()).hexdigest()[:12]
    except OSError:
        return ''


HARNESS_JS = r'''
window.__portal=true;
function __portalLoad(u){return new Promise(function(res,rej){var im=new Image();im.onload=function(){res(im);};im.onerror=function(){rej(new Error("이미지를 읽지 못했어요: "+u));};im.src=u;});}
function __portalLite(c){function rb(b){return b?{x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.w),h:Math.round(b.h)}:null;}
  return{no:c.no,status:c.status,policy:c.policy?{source:c.policy.source,variable:!!c.policy.variable,reason:c.policy.reason||""}:null,kind:c.kind||"area",label:c.label||"",detail:c.detail||"",confidence:c.confidence==null?null:Math.round(c.confidence),rawBox:rb(c.rawBox),designBox:rb(c.designBox),designNodeIds:c.designNodeIds||[],designValues:c.designValues||""};}
window.addEventListener("message",async function(e){var m=e.data;if(!m||m.type!=="portal-run")return;
  try{
    var full=await __portalLoad(m.design.pngUrl);var dc=canvasFor(full.width,full.height);dc.getContext("2d").drawImage(full,0,0);
    var cap=await __portalLoad(m.capture.pngUrl);
    var design={id:m.design.id,name:m.design.name,width:m.design.width,height:m.design.height,elements:m.design.elements||[],policy:m.design.policy||null};
    var capture={img:cap,width:cap.width,height:cap.height};
    if(m.capture.topTrim!=null)capture.topTrim=m.capture.topTrim;
    if(m.capture.bottomTrim!=null)capture.bottomTrim=m.capture.bottomTrim;
    var r=comparePair({id:"portal"},design,capture,dc),a=r.alignment||{};
    parent.postMessage({type:"portal-result",autoRunId:m.autoRunId,alignment:{mode:a.mode,s:a.s,tx:a.tx,ty:a.ty,score:a.score},range:r.range||null,notices:r.candidates.notices||[],candidates:r.candidates.map(__portalLite),capture:{w:cap.width,h:cap.height}},"*");
  }catch(err){parent.postMessage({type:"portal-error",autoRunId:m.autoRunId,message:String(err&&err.message||err)},"*");}
});
parent.postMessage({type:"portal-ready"},"*");
'''


class Auto:
    def __init__(self, store):
        self.store = store

    def init(self):
        with self.store.connect() as c:
            c.executescript(SCHEMA)

    # ── 페이지 ↔ 디자인 ─────────────────────────────────────────────
    def design_of_page(self, c, page_id):
        r = c.execute('SELECT design_id FROM page_design_link WHERE page_id=?', (page_id,)).fetchone()  # 플러그인에서 바로 받은 시안이 우선
        if not r:
            r = c.execute('SELECT design_id FROM design_case WHERE page_id=? AND design_id IS NOT NULL', (page_id,)).fetchone()
        if not r:
            r = c.execute('SELECT design_id FROM intake_item WHERE page_id=? AND design_id IS NOT NULL', (page_id,)).fetchone()
        if not r:
            return None
        return c.execute('SELECT d.*,a.filename,a.width,a.height FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?', (r['design_id'],)).fetchone()

    def ensure_elements(self, c, design):
        """디자인 요소 목록(검수기 입력). 없으면 Figma에서 프레임 전체를 읽어 저장한다."""
        row = c.execute('SELECT * FROM design_elements WHERE design_id=?', (design['id'],)).fetchone()
        if row:
            return {'frame': json.loads(row['frame']), 'elements': json.loads(row['elements'])}
        if design['provider'] != 'Figma REST' or design['file_key'] == 'local-design':
            raise ValueError('Figma 시안이 아니라 디자인 요소를 읽을 수 없어요. 시안을 Figma 링크로 연결하면 자동 검수가 됩니다.')
        data = figma_reader.api('files/' + design['file_key'] + '/nodes?ids=' + design['node_id'] + '&plugin_data=shared')
        item = (data.get('nodes') or {}).get(design['node_id'])
        if not item or not item.get('document'):
            raise ValueError('Figma에서 시안 프레임을 찾지 못했어요. 시안을 다시 연결해 주세요.')
        got = figma_elements.collect(item['document'])
        c.execute('INSERT OR REPLACE INTO design_elements VALUES (?,?,?,?,?)',
                  (design['id'], now(), data.get('version'), json.dumps(got['frame'], ensure_ascii=False), json.dumps(got['elements'], ensure_ascii=False)))
        return got

    # ── 자동 검수 회차 ─────────────────────────────────────────────
    def run_for(self, c, run_id, page_id=None):
        """그 차수 + 지금 시안의 자동 검수. 시안이 바뀌면 새로 돈다(옛 결과는 남는다)."""
        design = self.design_of_page(c, page_id) if page_id else None
        return c.execute('SELECT * FROM auto_run WHERE run_id=? AND design_id=?', (run_id, design['id'] if design else '')).fetchone()

    def ensure_run(self, page_id, run_id):
        """그 차수·지금 시안의 자동 검수가 없으면 '대기'로 만든다. 디자인이 안 붙은 페이지면 None."""
        with self.store.connect() as c:
            r = self.run_for(c, run_id, page_id)
            if r:
                return r
            design = self.design_of_page(c, page_id)
            if not design:
                return None
            c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,design_id) VALUES(?,?,?,?,?,?,?)',
                      (uid(), page_id, run_id, 'pending', engine_rev(), now(), design['id']))
            return self.run_for(c, run_id, page_id)

    def retry(self, page_id, run_id):
        with self.store.connect() as c:
            r = self.run_for(c, run_id, page_id)
            if r and r['status'] == 'failed':
                c.execute("UPDATE auto_run SET status='pending',error='',engine=? WHERE id=?", (engine_rev(), r['id']))

    def materials(self, page_id, run_id):
        """브라우저 엔진에 줄 재료(POST). 회차가 없으면 여기서 만든다. 실패하면 회차를 failed로 남기고 ValueError."""
        r = self.ensure_run(page_id, run_id)
        if not r:
            raise ValueError('이 페이지에 연결된 Figma 시안이 없어요.')
        try:
            with self.store.connect() as c:
                run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (run_id,)).fetchone()
                design = self.design_of_page(c, page_id)
                if not design:
                    raise ValueError('이 페이지에 연결된 Figma 시안이 없어요.')
                if not run or not run['dev_img']:
                    raise ValueError('이 차수에 개발 화면이 없어요.')
                got = self.ensure_elements(c, design)
        except ValueError as e:
            self.fail(r['id'], str(e))  # 실패 사유를 남긴다(같은 연결 안에서 쓰면 예외와 함께 되돌려지므로 따로)
            raise
        with self.store.connect() as c:
            settings = json.loads(design['qa_settings']) if design['qa_settings'] else {}
            frame = got['frame']
            return {
                'autoRunId': r['id'],
                'design': {'id': design['node_id'], 'name': design['name'], 'pngUrl': '/uploads/' + design['filename'],
                           'width': frame.get('width') or design['width'], 'height': frame.get('height') or design['height'],
                           'elements': got['elements'], 'policy': settings.get('policy')},
                'capture': {'pngUrl': '/uploads/' + run['dev_img'], 'width': run['dev_img_w'], 'height': run['dev_img_h']},
            }

    def save_result(self, auto_run_id, result):
        with self.store.connect() as c:
            r = c.execute('SELECT * FROM auto_run WHERE id=?', (auto_run_id,)).fetchone()
            if not r:
                raise ValueError('자동 검수 회차가 없어요.')
            if r['status'] == 'done':
                return r['id']  # 같은 결과가 두 번 오면 첫 결과를 지킨다
            cap = result.get('capture') or {}
            c.execute('UPDATE auto_run SET status=?,finished_at=?,alignment=?,range=?,notices=?,capture_w=?,capture_h=? WHERE id=?',
                      ('done', now(), json.dumps(result.get('alignment') or {}, ensure_ascii=False), json.dumps(result.get('range') or {}, ensure_ascii=False),
                       json.dumps(result.get('notices') or [], ensure_ascii=False), cap.get('w'), cap.get('h'), auto_run_id))
            for cand in result.get('candidates') or []:
                b = cand.get('rawBox') or {}
                c.execute('INSERT INTO auto_candidate VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                          (uid(), auto_run_id, int(cand.get('no') or 0), str(cand.get('kind') or 'area'), str(cand.get('label') or ''),
                           str(cand.get('detail') or ''), cand.get('confidence'), ENGINE_STATUS.get(cand.get('status'), 'open'), str(cand.get('status') or ''),
                           json.dumps(cand.get('policy') or {}, ensure_ascii=False), b.get('x'), b.get('y'), b.get('w'), b.get('h'),
                           json.dumps(cand.get('designBox') or {}, ensure_ascii=False), json.dumps(cand.get('designNodeIds') or [], ensure_ascii=False),
                           str(cand.get('designValues') or ''), None))
            return auto_run_id

    def fail(self, auto_run_id, message):
        with self.store.connect() as c:
            c.execute("UPDATE auto_run SET status='failed',error=?,finished_at=? WHERE id=? AND status<>'done'", (str(message)[:500], now(), auto_run_id))

    def candidates(self, c, auto_run_id):
        return c.execute('SELECT * FROM auto_candidate WHERE auto_run_id=? ORDER BY no', (auto_run_id,)).fetchall()

    # ── 사람의 판정 ───────────────────────────────────────────────
    def set_status(self, candidate_id, status, actor='', note=''):
        if status not in STATUS_LABEL:
            raise ValueError('알 수 없는 판정이에요.')
        with self.store.connect() as c:
            k = c.execute('SELECT * FROM auto_candidate WHERE id=?', (candidate_id,)).fetchone()
            if not k:
                raise ValueError('후보가 없어요.')
            if k['issue_id'] and status != 'open':
                raise ValueError('이미 지적으로 등록한 후보예요. 지적 쪽에서 처리해 주세요.')
            if k['status'] == status:
                return
            c.execute('UPDATE auto_candidate SET status=? WHERE id=?', (status, candidate_id))
            c.execute('INSERT INTO auto_candidate_event VALUES (?,?,?,?,?,?,?)', (uid(), candidate_id, k['status'], status, actor, now(), note))

    def register(self, candidate_id, actor, rnd):
        """후보 → 지적(inspection_issue). 사람이 누를 때만. dedup_key가 이미 있으면 그 지적에 잇는다."""
        with self.store.connect() as c:
            k = c.execute('SELECT k.*,r.page_id,r.run_id,r.capture_w,r.capture_h FROM auto_candidate k JOIN auto_run r ON r.id=k.auto_run_id WHERE k.id=?', (candidate_id,)).fetchone()
            if not k:
                raise ValueError('후보가 없어요.')
            if k['issue_id']:
                return k['issue_id']
            if k['status'] != 'open':
                raise ValueError('제외·가변으로 둔 후보는 먼저 되돌린 뒤 등록해 주세요.')
            page = c.execute('SELECT * FROM inspection_page WHERE uuid=?', (k['page_id'],)).fetchone()
            run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (k['run_id'],)).fetchone()
            sx = (run['coord_ref_w'] or k['capture_w'] or 1) / (k['capture_w'] or run['coord_ref_w'] or 1)
            sy = (run['coord_ref_h'] or k['capture_h'] or 1) / (k['capture_h'] or run['coord_ref_h'] or 1)
            box = [int(round((k['box_x'] or 0) * sx)), int(round((k['box_y'] or 0) * sy)), int(round((k['box_w'] or 0) * sx)), int(round((k['box_h'] or 0) * sy))]
            node_ids = json.loads(k['design_node_ids'] or '[]')
            anchor = node_ids[0] if node_ids else f'{box[0]},{box[1]},{box[2]},{box[3]}'
            dedup = f"{k['page_id']}|{anchor}|{k['kind']}|auto"
            category = KIND_CATEGORY.get(k['kind'], 'other')
            existing = c.execute('SELECT uuid,status FROM inspection_issue WHERE dedup_key=?', (dedup,)).fetchone()
            note = f"자동 검수 후보 #{k['no']} 등록: {k['label']}"
            if existing:
                issue_id = existing['uuid']
                self._history(c, issue_id, existing['status'], existing['status'], actor, f'{rnd}차 자동 후보 #{k["no"]} 재확인', rnd)
            else:
                issue_id = uid()
                c.execute('''INSERT INTO inspection_issue(uuid,screen_id,page_id,run_id,logical_element_key,box_x,box_y,box_w,box_h,category,expected,actual,description,severity,status,found_round,resolved_round,dedup_key,properties)
                             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (issue_id, page['screen_id'], k['page_id'], k['run_id'], k['label'] or issue_categories.label(category), box[0], box[1], box[2], box[3],
                           category, k['design_values'], '', k['detail'], '', '발견', rnd, None, dedup, json.dumps([issue_categories.label(category)], ensure_ascii=False)))
                self._history(c, issue_id, None, '발견', actor, note, rnd)
            c.execute('UPDATE auto_candidate SET issue_id=? WHERE id=?', (issue_id, candidate_id))
            c.execute('INSERT INTO auto_candidate_event VALUES (?,?,?,?,?,?,?)', (uid(), candidate_id, k['status'], 'open', actor, now(), note))
            return issue_id

    @staticmethod
    def _history(c, issue_id, from_status, to_status, actor, note, rnd):
        seq = c.execute('SELECT COALESCE(MAX(seq),-1)+1 s FROM issue_history WHERE issue_id=?', (issue_id,)).fetchone()['s']
        c.execute('INSERT INTO issue_history(uuid,issue_id,from_status,to_status,actor,at,note,seq,round) VALUES (?,?,?,?,?,?,?,?,?)',
                  (uid(), issue_id, from_status, to_status, actor, now(), note, seq, rnd))

    # ── 화면 조각 ─────────────────────────────────────────────────
    def view(self, page_id, run):
        """페이지 상세에 넣을 재료(읽기 전용 — 페이지를 여는 것만으로는 아무것도 쓰지 않는다).
        결과가 없으면 가상의 '대기' 상태를 돌려주고, 실제 회차 생성·엔진 실행은 페이지 JS의 POST가 한다."""
        if not run:
            return None
        try:
            with self.store.connect() as c:
                if not self.design_of_page(c, page_id):
                    return None
                r = self.run_for(c, run['uuid'], page_id)
                if not r:
                    return {'run': {'id': '', 'run_id': run['uuid'], 'status': 'pending', 'error': '', 'notices': '[]'},
                            'candidates': [], 'issue_numbers': {}, 'round': run['round'], 'scale': 1}
                cands = [dict(k) for k in self.candidates(c, r['id'])] if r['status'] == 'done' else []
                numbers = {}
                if any(k['issue_id'] for k in cands):
                    rows = c.execute('SELECT rowid rid,uuid FROM inspection_issue WHERE page_id=? ORDER BY rowid', (page_id,)).fetchall()
                    numbers = {row['uuid']: n + 1 for n, row in enumerate(rows)}
        except sqlite3.OperationalError:
            return None  # 옛 DB(접수·자동검수 표 없음)는 자동 검수 없이 그대로 보여준다
        return {'run': dict(r), 'candidates': cands, 'issue_numbers': numbers, 'round': run['round'],
                'scale': ((run['coord_ref_w'] or r['capture_w'] or 1) / (r['capture_w'] or run['coord_ref_w'] or 1)) if r['status'] == 'done' else 1}


def _e(v):
    return str(v if v is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def panel_html(view, page_id, person_options=''):
    """자동 검수 탭 안 내용. 후보 목록 + 판정 버튼. 상태(pending/failed)면 안내."""
    r = view['run']
    head = f'<div id="auto-state" data-status="{r["status"]}" data-page="{page_id}" data-run="{_e(r["run_id"])}" data-round="{view["round"]}" data-scale="{view["scale"]}"></div>'
    if r['status'] == 'pending':
        return head + '<p class="empty auto-msg" id="auto-msg">검수 중… 디자인과 개발 화면을 맞춰 보고 있어요. 잠시 뒤 결과가 뜹니다.</p>'
    if r['status'] == 'failed':
        return head + (f'<p class="empty auto-msg">자동 검수를 못 했어요 — {_e(r["error"])}</p>'
                       f'<form method="post" action="/auto/{_e(page_id)}/retry"><input type="hidden" name="run" value="{_e(r["run_id"])}"><button type="submit">다시 시도</button></form>')
    cands = view['candidates']
    notices = json.loads(r['notices'] or '[]')
    counts = {s: sum(1 for k in cands if k['status'] == s) for s in STATUS_LABEL}
    registered = sum(1 for k in cands if k['issue_id'])
    summary = f'확인할 후보 {counts["open"] - registered}건 · 지적 등록 {registered} · 제외 {counts["excluded"]} · 가변 글자·요소 {counts["variable"]}'
    notice_html = ''.join(f'<li>{_e(n)}</li>' for n in notices)
    out = head + f'<div class="auto-head"><span class="auto-sum">{summary}</span><span class="auto-hint">번호는 자동으로 찾은 후보예요. 오류가 맞으면 <b>지적 등록</b>, 아니면 <b>제외</b>를 누르세요. 손대지 않은 후보는 후보로 남습니다.</span></div>'
    if notice_html:
        out += f'<ul class="auto-notice">{notice_html}</ul>'
    groups = [('open', '후보'), ('excluded', '제외(오류 아님)'), ('variable', '가변 글자·요소')]
    for key, title in groups:
        items = [k for k in cands if k['status'] == key]
        if not items and key != 'open':
            continue
        fold = ' open' if key == 'open' else ''
        out += f'<details class="auto-group"{fold}><summary>{title} <span class="cnt">{len(items)}</span></summary><div class="grid">'
        out += ''.join(card_html(k, view['issue_numbers'], page_id, view['round'], person_options) for k in items) or '<p class="empty">항목 없음</p>'
        out += '</div></details>'
    return out


def card_html(k, numbers, page_id, rnd, person_options=''):
    kind_lbl = issue_categories.label(KIND_CATEGORY.get(k['kind'], 'other'))
    color = issue_categories.color(KIND_CATEGORY.get(k['kind'], 'other'))
    pol = json.loads(k['policy'] or '{}')
    pol_html = f'<div class="loc">가변 판정: {_e(pol.get("reason"))}</div>' if pol.get('reason') else ''
    conf = f'<span class="sev">신뢰도 {k["confidence"]}%</span>' if k['confidence'] is not None else ''
    if k['issue_id']:
        n = numbers.get(k['issue_id'])
        foot = f'<div class="passed">✓ 지적 #{n}로 등록됨</div>' if n else '<div class="passed">✓ 지적으로 등록됨</div>'
    else:
        btn = lambda st, txt, cls='': f'<button type="button" class="{cls}" onclick="autoStatus(\'{k["id"]}\',\'{st}\')">{txt}</button>'
        if k['status'] == 'open':
            foot = (f'<form class="auto-actions passform" onsubmit="return autoRegister(this,\'{k["id"]}\')" onclick="event.stopPropagation()">'
                    f'<select name="actor" required><option value="">담당자</option>{person_options}</select>'
                    f'<button type="submit" class="primary">지적 등록</button>'
                    f'{btn("excluded", "제외")}{btn("variable", "가변") if k["kind"] in ("text", "fixed", "variable") else ""}</form>')
        else:
            foot = f'<div class="auto-actions">{btn("open", "후보로 되돌리기")}</div>'
    box = f'({int(k["box_x"] or 0)},{int(k["box_y"] or 0)}) {int(k["box_w"] or 0)}×{int(k["box_h"] or 0)}'
    dv = f'<div class="loc">디자인 원본값: {_e(k["design_values"])}</div>' if k['design_values'] else ''
    return (f'<div class="issue auto-card st-{k["status"]}{" registered" if k["issue_id"] else ""}" id="cand-{k["id"]}" data-cand="{k["id"]}" onclick="autoFocus(\'{k["id"]}\')">'
            f'<div class="ihead"><span class="pinno auto-no" style="background:{color}">{k["no"]}</span><span class="state">{_e(STATUS_LABEL[k["status"]])}</span>{conf}<b>{_e(k["label"])}</b></div>'
            f'<div class="props"><span class="tag">{_e(kind_lbl)}</span></div>'
            f'<div class="loc">{_e(k["detail"])}</div>{dv}{pol_html}<div class="loc">위치 {box}</div>{foot}</div>')


def overlay_json(view):
    return json.dumps([{'id': k['id'], 'no': k['no'], 'status': k['status'], 'registered': bool(k['issue_id']),
                        'color': issue_categories.color(KIND_CATEGORY.get(k['kind'], 'other')),
                        'box': [k['box_x'] or 0, k['box_y'] or 0, k['box_w'] or 0, k['box_h'] or 0]} for k in view['candidates']], ensure_ascii=False)


CSS = '''
.auto-overlay{pointer-events:none}.auto-overlay .abox,.auto-overlay .abadge rect{pointer-events:auto}
.auto-overlay .abox{fill:none;stroke-width:3;stroke-dasharray:10 6;cursor:pointer}
.auto-overlay .abox.dim{opacity:.25}
.auto-overlay .abadge rect{stroke:#fff;stroke-width:2;cursor:pointer}
.auto-overlay .abadge text{fill:#fff;font:bold 24px sans-serif;text-anchor:middle;pointer-events:none}
.auto-overlay .abadge.dim{opacity:.35}
.auto-overlay .abadge.sel rect{stroke:#111;stroke-width:4}
.auto-overlay .abox.sel{stroke-width:6;stroke-dasharray:none}
.auto-head{display:flex;flex-direction:column;gap:4px;margin:4px 0 10px;font-size:13px}
.auto-sum{font-weight:700}.auto-hint{color:#64748b}
.auto-notice{margin:0 0 10px;padding-left:18px;color:#b45309;font-size:12px}
.auto-group{margin-bottom:10px}.auto-group summary{cursor:pointer;font-weight:700;margin-bottom:6px}
.auto-card .auto-no{border-radius:4px}
.auto-card.st-excluded,.auto-card.st-variable{opacity:.7}
.auto-actions{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}
.auto-actions select{font-size:12px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:6px;background:#fff}
.auto-actions button{font-size:12px;padding:4px 8px;border:1px solid #cbd5e1;background:#fff;color:#1f2937;border-radius:6px;cursor:pointer}
.auto-actions button.primary{background:#ea580c;border-color:#ea580c;color:#fff}
.auto-msg{color:#475569}
'''

JS = r'''
(function(){
  var st=document.getElementById('auto-state');if(!st)return;
  var page=st.dataset.page,run=st.dataset.run;
  // ── 저장된 후보를 개발 화면 위에 그린다(점선 상자 + 네모 번호) ──
  var dataEl=document.getElementById('auto-data'),svg=document.querySelector('svg.auto-overlay');
  if(dataEl&&svg){
    var items=JSON.parse(dataEl.textContent||'[]'),k=Number(st.dataset.scale)||1,ns='http://www.w3.org/2000/svg';
    items.forEach(function(c){
      var b=c.box.map(function(v){return v*k;}),dim=c.status!=='open'?' dim':'';
      var r=document.createElementNS(ns,'rect');r.setAttribute('x',b[0]);r.setAttribute('y',b[1]);r.setAttribute('width',b[2]);r.setAttribute('height',b[3]);r.setAttribute('rx',4);
      r.setAttribute('class','abox'+dim);r.setAttribute('id','abox-'+c.id);r.style.stroke=c.color;r.onclick=function(){autoFocus(c.id);};svg.appendChild(r);
      var g=document.createElementNS(ns,'g');g.setAttribute('class','abadge'+dim);g.setAttribute('id','abadge-'+c.id);
      var bx=Math.max(0,b[0]-8),by=Math.max(0,b[1]-36);
      var q=document.createElementNS(ns,'rect');q.setAttribute('x',bx);q.setAttribute('y',by);q.setAttribute('width',44);q.setAttribute('height',32);q.setAttribute('rx',6);q.style.fill=c.color;q.onclick=function(){autoFocus(c.id);};
      var t=document.createElementNS(ns,'text');t.setAttribute('x',bx+22);t.setAttribute('y',by+24);t.textContent=String(c.no);
      g.appendChild(q);g.appendChild(t);svg.appendChild(g);
    });
  }
  // ── 아직 결과가 없으면 숨은 엔진을 돌려 저장하고 다시 연다 ──
  if(st.dataset.status!=='pending')return;
  var msg=document.getElementById('auto-msg');
  function say(t){if(msg)msg.textContent=t;}
  function post(url,body){return fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json();});}
  post('/auto/'+page+'/materials',{run:run}).then(function(m){
    if(m.error){say('자동 검수를 못 했어요 — '+m.error);setTimeout(function(){location.reload();},1500);return;}
    var f=document.createElement('iframe');f.src='/engine/ui.html';f.setAttribute('aria-hidden','true');f.style.cssText='position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;left:-9999px';
    var done=false;
    window.addEventListener('message',function(e){var d=e.data;if(!d||!d.type||done)return;
      if(d.type==='portal-ready'){f.contentWindow.postMessage(Object.assign({type:'portal-run'},m),'*');}
      else if(d.type==='portal-result'){done=true;post('/auto/'+page+'/result',d).then(function(){location.reload();});}
      else if(d.type==='portal-error'){done=true;post('/auto/'+page+'/fail',{autoRunId:m.autoRunId,message:d.message}).then(function(){location.reload();});}
    });
    document.body.appendChild(f);
    setTimeout(function(){if(!done){done=true;post('/auto/'+page+'/fail',{autoRunId:m.autoRunId,message:'시간이 너무 오래 걸려 멈췄어요(3분).'}).then(function(){location.reload();});}},180000);
  }).catch(function(){say('자동 검수 재료를 못 받았어요.');});
})();
function autoFocus(id){
  document.querySelectorAll('.auto-overlay .sel').forEach(function(e){e.classList.remove('sel');});
  document.querySelectorAll('.auto-card.hl').forEach(function(e){e.classList.remove('hl');});
  var b=document.getElementById('abox-'+id),g=document.getElementById('abadge-'+id),c=document.getElementById('cand-'+id);
  if(b)b.classList.add('sel');if(g){g.classList.add('sel');g.parentNode.appendChild(g);}
  if(c){var panel=c.closest('.panel');if(panel&&window.showTab)showTab(panel.id.replace('panel-',''));c.classList.add('hl');var d=c.closest('details');if(d)d.open=true;var box=document.getElementById('cards');if(box)box.scrollTop=c.offsetTop-40;}
}
function autoStatus(id,status){
  var st=document.getElementById('auto-state');
  fetch('/auto/'+st.dataset.page+'/candidate/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
}
function autoRegister(form,id){
  var st=document.getElementById('auto-state'),actor=(form.actor.value||'').trim();
  if(!actor){alert('담당자를 골라 주세요.');return false;}
  fetch('/auto/'+st.dataset.page+'/candidate/'+id+'/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({actor:actor,round:Number(st.dataset.round)||1})})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
  return false;
}
'''


# ── HTTP ─────────────────────────────────────────────────────────
def _json(handler, obj, code=200):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _body_json(handler):
    length = int(handler.headers.get('Content-Length', 0) or 0)
    raw = handler.rfile.read(length) if length else b''
    try:
        return json.loads(raw.decode('utf-8')) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def get(handler, store, path, q):
    """GET /engine/ui.html (엔진 한 벌 + 포털 손잡이)"""
    if path == '/engine/ui.html':
        data = engine_html().encode('utf-8')
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/html; charset=utf-8')
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return True
    return False


def post(handler, store, path):
    """POST /auto/<page>/materials · /result · /fail · /retry · /candidate/<id>/status · /candidate/<id>/register"""
    parts = path.strip('/').split('/')
    if len(parts) < 3 or parts[0] != 'auto':
        return False
    auto = Auto(store)
    page_id, action = parts[1], parts[2]
    try:
        if action == 'materials' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, auto.materials(page_id, str(body.get('run') or '')))
        elif action == 'result' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, {'ok': auto.save_result(str(body.get('autoRunId') or ''), body)})
        elif action == 'fail' and len(parts) == 3:
            body = _body_json(handler)
            auto.fail(str(body.get('autoRunId') or ''), body.get('message') or '알 수 없는 오류')
            _json(handler, {'ok': True})
        elif action == 'retry' and len(parts) == 3:
            from urllib.parse import parse_qs
            length = int(handler.headers.get('Content-Length', 0) or 0)
            form = parse_qs(handler.rfile.read(length).decode('utf-8')) if length else {}
            auto.retry(page_id, (form.get('run') or [''])[0])
            handler.send_response(303)
            handler.send_header('Location', handler.headers.get('Referer') or '/')
            handler.end_headers()
        elif action == 'candidate' and len(parts) == 5 and parts[4] == 'status':
            body = _body_json(handler)
            auto.set_status(parts[3], str(body.get('status') or ''), str(body.get('actor') or ''), str(body.get('note') or ''))
            _json(handler, {'ok': True})
        elif action == 'candidate' and len(parts) == 5 and parts[4] == 'register':
            body = _body_json(handler)
            _json(handler, {'ok': True, 'issue': auto.register(parts[3], str(body.get('actor') or ''), int(body.get('round') or 1))})
        else:
            return False
    except ValueError as e:
        _json(handler, {'error': str(e)}, 200)
    return True
