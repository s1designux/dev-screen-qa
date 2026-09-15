#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사례.json 한 벌을 읽어 '시안 작성 가이드' 한 장(HTML)을 뽑는다.

데이터가 원본이고 이 HTML 은 그 데이터를 보여 주는 출력물일 뿐이다(CLAUDE.md 2번-1).
사례는 화면 이름이 아니라 **화면 유형**으로 모은다 — 같은 유형이면 같은 흐름이 먹기 때문이다.

    python3 docs/시안작성가이드/만들기.py
"""
import html
import json
from pathlib import Path

여기 = Path(__file__).resolve().parent
자료 = json.loads((여기 / "사례.json").read_text(encoding="utf-8"))
나갈곳 = 여기.parent / "시안작성가이드.html"


def E(s):
    return html.escape(str(s or ""))


# ── 미리보기 그림 — 화면 종류 이름 하나로 작은 그림을 그린다 ──────────────
칸 = '<div class="fld">{}</div>'
행 = '<div class="row">{}</div>'
셀 = '<div class="cell"></div>'
머리 = '<div class="cell h"></div>'
표머리 = 행.format(머리 * 3)
표본문 = (행.format(셀 * 3)) * 3
검색줄 = 행.format(셀 + 셀 + '<div class="btn sm">조회</div>')
카드 = '<div class="card"><i></i><b></b></div>'

그림표 = {
    "폼": lambda: 칸.format("아이디를 입력해 주세요.") + 칸.format("비밀번호를 입력해 주세요.") + '<div class="btn off">로그인</div>',
    "폼커서": lambda: 칸.format("아이디를 입력해 주세요.") + '<div class="fld on">|</div><div class="btn off">로그인</div>',
    "폼채움": lambda: 칸.format("test01") + 칸.format("●●●●●●") + '<div class="btn">로그인</div>',
    "폼버튼": lambda: 칸.format("test01") + 칸.format("●●●●●●") + '<div class="btn">로그인</div>',
    "폼오류": lambda: 칸.format("test01") + 칸.format("●●●●●●") + '<div class="fld bad">아이디 또는 비밀번호를 확인해 주세요.</div>',
    "조회전": lambda: '<div class="bar"></div>' + 검색줄 + '<div class="empty">조회하세요</div>',
    "달력": lambda: ('<div class="bar"></div>' + 검색줄 + '<div class="empty">&nbsp;</div>'
                   + '<div class="cal">' + '<i></i>' * 15 + '</div>'),
    "표": lambda: '<div class="bar"></div>' + 표머리 + 표본문,
    "표쪽": lambda: ('<div class="bar"></div>' + 표머리 + 표본문
                   + '<div class="pg"><i></i><i class="on"></i><i></i></div>'),
    "빈목록": lambda: '<div class="bar"></div>' + 표머리 + '<div class="empty">조회된 내역이 없습니다</div>',
    "표팝업": lambda: ('<div class="bar"></div>' + 표머리 + 행.format(셀 * 3)
                    + '<div class="pop"><div class="bar"></div><div class="bar"></div>'
                    + 행.format(셀 + '<div class="btn sm">저장</div>') + '</div>'),
    "확인팝업": lambda: ('<div class="bar"></div>' + 표머리
                     + '<div class="pop tall"><div class="empty">확인하시겠습니까?</div>'
                     + 행.format(셀 + '<div class="btn sm">확인</div>') + '</div>'),
    "상세": lambda: ('<div class="bar"></div>' + '<div class="bar w60"></div>'
                   + 행.format(셀 + 셀) + 행.format(셀 + 셀) + '<div class="bar w40"></div>'),
    "상세탭": lambda: ('<div class="tabs"><i></i><i class="on"></i><i></i></div>'
                    + 행.format(셀 + 셀) + 행.format(셀 + 셀) + '<div class="bar w40"></div>'),
    "상세펼침": lambda: ('<div class="bar"></div>' + '<div class="bar w60"></div>'
                     + '<div class="open">' + 행.format(셀 + 셀) + 행.format(셀 + 셀) + '</div>'),
    "상세아래": lambda: (행.format(셀 + 셀) + '<div class="bar w40"></div>'
                     + '<div class="empty">&nbsp;</div><div class="btn">확인</div>'),
    "이미지": lambda: '<div class="img"><span>◩</span></div>',
    "이미지로딩": lambda: '<div class="img load"><span>불러오는 중</span></div>',
    "이미지없음": lambda: '<div class="img none"><span>이미지 없음</span></div>',
    "이미지확대": lambda: '<div class="img full"><span>◩</span></div>',
    "대시보드": lambda: '<div class="bar"></div><div class="cards">' + 카드 * 4 + '</div>',
    "대시보드빈": lambda: '<div class="bar"></div><div class="empty">표시할 자료가 없습니다</div>',
    "스플래시": lambda: '<div class="splash"><span>◉</span></div>',
    "오류": lambda: '<div class="empty bad">연결할 수 없습니다<br>다시 시도해 주세요</div>',
}


def 그림(종류):
    만들기 = 그림표.get(종류)
    속 = 만들기() if 만들기 else '<div class="empty">&nbsp;</div>'
    return '<div class="scr">' + 속 + '</div>'


만드는색 = {"그냥 있음": "m0", "한 번 누름": "m1", "값 넣음": "m1", "안 되는 값": "m2",
          "데이터에 달림": "m2", "시간에 달림": "m3", "기기가 띄움": "m4", "되돌릴 수 없음": "m2"}


def 걸음카드(s, 차례, 첫장):
    메모 = f'<div class="memo">{E(s["무엇"])}</div>' if s.get("무엇") else ""
    법 = E(s.get("만드는법"))
    법표 = f'<div class="made {만드는색.get(법, "m0")}">{법}</div>' if 법 else ""
    return f"""<div class="fr {'root' if 첫장 else ''}">
      <div class="head"><span class="seq">{차례}</span><span class="role">{E(s['걸음'])}</span></div>
      <div class="nm">{E(s.get('이름예'))}</div>
      {그림(s.get('그림'))}
      {법표}
      <div class="act"><b>동작</b> {E(s.get('동작') or '-')}</div>
      {메모}
    </div>"""


def 유형블록(t, n):
    걸음 = "\n".join(걸음카드(s, i + 1, i == 0) for i, s in enumerate(t.get("표준흐름", [])))
    조심 = "".join(f"<li>{E(x)}</li>" for x in t.get("조심할것", []))

    그린것 = t.get("그린것", [])
    if 그린것:
        줄 = ""
        for g in 그린것:
            검 = E(g.get("검증"))
            색 = "ok" if "실제로" in 검 else "warn"
            줄 += (f"<tr><td class='k'>{E(g['화면'])}</td><td>{E(g['서비스'])}</td>"
                   f"<td class='dim'>{E(g['언제'])}</td><td><span class='tag {색}'>{검}</span></td>"
                   f"<td class='dim'>{E(g.get('메모'))}</td></tr>")
        그린표 = ("<table class='exp'><tr><th>화면</th><th>서비스</th><th>언제</th>"
                f"<th>믿을 만한가</th><th>메모</th></tr>{줄}</table>")
    else:
        그린표 = "<p class='none'>아직 이 유형으로 그린 시안이 들어오지 않았다. 표준 흐름은 예상으로 적은 것이다.</p>"

    겪은 = t.get("겪은일", [])
    if 겪은:
        줄 = "".join(
            f"<tr><td class='k'>{E(g['날짜'])}</td><td>{E(g['무슨일'])}</td><td>{E(g['그래서'])}</td></tr>"
            for g in 겪은)
        겪은표 = f"<table class='exp'><tr><th>언제</th><th>무슨 일</th><th>그래서</th></tr>{줄}</table>"
    else:
        겪은표 = "<p class='none'>아직 없다.</p>"

    굳 = E(t.get("굳기"))
    굳색 = {"굳음": "ok", "반쯤": "warn", "예상": "bad"}.get(굳, "warn")
    return f"""<h2><span class="n">{n}.</span> {E(t['이름'])}
      <span class="alias">{E(t.get('별명'))}</span>
      <span class="tag {굳색}">{굳}</span></h2>
    <p class="note">{E(t.get('알아보는법'))}</p>
    <p class="none">{E(t.get('굳기근거'))}</p>
    <p class="hand"><b>손 가는 순서</b> {E(t.get('손가는순서'))}</p>
    <div class="canvas">{걸음}</div>
    <h4>조심할 것</h4>
    <ul>{조심}</ul>
    <h4>이 유형으로 실제로 그린 것</h4>
    {그린표}
    <h4>겪은 일</h4>
    {겪은표}"""


흐름 = 자료["흐름원칙"]
흐름걸음 = "".join(
    f"""<div class="rule"><div class="num">{i+1}</div><div>
      <b>{E(r['제목'])}</b><span>{E(r['설명'])}</span></div></div>"""
    for i, r in enumerate(흐름["걸음"]))

규칙 = "".join(
    f"""<div class="rule"><div class="num">{i+1}</div><div>
      <b>{E(r['제목'])}</b><span>{E(r['설명'])}</span>
      <span class="std">{E(r['잣대'])}</span></div></div>"""
    for i, r in enumerate(자료["공통규칙"]))

토막 = "".join(
    f"<tr><td class='k'>{E(t['자리'])}</td><td>{E(t['무엇'])}</td><td><code>{E(t['예'])}</code></td><td class='dim'>{E(t['비고'])}</td></tr>"
    for t in 자료["이름토막"])

낱말 = "".join(
    f"<tr><td class='k'>{E(w['말'])}</td><td>{E(w['짓는동작'])}</td></tr>"
    for w in 자료["상태낱말"])

유형들 = "\n".join(유형블록(t, i + 5) for i, t in enumerate(자료["유형"]))
굳색표 = {"굳음": "ok", "반쯤": "warn", "예상": "bad"}
유형줄 = "".join(
    f"<div><b>{E(t['이름'])}</b><span>{E(t.get('별명'))}</span>"
    f"<span class='tag {굳색표.get(t.get('굳기'), 'warn')}'>{E(t.get('굳기'))}</span></div>"
    for t in 자료["유형"])

축 = 자료.get("나누는축", {})
찍기색 = {"쉬움": "ok", "보통": "warn", "어려움": "bad", "못 찍을 수 있음": "bad"}
축표 = "".join(
    f"<tr><td class='k'>{E(c['축'])}</td><td>{E(c['나누면'])}</td>"
    f"<td class='ok2'>{E(c['좋은점'])}</td><td class='bad2'>{E(c['아쉬운점'])}</td>"
    f"<td><span class='tag {'ok' if '쓰고' in c['지금'] else ''}'>{E(c['지금'])}</span></td></tr>"
    for c in 축.get("후보", []))
갈아 = "".join(f"<li>{E(x)}</li>" for x in 축.get("갈아탈때", []))

법표줄 = "".join(
    f"<tr><td class='k'><span class='made {만드는색.get(m['이름'], 'm0')}'>{E(m['이름'])}</span></td>"
    f"<td>{E(m['뜻'])}</td><td><span class='tag {찍기색.get(m['찍기'], '')}'>{E(m['찍기'])}</span></td>"
    f"<td class='dim'>{E(m['촬영기'])}</td></tr>"
    for m in 자료.get("만드는법", []))

알 = 자료.get("유형알아가는법", {})
알걸음 = "".join(
    f"""<div class="rule"><div class="num">{i+1}</div><div>
      <b>{E(r['제목'])}</b><span>{E(r['설명'])}</span></div></div>"""
    for i, r in enumerate(알.get("걸음", [])))

후보 = "".join(
    f"<tr><td class='k'>{E(c['모양'])}</td><td>{E(c['본곳'])}</td>"
    f"<td class='dim'>{E(c['횟수'])}번</td><td>{E(c['왜후보'])}</td></tr>"
    for c in 자료.get("유형후보", []))

자취 = "".join(
    f"<tr><td class='k'>{E(c['날짜'])}</td><td>{E(c['무엇'])}</td><td>{E(c['왜'])}</td></tr>"
    for c in 자료.get("유형자취", []))
미정 = "".join(f"<li>{E(x)}</li>" for x in 자료.get("아직못정한것", []))

HTML = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(자료['제목'])} — {E(자료['갱신일'])}</title>
<style>
  :root{{--ink:#1E293B;--dim:#64748B;--line:#E2E8F0;--bg:#F8FAFC;--ok:#0F766E;--warn:#B45309;--bad:#B91C1C;--blue:#1D6CEB}}
  *{{box-sizing:border-box}}
  body{{margin:0;padding:32px 24px 80px;font:15px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Pretendard",sans-serif;color:var(--ink);background:#fff}}
  .wrap{{max-width:1120px;margin:0 auto}}
  h1{{font-size:26px;margin:0 0 6px}}
  .sub{{color:var(--dim);margin:0 0 24px;font-size:14px}}
  h2{{font-size:19px;margin:46px 0 6px;padding-top:18px;border-top:2px solid var(--ink)}}
  h2 .n{{color:var(--blue)}}
  h2 .alias{{font-size:13px;color:var(--dim);font-weight:400;margin-left:8px}}
  h2 .tag{{margin-left:6px;vertical-align:middle}}
  h3{{font-size:16px;margin:32px 0 8px}}
  h4{{font-size:14px;margin:24px 0 6px;color:var(--dim)}}
  .lead{{margin:0 0 8px;color:var(--dim);font-size:14px}}
  .note{{font-size:14px;margin:0 0 6px}}
  .hand{{font-size:13.5px;color:var(--blue);background:#F2F7FF;border-radius:6px;padding:8px 12px;margin:0 0 4px;display:inline-block}}
  .hand b{{color:var(--dim);font-weight:600;margin-right:6px}}
  .dim{{color:var(--dim)}}
  .callout{{border:1px solid var(--line);border-left:5px solid var(--blue);background:var(--bg);padding:14px 16px;border-radius:6px;margin:0 0 28px;font-size:14px}}
  .rule{{display:flex;gap:11px;align-items:flex-start;margin:0 0 14px}}
  .num{{flex:none;width:23px;height:23px;border-radius:50%;background:var(--ink);color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center;font-weight:700;margin-top:3px}}
  .rule b{{display:block;font-size:15px}}
  .rule span{{display:block;color:var(--dim);font-size:13.5px}}
  .rule .std{{color:var(--warn);font-size:13px;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;margin:0 0 10px;font-size:14px}}
  th,td{{text-align:left;vertical-align:top;padding:9px 10px;border-bottom:1px solid var(--line)}}
  th{{background:var(--bg);font-weight:700;white-space:nowrap;border-bottom:2px solid var(--line)}}
  td.k{{white-space:nowrap;font-weight:600}}
  table.exp td{{font-size:13.5px}}
  ul{{padding-left:20px;margin:6px 0 4px}}
  li{{margin:4px 0;font-size:14px}}
  code{{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:13px}}
  .tag{{display:inline-block;font-size:12px;padding:1px 9px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--dim);white-space:nowrap}}
  .tag.ok{{border-color:var(--ok);color:var(--ok)}}
  .tag.warn{{border-color:var(--warn);color:var(--warn)}}
  .tag.bad{{border-color:var(--bad);color:var(--bad)}}
  .none{{color:var(--dim);font-size:13px;margin:2px 0 6px}}
  td.ok2{{color:var(--ok);font-size:13px}}
  td.bad2{{color:var(--warn);font-size:13px}}
  .made{{display:inline-block;font-size:10px;padding:1px 7px;border-radius:999px;margin:6px 0 0;white-space:nowrap}}
  .made.m0{{background:#EEF1F5;color:#5A6472}}
  .made.m1{{background:#E7F0FF;color:#1D4FA8}}
  .made.m2{{background:#FFF3E0;color:#9A5B00}}
  .made.m3{{background:#FDE8E8;color:#A32020}}
  .made.m4{{background:#2B3038;color:#fff}}
  td .made{{margin:0}}
  .types{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 28px}}
  .types div{{flex:1 1 150px;border:1px solid var(--line);border-radius:8px;padding:10px 13px;background:var(--bg)}}
  .types b{{display:block;font-size:14px}}
  .types span{{font-size:12.5px;color:var(--dim);display:block}}
  .types .tag{{margin-top:5px;display:inline-block}}

  .canvas{{display:flex;gap:10px;flex-wrap:wrap;background:#EEF1F5;border-radius:10px;padding:14px;margin:10px 0 4px}}
  .fr{{width:178px;background:#fff;border:1px solid #C3C9D1;border-radius:7px;padding:9px}}
  .fr.root{{border-color:var(--blue);box-shadow:0 0 0 2px rgba(29,108,235,.12)}}
  .fr .head{{display:flex;justify-content:space-between;align-items:center;gap:4px;margin-bottom:4px}}
  .fr .seq{{font-size:11px;color:var(--dim)}}
  .fr .role{{font-size:10px;padding:0 7px;border-radius:999px;background:#EEF1F5;color:var(--dim);white-space:nowrap}}
  .fr.root .role{{background:var(--blue);color:#fff}}
  .fr .nm{{font-size:11px;color:var(--blue);line-height:1.45;min-height:32px;word-break:keep-all;margin-bottom:6px}}
  .fr .act{{font-size:10.5px;margin-top:6px;line-height:1.5;word-break:keep-all}}
  .fr .act b{{color:var(--dim);font-weight:600}}
  .fr .memo{{font-size:10.5px;color:var(--dim);margin-top:4px;line-height:1.5;word-break:keep-all}}

  .scr{{height:104px;border:1px solid #E3E6EA;border-radius:5px;padding:7px;display:flex;flex-direction:column;gap:4px;position:relative;overflow:hidden;background:#fff}}
  .fld{{border:1px solid #CFD4DA;border-radius:3px;min-height:17px;font-size:8.5px;color:#9AA1A9;padding:2px 4px;display:flex;align-items:center}}
  .fld.on{{border-color:var(--blue);color:var(--blue)}}
  .fld.bad{{border-color:var(--bad);color:var(--bad)}}
  .btn{{background:var(--blue);color:#fff;border-radius:3px;min-height:17px;font-size:8.5px;display:flex;align-items:center;justify-content:center;flex:none}}
  .btn.off{{background:#C9CED5}}
  .btn.sm{{flex:none;width:34px}}
  .bar{{height:9px;background:#E8EBEF;border-radius:2px;flex:none}}
  .bar.w60{{width:60%}} .bar.w40{{width:40%}}
  .row{{display:flex;gap:3px;flex:none}}
  .cell{{flex:1;height:8px;background:#DFE3E8;border-radius:1px}}
  .cell.h{{background:#9AA1A9}}
  .empty{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:8.5px;color:#9AA1A9;text-align:center}}
  .empty.bad{{color:var(--bad)}}
  .pop{{position:absolute;left:16px;right:16px;top:28px;bottom:18px;background:#fff;border:1px solid #8B93A0;border-radius:4px;box-shadow:0 3px 10px rgba(0,0,0,.18);padding:7px;display:flex;flex-direction:column;gap:4px}}
  .pop.tall{{top:36px;bottom:30px}}
  .cal{{position:absolute;left:36px;top:26px;width:74px;height:58px;background:#fff;border:1px solid #8B93A0;border-radius:3px;display:grid;grid-template-columns:repeat(5,1fr);gap:2px;padding:4px}}
  .cal i{{background:#E8EBEF;border-radius:1px}}
  .pg{{display:flex;gap:3px;justify-content:center;margin-top:auto}}
  .pg i{{width:7px;height:7px;border-radius:1px;background:#DFE3E8}}
  .pg i.on{{background:var(--blue)}}
  .tabs{{display:flex;gap:4px;flex:none;border-bottom:1px solid #E3E6EA;padding-bottom:4px}}
  .tabs i{{flex:1;height:8px;background:#E8EBEF;border-radius:2px}}
  .tabs i.on{{background:var(--blue)}}
  .open{{border:1px dashed #B9C0C9;border-radius:3px;padding:4px;display:flex;flex-direction:column;gap:3px}}
  .img{{flex:1;background:#E8EBEF;border-radius:3px;display:flex;align-items:center;justify-content:center;color:#9AA1A9;font-size:16px}}
  .img span{{font-size:9px}} .img span:only-child{{font-size:18px}}
  .img.load{{background:repeating-linear-gradient(115deg,#E8EBEF,#E8EBEF 8px,#F2F4F7 8px,#F2F4F7 16px)}}
  .img.none{{background:#F7F8FA;border:1px dashed #C9CED5;color:var(--bad)}}
  .img.full{{margin:-7px;border-radius:0;background:#2B3038;color:#fff}}
  .cards{{flex:1;display:grid;grid-template-columns:1fr 1fr;gap:4px}}
  .card{{background:#F2F4F7;border-radius:3px;padding:4px;display:flex;flex-direction:column;gap:3px;justify-content:center}}
  .card i{{height:5px;width:60%;background:#C9CED5;border-radius:1px}}
  .card b{{height:9px;width:40%;background:var(--blue);opacity:.55;border-radius:1px}}
  .splash{{flex:1;background:var(--blue);border-radius:3px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px;margin:-7px}}
</style>
</head>
<body>
<div class="wrap">

<h1>{E(자료['제목'])}</h1>
<p class="sub">{E(자료['한줄'])} · {E(자료['갱신일'])} 기준</p>

<div class="callout">
  <b>화면 이름이 아니라 화면 '유형'으로 모읍니다.</b> 화면 이름은 서비스마다 다르지만 유형은 어디서나 같습니다.
  같은 유형이면 같은 흐름이 먹으므로, 새 화면을 그릴 때 그 유형의 표준 흐름만 따라가면 됩니다.
  <br><b>다만 아래 유형이 정답은 아닙니다.</b> {E(자료['쌓는법'])}
  이름표로 얼마나 믿을 만한지 적어 두었습니다 —
  <span class="tag ok">굳음</span> 실제로 찍어 봤다 ·
  <span class="tag warn">반쯤</span> 일부만 봤다 ·
  <span class="tag bad">예상</span> 아직 안 봤다.
  <br><span class="dim">원본은 <code>docs/시안작성가이드/사례.json</code> · 이 장은 그 자료를 보여 주는 출력물입니다.</span>
</div>

<div class="types">{유형줄}</div>

<h2><span class="n">1.</span> 무엇을 기준으로 나눌 것인가</h2>
<p class="note"><b>{E(축.get('한줄'))}</b></p>
<table><tr><th>축</th><th>나누면</th><th>좋은 점</th><th>아쉬운 점</th><th>지금</th></tr>{축표}</table>
<p class="note"><b>고른 것</b> — {E(축.get('고른것'))}</p>
<h4>이럴 때 축을 다시 본다</h4>
<ul>{갈아}</ul>

<h3>둘째 축 — 상태를 만드는 법</h3>
<p class="note dim">아래 이름표는 유형과 상관없이 걸음마다 붙습니다. 뒤쪽 유형 그림의 걸음 카드에도 같은 색으로 보입니다.</p>
<table><tr><th>이름표</th><th>뜻</th><th>찍기</th><th>촬영기는 어떻게 하나</th></tr>{법표줄}</table>

<h2><span class="n">2.</span> 유형은 이렇게 굳어진다</h2>
<p class="note"><b>{E(알.get('한줄'))}</b></p>
{알걸음}
<p class="hand"><b>문턱</b> {E(알.get('문턱'))}</p>

<h3>유형 후보 — 아직 올리지 않은 것</h3>
<table><tr><th>모양</th><th>본 곳</th><th>몇 번</th><th>왜 후보인가</th></tr>{후보}</table>

<h3>유형이 바뀐 자취</h3>
<table class="exp"><tr><th>언제</th><th>무엇</th><th>왜</th></tr>{자취}</table>

<h2><span class="n">3.</span> 흐름 짜는 법 — 어느 유형에나 먼저</h2>
<p class="note"><b>{E(흐름['한줄'])}</b></p>
{흐름걸음}

<h2><span class="n">4.</span> 어느 화면에나 해당하는 것</h2>
{규칙}

<h3>이름 적는 법</h3>
<table><tr><th>토막</th><th>무엇</th><th>예</th><th>비고</th></tr>{토막}</table>

<h3>뒤 토막에 쓰는 말 — 이 말들이 동작을 정한다</h3>
<p class="note dim">아래 말을 쓰면 동작 칸이 저절로 채워집니다. 다른 말을 쓰면 비워 두고 빨갛게 표시되어 사람이 적습니다.</p>
<table><tr><th>이름에 이 말이 있으면</th><th>촬영기가 짓는 동작</th></tr>{낱말}</table>

{유형들}

<h2><span class="n">{len(자료['유형'])+5}.</span> 아직 못 정한 것</h2>
<p class="lead">사례가 더 들어오면 여기서 규칙으로 올라갑니다.</p>
<ul>{미정}</ul>

</div>
</body>
</html>
"""

나갈곳.write_text(HTML, encoding="utf-8")
print(f"만들었습니다 → {나갈곳}")
