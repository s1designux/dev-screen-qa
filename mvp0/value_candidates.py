"""값 대조 후보 — 시안 값과 개발 값이 다른 곳을 페이지 상세에 **후보**로 올린다.

왜: 값 대조(`valueqa/`)는 지금까지 수정요청서(문서)로만 나갔다. 문서는 출력물이라 어디에도 남지 않고,
사람이 "이건 괜찮다"고 판단한 것도 다음에 또 올라온다. 검수 결과는 데이터가 원본이어야 한다(CLAUDE.md 2번-1).
그래서 값 대조 결과도 그림 검수와 **같은 자리**(auto_candidate)에 쌓고, 페이지 상세에서 같이 본다.

읽는 자료는 촬영기가 접수 때 그림 옆에 함께 넣어 둔 두 개다(`capture-app/site/intake.py`):
  uploads/{page}_design.json   시안 값 (틀 + 요소)
  uploads/{page}_dev값.json    개발 화면에서 잰 값

여기서 나오는 것도 **후보**다(CLAUDE.md 2번-2) — 지적 등록·제외는 사람이 누른다.
그림 검수(engine/ui.html)와는 `auto_run.source` 로 갈라 둔다: 'engine' / 'value'.

값은 **마지막 차수의 개발 화면**을 잰 것이라 옛 차수에는 붙이지 않는다(그때 화면이 아니다).
자료가 바뀌면(시안·개발 값 파일 지문) 새 회차로 다시 재고, 사람이 내린 판정은 이어받는다. 옛 회차는 남는다.
"""
import hashlib
import json
import sys as _sys
import uuid as _uuid
from datetime import datetime
from pathlib import Path

_뿌리 = Path(__file__).resolve().parents[1]
if str(_뿌리) not in _sys.path:
    _sys.path.insert(0, str(_뿌리))

준비됨 = True
try:
    from valueqa.__main__ import 시안읽기
    from valueqa.candidates import 후보뽑기
    from valueqa.fixdoc import _css값
    from valueqa import 개발관행
except Exception:                                   # valueqa 가 없으면 조용히 꺼져 있는다
    준비됨 = False

import 설정 as _설정

출처 = 'value'                                       # 규칙 성적표(rule_log)에서 한 줄로 세어진다
KIND = 'value'                                      # 후보 종류 — 그림 검수의 종류와 섞이지 않게

색속성 = {'color', 'backgroundColor', 'borderColor'}
글자속성 = {'fontSize', 'fontWeight', 'fontFamily'}


def uid():
    return _uuid.uuid4().hex


def now():
    return datetime.now().isoformat(timespec='seconds')


def 자리():
    return Path(_설정.자리('포털.그림보관'))


def 자료(page_id, uploads=None):
    """그 페이지에 (시안 값, 개발 값) 파일이 둘 다 있으면 그 자리. 없으면 None."""
    u = Path(uploads) if uploads else 자리()
    시안길, 개발길 = u / f'{page_id}_design.json', u / f'{page_id}_dev값.json'
    return (시안길, 개발길) if (시안길.exists() and 개발길.exists()) else None


def 지문(시안길, 개발길):
    """두 자료의 지문. 하나라도 바뀌면 다시 잰다."""
    h = hashlib.sha1()
    for p in (시안길, 개발길):
        h.update(p.read_bytes())
    # 끝의 판 번호는 '카드에 담는 모양'이 바뀔 때 올린다 — 옛 회차는 남고, 사람이 내린 판정은 이어받는다.
    return 'value5:' + h.hexdigest()[:12]


def 대조(시안길, 개발길):
    시안 = 시안읽기(str(시안길))
    with open(개발길, encoding='utf-8') as f:
        개발 = json.load(f)
    return 후보뽑기(시안, 개발)


# ── 후보 한 건을 카드로 옮기기 ────────────────────────────────────
def _고칠줄(c):
    """그 후보에서 실제로 다른 줄만(참고·밀림·여백은 뺀다)."""
    return [r for r in (c.get('rows') or [])
            if r['j'] != 'pass' and not r.get('cascade') and not r.get('deferred')]


