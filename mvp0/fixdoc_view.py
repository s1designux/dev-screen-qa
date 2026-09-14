"""수정요청서를 **읽는 화면**으로 — 내려받지 않고 그 자리에서 보고, 눌러서 PDF 로 저장한다.

디자이너는 `.md` 를 열어 볼 편집기가 없다. 그래서 같은 글을 A4 모양 한 장으로 그려 준다.
브라우저 인쇄창에서 '대상: PDF 로 저장' 을 고르면 그대로 PDF 가 된다(바깥 프로그램 없음, 폐쇄망에서도 된다).

**글을 다시 만들지 않는다.** `fixdoc.지시서묶음()` 이 내놓은 그 Markdown 을 읽어 모양만 입힌다 —
문서는 데이터를 읽어 만드는 출력물이고(CLAUDE.md 2번-1), 내려받는 `.md` 와 한 글자도 달라지면 안 된다.

여기서 다루는 markdown 은 fixdoc 이 실제로 쓰는 것만이다: 제목(#·##), 문단, 인용(>), 표(| … |),
목록(- , 1. ), 확인칸(- [ ] ), 가름줄(---), 그리고 줄 안의 **굵게** · `값` · <br>.
"""
import html
import re

import s1_tokens

_색 = re.compile(r"#[0-9A-Fa-f]{6}\b")
_코드 = re.compile(r"`([^`]+)`")
_굵게 = re.compile(r"\*\*(.+?)\*\*")


def _색칩(글):
    """`#RRGGBB` 로 적힌 색값 앞에 그 색 동그라미를 붙인다 — 숫자만으로는 무슨 색인지 안 보인다."""
    return _색.sub(lambda m: '<span class="sw" style="background:%s"></span>%s' % (m.group(0), m.group(0)), 글)


def _줄안(글):
    """한 줄 안의 꾸밈. 차례가 중요하다 — 먼저 싸매고(escape), 코드는 빼 두었다가 맨 뒤에 되돌린다."""
    글 = html.escape(글)
    곳간 = []

    def 담기(m):
        곳간.append(m.group(1))
        return "\x00%d\x00" % (len(곳간) - 1)

    글 = _코드.sub(담기, 글)
    글 = _굵게.sub(r"<strong>\1</strong>", 글)
    글 = 글.replace("&lt;br&gt;", "<br>")
    글 = _색칩(글)
    for i, 속 in enumerate(곳간):
        글 = 글.replace("\x00%d\x00" % i, "<code>%s</code>" % _색칩(속))
    return 글


def _표칸(줄):
    """`| a | b |` → ['a', 'b']"""
    속 = 줄.strip()
    if 속.startswith("|"):
        속 = 속[1:]
    if 속.endswith("|"):
        속 = 속[:-1]
    return [c.strip() for c in 속.split("|")]


def _가름줄이냐(줄):
    return bool(re.fullmatch(r"\|[\s:\-|]+\|", 줄.strip()))


