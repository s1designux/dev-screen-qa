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
import unicodedata

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


# 표 칸 너비를 가늠하는 자 — A4 가로 한 장에서 글이 놓이는 너비(297mm - 좌우 12mm)가 한계다.
# 여기를 넘으면 인쇄에서 오른쪽이 잘린다. 12px 글씨 기준으로 어림한 값이다(정확할 필요는 없다,
# 칸끼리 몫을 나누는 데만 쓴다). 값(`코드`)은 고정폭 글꼴이라 줄글보다 넓고 테두리·안쪽여백이 더 붙는다.
_종이폭 = 1032.0
_반각, _코드폭, _코드테, _색칩폭 = 6.0, 7.2, 10.0, 15.0
_칸여백 = 18.0
_글캡, _토큰캡 = 200.0, 196.0


def _폭픽셀(글, 코드냐):
    """글 한 도막이 차지하는 너비(px) 어림 — 한글·한자는 두 배로 센다.

    색값(`#RRGGBB`)에는 그 색 동그라미가 앞에 붙으니 그 자리도 함께 센다."""
    단위 = _코드폭 if 코드냐 else _반각
    폭 = sum(단위 * 2 if unicodedata.east_asian_width(c) in "WF" else 단위 for c in 글)
    폭 += _색칩폭 * len(_색.findall(글))
    return 폭 + (_코드테 if 코드냐 and 글.strip() else 0.0)


def _토막(줄):
    """한 줄을 [(글, 코드냐)] 로 가른다 — 백틱 안팎은 글꼴이 달라 너비가 다르다."""
    return [(부분, i % 2 == 1) for i, 부분 in enumerate(줄.split("`")) if 부분]


def _칸가늠(글):
    """한 칸의 (가장 긴 줄 너비, 끊을 수 없는 가장 긴 낱말 너비). 낱말 쪽이 그 칸에 꼭 필요한 너비다."""
    전체 = 토큰 = 0.0
    for 줄 in re.split(r"<br\s*/?>", 글):
        줄폭 = 0.0
        for 부분, 코드냐 in _토막(줄.replace("*", "")):
            줄폭 += _폭픽셀(부분, 코드냐)
            for 낱말 in 부분.split():
                토큰 = max(토큰, _폭픽셀(낱말, 코드냐))
        전체 = max(전체, 줄폭)
    return 전체, 토큰


def _칸너비(머리, 몸):
    """표 칸마다 백분율 너비를 정한다.

    먼저 칸마다 **끊을 수 없는 가장 긴 낱말**(선택자·토큰 이름) 만큼을 떼어 주고,
    남는 자리를 글이 긴 칸에 나눠 준다. 긴 칸 하나가 너비를 다 먹어
    옆 칸의 짧은 값이 한 글자씩 끊기는 것을 막는다.
    """
    바람, 최소 = [], []
    for c in range(len(머리)):
        전체 = 토큰 = 0.0
        for 행 in [머리] + 몸:
            if c < len(행):
                a, b = _칸가늠(행[c])
                전체, 토큰 = max(전체, a), max(토큰, b)
        최소.append(min(토큰, _토큰캡) + _칸여백)
        바람.append(max(min(전체, _글캡), min(토큰, _토큰캡)) + _칸여백)
    더 = [b - m for b, m in zip(바람, 최소)]
    남음 = _종이폭 - sum(최소)
    폭 = 최소
    if 남음 > 0 and sum(더) > 0:
        몫 = min(1.0, 남음 / sum(더))
        폭 = [m + d * 몫 for m, d in zip(최소, 더)]
    합 = sum(폭) or 1.0
    return ["%.2f%%" % (w * 100.0 / 합) for w in 폭]


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
            cols = "".join("<col style='width:%s'>" % w for w in _칸너비(머리, 몸))
            나온것.append("<div class='tw'><table><colgroup>%s</colgroup>"
                        "<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>" % (cols, th, trs))
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
  height:var(--sizing-34);min-width:var(--sizing-64);padding:0 var(--spacing-8);
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

