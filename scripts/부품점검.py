#!/usr/bin/env python3
"""부품 점검 — 화면이 **정본 부품을 그대로 쓰는지** 되짚는다.

토큰 점검(`s1-design` 스킬)은 "이 색·크기가 토큰인가"만 본다. 그래서 값은 다 맞는데
단추·입력칸·고르개를 화면마다 손으로 짜 넣은 것은 걸러지지 않는다. 이 점검기가 그 한 층을 본다.

기준값을 이 파일에 적어 두지 않는다 — 받아 둔 정본
(`~/.claude/s1-design-guide/ui-library/dist`)의 부품 명세·CSS·보기 마크업을 **그때그때 읽는다**.
정본이 바뀌면 판정도 따라 바뀐다.

보는 것 일곱:
  1  정본 부품 CSS 를 안 입은 화면        (손으로 옮겨 적은 사본을 쓰는 곳)
  2  표시 없는 부품                      (정본에 같은 부품이 있는데 손으로 짠 자리)
  3  정본에 없는 크기·변형 이름          (data-size="sm" 처럼 정본이 안 받는 값)
  4  뼈대(part) 어긋남                   (겉만 부르고 속 뼈대를 빠뜨린 자리)
  5  부품 생김새를 화면에서 덮어씀        (가이드 §9-7)
  6  직접 그린 아이콘                    (정본 아이콘 목록 밖)
  7  받아 둔 정본이 낡음                 (판 · 토큰 네 장)

여기서 나오는 것은 **고칠 후보**다. 자동으로 고치지 않는다.

    python3 scripts/부품점검.py [파일·폴더...] [--정본 <폴더>] [--조용히]

아무것도 안 주면 `mvp0/` 을 본다.

제외 표시: 화면 부품이 아닌 자리(핀을 얹는 그림판 SVG · 받아 둔 정본 사본)는
그 줄이나 구역에 `s1-제외` 를 적어 둔다 — 토큰 점검기와 같은 표시다.

정본에 그 부품이 **없어서** 우리가 그린 자리는 그 자리 위·같은 줄에 `DESIGN_SYSTEM_GAP` 을 적는다
(가이드 §9-9 가 시키는 그대로). 점검기는 그것을 위반이 아니라 **적어 둔 빈자리**로 따로 센다 —
숨기는 것이 아니라 세어서 보인다. 가이드에 그 부품이 생기면 그때 갈아입힌다.
"""
import json
import os
import re
import sys

기본정본 = os.environ.get("S1_GUIDE_DIR", os.path.expanduser("~/.claude/s1-design-guide"))
볼확장자 = {".py", ".html", ".htm", ".js"}
건너뛸폴더 = {".git", "node_modules", "__pycache__", "s1", "legacy", "assets"}
건너뛸파일 = {"s1.py",              # 정본 뼈대를 **짓는** 곳 — 여기가 기준이다
          "s1_components.py",   # 옛 사본(부르는 곳 없음, 이력으로만 둔다)
          "report.html", "export.json"}   # 만들어져 나온 것(.gitignore)

빈자리 = re.compile(r"DESIGN_SYSTEM_GAP")
제외시작 = re.compile(r"s1-제외\s*시작")
제외끝 = re.compile(r"s1-제외\s*끝")
제외한줄 = re.compile(r"s1-제외")


# ── 정본 읽기 ────────────────────────────────────────────────────────────────

