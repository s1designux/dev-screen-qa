#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""규칙 뽑기 — 검수기 코드에 적힌 규칙을 긁어 와, 사람이 읽는 문서와 어긋난 곳을 알려 준다.

왜: 규칙의 원본은 코드(`engine/ui.html`, `valueqa/`)이고, `docs/검수규칙-한눈에.html` 은
사람이 손으로 적은 사본이다. 코드를 고쳐도 사본은 저절로 바뀌지 않아 닷새씩 뒤처졌다.
이 도구는 둘을 맞대어 **빠진 줄·없어진 줄·달라진 숫자**를 짚고, 새 규칙의 표 한 줄 초안을 만들어 준다.

문서를 저 혼자 고쳐 쓰지는 않는다(CLAUDE.md 2번-2: 자동으로 확정하지 않는다).
`--넣기` 를 눌렀을 때만 빠진 줄을 표 끝에 '확인 필요' 표시와 함께 꽂는다.

쓰는 법:
  python3 scripts/규칙뽑기.py            # 점검만 — 어긋난 곳을 보여준다 (어긋나면 종료코드 1)
  python3 scripts/규칙뽑기.py --목록      # 코드에서 뽑은 규칙 전부를 JSON으로
  python3 scripts/규칙뽑기.py --초안      # 문서에 빠진 규칙의 표 한 줄 초안만 출력
  python3 scripts/규칙뽑기.py --넣기      # 그 초안을 문서에 실제로 꽂는다(사람이 문장을 다듬는다)
