"""포털 자동 검수(후보) 검증 — 데이터 흐름만. 엔진 결과 자체는 validation-image-qa/repro/portal_parity.js 가 잰다."""
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import intake_store as storemod
import auto_inspect
import figma_elements
import portal
import queries


def png():
    def chunk(k, v):
        return struct.pack('>I', len(v)) + k + v + struct.pack('>I', zlib.crc32(k + v) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')) + chunk(b'IEND', b'')


REST_DOC = {  # Figma REST /nodes 응답의 document 부분(축약)
    'id': '1:1', 'name': '웹_로그인 화면', 'type': 'FRAME', 'absoluteBoundingBox': {'x': 100, 'y': 200, 'width': 400, 'height': 300},
    'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}],
    'children': [
        {'id': '1:2', 'name': 'Button/Primary', 'type': 'INSTANCE', 'absoluteBoundingBox': {'x': 120, 'y': 260, 'width': 200, 'height': 40},
         'fills': [{'type': 'SOLID', 'color': {'r': 0.1451, 'g': 0.388, 'b': 0.922}}], 'strokes': [], 'cornerRadius': 8, 'opacity': 1,
         'children': [
             {'id': '1:3', 'name': 'label', 'type': 'TEXT', 'characters': '로그인', 'absoluteBoundingBox': {'x': 190, 'y': 270, 'width': 60, 'height': 20},
              'fills': [{'type': 'SOLID', 'color': {'r': 1, 'g': 1, 'b': 1}}],
              'style': {'fontFamily': 'Pretendard', 'fontPostScriptName': 'Pretendard-Bold', 'fontWeight': 700, 'fontSize': 14, 'textAlignHorizontal': 'CENTER', 'lineHeightPx': 18.2, 'lineHeightUnit': 'PIXELS'},
              'componentPropertyReferences': {'characters': 'label#12:3'}},
         ]},
        {'id': '1:4', 'name': 'hidden', 'type': 'RECTANGLE', 'visible': False, 'absoluteBoundingBox': {'x': 120, 'y': 320, 'width': 50, 'height': 50}, 'fills': [{'type': 'SOLID', 'color': {'r': 0, 'g': 0, 'b': 0}}]},
        {'id': '1:5', 'name': 'ghost group', 'type': 'GROUP', 'absoluteBoundingBox': {'x': 120, 'y': 400, 'width': 100, 'height': 30}, 'fills': [], 'strokes': [],
         'children': [{'id': '1:6', 'name': 'Vector', 'type': 'VECTOR', 'absoluteBoundingBox': {'x': 120, 'y': 400, 'width': 24, 'height': 24},
                       'fills': [{'type': 'SOLID', 'color': {'r': 0.2, 'g': 0.2, 'b': 0.2}, 'opacity': 0.5}]}]},
        {'id': '1:7', 'name': 'far away', 'type': 'RECTANGLE', 'absoluteBoundingBox': {'x': 900, 'y': 900, 'width': 10, 'height': 10}, 'fills': [{'type': 'SOLID', 'color': {'r': 0, 'g': 0, 'b': 0}}]},
    ],
}


class ElementsMapping(unittest.TestCase):
    def test_rest_tree_to_engine_elements(self):
        got = figma_elements.collect(REST_DOC)
        self.assertEqual(got['frame'], {'id': '1:1', 'name': '웹_로그인 화면', 'width': 400, 'height': 300})
        by = {e['id']: e for e in got['elements']}
        self.assertNotIn('1:1', by)          # 루트 자신은 제외(플러그인과 동일)
        self.assertNotIn('1:4', by)          # 숨김 제외
        self.assertNotIn('1:7', by)          # 프레임 밖 제외
        btn = by['1:2']
        self.assertEqual((btn['kind'], btn['depth'], btn['parentId'], btn['box']), ('shape', 1, '1:1', {'x': 20, 'y': 60, 'w': 200, 'h': 40}))
        self.assertEqual(btn['values']['fill'], '#2563EB')
        self.assertEqual(btn['values']['radius'], 8)
        t = by['1:3']
        self.assertEqual(t['kind'], 'text')
        self.assertEqual(t['chain'], [{'n': 'Button/Primary', 't': 'INSTANCE'}])
        self.assertEqual(t['propRef'], 'label')
        self.assertEqual(t['values']['fontWeight'], 700)
        self.assertEqual(t['values']['lineHeight'], 18.2)
        self.assertEqual(t['values']['color'], '#FFFFFF')
        self.assertEqual(by['1:5']['kind'], 'shape')      # 채움 없는 GROUP도 구역으로 남긴다
        self.assertEqual(by['1:6']['kind'], 'icon')
        self.assertEqual(by['1:6']['values']['fill'], 'rgba(51, 51, 51, 0.5)')


class AutoFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='auto-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        self.auto = auto_inspect.Auto(self.s)
        rows = [{'파일': '0.png', '화면이름': '로그인', '상태': '기본'}]
        files = [('찍은목록.json', json.dumps({'촬영본': rows}).encode()), ('0.png', png())]
        self.b = self.s.import_files(files, project_name='자동검수검증')[0]
        self.d = self.s.add_design('fkey', '1:1', '웹_로그인 화면', 'https://www.figma.com/design/fkey/?node-id=1-1', '1:0', png(),
                                   qa_settings={'policy': {'screenType': 'common', 'variable': {'1:3': False}}})
        r = self.s.batch(self.b)[1][0]
        self.s.select_design(r['id'], r['revision'], self.d)
        r = self.s.batch(self.b)[1][0]
        self.s.confirm(r['id'], r['revision'])
        self.s.start(self.b)
        r = self.s.batch(self.b)[1][0]
        self.page = r['page_id']
        with self.s.connect() as c:
            self.run = c.execute('SELECT * FROM inspection_run WHERE page_id=?', (self.page,)).fetchone()

    def tearDown(self):
        self.tmp.cleanup()

    def dump(self):
        with self.s.connect() as c:
            return ''.join(c.iterdump())

    def result(self):
        return {'autoRunId': None, 'alignment': {'mode': 'anchor', 's': 1, 'tx': 0, 'ty': 0, 'score': .9}, 'range': {'captureTop': 0}, 'notices': ['틀 띠 없음'],
                'capture': {'w': 1, 'h': 1},
                'candidates': [
                    {'no': 1, 'status': 'confirmed', 'kind': 'text', 'label': '글자 내용 차이', 'detail': '디자인 글자: 로그인', 'confidence': 88,
                     'rawBox': {'x': 10, 'y': 20, 'w': 60, 'h': 20}, 'designBox': {'x': 90, 'y': 70, 'w': 60, 'h': 20}, 'designNodeIds': ['1:3'], 'designValues': '14px 700', 'policy': None},
                    {'no': 2, 'status': 'variable', 'kind': 'text', 'label': '가변', 'detail': '', 'confidence': 40,
                     'rawBox': {'x': 0, 'y': 0, 'w': 5, 'h': 5}, 'designBox': None, 'designNodeIds': [], 'designValues': '', 'policy': {'source': 'screen', 'variable': True, 'reason': '일반화면의 글자'}},
                    {'no': 3, 'status': 'confirmed', 'kind': 'missing', 'label': '없어짐', 'detail': '', 'confidence': 70,
                     'rawBox': {'x': 1, 'y': 1, 'w': 8, 'h': 8}, 'designBox': None, 'designNodeIds': ['1:2'], 'designValues': '', 'policy': None},
                ]}

    def test_open_page_is_read_only_and_shows_waiting(self):
        before = self.dump()
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertEqual(self.dump(), before)                     # 페이지를 여는 것만으로는 아무것도 쓰지 않는다
        self.assertIn('data-status="pending"', body)
        self.assertIn('수정필요', body)
        self.assertIn('검수중입니다', body)

    def test_materials_reads_figma_once_and_uses_saved_policy(self):
        with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}, 'version': 'v7'}) as api:
            m = self.auto.materials(self.page, self.run['uuid'])
            m2 = self.auto.materials(self.page, self.run['uuid'])
        self.assertEqual(api.call_count, 1)                        # 두 번째는 저장본
        self.assertEqual(m['autoRunId'], m2['autoRunId'])
        self.assertEqual(m['design']['policy'], {'screenType': 'common', 'variable': {'1:3': False}, 'topGapMinPx': 6})  # 정책 층의 기본값이 함께 실린다
        self.assertEqual((m['design']['width'], m['design']['height']), (400, 300))
        self.assertEqual([e['id'] for e in m['design']['elements']], ['1:2', '1:3', '1:5', '1:6'])
        self.assertTrue(m['capture']['pngUrl'].startswith('/uploads/'))

    def test_materials_without_token_marks_failed_with_reason(self):
        with self.assertRaises(ValueError):
            self.auto.materials(self.page, self.run['uuid'])
        with self.s.connect() as c:
            r = c.execute('SELECT * FROM auto_run').fetchone()
        self.assertEqual(r['status'], 'failed')
        self.assertIn('Figma', r['error'])
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn('다시 시도', body)
        self.auto.retry(self.page, self.run['uuid'])
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM auto_run').fetchone()['status'], 'pending')

    def saved(self):
        with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}}):
            m = self.auto.materials(self.page, self.run['uuid'])
        res = self.result()
        res['autoRunId'] = m['autoRunId']
        self.auto.save_result(m['autoRunId'], res)
        return m['autoRunId']

    def test_save_then_page_shows_candidates_without_issues(self):
        rid = self.saved()
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM auto_run').fetchone()['status'], 'done')
            ks = self.auto.candidates(c, rid)
            self.assertEqual([k['status'] for k in ks], ['open', 'variable', 'open'])
            self.assertEqual(c.execute('SELECT COUNT(*) n FROM inspection_issue WHERE page_id=?', (self.page,)).fetchone()['n'], 0)  # 자동 확정 없음
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn('수정필요 <span class="cnt">2</span>', body)   # 제외 안 한 후보 2건
        self.assertIn('제외 <span class="cnt">1</span>', body)        # 가변으로 자동 분류된 1건
        self.assertIn('auto-overlay', body)
        self.assertIn('class="auto-ex"', body)                       # 카드 오른쪽 위 '제외' 체크
        self.assertIn('"no": 1', body)
        # 같은 결과가 두 번 와도 후보가 늘지 않는다
        res = self.result(); res['autoRunId'] = rid
        self.auto.save_result(rid, res)
        with self.s.connect() as c:
            self.assertEqual(len(self.auto.candidates(c, rid)), 3)

    def test_page_carries_alignment_with_capture_trim(self):
        """나란히 보기가 쓰는 화면 맞춤값 — 엔진이 잘라낸 위쪽 띠를 함께 내려보내야 자리가 맞는다."""
        with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}}):
            m = self.auto.materials(self.page, self.run['uuid'])
        res = self.result()
        res['autoRunId'] = m['autoRunId']
        res['alignment'] = {'mode': 'anchor', 's': 0.5, 'tx': 0, 'ty': 27, 'score': .9}
        res['range'] = {'captureTop': 118, 'captureBottom': 0}
        self.auto.save_result(m['autoRunId'], res)
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn('data-as="0.5"', body)
        self.assertIn('data-aty="27"', body)
        self.assertIn('data-actop="118"', body)   # 맞춤값은 잘린 그림 기준이라 되돌릴 값이 필요하다
        self.assertIn('ctop:Number(st.dataset.actop)', body)

    def test_engine_change_reruns_and_keeps_old_round(self):
        """검수 규칙(엔진 파일)을 고치면 옛 결과를 그대로 보여 주지 않고 새 회차로 다시 돈다."""
        rid = self.saved()
        view = self.auto.view(self.page, self.run)
        self.assertEqual(view['run']['status'], 'done')
        self.assertEqual(len(view['candidates']), 3)
        with patch('auto_inspect.engine_rev', return_value='새규칙지문'):
            view = self.auto.view(self.page, self.run)
            self.assertEqual(view['run']['status'], 'pending')   # 옛 후보를 보여 주지 않는다
            self.assertEqual(view['candidates'], [])
            with self.s.connect() as c:                          # 여는 것만으로는 DB에 쓰지 않는다
                self.assertEqual(c.execute('SELECT COUNT(*) n FROM auto_run').fetchone()['n'], 1)
            with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}, 'version': '7'}):
                m = self.auto.materials(self.page, self.run['uuid'])
            self.assertNotEqual(m['autoRunId'], rid)             # 새 회차로 돈다
            with self.s.connect() as c:
                rows = c.execute('SELECT id,status,engine FROM auto_run ORDER BY rowid').fetchall()
                self.assertEqual([r['status'] for r in rows], ['done', 'pending'])   # 옛 회차는 남는다
                self.assertEqual(rows[-1]['engine'], '새규칙지문')
                self.assertEqual(c.execute('SELECT COUNT(*) n FROM auto_candidate WHERE auto_run_id=?', (rid,)).fetchone()['n'], 3)
        view = self.auto.view(self.page, self.run)               # 규칙이 그대로면 다시 돌리지 않는다
        self.assertEqual(view['run']['status'], 'pending')       # (마지막 회차가 아직 '대기')

    def test_manual_range_reruns_and_feeds_engine(self):
        with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}, 'version': '7'}):
            self.auto.materials(self.page, self.run['uuid'])
            with self.s.connect() as c:
                first = c.execute('SELECT id FROM auto_run').fetchone()['id']
            self.auto.save_result(first, self.result())
            with self.s.connect() as c:
                c.execute('UPDATE inspection_run SET dev_img_w=1080,dev_img_h=2340 WHERE uuid=?', (self.run['uuid'],))  # 픽스처 PNG는 1×1이라 실제 크기를 흉내 낸다
            with self.assertRaises(ValueError):
                self.auto.set_range(self.page, self.run['uuid'], 2000, 400)                # 위·아래를 합치면 화면이 남지 않는다
            new_id = self.auto.set_range(self.page, self.run['uuid'], 120, '40', actor='river')
            with self.s.connect() as c:
                rows = c.execute('SELECT id,status FROM auto_run ORDER BY rowid').fetchall()
                self.assertEqual([r['status'] for r in rows], ['done', 'pending'])        # 옛 회차는 남고 새 회차가 '대기'
                self.assertEqual(rows[-1]['id'], new_id)
                self.assertEqual(c.execute('SELECT COUNT(*) n FROM auto_candidate WHERE auto_run_id=?', (first,)).fetchone()['n'], 3)
                rng = c.execute('SELECT top,bottom,actor FROM auto_range').fetchone()
                self.assertEqual((rng['top'], rng['bottom'], rng['actor']), (120, 40, 'river'))
            m = self.auto.materials(self.page, self.run['uuid'])
            self.assertEqual(m['autoRunId'], new_id)
            self.assertEqual((m['capture']['topTrim'], m['capture']['bottomTrim']), (120, 40))  # 사람이 정한 범위가 엔진으로 간다
            view = self.auto.view(self.page, self.run)
            self.assertEqual(view['run']['status'], 'pending')
            self.assertEqual((view['range']['manual_top'], view['range']['manual_bottom']), (120, 40))
            self.auto.set_range(self.page, self.run['uuid'], None, None)               # 자동으로 되돌리기
            m = self.auto.materials(self.page, self.run['uuid'])
            self.assertNotIn('topTrim', m['capture'])
            with self.assertRaises(ValueError):
                self.auto.set_range(self.page, self.run['uuid'], -1, 0)

    def test_status_change_keeps_history_and_register_makes_issue(self):
        rid = self.saved()
        with self.s.connect() as c:
            k1, k2, k3 = self.auto.candidates(c, rid)
        self.auto.set_status(k1['id'], 'excluded', actor='river', note='브라우저 틀')
        self.auto.set_status(k1['id'], 'open', actor='river')
        with self.assertRaises(ValueError):
            self.auto.set_status(k1['id'], 'nope')
        with self.s.connect() as c:
            ev = c.execute('SELECT from_status,to_status FROM auto_candidate_event WHERE candidate_id=? ORDER BY at,rowid', (k1['id'],)).fetchall()
            self.assertEqual([tuple(e) for e in ev], [('open', 'excluded'), ('excluded', 'open')])
        with self.assertRaises(ValueError):
            self.auto.register(k2['id'], 'river', 1)                # 가변으로 둔 후보는 바로 등록 못 함
        issue = self.auto.register(k1['id'], 'river', 1)
        self.assertEqual(self.auto.register(k1['id'], 'river', 1), issue)   # 두 번 눌러도 하나
        with self.s.connect() as c:
            i = c.execute('SELECT * FROM inspection_issue WHERE uuid=?', (issue,)).fetchone()
            self.assertEqual((i['status'], i['category'], i['found_round'], i['page_id']), ('발견', 'text', 1, self.page))
            self.assertEqual(i['dedup_key'], f'{self.page}|1:3|text|auto')
            self.assertEqual((i['box_x'], i['box_y'], i['box_w'], i['box_h']), (10, 20, 60, 20))
            h = queries.history_of_issue(c, issue)
            self.assertEqual(len(h), 1)
            self.assertEqual((h[0]['from_status'], h[0]['to_status'], h[0]['actor'], h[0]['round']), (None, '발견', 'river', 1))
            self.assertEqual(c.execute('SELECT issue_id FROM auto_candidate WHERE id=?', (k1['id'],)).fetchone()['issue_id'], issue)
        with self.assertRaises(ValueError):
            self.auto.set_status(k1['id'], 'excluded')                # 등록된 뒤에는 지적 쪽에서 처리
        body = portal.render_page(self.page, 1, store=self.s)
        self.assertIn('지적 #1로 등록됨', body)
        self.assertIn('수정필요 <span class="cnt">2</span>', body)   # 등록된 지적 1 + 남은 후보 1
        self.assertIn('id="pin-' + issue, body)                     # 사람이 등록한 것만 핀이 된다
        self.assertNotIn('id="pin-' + k3['id'], body)

    def test_engine_page_is_plugin_ui_with_portal_handle(self):
        html = auto_inspect.engine_html()
        self.assertIn('function comparePair(', html)
        self.assertIn('window.__portal=true', html)
        self.assertNotIn(auto_inspect.ENGINE_MARKER, html)


if __name__ == '__main__':
    unittest.main()
