"""개발화면 검수결과서 — 프로젝트 하나를 한 장짜리 문서로 반출한다.

원본은 DB다. 이 문서는 그 데이터를 그려 낸 출력물일 뿐이다(CLAUDE.md 2번-1).
종이는 **가로 A4**(13·16번), 장 구성은 `표지 → 화면마다 간지 → 검수 페이지 한 장씩`.

한 장 안: 위에 머리글(스토리보드 ID · 검수일 · 몇 차 · Pass/Fail),
아래 왼쪽 시안 · 가운데 개발 화면(번호 핀) · 오른쪽 수정필요 목록.

담는 것은 **사람이 제외하지 않은 것 전부**다 (river 확정 2026-09-16):
수정필요로 올린 것 + 검수기가 찾아 둔 것 중 사람이 제외·가변으로 내리지 않은 것.
사람이 제외하면 문서에서도 빠진다. 처리된 것(협의통과·검수완료·오류아님)은 넣지 않는다.

범위 둘 (river 2026-09-16):
- `open` — 수정필요가 있는 페이지만. 중간에 보내는 문서.
- `all`  — 모든 페이지. 마지막에 받는 문서.

표지·간지 모양은 `design-report-byriv`(river 정본) 규격을 따른다 —
강한 브랜드 면 → 제목 → 날짜·프로젝트 → 조직 차례, 본문 레이아웃을 표지에 쓰지 않는다.
"""
import base64
import html
import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import auto_inspect
import card_view
import db as dbmod
import issue_categories
import queries
import s1_tokens
from constants import UNRESOLVED_STATUSES
import 설정

한장묶음 = 12        # 한 장에 담는 수정필요 줄 수 — 넘으면 다음 장으로 이어 붙인다
최대폭 = 1400          # 문서에 담는 그림의 가로 px — 종이에 찍기엔 이만하면 넘친다
핀반지름 = 26
SCOPES = {'open': '수정필요가 있는 페이지', 'all': '모든 페이지'}


def _e(v):
    return html.escape(str(v)) if v is not None else ''


def 그림자리():
    return Path(설정.자리('포털.그림보관'))