def 정본읽기(자리):
    dist = os.path.join(자리, "ui-library", "dist")
    if not os.path.isdir(dist):
        sys.exit("정본 부품을 찾지 못했습니다 — %s (먼저 가이드받기.sh 를 돌리세요)" % dist)

    본 = {"판": "", "부품": {}, "아이콘": set(), "태그부품": {}, "태그자리": {}}
    try:
        m = json.load(open(os.path.join(dist, "manifest.json"), encoding="utf-8"))
        본["판"] = "%s %s" % (m.get("version", "?"), m.get("releasedAt", ""))
    except Exception:
        pass

    # 부품마다: 쓸 수 있는 크기·변형·뼈대 이름
    마니 = os.path.join(dist, "components")
    for 이름 in sorted(os.listdir(마니)) if os.path.isdir(마니) else []:
        if not 이름.endswith(".manifest.json"):
            continue
        d = json.load(open(os.path.join(마니, 이름), encoding="utf-8"))
        본["부품"][d["id"]] = {
            "크기": set(d.get("sizes") or []),
            "변형": set(d.get("variants") or []),
            "나눔": set(d.get("breaks") or {}),
            "뼈대": {p.split()[0] for p in (d.get("parts") or [])},
            "동작필요": bool(d.get("jsRequired")),
        }

    # 어느 속성에 그 값을 적는지는 정본 CSS 가 쓰는 대로 따른다(부품마다 다르다).
    css자리 = os.path.join(dist, "s1-ui.css")
    css = open(css자리, encoding="utf-8", errors="replace").read() if os.path.exists(css자리) else ""
    본["정본CSS"] = css
    쓰는속성 = re.compile(r'\[data-s1-component="([a-z-]+)"\](?:\[[^\]]*\])*?\[data-(size|variant|type|mode|state)="([a-z0-9-]+)"\]')
    for 부품, 속성, 값 in 쓰는속성.findall(css):
        본["부품"].setdefault(부품, {"크기": set(), "변형": set(), "나눔": set(), "뼈대": set(), "동작필요": False})
        본["부품"][부품].setdefault("속성", {}).setdefault(속성, set()).add(값)

    # 정본 보기 마크업에서 "이 태그는 어느 부품의 어느 뼈대인가"를 배운다.
    보기 = os.path.join(dist, "examples")
    태그부품, 태그자리 = {}, {}
    for 이름 in sorted(os.listdir(보기)) if os.path.isdir(보기) else []:
        if not 이름.endswith(".html"):
            continue
        글 = open(os.path.join(보기, 이름), encoding="utf-8", errors="replace").read()
        지금 = None
        for m in re.finditer(r"<([a-z]+)\b([^>]*)>", 글):
            태그, 속 = m.group(1), m.group(2)
            부품 = re.search(r'data-s1-component="([a-z-]+)"', 속)
            if 부품:
                지금 = 부품.group(1)
            뼈 = re.search(r'data-s1-part="([a-z-]+)"', 속)
            if 지금 and 태그 in ("input", "textarea", "select", "button", "table", "dialog"):
                태그부품.setdefault(태그, set()).add(지금)
                if 뼈:
                    태그자리.setdefault((지금, 태그), set()).add(뼈.group(1))
    본["태그부품"], 본["태그자리"] = 태그부품, 태그자리

    # 쓸 수 있는 아이콘
    낱 = os.path.join(자리, "registry", "components", "component-facts.json")
    if os.path.exists(낱):
        본["아이콘"] = set(json.load(open(낱, encoding="utf-8"))
                        .get("iconLibrary", {}).get("allowed", []))
    본["아이콘파일"] = {f[:-4] for f in os.listdir(os.path.join(dist, "assets", "icons"))} \
        if os.path.isdir(os.path.join(dist, "assets", "icons")) else set()
    return 본


# ── 훑기 ────────────────────────────────────────────────────────────────────

이음 = re.compile(r"""['"]\s*\n\s*[a-zA-Z]?['"]""")


def 이어붙이기(줄들):
    """파이썬 f-문자열이 한 태그를 여러 줄로 쪼갠 것을 이어 본다.

    `f'<input data-s1-part="field"' / f' value="..">'` 처럼 끊긴 태그를 한 줄처럼 읽는다.
    돌려주는 것은 (이은 글, 글자자리→원래 줄번호) 두 벌이다.
    """
    글 = "\n".join(줄들)
    줄번호 = []
    n = 1
    for 글자 in 글:
        줄번호.append(n)
        if 글자 == "\n":
            n += 1
    새글, 새번호 = [], []
    i = 0
    while i < len(글):
        m = 이음.match(글, i)
        if m:
            i = m.end()
            continue
        새글.append(글[i])
        새번호.append(줄번호[i])
        i += 1
    return "".join(새글), 새번호


def 벗기기(글):
    """`s1-제외` 로 뺀 줄을 빈 줄로 만든다. 줄 번호는 그대로 남는다."""
    줄들, 구역, 뺀수 = [], False, 0
    for 줄 in 글.splitlines():
        if 제외시작.search(줄):
            구역 = True
        if 구역 or 제외한줄.search(줄):
            줄들.append("")
            뺀수 += 1
            if 제외끝.search(줄):
                구역 = False
            continue
        줄들.append(줄)
    return 줄들, 뺀수


