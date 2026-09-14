"""후보를 **컴포넌트 덩어리**로 묶는다 — 버튼 하나가 카드 세 장으로 쪼개지지 않게.

지금까지는 시안 요소 하나가 카드 한 장이었다. 그런데 버튼은 시안에서 '상자 + 안의 글자'라
여러 요소다. 버튼 색이 틀리고 라벨 글자도 다르면 카드가 둘로 갈라져 나왔다 —
사람이 보기엔 **고칠 곳은 버튼 하나**인데.

묶는 열쇠는 이미 자료에 있다. 시안 요소 번호가 `I21033:16815;1433:123472` 모양일 때
앞쪽 `I21033:16815` 가 **그 컴포넌트를 화면에 한 번 놓은 것(인스턴스)** 이고 뒤쪽이 그 안의 낱낱이다.
앞쪽이 같으면 같은 덩어리다. 앞쪽이 없는 요소(컴포넌트 밖에 홀로 그린 것)는 저 혼자 한 덩어리다.

**자료는 그대로 둔다.** 속성별로 쌓는 것도, 차수 간 이력(dedup)도 건드리지 않는다 —
보여 줄 때만 묶는다(CLAUDE.md 2번-1: 문서·화면은 데이터를 읽어 만든 출력물).
그래서 제외·되돌림도 여전히 **묶음 안의 낱낱**에 걸린다. 카드 위 '전부 제외'가 그것들을 한꺼번에 누를 뿐이다.
"""
import json
import re

_인스턴스 = re.compile(r"^(I[^;]+);")


def _요소번호들(k):
    """후보가 가리키는 시안 요소 번호들. 그림 검수는 design_node_ids, 값 대조는 policy 의 키에 있다."""
    ids = []
    try:
        ids = json.loads(k['design_node_ids'] or '[]') or []
    except (TypeError, ValueError, KeyError):
        ids = []
    if ids:
        return [str(x) for x in ids]
    try:
        키 = (json.loads(k['policy'] or '{}') or {}).get('키') or ''
    except (TypeError, ValueError, KeyError):
        키 = ''
    부분 = str(키).split('|')
    return [부분[1]] if len(부분) > 1 and 부분[1] else []


def 덩어리키(k):
    """같은 컴포넌트를 한 번 놓은 것이면 같은 값. 알 수 없으면 저 혼자(후보 id)."""
    for nid in _요소번호들(k):
        m = _인스턴스.match(nid)
        if m:
            return m.group(1)
    return 'solo:%s' % k['id']


def 묶기(후보들):
    """[(덩어리키, [후보…])] — 처음 나온 차례대로. 묶음 안도 원래 차례를 지킨다."""
    차례, 통 = [], {}
    for k in 후보들:
        key = 덩어리키(k)
        if key not in 통:
            통[key] = []
            차례.append(key)
        통[key].append(k)
    return [(key, 통[key]) for key in 차례]


def 합친상자(후보들, 칸=('box_x', 'box_y', 'box_w', 'box_h')):
    """묶음이 차지하는 자리 하나 — 낱낱의 상자를 다 감싸는 네모."""
    상자 = []
    for k in 후보들:
        x, y, w, h = (k[c] or 0 for c in 칸)
        if w and h:
            상자.append((x, y, w, h))
    if not 상자:
        return [0, 0, 0, 0]
    x0 = min(b[0] for b in 상자)
    y0 = min(b[1] for b in 상자)
    x1 = max(b[0] + b[2] for b in 상자)
    y1 = max(b[1] + b[3] for b in 상자)
    return [x0, y0, x1 - x0, y1 - y0]