def 키(c):
    """차수·회차가 바뀌어도 같은 후보를 같은 것으로 알아보는 이름표.

    사람이 '제외'로 내린 판정을 다시 잴 때 이어받고, 수정요청서에서도 같은 것을 빼는 데 쓴다.
    다른 속성이 새로 어긋나면 다른 후보가 된다 — 사람이 한 번 더 본다(놓치는 쪽보다 낫다).
    """
    자리표 = (c.get('개발자리') or {}).get('고르개') or c.get('개발id') or '-'
    속성 = ','.join(sorted(r['k'] for r in _고칠줄(c))) or '구조'
    return '|'.join([c['갈래'], str(c.get('시안id') or '-'), str(자리표), 속성])


def 라벨(c):
    이름 = (c.get('이름') or '').strip()
    꼬리 = (' — ' + 이름[:40]) if 이름 else ''
    if c['갈래'] == '더있음':
        return '디자인에 없는 요소가 있음' + 꼬리
    if c['갈래'] == '빠짐':
        return '디자인에 있는 요소를 못 찾음' + 꼬리
    ks = {r['k'] for r in _고칠줄(c)}
    if ks and ks <= 색속성:
        머리 = '색상이 다르게 적용됨'
    elif ks and ks <= 글자속성:
        머리 = '폰트 모양·글자 값이 다름'
    else:
        머리 = '요소의 모양 또는 크기가 다름'
    return 머리 + 꼬리


def 자세히(c):
    줄 = ['%s %s → %s' % (r['label'], _css값(r['k'], r['a']), _css값(r['k'], r['b'])) for r in _고칠줄(c)]
    if not 줄:
        줄 = ['%s: 시안 %s · 개발 %s' % (d['속성'], d['시안'], d['개발']) for d in (c.get('다른곳') or [])]
    자리표 = (c.get('개발자리') or {}).get('고르개') or ''
    return ' · '.join(줄) + (' / 개발 자리 %s' % 자리표 if 자리표 else '')


def 시안값(c):
    return ' · '.join('%s %s' % (r['label'], _css값(r['k'], r['a'])) for r in _고칠줄(c))


def 줄들(c):
    """카드가 [무엇이 · 지금 개발 · 디자인 기준] 세 칸으로 그릴 줄. 글월을 되읽지 않게 값째로 남긴다."""
    줄 = [{'이름': r['label'], '기준': _css값(r['k'], r['a']), '개발': _css값(r['k'], r['b'])}
          for r in _고칠줄(c)]
    if not 줄:
        줄 = [{'이름': d['속성'], '기준': str(d['시안']), '개발': str(d['개발'])}
              for d in (c.get('다른곳') or [])]
    return 줄


def _잣대(결과, run):
    """개발 값(웹 좌표) → 개발 그림(촬영본) 좌표로 옮기는 배율·기준점.

    잰 값의 자리는 '판(아트보드)' 기준이고 촬영본은 '내용'만 담는다.
    contentX/Y 는 판 위에서 내용이 놓인 자리를 음수로 적어 둔 값이라 **더해야** 0에 맞는다.
    (예: contentX=-960 이면 판의 x=960 이 촬영본의 x=0)"""
    m = (결과.get('meta') or {}).get('개발') or {}
    폭 = m.get('docW') or m.get('artboardWidth') or m.get('viewportWidth') or 0
    k = ((run['dev_img_w'] or 폭) / 폭) if 폭 else 1
    return k, m.get('contentX') or 0, m.get('contentY') or 0


def _상자(c, k, dx, dy):
    """후보를 개발 그림 위 어디에 그릴지.

    개발에서 잰 상자(devBox)만 판 기준이라 contentX/Y 로 옮긴다.
    '디자인에 있는데 개발에 없음' 후보는 잴 개발 요소가 없어 시안 상자를 쓰는데,
    그건 이미 시안 프레임 기준이라 개발 보정을 먹이면 화면 밖으로 나간다."""
    dev = c.get('devBox')
    b = dev or c.get('box') or {}
    if not b:
        return None, None, None, None
    ox, oy = (dx, dy) if dev else (0, 0)
    return ((b['x'] + ox) * k, (b['y'] + oy) * k, b['w'] * k, b['h'] * k)


