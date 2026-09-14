"""검수 내용의 표시 분류. 원래 category/이력은 수정하지 않는다.

근거: legacy/plugin-image-qa/README.md 후보 분류, CLAUDE.md 8번 시각 차이 범위.
플러그인 후보를 포털 이슈로 가져오거나 확정하는 기능은 아니다.
"""
GROUPS = {
    'text': ('글자 내용·모양', '#2563eb'),
    'position': ('위치·정렬·크기', '#7c3aed'),
    'appearance': ('색상·모양', '#db2777'),
    'structure': ('요소 추가·누락', '#d97706'),
    'image': ('아이콘·이미지', '#0d9488'),
    'mixed': ('복합', '#334155'),
    'other': ('기타', '#6b7280'),
}
ALIASES = {
    'typography':'text','text':'text','font':'text',
    'layout':'position','position':'position','size':'position','alignment':'position',
    'color':'appearance','shape':'appearance','appearance':'appearance',
    'structure':'structure','missing':'structure','extra':'structure','added':'structure',
    'icon':'image','image':'image','mixed':'mixed',
    # 안쪽여백 등 간격은 검수 대상이 아니다(CLAUDE.md 8번) — 갈래를 두지 않고 '기타'로 떨어뜨린다.
}


def category_group(value):
    return ALIASES.get((value or '').split('-')[0], 'other')


def label(value):
    return GROUPS[category_group(value)][0]


def color(value):
    return GROUPS[category_group(value)][1]
