"""검수기 플러그인 ↔ 포털 규칙 배선(/api/policy/read·write) 검증.

플러그인은 피그마 프레임 id만 알고 포털의 화면 uuid는 모른다 → (파일 열쇠, 프레임 id)로 화면을 찾는다.
포털이 원본이므로 포털 값이 피그마 프레임의 거울 값을 이긴다.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import intake_store as storemod
import policy as policymod
import policy_api
from test_auto_inspect import png


class Wiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='policyapi-verifier-', dir='/private/tmp')
        root = Path(self.tmp.name)
        self.s = storemod.Store(root / 'test.db', root / 'uploads')
        self.s.init()
        self.pol = policymod.Policy(self.s)
        rows = [{'파일': '0.png', '화면이름': '로그인', '상태': '기본'}]
        self.b = self.s.import_files([('찍은목록.json', json.dumps({'촬영본': rows}).encode()), ('0.png', png())], project_name='배선검증')[0]
        self.d = self.s.add_design('fkey1', '1:1', '로그인 화면', 'https://www.figma.com/design/fkey1/?node-id=1-1', '1:0', png(),
                                   qa_settings={'policy': {'screenType': 'common', 'variable': {'n1': True}}})
        r = self.s.batch(self.b)[1][0]; self.s.select_design(r['id'], r['revision'], self.d)
        r = self.s.batch(self.b)[1][0]; self.s.confirm(r['id'], r['revision'])
        self.s.start(self.b)
        self.page = self.s.batch(self.b)[1][0]['page_id']
        with self.s.connect() as c:
            self.screen = c.execute('SELECT screen_id FROM inspection_page WHERE uuid=?', (self.page,)).fetchone()['screen_id']

    def tearDown(self):
        self.tmp.cleanup()

    def ref(self, **kw):
        return dict({'fileKey': 'fkey1', 'nodeId': '1:1', 'frameName': '로그인'}, **kw)

    def test_read_finds_screen_by_frame_and_portal_beats_figma_mirror(self):
        got = policy_api.read(self.s, self.ref(mirror={'screenType': 'common', 'variable': {'n1': True}}))
        self.assertEqual(got['screen']['id'], self.screen)
        self.assertEqual(got['policy']['screenType'], 'common')          # 포털에 없으면 거울 값
        self.assertEqual(got['policy']['variable'], {'n1': True})
        self.assertEqual(got['policy']['topGapMinPx'], 6)
        with self.s.connect() as c:
            self.pol.set(c, 'screen', 'screen.type', 'data', target=self.screen)
            self.pol.set(c, 'element', 'text.variable', False, target=self.screen, key='n1')
        got = policy_api.read(self.s, self.ref(mirror={'screenType': 'common', 'variable': {'n1': True}}))
        self.assertEqual(got['policy']['screenType'], 'data')            # 포털 행이 거울을 이김
        self.assertEqual(got['policy']['variable'], {'n1': False})

    def test_unknown_frame_is_told_kindly_not_crashed(self):
        got = policy_api.read(self.s, {'fileKey': 'zzz', 'nodeId': '9:9', 'frameName': '없는 화면'})
        self.assertIsNone(got['screen'])
        self.assertIn('검수 화면이 포털에 아직 없어요', got['note'])
        out = policy_api.write(self.s, {'fileKey': 'zzz', 'nodeId': '9:9', 'changes': [{'rule': 'screenType', 'value': 'data'}]})
        self.assertFalse(out['ok'])
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) n FROM policy_rule').fetchone()['n'], 0)

    def test_write_stacks_into_screen_and_element_layers(self):
        out = policy_api.write(self.s, self.ref(actor='river', changes=[
            {'rule': 'screenType', 'value': 'data'},
            {'rule': 'variable', 'key': 'n7', 'value': True},
            {'rule': 'exclude', 'key': 'n8', 'value': True},
            {'rule': 'rangeTop', 'value': 99},
            {'rule': 'rangeBottom', 'value': None}]))
        self.assertTrue(out['ok'])
        self.assertEqual(out['saved'], 4)                                 # rangeBottom은 원래 없던 값을 비운 것이라 안 쌓임
        self.assertEqual(out['policy']['screenType'], 'data')
        self.assertEqual(out['range'], {'top': 99, 'bottom': None})
        with self.s.connect() as c:
            got = self.pol.resolve(c, self.screen)
            self.assertEqual(got['source']['screen.type'], 'screen')
            self.assertEqual(got['elements']['text.variable'], {'n7': True})
            self.assertEqual(got['elements']['element.exclude'], {'n8': True})
            rows = c.execute("SELECT actor,note FROM policy_rule LIMIT 1").fetchall()
            self.assertEqual((rows[0]['actor'], rows[0]['note']), ('river', '검수기 플러그인에서'))

    def test_unknown_rule_is_refused(self):
        with self.assertRaises(ValueError):
            policy_api.write(self.s, self.ref(changes=[{'rule': '아무거나', 'value': 1}]))
        with self.s.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) n FROM policy_rule').fetchone()['n'], 0)

    def test_frame_found_by_name_when_id_differs(self):
        got = policy_api.read(self.s, {'fileKey': 'fkey1', 'nodeId': '9:9', 'frameName': '로그인'})
        self.assertEqual(got['screen']['id'], self.screen)                # 이름이 꼭 하나만 맞을 때만


if __name__ == '__main__':
    unittest.main()
