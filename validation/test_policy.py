"""검수 정책 층(시스템 → 서비스 → 화면 → 요소) 검증 — 값이 겹치는 순서, 이력 보존, 검수기로 넘어가는 모양."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import intake_store as storemod
import auto_inspect
import policy as policymod
from test_auto_inspect import png, REST_DOC


class Layers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='policy-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        self.pol = policymod.Policy(self.s)
        with self.s.connect() as c:
            c.execute("INSERT INTO project VALUES ('p1','버스')")
            c.execute("INSERT INTO project VALUES ('p2','관제')")
            c.execute("INSERT INTO screen(uuid,project_id,human_key,name,platform,states) VALUES ('s1','p1','BUS-AND-001','로그인','android','[]')")
            c.execute("INSERT INTO screen(uuid,project_id,human_key,name,platform,states) VALUES ('s2','p1','BUS-AND-002','홈','android','[]')")

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_then_layers_override_in_order(self):
        with self.s.connect() as c:
            r = self.pol.resolve(c, 's1')
            self.assertEqual((r['values']['topGap.minPx'], r['source']['topGap.minPx']), (6, 'default'))
            self.pol.set(c, 'system', 'topGap.minPx', 8, actor='river')
            self.pol.set(c, 'service', 'topGap.minPx', 4, target='p1')
            self.assertEqual(self.pol.resolve(c, 's1')['values']['topGap.minPx'], 4)          # 서비스가 시스템을 덮음
            self.assertEqual(self.pol.resolve(c, 's1')['source']['topGap.minPx'], 'service')
            self.pol.set(c, 'screen', 'topGap.minPx', 10, target='s1')
            self.assertEqual(self.pol.resolve(c, 's1')['values']['topGap.minPx'], 10)         # 화면이 서비스를 덮음
            self.assertEqual(self.pol.resolve(c, 's2')['values']['topGap.minPx'], 4)          # 같은 서비스 다른 화면은 서비스 값
            self.assertEqual(self.pol.resolve(c, project_id='p2')['values']['topGap.minPx'], 8)  # 다른 서비스는 시스템 값
            self.pol.set(c, 'screen', 'topGap.minPx', None, target='s1')                      # 화면 예외를 거두면 서비스 값으로
            self.assertEqual(self.pol.resolve(c, 's1')['values']['topGap.minPx'], 4)

    def test_history_is_kept_and_same_value_not_repeated(self):
        with self.s.connect() as c:
            a = self.pol.set(c, 'screen', 'screen.type', 'common', target='s1', actor='river')
            b = self.pol.set(c, 'screen', 'screen.type', 'common', target='s1', actor='river')  # 같은 값은 쌓지 않음
            self.pol.set(c, 'screen', 'screen.type', 'data', target='s1', actor='river')
            self.assertIsNotNone(a); self.assertIsNone(b)
            rows = c.execute("SELECT value FROM policy_rule WHERE scope='screen' ORDER BY rowid").fetchall()
            self.assertEqual([json.loads(r['value']) for r in rows], ['common', 'data'])
            with self.assertRaises(Exception):
                c.execute("DELETE FROM policy_rule")                                           # 이력은 지울 수 없다
            with self.assertRaises(ValueError):
                self.pol.set(c, 'system', 'text.variable', True)                              # 요소 규칙은 시스템 층에 못 둠
            with self.assertRaises(ValueError):
                self.pol.set(c, 'screen', 'topGap.minPx', 'abc', target='s1')                 # 숫자가 아님
            with self.assertRaises(ValueError):
                self.pol.set(c, 'screen', 'no.such.rule', 1, target='s1')

    def test_engine_policy_shape_and_figma_mirror(self):
        with self.s.connect() as c:
            mirror = {'screenType': 'common', 'variable': {'n1': True}}
            p = self.pol.engine_policy(c, 's1', mirror)
            self.assertEqual((p['screenType'], p['variable'], p['topGapMinPx']), ('common', {'n1': True}, 6))  # 포털 행이 없으면 거울 값
            self.pol.set(c, 'screen', 'screen.type', 'data', target='s1')
            self.pol.set(c, 'element', 'text.variable', False, target='s1', key='n1')
            self.pol.set(c, 'element', 'element.exclude', True, target='s1', key='n9')
            p = self.pol.engine_policy(c, 's1', mirror)
            self.assertEqual(p['screenType'], 'data')                                          # 포털 행이 거울을 이김
            self.assertEqual(p['variable'], {'n1': False})
            self.assertEqual(list(p['exclude']), ['n9'])
            self.pol.set(c, 'service', 'range.top', 99, target='p1')
            self.assertEqual(self.pol.capture_range(c, 's1'), (99, None))


class Remember(unittest.TestCase):
    """페이지 상세에서 후보를 가변·제외로 내리면 요소 층에 쌓이고, 다음 재료에 실려 검수기로 간다."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='policy-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        self.auto = auto_inspect.Auto(self.s)
        rows = [{'파일': '0.png', '화면이름': '로그인', '상태': '기본'}]
        self.b = self.s.import_files([('찍은목록.json', json.dumps({'촬영본': rows}).encode()), ('0.png', png())], project_name='정책검증')[0]
        self.d = self.s.add_design('fkey', '1:1', '웹_로그인 화면', 'https://www.figma.com/design/fkey/?node-id=1-1', '1:0', png(),
                                   qa_settings={'policy': {'screenType': 'common', 'variable': {'1:3': False}}})
        r = self.s.batch(self.b)[1][0]; self.s.select_design(r['id'], r['revision'], self.d)
        r = self.s.batch(self.b)[1][0]; self.s.confirm(r['id'], r['revision'])
        self.s.start(self.b)
        self.page = self.s.batch(self.b)[1][0]['page_id']
        with self.s.connect() as c:
            self.run = c.execute('SELECT * FROM inspection_run WHERE page_id=?', (self.page,)).fetchone()

    def tearDown(self):
        self.tmp.cleanup()

    def materials(self):
        with patch('figma_reader.api', return_value={'nodes': {'1:1': {'document': REST_DOC}}, 'version': '7'}):
            return self.auto.materials(self.page, self.run['uuid'])

    def test_decisions_become_element_policy_and_reach_engine(self):
        m = self.materials()
        self.assertEqual(m['design']['policy']['screenType'], 'common')                       # 거울 값
        self.assertEqual(m['design']['policy']['topGapMinPx'], 6)
        rid = m['autoRunId']
        res = {'autoRunId': rid, 'alignment': {}, 'range': {}, 'notices': [], 'capture': {'w': 1, 'h': 1}, 'candidates': [
            {'no': 1, 'status': 'confirmed', 'kind': 'text', 'label': '글자', 'detail': '', 'confidence': 80, 'rawBox': {'x': 0, 'y': 0, 'w': 1, 'h': 1}, 'designBox': {'x': 0, 'y': 0, 'w': 1, 'h': 1}, 'designNodeIds': ['1:3'], 'designValues': ''},
            {'no': 2, 'status': 'confirmed', 'kind': 'shape', 'label': '모양', 'detail': '', 'confidence': 70, 'rawBox': {'x': 0, 'y': 0, 'w': 1, 'h': 1}, 'designBox': {'x': 0, 'y': 0, 'w': 1, 'h': 1}, 'designNodeIds': ['1:2'], 'designValues': ''}]}
        self.auto.save_result(rid, res)
        with self.s.connect() as c:
            ks = self.auto.candidates(c, rid)
        self.auto.set_status(ks[0]['id'], 'variable', actor='river')
        self.auto.set_status(ks[1]['id'], 'excluded', actor='river')
        pol = policymod.Policy(self.s)
        with self.s.connect() as c:
            got = pol.resolve(c, self.run['screen_id'])
            self.assertEqual(got['elements']['text.variable'], {'1:3': True})                 # 거울(False)보다 사람이 방금 정한 것이 앞
            self.assertEqual(got['elements']['element.exclude'], {'1:2': True})
        p = self.materials()['design']['policy']
        self.assertEqual(p['variable'], {'1:3': True})
        self.assertEqual(list(p['exclude']), ['1:2'])
        self.auto.set_status(ks[1]['id'], 'open', actor='river')                              # 되돌리면 제외가 거둬진다
        p = self.materials()['design']['policy']
        self.assertNotIn('exclude', p)
        with self.s.connect() as c:
            self.assertGreaterEqual(c.execute("SELECT COUNT(*) n FROM policy_rule").fetchone()['n'], 3)  # 이력은 남는다

    def test_screen_range_feeds_capture_trim_but_round_range_wins(self):
        pol = policymod.Policy(self.s)
        with self.s.connect() as c:
            pol.set(c, 'screen', 'range.top', 120, target=self.run['screen_id'])
            c.execute('UPDATE inspection_run SET dev_img_w=1080,dev_img_h=2340 WHERE uuid=?', (self.run['uuid'],))
        m = self.materials()
        self.assertEqual(m['capture'].get('topTrim'), 120)
        self.assertNotIn('bottomTrim', m['capture'])
        self.auto.set_range(self.page, self.run['uuid'], 30, 40, actor='river')                # 차수에 직접 정한 것이 먼저
        m = self.materials()
        self.assertEqual((m['capture']['topTrim'], m['capture']['bottomTrim']), (30, 40))


if __name__ == '__main__':
    unittest.main()