손수찾기 = {
    "button": re.compile(r"<button\b([^>]*)>"),
    "input": re.compile(r"<input\b([^>]*)>"),
    "textarea": re.compile(r"<textarea\b([^>]*)>"),
    "select": re.compile(r"<select\b([^>]*)>"),
    "table": re.compile(r"<table\b([^>]*)>"),
    "dialog": re.compile(r"<dialog\b([^>]*)>"),
}
대신쓸것 = {"button": "button", "input": "input", "textarea": "textarea",
        "select": "select", "table": "table", "dialog": "modal"}
# 이름(class)만 보고 아는 자리 — 태그 한 덩어리를 통째로 잡아 **그 태그의 속성**만 본다
# (앞뒤 글을 함께 보면 옆 태그의 표시에 가려 놓친다).
반이름 = re.compile(r'<[a-z]+\b[^>]*class="[^"]*\b(chip|tag|badge|pill|tabbar|tabs?|page-nav'
                 r'|page-step|s1-btn|btn|button)\b[^"]*"[^>]*>')
반대신 = {"chip": "chip", "tag": "chip", "badge": "chip", "pill": "chip",
       "tabbar": "tab", "tab": "tab", "tabs": "tab",
       "page-nav": "pagination", "page-step": "pagination",
       "s1-btn": "button", "btn": "button", "button": "button"}

부품표시 = re.compile(r'data-s1-component="([a-z-]+)"')
뼈대표시 = re.compile(r'data-s1-part="([a-z-]+)"')
속성값 = re.compile(r'data-(size|variant|type|mode|break)="([a-z0-9-]+)"')

꾸밈속성 = ("color", "background", "background-color", "border", "border-color", "border-width",
        "border-radius", "font-size", "font-weight", "height", "min-height", "padding",
        "box-shadow", "line-height")
css규칙 = re.compile(r"^\s*([^{}@/][^{}]*)\{([^{}]*)\}?\s*$")
맨태그 = re.compile(r"(^|[\s,>+~])(button|input|select|textarea|table|thead|tbody|th|td|dialog)(?=[\s,:.\[{]|$)")
부품덮기 = re.compile(r"\[data-s1-component")
인라인svg = re.compile(r"<svg\b")
가면 = re.compile(r"mask-image\s*:\s*url\(['\"]?([^'\")]+)")


