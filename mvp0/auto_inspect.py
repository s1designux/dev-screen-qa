"""포털 자동 검수(후보 찾기) — 페이지 상세를 열면 저장된 후보가 바로 보이게 한다.

원칙(CLAUDE.md 2번): 자동 검수는 '후보'만 만든다. 확정(지적 등록)은 사람이 누른다.
엔진은 engine/ui.html 한 벌을 그대로 쓴다(복사하지 않는다). 포털은 그 파일을
/engine/ui.html 로 내보내며 맨 끝 시작 줄만 포털용 손잡이(harness)로 바꿔 끼운다.

흐름: 페이지 상세 열림 → (그 차수에 결과가 없으면) 브라우저가 숨은 iframe에서 엔진을 돌려
결과를 POST → 저장 → 다시 열면 저장본이 바로 표시. 후보·판정·등록 이력은 지우지 않는다.
"""
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import card_view
import figma_elements
import figma_reader
import issue_categories
import policy as policymod
import rule_log
import value_candidates

ENGINE_UI = Path(__file__).resolve().parents[1] / 'engine' / 'ui.html'
PLUGIN_UI = ENGINE_UI  # (옛 이름) 2026-09-14 피그마 플러그인 폐기 — 엔진 원본은 engine/ui.html 한 벌뿐이다
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
 capture_w INTEGER, capture_h INTEGER, design_id TEXT NOT NULL DEFAULT '',
 source TEXT NOT NULL DEFAULT 'engine'
);
CREATE TABLE IF NOT EXISTS auto_range (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES inspection_run(uuid),
 top INTEGER, bottom INTEGER, actor TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS auto_range_no_update BEFORE UPDATE ON auto_range BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS auto_range_no_delete BEFORE DELETE ON auto_range BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
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

STATUS_LABEL = {'open': '수정필요', 'excluded': '제외', 'variable': '가변 글자·요소'}
ENGINE_STATUS = {'confirmed': 'open', 'excluded': 'excluded', 'variable': 'variable'}
# 후보 종류 → 포털 이슈 분류(issue_categories.ALIASES 키)
KIND_CATEGORY = {'text': 'text', 'fixed': 'text', 'variable': 'text', 'missing': 'missing', 'area': 'mixed',
                 'position': 'position', 'icon': 'icon', 'image': 'image', 'shape': 'appearance', 'spacing': 'spacing'}

# 갈래는 **카드에 적힌 말**을 따른다. 요소 종류로 나누면 같은 말이 서로 다른 갈래로 흩어진다.
# (예: '디자인에 없는 요소'는 요소를 짚었든 자리로만 짚었든 '요소 추가·누락'이다.)
LABEL_CATEGORY = [
    ('디자인에 없는 요소', 'structure'),
    ('디자인에 있는 요소', 'structure'),
    ('아이콘 또는 이미지', 'icon'),
    ('색상이 다르게', 'color'),
    ('요소의 모양 또는 크기', 'shape'),
    ('요소의 위치 또는 정렬', 'position'),
    ('화면 맨 위 여백', 'position'),
    ('글자', 'text'),
    ('줄바꿈 또는 말줄임', 'text'),
    ('폰트 모양', 'text'),
]


def candidate_category(k):
    label = str(k['label'] or '')
    for prefix, cat in LABEL_CATEGORY:
        if label.startswith(prefix):
            return cat
    return KIND_CATEGORY.get(k['kind'], 'other')


def uid():
    return uuid.uuid4().hex


def migrate(c):
    """(호환용) 같은 연결 안에서는 외래키 검사를 끌 수 없어 표를 고칠 수 없다. Store.init()이 repair(경로)를 부른다."""
    return


def _table_sql(name):
    m = re.search(r'CREATE TABLE IF NOT EXISTS ' + name + r' \((.*?)\n\);', SCHEMA, re.S)
    return m.group(1)


def repair(database):
    """옛 모양의 자동 검수 표를 지금 모양으로 다시 세운다. 행은 하나도 버리지 않는다.
    - auto_run: design_id·source가 없거나 (run_id, design_id) 유일 제약이 남아 있으면(검수 범위를 바꿔 다시 돌리면 회차가 여러 개) 다시 세운다.
    - auto_candidate / auto_candidate_event: 참조가 이름 바뀐 옛 표(auto_run_v1 등)를 가리키면 다시 세운다.
    - 이름 바꾸다 남은 auto_run_v0/v1, auto_candidate_v0의 행은 합치고 표는 지운다.
    외래키 검사를 끈 별도 연결에서 한다(같은 연결·트랜잭션 안에서는 끌 수 없어 참조가 꼬였다)."""
    conn = sqlite3.connect(str(database))
    conn.execute('PRAGMA foreign_keys=OFF')
    conn.execute('PRAGMA legacy_alter_table=ON')  # 이름을 바꿀 때 다른 표의 참조를 건드리지 않는다
    try:
        def names():
            return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        def sql_of(n):
            r = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (n,)).fetchone()
            return r[0] if r else ''
        def cols(n):
            return [r[1] for r in conn.execute(f'PRAGMA table_info("{n}")')]
        def rebuild(table):
            conn.execute(f'CREATE TABLE "{table}__new" ({_table_sql(table)})')
            shared = [c for c in cols(table) if c in cols(table + '__new')]
            conn.execute(f'INSERT INTO "{table}__new"({",".join(shared)}) SELECT {",".join(shared)} FROM "{table}"')
            conn.execute(f'DROP TABLE "{table}"')
            conn.execute(f'ALTER TABLE "{table}__new" RENAME TO "{table}"')
        def merge(into, leftover):
            if leftover not in names():
                return
            shared = [c for c in cols(leftover) if c in cols(into)]
            conn.execute(f'INSERT INTO "{into}"({",".join(shared)}) SELECT {",".join(shared)} FROM "{leftover}" WHERE id NOT IN (SELECT id FROM "{into}")')
            conn.execute(f'DROP TABLE "{leftover}"')
        with conn:
            conn.executescript(SCHEMA)  # 없는 표·트리거를 만든다(있는 것은 그대로)
            for t in ('auto_run__new', 'auto_candidate__new', 'auto_candidate_event__new'):
                if t in names():
                    conn.execute(f'DROP TABLE "{t}"')  # 전에 고치다 만 자취
            if 'design_id' not in cols('auto_run') or 'source' not in cols('auto_run') or 'UNIQUE(' in sql_of('auto_run'):
                rebuild('auto_run')
            merge('auto_run', 'auto_run_v1')
            merge('auto_run', 'auto_run_v0')
            if not re.search(r'REFERENCES\s+"?auto_run"?\s*\(id\)', sql_of('auto_candidate')):
                rebuild('auto_candidate')
            merge('auto_candidate', 'auto_candidate_v0')
            if not re.search(r'REFERENCES\s+"?auto_candidate"?\s*\(id\)', sql_of('auto_candidate_event')):
                rebuild('auto_candidate_event')
            conn.executescript(SCHEMA)  # 다시 세운 표의 트리거
    finally:
        conn.close()


