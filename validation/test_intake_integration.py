"""Independent verifier tests. Only temporary databases/assets; no live Figma calls."""
import io
import json
import sqlite3
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import intake_store as storemod
import intake_http
import figma_reader
import portal
import queries


def png(payload=None):
    def chunk(k, v):
        return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00') if payload is None else payload)+chunk(b'IEND',b'')

class Handler:
    def __init__(self, body, origin='http://localhost:8000'):
        self.headers={'Content-Length':str(len(body)), 'Content-Type':'application/x-www-form-urlencoded','Host':'localhost:8000','Origin':origin}
        self.rfile=io.BytesIO(body)
        self.code=None
        self.body=''
    def _html(self, body, code=200): self.body,self.code=body,code
    def send_response(self, code): self.code=code
    def send_header(self,name,value):
        if name=='Location': self.location=value
    def end_headers(self): pass

class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='intake-verifier-',dir='/private/tmp')
        root=Path(self.tmp.name)
        self.s=storemod.Store(root/'test.db',root/'uploads')
        self.s.init()
    def tearDown(self): self.tmp.cleanup()
    def batch(self,n=10):
        rows=[{'파일':f'{i}.png','화면이름':'로그인','상태':f'상태{i}'} for i in range(n)]
        files=[('찍은목록.json',json.dumps({'촬영본':rows}).encode())]+[(f'{i}.png',png()) for i in range(n)]
        return self.s.import_files(files,project_name='독립검증')[0],files
    def item(self,b,i=0): return self.s.batch(b)[1][i]
    def design(self,node='1:1'): return self.s.add_design('test',node,'시안','https://www.figma.com/design/test/?node-id='+node.replace(':','-'),'1:0',png())
    def select_confirm(self,b,index,d):
        r=self.item(b,index); self.s.select_design(r['id'],r['revision'],d)
        r=self.item(b,index); self.s.confirm(r['id'],r['revision'])
    def test_ten_eight_two_and_duplicate(self):
        b,files=self.batch()
        for idx in (8,9):
            r=self.item(b,idx); self.s.edit_item(r['id'],r['revision'],'찾기',r['state_name'],'excluded','본문 미표시, 원인 미확인')
        rows=self.s.batch(b)[1]
        self.assertEqual(len(rows),10)
        self.assertEqual(sum(r['status']=='excluded' for r in rows),2)
        self.assertTrue(all(r['asset_id'] for r in rows))
        self.assertEqual(self.s.import_files(files,project_name='독립검증'),(b,True))
        self.assertEqual(len(list(self.s.uploads.glob('*.png'))),10)
    def test_missing_corrupt_and_duplicate_names(self):
        files=[('찍은목록.json',json.dumps({'촬영본':[{'파일':'missing.png'},{'파일':'broken.png'}]}).encode()),('broken.png',b'not png')]
        b,_=self.s.import_files(files,project_name='독립검증')
        self.assertTrue(all(r['error'] and not r['asset_id'] for r in self.s.batch(b)[1]))
        with self.assertRaises(ValueError): self.s.import_files([('a.png',png()),('dir/a.png',png())],project_name='독립검증')
        with self.assertRaises(ValueError): self.s.start(b)
    def test_crc_valid_but_undecodable_png_rejected(self):
        with self.assertRaises(ValueError): storemod.png_size(png(b'not a zlib image stream'))
    def test_hold_name_stale_revision_and_history(self):
        b,_=self.batch(1); r=self.item(b)
        with self.assertRaises(ValueError): self.s.edit_item(r['id'],0,'로그인','기본','held','')
        self.s.edit_item(r['id'],0,'이름 수정','새 상태','held','시안 없음')
        with self.assertRaises(ValueError): self.s.edit_item(r['id'],0,'로그인','기본','include','')
        r=self.item(b); self.assertEqual(r['screen_name'],'이름 수정')
        with self.assertRaises(ValueError): self.s.select_design(r['id'],r['revision'],self.design())
        with self.s.connect() as c:
            with self.assertRaises(sqlite3.IntegrityError): c.execute('DELETE FROM intake_event')
            with self.assertRaises(sqlite3.IntegrityError): c.execute("UPDATE intake_event SET action='changed'")
    def test_partial_start_reuse_reconnect_restart_and_pass(self):
        b,_=self.batch(3); d=self.design(); d2=self.design('1:2')
        with self.assertRaises(ValueError): self.s.start(b)
        r=self.item(b); self.s.select_design(r['id'],r['revision'],d)
        with self.assertRaises(ValueError): self.s.start(b)
        r=self.item(b); self.s.confirm(r['id'],r['revision'])
        r=self.item(b); self.s.select_design(r['id'],r['revision'],d2)
        self.assertEqual(self.item(b)['status'],'pending')
        r=self.item(b); self.s.confirm(r['id'],r['revision'])
        path=self.s.start(b)
        self.assertTrue(path.startswith('/screen/'))
        self.assertFalse(self.item(b,1)['page_id'])
        self.select_confirm(b,1,d2)
        self.s.start(b); self.s.start(b)
        self.s=storemod.Store(self.s.database,self.s.uploads); self.s.init()
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_page').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_issue').fetchone()[0],0)
            screen=c.execute('SELECT * FROM screen').fetchone()
            self.assertEqual(screen['human_key'],'')
            self.assertIsNone(queries.screen_pass_fail(c,screen['uuid']))
            self.assertIsNotNone(queries.get_screen(c,screen['uuid']))
            c.execute("UPDATE inspection_run SET pass_fail='pass'")
            self.assertEqual(queries.screen_pass_fail(c,screen['uuid']),'pass')
            c.execute("UPDATE inspection_run SET pass_fail='fail' WHERE page_id=?",(self.item(b)['page_id'],))
            self.assertEqual(queries.screen_pass_fail(c,screen['uuid']),'fail')
        with patch.object(portal,'REAL_DB',self.s.database),patch.object(portal,'UPLOADS',self.s.uploads):
            self.assertIn('미정',portal.render_screen(screen['uuid']))
            self.assertIn('Figma',portal.render_page(self.item(b)['page_id']))
    def test_http_csrf_origin_revision_and_unknown_batch(self):
        from urllib.parse import urlencode
        b,_=self.batch(1)
        for csrf,origin in [('', 'http://localhost:8000'),(intake_http.CSRF,'https://evil.example'),(intake_http.CSRF,'null')]:
            h=Handler(urlencode({'csrf':csrf}).encode(),origin)
            intake_http.post(h,self.s,f'/intake/{b}/start'); self.assertEqual(h.code,400)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':self.item(b)['id'],'revision':'bad','screen':'로그인','state':'기본','status':'include'}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/edit'); self.assertEqual(h.code,400)
        h=Handler(b''); intake_http.get(h,self.s,'/intake/'+'a'*32,{})
        self.assertEqual(h.code,404)
    def test_figma_no_network_invalid_link_and_untrusted_image(self):
        for link in ('http://www.figma.com/design/test/?node-id=1-2','https://evil.example/design/test/?node-id=1-2','https://www.figma.com/design/test/'):
            with self.assertRaises(ValueError): figma_reader.parse_link(link)
        self.assertEqual(figma_reader.parse_link('https://www.figma.com/design/test/?node-id=1-2&amp;m=dev'),('test','1:2'))
        with self.assertRaises(ValueError): figma_reader.image_bytes('http://127.0.0.1/private')
        with patch.object(figma_reader,'TOKEN',''):
            with self.assertRaises(ValueError): figma_reader.api('files/test')
    def test_actual_ten_capture_files(self):
        folder=Path('/Users/designgroup_02/dev-screen-qa-capture/capture-app/shots/20260909-auth-trial')
        if not folder.exists(): self.skipTest('실제 촬영 자료가 이 컴퓨터에 없음')
        files=[(p.name,p.read_bytes()) for p in folder.iterdir() if p.suffix=='.png' or p.name=='찍은목록.json']
        b,_=self.s.import_files(files,project_name='실제자료 독립검증')
        rows=self.s.batch(b)[1]
        self.assertEqual(len(rows),10)
        self.assertEqual(sum(r['screen_name']=='로그인' for r in rows),8)
        self.assertTrue(all(r['asset_id'] and not r['error'] for r in rows))
        for r in rows:
            if r['screen_name']!='로그인':
                self.s.edit_item(r['id'],r['revision'],r['screen_name'],r['state_name'],'excluded','본문 미표시, 원인 미확인')
        self.assertEqual(sum(r['status']=='excluded' for r in self.s.batch(b)[1]),2)

    def test_started_page_reconnect_requires_confirmation_and_preserves_asset(self):
        b,_=self.batch(1); d=self.design(); self.select_confirm(b,0,d); self.s.start(b)
        r=self.item(b); page=r['page_id']
        with self.s.connect() as c:
            old=c.execute('SELECT design_img FROM inspection_page WHERE uuid=?',(page,)).fetchone()[0]
        d2=self.design('2:2'); self.s.select_design(r['id'],r['revision'],d2)
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT design_img FROM inspection_page WHERE uuid=?',(page,)).fetchone()[0],old)
        with patch.object(portal,'REAL_DB',self.s.database),patch.object(portal,'UPLOADS',self.s.uploads):
            self.assertNotIn('src="/uploads/'+old,portal.render_page(page).split('<dialog')[0])
            with self.assertRaises(ValueError): portal._save_upload(page,'design',png(),(1,1))
        r=self.item(b); self.s.confirm(r['id'],r['revision'])
        with self.s.connect() as c:
            self.assertNotEqual(c.execute('SELECT design_img FROM inspection_page WHERE uuid=?',(page,)).fetchone()[0],old)
        self.assertTrue((self.s.uploads/old).exists())

    def test_http_multipart_import_and_size_limit(self):
        boundary='verifier-boundary'
        parts=[]
        for name,value in [('csrf',intake_http.CSRF),('project_name','HTTP 검증')]:
            parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode())
        parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="files"; filename="capture.png"\r\nContent-Type: image/png\r\n\r\n').encode()+png()+b'\r\n')
        parts.append(('--'+boundary+'--\r\n').encode())
        h=Handler(b''.join(parts)); h.headers['Content-Type']='multipart/form-data; boundary='+boundary
        intake_http.post(h,self.s,'/intake/import')
        self.assertEqual(h.code,303)
        self.assertEqual(len(self.s.batches()),1)
        h=Handler(b''); h.headers['Content-Length']=str(intake_http.MAX_BODY+1)
        intake_http.post(h,self.s,'/intake/import')
        self.assertEqual(h.code,400)

    def test_http_item_cannot_cross_batch(self):
        from urllib.parse import urlencode
        b,_=self.batch(1)
        other,_=self.s.import_files([('로그인@다른촬영.png',png())],project_name='독립검증')
        target=self.item(other)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':target['id'],'revision':target['revision'],'screen':'변조','state':'기본','status':'include'}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/edit')
        self.assertEqual(h.code,400)
        self.assertEqual(self.item(other)['screen_name'],'로그인')

    def test_figma_mock_single_frame_snapshot_without_pair_mutation(self):
        b,_=self.batch(1); before=dict(self.item(b))
        response={'version':'v1','nodes':{'1:2':{'document':{'id':'1:2','name':'로그인','type':'FRAME'}}}}
        with patch.object(figma_reader,'api',side_effect=[response,{'images':{'1:2':'https://x.figma.com/a'}}]) as api, patch.object(figma_reader,'image_bytes',return_value=png()):
            added,failed=figma_reader.fetch(self.s,'https://www.figma.com/design/test/?node-id=1-2')
        self.assertEqual((len(added),failed),(1,0))
        self.assertIn('version=v1',api.call_args_list[1].args[0])
        self.assertEqual(dict(self.item(b)),before)
        design=self.s.designs()[0]
        self.assertEqual(design['source_version'],'v1')
        self.assertEqual(design['scope_node'],'1:2')

    def test_figma_mock_page_range_partial_failure(self):
        frame=lambda node:{'id':node,'name':node,'type':'FRAME'}
        root={'id':'1:0','type':'CANVAS','children':[frame('1:1'),{'id':'2:0','type':'SECTION','children':[frame('2:1'),frame('2:2')]},dict(frame('9:9'),visible=False)]}
        response={'nodes':{'1:0':{'document':root}}}
        images={'images':{'1:1':'https://x.figma.com/ok','2:1':'https://x.figma.com/bad','2:2':None}}
        with patch.object(figma_reader,'api',side_effect=[response,images]),patch.object(figma_reader,'image_bytes',side_effect=[png(),b'broken']):
            added,failed=figma_reader.fetch(self.s,'https://www.figma.com/design/test/?node-id=1-0')
        self.assertEqual((len(added),failed),(1,2))
        self.assertEqual(len(self.s.designs()),1)
        self.assertEqual(self.s.designs()[0]['node_id'],'1:1')

    def test_figma_mock_access_errors_and_all_fail_preserve_selection(self):
        from urllib.error import HTTPError
        from unittest.mock import Mock
        for code,fragment in [(403,'권한'),(429,'요청이 많')]:
            opener=Mock(); opener.open.side_effect=HTTPError('https://api.figma.com',code,'test',{},None)
            with patch.object(figma_reader,'TOKEN','test-only'),patch.object(figma_reader,'build_opener',return_value=opener):
                with self.assertRaisesRegex(ValueError,fragment): figma_reader.api('files/test')
        b,_=self.batch(1); self.select_confirm(b,0,self.design()); before=dict(self.item(b))
        response={'nodes':{'1:2':{'document':{'id':'1:2','type':'FRAME'}}}}
        with patch.object(figma_reader,'api',side_effect=[response,{'images':{'1:2':None}}]):
            with self.assertRaises(ValueError): figma_reader.fetch(self.s,'https://www.figma.com/design/test/?node-id=1-2')
        self.assertEqual(dict(self.item(b)),before)

    def test_figma_mock_empty_or_oversize_scope(self):
        for children in [[],[{'id':f'1:{i}','type':'FRAME'} for i in range(25)]]:
            response={'nodes':{'1:0':{'document':{'id':'1:0','type':'CANVAS','children':children}}}}
            with patch.object(figma_reader,'api',return_value=response) as api:
                with self.assertRaises(ValueError): figma_reader.fetch(self.s,'https://www.figma.com/design/test/?node-id=1-0')
                self.assertEqual(api.call_count,1)

    def test_legacy_fixture_without_intake_schema_static_render(self):
        import load_fixture
        fixture=Path(__file__).resolve().parents[1]/'mvp0/fixtures/tb-web-001.json'
        legacy=Path(self.tmp.name)/'legacy.db'
        with patch.object(load_fixture,'BASE',Path(self.tmp.name)):
            load_fixture.load(fixture,legacy)
        with storemod.db.connect(legacy) as c:
            self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='intake_item'").fetchone())
            page=c.execute('SELECT uuid FROM inspection_page ORDER BY seq LIMIT 1').fetchone()[0]
            before=c.execute('SELECT COUNT(*) FROM inspection_issue').fetchone()[0]
        with patch.object(portal,'REAL_DB',legacy),patch.object(portal,'UPLOADS',Path(self.tmp.name)/'uploads'):
            body=portal.render_page(page)
            self.assertIn('페이지 상세',body)
            self.assertIn('TB-WEB-001',body)
        with storemod.db.connect(legacy) as c:
            self.assertIsNone(c.execute("SELECT name FROM sqlite_master WHERE name='intake_item'").fetchone())
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_issue').fetchone()[0],before)

    def test_single_existing_photo_returns_original_batch(self):
        b,_=self.batch(3)
        before=set(self.s.uploads.iterdir())
        duplicate=self.s.import_files([('1.png',png())],project_name='독립검증')
        self.assertEqual(duplicate,(b,True))
        self.assertEqual(len(self.s.batches()),1)
        self.assertEqual(len(self.s.batch(b)[1]),3)
        self.assertEqual(set(self.s.uploads.iterdir()),before)

    def test_mixed_existing_and_new_photos_rejected_without_save(self):
        b,_=self.batch(3)
        before=set(self.s.uploads.iterdir())
        with self.assertRaises(ValueError):
            self.s.import_files([('1.png',png()),('new.png',png())],project_name='독립검증')
        self.assertEqual(len(self.s.batches()),1)
        self.assertEqual(len(self.s.batch(b)[1]),3)
        self.assertEqual(set(self.s.uploads.iterdir()),before)

    def test_three_level_unconfirmed_confirm_and_back_flow(self):
        import intake_ui
        from urllib.parse import urlencode
        b,_=self.batch(3); first=self.item(b)
        groups=self.s.screen_groups()
        self.assertEqual(len(groups),1)
        self.assertEqual((groups[0]['page_count'],groups[0]['confirmed']),(3,0))
        self.assertEqual(self.s.page_destination(first['id']),f'/intake/{b}/connect?item={first["id"]}')
        with patch.object(portal,'REAL_DB',self.s.database),patch.object(portal,'UPLOADS',self.s.uploads):
            body=portal.render_list(False,None)
            self.assertEqual(body.count('>로그인</a>'),1)
            self.assertIn(groups[0]['href'],body)
            listing=intake_ui.page_list(self.s,b,first['id'])
            for idx in range(3): self.assertIn(f'상태{idx}',listing)
            detail=intake_ui.connect_page(self.s,b,first['id'])
            self.assertIn('<dialog id="design-picker">',detail)
            self.assertNotIn('<aside class="states"',detail)
            self.assertIn('review-scroll',detail)
            d=self.design(); self.s.select_design(first['id'],first['revision'],d)
            r=self.item(b)
            h=Handler(urlencode({'csrf':intake_http.CSRF,'item':r['id'],'revision':r['revision']}).encode())
            intake_http.post(h,self.s,f'/intake/{b}/confirm')
            self.assertEqual(h.code,303)
            r=self.item(b); self.assertTrue(r['page_id'])
            self.assertEqual(h.location,self.s.page_destination(r['id']))
            self.assertTrue(h.location.startswith('/screen/'))
            self.assertFalse(self.item(b,1)['page_id'])
            body=portal.render_list(False,None)
            self.assertEqual(body.count('>로그인</a>'),1)
            self.assertIn('짝 확인 1/3',body)
            with self.s.connect() as c:
                sid=c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?',(r['page_id'],)).fetchone()[0]
                self.assertIsNone(c.execute('SELECT pass_fail FROM inspection_run WHERE page_id=?',(r['page_id'],)).fetchone()[0])
            back=portal.render_screen(sid)
            for idx in range(3): self.assertIn(f'상태{idx}',back)
            self.assertIn(self.s.page_destination(self.item(b,1)['id']),back)

    def test_screen_groups_separate_names_and_excluded(self):
        b,_=self.batch(3)
        r=self.item(b,1); self.s.edit_item(r['id'],r['revision'],'다른 화면','단계','held','시안 대기')
        r=self.item(b,2); self.s.edit_item(r['id'],r['revision'],'제외 화면','단계','excluded','본문 없음')
        groups=self.s.screen_groups()
        self.assertEqual({g['name'] for g in groups},{'로그인','다른 화면'})
        self.assertTrue(all(g['page_count']==1 for g in groups))

    def test_legacy_alias_and_waiting_issues_remain_visible_unchanged(self):
        import load_fixture
        fixture=Path(__file__).resolve().parents[1]/'mvp0/fixtures/tb-web-001.json'
        legacy=Path(self.tmp.name)/'categories.db'
        with patch.object(load_fixture,'BASE',Path(self.tmp.name)):
            load_fixture.load(fixture,legacy)
        with storemod.db.connect(legacy) as c:
            page=c.execute('SELECT page_id FROM inspection_issue GROUP BY page_id ORDER BY COUNT(*) DESC LIMIT 1').fetchone()[0]
            issues=c.execute('SELECT uuid FROM inspection_issue WHERE page_id=? LIMIT 3',(page,)).fetchall()
            for row,state,cat in zip(issues,['보류','수정완료','발견'],['typography','layout','color']):
                c.execute('UPDATE inspection_issue SET status=?,category=? WHERE uuid=?',(state,cat,row[0]))
                c.execute('UPDATE issue_history SET to_status=? WHERE issue_id=?',(state,row[0]))
            before=[tuple(r) for r in c.execute('SELECT * FROM inspection_issue ORDER BY uuid')]
            histories=[tuple(r) for r in c.execute('SELECT * FROM issue_history ORDER BY uuid')]
        with patch.object(portal,'REAL_DB',legacy),patch.object(portal,'UPLOADS',Path(self.tmp.name)/'uploads'):
            body=portal.render_page(page,1)
            self.assertIn('수정필요',body)        # 보류·대기 지적도 '수정필요' 칸에 남는다
            self.assertIn('처리됨',body)
            for row in issues: self.assertIn('issue-'+row[0],body)
        with storemod.db.connect(legacy) as c:
            self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM inspection_issue ORDER BY uuid')],before)
            self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM issue_history ORDER BY uuid')],histories)

    def test_confirmed_page_design_dialog_keeps_existing_detail(self):
        from urllib.parse import urlencode
        b,_=self.batch(1); self.select_confirm(b,0,self.design()); self.s.start(b)
        r=self.item(b); destination=self.s.page_destination(r['id'])
        h=Handler(b''); intake_http.get(h,self.s,f'/intake/{b}/connect',{'item':[r['id']]})
        self.assertEqual(h.code,303)
        self.assertEqual(h.location,destination)
        with patch.object(portal,'REAL_DB',self.s.database),patch.object(portal,'UPLOADS',self.s.uploads):
            body=portal.render_page(r['page_id'])
            self.assertIn('<dialog id="design-picker">',body)
            self.assertIn('다른 시안으로 변경</button>',body)
            self.assertIn('id="cards"',body)
            self.assertNotIn('아직 등록된 검수 내용이 없습니다.',body)
        with patch.object(figma_reader,'TOKEN',''),patch.object(figma_reader,'fetch',return_value=(['mock-id'],0)):
            for action,extra in [('fetch',{'link':'https://www.figma.com/design/test/?node-id=1-1'}),('token',{'token':'test-only'})]:
                h=Handler(urlencode(dict(csrf=intake_http.CSRF,item=r['id'],**extra)).encode())
                intake_http.post(h,self.s,f'/intake/{b}/{action}')
                self.assertEqual(h.code,303)
                self.assertTrue(h.location.startswith(destination+'?designs=1&notice='))
        self.assertEqual(self.item(b)['status'],'confirmed')
        self.assertEqual(self.item(b)['page_id'],r['page_id'])

    def test_legacy_confirmed_without_page_can_open_selected_page(self):
        import intake_ui
        from urllib.parse import urlencode
        b,_=self.batch(2); d=self.design()
        self.select_confirm(b,0,d); self.select_confirm(b,1,d)
        r=self.item(b,1); self.assertIsNone(r['page_id'])
        body=intake_ui.connect_page(self.s,b,r['id'])
        self.assertIn('확인한 페이지 검수 열기',body)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':r['id']}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/start')
        self.assertEqual(h.code,303)
        self.assertEqual(h.location,self.s.page_destination(r['id']))
        self.assertNotEqual(h.location,self.s.page_destination(self.item(b,0)['id']))
        self.assertEqual(self.item(b,1)['status'],'confirmed')
        other,_=self.s.import_files([('other.png',png())],project_name='독립검증')
        alien=self.item(other)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':alien['id']}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/start')
        self.assertEqual(h.code,400)
        self.assertIsNone(self.item(other)['page_id'])
        h=Handler(b''); intake_http.get(h,self.s,f'/intake/{b}/screen/{alien["id"]}',{})
        self.assertEqual(h.code,404)

    def test_platform_layout_consistent_before_after_registration_and_read_only(self):
        import intake_ui
        for platform in ['android','ios','web','mobile-web']:
            with self.subTest(platform=platform):
                b,_=self.s.import_files([(platform+'.png',png())],project_name='배치검증',platform=platform)
                r=self.item(b)
                with self.s.connect() as c: before=''.join(c.iterdump())
                prepared=intake_ui.connect_page(self.s,b,r['id'])
                with self.s.connect() as c: self.assertEqual(''.join(c.iterdump()),before)
                self.select_confirm(b,0,self.design()); self.s.start(b)
                r=self.item(b)
                with self.s.connect() as c: before=''.join(c.iterdump())
                with patch.object(portal,'REAL_DB',self.s.database),patch.object(portal,'UPLOADS',self.s.uploads):
                    registered=portal.render_page(r['page_id'])
                with self.s.connect() as c: self.assertEqual(''.join(c.iterdump()),before)
                for body in [prepared,registered]:
                    if platform in ['android','ios']:
                        self.assertIn('<body class="app-view">',body)
                        self.assertIn('<div class="app-workspace">',body)
                        self.assertIn('<aside class="app-sidebar">',body)
                        self.assertIn('grid-template-columns:minmax(0,1fr) 340px',body)
                        self.assertIn('@media(max-width:1000px)',body)
                        self.assertIn('height:80vh',body)
                    else:
                        self.assertIn('<body class="web-view">',body)
                        self.assertNotIn('<aside class="app-sidebar">',body)
                        self.assertNotIn('<div class="app-workspace">',body)
                        self.assertIn('height:46vh',body)

    def test_comparison_javascript_mock_coordinates_and_controls(self):
        import comparison_view
        import subprocess
        result=subprocess.run(['node',str(Path(__file__).with_name('comparison_view_mock.js'))],input=comparison_view.JS,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_unified_renderer_draft_selection_registration_and_reselection(self):
        import intake_ui
        from urllib.parse import urlencode
        b,_=self.batch(1); r=self.item(b)
        with self.s.connect() as c: before=''.join(c.iterdump())
        blank=intake_ui.connect_page(self.s,b,r['id'])
        with self.s.connect() as c: self.assertEqual(''.join(c.iterdump()),before)
        self.assertIn('Figma 디자인을 연결해 주세요.',blank)
        styles=blank.split('<style>',1)[1].split('</style>',1)[0]
        def check_shape(body):
            self.assertEqual(body.split('<style>',1)[1].split('</style>',1)[0],styles)
            for marker in ['class="cols"','id="cards"','class="tabbar"','<dialog id="design-picker">','window.qaCompareIssue']:
                self.assertIn(marker,body)
        check_shape(blank)
        d=self.design(); self.s.select_design(r['id'],r['revision'],d)
        chosen=intake_ui.connect_page(self.s,b,r['id']);check_shape(chosen)
        self.assertIn('이 짝으로 확인',chosen)
        self.assertIsNone(self.item(b)['page_id'])
        r=self.item(b)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':r['id'],'revision':r['revision']}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/confirm');self.assertEqual(h.code,303)
        r=self.item(b);page=r['page_id']
        registered=portal.render_page(page,store=self.s);check_shape(registered)
        self.assertNotIn('이 짝으로 확인',registered)
        with self.s.connect() as c:
            old=c.execute('SELECT design_img FROM inspection_page WHERE uuid=?',(page,)).fetchone()[0]
        self.s.select_design(r['id'],r['revision'],self.design('9:9'))
        with self.s.connect() as c: before=''.join(c.iterdump())
        pending=portal.render_page(page,store=self.s);check_shape(pending)
        self.assertIn('이 짝으로 확인',pending)
        self.assertNotIn('src="/uploads/'+old,pending.split('<dialog')[0])
        with self.s.connect() as c:
            self.assertEqual(''.join(c.iterdump()),before)
            self.assertEqual(c.execute('SELECT design_img FROM inspection_page WHERE uuid=?',(page,)).fetchone()[0],old)
        r=self.item(b)
        h=Handler(urlencode({'csrf':intake_http.CSRF,'item':r['id'],'revision':r['revision']}).encode())
        intake_http.post(h,self.s,f'/intake/{b}/confirm');self.assertEqual(h.code,303)
        self.assertEqual(self.item(b)['page_id'],page)
        check_shape(portal.render_page(page,store=self.s))
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_page').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM inspection_issue').fetchone()[0],0)

    def test_recommendation_pending_protected_and_user_override_history(self):
        import intake_ui
        b,_=self.batch(3); d=self.design(); r=self.item(b)
        reason='<script>추천 사유</script>'
        self.s.select_design(r['id'],r['revision'],d,recommendation=reason)
        r=self.item(b)
        self.assertEqual(r['status'],'pending');self.assertIsNone(r['page_id'])
        self.assertEqual(self.s.recommendation(r['id']),reason)
        with self.assertRaises(ValueError): self.s.start(b)
        with self.assertRaises(ValueError): self.s.select_design(r['id'],r['revision'],d,recommendation='덮어쓰기')
        body=intake_ui.connect_page(self.s,b,r['id'])
        self.assertIn('추천 연결 · 확인 대기',body)
        self.assertNotIn(reason,body)
        self.assertIn('&lt;script&gt;추천 사유&lt;/script&gt;',body)
        self.s.select_design(r['id'],r['revision'],self.design('7:7'))
        self.assertEqual(self.s.recommendation(r['id']),'')
        self.assertEqual(self.item(b)['status'],'pending')
        self.assertIn('추천 연결',[e['action'] for e in self.s.batch(b)[2]])
        for idx,status in [(1,'held'),(2,'excluded')]:
            r=self.item(b,idx);self.s.edit_item(r['id'],r['revision'],'로그인',r['state_name'],status,'대기')
            r=self.item(b,idx)
            with self.assertRaises(ValueError): self.s.select_design(r['id'],r['revision'],d,recommendation='추천')
        r=self.item(b);self.s.confirm(r['id'],r['revision']);r=self.item(b)
        with self.assertRaises(ValueError): self.s.select_design(r['id'],r['revision'],d,recommendation='추천')

    def test_picker_retains_current_snapshot_after_same_node_refresh(self):
        import intake_ui,re
        b,_=self.batch(1);old=self.design();self.select_confirm(b,0,old)
        new=self.design()  # Same Figma node, newer snapshot must not replace current preview.
        r=self.item(b);body=intake_ui.design_dialog(self.s,b,r)
        radios=re.findall(r'<input type="radio"[^>]+>',body)
        self.assertTrue(radios)
        self.assertIn('value="'+old+'"',radios[0])
        self.assertIn('checked',radios[0])
        self.assertTrue(any('value="'+new+'"' in radio for radio in radios))
        self.assertEqual(self.item(b)['design_id'],old)

    def test_picker_radio_preview_has_no_submit_and_fixed_capture(self):
        import intake_ui,re,subprocess
        b,_=self.batch(1);self.design();r=self.item(b)
        with self.s.connect() as c: before=''.join(c.iterdump())
        body=intake_ui.design_dialog(self.s,b,r)
        script=re.findall(r'<script>(.*?)</script>',body,re.S)[-1]
        harness="""const vm=require('node:vm'),assert=require('node:assert/strict');let change,close,resetCount=0;
const design={src:'old'},name={textContent:'old'},capture={src:'fixed'};
const elements={'design-picker':{addEventListener(k,fn){if(k==='change')change=fn;else if(k==='close')close=fn},querySelector(q){if(q==='form')return {reset(){resetCount++}};return {dataset:{src:'old',name:'old'}}}},'pick-design-image':design,'pick-design-name':name};
const context={document:{getElementById(id){return elements[id]}},fetch(){throw Error('network forbidden')}};
vm.runInNewContext(SOURCE,context);
change({target:{name:'design',dataset:{src:'new.png',name:'<img onerror=alert(1)>'}}});
assert.equal(design.src,'new.png');assert.equal(name.textContent,'<img onerror=alert(1)>');assert.equal(capture.src,'fixed');
close();assert.equal(resetCount,1);assert.equal(design.src,'old');assert.equal(name.textContent,'old');
""".replace('SOURCE',json.dumps(script))
        result=subprocess.run(['node','-e',harness],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.s.connect() as c:self.assertEqual(''.join(c.iterdump()),before)
        self.assertIn('action="/intake/'+b+'/select"',body)
        self.assertIn('/uploads/'+r['filename'],body)

    def test_html_escapes_user_names(self):
        import intake_ui
        b,_=self.batch(1); r=self.item(b)
        self.s.edit_item(r['id'],r['revision'],'<script>alert(1)</script>','<img src=x>','include','')
        body=intake_ui.batch_page(self.s,b)
        self.assertNotIn('<script>alert(1)</script>',body)
        self.assertIn('&lt;script&gt;',body)

if __name__=='__main__': unittest.main(verbosity=2)
