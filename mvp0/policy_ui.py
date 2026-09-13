"""검수 규칙(정책 값) 화면 — 시스템 기본 → 서비스 → 화면 → 요소, 어느 층이 지금 값을 정했는지 보이고 바꾼다.

GET  /policy                         : 시스템 기본값 + 서비스 목록
GET  /policy/service/<project uuid>  : 그 서비스의 값(시스템 기본을 덮은 것만 표시)과 화면 목록
GET  /policy/screen/<screen uuid>    : 그 화면의 값 + 요소 층(사람이 후보에서 가변·제외로 내린 것)
POST /policy/set                     : scope·target·rule·(key)·value·actor  → 쌓기(값 비우면 그 층 예외 거둠)
"""
import json
from html import escape as _e
from urllib.parse import parse_qs

import policy as policymod
import rule_log

CSS = '''
body{margin:0;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard",sans-serif;color:#1E293B;background:#F8FAFC}
.wrap{max-width:960px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.sub{color:#64748B;margin:0 0 20px;font-size:14px}
a.back{color:#1D6CEB;text-decoration:none;font-size:14px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;font-size:14px}
th,td{padding:9px 12px;border-bottom:1px solid #E2E8F0;text-align:left;vertical-align:middle}
th{background:#F1F5F9;font-weight:700;white-space:nowrap}
tr:last-child td{border-bottom:0}
td.k{font-weight:600;white-space:nowrap}td.help{color:#64748B;font-size:13px}
.src{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid #CBD5E1;color:#64748B;background:#fff;white-space:nowrap}
.src.here{border-color:#1D6CEB;color:#1D6CEB}.src.default{border-style:dashed}
form.inline{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
input[type=number],select{font:inherit;font-size:13px;padding:3px 6px;border:1px solid #CBD5E1;border-radius:6px;background:#fff;max-width:120px}
button{font:inherit;font-size:13px;padding:4px 10px;border:1px solid #CBD5E1;border-radius:6px;background:#fff;cursor:pointer}
button.primary{background:#1D6CEB;border-color:#1D6CEB;color:#fff}
ul.list{list-style:none;padding:0;margin:0}ul.list li{padding:6px 0;border-bottom:1px solid #E2E8F0}ul.list a{color:#1D6CEB;text-decoration:none}
.note{background:#fff;border:1px solid #E2E8F0;border-left:4px solid #B45309;border-radius:6px;padding:10px 14px;font-size:14px;margin:0 0 18px}
.hist{font-size:13px;color:#64748B}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.bad{color:#B91C1C;font-weight:700}.good{color:#166534}
'''


def _shell(title, body, back=('/', '← 목록')):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_e(title)}</title><style>{CSS}</style></head><body><div class="wrap">'
            f'<a class="back" href="{_e(back[0])}">{_e(back[1])}</a>{body}</div></body></html>')


def _src_tag(scope, here):
    label = '기본값' if scope == 'default' else policymod.SCOPE_LABEL.get(scope, scope)
    cls = 'src' + (' here' if scope == here else '') + (' default' if scope == 'default' else '')
    return f'<span class="{cls}">{_e(label)}</span>'


def _value_text(rule, v):
    spec = policymod.CATALOG[rule]
    if v is None:
        return '<span style="color:#94A3B8">비움</span>'
    if spec['type'] == 'choice':
        return _e(spec['choices'].get(v, str(v)))
    if spec['type'] == 'bool':
        return '예' if v else '아니오'
    return _e(str(v))


def _field(rule, v):
    spec = policymod.CATALOG[rule]
    if spec['type'] == 'choice':
        opts = ''.join(f'<option value="{_e(k)}"{" selected" if k == v else ""}>{_e(t)}</option>' for k, t in spec['choices'].items())
        return f'<select name="value">{opts}</select>'
    if spec['type'] == 'bool':
        return (f'<select name="value"><option value="">비움</option><option value="true"{" selected" if v is True else ""}>예</option>'
                f'<option value="false"{" selected" if v is False else ""}>아니오</option></select>')
    return f'<input type="number" name="value" min="0" step="1" value="{"" if v is None else _e(str(v))}" placeholder="비움">'