def now():
    return datetime.now().isoformat(timespec='seconds')


def engine_html():
    """플러그인 ui.html + 포털용 손잡이. 파일을 복사하지 않고 매 요청마다 읽는다(규칙을 고치면 바로 반영)."""
    src = PLUGIN_UI.read_text(encoding='utf-8')
    if ENGINE_MARKER not in src:
        raise RuntimeError('검수기 시작 줄을 찾지 못했습니다(engine/ui.html).')
    return src.replace(ENGINE_MARKER, HARNESS_JS, 1)


_ENGINE_REV = {}


def engine_rev():
    """지금 검수 규칙(엔진 파일)의 지문. 파일이 바뀌면 값이 달라진다."""
    try:
        stamp = PLUGIN_UI.stat().st_mtime_ns
    except OSError:
        return ''
    if _ENGINE_REV.get('stamp') != stamp:
        try:
            _ENGINE_REV.update(stamp=stamp, rev=hashlib.sha1(PLUGIN_UI.read_bytes()).hexdigest()[:12])
        except OSError:
            return ''
    return _ENGINE_REV.get('rev', '')


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
        if design['provider'] == 'Figma 플러그인':
            raise ValueError('이 시안은 플러그인에서 요소 목록 없이 왔어요. 피그마에서 플러그인을 다시 불러온 뒤 그 프레임을 골라 「검수 시안 바꾸기」를 눌러 주세요.')
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
        return c.execute("SELECT * FROM auto_run WHERE run_id=? AND design_id=? AND source='engine' ORDER BY rowid DESC LIMIT 1",
                         (run_id, design['id'] if design else '')).fetchone()

    # ── 검수 범위(사람이 정한 위·아래 제외 px) ────────────────────────
    def current_range(self, c, run_id):
        """그 차수 개발 화면에 사람이 마지막으로 정한 검수 범위. 없으면 None(자동)."""
        try:
            return c.execute('SELECT * FROM auto_range WHERE run_id=? ORDER BY rowid DESC LIMIT 1', (run_id,)).fetchone()
        except sqlite3.OperationalError:
            return None

    def set_range(self, page_id, run_id, top, bottom, actor='', note=''):
        """검수 범위를 기록하고(append-only) 그 차수·지금 시안의 자동 검수를 새 회차로 다시 돌게 한다. 옛 회차·후보는 남는다.
        top/bottom이 둘 다 None이면 '자동으로 되돌림'."""
        def px(v, name):
            if v is None or v == '':
                return None
            try:
                v = int(round(float(v)))
            except (TypeError, ValueError):
                raise ValueError(f'{name} 값이 숫자가 아니에요.')
            if v < 0:
                raise ValueError(f'{name} 값은 0 이상이어야 해요.')
            return v
        top, bottom = px(top, '위쪽'), px(bottom, '아래쪽')
        with self.store.connect() as c:
            run = c.execute('SELECT * FROM inspection_run WHERE uuid=?', (run_id,)).fetchone()
            if not run or not run['dev_img']:
                raise ValueError('이 차수에 개발 화면이 없어요.')
            h = run['dev_img_h'] or 0
            if h and (top or 0) + (bottom or 0) >= h - 8:
                raise ValueError('위·아래를 합치면 화면이 남지 않아요.')
            design = self.design_of_page(c, page_id)
            if not design:
                raise ValueError('이 페이지에 연결된 Figma 시안이 없어요.')
            c.execute('INSERT INTO auto_range VALUES (?,?,?,?,?,?,?)', (uid(), run_id, top, bottom, actor, now(), note))
            new_id = uid()
            c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,design_id) VALUES(?,?,?,?,?,?,?)',
                      (new_id, page_id, run_id, 'pending', engine_rev(), now(), design['id']))
            return new_id

    def ensure_run(self, page_id, run_id):
        """그 차수·지금 시안의 자동 검수가 없으면 '대기'로 만든다. 디자인이 안 붙은 페이지면 None.

        검수 규칙(엔진)이 바뀌었으면 새 회차로 다시 돌린다 — 옛 회차·후보·이력은 그대로 남는다
        (검수 범위를 바꿀 때와 같은 방식). 규칙을 고쳐 놓고 옛 결과를 계속 보여 주면
        고친 것이 화면에 반영되지 않는다.
        """
        rev = engine_rev()
        with self.store.connect() as c:
            r = self.run_for(c, run_id, page_id)
            if r and (r['status'] != 'done' or (r['engine'] or '') == rev or not rev):
                return r
            design = self.design_of_page(c, page_id)
            if not design:
                return r
            c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,design_id) VALUES(?,?,?,?,?,?,?)',
                      (uid(), page_id, run_id, 'pending', rev, now(), design['id']))
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
            # 정책 값은 층으로 겹친다: 시스템 → 서비스 → 화면 → 요소. 피그마 프레임에서 따라온 설정은 포털 행이 없을 때만.
            pol = policymod.Policy(self.store)
            merged = pol.engine_policy(c, run['screen_id'], settings.get('policy'))
            out = {
                'autoRunId': r['id'],
                'design': {'id': design['node_id'], 'name': design['name'], 'pngUrl': '/uploads/' + design['filename'],
                           'width': frame.get('width') or design['width'], 'height': frame.get('height') or design['height'],
                           'elements': got['elements'], 'policy': merged or None},
                'capture': {'pngUrl': '/uploads/' + run['dev_img'], 'width': run['dev_img_w'], 'height': run['dev_img_h']},
            }
            # 검수 범위: 이 차수에 직접 정한 것 > 화면·서비스 층에 정한 것 > 자동 규칙
            top, bottom = pol.capture_range(c, run['screen_id'])
            rng = self.current_range(c, run_id)
            if rng:
                top, bottom = rng['top'], rng['bottom']
            if top is not None:
                out['capture']['topTrim'] = top
            if bottom is not None:
                out['capture']['bottomTrim'] = bottom
            return out

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
            rule_log.record(c, k, status, actor=actor, note=note)  # 어느 규칙이 이 후보를 그 자리에 뒀는지 함께 남긴다
            self._remember(c, k, status, actor)

    def _remember(self, c, k, status, actor):
        """사람이 후보에 내린 판정을 그 화면의 **요소 층 정책**으로 쌓는다 — 다음 차수·다음 시안에서도 기억하게.
        가변 ↔ 고정(open)은 글자에만, 제외는 어떤 요소든. 요소를 여럿 가리키는 후보는 하나하나에 쓴다."""
        if value_candidates.값후보인가(k):
            return                                   # 값 대조 후보의 판정은 그림 검수 규칙이 아니다 — 요소 층에 쌓지 않는다
        ids = json.loads(k['design_node_ids'] or '[]')
        if not ids:
            return
        run = c.execute('SELECT r.screen_id FROM auto_run a JOIN inspection_run r ON r.uuid=a.run_id WHERE a.id=?', (k['auto_run_id'],)).fetchone()
        if not run:
            return
        pol = policymod.Policy(self.store)
        for nid in ids:
            if status == 'variable':
                pol.set(c, 'element', 'text.variable', True, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 가변으로')
            elif status == 'excluded':
                pol.set(c, 'element', 'element.exclude', True, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 제외로')
            else:  # open: 가변·제외를 거둔다. 글자면 '고정'으로 못 박는다(사람이 정한 것이 규칙보다 앞선다)
                pol.set(c, 'element', 'element.exclude', None, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}를 되돌림')
                if k['kind'] in ('text', 'fixed', 'variable'):
                    pol.set(c, 'element', 'text.variable', False, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}에서 고정으로')
                else:
                    pol.set(c, 'element', 'text.variable', None, target=run['screen_id'], key=nid, actor=actor, note=f'후보 #{k["no"]}를 되돌림')

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
            category = candidate_category(k)
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
            rule_log.record(c, k, 'open', actor=actor, action='register', note=note)  # 사람이 진짜 오류로 인정 — 규칙이 맞았다는 기록
            return issue_id

    @staticmethod
    def _history(c, issue_id, from_status, to_status, actor, note, rnd):
        seq = c.execute('SELECT COALESCE(MAX(seq),-1)+1 s FROM issue_history WHERE issue_id=?', (issue_id,)).fetchone()['s']
        c.execute('INSERT INTO issue_history(uuid,issue_id,from_status,to_status,actor,at,note,seq,round) VALUES (?,?,?,?,?,?,?,?,?)',
                  (uid(), issue_id, from_status, to_status, actor, now(), note, seq, rnd))

    # ── 화면 조각 ─────────────────────────────────────────────────
    def view(self, page_id, run):
        """페이지 상세에 넣을 재료 — 그림 검수 후보 + 값 대조 후보(valueqa)를 한 목록으로."""
        return value_candidates.붙이기(self.store, page_id, run, self._engine_view(page_id, run))

    def _engine_view(self, page_id, run):
        """그림 검수(engine/ui.html) 쪽 재료(읽기 전용 — 페이지를 여는 것만으로는 아무것도 쓰지 않는다).
        결과가 없으면 가상의 '대기' 상태를 돌려주고, 실제 회차 생성·엔진 실행은 페이지 JS의 POST가 한다."""
        if not run:
            return None
        try:
            with self.store.connect() as c:
                design = self.design_of_page(c, page_id)
                if not design:
                    return None
                fr = c.execute('SELECT frame FROM design_elements WHERE design_id=?', (design['id'],)).fetchone()
                try:
                    dframe = json.loads(fr['frame']) if fr else {}
                except (TypeError, ValueError):
                    dframe = {}
                design_frame = {'w': dframe.get('width') or design['width'], 'h': dframe.get('height') or design['height']}
                r = self.run_for(c, run['uuid'], page_id)
                rng = self.current_range(c, run['uuid'])
                range_view = {'manual_top': rng['top'] if rng else None, 'manual_bottom': rng['bottom'] if rng else None,
                              'dev_img': run['dev_img'], 'w': run['dev_img_w'], 'h': run['dev_img_h']}
                rev = engine_rev()
                stale = bool(r) and r['status'] == 'done' and bool(rev) and (r['engine'] or '') != rev
                if not r or stale:
                    # 검수 규칙을 고쳤으면 옛 결과를 그대로 보여 주지 않는다. 페이지 JS가 새 회차를 돌려 저장한다.
                    return {'run': {'id': '', 'run_id': run['uuid'], 'status': 'pending', 'error': '', 'notices': '[]'},
                            'candidates': [], 'issue_numbers': {}, 'round': run['round'], 'scale': 1, 'range': range_view,
                            'screen_id': run['screen_id'], 'design_frame': design_frame}
                cands = [dict(k) for k in self.candidates(c, r['id'])] if r['status'] == 'done' else []
                numbers = {}
                if any(k['issue_id'] for k in cands):
                    rows = c.execute('SELECT rowid rid,uuid FROM inspection_issue WHERE page_id=? ORDER BY rowid', (page_id,)).fetchall()
                    numbers = {row['uuid']: n + 1 for n, row in enumerate(rows)}
        except sqlite3.OperationalError:
            return None  # 옛 DB(접수·자동검수 표 없음)는 자동 검수 없이 그대로 보여준다
        try:
            al = json.loads(r['alignment'] or '{}')
        except (TypeError, ValueError, IndexError):
            al = {}
        return {'run': dict(r), 'candidates': cands, 'issue_numbers': numbers, 'round': run['round'], 'range': range_view,
                'screen_id': run['screen_id'], 'design_frame': design_frame, 'alignment': al,
                'scale': ((run['coord_ref_w'] or r['capture_w'] or 1) / (r['capture_w'] or run['coord_ref_w'] or 1)) if r['status'] == 'done' else 1}


def _e(v):
    return str(v if v is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def panel_html(view, page_id, person_options='', which='open'):
    """자동 검수 내용. which='open'이면 '수정필요' 칸(대기·실패 안내와 검수 범위도 여기), 'excluded'면 '제외' 칸."""
    if which != 'open':
        items = [k for k in view['candidates'] if k['status'] != 'open']
        cards = ''.join(card_html(k, view['issue_numbers'], page_id, view['round']) for k in items)
        return f'<div class="grid">{cards}</div>' if cards else '<p class="empty">항목 없음</p>'
    r = view['run']
    df = view.get('design_frame') or {}
    al = view.get('alignment') or {}
    try:
        ctop = (json.loads(r['range'] or '{}') or {}).get('captureTop') or 0   # 엔진이 잘라낸 위쪽 띠 — 맞춤값이 잘린 그림 기준이라 되돌려 줘야 한다
    except (TypeError, ValueError, IndexError, KeyError):
        ctop = 0
    head = (f'<div id="auto-state" data-status="{r["status"]}" data-page="{page_id}" data-run="{_e(r["run_id"])}" '
            f'data-round="{view["round"]}" data-scale="{view["scale"]}" '
            f'data-dw="{df.get("w") or 0}" data-dh="{df.get("h") or 0}" '
            f'data-as="{al.get("s") or 0}" data-atx="{al.get("tx") or 0}" data-aty="{al.get("ty") or 0}" '
            f'data-actop="{ctop}"></div>')
    def grid(items):
        cards = ''.join(card_html(k, view['issue_numbers'], page_id, view['round']) for k in items)
        return f'<div class="grid">{cards}</div>' if cards else ''
    열린것 = [k for k in view['candidates'] if k['status'] == 'open']
    # 그림 검수가 아직 돌고 있거나 못 돌았어도 값 대조 후보는 이미 나와 있다 — 먼저 보여 준다.
    값것 = [k for k in 열린것 if value_candidates.값후보인가(k)]
    if r['status'] == 'pending':
        줄 = ' inline' if 값것 else ''
        return head + (f'<p class="empty auto-wait{줄}"><span class="auto-spin" aria-hidden="true"></span>'
                       '<span id="auto-msg">검수중입니다.</span></p>') + grid(값것)
    if r['status'] == 'failed':
        return head + (f'<p class="empty auto-msg">자동 검수를 못 했어요 — {_e(r["error"])}</p>'
                       f'<form method="post" action="/auto/{_e(page_id)}/retry"><input type="hidden" name="run" value="{_e(r["run_id"])}"><button type="submit">다시 시도</button></form>'
                       + range_html(view, person_options)) + grid(값것)
    return head + range_html(view, person_options) + grid(열린것)


def range_html(view, person_options=''):
    """검수 범위 카드: 지금 개발 화면에서 위·아래 몇 px를 비교에서 뺐는지 + '조정'(선 두 개 끌기 → 그 범위로 다시 검수)."""
    rv = view.get('range') or {}
    if view.get('값만') or not rv.get('dev_img'):
        return ''
    r = view['run']
    try:
        eng = json.loads(r.get('range') or '{}') if isinstance(r, dict) else {}
    except (TypeError, ValueError):
        eng = {}
    top, bottom = eng.get('captureTop') or 0, eng.get('captureBottom') or 0
    rules = {}
    for x in eng.get('rules') or []:
        rules.setdefault(x.get('edge'), []).append(x.get('title') or '')
    def how(edge, manual, px):
        if manual is not None:
            return '직접 정함'
        if not px:
            return '자동 · 뺀 것 없음'
        return '자동 · ' + ('·'.join(rules[edge]) if rules.get(edge) else ('브라우저 틀' if edge == 'top' else '하단 띠'))
    mt, mb = rv.get('manual_top'), rv.get('manual_bottom')
    if r.get('status') == 'done':
        summary = f'위쪽 {top}px ({how("top", mt, top)}) · 아래쪽 {bottom}px ({how("bottom", mb, bottom)})'
    else:
        summary = '직접 정한 범위로 검수함' if (mt is not None or mb is not None) else '자동'
    return (f'<div class="auto-range" id="auto-range" data-img="/uploads/{_e(rv["dev_img"])}" data-w="{rv.get("w") or 0}" data-h="{rv.get("h") or 0}" '
            f'data-top="{top}" data-bottom="{bottom}" data-mtop="{"" if mt is None else mt}" data-mbottom="{"" if mb is None else mb}">'
            f'<b>검수 범위</b> <span class="auto-range-sum">{_e(summary)}</span>'
            f'<button type="button" id="auto-range-btn" class="auto-range-btn" title="검수 범위 조정" onclick="autoRangeOpen()">조정</button>'
            + (f' <a class="auto-policy-link" href="/policy/screen/{_e(view["screen_id"])}">이 화면의 규칙</a>' if view.get('screen_id') else '') + '</div>'
            f'<dialog class="auto-range-editor" id="auto-range-editor"><div class="s1-modal-inset">'
            f'<b class="auto-range-title">검수 범위 조정</b>'
            f'<p class="auto-hint">붉은 선 바깥(위쪽 선 위, 아래쪽 선 아래)은 비교하지 않아요. 상태바·주소창·키보드·하단 단추 줄이 끝나는 곳에 선을 끌어 맞춰 주세요.</p>'
            f'<div class="auto-range-stage"><img id="auto-range-img" alt="개발 화면"><div class="auto-range-line" id="auto-range-top"></div><div class="auto-range-line" id="auto-range-bottom"></div>'
            f'<div class="auto-range-shade" id="auto-range-shade-top"></div><div class="auto-range-shade" id="auto-range-shade-bottom"></div></div>'
            f'<form class="auto-range-form" onsubmit="return autoRangeSave(this,false)">'
            f'<label>위쪽 제외 <input type="number" name="top" min="0" step="1"> px</label>'
            f'<label>아래쪽 제외 <input type="number" name="bottom" min="0" step="1"> px</label>'
            f'<select name="actor"><option value="">담당자</option>{person_options}</select>'
            f'<button type="submit" class="primary">이 범위로 다시 검수</button>'
            f'<button type="button" onclick="autoRangeSave(this.form,true)">자동으로 되돌리기</button>'
            f'<button type="button" onclick="autoRangeClose()">닫기</button></form></div></dialog>')


def card_html(k, numbers, page_id, rnd):
    cat = candidate_category(k)
    kind_lbl = issue_categories.label(cat)
    color = issue_categories.color(cat)
    conf = f'<span class="sev">신뢰도 {k["confidence"]}%</span>' if k['confidence'] is not None else ''
    if k['issue_id']:
        n = numbers.get(k['issue_id'])
        foot = f'<div class="passed">✓ 지적 #{n}로 등록됨</div>' if n else '<div class="passed">✓ 지적으로 등록됨</div>'
        ex = ''
    else:
        foot = ''
        # 오른쪽 위 '제외' 단추 — 누르면 '제외' 칸으로, 다시 누르면 '수정필요'로 돌아온다
        off = k['status'] != 'open'
        ex = (f'<button type="button" class="auto-ex{" on" if off else ""}" '
              f'onclick="event.stopPropagation();autoStatus(\'{k["id"]}\', '
              f'\'{"open" if off else "excluded"}\')">{"제외됨" if off else "제외"}</button>')
    from_value = value_candidates.값후보인가(k)
    tags = f'<span class="tag">{_e(kind_lbl)}</span>' + ('<span class="tag val">값 대조</span>' if from_value else '')
    # 본문(무엇이 기준인지 · 지금 개발은 어떤지 · 개발이 볼 자리)은 card_view가 줄을 갈라 그린다.
    return (f'<div class="issue auto-card st-{k["status"]}{" registered" if k["issue_id"] else ""}" id="cand-{k["id"]}" data-cand="{k["id"]}" onclick="autoFocus(\'{k["id"]}\')">'
            f'{ex}<div class="ihead"><span class="pinno auto-no" style="background:{color}">{k["no"]}</span>{conf}<b>{_e(card_view.제목(k))}</b></div>'
            f'<div class="props">{tags}</div>'
            f'{card_view.body_html(k, page_id)}{foot}</div>')


def _design_box(k):
    """후보의 디자인 쪽 자리(시안 좌표). 없으면 None — 그때는 개발 쪽 자리를 그대로 쓴다."""
    try:
        b = json.loads(k.get('design_box') or '') if isinstance(k, dict) else ''
    except (TypeError, ValueError):
        return None
    if not isinstance(b, dict) or not b.get('w') or not b.get('h'):
        return None
    return [b.get('x') or 0, b.get('y') or 0, b['w'], b['h']]


def overlay_json(view):
    return json.dumps([{'id': k['id'], 'no': k['no'], 'status': k['status'], 'registered': bool(k['issue_id']),
                        'color': issue_categories.color(candidate_category(k)),
                        'box': [k['box_x'] or 0, k['box_y'] or 0, k['box_w'] or 0, k['box_h'] or 0],
                        'dbox': _design_box(k), 'issue': k['issue_id']} for k in view['candidates']], ensure_ascii=False)


CSS = '''
.auto-overlay{pointer-events:none}.auto-overlay .abox,.auto-overlay .abadge rect{pointer-events:auto}
.auto-overlay .abox{fill:none;stroke-width:3;stroke-dasharray:10 6;cursor:pointer}
.auto-overlay .abox.dim{opacity:.25}
.auto-overlay .abadge rect{stroke:var(--color-surface-default);stroke-width:2;cursor:pointer}
.auto-overlay .abadge text{fill:var(--color-surface-default);font:bold 24px sans-serif;text-anchor:middle;pointer-events:none}
.auto-overlay .abadge.dim{opacity:.35}
.auto-overlay .abadge.sel rect{stroke:var(--color-text-primary);stroke-width:4}
.auto-overlay .abox.sel{stroke-width:6;stroke-dasharray:none}
.auto-head{display:flex;flex-direction:column;gap:var(--spacing-4);margin:var(--spacing-4) 0 var(--spacing-10);font-size:var(--font-size-14)}
.auto-sum{font-weight:var(--font-weight-bold)}.auto-hint{color:var(--color-text-caption)}
.auto-group{margin-bottom:var(--spacing-10)}.auto-group summary{cursor:pointer;font-weight:var(--font-weight-bold);margin-bottom:var(--spacing-6)}
.auto-card{position:relative}.auto-card .auto-no{border-radius:var(--radius-4)}
.auto-card .auto-ex{position:absolute;top:10px;right:10px;margin:0;display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;height:var(--sizing-34);min-width:64px;padding:0 var(--spacing-16);font-family:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);line-height:1;color:var(--color-chip-line-label-default);background:var(--color-chip-line-bg-default);border:var(--border-width-1) solid var(--color-chip-line-border-default);border-radius:var(--radius-full);cursor:pointer;user-select:none}
.auto-card .auto-ex:hover{background:var(--color-chip-line-bg-hover)}
.auto-card .auto-ex.on{background:var(--color-chip-line-bg-selected);border-color:var(--color-chip-line-border-selected);color:var(--color-chip-line-label-selected)}
.auto-card .auto-ex.on:hover{background:var(--color-chip-line-bg-hover)}
.auto-card.st-excluded,.auto-card.st-variable{opacity:.7}
.auto-actions{display:flex;gap:var(--spacing-6);margin-top:var(--spacing-6);flex-wrap:wrap}


.auto-actions button.primary{background:var(--color-action-primary-default);border-color:var(--color-action-primary-default);color:var(--color-surface-default)}
.auto-msg{color:var(--color-text-tertiary)}
.auto-range{display:flex;align-items:center;gap:var(--spacing-8);margin:0 0 var(--spacing-8);padding:var(--spacing-6) var(--spacing-10);border:1px solid var(--color-border-subtle);border-radius:var(--radius-8);background:var(--color-bg-subtle);font-size:var(--font-size-12)}
.auto-range .auto-range-sum{flex:1;color:var(--color-text-tertiary)}

.auto-range-form button.primary{background:var(--color-action-primary-default);border-color:var(--color-action-primary-default);color:var(--color-surface-default)}
.auto-range-editor{width:min(900px,92vw);max-height:90vh;overflow:auto;margin:auto}
.auto-range-editor::backdrop{background:var(--color-overlay)}
.auto-range-title{display:block;margin:0 0 var(--spacing-8);font-size:var(--font-size-14)}
.cv-tools .auto-range-btn{margin-left:auto}
.auto-range-editor .auto-hint{margin:0 0 var(--spacing-8);font-size:var(--font-size-12);color:var(--color-text-caption)}
.auto-range-stage{position:relative;display:inline-block;max-width:100%;line-height:0;user-select:none;touch-action:none}
.auto-range-stage img{max-width:100%;max-height:60vh;display:block;border:1px solid var(--color-border-default)}
.auto-range-line{position:absolute;left:0;right:0;height:0;border-top:2px solid var(--color-text-danger);cursor:ns-resize;z-index:2}
.auto-range-line::after{content:"";position:absolute;left:0;right:0;top:-8px;height:18px}
.auto-range-shade{position:absolute;left:0;right:0;background:var(--color-status-error);opacity:.18;pointer-events:none;z-index:1}
.auto-range-form{display:flex;flex-wrap:wrap;gap:var(--spacing-8);align-items:center;margin-top:var(--spacing-8);font-size:var(--font-size-12)}
.auto-range-form input{width:70px}
.auto-wait.inline{position:static;flex-direction:row;justify-content:flex-start;gap:var(--spacing-8);margin:0 0 var(--spacing-10);font-size:var(--font-size-14)}
.auto-wait.inline .auto-spin{width:18px;height:18px;border-width:var(--border-width-2)}

.auto-wait{color:var(--color-text-tertiary);position:absolute;inset:0;margin:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:var(--spacing-14)}
.auto-spin{width:44px;height:44px;flex:none;border:4px solid var(--color-border-subtle);border-top-color:var(--color-action-primary-default);border-radius:50%;animation:auto-spin .8s linear infinite}
@keyframes auto-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.auto-spin{animation-duration:2.4s}}
'''

JS = r'''
(function(){
  var st=document.getElementById('auto-state');if(!st)return;
  var page=st.dataset.page,run=st.dataset.run;
  // ── 저장된 후보를 개발 화면 위에 그린다(점선 상자 + 네모 번호) ──
  var dataEl=document.getElementById('auto-data'),svg=document.querySelector('svg.auto-overlay');
  if(dataEl&&svg){
    var items=JSON.parse(dataEl.textContent||'[]'),k=Number(st.dataset.scale)||1,ns='http://www.w3.org/2000/svg';
    window.qaDesignRef={w:Number(st.dataset.dw)||0,h:Number(st.dataset.dh)||0};
    window.qaAlign={s:Number(st.dataset.as)||0,tx:Number(st.dataset.atx)||0,ty:Number(st.dataset.aty)||0,ctop:Number(st.dataset.actop)||0};
    window.qaDesignBox=window.qaDesignBox||{};
    items.forEach(function(c){
      if(c.dbox){window.qaDesignBox[c.id]=c.dbox;if(c.issue)window.qaDesignBox[c.issue]=c.dbox;}
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
  if(window.qaCompareIssue)window.qaCompareIssue(id);
}
function autoStatus(id,status){
  var st=document.getElementById('auto-state');
  fetch('/auto/'+st.dataset.page+'/candidate/'+id+'/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:status})})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
}
// ── 검수 범위 조정: 개발 화면 위에 선 두 개를 끌어 위·아래 제외 px를 정하고, 그 범위로 새 회차를 돌린다 ──
var __rangeEd=null;
function autoRangeOpen(){
  var box=document.getElementById('auto-range'),ed=document.getElementById('auto-range-editor');if(!box||!ed)return;
  if(!ed.open){if(ed.showModal)ed.showModal();else ed.setAttribute('open','');}
  var img=document.getElementById('auto-range-img'),H=Number(box.dataset.h)||0,form=ed.querySelector('form');
  var top=box.dataset.mtop!==''?Number(box.dataset.mtop):Number(box.dataset.top)||0,bottom=box.dataset.mbottom!==''?Number(box.dataset.mbottom):Number(box.dataset.bottom)||0;
  __rangeEd={box:box,ed:ed,img:img,H:H,form:form,top:top,bottom:bottom};
  function draw(){var e=__rangeEd,k=e.img.clientHeight/(e.H||1);
    document.getElementById('auto-range-top').style.top=(e.top*k)+'px';document.getElementById('auto-range-bottom').style.top=(e.img.clientHeight-e.bottom*k)+'px';
    var st=document.getElementById('auto-range-shade-top'),sb=document.getElementById('auto-range-shade-bottom');st.style.top='0';st.style.height=(e.top*k)+'px';sb.style.bottom='0';sb.style.height=(e.bottom*k)+'px';
    e.form.top.value=e.top;e.form.bottom.value=e.bottom;}
  __rangeEd.draw=draw;
  img.onload=draw;img.src=box.dataset.img;if(img.complete)draw();
  function drag(lineId,which){var line=document.getElementById(lineId);
    line.onpointerdown=function(ev){ev.preventDefault();line.setPointerCapture(ev.pointerId);
      line.onpointermove=function(mv){var e=__rangeEd,rect=e.img.getBoundingClientRect(),k=e.img.clientHeight/(e.H||1),y=Math.max(0,Math.min(rect.height,mv.clientY-rect.top));
        var px=Math.round(y/k);if(which==='top')e.top=Math.max(0,Math.min(px,e.H-e.bottom-8));else e.bottom=Math.max(0,Math.min(e.H-px,e.H-e.top-8));draw();};
      line.onpointerup=line.onpointercancel=function(){line.onpointermove=null;};};}
  drag('auto-range-top','top');drag('auto-range-bottom','bottom');
  form.top.oninput=function(){__rangeEd.top=Math.max(0,Number(this.value)||0);draw();};
  form.bottom.oninput=function(){__rangeEd.bottom=Math.max(0,Number(this.value)||0);draw();};
  window.addEventListener('resize',draw);
}
function autoRangeClose(){var ed=document.getElementById('auto-range-editor');if(!ed)return;if(ed.close)ed.close();else ed.removeAttribute('open');}
function autoRangeSave(form,reset){
  var st=document.getElementById('auto-state'),e=__rangeEd;if(!st||!e)return false;
  var body=reset?{run:st.dataset.run,top:null,bottom:null,actor:form.actor.value||''}:{run:st.dataset.run,top:e.top,bottom:e.bottom,actor:form.actor.value||''};
  fetch('/auto/'+st.dataset.page+'/range',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json();}).then(function(j){if(j.error){alert(j.error);return;}location.reload();});
  return false;
}
// ── '조정' 단추를 비교 보기 줄 오른쪽 끝으로 · 팝업은 어느 탭에서 눌러도 뜨도록 몸통으로 ──
(function(){
  function move(){
    var btn=document.getElementById('auto-range-btn'),tools=document.querySelector('.cv-tools');
    if(btn&&tools&&btn.parentNode!==tools)tools.appendChild(btn);
    var ed=document.getElementById('auto-range-editor');
    if(ed&&ed.parentNode!==document.body)document.body.appendChild(ed);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',move);else move();
})();
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
    """POST /auto/<page>/materials · /result · /fail · /retry · /range · /candidate/<id>/status · /candidate/<id>/register"""
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
        elif action == 'range' and len(parts) == 3:
            body = _body_json(handler)
            _json(handler, {'ok': True, 'autoRunId': auto.set_range(page_id, str(body.get('run') or ''), body.get('top'), body.get('bottom'), str(body.get('actor') or ''))})
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
