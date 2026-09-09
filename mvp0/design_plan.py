"""Design-first inspection planning. Original images and events are append-only."""
import json
from contextlib import nullcontext
from intake_store import uid, now

SCHEMA = '''
CREATE TABLE IF NOT EXISTS design_case_exclusion (case_id TEXT PRIMARY KEY, excluded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS design_plan (
 id TEXT PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES intake_batch(id),name TEXT NOT NULL,
 source_note TEXT NOT NULL,screen_id TEXT REFERENCES screen(uuid),created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS design_case (
 id TEXT PRIMARY KEY,plan_id TEXT NOT NULL REFERENCES design_plan(id),design_id TEXT NOT NULL REFERENCES intake_design(id),
 seq INTEGER NOT NULL,tc TEXT NOT NULL,expected TEXT NOT NULL,prerequisite TEXT NOT NULL,
 capture_id TEXT REFERENCES plan_capture(id),status TEXT NOT NULL DEFAULT 'required' CHECK(status IN ('required','pending','confirmed')),
 match_note TEXT NOT NULL DEFAULT '',request_reason TEXT NOT NULL DEFAULT '',page_id TEXT REFERENCES inspection_page(uuid),
 revision INTEGER NOT NULL DEFAULT 0, UNIQUE(plan_id,design_id)
);
CREATE TABLE IF NOT EXISTS plan_capture (
 id TEXT PRIMARY KEY,plan_id TEXT NOT NULL REFERENCES design_plan(id),asset_id TEXT NOT NULL REFERENCES intake_asset(id),
 name TEXT NOT NULL,case_id TEXT REFERENCES design_case(id),created_at TEXT NOT NULL,UNIQUE(plan_id,asset_id)
);
CREATE TABLE IF NOT EXISTS design_plan_event (
 id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,case_id TEXT,action TEXT NOT NULL,detail TEXT NOT NULL,at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS design_plan_event_no_update BEFORE UPDATE ON design_plan_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS design_plan_event_no_delete BEFORE DELETE ON design_plan_event BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''
LABEL={'required':'추가 촬영 필요','pending':'연결됨 · 검수 전','confirmed':'짝 확인됨'}

class Plans:
    def __init__(self,store):self.store=store
    def init(self):
        with self.store.connect() as c:c.executescript(SCHEMA)
    def event(self,c,plan,case,action,detail):
        c.execute('INSERT INTO design_plan_event VALUES(?,?,?,?,?,?)',(uid(),plan,case,action,json.dumps(detail,ensure_ascii=False),now()))
    def plans(self):
        with self.store.connect() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='design_plan'").fetchone():return []
            return c.execute('SELECT p.*,b.platform,b.project_id,j.name project_name FROM design_plan p JOIN intake_batch b ON b.id=p.batch_id JOIN project j ON j.uuid=b.project_id ORDER BY p.created_at').fetchall()
    def get(self,plan,include_excluded=False):
        p=next((dict(p) for p in self.plans() if p['id']==plan),None)
        if not p:raise ValueError('디자인 검수 목록을 찾을 수 없습니다.')
        with self.store.connect() as c:
            cases=c.execute('''SELECT t.*,EXISTS(SELECT 1 FROM design_case_exclusion x WHERE x.case_id=t.id) excluded,d.name,d.source_url,d.fetched_at,a.filename design_file,ca.filename capture_file,
            ca.width,ca.height,pc.name capture_name FROM design_case t JOIN intake_design d ON d.id=t.design_id
            JOIN intake_asset a ON a.id=d.asset_id LEFT JOIN plan_capture pc ON pc.id=t.capture_id
            LEFT JOIN intake_asset ca ON ca.id=pc.asset_id WHERE t.plan_id=? ORDER BY t.seq,t.id''',(plan,)).fetchall()
        return p,[dict(t) for t in cases if include_excluded or not t["excluded"]]
    def case(self,plan,case):
        p,rows=self.get(plan,include_excluded=True);r=next((r for r in rows if r['id']==case),None)
        if not r:raise ValueError('이 목록의 디자인 페이지를 선택하세요.')
        return p,r
    def captures(self,plan):
        with self.store.connect() as c:return c.execute('SELECT p.*,a.filename,a.width,a.height FROM plan_capture p JOIN intake_asset a ON a.id=p.asset_id WHERE p.plan_id=? ORDER BY p.created_at DESC,p.id',(plan,)).fetchall()
    def create(self,batch,name,ordered,source_note):
        self.store.batch(batch)
        if not ordered:raise ValueError('시안이 필요합니다.')
        with self.store.connect() as c:
            existing=c.execute('SELECT id FROM design_plan WHERE batch_id=? AND name=?',(batch,name)).fetchone()
            if existing:return existing['id']
            plan=uid();c.execute('INSERT INTO design_plan VALUES(?,?,?,?,?,?)',(plan,batch,name,source_note,None,now()))
            for seq,spec in enumerate(ordered,1):
                if not c.execute('SELECT 1 FROM intake_design WHERE id=?',(spec['design_id'],)).fetchone():raise ValueError('시안 없음')
                case=uid();c.execute('INSERT INTO design_case(id,plan_id,design_id,seq,tc,expected,prerequisite,request_reason) VALUES(?,?,?,?,?,?,?,?)',(case,plan,spec['design_id'],seq,spec['tc'],spec['expected'],spec.get('prerequisite',''),spec.get('reason','TC에 맞는 개발 캡처가 필요합니다.')))
            for r in c.execute("SELECT * FROM intake_item WHERE batch_id=? AND asset_id IS NOT NULL AND status!='excluded'",(batch,)).fetchall():
                c.execute('INSERT INTO plan_capture VALUES(?,?,?,?,?,?)',(uid(),plan,r['asset_id'],r['state_name'],None,now()))
            self.event(c,plan,None,'디자인 기준 목록 생성',{'시안수':len(ordered),'순서기준':source_note,'TC원본':ordered})
        return plan
    def add(self,plan,design):
        self.get(plan)
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            d=c.execute('SELECT * FROM intake_design WHERE id=?',(design,)).fetchone()
            if not d:raise ValueError('추가할 디자인을 선택하세요.')
            if c.execute('SELECT 1 FROM design_case WHERE plan_id=? AND design_id=?',(plan,design)).fetchone():raise ValueError('이미 등록한 디자인입니다. 제외했다면 복원하세요.')
            seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 FROM design_case WHERE plan_id=?',(plan,)).fetchone()[0]
            case=uid()
            tc='1. 디자인에 표시된 상태로 이동합니다.\n2. 입력·언어·버튼 상태를 시안과 맞춥니다.\n3. 개발 화면을 촬영합니다.'
            expected=d['name']+'와 같은 상태'
            c.execute('INSERT INTO design_case(id,plan_id,design_id,seq,tc,expected,prerequisite,request_reason) VALUES(?,?,?,?,?,?,?,?)',(case,plan,design,seq,tc,expected,'촬영 전 구체적인 조작 절차를 보완하세요.','새 디자인에 맞는 개발 캡처가 필요합니다.'))
            self.event(c,plan,case,'디자인 추가',{'디자인':design,'순서':seq,'tc':tc,'expected':expected})
        return case

    def create_empty(self,project,name,platform,ordered):
        name=name.strip()
        if not name or len(name)>120 or platform not in ('android','ios','web','mobile-web'):raise ValueError('화면 이름과 플랫폼을 확인하세요.')
        with self.store.connect() as c:
            if not c.execute('SELECT 1 FROM project WHERE uuid=?',(project,)).fetchone():raise ValueError('프로젝트를 선택하세요.')
            batch=uid();c.execute('INSERT INTO intake_batch VALUES(?,?,?,?,?,?)',(batch,project,now(),json.dumps({'접수방식':'디자인 먼저'},ensure_ascii=False),uid(),platform))
            self.store.event(c,batch,None,'디자인 기준 준비',{'화면':name})
        return self.create(batch,name,ordered,'작업자가 지정한 디자인 순서')

    def update(self,plan,case,revision,action,fields):
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM design_case WHERE plan_id=? AND id=?',(plan,case)).fetchone()
            self.store.check(r,revision)
            excluded=c.execute('SELECT 1 FROM design_case_exclusion WHERE case_id=?',(case,)).fetchone()
            if action in ('exclude','restore'):
                if action=='exclude':
                    if excluded:raise ValueError('이미 제외한 디자인입니다.')
                    c.execute('INSERT INTO design_case_exclusion VALUES(?,?)',(case,now()))
                else:
                    if not excluded:raise ValueError('이미 목록에 있는 디자인입니다.')
                    c.execute('DELETE FROM design_case_exclusion WHERE case_id=?',(case,))
                c.execute('UPDATE design_case SET revision=revision+1 WHERE id=?',(case,))
            elif excluded:raise ValueError('제외한 디자인입니다. 목록에서 복원한 뒤 작업하세요.')
            elif action=='tc':
                vals=[fields.get(k,'').strip() for k in ('tc','expected','prerequisite')]
                if not vals[0] or not vals[1] or any(len(v)>6000 for v in vals):raise ValueError('촬영 절차와 기대 모습을 입력하세요.')
                c.execute('UPDATE design_case SET tc=?,expected=?,prerequisite=?,revision=revision+1 WHERE id=?',(*vals,case))
            elif action=='select':
                if r['page_id'] and c.execute('SELECT 1 FROM inspection_issue WHERE page_id=? LIMIT 1',(r['page_id'],)).fetchone():raise ValueError('지적이 등록된 화면의 캡처 교체는 새 차수에서 진행합니다.')
                cap=fields.get('capture','');note=fields.get('note','작업자가 캡처 선택')[:2000]
                if not c.execute('SELECT 1 FROM plan_capture WHERE plan_id=? AND id=?',(plan,cap)).fetchone():raise ValueError('이 목록의 캡처를 선택하세요.')
                if r['page_id']:
                    image=c.execute('SELECT a.* FROM plan_capture pc JOIN intake_asset a ON a.id=pc.asset_id WHERE pc.id=?',(cap,)).fetchone()
                    run=c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1',(r['page_id'],)).fetchone()
                    self.event(c,plan,case,'검수 전 연결 변경',{'이전촬영기록':dict(run),'새캡처':cap})
                    c.execute('UPDATE inspection_run SET dev_img=?,dev_img_w=?,dev_img_h=?,coord_ref_w=?,coord_ref_h=? WHERE uuid=?',(image['filename'],image['width'],image['height'],image['width'],image['height'],run['uuid']))
                status='confirmed' if r['page_id'] else ('required' if r['status']=='required' and fields.get('keep_request')=='1' else 'pending')
                c.execute("UPDATE design_case SET capture_id=?,status=?,match_note=?,revision=revision+1 WHERE id=?",(cap,status,note,case))
            elif action=='request':
                if r['page_id']:raise ValueError('검수 시작 후 추가 촬영은 새 차수에서 진행합니다.')
                reason=fields.get('reason','').strip()
                if not reason or len(reason)>2000:raise ValueError('추가 촬영 사유를 입력하세요.')
                c.execute("UPDATE design_case SET status='required',request_reason=?,revision=revision+1 WHERE id=?",(reason,case))
            elif action=='confirm':
                if r['status']!='pending' or not r['capture_id']:raise ValueError('먼저 TC에 맞는 캡처를 선택하세요.')
                p=c.execute('SELECT p.*,b.project_id,b.platform FROM design_plan p JOIN intake_batch b ON b.id=p.batch_id WHERE p.id=?',(plan,)).fetchone()
                cap=c.execute('SELECT a.* FROM plan_capture p JOIN intake_asset a ON a.id=p.asset_id WHERE p.id=?',(r['capture_id'],)).fetchone()
                d=c.execute('SELECT d.name,a.filename FROM intake_design d JOIN intake_asset a ON a.id=d.asset_id WHERE d.id=?',(r['design_id'],)).fetchone()
                sid=p['screen_id']
                if not sid:
                    sid=uid();c.execute('INSERT INTO screen(uuid,project_id,human_key,name,platform,states) VALUES(?,?,?,?,?,?)',(sid,p['project_id'],'',p['name'],p['platform'],'[]'));c.execute('UPDATE design_plan SET screen_id=? WHERE id=?',(sid,plan))
                pg=uid();c.execute('INSERT INTO inspection_page(uuid,screen_id,seq,name,design_img) VALUES(?,?,?,?,?)',(pg,sid,r['seq'],d['name'],d['filename']))
                c.execute('INSERT INTO inspection_run(uuid,screen_id,page_id,round,created_at,dev_img,dev_img_w,dev_img_h,coord_ref_w,coord_ref_h) VALUES(?,?,?,?,?,?,?,?,?,?)',(uid(),sid,pg,1,now(),cap['filename'],cap['width'],cap['height'],cap['width'],cap['height']))
                c.execute("UPDATE design_case SET status='confirmed',page_id=?,revision=revision+1 WHERE id=?",(pg,case))
            else:raise ValueError('지원하지 않는 작업입니다.')
            self.event(c,plan,case,action,{'이전상태':r['status'],'이전TC':{'tc':r['tc'],'expected':r['expected'],'prerequisite':r['prerequisite']},'이전캡처':r['capture_id'],'입력':fields})
    def upload(self,plan,case,revision,name,data,conn=None):
        self.case(plan,case)
        with (nullcontext(conn) if conn is not None else self.store.connect()) as c:
            if conn is None:c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM design_case WHERE id=?',(case,)).fetchone();self.store.check(r,revision)
            if c.execute('SELECT 1 FROM design_case_exclusion WHERE case_id=?',(case,)).fetchone():raise ValueError('제외한 디자인은 복원 후 촬영본을 등록하세요.')
            if r['page_id']:raise ValueError('검수 시작 후 촬영본은 새 차수에서 연결해야 합니다.')
            asset=self.store.asset(c,data);cap=uid();c.execute('INSERT INTO plan_capture VALUES(?,?,?,?,?,?)',(cap,plan,asset,name,case,now()))
            c.execute("UPDATE design_case SET capture_id=?,status='pending',match_note='TC에 따라 추가 촬영한 결과 · 사람 확인 필요',revision=revision+1 WHERE id=?",(cap,case))
            self.event(c,plan,case,'추가 촬영본 등록',{'캡처':cap,'이름':name})
    def queue(self,plan):
        p,rows=self.get(plan)
        return {'format':'design-capture-request-v1','plan_id':plan,'project':p['project_name'],'screen':p['name'],'platform':p['platform'],'created_at':now(),'cases':[{'case_id':r['id'],'seq':r['seq'],'design_name':r['name'],'design_url':r['source_url'],'steps':r['tc'],'expected':r['expected'],'prerequisite':r['prerequisite'],'reason':r['request_reason'],'output_name':'TC-'+r['id']+'@capture.png'} for r in rows if r['status']=='required']}
