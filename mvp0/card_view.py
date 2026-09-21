"""후보 카드 본문 — 무엇이 기준이고, 지금은 어떻게 되어 있고, 개발자는 어디를 보면 되는지.

왜 (river 2026-09-14):
  카드 아래에 detail·디자인 원본값·가변 판정·위치가 회색 글줄로 줄줄이 붙어 있었다.
  값 대조 후보는 detail 왼쪽 값과 '디자인 원본값'이 **같은 말을 두 번** 했고,
  어느 쪽이 기준인지, 개발자가 코드에서 어디를 봐야 하는지가 한눈에 안 보였다.

여기서 하는 일:
  ① 같은 말은 한 번만 — 기준값은 표의 '디자인 기준' 칸에만 적는다
  ② 줄 나누기 — [무엇이 · 지금 개발 · 디자인 기준] 세 칸(잰 값이 없으면 두 칸)
  ③ '개발이 볼 자리'(선택자·컴포넌트·화면 좌표)를 아래에 따로 묶는다
  ④ 기준값에 **토큰·컴포넌트 이름**이 있으면 그 이름을 함께 — 없으면 헥사 그대로(레거시 화면)

읽기 전용이다. 판정·저장은 건드리지 않는다.
"""
import json
import re
import sqlite3
import sys as _sys
import time
from pathlib import Path

_뿌리 = Path(__file__).resolve().parents[1]
if str(_뿌리) not in _sys.path:
    _sys.path.insert(0, str(_뿌리))
import 설정 as _설정


