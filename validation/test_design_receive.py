"""플러그인에서 검수 시안을 바로 받기 — 짝 찾기·새 판 쌓기·페이지 연결·자동 검수 다시 돌기."""
import base64
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import intake_store as storemod
import auto_inspect
import design_receive
import portal


def png(tag=b'\x00\xff\x00\x00'):
    def chunk(k, v):
        return struct.pack('>I', len(v)) + k + v + struct.pack('>I', zlib.crc32(k + v) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(tag)) + chunk(b'IEND', b'')


class Handler:
    def __init__(self, body=b'', method='POST'):
        self.headers = {'Content-Length': str(len(body)), 'Content-Type': 'application/json', 'Host': 'localhost:8765'}
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.code = None
        self.sent = {}
        self.path = ''

    def send_response(self, code): self.code = code
    def send_header(self, k, v): self.sent[k] = v
    def end_headers(self): pass
    def send_error(self, code): self.code = code


class Receive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='receive-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        # 옛 방식 페이지(시안 PNG를 직접 올린 것, 접수함 연결 없음) — 실제 포털 DB 모양
        with self.s.connect() as c:
            c.execute("INSERT INTO project(uuid,name) VALUES('pj','과제')")
            c.execute("INSERT INTO screen(uuid,project_id,human_key,name,platform) VALUES('sc','pj','BUS-AND-001','로그인','android')")
            c.execute("INSERT INTO inspection_page(uuid,screen_id,seq,name,design_img) VALUES('pg','sc',1,'로그인버튼 활성화','old.png')")
            c.execute("INSERT INTO inspection_run(uuid,screen_id,page_id,round,created_at,dev_img,dev_img_w,dev_img_h,coord_ref_w,coord_ref_h) VALUES('run','sc','pg',1,'2026-09-10T00:00:00','dev.png',360,780,360,780)")
        self.page, self.page_name, self.key = 'pg', '로그인버튼 활성화', 'BUS-AND-001'
        self.r = design_receive.Receiver(self.s)

    def tearDown(self):
        self.tmp.cleanup()

    def frame(self, node='7:1', name=None):
        return {'id': node, 'name': name or self.page_name, 'width': 360, 'height': 780, 'png': base64.b64encode(png()).decode(),
                'elements': [{'id': '7:2', 'name': 'label', 'type': 'TEXT', 'kind': 'text', 'box': {'x': 10, 'y': 10, 'w': 60, 'h': 20}, 'depth': 1, 'parentId': '7:1', 'text': '로그인', 'values': {}}],
                'policy': {'screenType': 'common'}}

    def test_status_matches_by_name_then_by_id_after_receive(self):
        st = self.r.frames_status({'fileName': '버스 앱', 'frames': [{'id': '7:1', 'name': self.page_name}, {'id': '7:9', 'name': '없는 화면'}]})
        self.assertEqual(st['frames'][0]['match']['how'], 'name')
        self.assertEqual(st['frames'][0]['match']['page'], self.page)
        self.assertTrue(st['frames'][0]['match']['url'].endswith('/page/' + self.page))
        self.assertIsNone(st['frames'][1]['match'])
        self.assertTrue(any(o['page'] == self.page for o in st['options']))
        self.r.receive({'fileName': '버스 앱', 'page': self.page, 'frame': self.frame()})
        st2 = self.r.frames_status({'fileName': '버스 앱', 'frames': [{'id': '7:1', 'name': '이름 바뀜'}]})
        self.assertEqual(st2['frames'][0]['match']['how'], 'id')      # 한 번 받은 뒤엔 이름이 바뀌어도 id로 찾는다

    def test_receive_stacks_new_version_links_page_and_keeps_history(self):
        before = self.s.page_design(self.page)
        self.assertIsNone(before)
        out = self.r.receive({'fileName': '버스 앱', 'page': self.page, 'frame': self.frame()})
        self.assertTrue(out['url'].endswith('/page/' + self.page))
        with self.s.connect() as c:
            d = c.execute('SELECT * FROM intake_design WHERE id=?', (out['design'],)).fetchone()
            self.assertEqual((d['provider'], d['file_key'], d['node_id']), ('Figma 플러그인', 'name:버스 앱', '7:1'))
            self.assertEqual(json.loads(d['qa_settings']), {'policy': {'screenType': 'common'}})
            self.assertEqual(json.loads(c.execute('SELECT elements FROM design_elements WHERE design_id=?', (out['design'],)).fetchone()['elements'])[0]['text'], '로그인')
            pg = c.execute('SELECT design_img FROM inspection_page WHERE uuid=?', (self.page,)).fetchone()
            ev = c.execute('SELECT from_img,to_img FROM page_design_event WHERE page_id=?', (self.page,)).fetchall()
        self.assertEqual(pg['design_img'], ev[0]['to_img'])
        self.assertNotEqual(ev[0]['from_img'], ev[0]['to_img'])
        # 두 번째 판 — 옛 판은 남고 페이지는 최신 판을 본다
        out2 = self.r.receive({'fileName': '버스 앱', 'page': self.page, 'frame': dict(self.frame(), png=base64.b64encode(png(b'\x00\x00\xff\x00')).decode())})
        with self.s.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) n FROM intake_design WHERE node_id='7:1'").fetchone()['n'], 2)
            self.assertEqual(c.execute('SELECT COUNT(*) n FROM page_design_event WHERE page_id=?', (self.page,)).fetchone()['n'], 2)
        now = self.s.page_design(self.page)
        self.assertEqual(now['new_id'], out2['design'])
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn(now['design_file'], body)

    def test_auto_inspection_restarts_for_new_design_and_keeps_old_result(self):
        with self.s.connect() as c:
            run = c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1', (self.page,)).fetchone()
        auto = auto_inspect.Auto(self.s)
        self.assertIsNone(auto.view(self.page, run))                  # 시안이 PNG뿐이면 자동 검수 없음
        out1 = self.r.receive({'fileName': '버스 앱', 'page': self.page, 'frame': self.frame()})
        m = auto.materials(self.page, run['uuid'])                      # 플러그인이 보낸 요소를 그대로 씀(Figma 토큰 불필요)
        self.assertEqual(m['design']['elements'][0]['text'], '로그인')
        self.assertEqual(m['design']['policy'], {'screenType': 'common', 'topGapMinPx': 6})
        auto.save_result(m['autoRunId'], {'candidates': [{'no': 1, 'status': 'confirmed', 'kind': 'text', 'label': 'x', 'rawBox': {'x': 0, 'y': 0, 'w': 1, 'h': 1}}], 'capture': {'w': 1, 'h': 1}})
        self.assertEqual(auto.view(self.page, run)['run']['status'], 'done')
        out2 = self.r.receive({'fileName': '버스 앱', 'page': self.page, 'frame': self.frame()})
        v = auto.view(self.page, run)
        self.assertEqual(v['run']['status'], 'pending')                # 새 시안 → 다시 돈다
        with self.s.connect() as c:
            rows = c.execute('SELECT design_id,status FROM auto_run ORDER BY rowid').fetchall()
        self.assertEqual([(r['design_id'], r['status']) for r in rows], [(out1['design'], 'done')])  # 옛 결과는 남고, 새 회차는 POST 때 생긴다
        auto.materials(self.page, run['uuid'])
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) n FROM auto_run').fetchone()['n'], 2)
            self.assertEqual(c.execute('SELECT design_id FROM auto_run ORDER BY rowid DESC LIMIT 1').fetchone()['design_id'], out2['design'])

    def test_old_auto_run_table_is_migrated(self):
        root = Path(self.tmp.name)
        s2 = storemod.Store(root / 'old.db', root / 'up2')
        s2.init()
        with s2.connect() as c:
            c.execute("INSERT INTO project(uuid,name) VALUES('pj','과제')")
            c.execute("INSERT INTO screen(uuid,project_id,human_key,name,platform) VALUES('sc','pj','X-1','x','web')")
            c.execute("INSERT INTO inspection_page(uuid,screen_id,seq,name) VALUES('p','sc',1,'x')")
            c.execute("INSERT INTO inspection_run(uuid,screen_id,page_id,round,created_at) VALUES('r','sc','p',1,'2026-09-10')")
            c.executescript('''DROP TABLE auto_run; CREATE TABLE auto_run (id TEXT PRIMARY KEY, page_id TEXT NOT NULL, run_id TEXT NOT NULL,
 status TEXT NOT NULL, engine TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, finished_at TEXT, error TEXT NOT NULL DEFAULT '',
 alignment TEXT NOT NULL DEFAULT '', range TEXT NOT NULL DEFAULT '', notices TEXT NOT NULL DEFAULT '[]', capture_w INTEGER, capture_h INTEGER, UNIQUE(run_id));
 INSERT INTO auto_run(id,page_id,run_id,status,created_at) VALUES('a','p','r','done','2026-09-10');''')
        s2.init()
        with s2.connect() as c:
            cols = [r[1] for r in c.execute('PRAGMA table_info(auto_run)')]
            self.assertIn('design_id', cols)
            self.assertEqual(c.execute('SELECT status,design_id FROM auto_run').fetchone()[:], ('done', ''))
            c.execute("INSERT INTO auto_candidate VALUES ('k','a',1,'text','x','',50,'open','confirmed','',0,0,1,1,'','[]','',NULL)")  # 참조가 새 표를 가리켜야 한다
            self.assertNotIn('auto_run_v0', c.execute("SELECT sql FROM sqlite_master WHERE name='auto_candidate'").fetchone()[0])

    def test_http_cors_and_bad_input(self):
        h = Handler()
        self.assertTrue(design_receive.options(h, '/api/frames'))
        self.assertEqual((h.code, h.sent['Access-Control-Allow-Origin']), (204, '*'))
        self.assertFalse(design_receive.options(Handler(), '/screen/x'))
        body = json.dumps({'fileName': 'f', 'page': self.page, 'frame': {'id': '1:1', 'png': 'bm90cG5n'}}).encode()
        h = Handler(body)
        self.assertTrue(design_receive.post(h, self.s, '/api/design'))
        self.assertIn('PNG', json.loads(h.wfile.getvalue().decode())['error'])
        self.assertEqual(h.sent['Access-Control-Allow-Origin'], '*')
        h = Handler(json.dumps({'fileName': 'f', 'frames': [{'id': '1:1', 'name': self.page_name}]}).encode())
        design_receive.post(h, self.s, '/api/frames')
        self.assertEqual(json.loads(h.wfile.getvalue().decode())['frames'][0]['match']['page'], self.page)