# ── 저장 ────────────────────────────────────────────────────────
def 챙기기(store, page_id, run, 길):
    """그 차수의 값 대조 후보를 (없거나 자료가 바뀌었으면 다시 재서) 돌려준다."""
    시안길, 개발길 = 길
    판 = 지문(시안길, 개발길)
    with store.connect() as c:
        r = c.execute("SELECT * FROM auto_run WHERE run_id=? AND source=? ORDER BY rowid DESC LIMIT 1",
                      (run['uuid'], 출처)).fetchone()
        if r and r['engine'] == 판 and r['status'] == 'done':
            return [dict(x) for x in c.execute('SELECT * FROM auto_candidate WHERE auto_run_id=? ORDER BY no', (r['id'],))]
        옛것 = {}
        if r:
            for x in c.execute('SELECT * FROM auto_candidate WHERE auto_run_id=?', (r['id'],)):
                try:
                    p = json.loads(x['policy'] or '{}')
                except (TypeError, ValueError):
                    p = {}
                if p.get('키'):
                    옛것[p['키']] = x
        결과 = 대조(시안길, 개발길)
        배율, dx, dy = _잣대(결과, run)
        새회차 = uid()
        # 개발 관행 표가 접은 것도 회차에 함께 남긴다 — 어느 규칙이 몇 건을 접었는지 되짚을 수 있게(2번-3).
        접음 = {}
        for x in 결과.get('접은것') or []:
            접음[x['규칙']] = 접음.get(x['규칙'], 0) + 1
        알림 = [{'규칙': k, '이름': 개발관행.제목.get(k, k), '건수': v} for k, v in sorted(접음.items(), key=lambda kv: -kv[1])]
        c.execute('INSERT INTO auto_run(id,page_id,run_id,status,engine,created_at,finished_at,capture_w,capture_h,design_id,source,notices)'
                  ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                  (새회차, page_id, run['uuid'], 'done', 판, now(), now(),
                   run['dev_img_w'], run['dev_img_h'], '', 출처, json.dumps(알림, ensure_ascii=False)))
        for n, k in enumerate(결과.get('후보') or [], 1):
            이름표 = 키(k)
            앞 = 옛것.get(이름표)
            상태 = 앞['status'] if 앞 else 'open'
            지적 = 앞['issue_id'] if 앞 else None
            x, y, w, h = _상자(k, 배율, dx, dy)
            새후보 = uid()
            c.execute('INSERT INTO auto_candidate VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (새후보, 새회차, n, KIND, 라벨(k), 자세히(k),
                       int(round((k.get('신뢰도') or 0) * 100)), 상태, 'confirmed',
                       json.dumps({'source': 출처, '키': 이름표, '줄': 줄들(k),
                                  '자리': (k.get('개발자리') or {}).get('고르개') or ''}, ensure_ascii=False),
                       x, y, w, h,
                       json.dumps(k.get('box') or {}, ensure_ascii=False),
                       json.dumps([k['시안id']] if k.get('시안id') else [], ensure_ascii=False),
                       시안값(k), 지적))
            if 앞 and 상태 != 'open':               # 사람이 전에 내린 판정을 이어받았다는 것도 이력으로 남긴다
                c.execute('INSERT INTO auto_candidate_event VALUES (?,?,?,?,?,?,?)',
                          (uid(), 새후보, 'open', 상태, '', now(), '앞 회차 판정 이어받음'))
        return [dict(x) for x in c.execute('SELECT * FROM auto_candidate WHERE auto_run_id=? ORDER BY no', (새회차,))]


