"""값 대조 후보의 '그릴 자리' 검증 — 개발 그림 밖으로 나가지 않는지.

잰 값의 자리는 판(아트보드) 기준이고 촬영본은 내용만 담는다.
contentX/Y 를 반대 부호로 먹이면 후보가 통째로 화면 한 폭만큼 밀려 개발 그림 밖으로 나간다.
'디자인에 있는데 개발에 없음' 후보는 잴 개발 요소가 없어 시안 상자를 쓰는데,
거기에 개발 보정을 또 먹여도 같은 일이 생긴다.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mvp0'))
import value_candidates as vc


class 그릴자리(unittest.TestCase):
    잣대 = (1, -960, -20)   # 배율 1 · 판 위에서 내용이 x=960, y=20 에 놓였다

    def test_개발에서_잰_상자는_내용_기준으로_옮긴다(self):
        c = {'devBox': {'x': 960, 'y': 20, 'w': 1920, 'h': 40}}
        self.assertEqual(vc._상자(c, *self.잣대), (0, 0, 1920, 40))

    def test_판_오른쪽에_놓인_요소도_그림_안에_들어온다(self):
        c = {'devBox': {'x': 2800, 'y': 100, 'w': 80, 'h': 20}}
        x, y, w, h = vc._상자(c, *self.잣대)
        self.assertEqual((x, y, w, h), (1840, 80, 80, 20))
        self.assertLessEqual(x + w, 1920)          # 개발 그림(폭 1920) 밖으로 나가지 않는다

    def test_시안_상자만_있는_후보는_개발_보정을_먹이지_않는다(self):
        # '디자인에 있는데 개발에 없음' — 잴 개발 요소가 없어 시안 상자를 쓴다
        c = {'box': {'x': 320, 'y': 906, 'w': 1280, 'h': 32}}
        self.assertEqual(vc._상자(c, *self.잣대), (320, 906, 1280, 32))

    def test_상자가_아예_없으면_자리를_비운다(self):
        self.assertEqual(vc._상자({}, *self.잣대), (None, None, None, None))

    def test_배율은_잰_폭과_그림_폭의_비로_잡는다(self):
        결과 = {'meta': {'개발': {'docW': 960, 'contentX': -100, 'contentY': -5}}}
        k, dx, dy = vc._잣대(결과, {'dev_img_w': 1920})
        self.assertEqual((k, dx, dy), (2, -100, -5))

    def test_잰_폭을_모르면_배율은_1(self):
        k, dx, dy = vc._잣대({'meta': {}}, {'dev_img_w': 1920})
        self.assertEqual((k, dx, dy), (1, 0, 0))


if __name__ == '__main__':
    unittest.main(verbosity=2)
