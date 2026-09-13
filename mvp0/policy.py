"""검수 정책(규칙 값)의 층 — 시스템 기본값 → 서비스 → 화면 → 요소.

원칙(CLAUDE.md 2번·8번): 규칙의 **알고리즘**은 검수기 파일(plugin-image-qa/ui.html)에 있고,
여기에는 **값**만 둔다 — 켜고 끄기·기준값·이름 규칙·화면별 예외·요소별 예외.
아래층이 위층을 덮는다. 지우지 않는다: 모든 변경은 행으로 쌓고, 가장 최근 행이 지금 값이다.
값을 null로 쓰면 '그 층의 예외를 거둠'(위층 값으로 돌아감)이다.

포털이 원본이다. 검수기 플러그인이 피그마 프레임에 두는 설정(qa_settings)은 거울일 뿐이라,
포털 행이 있으면 포털 행이 이긴다.
"""
import json
import sqlite3
import uuid
from datetime import datetime

SCHEMA = '''
CREATE TABLE IF NOT EXISTS policy_rule (
 id TEXT PRIMARY KEY,
 scope TEXT NOT NULL CHECK(scope IN ('system','service','screen','element')),
 target TEXT NOT NULL DEFAULT '',   -- service: project.uuid / screen·element: screen.uuid / system: ''
 rule TEXT NOT NULL,                -- 규칙 이름(CATALOG의 키)
 key TEXT NOT NULL DEFAULT '',      -- element 층에서만: 디자인 요소(노드) id
 value TEXT NOT NULL,               -- JSON. null이면 이 층의 예외를 거둠
 actor TEXT NOT NULL DEFAULT '', at TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS policy_rule_lookup ON policy_rule(scope, target, rule, key);
CREATE TRIGGER IF NOT EXISTS policy_rule_no_update BEFORE UPDATE ON policy_rule BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS policy_rule_no_delete BEFORE DELETE ON policy_rule BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''

SCOPES = ('system', 'service', 'screen', 'element')
SCOPE_LABEL = {'system': '시스템 기본', 'service': '서비스', 'screen': '화면', 'element': '요소'}

# 규칙 목록. 검수기가 실제로 읽는 값만 둔다(여기 없는 이름은 저장을 거절한다).
#   engine: 검수기에 넘길 때 design.policy 안의 이름 / element: 요소별로 정하는 것인지
CATALOG = {
    'screen.type':      {'title': '화면 종류', 'help': '공통화면(로그인·약관…)은 글자가 고정, 일반화면은 데이터라 가변',
                         'type': 'choice', 'choices': {'auto': '이름으로 추정', 'common': '공통화면', 'data': '일반화면'},
                         'default': 'auto', 'engine': 'screenType', 'scopes': ('system', 'service', 'screen')},
    'text.variable':    {'title': '이 글자는 가변/고정', 'help': '사람이 정한 것이 모든 규칙보다 앞선다',
                         'type': 'bool', 'default': None, 'engine': 'variable', 'scopes': ('element',), 'element': True},
    'element.exclude':  {'title': '이 요소는 검수 대상 아님', 'help': '가짜 틀·장식처럼 견줄 필요가 없는 것',
                         'type': 'bool', 'default': None, 'engine': 'exclude', 'scopes': ('element',), 'element': True},
    'topGap.minPx':     {'title': '맨 위 여백 차이 기준(px)', 'help': '이보다 작은 차이는 정렬 오차로 보고 후보로 올리지 않음',
                         'type': 'int', 'default': 6, 'engine': 'topGapMinPx', 'scopes': ('system', 'service', 'screen')},
    'range.top':        {'title': '개발 화면 위쪽 뺄 px', 'help': '브라우저 탭·상태바. 비우면 자동 규칙',
                         'type': 'int', 'default': None, 'engine': None, 'scopes': ('service', 'screen')},
    'range.bottom':     {'title': '개발 화면 아래쪽 뺄 px', 'help': '하단 내비게이션·홈 바. 비우면 자동 규칙',
                         'type': 'int', 'default': None, 'engine': None, 'scopes': ('service', 'screen')},
}


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now().isoformat(timespec='seconds')


def _check(rule, value):
    spec = CATALOG.get(rule)
    if not spec:
        raise ValueError(f'없는 규칙이에요: {rule}')
    if value is None:
        return None
    t = spec['type']
    if t == 'bool':
        if isinstance(value, bool):
            return value
        if value in ('true', 'false', '1', '0', 1, 0):
            return value in ('true', '1', 1)
        raise ValueError(f'{spec["title"]}: 예/아니오 값이어야 해요.')
    if t == 'int':
        try:
            v = int(round(float(value)))
        except (TypeError, ValueError):
            raise ValueError(f'{spec["title"]}: 숫자여야 해요.')
        if v < 0:
            raise ValueError(f'{spec["title"]}: 0 이상이어야 해요.')
        return v
    if t == 'choice':
        if value not in spec['choices']:
            raise ValueError(f'{spec["title"]}: {", ".join(spec["choices"])} 중 하나여야 해요.')
        return value
    return value


class Policy:
    def __init__(self, store):
        self.store = store

    # ── 쓰기(쌓기만 한다) ────────────────────────────────────────
    def set(self, c, scope, rule, value, target='', key='', actor='', note=''):
        """한 층의 한 규칙 값을 쌓는다. value=None 이면 그 층의 예외를 거둔다."""
        if scope not in SCOPES:
            raise ValueError('없는 층이에요.')
        spec = CATALOG.get(rule)
        if not spec:
            raise ValueError(f'없는 규칙이에요: {rule}')
        if scope not in spec['scopes']:
            raise ValueError(f'{spec["title"]}은(는) {"·".join(SCOPE_LABEL[s] for s in spec["scopes"])} 층에서만 정해요.')
        if spec.get('element') and not key:
            raise ValueError('어느 요소인지(key)가 필요해요.')
        if scope != 'system' and not target:
            raise ValueError('어느 서비스·화면인지(target)가 필요해요.')
        v = _check(rule, value)
        cur = self.current(c, scope, target, rule, key)
        if cur is not None and cur['value'] == v:
            return None  # 같은 값이면 쌓지 않는다
        if cur is None and v is None:
            return None
        rid = uid()
        c.execute('INSERT INTO policy_rule VALUES (?,?,?,?,?,?,?,?,?)',
                  (rid, scope, target if scope != 'system' else '', rule, key if spec.get('element') else '',
                   json.dumps(v, ensure_ascii=False), actor, now(), note))
        return rid

    # ── 읽기 ─────────────────────────────────────────────────────
    def current(self, c, scope, target, rule, key=''):
        r = c.execute('SELECT * FROM policy_rule WHERE scope=? AND target=? AND rule=? AND key=? ORDER BY rowid DESC LIMIT 1',
                      (scope, target if scope != 'system' else '', rule, key)).fetchone()
        if not r:
            return None
        return {'value': json.loads(r['value']), 'actor': r['actor'], 'at': r['at'], 'note': r['note'], 'id': r['id']}

    def layer(self, c, scope, target):
        """한 층에서 지금 살아 있는 값 전부: {(rule,key): {...}}. 거둔 것(null)은 뺀다."""
        rows = c.execute('SELECT * FROM policy_rule WHERE scope=? AND target=? ORDER BY rowid', (scope, target if scope != 'system' else '')).fetchall()
        out = {}
        for r in rows:  # 뒤 행이 앞 행을 덮는다
            v = json.loads(r['value'])
            k = (r['rule'], r['key'])
            if v is None:
                out.pop(k, None)
            else:
                out[k] = {'value': v, 'actor': r['actor'], 'at': r['at'], 'note': r['note'], 'scope': scope}
        return out

    def resolve(self, c, screen_id=None, project_id=None):
        """네 층을 위에서 아래로 겹쳐 지금 값과 '어느 층이 정했는지'를 돌려준다.
        {'values': {rule: value}, 'elements': {rule: {key: value}}, 'source': {rule: scope|'default'}, 'element_source': {(rule,key): scope}}"""
        if screen_id and not project_id:
            r = c.execute('SELECT project_id FROM screen WHERE uuid=?', (screen_id,)).fetchone()
            project_id = r['project_id'] if r else None
        values = {rule: spec['default'] for rule, spec in CATALOG.items() if not spec.get('element')}
        source = {rule: 'default' for rule in values}
        elements, element_source = {}, {}
        layers = [('system', '')]
        if project_id:
            layers.append(('service', project_id))
        if screen_id:
            layers += [('screen', screen_id), ('element', screen_id)]
        for scope, target in layers:
            for (rule, key), item in self.layer(c, scope, target).items():
                if CATALOG[rule].get('element'):
                    elements.setdefault(rule, {})[key] = item['value']
                    element_source[(rule, key)] = scope
                else:
                    values[rule] = item['value']
                    source[rule] = scope
        return {'values': values, 'elements': elements, 'source': source, 'element_source': element_source, 'project_id': project_id}

    def engine_policy(self, c, screen_id, mirror=None):
        """검수기에 넘길 design.policy. mirror = 피그마 프레임에서 따라온 설정(qa_settings의 policy) — 포털 행이 없을 때만 쓴다."""
        got = self.resolve(c, screen_id)
        pol = {}
        m = mirror if isinstance(mirror, dict) else {}
        # 화면 종류: 포털 값이 auto(=정하지 않음)면 거울 값을 쓴다
        st = got['values'].get('screen.type')
        if st and st != 'auto':
            pol['screenType'] = st
        elif m.get('screenType') in ('common', 'data'):
            pol['screenType'] = m['screenType']
        variable = dict(m.get('variable') or {})
        variable.update(got['elements'].get('text.variable', {}))
        if variable:
            pol['variable'] = variable
        exclude = {k: '사람이 검수 대상에서 뺌' for k, v in got['elements'].get('element.exclude', {}).items() if v}
        if exclude:
            pol['exclude'] = exclude
        pol['topGapMinPx'] = got['values'].get('topGap.minPx')
        return pol

    def capture_range(self, c, screen_id):
        """화면·서비스 층에 정한 개발 화면 위·아래 뺄 px. 없으면 None."""
        got = self.resolve(c, screen_id)
        return got['values'].get('range.top'), got['values'].get('range.bottom')

    def history(self, c, scope=None, target=None, limit=200):
        q, args = 'SELECT * FROM policy_rule', []
        conds = []
        if scope:
            conds.append('scope=?'); args.append(scope)
        if target is not None:
            conds.append('target=?'); args.append(target)
        if conds:
            q += ' WHERE ' + ' AND '.join(conds)
        q += ' ORDER BY rowid DESC LIMIT ?'
        args.append(limit)
        return [dict(r) for r in c.execute(q, args).fetchall()]
