"""후보 카드 본문 검증 — 기준·지금·자리가 줄로 갈라지고, 같은 말이 두 번 나오지 않는지."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import card_view


def 후보(**바꿀것):
    k = {'id': 'c1', 'no': 3, 'kind': 'value', 'label': '요소의 모양 또는 크기가 다름 — 상자',
         'detail': '', 'confidence': 90, 'status': 'open', 'policy': '{}',
         'box_x': 0, 'box_y': 777, 'box_w': 1920, 'box_h': 123,
         'design_box': '{}', 'design_node_ids': '[]', 'design_values': '', 'issue_id': None}
    k.update(바꿀것)
    return k


def 시안(요소들):
    """요소 자료를 uploads 자리에 두고, 그 자리를 쓰는 (page_id, 인자) 한 벌."""
    방 = tempfile.mkdtemp()
    (Path(방) / 'p1_design.json').write_text(json.dumps({'틀': {'폭': 1920, '높이': 1080}, '요소': 요소들},
                                                        ensure_ascii=False), encoding='utf-8')
    card_view._요소캐시.clear()
    return 'p1', {'database': str(Path(방) / '없는.db'), 'uploads': 방}


class 카드(unittest.TestCase):
    def test_값후보는_지금과_기준을_따로_적는다(self):
        k = 후보(policy=json.dumps({'source': 'value', '키': '값다름|n1|#footer|box.h',
                                    '줄': [{'이름': '높이', '기준': '120px', '개발': '123px'}],
                                    '자리': '#footer'}, ensure_ascii=False))
        줄, 자리, 안내, 잰것 = card_view.줄뽑기(k)
        self.assertTrue(잰것)
        self.assertEqual(자리, '#footer')
        self.assertEqual(줄, [{'이름': '높이', '기준': '120px', '개발': '123px'}])

    def test_옛_글월도_같은_줄로_읽는다(self):
        k = 후보(policy=json.dumps({'source': 'value', '키': '값다름|n1|#footer|box.h'}, ensure_ascii=False),
                detail='높이 120px → 123px · 배경색 #FFFFFF → transparent / 개발 자리 #footer',
                design_values='높이 120px · 배경색 #FFFFFF')
        줄, 자리, _, 잰것 = card_view.줄뽑기(k)
        self.assertEqual(자리, '#footer')
        self.assertEqual(줄, [{'이름': '높이', '기준': '120px', '개발': '123px'},
                              {'이름': '배경색', '기준': '#FFFFFF', '개발': 'transparent'}])

    def test_기준값을_두_번_적지_않는다(self):
        k = 후보(policy=json.dumps({'source': 'value', '키': '값다름|n1|#footer|box.h'}, ensure_ascii=False),
                detail='높이 120px → 123px / 개발 자리 #footer', design_values='높이 120px')
        본문 = card_view.body_html(k, None)
        self.assertNotIn('디자인 원본값', 본문)
        self.assertEqual(본문.count('120px'), 1)
        self.assertIn('지금 개발', 본문)
        self.assertIn('디자인 기준', 본문)
        self.assertIn('개발이 볼 자리', 본문)

    def test_그림후보는_기준만_줄로_펴고_눈대조를_알린다(self):
        k = 후보(kind='text', label='글자 내용 또는 표기가 다르게 보입니다.',
                detail='디자인 글자: “통근버스” — 개발 캡처의 글자와 눈으로 대조해 주세요.',
                design_values='크기 16 · 굵기 700 · 글꼴 Pretendard · 색 #000000\n170×24 · 둥글기 0',
                policy=json.dumps({'source': 'role', 'reason': '고정 문구 자리 (gnb)'}, ensure_ascii=False))
        줄, 자리, 안내, 잰것 = card_view.줄뽑기(k)
        self.assertFalse(잰것)
        self.assertEqual(안내, '개발 캡처의 글자와 눈으로 대조해 주세요.')
        self.assertEqual(줄[0], {'이름': '글자', '기준': '“통근버스”', '개발': None})
        self.assertIn({'이름': '글꼴', '기준': 'Pretendard', '개발': None}, 줄)
        self.assertIn({'이름': '글자색', '기준': '#000000', '개발': None}, 줄)
        본문 = card_view.body_html(k, None)
        self.assertIn('눈으로 대조', 본문)
        self.assertIn('규칙 · 고정 문구 자리 (gnb)', 본문)

    def test_간격_후보는_개발_어림값을_같은_줄에_붙인다(self):
        k = 후보(kind='spacing', label='컴포넌트 사이의 세로 간격이 다릅니다.', detail='',
                design_values='디자인 간격 24px · 개발 이미지 약 30px')
        줄, _, _, _ = card_view.줄뽑기(k)
        self.assertEqual(줄, [{'이름': '간격', '기준': '24px', '개발': '약 30px'}])

    def test_토큰과_컴포넌트_이름이_있으면_그_이름을_보여준다(self):
        page, 자리 = 시안([
            {'id': 'btn', 'name': 'C/BTN/basic_L', 'kind': 'shape', 'parentId': None,
             'component': {'name': 'Property 1=solid', 'set': 'C/BTN/basic_L', 'props': {'Property 1': 'solid'}},
             'values': {'fill': '#F5F5F5'}, '토큰': {'fill': 'color/bg/disabled'}},
        ])
        k = 후보(design_node_ids=json.dumps(['btn']),
                policy=json.dumps({'source': 'value', '키': '값다름|btn|.btn|backgroundColor',
                                    '줄': [{'이름': '배경색', '기준': '#F5F5F5', '개발': '#FFFFFF'}],
                                    '자리': '.btn'}, ensure_ascii=False))
        본문 = card_view.body_html(k, page, **자리)
        self.assertIn('color/bg/disabled', 본문)        # 토큰 이름
        self.assertIn('C/BTN/basic_L · solid', 본문)     # 컴포넌트 이름
        self.assertIn('#F5F5F5', 본문)                   # 레거시 값도 함께

    def test_토큰이_없으면_헥사만_보인다(self):
        page, 자리 = 시안([{'id': 'box', 'name': 'Rectangle 3', 'kind': 'shape', 'parentId': None,
                          'values': {'fill': '#D9D9D9'}}])
        k = 후보(design_node_ids=json.dumps(['box']),
                policy=json.dumps({'source': 'value', '키': '값다름|box|.x|backgroundColor',
                                    '줄': [{'이름': '배경색', '기준': '#D9D9D9', '개발': '#DCDCDC'}],
                                    '자리': '.x'}, ensure_ascii=False))
        본문 = card_view.body_html(k, page, **자리)
        self.assertIn('#D9D9D9', 본문)
        self.assertNotIn('c-tok', 본문)
        self.assertNotIn('Rectangle 3', 본문)            # 피그마가 붙인 이름은 안 쓴다
        self.assertIn('상자', 본문)                        # 라벨 꼬리를 대신 쓴다

    def test_견줄_값이_없는_후보도_무엇을_보는지_알린다(self):
        k = 후보(label='디자인에 없는 요소가 있음 — 배너',
                policy=json.dumps({'source': 'value', '키': '더있음|-|.banner|구조'}, ensure_ascii=False))
        본문 = card_view.body_html(k, None)
        self.assertIn('있고 없고', 본문)

    def test_로고_후보는_가로폭을_한_줄로_보여준다(self):
        k = 후보(kind='icon', label='아이콘 또는 이미지가 다르게 보입니다.',
                detail='디자인 그림은 가로 169px · 개발 이미지는 약 183px로 보입니다(약 8% 큼).',
                design_values='170×24 · 둥글기 0')
        줄, _, 안내, 잰것 = card_view.줄뽑기(k)
        self.assertFalse(잰것)
        self.assertEqual(줄[0], {'이름': '가로폭', '기준': '169px', '개발': '약 183px'})
        self.assertIn({'이름': '상자 크기', '기준': '170×24', '개발': None}, 줄)
        self.assertEqual(안내, '약 8% 큼')
        본문 = card_view.body_html(k, None)
        self.assertIn('지금 개발', 본문)
        self.assertNotIn('눈으로 대조', 본문)          # 잰 값이 있으면 눈대조 안내는 붙이지 않는다


if __name__ == '__main__':
    unittest.main()
