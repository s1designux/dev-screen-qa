"""검수기 플러그인 ↔ 포털 규칙 배선.

검수기(plugin-image-qa)는 피그마 안에서 돌지만, 규칙 값의 **원본은 포털**이다(CLAUDE.md 8번).
그래서 플러그인은 비교를 시작하기 전에 포털에서 그 화면의 규칙을 받아 가고,
사람이 검수기에서 가변/고정·화면 종류·검수 범위를 바꾸면 포털 층에도 쌓는다.
포털이 꺼져 있으면 플러그인은 조용히 예전처럼 피그마 프레임에만 저장한다(배선이 없어도 일은 된다).

POST /api/policy/read   {fileKey|fileName, nodeId, frameName}
  → {screen:{…}|null, policy:{screenType,variable,exclude,topGapMinPx}, range:{top,bottom}, source:{…}}
POST /api/policy/write  {fileKey|fileName, nodeId, frameName, actor, changes:[{rule,key?,value,scope?}]}
  → {ok:true, screen:{…}, saved:N, policy:{…}, range:{…}}
"""
import json

import design_receive
import policy as policymod

# 플러그인이 보내는 이름 → 정책 규칙 이름. 여기 없는 이름은 받지 않는다.
RULE_ALIAS = {
    'screenType': 'screen.type',
    'variable': 'text.variable',
    'exclude': 'element.exclude',
    'topGapMinPx': 'topGap.minPx',
    'rangeTop': 'range.top',
    'rangeBottom': 'range.bottom',
}


def _screen(store, c, body):
    return design_receive.Receiver(store).screen_for_frame(c, body)


def _snapshot(pol, c, screen_id, mirror=None):
    got = pol.resolve(c, screen_id)
    top, bottom = got['values'].get('range.top'), got['values'].get('range.bottom')
    return {
        'policy': pol.engine_policy(c, screen_id, mirror),
        'range': {'top': top, 'bottom': bottom},
        'source': {RULE_ALIAS_INV.get(k, k): v for k, v in got['source'].items()},
    }


RULE_ALIAS_INV = {v: k for k, v in RULE_ALIAS.items()}


def read(store, body):
    pol = policymod.Policy(store)
    with store.connect() as c:
        row = _screen(store, c, body)
        if not row:
            return {'screen': None, 'policy': None, 'range': {'top': None, 'bottom': None},
                    'note': '이 프레임에 해당하는 검수 화면이 포털에 아직 없어요. 검수기에서 정한 값은 피그마 프레임에만 저장됩니다.'}
        snap = _snapshot(pol, c, row['screen'], body.get('mirror'))
    return dict({'screen': {'id': row['screen'], 'key': row['human_key'], 'name': row['screen_name'],
                            'page': row['page'], 'pageName': row['page_name']}}, **snap)


def write(store, body):
    pol = policymod.Policy(store)
    actor = str(body.get('actor') or '검수기')
    changes = body.get('changes') or []
    if not isinstance(changes, list):
        raise ValueError('바꿀 값 목록이 없어요.')
    with store.connect() as c:
        row = _screen(store, c, body)
        if not row:
            return {'ok': False, 'screen': None,
                    'error': '이 프레임에 해당하는 검수 화면이 포털에 없어요. 먼저 촬영 준비나 「검수 시안 바꾸기」로 화면을 만들어 주세요.'}
        saved = 0
        for ch in changes:
            if not isinstance(ch, dict):
                continue
            name = str(ch.get('rule') or '')
            rule = RULE_ALIAS.get(name, name)
            spec = policymod.CATALOG.get(rule)
            if not spec:
                raise ValueError(f'포털이 모르는 규칙이에요: {name}')
            scope = str(ch.get('scope') or ('element' if spec.get('element') else 'screen'))
            target = row['screen'] if scope in ('screen', 'element') else (ch.get('target') or '')
            if pol.set(c, scope, rule, ch.get('value'), target=target, key=str(ch.get('key') or ''),
                       actor=actor, note='검수기 플러그인에서'):
                saved += 1
        snap = _snapshot(pol, c, row['screen'])
    return dict({'ok': True, 'saved': saved,
                 'screen': {'id': row['screen'], 'key': row['human_key'], 'name': row['screen_name']}}, **snap)


def post(handler, store, path):
    if path not in ('/api/policy/read', '/api/policy/write'):
        return False
    length = int(handler.headers.get('Content-Length', 0) or 0)
    raw = handler.rfile.read(length) if length else b''
    try:
        body = json.loads(raw.decode('utf-8')) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        design_receive._json(handler, {'error': '자료 모양이 맞지 않아요.'}, 400)
        return True
    try:
        out = read(store, body) if path.endswith('/read') else write(store, body)
    except ValueError as e:
        out = {'error': str(e)}
    design_receive._json(handler, out)
    return True