"""
import argparse, ast, hashlib, json, os, re, sys

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
엔진 = os.path.join(뿌리, "engine", "ui.html")
문서 = os.path.join(뿌리, "docs", "검수규칙-한눈에.html")
값비교 = os.path.join(뿌리, "valueqa", "compare.py")
값규정 = os.path.join(뿌리, "valueqa", "rules.py")

# 코드의 표 이름 → 문서에서 쓰는 짧은 이름(= data-규칙 앞머리)
표들 = [
    ("POLICY_EXCLUDE_RULES", "시안제외", "디자인 시안에서 먼저 빼는 것"),
    ("POLICY_IMAGE_RULES", "그림덩어리", "그림 한 덩어리로 보는 것"),
    ("CAPTURE_EXCLUDE_RULES", "촬영본제외", "개발 사진에서 먼저 빼는 것"),
    ("POLICY_TEXT_RULES", "가변표", "글자가 데이터라서 달라도 되는지"),
    ("POLICY_LIST_RULES", "목록표", "여러 후보를 함께 봐야 아는 것"),
]


def 엔진규칙(글=None):
    """`var 이름=[ {id:"..",title:".."} ... ]` 에서 규칙 이름표를 긁는다."""
    글 = 글 if 글 is not None else open(엔진, encoding="utf-8").read()
    줄들 = 글.split("\n")
    out = []
    for 변수, 짧은, 제목 in 표들:
        시작 = None
        for i, l in enumerate(줄들):
            if l.startswith("var %s=[" % 변수):
                시작 = i
                break
        if 시작 is None:
            continue
        끝 = 시작
        for i in range(시작 + 1, len(줄들)):
            if re.match(r"^\}?\];\s*$", 줄들[i]):
                끝 = i
                break
        토막 = 줄들[시작:끝 + 1]
        for i, l in enumerate(토막):
            m = re.search(r'id:"([^"]+)",\s*(?:edge:"[^"]*",\s*)?title:"([^"]+)"', l)
            if not m:
                continue
            설명 = []
            for 다음 in 토막[i + 1:i + 5]:
                c = 다음.strip()
                if not c.startswith("//"):
                    break
                설명.append(c[2:].strip())
            out.append({"표": 짧은, "표제목": 제목, "id": m.group(1),
                        "이름": m.group(2), "설명": " ".join(설명)})
    return out


def _사전(경로, 이름):
    글 = open(경로, encoding="utf-8").read()
    m = re.search(r"^%s = (\{.*?^\})" % re.escape(이름), 글, re.S | re.M)
    return ast.literal_eval(m.group(1)) if m else {}


def 겉칸열쇠(사전글):
    """사전 글월에서 **맨 바깥 층**의 열쇠만 뽑는다(속에 든 사전은 건너뛴다)."""
    out, 깊이, i = set(), 0, 0
    while i < len(사전글):
        c = 사전글[i]
        if c in "{[(":
            깊이 += 1
        elif c in "}])":
            깊이 -= 1
        elif c == '"' and 깊이 == 1:
            j = 사전글.index('"', i + 1)
            열쇠 = 사전글[i + 1:j]
            뒤 = 사전글[j + 1:j + 2]
            if 뒤 == ":":
                out.add(열쇠)
            i = j
        i += 1
    return out


def 값규칙():
    """값 대조에서 속성마다 몇까지 봐주는지 + 규정 대조 세 판정."""
    허용, 이름 = _사전(값비교, "허용"), _사전(값비교, "이름")
    별칭 = {"opacity": "투명도"}
    out = []
    for k, v in 허용.items():
        out.append({"표": "값허용치", "표제목": "값 대조 허용치", "id": k,
                    "이름": 이름.get(k, 별칭.get(k, k)), "설명": "넘어감 %s / 주의 %s" % (v[0], v[1]),
                    "값": list(v)})
    for k, 라벨 in 이름.items():
        if k not in 허용:
            out.append({"표": "값허용치", "표제목": "값 대조 허용치", "id": k,
                        "이름": 라벨, "설명": "글자 그대로 같아야 함", "값": None})
    글 = open(값규정, encoding="utf-8").read()
    # 규정 대조는 `규정검사()` 가 돌려주는 세 갈래가 곧 규칙이다.
    # 주석·설명글에 낱말이 남아 있어도 '있다'고 보면 안 되므로, 돌려주는 사전 안에서만 찾는다.
    m = re.search(r"^def 규정검사\(.*?^\s*return (\{.*?^\s*\})", 글, re.S | re.M)
    반환 = 겉칸열쇠(m.group(1)) if m else set()   # 속에 든 사전('셈')의 열쇠는 세지 않는다
    for 키, 라벨 in (("토큰밖", "토큰 밖의 값"), ("규격", "컴포넌트 규격"),
                     ("시안규정", "시안 자체가 규정 밖")):
        if 키 in 반환:
            out.append({"표": "규정대조", "표제목": "규정 대조", "id": 키,
                        "이름": 라벨, "설명": "", "값": None})
    return out


def 코드규칙():
    return 엔진규칙() + 값규칙()


def 문서규칙(글=None):
    글 = 글 if 글 is not None else open(문서, encoding="utf-8").read()
    out = set()
    for 값 in re.findall(r'data-규칙="([^"]+)"', 글):
        out.update(값.split())   # 한 줄이 규칙 여럿을 맡을 수 있다(안쪽여백 네 방향처럼)
    return out


def 열쇠(r):
    return "%s.%s" % (r["표"], r["id"])


def 줄찾기(글, 열쇠):
    """그 규칙을 맡은 표 한 줄을 찾는다. 한 줄이 규칙 여럿을 맡는 경우(안쪽여백 네 방향)도 찾는다."""
    for m in re.finditer(r"<tr[^>]*data-규칙=\"([^\"]+)\"[^>]*>(.*?)</tr>", 글, re.S):
        if 열쇠 in m.group(1).split():
            return m
    return None


def 칸들(줄):
    return [re.sub(r"<[^>]*>", " ", c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", 줄, re.S)]


def 칸수(줄):
    """표 한 줄이 실제로 차지하는 칸 수. colspan 으로 여러 칸을 묶은 줄도 제대로 센다."""
    n = 0
    for 머리 in re.findall(r"<t[dh]([^>]*)>", 줄):
        m = re.search(r'colspan="?(\d+)"?', 머리)
        n += int(m.group(1)) if m else 1
    return n


def 숫자점검(글):
    """문서에 적힌 허용치가 코드와 같은지. 넘어감·주의를 **칸 차례대로** 본다(둘이 뒤바뀐 것도 잡는다)."""
    어긋남 = []
    for r in 값규칙():
        if not r.get("값"):
            continue
        m = 줄찾기(글, 열쇠(r))
        if not m:
            continue   # 줄 자체가 없는 것은 위에서 [문서에 없음] 으로 이미 말한다
        if 'data-숫자="안봄"' in m.group(0):
            continue   # 후보로 올리지 않는 속성(안쪽여백)은 허용치 숫자를 문서에 적지 않는다
        cs = 칸들(m.group(2))
        본칸, 빠진 = 0, []
        for v in r["값"]:
            찾음 = False
            for i in range(본칸, len(cs)):   # 앞 칸으로 되돌아가지 않는다 = 차례가 지켜져야 한다
                if re.search(r"(?<![\d.])%s(?![\d])" % re.escape(str(v)), cs[i]):
                    본칸, 찾음 = i, True
                    break
            if 찾음:
                continue
            if v == 0 and any("같아야" in c for c in cs):
                continue
            빠진.append(str(v))
        if 빠진:
            어긋남.append((r["이름"], r["값"], 빠진))
    return 어긋남


def 도장(rs):
    """규칙 문구가 바뀐 것을 알아채려고 한 줄에 남기는 짧은 지문.

    한 줄이 규칙 여럿을 맡을 수 있으므로(안쪽여백 네 방향) 그 줄이 맡은 규칙을 모두 넣어 찍는다.
    """
    if isinstance(rs, dict):
        rs = [rs]
    씨 = "\n".join(sorted("%s|%s|%s" % (열쇠(r), r["이름"], r.get("설명") or "") for r in rs))
    return hashlib.sha1(씨.encode("utf-8")).hexdigest()[:8]


def 줄마다규칙(글):
    """문서의 표 줄 → 그 줄이 맡은 코드 규칙들."""
    있는 = {열쇠(r): r for r in 코드규칙()}
    out = []
    for m in re.finditer(r'<tr[^>]*data-규칙="([^"]+)"[^>]*>.*?</tr>', 글, re.S):
        rs = [있는[k] for k in m.group(1).split() if k in 있는]
        if rs:
            out.append((m, rs))
    return out


def 문구점검(글):
    어긋남 = []
    for m, rs in 줄마다규칙(글):
        적힌 = re.search(r'data-판="([^"]+)"', m.group(0))
        if 적힌 and 적힌.group(1) != 도장(rs):
            어긋남.append((열쇠(rs[0]), ", ".join(r["이름"] for r in rs)))
    return 어긋남


def 초안줄(r, 칸수=2, 번호칸=False):
    설명 = r["설명"] or r["이름"]
    칸 = []
    if 번호칸:
        칸.append('<td class="n">?</td>')
    칸.append('<td class="k">%s <span class="tag new">확인 필요</span></td>' % r["이름"])
    남은 = max(1, 칸수 - len(칸))
    칸.append("<td%s>%s</td>" % (' colspan="%d"' % 남은 if 남은 > 1 else "", 설명))
    return '  <tr data-규칙="%s" data-판="%s">%s</tr>' % (열쇠(r), 도장([r]), "".join(칸))


def 표끝찾기(글, 표):
    """그 표의 줄이 **가장 많이 모여 있는 <table>** 을 고르고, 그 안의 마지막 줄 뒤 자리를 돌려준다.

    문서 한 장에 같은 갈래의 표가 둘 이상 있을 수 있다(값 허용치 표 / 일부러 빼는 것 표).
    가장 많이 모인 표가 그 갈래의 본 표다. 칸 수와 번호칸 여부도 함께 돌려준다.
    """
    최고 = None
    for t in re.finditer(r"<table[^>]*>.*?</table>", 글, re.S):
        줄들 = [m for m in re.finditer(r'<tr[^>]*data-규칙="([^"]+)"[^>]*>(.*?)</tr>', t.group(0), re.S)
                if any(k.startswith(표 + ".") for k in m.group(1).split())]
        if not 줄들:
            continue
        if not 최고 or len(줄들) > 최고[0]:
            마지막 = 줄들[-1]
            번호 = 'class="n"' in 마지막.group(0)
            최고 = (len(줄들), t.start() + 마지막.end(), 칸수(마지막.group(0)), 번호)
    return 최고[1:] if 최고 else None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--목록", action="store_true")
    p.add_argument("--초안", action="store_true")
    p.add_argument("--넣기", action="store_true")
    p.add_argument("--도장", action="store_true", help="지금 문서가 맞다고 보고, 규칙 문구 지문을 다시 찍는다")
    a = p.parse_args()

    코드 = 코드규칙()
    if a.목록:
        print(json.dumps(코드, ensure_ascii=False, indent=2))
        return 0

    글 = open(문서, encoding="utf-8").read()
    if a.도장:
        새글, 찍음 = 글, 0
        while True:
            남은 = [(m, rs) for m, rs in 줄마다규칙(새글)
                    if (re.search(r'data-판="([^"]+)"', m.group(0)) or [None])
                    and (re.search(r'data-판="([^"]+)"', m.group(0)).group(1) if re.search(r'data-판="([^"]+)"', m.group(0)) else None) != 도장(rs)]
            if not 남은:
                break
            m, rs = 남은[0]
            새줄 = re.sub(r'\s*data-판="[^"]*"', "", m.group(0))
            새줄 = 새줄.replace('data-규칙="', 'data-판="%s" data-규칙="' % 도장(rs), 1)
            새글 = 새글[:m.start()] + 새줄 + 새글[m.end():]
            찍음 += 1
        open(문서, "w", encoding="utf-8").write(새글)
        print("규칙 문구 지문 %d개를 찍었습니다." % 찍음)
        return 0
    적힌 = 문서규칙(글)
    있는 = {열쇠(r): r for r in 코드}
    빠짐 = [r for k, r in 있는.items() if k not in 적힌]
    남음 = sorted(적힌 - set(있는))
    숫자 = 숫자점검(글)
    문구 = 문구점검(글)

    if a.초안:
        for r in 빠짐:
            자리 = 표끝찾기(글, r["표"])
            print(초안줄(r, 자리[1], 자리[2]) if 자리 else 초안줄(r))
        if not 빠짐:
            print("문서에 빠진 규칙이 없습니다.")
        return 0

    if a.넣기:
        if not 빠짐:
            print("문서에 꽂을 것이 없습니다.")
            return 0
        새글, 꽂음 = 글, 0
        for r in 빠짐:
            찾음 = 표끝찾기(새글, r["표"])
            if 찾음 is None:
                print("! %s 표를 문서에서 못 찾았습니다 — %s 는 손으로 넣어 주세요." % (r["표"], r["이름"]))
                continue
            자리, 칸수, 번호칸 = 찾음
            새글 = 새글[:자리] + "\n" + 초안줄(r, 칸수, 번호칸) + 새글[자리:]
            꽂음 += 1
        open(문서, "w", encoding="utf-8").write(새글)
        print("%d줄 꽂았습니다 — 문장은 사람이 다듬습니다." % 꽂음)
        return 0

    print("코드에 있는 규칙 %d개 · 문서에 적힌 규칙 %d개" % (len(있는), len(적힌)))
    for r in 빠짐:
        print("  [문서에 없음] %s — %s" % (열쇠(r), r["이름"]))
    for k in 남음:
        print("  [코드에 없음] %s — 규칙이 없어졌는데 문서에 남아 있습니다." % k)
    for 이름, 값, 빠진 in 숫자:
        print("  [숫자 다름] %s — 코드는 %s 인데 문서에 %s 가 안 보입니다." % (이름, 값, ", ".join(빠진)))
    for k, 이름 in 문구:
        print("  [문구 바뀜] %s — 코드의 규칙 설명이 바뀌었습니다(지금: %s). 문서 줄을 다시 읽어 보세요." % (k, 이름))
    if 빠짐 or 남음 or 숫자 or 문구:
        print("\n새 규칙의 표 한 줄 초안: python3 scripts/규칙뽑기.py --초안")
        return 1
    print("문서와 코드가 같습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