def 그림담기(파일):
    """PNG 한 장을 문서 안에 품는다(JPEG 로 줄여서). 포털이 꺼져 있어도 열리게 한다."""
    if not 파일:
        return None
    p = 그림자리() / 파일
    if not p.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(p)
        im.load()
    except OSError:
        return None
    if im.mode in ('RGBA', 'LA', 'P'):
        바탕 = Image.new('RGB', im.size, (255, 255, 255))
        im = im.convert('RGBA')
        바탕.paste(im, mask=im.split()[-1])
        im = 바탕
    else:
        im = im.convert('RGB')
    if im.width > 최대폭:
        im = im.resize((최대폭, max(1, round(im.height * 최대폭 / im.width))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=78, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def 핀자리(항목들, 폭):
    """핀은 상자 위쪽 바깥에 둔다. 겹치면 옆으로만 민다(페이지 상세와 같은 규칙)."""
    R, 최소, 걸음 = 핀반지름, 72, 74
    놓은것, 결과 = [], []
    for i in 항목들:
        x, y = i['상자'][0], i['상자'][1]
        기준 = x + 30
        px, py, 안전 = 기준, max(R + 4, y - R - 4), 0
        while any((px - qx) ** 2 + (py - qy) ** 2 < 최소 * 최소 for qx, qy in 놓은것) and 안전 < 90:
            px += 걸음
            if px > 폭 - 30:
                px, py = 기준, max(R + 4, py - 64)
            안전 += 1
        놓은것.append((px, py))
        결과.append((px, py))
    return 결과


def 덧그림(항목들, vb_w, vb_h):
    """개발 화면 위에 얹는 상자·핀. 좌표는 그 차수의 기준 크기(coord_ref) 자 위에 있다."""
    if not 항목들:
        return ''
    상자 = 선 = 핀 = ''
    for i, (px, py) in zip(항목들, 핀자리(항목들, vb_w)):
        x, y, w, h = i['상자']
        c = issue_categories.color(None)
        상자 += f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{c}" fill-opacity=".12" stroke="{c}" stroke-width="3"/>'
        if py < y - 4:
            tx = min(max(px, x), x + w)
            선 += f'<line x1="{px}" y1="{py + 핀반지름}" x2="{tx}" y2="{y}" stroke="{c}" stroke-width="2"/>'
        핀 += (f'<g transform="translate({px},{py})"><circle r="{핀반지름}" fill="{c}"/>'
              f'<text y="9" text-anchor="middle" font-size="30" font-weight="700" fill="#fff">{i["번호"]}</text></g>')
    return (f'<svg class="ov" viewBox="0 0 {vb_w} {vb_h}" preserveAspectRatio="xMidYMin meet">'
            f'{상자}{선}{핀}</svg>')


def _줄글(줄):
    """[무엇이] 지금 개발 → 시안 기준. 잰 값이 없으면 기준만 적는다."""
    이름 = 줄.get('이름') or ''
    기준, 개발 = 줄.get('기준') or '', 줄.get('개발') or ''
    값 = f'{_e(개발)} → {_e(기준)}' if 개발 and 기준 else _e(기준 or 개발)
    return f'<p class="v"><b>{_e(이름)}</b> {값}</p>' if 값 else ''


def 항목_지적(i):
    """사람이 올린 수정필요 한 건."""
    속성 = json.loads(i['properties']) if i['properties'] else []
    줄 = {'이름': ' · '.join(속성) or '값', '기준': i['expected'] or '', '개발': i['actual'] or ''}
    return {'제목': i['description'] or issue_categories.label(i['category']),
            '갈래': issue_categories.label(i['category']), '꼬리': i['status'],
            '줄들': [줄] if (줄['기준'] or 줄['개발']) else [], '자리': '',
            '상자': [i['box_x'] or 0, i['box_y'] or 0, i['box_w'] or 0, i['box_h'] or 0]}


def 항목_후보(k, 배율):
    """검수기가 찾아 둔 것 한 건. 사람이 제외하지 않았으니 고쳐야 할 것으로 본다."""
    줄들, 자리, 안내, _ = card_view.줄뽑기(k)
    갈래 = issue_categories.label(auto_inspect.candidate_category(k))
    return {'제목': k['label'] or 갈래, '갈래': 갈래,
            '꼬리': '값 대조' if (k['policy'] or '').find('"value"') >= 0 else '검수기',
            '줄들': 줄들, '자리': 자리 or 안내,
            '상자': [(k['box_x'] or 0) * 배율, (k['box_y'] or 0) * 배율,
                   (k['box_w'] or 0) * 배율, (k['box_h'] or 0) * 배율]}


def 후보항목(conn, page_id, run_id, 기준폭):
    """그 차수의 마지막 검수 결과에서, 사람이 제외하지 않은 것만. 좌표는 기준 자로 옮겨 온다."""
    나온것 = []
    try:
        for 출처 in ('engine', 'value'):
            r = conn.execute("SELECT * FROM auto_run WHERE page_id=? AND run_id=? AND source=? AND status='done'"
                             " ORDER BY rowid DESC LIMIT 1", (page_id, run_id, 출처)).fetchone()
            if not r:
                continue
            잰폭 = r['capture_w'] or 기준폭 or 1
            배율 = (기준폭 or 잰폭) / 잰폭
            for k in conn.execute("SELECT * FROM auto_candidate WHERE auto_run_id=? AND status='open'"
                                  " AND issue_id IS NULL ORDER BY no", (r['id'],)):
                나온것.append(항목_후보(k, 배율))
    except sqlite3.OperationalError:
        return []           # 옛 DB(자동 검수 표 없음)
    return 나온것


def 페이지자료(conn, 화면, 쪽):
    """한 장에 들어갈 것만 모은다. 마지막 차수 기준(river 2026-09-16)."""
    차수들 = queries.runs_of_page(conn, 쪽['uuid'])
    끝차수 = 차수들[-1] if 차수들 else None
    기준폭 = (끝차수['coord_ref_w'] if 끝차수 else None) or 1920
    지적 = [항목_지적(i) for i in queries.issues_of_page(conn, 쪽['uuid'])
          if i['status'] in UNRESOLVED_STATUSES]
    if 끝차수:
        지적 += 후보항목(conn, 쪽['uuid'], 끝차수['uuid'], 기준폭)
    for n, 항 in enumerate(지적):
        항['번호'] = n + 1
    날짜 = {d['round']: d for d in queries.page_dates(conn, 쪽['uuid'])}
    d = 날짜.get(끝차수['round']) if 끝차수 else None
    return {
        '쪽': 쪽, '화면': 화면, '차수': 끝차수['round'] if 끝차수 else None,
        '검수일': (d and (d['inspected_at'] or d['uploaded_at'])) or '—',
        '지적': 지적,
        '시안': 쪽['design_img'] if 'design_img' in 쪽.keys() else None,
        '개발': 끝차수['dev_img'] if 끝차수 else None,
        'vb_w': 기준폭,
        'vb_h': (끝차수['coord_ref_h'] if 끝차수 else None) or 1080,
    }


def 지적줄(항):
    c = issue_categories.color(None)
    값 = ''.join(_줄글(줄) for 줄 in 항['줄들'])
    자리 = f'<p class="where">{_e(항["자리"])}</p>' if 항['자리'] else ''
    return (f'<li><span class="no" style="background:{c}">{항["번호"]}</span>'
            f'<div><p class="ttl">{_e(항["제목"])}</p>'
            f'<p class="meta">{_e(항["갈래"])} · {_e(항["꼬리"])}</p>{값}{자리}</div></li>')


def 표지(project, scope, 화면수, 쪽수, 지적수):
    오늘 = datetime.now().strftime('%Y-%m-%d')
    갈래 = '수정필요만 모은 중간 공유본' if scope == 'open' else '모든 페이지를 담은 최종본'
    return (f'<section class="sheet cover"><div class="brand"></div>'
            f'<h1>개발화면 검수결과서</h1>'
            f'<p class="sub">{_e(project["name"])}</p>'
            f'<dl class="facts"><dt>만든 날</dt><dd>{오늘}</dd>'
            f'<dt>담은 것</dt><dd>{갈래}</dd>'
            f'<dt>화면</dt><dd>{화면수}개 · 검수 페이지 {쪽수}장</dd>'
            f'<dt>수정필요</dt><dd>{지적수}건</dd></dl>'
            f'<p class="org">S-1 UX 디자인그룹</p></section>')


def 간지(화면, 쪽수, 지적수):
    return (f'<section class="sheet divider"><p class="key">{_e(화면["human_key"] or "")}</p>'
            f'<h2>{_e(화면["name"])}</h2>'
            f'<p class="sub">{_e(화면["platform"])} · 검수 페이지 {쪽수}장 · 수정필요 {지적수}건</p></section>')


def 한장들(자료):
    """한 장에 다 안 들어가면 같은 그림을 다시 얹고 다음 줄부터 이어 붙인다."""
    지적 = 자료['지적']
    묶음 = [지적[i:i + 한장묶음] for i in range(0, len(지적), 한장묶음)] or [[]]
    return ''.join(한장(자료, 조각, n, len(묶음)) for n, 조각 in enumerate(묶음))


def 한장(자료, 조각, 순번=0, 전체=1):
    쪽, 화면 = 자료['쪽'], 자료['화면']
    키 = 쪽.get('human_key') or 화면['human_key'] or ''
    차수 = f'{자료["차수"]}차' if 자료['차수'] else '—'
    판정 = 쪽.get('pass_fail')
    판정칸 = f'<span class="pf {판정}">{판정.upper()}</span>' if 판정 in ('pass', 'fail') else '—'
    시안 = 그림담기(자료['시안'])
    개발 = 그림담기(자료['개발'])
    왼쪽 = f'<img src="{시안}" alt="시안">' if 시안 else '<span class="ph">시안 없음</span>'
    덧 = 덧그림(자료['지적'], 자료['vb_w'], 자료['vb_h'])
    가운데 = (f'<img src="{개발}" alt="개발 화면">{덧}' if 개발
              else f'<span class="ph">개발 화면 없음</span>{덧}')
    줄 = ''.join(지적줄(항) for 항 in 조각)
    목록 = f'<ol class="issues">{줄}</ol>' if 줄 else '<p class="none">수정필요 없음</p>'
    이어 = f' <span class="cont">({순번 + 1}/{전체})</span>' if 전체 > 1 else ''
    return (f'<section class="sheet page">'
            f'<header class="head"><h3>{_e(쪽["name"])}{이어}</h3>'
            f'<p class="crumb">{_e(화면["name"])}</p>'
            f'<dl class="tags"><dt>스토리보드 ID</dt><dd>{_e(키 or "—")}</dd>'
            f'<dt>검수일</dt><dd>{_e(자료["검수일"])}</dd>'
            f'<dt>차수</dt><dd>{차수}</dd>'
            f'<dt>Pass/Fail</dt><dd>{판정칸}</dd></dl></header>'
            f'<div class="body"><figure class="shot"><figcaption>시안</figcaption><div class="frame">{왼쪽}</div></figure>'
            f'<figure class="shot"><figcaption>개발 화면</figcaption><div class="frame">{가운데}</div></figure>'
            f'<div class="list"><h4>수정필요 {len(자료["지적"])}건</h4>{목록}</div></div></section>')


def build(project_uuid, scope='open', db_path=None):
    """프로젝트 하나의 검수결과서 HTML. scope: 'open'(수정필요만) / 'all'(전부)."""
    if scope not in SCOPES:
        scope = 'open'
    conn = dbmod.connect(db_path or dbmod.DB_PATH)
    project = conn.execute('SELECT * FROM project WHERE uuid=?', (project_uuid,)).fetchone()
    if project is None:
        conn.close()
        return None
    화면들 = conn.execute('SELECT * FROM screen WHERE project_id=? ORDER BY human_key, name', (project_uuid,)).fetchall()
    묶음 = []
    for s in 화면들:
        자료들 = []
        for 쪽 in queries.pages_of_screen(conn, s['uuid']):
            행 = conn.execute('SELECT * FROM inspection_page WHERE uuid=?', (쪽['uuid'],)).fetchone()
            쪽 = dict(쪽, design_img=행['design_img'])
            자료 = 페이지자료(conn, s, 쪽)
            if scope == 'open' and not 자료['지적']:
                continue
            자료들.append(자료)
        if 자료들:
            묶음.append((s, 자료들))
    conn.close()

    쪽수 = sum(len(v) for _, v in 묶음)
    지적수 = sum(len(a['지적']) for _, v in 묶음 for a in v)
    본문 = 표지(project, scope, len(묶음), 쪽수, 지적수)
    for s, 자료들 in 묶음:
        본문 += 간지(s, len(자료들), sum(len(a['지적']) for a in 자료들))
        본문 += ''.join(한장들(a) for a in 자료들)
    if not 묶음:
        본문 += ('<section class="sheet page"><p class="none">담을 검수 페이지가 없습니다. '
                 '수정필요를 올린 뒤 다시 받으세요.</p></section>')
    제목 = f'개발화면 검수결과서 · {project["name"]}'
    return (f'<!doctype html><html lang=ko><head><meta charset=utf-8>'
            f'<meta name=viewport content="width=device-width,initial-scale=1">'
            f'<title>{_e(제목)}</title>{s1_tokens.품기()}<style>{CSS}</style></head><body>'
            f'<div class="bar"><span class="t">{_e(제목)}</span>'
            f'<button class="s1-btn s1-btn-primary" onclick="window.print()">PDF로 저장 / 인쇄</button>'
            f'<p class="hint">인쇄창에서 <b>대상 → PDF로 저장</b> 을 고르면 그대로 PDF 파일이 됩니다.</p></div>'
            f'{본문}</body></html>')


CSS = '''
body{margin:0;background:var(--color-bg-subtle);color:var(--color-text-primary);
 font-family:'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo',sans-serif}
.bar{position:sticky;top:0;z-index:5;display:flex;align-items:center;gap:var(--spacing-12);
 padding:var(--spacing-10) var(--spacing-16);background:var(--color-surface-default);
 border-bottom:var(--border-width-1) solid var(--color-border-subtle)}
.bar .t{font-weight:var(--font-weight-bold)}
.bar .hint{margin:0;font-size:var(--font-size-12);color:var(--color-text-caption)}

/* 한 장 = 가로 A4. 종이 치수(mm)는 간격 토큰과 다른 축이라 그대로 쓴다. */
.sheet{position:relative;width:297mm;height:210mm;margin:var(--spacing-20) auto;padding:12mm;
 box-sizing:border-box;overflow:hidden;background:var(--color-surface-default);
 border:var(--border-width-1) solid var(--color-border-subtle)}

.cover{display:flex;flex-direction:column;justify-content:flex-end}
.cover .brand{position:absolute;left:0;top:0;right:0;height:78mm;background:var(--color-action-primary-default)}
.cover h1{position:relative;margin:0 0 var(--spacing-8);font-size:44px;font-weight:var(--font-weight-bold);letter-spacing:-.02em}
.cover .sub{margin:0 0 var(--spacing-24);font-size:24px;color:var(--color-text-secondary)}
.cover .facts{display:grid;grid-template-columns:34mm 1fr;gap:var(--spacing-6) var(--spacing-12);
 margin:0 0 var(--spacing-24);font-size:var(--font-size-14);max-width:150mm}
.cover .facts dt{color:var(--color-text-caption)}
.cover .facts dd{margin:0}
.cover .org{margin:0;font-size:var(--font-size-14);color:var(--color-text-caption)}

.divider{display:flex;flex-direction:column;justify-content:center;
 border-left:8mm solid var(--color-action-primary-default)}
.divider .key{margin:0 0 var(--spacing-8);font-size:var(--font-size-14);color:var(--color-text-caption)}
.divider h2{margin:0 0 var(--spacing-10);font-size:38px;font-weight:var(--font-weight-bold)}
.divider .sub{margin:0;font-size:var(--font-size-16);color:var(--color-text-secondary)}

.page{display:flex;flex-direction:column;gap:var(--spacing-10)}
.head{display:grid;grid-template-columns:1fr auto;gap:var(--spacing-4) var(--spacing-16);
 padding-bottom:var(--spacing-8);border-bottom:var(--border-width-2) solid var(--color-border-emphasis)}
.head h3{margin:0;font-size:var(--font-size-20);font-weight:var(--font-weight-bold)}
.head .crumb{grid-row:2;margin:0;font-size:var(--font-size-12);color:var(--color-text-caption)}
.head .tags{grid-column:2;grid-row:1/3;display:flex;align-items:center;gap:var(--spacing-16);margin:0;font-size:var(--font-size-12)}
.head .tags dt{color:var(--color-text-caption)}
.head .tags dd{margin:0 0 0 var(--spacing-4);font-weight:var(--font-weight-bold);display:inline}
.head .tags dt,.head .tags dd{display:inline}
.pf{padding:var(--spacing-2) var(--spacing-8);border-radius:var(--radius-4);color:#fff}
.pf.pass{background:var(--color-status-success)}
.pf.fail{background:var(--color-status-critical)}

.body{flex:1;display:grid;grid-template-columns:1fr 1fr 78mm;gap:var(--spacing-12);min-height:0}
.shot{display:flex;flex-direction:column;gap:var(--spacing-4);margin:0;min-height:0}
.shot figcaption{font-size:var(--font-size-12);color:var(--color-text-caption)}
/* 틀은 그림에 딱 맞춘다 — 그래야 그 위에 얹는 핀이 그림과 같은 자 위에 놓인다.
   (틀을 남는 자리만큼 늘리면 그림은 위에, 핀은 가운데로 가 서로 어긋난다.) */
.frame{position:relative;align-self:flex-start;display:inline-flex;max-width:100%;
 background:var(--color-bg-default);border:var(--border-width-1) solid var(--color-border-subtle)}
.frame img{display:block;width:auto;max-width:100%;max-height:150mm}
.frame .ov{position:absolute;inset:0;width:100%;height:100%}
.frame .ph{padding:var(--spacing-16);font-size:var(--font-size-12);color:var(--color-text-caption)}

.list{min-height:0;overflow:hidden}
.list h4{margin:0 0 var(--spacing-8);font-size:var(--font-size-14);font-weight:var(--font-weight-bold)}
.issues{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:var(--spacing-8)}
.issues li{display:flex;gap:var(--spacing-8);padding-bottom:var(--spacing-8);
 border-bottom:var(--border-width-1) dashed var(--color-border-subtle)}
.issues .no{flex:0 0 auto;width:18px;height:18px;border-radius:50%;color:#fff;
 font-size:var(--font-size-12);line-height:18px;text-align:center}
.cont{font-size:var(--font-size-12);font-weight:var(--font-weight-regular);color:var(--color-text-caption)}
.issues .ttl{margin:0;font-size:var(--font-size-12);font-weight:var(--font-weight-bold);word-break:keep-all}
.issues .meta{margin:var(--spacing-2) 0 0;font-size:var(--font-size-11,11px);color:var(--color-text-caption)}
.issues .v{margin:var(--spacing-2) 0 0;font-size:var(--font-size-11,11px);overflow-wrap:anywhere}
.issues .v b{font-weight:var(--font-weight-bold);color:var(--color-text-caption);margin-right:var(--spacing-4)}
.issues .where{margin:var(--spacing-2) 0 0;font-size:var(--font-size-11,11px);color:var(--color-text-caption);overflow-wrap:anywhere}
.none{margin:0;font-size:var(--font-size-12);color:var(--color-text-caption)}

@media print{
 body{background:var(--color-surface-default)}
 .bar{display:none}
 .sheet{margin:0;border:0;width:auto;height:auto;min-height:0;padding:0;break-after:page}
 .sheet:last-child{break-after:auto}
}
@page{size:A4 landscape;margin:12mm}
'''