def 파일보기(길, 본):
    글 = open(길, encoding="utf-8", errors="replace").read()
    줄들, 뺀수 = 벗기기(글)
    말썽 = []
    이은글, 번호 = 이어붙이기(줄들)

    def 줄(자리):
        return 번호[자리] if 자리 < len(번호) else len(줄들)

    # ── 줄 단위로 보는 것 (1 · 5) ──────────────────────────────────────────
    for n, 한줄 in enumerate(줄들, 1):
        # 1 — 손으로 옮겨 적은 사본을 입는 화면
        if "s1_tokens.링크()" in 한줄:
            말썽.append((n, "사본을 입음", "s1_tokens.링크()",
                       "정본 부품 CSS 가 아니라 손으로 옮겨 적은 사본입니다 — 부품() 으로 바꾸세요"))
        # 5 — 부품 생김새를 화면에서 덮어씀
        m = css규칙.match(한줄)
        if m:
            고른것, 속 = m.group(1), m.group(2)
            꾸밈 = [q for q in 꾸밈속성 if re.search(r"(^|[;\s])%s\s*:" % re.escape(q), 속)]
            if 꾸밈 and (부품덮기.search(고른것) or 맨태그.search(고른것)):
                말썽.append((n, "부품 덮어씀", 고른것.strip()[:60],
                           "화면은 배치만 합니다 — 생김새(%s)는 정본이 정합니다" % ", ".join(꾸밈[:3])))

    # ── 태그 단위로 보는 것 (2 · 3 · 4 · 6) ────────────────────────────────
    # 2 — 표시 없는 부품
    for 태그, 잡기 in 손수찾기.items():
        for m in 잡기.finditer(이은글):
            속 = m.group(1)
            if 태그 == "input" and re.search(r'type="?(hidden|file)', 속):
                continue
            if 부품표시.search(속) or 뼈대표시.search(속):
                continue
            말썽.append((줄(m.start()), "표시 없는 부품", "<%s>" % 태그,
                       "정본 %s 부품이 있습니다 — data-s1-component 로 부르세요" % 대신쓸것[태그]))
    for m in 반이름.finditer(이은글):
        낱, 태그속 = m.group(1), m.group(0)
        if 부품표시.search(태그속) or 뼈대표시.search(태그속):
            continue
        말썽.append((줄(m.start()), "표시 없는 부품", ".%s" % 낱,
                   "정본 %s 부품이 있습니다 — data-s1-component 로 부르세요" % 반대신[낱]))

    # 3 — 정본에 없는 크기·변형 이름
    for m in re.finditer(r"<[a-z]+\b[^>]*data-s1-component=\"([a-z-]+)\"[^>]*>", 이은글):
        부품, 태그속 = m.group(1), m.group(0)
        앎 = 본["부품"].get(부품)
        if 앎 is None:
            말썽.append((줄(m.start()), "정본에 없는 부품", 부품, "정본 부품 목록에 없는 이름입니다"))
            continue
        받는 = 앎.get("속성", {})
        for 속성, 값 in 속성값.findall(태그속):
            쓸수있음 = 앎["나눔"] if 속성 == "break" else 받는.get(속성)
            if 쓸수있음 and 값 not in 쓸수있음:
                말썽.append((줄(m.start()), "정본에 없는 값",
                           '%s data-%s="%s"' % (부품, 속성, 값),
                           "정본이 받는 것: %s" % " · ".join(sorted(쓸수있음))))

    # 4 — 뼈대(part) 가 그 부품·그 태그의 것인가
    모든뼈대 = set()
    for 앎 in 본["부품"].values():
        모든뼈대 |= 앎["뼈대"]
    for m in 뼈대표시.finditer(이은글):
        if 모든뼈대 and m.group(1) not in 모든뼈대:
            말썽.append((줄(m.start()), "정본에 없는 뼈대", m.group(1),
                       "정본 부품의 뼈대 이름이 아닙니다"))
    for 태그 in ("input", "textarea", "select", "button"):
        맞는것 = set()
        for (부품, t), 자리들 in 본["태그자리"].items():
            if t == 태그:
                맞는것 |= 자리들
        if not 맞는것:
            continue
        for m in re.finditer(r"<%s\b([^>]*)>" % 태그, 이은글):
            단 = 뼈대표시.search(m.group(1))
            if 단 and 단.group(1) not in 맞는것:
                말썽.append((줄(m.start()), "뼈대 어긋남",
                           '<%s data-s1-part="%s">' % (태그, 단.group(1)),
                           "정본은 여기에 %s 를 답니다" % " · ".join(sorted(맞는것))))

    # 6 — 직접 그린 아이콘
    for m in 인라인svg.finditer(이은글):
        말썽.append((줄(m.start()), "직접 그린 아이콘", "<svg>",
                   "정본 아이콘을 쓰거나, 그림판이면 s1-제외 를 적어 두세요"))
    for m in 가면.finditer(이은글):
        길이름 = m.group(1)
        이름 = os.path.basename(길이름)
        이름 = 이름[:-4] if 이름.endswith(".svg") else 이름
        if 본["아이콘파일"] and 이름 not in 본["아이콘파일"]:
            말썽.append((줄(m.start()), "목록 밖 아이콘", 이름,
                       "정본 아이콘 %d개 밖입니다 — DESIGN_SYSTEM_GAP 으로 적어 두세요"
                       % len(본["아이콘파일"])))

    # 정본에 없어 우리가 그린 것으로 **적어 둔** 자리는 위반이 아니라 빈자리로 센다(가이드 §9-9).
    # 적어 둔 자리는 그 줄부터 **빈 줄이 나올 때까지**(길어도 열두 줄) 미친다 —
    # 한 덩어리를 한 번만 적게 하려는 것이다.
    적어둠 = set()
    for n, 한줄 in enumerate(줄들, 1):
        if not 빈자리.search(한줄):
            continue
        for k in range(n, min(n + 12, len(줄들)) + 1):
            적어둠.add(k)
            if k > n and not 줄들[k - 1].strip():
                break
    빈자리갈래 = ("부품 덮어씀", "직접 그린 아이콘", "목록 밖 아이콘", "정본에 없는 부품",
              "표시 없는 부품")
    말썽 = [(n, ("GAP·" + 갈래) if (n in 적어둠 and 갈래 in 빈자리갈래) else 갈래, 무엇, 꼬리)
          for n, 갈래, 무엇, 꼬리 in 말썽]
    말썽.sort(key=lambda x: x[0])
    return 말썽, 뺀수


