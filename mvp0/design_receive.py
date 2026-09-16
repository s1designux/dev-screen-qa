"""검수 화면 시안을 Figma 플러그인에서 바로 받기 (촬영 준비 단계를 거치지 않는 길).

플러그인(촬영 준비로 보내기)이 고른 프레임을 두고 먼저 묻는다: "이 프레임, 검수 화면이 이미 있어?"
 - 있으면 플러그인 단추가 '검수 시안 바꾸기'가 되고, 누르면 여기로 그림·요소·설정이 온다.
 - 시안은 새 판(intake_design 행)으로 쌓고 지우지 않는다. 페이지는 page_design_link로 최신 판을 가리킨다.
 - 핀은 개발 화면 기준이라 그대로. 자동 검수 후보는 새 시안으로 다시 돈다(auto_run이 시안별).
Figma 토큰이 필요 없다 — 플러그인이 river님 로그인 안에서 읽어 보낸다.
"""
import base64
import json
import re
import unicodedata
import uuid
from datetime import datetime

import figma_reader

PROVIDER = 'Figma 플러그인'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS page_design_link (
 page_id TEXT PRIMARY KEY REFERENCES inspection_page(uuid), design_id TEXT NOT NULL REFERENCES intake_design(id), linked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_design_event (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL, design_id TEXT NOT NULL, from_img TEXT, to_img TEXT NOT NULL,
 at TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS page_capture_event (
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL, run_id TEXT NOT NULL, from_img TEXT, to_img TEXT NOT NULL, at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS page_capture_event_no_update BEFORE UPDATE ON page_capture_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS page_capture_event_no_delete BEFORE DELETE ON page_capture_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS page_design_event_no_update BEFORE UPDATE ON page_design_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS page_design_event_no_delete BEFORE DELETE ON page_design_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now().isoformat(timespec='seconds')


def file_key_of(payload):
    """플러그인이 파일 열쇠를 못 주면(개인 플러그인) 파일 이름으로 대신 묶는다."""
    key = str(payload.get('fileKey') or '').strip()
    if re.fullmatch(r'[A-Za-z0-9]+', key):
        return key
    name = nfc(payload.get('fileName')).strip()
    return 'name:' + name if name else 'plugin'


def nfc(s):
    """한글 자모가 풀린 글자(NFD)와 모아진 글자(NFC)를 같은 것으로 본다.
    macOS를 거쳐 들어온 파일 이름은 풀려 있고 피그마가 주는 이름은 모아져 있어, 안 맞추면 같은 파일을 못 알아본다."""
    return unicodedata.normalize('NFC', str(s or ''))


def _norm(s):
    return re.sub(r'\s+', '', nfc(s)).lower()


class Receiver:
    def __init__(self, store):
        self.store = store

    def init(self):
        with self.store.connect() as c:
            c.executescript(SCHEMA)

    # ── 페이지 목록·짝 찾기 ─────────────────────────────────────────
    def pages(self, c):
        return c.execute('''SELECT p.uuid page, p.name page_name, s.uuid screen, s.human_key, s.name screen_name, s.platform
                            FROM inspection_page p JOIN screen s ON s.uuid=p.screen_id ORDER BY s.human_key, s.name, p.seq, p.rowid''').fetchall()

    @staticmethod
    def url_of(row):
        return f"/screen/{row['human_key'] or row['screen']}/page/{row['page']}"

    def frame_map(self, c):
        """(파일 열쇠, 프레임 id) → 페이지 uuid. 가장 최근에 붙인 것부터."""
        id_map = {}
        for r in c.execute('SELECT l.page_id, d.file_key, d.node_id FROM page_design_link l JOIN intake_design d ON d.id=l.design_id'):
            id_map.setdefault((nfc(r['file_key']), r['node_id']), r['page_id'])
        for sql in ('SELECT i.page_id, d.file_key, d.node_id FROM intake_item i JOIN intake_design d ON d.id=i.design_id WHERE i.page_id IS NOT NULL',
                    'SELECT dc.page_id, d.file_key, d.node_id FROM design_case dc JOIN intake_design d ON d.id=dc.design_id WHERE dc.page_id IS NOT NULL'):
            try:
                for r in c.execute(sql):
                    id_map.setdefault((nfc(r['file_key']), r['node_id']), r['page_id'])
            except Exception:  # 접수 표가 없는 옛 DB
                pass
        return id_map

    def screen_for_frame(self, c, payload):
        """검수기 플러그인이 보낸 (파일 열쇠, 프레임 id)로 포털의 화면을 찾는다. 없으면 None.
        프레임 id로 못 찾으면 프레임 이름이 꼭 하나만 맞을 때에 한해 그것으로 본다."""
        key = file_key_of(payload)
        node = str(payload.get('nodeId') or payload.get('frameId') or '')
        rows = [dict(r) for r in self.pages(c)]
        page = self.frame_map(c).get((key, node))
        row = next((r for r in rows if r['page'] == page), None) if page else None
        if not row:
            # 프레임 id로 못 찾으면 이름으로. 검수 페이지 이름(상태명)과 화면 이름 둘 다 보되,
            # **꼭 하나만** 맞을 때만 인정한다(엉뚱한 화면에 규칙을 쌓지 않게).
            want = _norm(payload.get('frameName') or payload.get('name'))
            for field in ('page_name', 'screen_name'):
                same = [r for r in rows if _norm(r[field]) == want]
                if len(same) == 1:
                    return same[0]
        return row

    def frames_status(self, payload):
        """플러그인이 고른 프레임마다 '검수 화면이 있는지'. id로 정확히 맞으면 how='id', 이름만 같으면 how='name'."""
        key = file_key_of(payload)
        with self.store.connect() as c:
            rows = [dict(r) for r in self.pages(c)]
            by_page = {r['page']: r for r in rows}
            id_map = self.frame_map(c)  # 프레임 id → 페이지 (가장 최근에 붙인 것부터)
        out = []
        for f in payload.get('frames') or []:
            node = str(f.get('id') or '')
            match = None
            page = id_map.get((key, node))
            if page and page in by_page:
                match = dict(by_page[page], how='id')
            else:
                same = [r for r in rows if _norm(r['page_name']) == _norm(f.get('name'))]
                if len(same) == 1:
                    match = dict(same[0], how='name')
            out.append({'id': node, 'name': f.get('name'), 'match': ({'page': match['page'], 'label': f"{match['screen_name']} › {match['page_name']}", 'how': match['how'], 'url': self.url_of(match)} if match else None)})
        options = [{'page': r['page'], 'label': f"{r['screen_name']} › {r['page_name']}", 'url': self.url_of(r)} for r in rows]
        return {'frames': out, 'options': options}

    # ── 받기 ─────────────────────────────────────────────────────
    def receive(self, payload):
        """{fileKey|fileName, page, frame:{id,name,width,height,png(base64), elements, policy}} → 새 시안 판 + 페이지 연결."""
        key = file_key_of(payload)
        page_id = str(payload.get('page') or '')
        frame = payload.get('frame') or {}
        node = str(frame.get('id') or '')
        if not page_id or not node:
            raise ValueError('어느 검수 화면에 붙일지와 프레임이 있어야 해요.')
        png = frame.get('png')
        try:
            data = base64.b64decode(png) if isinstance(png, str) else bytes(png or b'')
        except (ValueError, TypeError):
            raise ValueError('그림을 읽지 못했습니다.')
        if not data.startswith(b'\x89PNG'):
            raise ValueError('PNG 그림이 아닙니다.')
        settings = {'policy': frame['policy']} if isinstance(frame.get('policy'), dict) else None
        with self.store.connect() as c:
            page = c.execute('SELECT p.*, s.human_key FROM inspection_page p JOIN screen s ON s.uuid=p.screen_id WHERE p.uuid=?', (page_id,)).fetchone()
            if not page:
                raise ValueError('검수 화면을 찾지 못했습니다.')
        source_url = figma_reader.link_for(key, node) if not key.startswith('name:') and key != 'plugin' else ''
        design = self.store.add_design(key, node, str(frame.get('name') or page['name']), source_url, node, data, None, provider=PROVIDER, qa_settings=settings)
        with self.store.connect() as c:
            fname = c.execute('SELECT a.filename FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?', (design,)).fetchone()['filename']
            els = frame.get('elements')
            if isinstance(els, list):
                fr = {'id': node, 'name': frame.get('name') or '', 'width': frame.get('width'), 'height': frame.get('height')}
                c.execute('INSERT OR REPLACE INTO design_elements VALUES (?,?,?,?,?)', (design, now(), None, json.dumps(fr, ensure_ascii=False), json.dumps(els, ensure_ascii=False)))
            c.execute('INSERT OR REPLACE INTO page_design_link VALUES (?,?,?)', (page_id, design, now()))
            c.execute('INSERT INTO page_design_event VALUES (?,?,?,?,?,?,?,?)', (uid(), page_id, design, page['design_img'], fname, now(), PROVIDER, f"플러그인에서 시안 새 판 받음: {frame.get('name') or ''}"))
            c.execute('UPDATE inspection_page SET design_img=? WHERE uuid=?', (fname, page_id))
        return {'ok': True, 'page': page_id, 'design': design, 'url': f"/screen/{page['human_key'] or page['screen_id']}/page/{page_id}"}


    # ── 촬영기가 바로 넣은 페이지(접수함 연결 없음)의 개발 화면 바꾸기 ─────────
    def sibling_captures(self, page_id):
        """같은 화면 묶음(같은 촬영 때 찍은 상태들)의 개발 사진. 팝업에서 고를 후보."""
        with self.store.connect() as c:
            sid = c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?', (page_id,)).fetchone()
            if not sid:
                return []
            return c.execute('''SELECT r.uuid run_id, r.page_id, p.name page_name, r.round, r.dev_img filename, r.dev_img_w width, r.dev_img_h height
                                FROM inspection_run r JOIN inspection_page p ON p.uuid=r.page_id
                                WHERE p.screen_id=? AND r.dev_img IS NOT NULL ORDER BY p.seq, r.round''', (sid['screen_id'],)).fetchall()

    def replace_capture(self, page_id, filename):
        """이 페이지의 최신 차수 개발 이미지를 같은 화면 묶음의 다른 사진으로 바꾼다(지적이 없을 때만). 파일은 지우지 않고 이력을 남긴다."""
        caps = {r['filename']: r for r in self.sibling_captures(page_id)}
        cap = caps.get(filename)
        if not cap:
            raise ValueError('같은 화면에서 찍은 사진 중에서 골라 주세요.')
        with self.store.connect() as c:
            if c.execute('SELECT 1 FROM inspection_issue WHERE page_id=? LIMIT 1', (page_id,)).fetchone():
                raise ValueError('수정필요 항목이 있는 화면은 새 차수에서 바꿉니다.')
            run = c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1', (page_id,)).fetchone()
            if not run:
                raise ValueError('검수 차수가 없습니다.')
            if run['dev_img'] == filename:
                return
            c.execute('UPDATE inspection_run SET dev_img=?,dev_img_w=?,dev_img_h=?,coord_ref_w=?,coord_ref_h=? WHERE uuid=?',
                      (filename, cap['width'], cap['height'], cap['width'], cap['height'], run['uuid']))
            c.execute('INSERT INTO page_capture_event VALUES (?,?,?,?,?,?,?)', (uid(), page_id, run['uuid'], run['dev_img'], filename, now(), f"같은 화면의 사진으로 바꿈: {cap['page_name']}"))


# ── HTTP (플러그인 창에서 오므로 CORS 허용 · 내 PC 안에서만) ─────────────
def _json(handler, obj, code=200):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def options(handler, path):
    if not path.startswith('/api/'):
        return False
    handler.send_response(204)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
    handler.end_headers()
    return True


def post(handler, store, path):
    """POST /api/frames {fileKey|fileName, frames:[{id,name}]} · POST /api/design {fileKey|fileName, page, frame:{…}}"""
    if path not in ('/api/frames', '/api/design'):
        return False
    length = int(handler.headers.get('Content-Length', 0) or 0)
    if length > 60 * 1024 * 1024:
        _json(handler, {'error': '보낸 자료가 너무 커요(60MB 넘음).'}, 413)
        return True
    raw = handler.rfile.read(length) if length else b''
    try:
        body = json.loads(raw.decode('utf-8')) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        _json(handler, {'error': '자료 모양이 맞지 않습니다.'}, 400)
        return True
    r = Receiver(store)
    try:
        _json(handler, r.frames_status(body) if path == '/api/frames' else r.receive(body))
    except ValueError as e:
        _json(handler, {'error': str(e)}, 200)
    return True