def _rules_table(pol, c, scope, target, resolved, back_url, person_options=''):
    """한 층에서 정할 수 있는 규칙 표. 지금 값·어느 층이 정했는지·이 층에서 바꾸는 폼."""
    rows = []
    for rule, spec in policymod.CATALOG.items():
        if spec.get('element') or scope not in spec['scopes']:
            continue
        v = resolved['values'].get(rule)
        src = resolved['source'].get(rule, 'default')
        mine = pol.current(c, scope, target, rule)
        mine_v = mine['value'] if mine else None
        form = (f'<form class="inline" method="post" action="/policy/set">'
                f'<input type="hidden" name="scope" value="{scope}"><input type="hidden" name="target" value="{_e(target)}">'
                f'<input type="hidden" name="rule" value="{_e(rule)}"><input type="hidden" name="back" value="{_e(back_url)}">'
                f'{_field(rule, mine_v)}<select name="actor"><option value="">담당자</option>{person_options}</select>'
                f'<button type="submit" class="primary">이 층에 정하기</button></form>')
        rows.append(f'<tr><td class="k">{_e(spec["title"])}<br><span class="help">{_e(spec["help"])}</span></td>'
                    f'<td>{_value_text(rule, v)}</td><td>{_src_tag(src, scope)}</td><td>{form}</td></tr>')
    return ('<table><tr><th>규칙</th><th>지금 값</th><th>정한 층</th><th>이 층에서 바꾸기</th></tr>' + ''.join(rows) + '</table>')


def _history(pol, c, scope, target):
    hs = pol.history(c, scope, target, limit=30)
    if not hs:
        return ''
    items = []
    for h in hs:
        v = json.loads(h['value'])
        spec = policymod.CATALOG.get(h['rule'], {'title': h['rule']})
        key = f' · 요소 {h["key"]}' if h['key'] else ''
        items.append(f'<li class="hist">{_e(h["at"])} · {_e(spec["title"])}{_e(key)} → {_value_text(h["rule"], v) if h["rule"] in policymod.CATALOG else _e(str(v))}'
                     f'{" · " + _e(h["actor"]) if h["actor"] else ""}{" · " + _e(h["note"]) if h["note"] else ""}</li>')
    return '<h2>이 층의 변경 이력</h2><ul class="list">' + ''.join(items) + '</ul>'


def _rule_score(c, screen_id=None):
    """규칙별 성적표 — 그 규칙이 이름표를 붙인 후보가 몇 개였고, 사람이 그대로 뒀는지 뒤집었는지.

    여기서 규칙을 고치지는 않는다(CLAUDE.md 2번). 세어서 보여주기만 하고, 고칠지는 사람이 정한다."""
    rows = rule_log.stats(c, screen_id)
    seen = [r for r in rows if r['agree'] or r['overturn']]
    if not rows:
        return ('<h2>규칙 성적</h2><p class="sub">아직 판정 기록이 없어요. 페이지 상세에서 후보를 '
                '<b>제외</b>·<b>가변</b>으로 내리거나 <b>지적으로 등록</b>하면 어느 규칙이 그렇게 만들었는지 여기에 쌓입니다.</p>')
    body = []
    for r in rows:
        judged = r['agree'] + r['overturn']
        rate = '—' if r['rate'] is None else f'{r["rate"]}%'
        cls = ' class="bad"' if (r['rate'] is not None and r['rate'] < 60 and judged >= 3) else (' class="good"' if (r['rate'] is not None and r['rate'] >= 90 and judged >= 3) else '')
        body.append(f'<tr><td class="k">{_e(r["title"])}</td><td class="help">{_e(r["rule"])}</td>'
                    f'<td class="n">{r["fired"]}</td><td class="n">{r["agree"]}</td><td class="n">{r["overturn"]}</td>'
                    f'<td class="n"{cls}>{rate}</td></tr>')
    note = ('' if seen else '<p class="sub">아직 사람이 판정한 후보가 없어 맞음·뒤집힘이 모두 0입니다.</p>')
    return ('<h2>규칙 성적</h2><p class="sub">후보를 그 자리에 둔 규칙마다, 사람이 <b>그대로 둔 수</b>와 <b>뒤집은 수</b>입니다. '
            '뒤집힘이 많은 규칙이 다음에 고칠 규칙입니다. (여기서 자동으로 바꾸지 않습니다.)</p>' + note +
            '<table><tr><th>규칙</th><th>이름</th><th>나온 후보</th><th>그대로 둠</th><th>뒤집음</th><th>맞은 비율</th></tr>'
            + ''.join(body) + '</table>')