/* 문서 — A4 **가로** 한 장. mm 는 종이 치수라 토큰이 없다(간격 토큰과 다른 축이다).
   세로로 두면 표가 종이보다 넓어 오른쪽이 잘린다(선택자·토큰 이름은 중간에서 끊을 수 없는 글이다).
   검수결과서도 가로 A4 다(CLAUDE.md 13·16번). 글줄은 아래에서 따로 좁혀 읽기 좋게 둔다. */
.sheet{width:297mm;min-height:210mm;margin:var(--spacing-20) auto var(--spacing-40);
  background:var(--color-surface-default);
  border:var(--border-width-1) solid var(--color-border-subtle);
  padding:14mm}
h1{font-size:var(--font-size-20);font-weight:var(--font-weight-bold);
  margin:0 0 var(--spacing-6)}
h2{font-size:var(--font-size-16);font-weight:var(--font-weight-bold);
  margin:var(--spacing-24) 0 var(--spacing-10);padding-bottom:var(--spacing-6);
  border-bottom:var(--border-width-2) solid var(--color-border-emphasis)}
h3{font-size:var(--font-size-14);font-weight:var(--font-weight-bold);
  margin:var(--spacing-16) 0 var(--spacing-8)}
/* 줄글은 종이 끝까지 늘리지 않는다 — 가로 종이의 한 줄은 너무 길어 눈이 되돌아오지 못한다.
   표만 종이 너비를 다 쓴다. */
p,ul,ol,blockquote{max-width:190mm}
p{margin:0 0 var(--spacing-10)}
hr{border:0;border-top:var(--border-width-1) solid var(--color-border-subtle);
  margin:var(--spacing-20) 0}
blockquote{margin:var(--spacing-12) 0;padding:var(--spacing-10) var(--spacing-14);
  background:var(--color-bg-subtle);
  border-left:var(--spacing-4) solid var(--color-status-warning);
  color:var(--color-text-tertiary);font-size:var(--font-size-12)}
/* 값은 줄을 넘겨서라도 종이 안에 둔다 — 끊지 않으면(nowrap) 표가 A4 밖으로 나가 오른쪽이 잘린다.
   끊긴 줄에도 테두리·안쪽여백이 그대로 붙게 box-decoration-break 를 쓴다. */
code{background:var(--color-bg-subtle);
  border:var(--border-width-1) solid var(--color-border-default);
  border-radius:var(--radius-4);padding:var(--spacing-2) var(--spacing-4);
  font-family:'SFMono-Regular',Menlo,Consolas,monospace;
  font-size:var(--font-size-12);white-space:normal;overflow-wrap:anywhere;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
.sw{display:inline-block;width:var(--spacing-10);height:var(--spacing-10);
  border-radius:var(--radius-2);
  border:var(--border-width-1) solid var(--color-border-strong);
  margin-right:var(--spacing-4);vertical-align:-1px}
/* 표는 종이 너비를 넘지 않는다. 칸 너비는 글 길이를 보고 파이썬이 <colgroup> 으로 정해 주고(_칸너비),
   여기서는 그 너비를 그대로 지키게 한다(table-layout:fixed). 한글은 띄어쓰기에서 끊고(keep-all),
   띄어쓰기가 없는 긴 낱말(선택자·토큰 이름)만 어쩔 수 없이 중간에서 끊는다(anywhere). */
.tw{overflow-x:auto;margin:0 0 var(--spacing-14)}
table{border-collapse:collapse;width:100%;max-width:100%;table-layout:fixed;
  font-size:var(--font-size-12)}
th,td{border:var(--border-width-1) solid var(--color-table-border-default);
  padding:var(--spacing-6) var(--spacing-8);text-align:left;vertical-align:top;
  word-break:keep-all;overflow-wrap:anywhere}
th{background:var(--color-table-header-bg);font-weight:var(--font-weight-bold)}
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
  /* 화면에서는 밀어서 볼 수 있지만 종이에는 밀 곳이 없다 — 넘치는 만큼 그대로 잘린다.
     그래서 인쇄에서는 감추지 않고(visible) 다 보이게 둔다. */
  .tw{overflow:visible}
  h2{break-after:avoid}
  tr{break-inside:avoid}
  blockquote{break-inside:avoid}
}
@page{size:A4 landscape;margin:12mm}
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
