"""판정 ↔ 규칙 잇기 — 사람이 후보에 내린 판정이 '어느 규칙 때문에 생긴 것인지'를 남긴다.

왜 필요한가: 검수기는 후보마다 「가변 글자(표 본문 값)」처럼 사람이 읽는 사유만 남겼다.
사람이 그 후보를 뒤집어도 **어느 규칙이 틀렸는지** 셀 수가 없어, 규칙을 고칠 근거가 안 쌓인다.
그래서 판정할 때마다 (규칙 이름, 엔진이 내린 자리, 사람이 내린 자리)를 한 행으로 쌓는다.

원칙(CLAUDE.md 2번·12번): 여기서 규칙을 자동으로 고치지 않는다. 세기만 한다.
규칙 발굴·제안은 다음 조각(④⑤)의 몫이고, 이 기록이 그 재료다. 행은 지우지 않는다.

규칙 이름은 검수기(engine/ui.html)의 표에 적힌 id를 그대로 쓴다 —
제외표(manual·tabStrip·designChrome·occluded·tabSelected) / 가변표(manual·pattern·tableHeader·
menu·role·repeat·button·screen) / 목록표(rowValueMissing). 규칙이 안 걸린 후보는 'none'.
"""
import json
import uuid
from datetime import datetime

SCHEMA = '''
CREATE TABLE IF NOT EXISTS rule_verdict (
 id TEXT PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL DEFAULT '',
 screen_id TEXT NOT NULL DEFAULT '', page_id TEXT NOT NULL DEFAULT '', run_id TEXT NOT NULL DEFAULT '',
 auto_run_id TEXT NOT NULL DEFAULT '', candidate_id TEXT NOT NULL, node_id TEXT NOT NULL DEFAULT '',
 rule TEXT NOT NULL, rule_reason TEXT NOT NULL DEFAULT '',
 engine_status TEXT NOT NULL DEFAULT '',
 from_status TEXT NOT NULL DEFAULT '', to_status TEXT NOT NULL DEFAULT '',
 outcome TEXT NOT NULL CHECK(outcome IN ('agree','overturn')),
 action TEXT NOT NULL DEFAULT 'status', label TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS rule_verdict_rule ON rule_verdict(rule, outcome);
CREATE INDEX IF NOT EXISTS rule_verdict_screen ON rule_verdict(screen_id);
CREATE TRIGGER IF NOT EXISTS rule_verdict_no_update BEFORE UPDATE ON rule_verdict BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS rule_verdict_no_delete BEFORE DELETE ON rule_verdict BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
'''

# 엔진이 내린 자리 → 포털 판정값 (auto_inspect.ENGINE_STATUS와 같은 표. 여기서 다시 import하면 서로 부르게 된다)
ENGINE_TO_STATUS = {'confirmed': 'open', 'excluded': 'excluded', 'variable': 'variable'}

RULE_TITLE = {
    'none': '규칙이 걸리지 않음(그냥 다르게 보임)',
    'manual': '사람이 전에 정한 것',
    'tabStrip': 'GNB 아래 탭 줄',
    'designChrome': '시안에 그려 넣은 브라우저 틀·작업표시줄',
    'occluded': '그림에서 다른 것에 가려 안 보임',
    'tabSelected': '선택된 탭(자리는 묻지 않음)',
    'pattern': '글자 꼴(숫자·날짜·안내문)',
    'tableHeader': '표 컬럼 제목은 고정',
    'menu': '메뉴·탭 이름은 고정',
    'role': '컴포넌트 역할 이름',
    'repeat': '표 본문·반복되는 행 안은 가변',
    'button': '버튼 모양 안의 글자는 고정',
    'screen': '화면 종류(공통=고정 / 일반=가변)',
    'rowValueMissing': '표 본문 값이 안 보이는 것은 데이터 차이',
    'exclude': '제외(규칙 이름 없음 — 옛 결과)',
    'value': '값 대조 — 시안 값과 다름(valueqa)',
}


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now().isoformat(timespec='seconds')


def rule_of(candidate_row):
    """후보 한 줄에서 (규칙 이름, 사유)를 꺼낸다. 엔진이 이름표를 안 붙였으면 'none'."""
    try:
        pol = json.loads(candidate_row['policy'] or '{}')
    except (TypeError, ValueError):
        pol = {}
    if not isinstance(pol, dict):
        pol = {}
    rule = str(pol.get('source') or '') or 'none'
    return rule, str(pol.get('reason') or '')