def page_root(store, person_options=''):
    pol = policymod.Policy(store)
    with store.connect() as c:
        resolved = pol.resolve(c)
        table = _rules_table(pol, c, 'system', '', resolved, '/policy', person_options)
        projects = c.execute('SELECT uuid,name FROM project ORDER BY name').fetchall()
        hist = _history(pol, c, 'system', '')
        score = _rule_score(c)
    items = ''.join(f'<li><a href="/policy/service/{_e(p["uuid"])}">{_e(p["name"] or "(이름 없음)")}</a></li>' for p in projects)
    body = (f'<h1>검수 규칙</h1><p class="sub">규칙 값은 <b>시스템 기본 → 서비스 → 화면 → 요소</b> 순으로 겹치고, 아래층이 위층을 덮습니다. '
            f'바꾼 값은 지우지 않고 이력으로 쌓입니다.</p>'
            f'<h2>시스템 기본값</h2>{table}{score}{hist}'
            f'<h2>서비스별 규칙</h2><ul class="list">{items or "<li>서비스가 아직 없어요.</li>"}</ul>')
    return _shell('검수 규칙', body)


def page_service(store, project_id, person_options=''):
    pol = policymod.Policy(store)
    with store.connect() as c:
        p = c.execute('SELECT uuid,name FROM project WHERE uuid=?', (project_id,)).fetchone()
        if not p:
            return None
        resolved = pol.resolve(c, project_id=project_id)
        url = f'/policy/service/{project_id}'
        table = _rules_table(pol, c, 'service', project_id, resolved, url, person_options)
        screens = c.execute('SELECT uuid,human_key,name FROM screen WHERE project_id=? ORDER BY human_key,name', (project_id,)).fetchall()
        hist = _history(pol, c, 'service', project_id)
    items = ''.join(f'<li><a href="/policy/screen/{_e(s["uuid"])}">{_e(s["human_key"] or "")} {_e(s["name"] or "")}</a></li>' for s in screens)
    body = (f'<h1>서비스 규칙 — {_e(p["name"])}</h1><p class="sub">여기 정한 값은 이 서비스의 모든 화면에 적용되고, 화면·요소 층에서 다시 덮을 수 있습니다.</p>'
            f'{table}{hist}<h2>화면별 규칙</h2><ul class="list">{items or "<li>화면이 아직 없어요.</li>"}</ul>')
    return _shell(f'서비스 규칙 — {p["name"]}', body, ('/policy', '← 검수 규칙'))


