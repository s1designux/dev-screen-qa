"""촬영 접수·디자인 연결. 원본 파일과 이벤트는 append-only, 화면 출력과 분리."""
import hashlib
import json
import struct
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path

import db


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def png_size(data):
    if len(data) > 25 * 1024 * 1024 or data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('읽을 수 있는 PNG 파일만 가져올 수 있습니다. (한 장 최대 25MB)')
    pos, size, ended, has_data = 8, None, False, False
    compressed = bytearray()
    header = None
    while pos + 12 <= len(data):
        n = int.from_bytes(data[pos:pos+4], 'big')
        kind, payload = data[pos+4:pos+8], data[pos+8:pos+8+n]
        if pos + 12 + n > len(data):
            break
        crc = int.from_bytes(data[pos+8+n:pos+12+n], 'big')
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError('PNG 파일이 손상되었습니다.')
        if size is None:
            if kind != b'IHDR' or n != 13:
                break
            size = struct.unpack('>II', payload[:8])
            header = payload
        has_data |= kind == b'IDAT'
        if kind == b'IDAT':
            compressed.extend(payload)
        pos += n + 12
        if kind == b'IEND':
            ended = True
            break
    if not size or not ended or not has_data or min(size) < 1 or max(size) > 20000:
        raise ValueError('PNG 파일이 손상되었거나 크기가 너무 큽니다.')
    w,h = size
    depth,color,compression,filter_method,interlace = header[8:13]
    channels = {0:1,2:3,3:1,4:2,6:4}.get(color)
    allowed_depth = {0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}
    if not channels or depth not in allowed_depth[color] or compression or filter_method or interlace not in (0,1) or w*h > 40000000:
        raise ValueError('PNG 형식 또는 크기를 확인해 주세요.')
    passes = [(0,0,1,1)] if interlace==0 else [(0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
    strides=[]
    for x,y,dx,dy in passes:
        pw,ph=max(0,(w-x+dx-1)//dx),max(0,(h-y+dy-1)//dy)
        if pw and ph:
            strides.append((1+(pw*channels*depth+7)//8,ph))
    expected=sum(stride*rows for stride,rows in strides)
    if expected>160*1024*1024:
        raise ValueError('PNG를 펼친 크기가 너무 큽니다.')
    try:
        decoder=zlib.decompressobj()
        raw=decoder.decompress(bytes(compressed),expected+1)
        if len(raw)!=expected or not decoder.eof or decoder.unused_data:
            raise ValueError()
        offset=0
        for stride,rows in strides:
            if any(raw[offset+i*stride]>4 for i in range(rows)):
                raise ValueError()
            offset+=stride*rows
    except (ValueError,zlib.error):
        raise ValueError('PNG 이미지 데이터가 손상되었습니다.') from None
    return size


SCHEMA = '''
CREATE TABLE IF NOT EXISTS intake_batch (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES project(uuid),
 created_at TEXT NOT NULL, metadata TEXT NOT NULL, fingerprint TEXT NOT NULL,
 platform TEXT NOT NULL, UNIQUE(project_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS intake_asset (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, digest TEXT NOT NULL,
 width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intake_item (
 id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES intake_batch(id), seq INTEGER NOT NULL,
 source_name TEXT NOT NULL, screen_name TEXT NOT NULL, state_name TEXT NOT NULL,
 asset_id TEXT REFERENCES intake_asset(id), error TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'unlinked' CHECK(status IN ('unlinked','pending','confirmed','held','excluded')),
 reason TEXT NOT NULL DEFAULT '', design_id TEXT REFERENCES intake_design(id),
 page_id TEXT REFERENCES inspection_page(uuid), revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS intake_design (
 id TEXT PRIMARY KEY, file_key TEXT NOT NULL, node_id TEXT NOT NULL, name TEXT NOT NULL,
 source_url TEXT NOT NULL, scope_node TEXT NOT NULL, asset_id TEXT NOT NULL REFERENCES intake_asset(id),
 fetched_at TEXT NOT NULL, source_version TEXT, provider TEXT NOT NULL,
 qa_settings TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS intake_event (
 id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES intake_batch(id), item_id TEXT,
 action TEXT NOT NULL, detail TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS intake_event_no_update BEFORE UPDATE ON intake_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS intake_event_no_delete BEFORE DELETE ON intake_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''


class Store:
    def __init__(self, database, uploads):
        self.database, self.uploads = Path(database), Path(uploads)

    def connect(self):
        return db.connect(self.database)

    def init(self):
        self.uploads.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            db.init_schema(c)
            c.executescript(SCHEMA)
            if 'qa_settings' not in [r[1] for r in c.execute('PRAGMA table_info(intake_design)')]:
                c.execute("ALTER TABLE intake_design ADD COLUMN qa_settings TEXT NOT NULL DEFAULT ''")  # 검수기에서 사람이 정한 설정(JSON). 예전 DB 보강.
            from design_plan import SCHEMA as PLAN_SCHEMA
            c.executescript(PLAN_SCHEMA)
            from auto_inspect import SCHEMA as AUTO_SCHEMA  # 자동 검수 후보(사람이 확정하기 전 단계)
            c.executescript(AUTO_SCHEMA)
            from design_receive import SCHEMA as RECEIVE_SCHEMA  # 플러그인에서 바로 받은 시안 ↔ 페이지 연결
            c.executescript(RECEIVE_SCHEMA)
            from policy import SCHEMA as POLICY_SCHEMA  # 검수 정책 값의 층(시스템·서비스·화면·요소)
            c.executescript(POLICY_SCHEMA)
            from rule_log import SCHEMA as RULELOG_SCHEMA  # 사람의 판정 ↔ 그렇게 만든 규칙 잇기
            c.executescript(RULELOG_SCHEMA)
        import auto_inspect
        auto_inspect.repair(self.database)  # 옛 모양의 자동 검수 표를 고친다(외래키를 끈 별도 연결에서)

    def event(self, c, batch, item, action, detail, actor='로컬 사용자'):
        c.execute('INSERT INTO intake_event VALUES (?,?,?,?,?,?,?)',
                  (uid(), batch, item, action, json.dumps(detail, ensure_ascii=False), actor, now()))

    def asset(self, c, data):
        w, h = png_size(data)
        key = uid()
        filename = key + '.png'
        with (self.uploads / filename).open('xb') as f:
            f.write(data)
        c.execute('INSERT INTO intake_asset VALUES (?,?,?,?,?,?)',
                  (key, filename, hashlib.sha256(data).hexdigest(), w, h, now()))
        return key

    def projects(self):
        with self.connect() as c:
            return c.execute('SELECT * FROM project ORDER BY name').fetchall()

    def import_files(self, files, project_id='', project_name='', platform='android'):
        # filename is a label only: never use manifest paths to read the filesystem.
        clean = {}
        for name, data in files:
            name = Path(name.replace('\\', '/')).name
            if name in clean:
                raise ValueError('같은 이름의 파일이 두 개 있습니다. 폴더 하나씩 가져와 주세요.')
            if name.lower().endswith('.png') or name == '찍은목록.json':
                clean[name] = data
        if not clean:
            raise ValueError('PNG 또는 찍은목록.json을 선택해 주세요.')
        try:
            metadata = json.loads(clean.get('찍은목록.json', b'{}').decode('utf-8-sig'))
            if not isinstance(metadata, dict):
                raise ValueError()
            rows = metadata.get('촬영본', metadata.get('찍힌것', []))
            if not isinstance(rows, list) or any(not isinstance(r, dict) or not isinstance(r.get('파일'), str) for r in rows):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise ValueError('찍은목록.json 형식을 확인해 주세요. 접수는 아직 저장하지 않았습니다.')
        listed = {Path(r['파일'].replace('\\', '/')).name: r for r in rows}
        if len(listed) != len(rows):
            raise ValueError('목록에 같은 파일 이름이 반복되어 있습니다.')
        for name in clean:
            if name.lower().endswith('.png') and name not in listed:
                listed[name] = {}
        if not listed:
            raise ValueError('접수할 촬영본이 없습니다.')
        if len(listed) > 100:
            raise ValueError('한 번에 최대 100장까지 가져올 수 있습니다.')
        fingerprint = hashlib.sha256(json.dumps([(n, hashlib.sha256(d).hexdigest()) for n,d in sorted(clean.items())]).encode()).hexdigest()
        with self.connect() as c:
            if project_id:
                if not c.execute('SELECT 1 FROM project WHERE uuid=?', (project_id,)).fetchone():
                    raise ValueError('프로젝트를 다시 선택해 주세요.')
            else:
                project_name = project_name.strip()
                if not project_name or len(project_name) > 120:
                    raise ValueError('프로젝트 이름을 입력해 주세요. (120자 이내)')
                old = c.execute('SELECT uuid FROM project WHERE name=?', (project_name,)).fetchone()
                project_id = old['uuid'] if old else uid()
                if not old:
                    c.execute('INSERT INTO project VALUES (?,?)', (project_id, project_name))
            existing = c.execute('SELECT id FROM intake_batch WHERE project_id=? AND fingerprint=?', (project_id, fingerprint)).fetchone()
            if existing:
                self.event(c, existing['id'], None, '중복 접수', {'결과':'기존 접수 유지'})
                return existing['id'], True
            prior = []
            for name, row in listed.items():
                if name not in clean:
                    continue
                match = c.execute('''SELECT i.batch_id FROM intake_item i
                    JOIN intake_batch b ON b.id=i.batch_id JOIN intake_asset a ON a.id=i.asset_id
                    WHERE b.project_id=? AND i.source_name=? AND a.digest=? LIMIT 1''',
                    (project_id, name, hashlib.sha256(clean[name]).hexdigest())).fetchone()
                if match:
                    prior.append(match['batch_id'])
            if prior:
                if len(prior)==len(listed) and len(set(prior))==1:
                    self.event(c,prior[0],None,'중복 촬영본 접수',{'결과':'기존 접수 유지'})
                    return prior[0],True
                raise ValueError('이미 접수된 촬영본이 포함되어 있습니다. 접수함에서 이어서 작업하거나 중복 사진을 빼고 새 사진만 선택해 주세요. 이번 접수는 저장하지 않았습니다.')
            batch = uid()
            if platform not in ('android','ios','web','mobile-web'):
                raise ValueError('플랫폼을 확인해 주세요.')
            c.execute('INSERT INTO intake_batch VALUES (?,?,?,?,?,?)',
                      (batch, project_id, now(), json.dumps(metadata, ensure_ascii=False), fingerprint, platform))
            for seq,(name,r) in enumerate(listed.items(),1):
                stem = Path(name).stem.split('@',1)
                screen = str(r.get('화면이름') or stem[0]).strip()[:120]
                state = str(r.get('상태') or (stem[1] if len(stem)>1 else '기본')).strip()[:120]
                key, error = None, ''
                if name not in clean:
                    error = '목록에 있지만 PNG 파일이 없습니다. 원본 폴더와 함께 다시 접수해 주세요.'
                else:
                    try:
                        key = self.asset(c, clean[name])
                    except ValueError as e:
                        error = str(e)
                item = uid()
                c.execute('INSERT INTO intake_item (id,batch_id,seq,source_name,screen_name,state_name,asset_id,error) VALUES (?,?,?,?,?,?,?,?)',
                          (item,batch,seq,name,screen,state,key,error))
            self.event(c,batch,None,'접수 저장',{'파일 수':len(listed)})
            return batch, False

    def batches(self):
        with self.connect() as c:
            return c.execute('''SELECT b.*,p.name project_name,COUNT(i.id) total,
              SUM(i.status='confirmed') confirmed,SUM(i.status='excluded') excluded
              FROM intake_batch b JOIN project p ON p.uuid=b.project_id JOIN intake_item i ON i.batch_id=b.id
              GROUP BY b.id ORDER BY b.created_at DESC,b.rowid DESC''').fetchall()

    def batch(self, batch):
        with self.connect() as c:
            b = c.execute('SELECT b.*,p.name project_name FROM intake_batch b JOIN project p ON p.uuid=b.project_id WHERE b.id=?',(batch,)).fetchone()
            if not b:
                raise ValueError('접수 기록을 찾을 수 없습니다.')
            items = c.execute('''SELECT i.*,a.filename,a.width,a.height,d.name design_name,d.source_url,
              d.fetched_at,da.filename design_file FROM intake_item i
              LEFT JOIN intake_asset a ON a.id=i.asset_id LEFT JOIN intake_design d ON d.id=i.design_id
              LEFT JOIN intake_asset da ON da.id=d.asset_id WHERE batch_id=? ORDER BY seq''',(batch,)).fetchall()
            events = c.execute('SELECT * FROM intake_event WHERE batch_id=? ORDER BY rowid DESC LIMIT 100',(batch,)).fetchall()
            return b, items, events

    def edit_item(self, item, revision, screen, state, status, reason):
        if status not in ('include','held','excluded'):
            raise ValueError('대상 상태를 확인해 주세요.')
        screen, state, reason = screen.strip(), state.strip(), reason.strip()
        if not screen or not state or len(screen)>120 or len(state)>120 or len(reason)>1000:
            raise ValueError('화면 이름과 상태는 120자 이내로 입력해 주세요.')
        if status in ('held','excluded') and not reason:
            raise ValueError('보류·제외 사유를 입력해 주세요.')
        with self.connect() as c:
            r = c.execute('SELECT * FROM intake_item WHERE id=?',(item,)).fetchone()
            self.check(r,revision)
            if r['page_id']:
                raise ValueError('검수를 시작한 항목의 이름·대상 변경은 이번 단계에서 제공하지 않습니다.')
            next_status = ('pending' if r['design_id'] else 'unlinked') if status=='include' else status
            c.execute('UPDATE intake_item SET screen_name=?,state_name=?,status=?,reason=?,revision=revision+1 WHERE id=?',
                      (screen,state,next_status,reason,item))
            self.event(c,r['batch_id'],item,'이름·대상 변경',{'이전':dict(r),'화면':screen,'상태':state,'대상':next_status,'사유':reason})

    @staticmethod
    def check(r,revision):
        if not r:
            raise ValueError('촬영본을 찾을 수 없습니다.')
        if r['revision'] != int(revision):
            raise ValueError('다른 창에서 변경되었습니다. 새로고침 후 다시 확인해 주세요.')

    def add_design(self,file_key,node_id,name,source_url,scope_node,data,version=None,provider='Figma REST',qa_settings=None):
        with self.connect() as c:
            asset = self.asset(c,data)
            key = uid()
            c.execute('INSERT INTO intake_design VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                      (key,file_key,node_id,name,source_url,scope_node,asset,now(),version,provider,
                       json.dumps(qa_settings,ensure_ascii=False) if qa_settings else ''))
            return key

    def designs(self, file_key=None, node_id=None):
        with self.connect() as c:
            rows = c.execute('SELECT d.*,a.filename FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id ORDER BY d.rowid DESC').fetchall()
            seen, out = set(), []
            for r in rows:
                if file_key and (r['file_key']!=file_key or node_id not in (r['scope_node'],r['node_id'])):
                    continue
                key = (r['file_key'],r['node_id'])
                if key not in seen:
                    out.append(r)
                    seen.add(key)
            return out

    def select_design(self,item,revision,design, recommendation=None):
        with self.connect() as c:
            r=c.execute('SELECT * FROM intake_item WHERE id=?',(item,)).fetchone()
            self.check(r,revision)
            if recommendation is not None and (r['status'] != 'unlinked' or r['design_id']):
                raise ValueError('이미 선택한 시안은 추천으로 덮어쓰지 않습니다.')
            if r['status'] in ('held','excluded') or not r['asset_id']:
                raise ValueError('연결 대상인 정상 촬영본만 디자인을 선택할 수 있습니다.')
            if r['page_id'] and c.execute('SELECT 1 FROM inspection_issue WHERE page_id=? LIMIT 1',(r['page_id'],)).fetchone():
                raise ValueError('지적이 있는 페이지의 디자인 교체는 이번 단계에서 제공하지 않습니다. 기존 검수 근거를 보존합니다.')
            if not c.execute('SELECT 1 FROM intake_design WHERE id=?',(design,)).fetchone():
                raise ValueError('디자인을 다시 선택해 주세요.')
            c.execute("UPDATE intake_item SET design_id=?,status='pending',revision=revision+1 WHERE id=?",(design,item))
            self.event(c,r['batch_id'],item,'추천 연결' if recommendation is not None else '디자인 선택',{'이전 디자인':r['design_id'],'새 디자인':design, '추천 사유': recommendation})

    def captures_of_batch(self,batch):
        """같은 접수함에서 찍은 사진들(개발 화면 바꾸기 팝업용). 보류·제외된 것도 보여 주되 표시만 한다."""
        with self.connect() as c:
            return c.execute('''SELECT i.id,i.seq,i.screen_name,i.state_name,i.status,a.filename,a.width,a.height FROM intake_item i
                JOIN intake_asset a ON a.id=i.asset_id WHERE i.batch_id=? ORDER BY i.seq''',(batch,)).fetchall()

    def replace_capture(self,item,revision,capture):
        """검수 중인 페이지의 개발 화면을 같은 접수함의 다른 사진으로 바꾼다(지적이 없을 때만 — 있으면 새 차수).
        사진 파일은 지우지 않고 그 차수(run)의 개발 이미지만 바꾸며 이력을 남긴다."""
        with self.connect() as c:
            r=c.execute('SELECT * FROM intake_item WHERE id=?',(item,)).fetchone()
            self.check(r,revision)
            if not r['page_id']:
                raise ValueError('검수가 시작된 페이지에서만 개발 화면을 바꿀 수 있어요.')
            if c.execute('SELECT 1 FROM inspection_issue WHERE page_id=? LIMIT 1',(r['page_id'],)).fetchone():
                raise ValueError('지적이 등록된 화면의 개발 화면 교체는 새 차수에서 진행합니다.')
            cap=c.execute('SELECT i.id,a.* FROM intake_item i JOIN intake_asset a ON a.id=i.asset_id WHERE i.id=? AND i.batch_id=?',(capture,r['batch_id'])).fetchone()
            if not cap:
                raise ValueError('이 접수함에서 찍은 사진을 골라 주세요.')
            run=c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1',(r['page_id'],)).fetchone()
            if not run:
                raise ValueError('검수 차수가 없어요.')
            if run['dev_img']==cap['filename']:
                return
            c.execute('UPDATE inspection_run SET dev_img=?,dev_img_w=?,dev_img_h=?,coord_ref_w=?,coord_ref_h=? WHERE uuid=?',
                      (cap['filename'],cap['width'],cap['height'],cap['width'],cap['height'],run['uuid']))
            c.execute('UPDATE intake_item SET revision=revision+1 WHERE id=?',(item,))
            self.event(c,r['batch_id'],item,'개발 화면 변경',{'차수':run['round'],'이전':run['dev_img'],'새 사진':cap['filename'],'촬영본':capture})

    def recommendation(self,item):
        with self.connect() as c:
            event=c.execute("SELECT action,detail FROM intake_event WHERE item_id=? AND action IN ('추천 연결','디자인 선택') ORDER BY rowid DESC LIMIT 1",(item,)).fetchone()
            return json.loads(event['detail']).get('추천 사유','') if event and event['action']=='추천 연결' else ''

    def confirm(self,item,revision):
        with self.connect() as c:
            r=c.execute('SELECT * FROM intake_item WHERE id=?',(item,)).fetchone()
            self.check(r,revision)
            if r['status'] != 'pending' or not r['asset_id'] or not r['design_id']:
                raise ValueError('먼저 디자인을 선택하고 두 이미지를 확인해 주세요.')
            if r['page_id']:
                if c.execute('SELECT 1 FROM inspection_issue WHERE page_id=? LIMIT 1',(r['page_id'],)).fetchone():
                    raise ValueError('지적이 생겨 디자인 교체를 중단했습니다. 기존 검수 근거를 보존합니다.')
                design=c.execute('SELECT a.filename FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?',(r['design_id'],)).fetchone()
                c.execute('UPDATE inspection_page SET design_img=? WHERE uuid=?',(design['filename'],r['page_id']))
            c.execute("UPDATE intake_item SET status='confirmed',revision=revision+1 WHERE id=?",(item,))
            self.event(c,r['batch_id'],item,'사람이 짝 확인',{'디자인':r['design_id'],'촬영본':r['asset_id']})

    def start(self,batch):
        with self.connect() as c:
            b=c.execute('SELECT * FROM intake_batch WHERE id=?',(batch,)).fetchone()
            if not b:
                raise ValueError('접수 기록을 찾을 수 없습니다.')
            rows=c.execute("SELECT * FROM intake_item WHERE batch_id=? AND status='confirmed' ORDER BY seq",(batch,)).fetchall()
            if not rows:
                raise ValueError('짝을 확인한 촬영본이 아직 없습니다.')
            for r in rows:
                if r['page_id']:
                    continue
                # A batch's screen is isolated from past inspections / later rounds.
                old=c.execute('''SELECT p.screen_id FROM intake_item i JOIN inspection_page p ON p.uuid=i.page_id
                  WHERE i.batch_id=? AND i.screen_name=? LIMIT 1''',(batch,r['screen_name'])).fetchone()
                screen=old['screen_id'] if old else uid()
                if not old:
                    # Existing schema requires text. Empty means official label not assigned.
                    c.execute('INSERT INTO screen(uuid,project_id,human_key,name,platform,states) VALUES (?,?,?,?,?,?)',
                              (screen,b['project_id'],'',r['screen_name'],b['platform'],'[]'))
                dev=c.execute('SELECT * FROM intake_asset WHERE id=?',(r['asset_id'],)).fetchone()
                design=c.execute('SELECT a.* FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?',(r['design_id'],)).fetchone()
                page=uid()
                seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 n FROM inspection_page WHERE screen_id=?',(screen,)).fetchone()['n']
                c.execute('INSERT INTO inspection_page(uuid,screen_id,seq,name,design_img) VALUES (?,?,?,?,?)',
                          (page,screen,seq,r['state_name'],design['filename']))
                c.execute('INSERT INTO inspection_run(uuid,screen_id,page_id,round,created_at,dev_img,dev_img_w,dev_img_h,coord_ref_w,coord_ref_h) VALUES (?,?,?,?,?,?,?,?,?,?)',
                          (uid(),screen,page,1,now(),dev['filename'],dev['width'],dev['height'],dev['width'],dev['height']))
                c.execute('UPDATE intake_item SET page_id=?,revision=revision+1 WHERE id=?',(page,r['id']))
                states=[x['name'] for x in c.execute('SELECT name FROM inspection_page WHERE screen_id=? ORDER BY seq',(screen,))]
                c.execute('UPDATE screen SET states=? WHERE uuid=?',(json.dumps(states,ensure_ascii=False),screen))
                self.event(c,batch,r['id'],'검수 준비 완료',{'페이지':page,'차수':1,'판정':'미검수'})
            first=c.execute('SELECT page_id FROM intake_item WHERE id=?',(rows[0]['id'],)).fetchone()['page_id']
            screen=c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?',(first,)).fetchone()['screen_id']
            return f'/screen/{screen}/page/{first}'

    LATEST_SQL = """SELECT d.id orig_id,d.fetched_at orig_at,n.id new_id,n.name,n.fetched_at,n.source_url,
        a.filename design_file FROM intake_design d
        JOIN intake_design n ON n.rowid=(SELECT x.rowid FROM intake_design x
          WHERE x.file_key=d.file_key AND x.node_id=d.node_id ORDER BY x.rowid DESC LIMIT 1)
        JOIN intake_asset a ON a.id=n.asset_id WHERE d.id=?"""

    def latest_design(self,design):
        """같은 Figma 프레임(file_key+node_id)의 가장 최근 판. 옛 판은 지우지 않고 그대로 둔다."""
        if not design:
            return None
        with self.connect() as c:
            return c.execute(self.LATEST_SQL,(design,)).fetchone()

    def page_design(self,page):
        """검수 페이지가 지금 보아야 할 시안. 처음 붙인 판이 아니라 같은 프레임의 최신 판을 따라간다.
        받아온 뒤 새 판이 생겼으면 changed=True (화면에 '시안 새 판'으로 표시)."""
        with self.connect() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='intake_design'").fetchone():
                return None
            design=None
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='page_design_link'").fetchone():
                design=c.execute('SELECT design_id FROM page_design_link WHERE page_id=?',(page,)).fetchone()  # 플러그인에서 바로 받은 시안이 우선
            if not design:
                design=c.execute('SELECT design_id FROM intake_item WHERE page_id=?',(page,)).fetchone()
            if not design and c.execute("SELECT 1 FROM sqlite_master WHERE name='design_case'").fetchone():
                design=c.execute('SELECT design_id FROM design_case WHERE page_id=?',(page,)).fetchone()
            if not design or not design['design_id']:
                return None
            row=c.execute(self.LATEST_SQL,(design['design_id'],)).fetchone()
        if not row:
            return None
        out=dict(row)
        out['changed']=row['new_id']!=row['orig_id']
        return out

    def page_link(self,page):
        with self.connect() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='intake_item'").fetchone():
                return None  # Read-only legacy/static rendering before intake initialization.
            return c.execute('''SELECT i.*,d.source_url,d.name design_name,d.fetched_at FROM intake_item i
                LEFT JOIN intake_design d ON d.id=i.design_id WHERE i.page_id=?''',(page,)).fetchone()

    def screen_groups(self):
        """未확인 자료도 화면 목록에서 찾는다. 준비 상태와 검수 판정은 분리."""
        with self.connect() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='intake_item'").fetchone():
                return []
            rows=c.execute('''SELECT i.*,b.project_id,b.platform,b.created_at,p.name project_name,
                ip.screen_id FROM intake_item i JOIN intake_batch b ON b.id=i.batch_id
                JOIN project p ON p.uuid=b.project_id LEFT JOIN inspection_page ip ON ip.uuid=i.page_id
                ORDER BY b.created_at DESC,b.rowid DESC,i.seq''').fetchall()
            grouped={}
            for r in rows:
                if r['status']=='excluded':
                    continue
                key=(r['batch_id'],r['screen_name'])
                if key not in grouped:
                    grouped[key]={'batch_id':r['batch_id'],'item_id':r['id'],'name':r['screen_name'],
                        'project_name':r['project_name'],'project_id':r['project_id'],'platform':r['platform'],
                        'created_at':r['created_at'],'items':[],'screen_ids':set()}
                grouped[key]['items'].append(dict(r))
                if r['screen_id']:
                    grouped[key]['screen_ids'].add(r['screen_id'])
            import queries
            out=[]
            for group in grouped.values():
                page_count=len(group['items'])
                confirmed=sum(r['status']=='confirmed' for r in group['items'])
                results=[]
                total=unresolved=0
                for sid in group['screen_ids']:
                    for page in queries.pages_of_screen(c,sid):
                        total+=page['total'];unresolved+=page['unresolved'];results.append(page['pass_fail'])
                pf='fail' if 'fail' in results else ('pass' if len(results)==page_count and confirmed==page_count and all(x=='pass' for x in results) else None)
                group.update(page_count=page_count,confirmed=confirmed,unresolved=unresolved,total=total,pass_fail=pf,
                    href=f"/intake/{group['batch_id']}/screen/{group['item_id']}")
                out.append(group)
            from design_plan import Plans
            plans=Plans(self)
            planned=plans.plans()
            covered={p['batch_id'] for p in planned}
            out=[g for g in out if g['batch_id'] not in covered]
            for p in planned:
                _,cases=plans.get(p['id'])
                prior_ids={x['screen_id'] for x in c.execute('SELECT DISTINCT ip.screen_id FROM inspection_page ip JOIN intake_item i ON i.page_id=ip.uuid WHERE i.batch_id=?',(p['batch_id'],))}
                if p['screen_id']:prior_ids.add(p['screen_id'])
                total=unresolved=0;results=[]
                for t in cases:
                    if t['page_id']:
                        pg=c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?',(t['page_id'],)).fetchone()
                        info=next(x for x in queries.pages_of_screen(c,pg['screen_id']) if x['uuid']==t['page_id'])
                        total+=info['total'];unresolved+=info['unresolved'];results.append(info['pass_fail'])
                count=len(cases);confirmed=sum(t['status']=='confirmed' for t in cases)
                pf='fail' if 'fail' in results else ('pass' if len(results)==count and confirmed==count and all(x=='pass' for x in results) else None)
                out.append(dict(batch_id=p['batch_id'],item_id='',name=p['name'],project_name=p['project_name'],project_id=p['project_id'],platform=p['platform'],created_at=p['created_at'],screen_ids=prior_ids,page_count=count,confirmed=confirmed,unresolved=unresolved,total=total,pass_fail=pf,href='/design/'+p['id']))
            return out

    def page_destination(self, item):
        with self.connect() as c:
            r=c.execute('SELECT i.*,p.screen_id FROM intake_item i LEFT JOIN inspection_page p ON p.uuid=i.page_id WHERE i.id=?',(item,)).fetchone()
            if not r:
                raise ValueError('촬영본을 찾을 수 없습니다.')
            if r['page_id'] and r['status']=='confirmed':
                return f"/screen/{r['screen_id']}/page/{r['page_id']}"
            return f"/intake/{r['batch_id']}/connect?item={r['id']}"