if __name__ == '__main__':
    unittest.main()


class ReplaceCapture(unittest.TestCase):
    """촬영기로 들어온 페이지의 '개발 화면 변경' 팝업 — 같은 접수함 사진 중 고르기."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='replace-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        rows = [{'파일': '0.png', '화면이름': '로그인', '상태': '기본'}, {'파일': '1.png', '화면이름': '로그인', '상태': '버튼 활성화'}]
        files = [('찍은목록.json', json.dumps({'촬영본': rows}).encode()), ('0.png', png()), ('1.png', png(b'\x00\x00\xff\x00'))]
        self.b = self.s.import_files(files, project_name='교체검증')[0]
        d = self.s.add_design('fkey', '1:1', '로그인', 'https://www.figma.com/design/fkey/?node-id=1-1', '1:0', png())
        r = self.s.batch(self.b)[1][0]
        self.s.select_design(r['id'], r['revision'], d)
        r = self.s.batch(self.b)[1][0]
        self.s.confirm(r['id'], r['revision'])
        self.s.start(self.b)
        self.items = self.s.batch(self.b)[1]
        self.page = self.items[0]['page_id']

    def tearDown(self):
        self.tmp.cleanup()

    def run_row(self):
        with self.s.connect() as c:
            return c.execute('SELECT * FROM inspection_run WHERE page_id=? ORDER BY round DESC LIMIT 1', (self.page,)).fetchone()

    def test_popup_lists_batch_photos_and_replaces_current_round(self):
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn('개발 화면 변경', body)
        self.assertIn('id="capture-picker"', body)
        self.assertEqual(body.count('name="capture"'), 2)
        self.assertIn(f'/intake/{self.b}/capture', body)
        before = self.run_row()
        item0, item1 = self.items
        self.s.replace_capture(item0['id'], item0['revision'], item1['id'])
        after = self.run_row()
        self.assertEqual(after['dev_img'], item1['filename'])
        self.assertNotEqual(after['dev_img'], before['dev_img'])
        self.assertEqual(after['round'], before['round'])                 # 같은 차수 안에서 교체
        with self.s.connect() as c:
            ev = c.execute("SELECT detail FROM intake_event WHERE action='개발 화면 변경'").fetchone()
        self.assertEqual(json.loads(ev['detail'])['새 사진'], item1['filename'])
        with self.assertRaises(ValueError):
            self.s.replace_capture(item0['id'], item0['revision'], item1['id'])   # 판이 바뀌었으니 새로고침 필요
        with self.assertRaises(ValueError):
            self.s.replace_capture(item0['id'], item0['revision'] + 1, 'nope')

    def test_after_issue_registered_replacement_needs_new_round(self):
        with self.s.connect() as c:
            sc = c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?', (self.page,)).fetchone()['screen_id']
            c.execute("INSERT INTO inspection_issue(uuid,screen_id,page_id,status,dedup_key) VALUES('i1',?,?,'발견','k1')", (sc, self.page))
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertNotIn('개발 화면 변경', body)
        self.assertIn('바꾸려면 새 차수', body)
        item0, item1 = self.items
        with self.assertRaises(ValueError):
            self.s.replace_capture(item0['id'], item0['revision'], item1['id'])


class ReplaceCaptureLegacy(unittest.TestCase):
    """촬영기가 바로 넣은 페이지(접수함 연결 없음) — 같은 화면 묶음의 사진 중 고르기."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='replace-legacy-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        with self.s.connect() as c:
            c.execute("INSERT INTO project(uuid,name) VALUES('pj','버스')")
            c.execute("INSERT INTO screen(uuid,project_id,human_key,name,platform) VALUES('sc','pj','BUS-AND-001','로그인','android')")
            for i, (pg, name) in enumerate((('p1', '기본'), ('p2', '버튼 활성화'), ('p3', '오류'))):
                c.execute("INSERT INTO inspection_page(uuid,screen_id,seq,name,design_img) VALUES(?,?,?,?,?)", (pg, 'sc', i + 1, name, f'{pg}_design.png'))
                c.execute("INSERT INTO inspection_run(uuid,screen_id,page_id,round,created_at,dev_img,dev_img_w,dev_img_h,coord_ref_w,coord_ref_h) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (f'r{i}', 'sc', pg, 1, '2026-09-10', f'r{i}_dev.png', 360, 780 + i, 360, 780 + i))
        self.r = design_receive.Receiver(self.s)

    def tearDown(self):
        self.tmp.cleanup()

    def test_popup_lists_sibling_photos_and_replaces(self):
        body = portal.render_page('p1', 1, store=self.s)
        self.assertIn('개발 화면 변경', body)
        self.assertIn('/screen/BUS-AND-001/page/p1/capture', body)
        self.assertEqual(body.count('name="capture"'), 3)
        self.assertIn('PNG 업로드', body)                                   # 직접 올리기도 그대로
        self.r.replace_capture('p1', 'r2_dev.png')
        with self.s.connect() as c:
            run = c.execute("SELECT dev_img,dev_img_h,coord_ref_h FROM inspection_run WHERE page_id='p1'").fetchone()
            ev = c.execute("SELECT from_img,to_img FROM page_capture_event WHERE page_id='p1'").fetchone()
        self.assertEqual((run['dev_img'], run['dev_img_h'], run['coord_ref_h']), ('r2_dev.png', 782, 782))
        self.assertEqual((ev['from_img'], ev['to_img']), ('r0_dev.png', 'r2_dev.png'))
        with self.assertRaises(ValueError):
            self.r.replace_capture('p1', 'nope.png')

    def test_blocked_after_issue(self):
        with self.s.connect() as c:
            c.execute("INSERT INTO inspection_issue(uuid,screen_id,page_id,status,dedup_key) VALUES('i1','sc','p1','발견','k')")
        body = portal.render_page('p1', 1, store=self.s)
        self.assertNotIn('개발 화면 변경', body)
        with self.assertRaises(ValueError):
            self.r.replace_capture('p1', 'r1_dev.png')