def 본문(md):
    """fixdoc 의 Markdown → 읽는 HTML."""
    줄들 = md.split("\n")
    나온것 = []
    i, n = 0, len(줄들)
    문단 = []

    def 문단닫기():
        if 문단:
            나온것.append("<p>%s</p>" % "<br>".join(_줄안(x) for x in 문단))
            문단.clear()

    while i < n:
        줄 = 줄들[i]
        벗김 = 줄.strip()

        if not 벗김:
            문단닫기()
            i += 1
            continue

        if 벗김 == "---":
            문단닫기()
            나온것.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", 벗김)
        if m:
            문단닫기()
            깊이 = len(m.group(1))
            나온것.append("<h%d>%s</h%d>" % (깊이, _줄안(m.group(2)), 깊이))
            i += 1
            continue

        if 벗김.startswith(">"):
            문단닫기()
            모음 = []
            while i < n and 줄들[i].strip().startswith(">"):
                모음.append(줄들[i].strip()[1:].strip())
                i += 1
            나온것.append("<blockquote>%s</blockquote>" % "<br>".join(_줄안(x) for x in 모음))
            continue

        # 표 — 첫 줄이 머리, 둘째 줄이 가름줄일 때만 표로 본다.
        if 벗김.startswith("|") and i + 1 < n and _가름줄이냐(줄들[i + 1]):
            문단닫기()
            머리 = _표칸(줄들[i])
            i += 2
            몸 = []
            while i < n and 줄들[i].strip().startswith("|"):
                몸.append(_표칸(줄들[i]))
                i += 1
            th = "".join("<th>%s</th>" % _줄안(c) for c in 머리)
            trs = ""
            for r in 몸:
                # 칸 수가 모자라면 빈 칸으로 채운다(↳ 줄이 줄어 있는 경우가 있다).
                r = r + [""] * (len(머리) - len(r))
                trs += "<tr>%s</tr>" % "".join("<td>%s</td>" % _줄안(c) for c in r[:len(머리)])
            나온것.append("<div class='tw'><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>" % (th, trs))
            continue

        # 확인칸 목록
        if re.match(r"^- \[[ xX]\]\s", 벗김):
            문단닫기()
            모음 = []
            while i < n and re.match(r"^- \[[ xX]\]\s", 줄들[i].strip()):
                속 = 줄들[i].strip()
                켬 = 속[3].lower() == "x"
                모음.append((켬, 속[6:].strip()))
                i += 1
            lis = "".join("<li><input type=checkbox%s> %s</li>" % (" checked" if 켬 else "", _줄안(t))
                          for 켬, t in 모음)
            나온것.append("<ul class='chk'>%s</ul>" % lis)
            continue

        if 벗김.startswith("- "):
            문단닫기()
            모음 = []
            while i < n and 줄들[i].strip().startswith("- ") and not re.match(r"^- \[[ xX]\]\s", 줄들[i].strip()):
                모음.append(줄들[i].strip()[2:])
                i += 1
            나온것.append("<ul>%s</ul>" % "".join("<li>%s</li>" % _줄안(x) for x in 모음))
            continue

        if re.match(r"^\d+\.\s", 벗김):
            문단닫기()
            모음 = []
            while i < n and re.match(r"^\d+\.\s", 줄들[i].strip()):
                모음.append(re.sub(r"^\d+\.\s+", "", 줄들[i].strip()))
                i += 1
            나온것.append("<ol>%s</ol>" % "".join("<li>%s</li>" % _줄안(x) for x in 모음))
            continue

        문단.append(벗김)
        i += 1

    문단닫기()
    return "\n".join(나온것)