def page_screen(store, screen_id, person_options=''):
    pol = policymod.Policy(store)
    with store.connect() as c:
        s = c.execute('SELECT s.uuid,s.human_key,s.name,s.project_id,p.name pname FROM screen s JOIN project p ON p.uuid=s.project_id WHERE s.uuid=?', (screen_id,)).fetchone()
        if not s:
            return None
        resolved = pol.resolve(c, screen_id)
        url = f'/policy/screen/{screen_id}'
        table = _rules_table(pol, c, 'screen', screen_id, resolved, url, person_options)
        el_rows = []
        for rule, spec in policymod.CATALOG.items():
            if not spec.get('element'):
                continue
            for key, v in sorted(resolved['elements'].get(rule, {}).items()):
                cur = pol.current(c, 'element', screen_id, rule, key) or {}
                undo = (f'<form class="inline" method="post" action="/policy/set"><input type="hidden" name="scope" value="element">'
                        f'<input type="hidden" name="target" value="{_e(screen_id)}"><input type="hidden" name="rule" value="{_e(rule)}">'
                        f'<input type="hidden" name="key" value="{_e(key)}"><input type="hidden" name="value" value="">'
                        f'<input type="hidden" name="back" value="{_e(url)}"><button type="submit">거두기</button></form>')
                el_rows.append(f'<tr><td class="k">{_e(spec["title"])}</td><td>{_e(key)}</td><td>{_value_text(rule, v)}</td>'
                               f'<td class="help">{_e(cur.get("note") or "")}{(" · " + _e(cur["actor"])) if cur.get("actor") else ""}</td><td>{undo}</td></tr>')
        hist = _history(pol, c, 'screen', screen_id) + _history(pol, c, 'element', screen_id).replace('이 층의 변경 이력', '요소 층의 변경 이력')
        score = _rule_score(c, screen_id)
    el_table = ('<table><tr><th>규칙</th><th>요소</th><th>값</th><th>어떻게 정해졌나</th><th></th></tr>' + ''.join(el_rows) + '</table>') if el_rows else \
        '<p class="sub">아직 없어요. 페이지 상세에서 후보를 <b>가변</b>·<b>제외</b>로 내리면 여기에 쌓입니다.</p>'
    body = (f'<h1>화면 규칙 — {_e(s["human_key"] or "")} {_e(s["name"] or "")}</h1>'
            f'<p class="sub">서비스 <a href="/policy/service/{_e(s["project_id"])}">{_e(s["pname"])}</a> 의 값을 이 화면에서만 덮습니다. '
            f'검수 범위(위·아래 px)는 차수에서 직접 정한 것이 있으면 그쪽이 먼저입니다.</p>'
            f'{table}<h2>요소별 예외 (사람이 정한 것)</h2>{el_table}{score}{hist}')
    return _shell(f'화면 규칙 — {s["human_key"] or s["name"]}', body, (f'/policy/service/{s["project_id"]}', '← 서비스 규칙'))


def get(handler, store, path, person_options=''):
    if path == '/policy':
        html = page_root(store, person_options)
    elif path.startswith('/policy/service/'):
        html = page_service(store, path.rsplit('/', 1)[1], person_options)
    elif path.startswith('/policy/screen/'):
        html = page_screen(store, path.rsplit('/', 1)[1], person_options)
    else:
        return False
    if html is None:
        html = _shell('없음', '<p>그런 서비스·화면이 없어요.</p>', ('/policy', '← 검수 규칙'))
        code = 404
    else:
        code = 200
    handler._html(html, code)
    return True


def post(handler, store, path):
    if path != '/policy/set':
        return False
    length = int(handler.headers.get('Content-Length', 0) or 0)
    form = {k: v[0] for k, v in parse_qs(handler.rfile.read(length).decode('utf-8')).items()} if length else {}
    scope, target, rule, key = form.get('scope', ''), form.get('target', ''), form.get('rule', ''), form.get('key', '')
    raw = form.get('value', '')
    value = None if raw == '' else raw
    pol = policymod.Policy(store)
    back = form.get('back') or '/policy'
    try:
        with store.connect() as c:
            pol.set(c, scope, rule, value, target=target, key=key, actor=form.get('actor', ''), note='규칙 화면에서')
    except ValueError as e:
        handler._html(_shell('저장 못 함', f'<p class="note">{_e(str(e))}</p>', (back, '← 돌아가기')), 200)
        return True
    handler.send_response(303)
    handler.send_header('Location', back)
    handler.end_headers()
    return True
