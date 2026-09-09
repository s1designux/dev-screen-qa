"""Independent design-first verification: temp DB only, no browser/network writes."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_intake_integration import png, Handler
import io,zipfile
import intake_http,design_plan_http,design_plan_ui
from intake_store import Store
from design_plan import Plans

class DesignPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='design-plan-verifier-',dir='/private/tmp')
        root=Path(self.temp.name)
        self.store=Store(root/'test.db',root/'uploads');self.store.init()
        self.plans=Plans(self.store);self.plans.init()
        self.batch,_=self.store.import_files([('기본.png',png())],project_name='테스트 프로젝트')
        self.designs=[self.store.add_design('file',f'1:{n}',f'시안{n}',f'https://www.figma.com/design/file/?node-id=1-{n}','1:0',png()) for n in (1,2)]
        self.specs=[dict(design_id=d,tc=f'절차 {i}',expected=f'기대 {i}',prerequisite='전제') for i,d in enumerate(self.designs)]
        self.plan=self.plans.create(self.batch,'로그인',self.specs,'디자인 순서')
    def tearDown(self):self.temp.cleanup()
    def case(self,i=0):return self.plans.get(self.plan)[1][i]
    def update(self,action,fields={},i=0):
        r=self.case(i);self.plans.update(self.plan,r['id'],r['revision'],action,fields)
    def events(self):
        with self.store.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM design_plan_event WHERE plan_id=? ORDER BY rowid',(self.plan,))]
    def test_create_order_queue_and_readonly_original(self):
        with self.store.connect() as c:before=''.join(c.iterdump())
        p,rows=self.plans.get(self.plan);q=self.plans.queue(self.plan)
        self.assertEqual([r['design_id'] for r in rows],self.designs)
        self.assertEqual([r['seq'] for r in rows],[1,2])
        self.assertEqual(q['format'],'design-capture-request-v1')
        self.assertEqual([r['steps'] for r in q['cases']],['절차 0','절차 1'])
        self.assertTrue(all(r['output_name']==f'TC-{r["case_id"]}@capture.png' for r in q['cases']))
        self.assertEqual(json.loads(json.dumps(q,ensure_ascii=False)),q)
        with self.store.connect() as c:self.assertEqual(''.join(c.iterdump()),before)
        self.assertEqual(self.store.batch(self.batch)[1][0]['status'],'unlinked')
    def test_request_upload_pending_confirm_new_page(self):
        self.update('request',{'reason':'키보드 포함 필요'})
        r=self.case();self.plans.upload(self.plan,r['id'],r['revision'],'새 촬영.png',png())
        r=self.case();self.assertEqual(r['status'],'pending');self.assertIsNone(r['page_id'])
        self.assertEqual(len(self.plans.queue(self.plan)['cases']),1)
        self.update('confirm');r=self.case();self.assertEqual(r['status'],'confirmed');self.assertTrue(r['page_id'])
        with self.store.connect() as c:
            page=c.execute('SELECT * FROM inspection_page WHERE uuid=?',(r['page_id'],)).fetchone()
            run=c.execute('SELECT * FROM inspection_run WHERE page_id=?',(r['page_id'],)).fetchone()
            self.assertEqual(page['seq'],1);self.assertIsNone(run['pass_fail']);self.assertEqual(run['round'],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_issue').fetchone()[0],0)
        self.assertTrue((self.store.uploads/r['capture_file']).exists())
        self.assertEqual(len(self.plans.captures(self.plan)),2)
        with self.assertRaises(ValueError):self.update('confirm')
    def test_cross_plan_scope_and_revision_rejection(self):
        other_batch,_=self.store.import_files([('다름.png',png())],project_name='다른 프로젝트')
        other=self.plans.create(other_batch,'로그인',self.specs,'순서')
        other_case=self.plans.get(other)[1][0];cap=self.plans.captures(other)[0]
        with self.assertRaises(ValueError):self.plans.case(self.plan,other_case['id'])
        with self.assertRaises(ValueError):self.update('select',{'capture':cap['id']})
        r=self.case()
        with self.assertRaises(ValueError):self.plans.update(self.plan,other_case['id'],0,'request',{'reason':'침범'})
        with self.assertRaises(ValueError):self.plans.upload(self.plan,other_case['id'],0,'x.png',png())
        self.update('request',{'reason':'변경'})
        with self.assertRaises(ValueError):self.plans.update(self.plan,r['id'],r['revision'],'request',{'reason':'오래된 입력'})
        with self.assertRaises(ValueError):self.plans.upload(self.plan,r['id'],r['revision'],'x.png',png())
    def test_select_reuse_requires_confirmation(self):
        cap=self.plans.captures(self.plan)[0]['id']
        with self.assertRaises(ValueError):self.update('confirm')
        self.update('select',{'capture':cap,'note':'같은 시각상태'})
        self.update('select',{'capture':cap},1)
        self.assertTrue(all(r['status']=='pending' for r in self.plans.get(self.plan)[1]))
        self.assertEqual(self.plans.queue(self.plan)['cases'],[])
        self.update('confirm');self.update('confirm',i=1)
        with self.store.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_page').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM screen').fetchone()[0],1)
    def test_bad_upload_no_mutation_and_append_only(self):
        r=self.case();before=self.events();assets=set(self.store.uploads.iterdir())
        with self.assertRaises(ValueError):self.plans.upload(self.plan,r['id'],r['revision'],'broken.png',b'broken')
        self.assertEqual(self.case(),r);self.assertEqual(self.events(),before);self.assertEqual(set(self.store.uploads.iterdir()),assets)
        with self.store.connect() as c:
            with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM design_plan_event')
            with self.assertRaises(sqlite3.IntegrityError):c.execute("UPDATE design_plan_event SET action='overwrite'")
    def test_started_case_request_cannot_create_dead_end(self):
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']});self.update('confirm')
        before=self.case()
        with self.assertRaises(ValueError):self.update('request',{'reason':'추가 촬영'})
        self.assertEqual(self.case(),before)
    def multipart(self,fields,files):
        boundary='design-test-boundary';chunks=[]
        for k,v in dict(csrf=intake_http.CSRF,**fields).items():
            chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode())
        for name,data in files:
            chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\n\r\n').encode()+data+b'\r\n')
        chunks.append(f'--{boundary}--\r\n'.encode());h=Handler(b''.join(chunks));h.headers['Content-Type']='multipart/form-data; boundary='+boundary
        return h
    def test_empty_design_first_and_http_create(self):
        from urllib.parse import urlencode
        project=self.plans.get(self.plan)[0]['project_id']
        h=Handler(urlencode({'csrf':intake_http.CSRF,'project':project,'name':'촬영 전','platform':'android','order_'+self.designs[0]:'2','order_'+self.designs[1]:'1'}).encode())
        design_plan_http.post(h,self.store,'/design/create');self.assertEqual(h.code,303)
        created=h.location.split('/')[-1];_,cases=self.plans.get(created)
        self.assertEqual([r['design_id'] for r in cases],list(reversed(self.designs)))
        self.assertEqual(self.plans.captures(created),[])
        self.assertTrue(all(r['status']=='required' for r in cases))
    def test_http_bundle_required_only_and_readonly_render(self):
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']})
        h=Handler(b'');h.wfile=io.BytesIO()
        with self.store.connect() as c:before=''.join(c.iterdump())
        design_plan_http.get(h,self.store,f'/design/{self.plan}/bundle');self.assertEqual(h.code,200)
        with zipfile.ZipFile(io.BytesIO(h.wfile.getvalue())) as z:
            q=json.loads(z.read('촬영요청.json'))
            self.assertEqual(len(q['cases']),1)
            self.assertEqual(q['cases'][0]['case_id'],self.case(1)['id'])
            self.assertEqual(sum(n.startswith('디자인/') for n in z.namelist()),1)
            self.assertIn('capture_tc.py',z.namelist())
        for case in self.plans.get(self.plan)[1]:
            rendered=design_plan_ui.detail(self.store,self.plan,case['id'])
            self.assertNotIn('TC · 촬영 절차',rendered)
            self.assertNotIn('name="tc"',rendered)
            self.assertNotIn(case['tc'],rendered)
            self.assertNotIn('담당자 명단',rendered)
            self.assertIn('class="capture-layout"',rendered)
            self.assertIn('class="capture-list"',rendered)
        with self.store.connect() as c:self.assertEqual(''.join(c.iterdump()),before)
    def test_http_csrf_upload_and_confirm(self):
        from urllib.parse import urlencode
        r=self.case();path=f'/design/{self.plan}/case/{r["id"]}'
        h=Handler(urlencode({'revision':r['revision'],'reason':'test'}).encode())
        design_plan_http.post(h,self.store,path+'/request');self.assertEqual(h.code,400)
        h=self.multipart({'revision':r['revision']},[('new.png',png())]);design_plan_http.post(h,self.store,path+'/upload')
        self.assertEqual(h.code,303);self.assertEqual(self.case()['status'],'pending')
        r=self.case();h=Handler(urlencode({'csrf':intake_http.CSRF,'revision':r['revision']}).encode())
        design_plan_http.post(h,self.store,path+'/confirm');self.assertEqual(h.code,303)
        self.assertEqual(self.case()['status'],'confirmed')
    def test_http_bulk_import_missing_preflight_then_success(self):
        entries=[{'case_id':self.case(i)['id'],'파일':f'{i}.png'} for i in range(2)]
        manifest=json.dumps({'format':'design-capture-results-v1','plan_id':self.plan,'찍힌것':entries}).encode()
        h=self.multipart({},[('찍은목록.json',manifest),('0.png',png())]);design_plan_http.post(h,self.store,f'/design/{self.plan}/import')
        self.assertEqual(h.code,400);self.assertTrue(all(r['status']=='required' for r in self.plans.get(self.plan)[1]))
        h=self.multipart({},[('찍은목록.json',manifest),('0.png',png()),('1.png',png())]);design_plan_http.post(h,self.store,f'/design/{self.plan}/import')
        self.assertEqual(h.code,303);self.assertTrue(all(r['status']=='pending' and not r['page_id'] for r in self.plans.get(self.plan)[1]))
    def test_http_malformed_manifest_returns_400(self):
        for manifest in [[],{'format':'design-capture-results-v1','plan_id':self.plan,'찍힌것':[None]}]:
            with self.subTest(manifest=manifest):
                h=self.multipart({},[('찍은목록.json',json.dumps(manifest).encode())])
                design_plan_http.post(h,self.store,f'/design/{self.plan}/import')
                self.assertEqual(h.code,400)
    def test_http_missing_revision_returns_400(self):
        from urllib.parse import urlencode
        h=Handler(urlencode({'csrf':intake_http.CSRF,'reason':'test'}).encode())
        design_plan_http.post(h,self.store,f'/design/{self.plan}/case/{self.case()["id"]}/request')
        self.assertEqual(h.code,400)

    def test_registered_design_plan_blocks_legacy_upload_bypass(self):
        import portal
        from unittest.mock import patch
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']});self.update('confirm')
        page=self.case()['page_id']
        with patch.object(portal,'REAL_DB',self.store.database),patch.object(portal,'UPLOADS',self.store.uploads):
            with self.assertRaises(ValueError):portal._save_upload(page,'dev',png(),(1,1))

    def test_bulk_write_failure_rolls_back_all_database_changes(self):
        from unittest.mock import patch
        entries=[{'case_id':self.case(i)['id'],'파일':f'{i}.png'} for i in range(2)]
        manifest=json.dumps({'format':'design-capture-results-v1','plan_id':self.plan,'찍힌것':entries}).encode()
        h=self.multipart({},[('찍은목록.json',manifest),('0.png',png()),('1.png',png())])
        with self.store.connect() as c:before=''.join(c.iterdump())
        original=self.store.asset;count=0
        def fail_second(c,data):
            nonlocal count
            count+=1
            if count==2:raise ValueError('simulated second asset failure')
            return original(c,data)
        with patch.object(self.store,'asset',side_effect=fail_second):
            design_plan_http.post(h,self.store,f'/design/{self.plan}/import')
        self.assertEqual(h.code,400)
        with self.store.connect() as c:self.assertEqual(''.join(c.iterdump()),before)
    def test_registered_legacy_url_uses_design_workflow_and_is_readonly(self):
        import portal
        from unittest.mock import patch
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']});self.update('confirm')
        r=self.case();p=self.plans.get(self.plan)[0]
        h=Handler(b'');h.path=f'/screen/{p["screen_id"]}/page/{r["page_id"]}';h._local_host=lambda:True
        with self.store.connect() as c:before=''.join(c.iterdump())
        with patch.object(portal,'REAL_DB',self.store.database),patch.object(portal,'UPLOADS',self.store.uploads):
            portal.Handler.do_GET(h)
        self.assertEqual(h.code,200)
        self.assertNotIn('TC · 촬영 절차',h.body)
        self.assertNotIn('name="tc"',h.body)
        self.assertNotIn(r['tc'],h.body)
        self.assertNotIn('담당자 명단',h.body)
        self.assertIn('href="/design/'+self.plan+'"',h.body)
        self.assertIn('id="cards"',h.body)
        self.assertNotIn('action="/screen/',h.body) # no legacy upload forms on this empty case
        with self.store.connect() as c:self.assertEqual(''.join(c.iterdump()),before)

    def test_exclude_restore_queue_and_mutation_guards(self):
        r=self.case();case=r['id'];old=dict(r)
        self.plans.update(self.plan,case,r['revision'],'exclude',{})
        excluded=self.plans.case(self.plan,case)[1]
        self.assertEqual(excluded['excluded'],1)
        self.assertEqual(len(self.plans.get(self.plan)[1]),1)
        self.assertEqual(len(self.plans.get(self.plan,include_excluded=True)[1]),2)
        self.assertNotIn(case,[r['case_id'] for r in self.plans.queue(self.plan)['cases']])
        for action,fields in [('tc',{'tc':'new','expected':'new'}),('request',{'reason':'new'}),('select',{'capture':self.plans.captures(self.plan)[0]['id']}),('confirm',{})]:
            with self.assertRaises(ValueError):self.plans.update(self.plan,case,excluded['revision'],action,fields)
        with self.assertRaises(ValueError):self.plans.upload(self.plan,case,excluded['revision'],'x.png',png())
        with self.assertRaises(ValueError):self.plans.update(self.plan,case,old['revision'],'restore',{})
        self.plans.update(self.plan,case,excluded['revision'],'restore',{})
        restored=self.plans.case(self.plan,case)[1]
        for key in ['tc','expected','prerequisite','design_id','seq','status']:self.assertEqual(restored[key],old[key])
        self.assertEqual([r['case_id'] for r in self.plans.queue(self.plan)['cases']],[row['id'] for row in self.plans.get(self.plan)[1]])
        actions=[r['action'] for r in self.events()];self.assertIn('exclude',actions);self.assertIn('restore',actions)
    def test_exclude_confirmed_preserves_inspection_and_original_assets(self):
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']});self.update('confirm')
        r=self.case();case=r['id'];assets={p.name:p.read_bytes() for p in self.store.uploads.iterdir()}
        with self.store.connect() as c:
            c.execute('INSERT INTO inspection_issue(uuid,screen_id,page_id,status,description) VALUES(?,?,?,?,?)',('issue',self.plans.get(self.plan)[0]['screen_id'],r['page_id'],'발견','지적 원본'))
            c.execute('INSERT INTO issue_history(uuid,issue_id,to_status,note) VALUES(?,?,?,?)',('history','issue','발견','최초 이력'))
        def snapshots():
            with self.store.connect() as c:return {t:[tuple(row) for row in c.execute('SELECT * FROM '+t)] for t in ['inspection_page','inspection_run','inspection_issue','issue_history']}
        before=snapshots()
        self.plans.update(self.plan,case,r['revision'],'exclude',{})
        excluded=self.plans.case(self.plan,case)[1]
        self.assertIn('제외',design_plan_ui.detail(self.store,self.plan,case))
        self.plans.update(self.plan,case,excluded['revision'],'restore',{})
        self.assertEqual(snapshots(),before)
        self.assertEqual({p.name:p.read_bytes() for p in self.store.uploads.iterdir()},assets)
        self.assertEqual(self.plans.case(self.plan,case)[1]['page_id'],r['page_id'])
    def test_add_appends_order_and_rejects_existing_even_excluded(self):
        old=self.case();self.plans.update(self.plan,old['id'],old['revision'],'exclude',{})
        with self.assertRaises(ValueError):self.plans.add(self.plan,old['design_id'])
        d=self.store.add_design('file','1:99','추가 시안','https://www.figma.com/design/file/?node-id=1-99','1:0',png())
        new=self.plans.add(self.plan,d);r=self.plans.case(self.plan,new)[1]
        self.assertEqual(r['seq'],3);self.assertEqual(r['status'],'required');self.assertIsNone(r['page_id'])
        with self.assertRaises(ValueError):self.plans.add('not-a-plan',d)
        with self.assertRaises(ValueError):self.plans.add(self.plan,'not-a-design')
        self.assertIn('디자인 추가',[r['action'] for r in self.events()])
    def test_http_add_exclude_restore_scope_and_manage(self):
        from urllib.parse import urlencode
        r=self.case();case=r['id']
        def post(action,revision):
            h=Handler(urlencode({'csrf':intake_http.CSRF,'revision':revision}).encode())
            design_plan_http.post(h,self.store,f'/design/{self.plan}/case/{case}/{action}')
            return h
        self.assertEqual(post('exclude',r['revision']).code,303)
        self.assertEqual(post('restore',r['revision']).code,400)
        self.assertIn('목록으로 복원',design_plan_ui.manage(self.store,self.plan))
        r=self.plans.case(self.plan,case)[1]
        self.assertEqual(post('restore',r['revision']).code,303)
        other=self.plans.create(self.batch,'다른 목록',self.specs,'순서')
        alien=self.plans.get(other)[1][0]
        h=Handler(urlencode({'csrf':intake_http.CSRF,'revision':alien['revision']}).encode())
        design_plan_http.post(h,self.store,f'/design/{self.plan}/case/{alien["id"]}/exclude')
        self.assertEqual(h.code,400);self.assertFalse(self.plans.case(other,alien['id'])[1]['excluded'])
        d=self.store.add_design('file','2:99','HTTP 추가','https://www.figma.com/design/file/?node-id=2-99','1:0',png())
        h=Handler(urlencode({'csrf':intake_http.CSRF,'design':d}).encode())
        design_plan_http.post(h,self.store,f'/design/{self.plan}/add');self.assertEqual(h.code,303)
        self.assertIn(d,[row['design_id'] for row in self.plans.get(self.plan)[1]])

    def test_http_new_design_png_validation_and_append(self):
        before=self.plans.get(self.plan)[1]
        for name,files in [('',[('new.png',png())]),('x'*121,[('new.png',png())]),('정상 이름',[('bad.png',b'broken')]),('정상 이름',[])]:
            h=self.multipart({'name':name},files)
            design_plan_http.post(h,self.store,f'/design/{self.plan}/upload-design')
            self.assertEqual(h.code,400)
            self.assertEqual(self.plans.get(self.plan)[1],before)
        h=self.multipart({'name':'새 원본 <img>'},[('../new.png',png())])
        design_plan_http.post(h,self.store,f'/design/{self.plan}/upload-design');self.assertEqual(h.code,303)
        rows=self.plans.get(self.plan)[1];self.assertEqual(len(rows),3)
        new=rows[-1];self.assertEqual(new['seq'],3);self.assertEqual(new['status'],'required');self.assertIsNone(new['page_id'])
        self.assertEqual((self.store.uploads/new['design_file']).read_bytes(),png())
        self.assertNotIn('/',new['design_file'])
        self.assertIn('새 원본 &lt;img&gt;',design_plan_ui.listing(self.store,self.plan))
        with self.store.connect() as c:
            d=c.execute('SELECT * FROM intake_design WHERE id=?',(new['design_id'],)).fetchone()
            self.assertEqual(d['provider'],'작업자 원본 PNG 등록')
        h=self.multipart({'name':'없는 대상'},[('new.png',png())])
        design_plan_http.post(h,self.store,'/design/invalid/upload-design');self.assertEqual(h.code,400)

    def test_page_navigation_edges_exclusion_restore_and_no_writes(self):
        import re
        d=self.store.add_design('file','3:99','마지막','https://www.figma.com/design/file/?node-id=3-99','1:0',png())
        last=self.plans.add(self.plan,d);first=self.case()['id'];middle=self.case(1)['id']
        def nav(case):
            body=design_plan_ui.detail(self.store,self.plan,case)
            result=re.search(r'<nav class="page-navigation".*?</nav>',body,re.S).group()
            self.assertGreater(body.index(result),body.index('<a class="back"'))
            return result
        with self.store.connect() as c:before=''.join(c.iterdump())
        left=nav(first);center=nav(middle);right=nav(last)
        self.assertIn('aria-disabled="true">← 이전',left);self.assertIn('1 / 3',left)
        self.assertIn('/case/'+middle,left)
        self.assertIn('/case/'+first,center);self.assertIn('/case/'+last,center);self.assertIn('2 / 3',center)
        self.assertIn('aria-disabled="true">다음 →',right);self.assertIn('3 / 3',right)
        with self.store.connect() as c:self.assertEqual(''.join(c.iterdump()),before)
        r=self.plans.case(self.plan,middle)[1];self.plans.update(self.plan,middle,r['revision'],'exclude',{})
        left=nav(first);self.assertIn('/case/'+last,left);self.assertNotIn('/case/'+middle,left);self.assertIn('1 / 2',left)
        r=self.plans.case(self.plan,last)[1];self.plans.update(self.plan,last,r['revision'],'exclude',{})
        only=nav(first);self.assertEqual(only.count('aria-disabled="true"'),2);self.assertIn('1 / 1',only)
        r=self.plans.case(self.plan,middle)[1];self.plans.update(self.plan,middle,r['revision'],'restore',{})
        self.assertIn('/case/'+middle,nav(first))

    def test_pending_confirmation_is_in_visible_tc_sidebar(self):
        self.update('select',{'capture':self.plans.captures(self.plan)[0]['id']})
        r=self.case();body=design_plan_ui.detail(self.store,self.plan,r['id'])
        visible=body.split('<dialog')[0]
        self.assertIn('action="/design/'+self.plan+'/case/'+r['id']+'/confirm"',visible)
        self.assertIn('이 캡처로 검수 시작',visible)

    def test_baseline_selection_preserves_required_queue_via_http(self):
        from urllib.parse import urlencode
        r=self.case();cap=self.plans.captures(self.plan)[0]['id']
        body=design_plan_ui.detail(self.store,self.plan,r['id'])
        self.assertIn('name="keep_request" value="1"',body)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'revision':r['revision'],'capture':cap,'keep_request':'1'}).encode())
        design_plan_http.post(h,self.store,f'/design/{self.plan}/case/{r["id"]}/select')
        self.assertEqual(h.code,303)
        current=self.case();self.assertEqual(current['capture_id'],cap);self.assertEqual(current['status'],'required')
        self.assertEqual(current['request_reason'],r['request_reason'])
        self.assertIn(r['id'],[q['case_id'] for q in self.plans.queue(self.plan)['cases']])
        with self.assertRaises(ValueError):self.update('confirm')
    def test_registered_capture_replacement_archives_run_and_blocks_with_issue(self):
        r=self.case(1);self.plans.upload(self.plan,r['id'],r['revision'],'대체.png',png())
        replacement=self.case(1)['capture_id']
        oldcap=next(c for c in self.plans.captures(self.plan) if c['id']!=replacement)['id']
        self.update('select',{'capture':oldcap});self.update('confirm')
        case=self.case();page=case['page_id']
        with self.store.connect() as c:old=dict(c.execute('SELECT * FROM inspection_run WHERE page_id=?',(page,)).fetchone())
        oldbytes=(self.store.uploads/old['dev_img']).read_bytes()
        self.update('select',{'capture':replacement})
        current=self.case();self.assertEqual(current['page_id'],page);self.assertEqual(current['status'],'confirmed')
        with self.store.connect() as c:
            run=dict(c.execute('SELECT * FROM inspection_run WHERE page_id=?',(page,)).fetchone())
            self.assertEqual(run['uuid'],old['uuid']);self.assertNotEqual(run['dev_img'],old['dev_img'])
            self.assertEqual((run['dev_img_w'],run['dev_img_h'],run['coord_ref_w'],run['coord_ref_h']),(1,1,1,1))
            c.execute('INSERT INTO inspection_issue(uuid,screen_id,page_id,status) VALUES(?,?,?,?)',('blocker',run['screen_id'],page,'보류'))
        preserved=[json.loads(e['detail']) for e in self.events() if e['action']=='검수 전 연결 변경']
        self.assertEqual(preserved[-1]['이전촬영기록'],old)
        self.assertEqual((self.store.uploads/old['dev_img']).read_bytes(),oldbytes)
        with self.assertRaises(ValueError):self.update('select',{'capture':oldcap})
        self.assertEqual(self.case(),current)

    def test_tc_original_values_remain_in_event_history(self):
        self.update('tc',{'tc':'새 절차','expected':'새 기대','prerequisite':'새 전제'})
        history=json.dumps([json.loads(r['detail']) for r in self.events()],ensure_ascii=False)
        for original in ['절차 0','기대 0','전제']:self.assertIn(original,history)
        self.assertEqual(self.case()['tc'],'새 절차')

if __name__=='__main__':unittest.main(verbosity=2)