def _e(v):
    return (str(v if v is not None else '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _g(k, name, default=''):
    try:
        v = k[name]
    except (KeyError, IndexError, TypeError):
        return default
    return default if v is None else v


def _짐(v):
    try:
        x = json.loads(v or 'null')
    except (TypeError, ValueError):
        return None
    return x


# ── 값 한 조각에서 '이름'과 '값'을 가른다 ────────────────────────────
# 이름표는 우리가 적은 것만 안다(valueqa/compare.py 이름표 + engine/ui.html formatDesignValues).
_속성이름 = (
    '가로 위치', '세로 위치', '너비', '높이', '글자색', '배경색', '글자 크기', '글자 굵기', '글꼴',
    '모서리 둥글기', '테두리 두께', '테두리색', '안쪽여백↑', '안쪽여백→', '안쪽여백↓', '안쪽여백←',
    '크기', '굵기', '줄높이', '색', '배경', '테두리', '둥글기', '글자',
    '디자인 간격', '디자인 위 여백', '간격',
)
_이름고침 = {'디자인 간격': '간격', '디자인 위 여백': '위 여백', '색': '글자색', '배경': '배경색', '테두리': '테두리색'}
_상자꼴 = re.compile(r'^[\d.]+×[\d.]+$')
_긴이름순 = tuple(sorted(_속성이름, key=len, reverse=True))


def _쪼개기(조각):
    """'배경색 var(--color-surface-default)' → ('배경색', 'var(--color-surface-default)'). 모르는 모양이면 (None, 조각)."""
    조각 = (조각 or '').strip()
    for 이름 in _긴이름순:
        if 조각.startswith(이름 + ' '):
            return _이름고침.get(이름, 이름), 조각[len(이름) + 1:].strip()
    if _상자꼴.match(조각):
        return '상자 크기', 조각
    return None, 조각


def _줄(이름, 기준, 개발=None):
    return {'이름': 이름, '기준': 기준, '개발': 개발}


# ── 후보 한 건 → 표로 그릴 줄들 ──────────────────────────────────
_글자따옴 = re.compile(r'디자인 글자\s*:\s*[“"]([^”"]*)[”"]\.?')
_색따옴 = re.compile(r'디자인 (글자색|배경)\s+(#[0-9A-Fa-f]{3,8}|rgba?\([^)]*\))')
# 그림 한 덩어리(로고)의 가로폭 — 엔진이 적어 준 글월을 한 줄 표로 편다
_그림폭 = re.compile(r'디자인 그림은 가로 ([\d.]+)px\s*·\s*개발 이미지는 약 ([\d.]+)px로 보입니다\(([^)]*)\)\.?')


def _값후보줄(k):
    """값 대조 후보 — 잰 값이 있다. 새 판은 policy['줄']에, 옛 판은 글월을 되읽어 쓴다."""
    pol = _짐(_g(k, 'policy')) or {}
    자리 = pol.get('자리') or ''
    줄들 = []
    for r in pol.get('줄') or []:
        줄들.append(_줄(r.get('이름'), r.get('기준', ''), r.get('개발')))
    if 줄들:
        return 줄들, 자리
    글 = str(_g(k, 'detail'))
    if ' / 개발 자리 ' in 글:
        글, 자리 = 글.split(' / 개발 자리 ', 1)
    for 조각 in 글.split(' · '):
        if ' → ' not in 조각:
            continue
        왼, 오 = 조각.split(' → ', 1)
        이름, 기준 = _쪼개기(왼)
        줄들.append(_줄(이름, 기준, 오.strip()))
    return 줄들, 자리.strip()


def _그림후보줄(k):
    """그림 검수 후보 — 개발 쪽은 잰 값이 없다(눈으로 대조). 기준값만 줄로 편다."""
    줄들, 안내 = [], []
    글 = str(_g(k, 'detail')).strip()
    m0 = _그림폭.search(글)
    if m0:
        줄들.append(_줄('가로폭', m0.group(1) + 'px', '약 ' + m0.group(2) + 'px'))
        안내.append(m0.group(3).strip())
        글 = _그림폭.sub('', 글)
    m = _글자따옴.search(글)
    if m:
        줄들.append(_줄('글자', '“' + m.group(1) + '”'))
        글 = _글자따옴.sub('', 글)
    for m2 in _색따옴.finditer(글):
        줄들.append(_줄(_이름고침.get(m2.group(1), m2.group(1)), m2.group(2)))
    글 = _색따옴.sub('', 글)
    글 = re.sub(r'\s*[·—-]\s*$', '', re.sub(r'\s{2,}', ' ', 글).strip()).strip()
    글 = re.sub(r'^\s*[·—-]\s*', '', 글).strip()
    if 글:
        안내.append(글)
    본 = set()
    for 줄 in 줄들:
        본.add(줄['이름'])
    for 칸 in str(_g(k, 'design_values')).split('\n'):
        for 조각 in 칸.split(' · '):
            조각 = 조각.strip()
            if not 조각:
                continue
            이름, 값 = _쪼개기(조각)
            if 이름 == '개발 이미지 약' or 조각.startswith('개발 이미지 약'):
                if 줄들:
                    줄들[-1]['개발'] = 조각.replace('개발 이미지 ', '')
                continue
            if 이름 and 이름 in 본:
                continue
            if 이름:
                본.add(이름)
            줄들.append(_줄(이름, 값))
    return 줄들, ' '.join(안내)


def 줄뽑기(k):
    """(줄들, 개발자리, 안내글, 잰것인가)"""
    pol = _짐(_g(k, 'policy')) or {}
    if pol.get('source') == 'value':
        줄들, 자리 = _값후보줄(k)
        return 줄들, 자리, '', True
    줄들, 안내 = _그림후보줄(k)
    return 줄들, '', 안내, False


# ── 시안 요소(토큰·컴포넌트) ─────────────────────────────────────
_요소캐시 = {}


def _자료함():
    return Path(_설정.자리('포털.자료함'))


def 요소표(page_id, database=None, uploads=None):
    """그 페이지에 붙은 시안의 요소를 {노드id: 요소}로. 못 찾으면 빈 표(카드는 그대로 그려진다)."""
    if not page_id:
        return {}
    이제 = time.time()
    앞 = _요소캐시.get(page_id)
    if 앞 and 이제 - 앞[0] < 2.0:
        return 앞[1]
    요소들 = []
    try:
        con = sqlite3.connect('file:%s?mode=ro' % (database or _자료함()), uri=True)
        try:
            con.row_factory = sqlite3.Row
            r = con.execute('SELECT e.elements FROM page_design_link l JOIN design_elements e'
                            ' ON e.design_id=l.design_id WHERE l.page_id=?', (page_id,)).fetchone()
            if r:
                요소들 = _짐(r['elements']) or []
        finally:
            con.close()
    except sqlite3.Error:
        요소들 = []
    if not 요소들:
        길 = Path(uploads or _설정.자리('포털.그림보관')) / ('%s_design.json' % page_id)
        if 길.exists():
            try:
                요소들 = (json.loads(길.read_text(encoding='utf-8')) or {}).get('요소') or []
            except (OSError, ValueError):
                요소들 = []
    표 = {e.get('id'): e for e in 요소들 if isinstance(e, dict) and e.get('id')}
    _요소캐시[page_id] = (이제, 표)
    return 표


def 기준요소(k, 표):
    """후보가 가리키는 시안 요소와, 그 요소가 속한 컴포넌트(위로 거슬러 찾은 첫 인스턴스)."""
    if not 표:
        return None, None
    ids = _짐(_g(k, 'design_node_ids')) or []
    요소 = next((표[i] for i in ids if i in 표), None)
    if 요소 is None:
        return None, None
    컴 = 요소
    본 = 0
    while 컴 is not None and 본 < 8:
        if 컴.get('component'):
            return 요소, 컴
        컴 = 표.get(컴.get('parentId'))
        본 += 1
    return 요소, None


def 컴포넌트말(컴):
    c = (컴 or {}).get('component') or {}
    이름 = (c.get('set') or c.get('name') or '').strip()
    if not 이름:
        return ''
    값 = [str(v) for v in (c.get('props') or {}).values() if str(v).strip()]
    return 이름 + (' · ' + ' · '.join(값) if 값 else '')


_토큰칸 = {'배경색': ('fill', 'backgroundColor'), '글자색': ('color',), '테두리색': ('stroke', 'borderColor'),
           '테두리 두께': ('strokeWidth', 'borderWidth'), '모서리 둥글기': ('radius', 'borderRadius'),
           '둥글기': ('radius',), '글자 크기': ('fontSize',), '크기': ('fontSize',),
           '글자 굵기': ('fontWeight',), '굵기': ('fontWeight',), '글꼴': ('fontFamily',), '글자': ('text',)}


def 토큰표(요소):
    """시안 요소에 실려 온 디자인가이드 이름. 레거시 화면은 비어 있다(그러면 헥사 그대로 보인다)."""
    if not 요소:
        return {}
    t = 요소.get('토큰') or 요소.get('tokens') or {}
    return t if isinstance(t, dict) else {}


def 토큰이름(이름, 표):
    for 칸 in _토큰칸.get(이름 or '', ()):
        if 표.get(칸):
            return str(표[칸])
    return ''


_갈래말 = {'더있음': '디자인에 없는 것이 개발 화면에 있어요 — 값이 아니라 있고 없고를 봅니다.',
           '빠짐': '디자인에는 있는데 개발 화면에서 못 찾았어요 — 값이 아니라 있고 없고를 봅니다.'}


def 갈래말(k):
    키 = ((_짐(_g(k, 'policy')) or {}).get('키') or '').split('|')[0]
    return _갈래말.get(키, '견줄 값이 없어요 — 개발 화면과 눈으로 대조해 주세요.')


# ── 카드에 그리기 ────────────────────────────────────────────────
def 제목(k):
    """라벨에서 요소 이름 꼬리(' — …')를 뗀 앞머리. 꼬리는 본문 첫 줄로 내려간다."""
    return str(_g(k, 'label')).split(' — ', 1)[0].strip() or '차이 후보'


def 이름꼬리(k):
    쪽 = str(_g(k, 'label')).split(' — ', 1)
    return 쪽[1].strip() if len(쪽) > 1 else ''


# Figma가 알아서 붙인 이름(Rectangle 3 …)은 사람에게 아무것도 알려주지 않는다 — 그럴 땐 라벨 꼬리를 쓴다.
_흔한이름 = re.compile(r'^(rectangle|frame|group|vector|ellipse|line|union|subtract|component|instance|image|mask)\b', re.I)


def 쓸이름(레이어, 꼬리):
    레이어 = (레이어 or '').strip()
    if 레이어 and not _흔한이름.match(레이어):
        return 레이어
    return (꼬리 or 레이어 or '').strip()


def 컴포넌트이름(k, page_id=None, database=None, uploads=None):
    """그 후보가 속한 시안 컴포넌트 이름. 컴포넌트로 만들어 두지 않은 요소면 빈 글자."""
    return 컴포넌트말(기준요소(k, 요소표(page_id, database, uploads))[1])


def 곁말들(k, page_id=None, database=None, uploads=None):
    """제목 옆에 붙일 작은 말 — [컴포넌트, 요소 이름]. 같은 말이면 한 번만.

    요소 이름은 예전에 본문 첫 줄로 따로 내려가 **두 줄**이 됐다(‘W/Footer · 값 대조’ 밑에 ‘m_footer’).
    나눌 까닭이 없어 한 줄로 합친다(river 2026-09-16).
    """
    요소, 컴 = 기준요소(k, 요소표(page_id, database, uploads))
    컴말 = 컴포넌트말(컴)
    이름 = 쓸이름((요소 or {}).get('name'), 이름꼬리(k))
    if 이름 and 컴말.startswith(이름):
        이름 = ''
    return [x for x in (컴말, 이름[:60]) if x]


def body_html(k, page_id=None, database=None, uploads=None, 이름빼기=False):
    """이름빼기=True 면 요소 이름 줄을 그리지 않는다 — 부르는 쪽이 제목 옆에 이미 적었을 때."""
    줄들, 자리, 안내, 잰것 = 줄뽑기(k)
    표 = 요소표(page_id, database, uploads)
    요소, 컴 = 기준요소(k, 표)
    토큰 = 토큰표(요소)
    컴말 = 컴포넌트말(컴)
    조각 = ['<div class="c-body">']

    이름 = 쓸이름((요소 or {}).get('name'), 이름꼬리(k))
    if 이름빼기 or (이름 and 컴말.startswith(이름)):
        이름 = ''                                    # 제목 옆에 이미 적었거나, 컴포넌트와 같은 말이면 한 번만
    if 이름:
        조각.append('<div class="c-sub">%s</div>' % _e(이름[:60]))
    if 안내:
        조각.append('<p class="c-lead">%s</p>' % _e(안내))

    if 줄들:
        여럿 = 잰것 or any(r['개발'] for r in 줄들)
        조각.append('<div class="c-diff%s">' % ('' if 여럿 else ' one'))
        조각.append('<span class="hd"></span>')   # 첫 칸 제목은 두지 않는다 — 아래 줄 이름이 스스로 말한다(river 2026-09-14)
        if 여럿:
            조각.append('<span class="hd">지금 개발</span><span class="hd"></span>')
        조각.append('<span class="hd">디자인 기준</span>')
        for r in 줄들:
            tk = 토큰이름(r['이름'], 토큰)
            조각.append('<span class="nm">%s</span>' % _e(r['이름'] or '값'))
            if 여럿:
                조각.append('<span class="now">%s</span><span class="to">→</span>'
                            % _e(r['개발'] if r['개발'] else '—'))
            조각.append('<span class="ref">%s%s</span>'
                        % (_e(r['기준']), ('<b class="c-tok">%s</b>' % _e(tk)) if tk else ''))
        조각.append('</div>')

    if not 잰것 and not any(r['개발'] for r in 줄들):
        조각.append('<p class="c-eye">개발 값을 재지 못한 자리예요 — 위 기준과 개발 화면을 눈으로 대조해 주세요.</p>')
    elif not 줄들:
        조각.append('<p class="c-eye">%s</p>' % _e(갈래말(k)))

    칸 = []
    if 자리:
        칸.append(('개발이 볼 자리', '<code class="c-sel">%s</code>' % _e(자리)))
    # '디자인 컴포넌트'는 본문에 줄을 두지 않는다 — 있을 때만 **제목 옆 글씨**로 나간다(river 2026-09-14).
    # '화면 자리'(핀 번호 · 좌표 · 크기) 줄은 두지 않는다 (river 확정 2026-09-14).
    # 번호는 카드 왼쪽 위에 이미 크게 붙어 있고, 픽셀 좌표는 개발이 쓰지 않는다 —
    # 수정요청서는 좌표 대신 선택자와 '아래쪽 가운데' 같은 말로 자리를 가리킨다.
    if 칸:
        조각.append('<dl class="c-where">' + ''.join(
            '<dt>%s</dt><dd>%s</dd>' % (_e(a), b) for a, b in 칸) + '</dl>')

    pol = _짐(_g(k, 'policy')) or {}
    if pol.get('reason'):
        조각.append('<div class="c-note">규칙 · %s</div>' % _e(pol['reason']))
    조각.append('</div>')
    return ''.join(조각)


CSS = '''
/* 제목이 오른쪽 위 '제외' 단추 밑으로 숨지 않게 자리를 비워 둔다 */
.auto-card .ihead{padding-right:var(--spacing-56)}
.auto-card .ihead b{line-height:1.45;word-break:keep-all}
.c-body{margin-top:var(--spacing-2);font-size:var(--font-size-12);color:var(--color-text-secondary)}
.c-sub{margin:0 0 var(--spacing-8);font-size:var(--font-size-12);font-weight:var(--font-weight-bold);color:var(--color-text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.c-lead{margin:0 0 var(--spacing-8);color:var(--color-text-tertiary);line-height:1.55}
.c-diff{display:grid;gap:var(--spacing-4) var(--spacing-12);align-items:baseline;margin:0;justify-content:start;
  grid-template-columns:max-content minmax(0,max-content) 10px minmax(0,max-content)}
.c-diff.one{grid-template-columns:max-content minmax(0,1fr)}
.c-diff .hd{font-size:var(--font-size-10);font-weight:var(--font-weight-bold);color:var(--color-text-helper);padding-bottom:var(--spacing-4)}
.c-diff .nm{color:var(--color-text-caption);white-space:nowrap}
.c-diff .now{color:var(--color-text-danger);font-weight:var(--font-weight-bold);word-break:break-all}
.c-diff .to{color:var(--color-border-default);text-align:center}
.c-diff .ref{color:var(--color-text-primary);font-weight:var(--font-weight-bold);word-break:break-all}
.c-tok{display:block;font-size:var(--font-size-10);font-weight:var(--font-weight-bold);color:var(--color-text-secondary);letter-spacing:.01em}
.c-eye{margin:var(--spacing-8) 0 0;color:var(--color-text-caption)}
/* 윗선을 두지 않는다 — 차이 묶음을 가르는 판 테두리와 생김새가 같아 헷갈렸다(river 2026-09-14) */
.c-where{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:var(--spacing-4) var(--spacing-10);
  margin:var(--spacing-10) 0 0;padding-top:var(--spacing-8)}
.c-where dt{color:var(--color-text-helper);font-size:var(--font-size-12);white-space:nowrap}
.c-where dd{margin:0;color:var(--color-text-tertiary);font-size:var(--font-size-12);min-width:0}
.c-sel{font-family:ui-monospace,monospace;font-size:var(--font-size-12);color:var(--color-text-secondary);background:var(--color-bg-subtle);
  border-radius:var(--radius-4);padding:var(--spacing-2) var(--spacing-6);word-break:break-all}
.c-comp{font-weight:var(--font-weight-bold);color:var(--color-text-secondary)}
.c-note{margin-top:var(--spacing-8);color:var(--color-text-helper);font-size:var(--font-size-12)}
'''
