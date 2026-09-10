"""Figma REST 노드 트리 → 검수기 요소 목록.

plugin-image-qa/code.js 의 collectDesign()과 같은 모양을 만든다(포털에서 같은 엔진을 돌리기 위해).
플러그인은 Figma 플러그인 API로, 여기는 REST 응답(JSON)으로 읽는 것만 다르다.
규칙을 바꿀 때는 양쪽을 같이 고친다.
"""

SHAPE_TYPES = {'FRAME', 'COMPONENT', 'INSTANCE', 'GROUP', 'SECTION', 'RECTANGLE', 'ELLIPSE'}
ICON_TYPES = {'VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'POLYGON', 'LINE'}


def round1(n):
    return round(n * 10) / 10


def to255(v):
    return int(round(v * 255))


def color_string(paint):
    if not isinstance(paint, dict) or paint.get('type') != 'SOLID' or paint.get('visible') is False:
        return None
    c = paint.get('color') or {}
    a = paint.get('opacity', 1)
    if a is None:
        a = 1
    r, g, b = (c.get('r', 0), c.get('g', 0), c.get('b', 0))
    if a < 1:
        return f'rgba({to255(r)}, {to255(g)}, {to255(b)}, {round1(a)})'
    return '#' + ''.join(f'{to255(v):02X}' for v in (r, g, b))


def first_solid(items):
    if not isinstance(items, list):
        return None
    for p in items:
        c = color_string(p)
        if c:
            return c
    return None


def safe_number(v):
    return round1(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def line_height(style):
    unit = style.get('lineHeightUnit')
    if unit == 'PIXELS' and isinstance(style.get('lineHeightPx'), (int, float)):
        return round1(style['lineHeightPx'])
    pct = style.get('lineHeightPercentFontSize', style.get('lineHeightPercent'))
    if unit in ('FONT_SIZE_%', 'INTRINSIC_%') and isinstance(pct, (int, float)):
        if unit == 'INTRINSIC_%' and abs(pct - 100) < 0.01:
            return '자동'
        return f'{round1(pct)}%'
    return None


def radius(node):
    if isinstance(node.get('cornerRadius'), (int, float)):
        return round1(node['cornerRadius'])
    rr = node.get('rectangleCornerRadii')
    if isinstance(rr, list) and rr and isinstance(rr[0], (int, float)):
        return round1(rr[0])
    return None


def stroke_width(node):
    for k in ('strokeWeight', 'individualStrokeWeights'):
        v = node.get(k)
        if isinstance(v, (int, float)):
            return round1(v)
        if isinstance(v, dict) and isinstance(v.get('top'), (int, float)):
            return round1(v['top'])
    return None


def prop_ref(node):
    refs = node.get('componentPropertyReferences') or {}
    v = refs.get('characters')
    return str(v).split('#')[0] if v else None


def read_element(node, root_box, depth, parent_id, parent_type, chain):
    bb = node.get('absoluteBoundingBox')
    if not bb or bb.get('width', 0) < 1 or bb.get('height', 0) < 1:
        return None
    box = {'x': round1(bb['x'] - root_box['x']), 'y': round1(bb['y'] - root_box['y']),
           'w': round1(bb['width']), 'h': round1(bb['height'])}
    base = {'id': node['id'], 'name': node.get('name') or node.get('type'), 'type': node.get('type'),
            'box': box, 'depth': depth, 'parentId': parent_id or None, 'parentType': parent_type or None}
    if node.get('type') == 'TEXT':
        st = node.get('style') or {}
        base['kind'] = 'text'
        base['text'] = str(node.get('characters') or '')[:120]
        base['chain'] = (chain or [])[:4]
        base['propRef'] = prop_ref(node)
        base['values'] = {
            'text': base['text'],
            'fontSize': safe_number(st.get('fontSize')),
            'fontWeight': safe_number(st.get('fontWeight')),
            'fontFamily': st.get('fontFamily') or '혼합',
            'fontStyle': (st.get('fontPostScriptName') or '').split('-')[-1] if st.get('fontPostScriptName') else '',
            'lineHeight': line_height(st),
            'color': first_solid(node.get('fills')),
            'textAlign': st.get('textAlignHorizontal'),
        }
        return base
    fill = first_solid(node.get('fills'))
    fills = node.get('fills')
    has_image = isinstance(fills, list) and any(isinstance(p, dict) and p.get('type') == 'IMAGE' and p.get('visible') is not False for p in fills)
    stroke = first_solid(node.get('strokes'))
    if not fill and not stroke and not has_image and node.get('type') not in SHAPE_TYPES:
        return None
    base['kind'] = 'image' if has_image else ('icon' if node.get('type') in ICON_TYPES else 'shape')
    base['text'] = ''
    base['values'] = {
        'width': round1(bb['width']), 'height': round1(bb['height']),
        'fill': fill, 'stroke': stroke, 'strokeWidth': stroke_width(node),
        'radius': radius(node), 'opacity': safe_number(node.get('opacity', 1)),
    }
    return base


def collect(root):
    """루트 프레임의 REST 문서 → {'frame': {...}, 'elements': [...]}. 루트 자신은 목록에 넣지 않는다(플러그인과 동일)."""
    rb = root.get('absoluteBoundingBox') or {'x': 0, 'y': 0, 'width': 0, 'height': 0}
    items = []

    def walk(n, depth, parent_id, parent_type, chain):
        if n is not root and n.get('visible', True) is not False and n.get('absoluteBoundingBox'):
            el = read_element(n, rb, depth, parent_id, parent_type, chain)
            if el:
                b = el['box']
                if b['x'] < rb['width'] and b['y'] < rb['height'] and b['x'] + b['w'] > 0 and b['y'] + b['h'] > 0:
                    items.append(el)
        next_chain = [] if n is root else ([{'n': str(n.get('name') or ''), 't': n.get('type')}] + (chain or []))[:4]
        for child in n.get('children') or []:
            walk(child, depth + 1, n['id'], n.get('type'), next_chain)

    walk(root, 0, None, None, [])
    return {'frame': {'id': root['id'], 'name': root.get('name') or '디자인',
                      'width': round1(rb['width']), 'height': round1(rb['height'])},
            'elements': items}
