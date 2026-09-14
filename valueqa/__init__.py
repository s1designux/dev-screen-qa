"""값 대조 — 시안 값과 개발 값을 짝지어 '다른 곳'을 후보로 뽑는다.

PC 웹 검수는 그림 대조가 아니라 **값 대조**다(색·글꼴·글자크기·굵기·모서리·테두리·크기).
여기 있는 것은 이미 검증된 두 벌을 파이썬으로 옮긴 것이다(알고리즘을 새로 만들지 않았다):

    plugin-value-qa/ui.html  →  runMatcher()   : 이름표 없이 짝 맞추기
                             →  compareRows()  : 값 견주기
                             →  doCompare()    : 구조 차이(추가·누락) 가려내기

옮긴 이유: 저쪽은 피그마 플러그인 창 안에서만 돌고, 검수는 포털에서만 하기로 했다(CLAUDE.md 4번).
같은 입력에 같은 답이 나오는지는 `python3 -m valueqa.selftest` 가 매번 확인한다.

**여기서 나오는 것은 지적이 아니라 후보다** (CLAUDE.md 2번-2). 확정은 사람이 한다.
"""
from .match import 짝맞추기
from .compare import 값견주기
from .candidates import 후보뽑기
from .design import 시안값으로

__all__ = ["짝맞추기", "값견주기", "후보뽑기", "시안값으로"]