# ── 7 · 받아 둔 정본이 낡았나 ────────────────────────────────────────────────

def 판점검(뿌리, 자리, 본):
    말 = []
    우리 = os.path.join(뿌리, "mvp0", "assets", "css", "s1-ui.css")
    if os.path.exists(우리):
        머리 = open(우리, encoding="utf-8", errors="replace").readline()
        m = re.search(r"s1-ui ([0-9.]+ [0-9-]+)", 머리)
        가진판 = m.group(1) if m else "(판 모름)"
        if 본["판"] and 가진판.split()[0] != 본["판"].split()[0]:
            말.append("부품 판이 뒤처졌습니다 — 가진 것 %s · 정본 %s (bash scripts/부품받기.sh)"
                      % (가진판, 본["판"]))
    else:
        말.append("정본 부품 CSS 가 없습니다 — bash scripts/부품받기.sh")
    for 이름 in ("tokens.css", "component-tokens.css", "typography.css", "site-base.css"):
        a = os.path.join(뿌리, "mvp0", "assets", "css", 이름)
        b = os.path.join(자리, "assets", "css", 이름)
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        머리줄 = lambda l: "디자인가이드" in l and "판" in l   # 받아 두며 적어 넣는 한 줄
        갑 = [l for l in open(a, encoding="utf-8", errors="replace").read().splitlines()
              if not 머리줄(l)]
        을 = [l for l in open(b, encoding="utf-8", errors="replace").read().splitlines()
              if not 머리줄(l)]
        if 갑 != 을:
            말.append("토큰이 정본과 다릅니다 — %s (가이드받기.sh --내려두기 mvp0/assets/css)" % 이름)
    return 말


def 파일들(대상):
    for 길 in 대상:
        if os.path.isfile(길):
            yield 길
            continue
        for 뿌리, 폴더들, 이름들 in os.walk(길):
            폴더들[:] = [d for d in 폴더들 if d not in 건너뛸폴더]
            for 이름 in 이름들:
                if os.path.splitext(이름)[1] in 볼확장자 and 이름 not in 건너뛸파일:
                    yield os.path.join(뿌리, 이름)


def main(argv):
    자리, 대상, 조용히 = 기본정본, [], False
    i = 0
    while i < len(argv):
        if argv[i] == "--정본":
            자리 = argv[i + 1]
            i += 2
            continue
        if argv[i] == "--조용히":
            조용히 = True
            i += 1
            continue
        대상.append(argv[i])
        i += 1
    뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not 대상:
        대상 = [os.path.join(뿌리, "mvp0")]

    본 = 정본읽기(자리)
    print("정본 부품 판: %s · 부품 %d갈래" % (본["판"] or "(모름)", len(본["부품"])))

    낡음 = 판점검(뿌리, 자리, 본)
    for 말 in 낡음:
        print("  [낡음] %s" % 말)

    모두, 파일수, 뺀줄 = 0, 0, 0
    갈래수 = {}
    for 길 in sorted(set(파일들(대상))):
        말썽, 뺀수 = 파일보기(길, 본)
        파일수 += 1
        뺀줄 += 뺀수
        for _, 갈래, _, _ in 말썽:
            갈래수[갈래] = 갈래수.get(갈래, 0) + 1
        모두 += sum(1 for _, 갈래, _, _ in 말썽 if not 갈래.startswith("GAP·"))
        if 말썽 and not 조용히:
            print("\n%s" % os.path.relpath(길, 뿌리))
            for n, 갈래, 무엇, 꼬리 in 말썽:
                print("  %s:%d  [%s] %s — %s" % (os.path.basename(길), n, 갈래, 무엇, 꼬리))

    print("")
    for 갈래, 수 in sorted(갈래수.items(), key=lambda x: (x[0].startswith("GAP·"), -x[1])):
        print("  %-18s %4d곳%s" % (갈래, 수, "  (적어 둔 빈자리)" if 갈래.startswith("GAP·") else ""))
    꼬리 = " · 제외 표시로 건너뛴 줄 %d" % 뺀줄 if 뺀줄 else ""
    print("\n파일 %d개 · 정본 밖 %d곳%s" % (파일수, 모두 + len(낡음), 꼬리))
    return 1 if (모두 or 낡음) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