def 마지막차수인가(store, page_id, run):
    with store.connect() as c:
        m = c.execute('SELECT MAX(round) m FROM inspection_run WHERE page_id=?', (page_id,)).fetchone()['m']
    return (not m) or run['round'] == m


def 붙이기(store, page_id, run, base):
    """그림 검수 화면 재료(base)에 값 대조 후보를 얹는다. 그림 검수가 없는 페이지면 값 대조만으로 화면을 만든다."""
    if not 준비됨 or not run:
        return base
    길 = 자료(page_id)
    if not 길 or not 마지막차수인가(store, page_id, run):
        return base
    try:
        값후보 = 챙기기(store, page_id, run, 길)
    except Exception:                               # 값 대조가 깨져도 페이지는 열려야 한다
        return base
    if not 값후보:
        return base
    if base is None:
        base = {'run': {'id': '', 'run_id': run['uuid'], 'status': 'done', 'error': '', 'notices': '[]', 'range': '{}'},
                'candidates': [], 'issue_numbers': {}, 'round': run['round'], 'scale': 1,
                'range': {'manual_top': None, 'manual_bottom': None,
                          'dev_img': run['dev_img'], 'w': run['dev_img_w'], 'h': run['dev_img_h']},
                'screen_id': run['screen_id'], '값만': True}
    앞번호 = max([k['no'] for k in base['candidates']] or [0])
    for i, k in enumerate(값후보, 1):
        k['no'] = 앞번호 + i                          # 번호는 화면에 보이는 차례대로 (그림 검수 다음)
    base['candidates'] = list(base['candidates']) + 값후보
    base['값후보'] = len(값후보)
    if any(k['issue_id'] for k in 값후보) and not base['issue_numbers']:
        with store.connect() as c:
            rows = c.execute('SELECT uuid FROM inspection_issue WHERE page_id=? ORDER BY rowid', (page_id,)).fetchall()
        base['issue_numbers'] = {r['uuid']: n + 1 for n, r in enumerate(rows)}
    return base


def 값후보인가(k):
    try:
        return (json.loads(k['policy'] or '{}') or {}).get('source') == 출처
    except (TypeError, ValueError):
        return False


# ── 수정요청서 쪽에서 쓰는 것: 사람이 내린 판정 ─────────────────────
def 판정표(store, page_ids):
    """{page_id: {키: 상태}} — 수정요청서가 '제외'된 것을 빼는 데 쓴다(문서는 데이터를 읽어 만든다)."""
    표 = {}
    if not page_ids:
        return 표
    with store.connect() as c:
        물음표 = ','.join('?' * len(page_ids))
        try:
            rows = c.execute(
                f"""SELECT a.page_id, k.policy, k.status FROM auto_candidate k
                    JOIN auto_run a ON a.id=k.auto_run_id
                    WHERE a.source=? AND a.page_id IN ({물음표})
                    ORDER BY a.rowid""", [출처] + list(page_ids)).fetchall()
        except Exception:                           # 옛 DB(자동 검수 표 없음)
            return 표
    for r in rows:
        try:
            p = json.loads(r['policy'] or '{}')
        except (TypeError, ValueError):
            continue
        if p.get('키'):
            표.setdefault(r['page_id'], {})[p['키']] = r['status']
    return 표


def 거른것(결과, 판정):
    """사람이 '제외·가변'으로 내린 후보를 결과에서 뺀다. 판정이 없으면 그대로."""
    if not 판정:
        return 결과
    남길 = [c for c in (결과.get('후보') or []) if 판정.get(키(c), 'open') == 'open']
    if len(남길) == len(결과.get('후보') or []):
        return 결과
    결과 = dict(결과)
    결과['후보'] = 남길
    셈 = dict(결과.get('셈') or {})
    셈['후보'] = len(남길)
    셈['값다름'] = sum(1 for c in 남길 if c['갈래'] == '값다름')
    셈['더있음'] = sum(1 for c in 남길 if c['갈래'] == '더있음')
    셈['빠짐'] = sum(1 for c in 남길 if c['갈래'] == '빠짐')
    결과['셈'] = 셈
    return 결과