def record(c, candidate_row, to_status, actor='', action='status', note=''):
    """사람이 후보에 판정을 내릴 때마다 한 행. 엔진이 둔 자리와 같으면 'agree', 다르면 'overturn'.

    지적 등록(action='register')은 '엔진이 검토하라고 둔 것을 사람이 진짜 오류로 인정'한 것이라
    엔진이 confirmed로 뒀으면 agree다."""
    k = candidate_row
    rule, reason = rule_of(k)
    eng = str(k['engine_status'] or '')
    want = ENGINE_TO_STATUS.get(eng, 'open')
    outcome = 'agree' if want == to_status else 'overturn'
    row = c.execute('''SELECT a.id auto_run_id, a.page_id, a.run_id, r.screen_id
                       FROM auto_run a LEFT JOIN inspection_run r ON r.uuid=a.run_id WHERE a.id=?''',
                    (k['auto_run_id'],)).fetchone()
    try:
        nodes = json.loads(k['design_node_ids'] or '[]')
    except (TypeError, ValueError):
        nodes = []
    c.execute('INSERT INTO rule_verdict VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
              (uid(), now(), actor,
               (row['screen_id'] if row and row['screen_id'] else ''), (row['page_id'] if row else ''),
               (row['run_id'] if row else ''), k['auto_run_id'], k['id'], (nodes[0] if nodes else ''),
               rule, reason, eng, str(k['status'] or ''), to_status, outcome, action,
               str(k['label'] or ''), note))
    return outcome


# 어느 화면의 판정인지는 **페이지를 따라** 본다.
# rule_verdict.screen_id 는 '판정하던 그때의 화면'이라 append-only 로 굳어 있고(고치지 않는다),
# 검수 페이지를 다른 화면으로 옮기면(page_move.py) 지금 화면은 페이지가 알고 있다.
# 페이지를 못 적은 옛 행만 그때 적힌 화면으로 되짚는다.
_SCREEN_COND = ("(page_id IN (SELECT uuid FROM inspection_page WHERE screen_id=?)"
                " OR (page_id='' AND screen_id=?))")
_SCREEN_WHERE = 'WHERE ' + _SCREEN_COND


# ── 읽기: 규칙별 성적 ────────────────────────────────────────────
def stats(c, screen_id=None):
    """규칙마다 [나온 후보 수, 사람이 그대로 둔 수(agree), 사람이 뒤집은 수(overturn)].

    '나온 후보 수'는 지금 저장된 후보들 가운데 그 규칙이 이름표를 붙인 것의 수다(가장 최근 회차만 세지 않는다 —
    옛 회차도 사람이 그때 본 것이라 근거로 남긴다). 판정이 없는 후보는 사람이 아직 안 본 것이다."""
    where, args = '', []
    if screen_id:
        where = ' JOIN auto_run a ON a.id=k.auto_run_id JOIN inspection_run r ON r.uuid=a.run_id WHERE r.screen_id=?'
        args = [screen_id]
    fired = {}
    for k in c.execute(f'SELECT k.policy, k.id FROM auto_candidate k{where}', args):
        rule, _ = rule_of(k)
        fired[rule] = fired.get(rule, 0) + 1
    vw, vargs = (_SCREEN_WHERE, [screen_id, screen_id]) if screen_id else ('', [])
    judged = {}
    for r in c.execute(f'SELECT rule, outcome, COUNT(*) n FROM rule_verdict {vw} GROUP BY rule, outcome', vargs):
        judged.setdefault(r['rule'], {})[r['outcome']] = r['n']
    out = []
    for rule in sorted(set(fired) | set(judged), key=lambda x: (x == 'none', x)):
        g = judged.get(rule, {})
        agree, over = g.get('agree', 0), g.get('overturn', 0)
        out.append({'rule': rule, 'title': RULE_TITLE.get(rule, rule), 'fired': fired.get(rule, 0),
                    'agree': agree, 'overturn': over,
                    'rate': round(agree * 100 / (agree + over)) if (agree + over) else None})
    return out


def recent(c, screen_id=None, rule=None, limit=50):
    q, args, conds = 'SELECT * FROM rule_verdict', [], []
    if screen_id:
        conds.append(_SCREEN_COND); args += [screen_id, screen_id]
    if rule:
        conds.append('rule=?'); args.append(rule)
    if conds:
        q += ' WHERE ' + ' AND '.join(conds)
    q += ' ORDER BY rowid DESC LIMIT ?'
    args.append(limit)
    return [dict(r) for r in c.execute(q, args).fetchall()]
