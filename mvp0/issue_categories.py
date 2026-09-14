"""검수 내용의 표시 분류. 원래 category/이력은 수정하지 않는다.

근거: legacy/plugin-image-qa/README.md 후보 분류, CLAUDE.md 8번 시각 차이 범위.
플러그인 후보를 포털 이슈로 가져오거나 확정하는 기능은 아니다.

**이름은 퍼블리셔·개발이 고칠 때 쓰는 말로 짧게 적는다** (river 확정 2026-09-14).
'색'과 '크기'는 갈라 둔다 — 한 덩어리로 두면 절반이 한 이름표에 몰려 고를 수가 없다.

**색으로 가르지 않는다** (river 확정 2026-09-14). 화면 위 핀은 전부 같은 진회색이다.
일곱 색을 두어도 실제로는 카드 절반이 한 색이라 정보가 거의 없었고,
색 차이를 보는 지적 위에 색깔 핀을 얹으면 보는 데 방해가 된다. 가르는 일은 **이름표(칩)**가 맡는다.
"""
핀색 = 'var(--color-text-primary)'          # 화면 위 번호 핀 — 하나뿐이다

GROUPS = {
    'text':       '글자',
    'position':   '자리',
    'appearance': '색',
    'size':       '크기',
    'structure':  '있고 없음',
    'image':      '아이콘·이미지',
    'mixed':      '복합',
    'other':      '기타',
}
ALIASES = {
    'typography': 'text', 'text': 'text', 'font': 'text',
    'layout': 'position', 'position': 'position', 'alignment': 'position',
    'color': 'appearance', 'appearance': 'appearance',
    'shape': 'size', 'size': 'size',
    'structure': 'structure', 'missing': 'structure', 'extra': 'structure', 'added': 'structure',
    'icon': 'image', 'image': 'image', 'mixed': 'mixed',
    # 안쪽여백 등 간격은 검수 대상이 아니다(CLAUDE.md 8번) — 갈래를 두지 않고 '기타'로 떨어뜨린다.
}


def category_group(value):
    return ALIASES.get((value or '').split('-')[0], 'other')


def label(value):
    return GROUPS[category_group(value)]


def color(value):
    """예전 부르는 쪽을 위해 남겨 둔다 — 이제 갈래와 상관없이 같은 색이다."""
    return 핀색