CSS = """
/* 값은 전부 S-1 디자인가이드 토큰(var(--…))이다. 여기에 색·크기를 직접 적지 않는다.
   토큰 네 장은 포털이 /assets/css/ 로 내보낸다(가이드받기.sh --내려두기 로 받아 둔 것). */
*{box-sizing:border-box}
body{margin:0;background:var(--color-bg-level-3);color:var(--color-text-primary);
  line-height:var(--line-height-140);
  font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;
  font-size:var(--font-size-14)}

/* 위 띠 — 문서가 아니라 화면 크롬이다. 인쇄에는 나오지 않는다. */
.bar{position:sticky;top:0;z-index:9;background:var(--color-surface-default);
  border-bottom:var(--border-width-1) solid var(--color-border-default);
  padding:var(--spacing-12) var(--spacing-20);
  display:flex;align-items:center;gap:var(--spacing-8);flex-wrap:wrap}
.bar .t{font-size:var(--font-size-16);font-weight:var(--font-weight-bold);
  color:var(--color-text-primary);margin-right:auto}
.bar .hint{width:100%;margin:var(--spacing-6) 0 0;
  font-size:var(--font-size-12);color:var(--color-text-caption)}

/* S-1 Button · Size XSM(PC) — h34 / 좌우 spacing-8 / radius-4 / body 14M */
.s1-btn{display:inline-flex;align-items:center;justify-content:center;
  height:34px;min-width:64px;padding:0 var(--spacing-8);
  border-radius:var(--radius-button-md);border:var(--border-width-1) solid transparent;
  font:inherit;font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  text-decoration:none;cursor:pointer}
.s1-btn-primary{background:var(--color-button-bg-primary--default);
  border-color:var(--color-button-border-primary--default);
  color:var(--color-button-label-primary--default)}
.s1-btn-primary:hover{background:var(--color-button-bg-primary--hover);
  border-color:var(--color-button-border-primary--hover);
  color:var(--color-button-label-primary--hover)}
.s1-btn-secondary{background:var(--color-button-bg-secondary--default);
  border-color:var(--color-button-border-secondary--default);
  color:var(--color-button-label-secondary--default)}
.s1-btn-secondary:hover{background:var(--color-button-bg-secondary--hover);
  border-color:var(--color-button-border-secondary--hover);
  color:var(--color-button-label-secondary--hover)}

/* 문서 — A4 한 장. mm 는 종이 치수라 토큰이 없다(간격 토큰과 다른 축이다). */
.sheet{width:210mm;min-height:297mm;margin:var(--spacing-20) auto var(--spacing-40);
  background:var(--color-surface-default);
  border:var(--border-width-1) solid var(--color-border-subtle);
  padding:16mm 14mm}
h1{font-size:var(--font-size-20);font-weight:var(--font-weight-bold);
  margin:0 0 var(--spacing-6)}
h2{font-size:var(--font-size-16);font-weight:var(--font-weight-bold);
  margin:var(--spacing-24) 0 var(--spacing-10);padding-bottom:var(--spacing-6);
  border-bottom:var(--border-width-2) solid var(--color-border-emphasis)}
h3{font-size:var(--font-size-14);font-weight:var(--font-weight-bold);
  margin:var(--spacing-16) 0 var(--spacing-8)}
p{margin:0 0 var(--spacing-10)}
hr{border:0;border-top:var(--border-width-1) solid var(--color-border-subtle);
  margin:var(--spacing-20) 0}
blockquote{margin:var(--spacing-12) 0;padding:var(--spacing-10) var(--spacing-14);
  background:var(--color-bg-subtle);
  border-left:var(--spacing-4) solid var(--color-status-warning);
  color:var(--color-text-tertiary);font-size:var(--font-size-12)}
code{background:var(--color-bg-subtle);
  border:var(--border-width-1) solid var(--color-border-default);
  border-radius:var(--radius-4);padding:var(--spacing-2) var(--spacing-4);
  font-family:'SFMono-Regular',Menlo,Consolas,monospace;
  font-size:var(--font-size-12);white-space:nowrap}
.sw{display:inline-block;width:var(--spacing-10);height:var(--spacing-10);
  border-radius:var(--radius-2);
  border:var(--border-width-1) solid var(--color-border-strong);
  margin-right:var(--spacing-4);vertical-align:-1px}
.tw{overflow-x:auto;margin:0 0 var(--spacing-14)}
table{border-collapse:collapse;width:100%;font-size:var(--font-size-12)}
th,td{border:var(--border-width-1) solid var(--color-table-border-default);
  padding:var(--spacing-6) var(--spacing-8);text-align:left;vertical-align:top}
th{background:var(--color-table-header-bg);font-weight:var(--font-weight-bold);white-space:nowrap}
tbody tr:nth-child(even){background:var(--color-bg-default)}
ul,ol{margin:0 0 var(--spacing-12);padding-left:var(--spacing-20)}
li{margin:var(--spacing-2) 0}
ul.chk{list-style:none;padding-left:var(--spacing-2)}
ul.chk li{padding:var(--spacing-4) 0;
  border-bottom:var(--border-width-1) dashed var(--color-border-subtle)}
ul.chk input{margin-right:var(--spacing-6);vertical-align:-1px}

@media screen and (max-width:860px){
  .sheet{width:auto;min-height:0;margin:var(--spacing-12);padding:var(--spacing-16)}
}
@media print{
  body{background:var(--color-surface-default)}
  .bar{display:none}
  .sheet{width:auto;min-height:0;margin:0;padding:0;border:0}
  h2{break-after:avoid}
  tr{break-inside:avoid}
  blockquote{break-inside:avoid}
}
@page{size:A4;margin:14mm}
"""


def 한장(md, 제목, md주소):
    """읽는 화면 한 장. 위 띠에 'PDF 로 저장' 과 '.md 내려받기'."""
    토큰 = s1_tokens.링크()
    return ("<!doctype html><html lang=ko><head><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s</title>%s<style>%s</style></head><body>"
            "<div class=bar><span class=t>%s</span>"
            "<button class='s1-btn s1-btn-primary' onclick='window.print()'>PDF로 저장 / 인쇄</button>"
            "<a class='s1-btn s1-btn-secondary' href='%s' download>.md 내려받기</a>"
            "<p class=hint>인쇄창에서 <b>대상 → PDF로 저장</b> 을 고르면 그대로 PDF 파일이 됩니다.</p></div>"
            "<div class=sheet>%s</div></body></html>"
            % (html.escape(제목), 토큰, CSS, html.escape(제목), html.escape(md주소), 본문(md)))
