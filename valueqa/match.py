"""이름표 없이 짝 맞추기 — 시안 요소 ↔ 개발 요소.

레이어 이름이나 개발 쪽 id 에 기대지 않는다. 글자·자리·크기·종류 네 가지만 보고 잇는다.
(plugin-value-qa/ui.html 의 runMatcher() 를 그대로 옮긴 것. 점수 배합을 바꾸면 저쪽도 함께 바꾼다.)
"""
import math
import re

지울글자 = re.compile(r"[\s\.,#·\[\]（）()！!？?～~・]")


def 다듬기(s):
    return 지울글자.sub("", (s or "").lower())


def 두글자쌍(s):
    o = {}
    n = 0
    for i in range(len(s) - 1):
        o[s[i:i + 2]] = 1
        n += 1
    return o, max(1, n)


def 글자닮음(a, b):
    a, b = 다듬기(a), 다듬기(b)
    if not a and not b:
        return 0.5
    if not a or not b:
        return 0.15
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    A, an = 두글자쌍(a)
    B, bn = 두글자쌍(b)
    같은수 = sum(1 for k in A if k in B)
    return 같은수 / (an + bn - 같은수)


def 짝점수(f, d, FW, FH, DW, DH):
    t = 글자닮음(f.get("text"), d.get("text"))
    같은종류 = 1.0 if f.get("isText") == d.get("isText") else 0.0
    둘다글자 = f.get("isText") and d.get("isText")
    거리 = math.hypot(f["box"]["x"] / FW - d["box"]["x"] / DW,
                     f["box"]["y"] / FH - d["box"]["y"] / DH)
    자리 = max(0.0, 1 - 거리 / 0.4)
    높이비 = min(f["box"]["h"], d["box"]["h"]) / max(f["box"]["h"], d["box"]["h"], 0.001)
    너비비 = min(f["box"]["w"], d["box"]["w"]) / max(f["box"]["w"], d["box"]["w"], 0.001)
    크기 = 높이비 if 둘다글자 else 너비비 * 높이비
    return 0.30 * t + 0.10 * 같은종류 + 0.35 * 자리 + 0.25 * 크기


def 짝맞추기(시안, 개발, 문턱=0.5):
    """{pairs, unmatchedF, unmatchedD, fig, devEls} 를 돌려준다."""
    FW = 시안["meta"]["artboardWidth"]
    FH = 시안["meta"].get("artboardHeight") or FW
    DW = 개발["meta"]["artboardWidth"]
    DH = 개발["meta"].get("artboardHeight") or DW
    fig = 시안["elements"]
    # 화면 전체를 덮는 바깥 상자(body 래퍼)는 짝 대상에서 뺀다 — 무엇과도 어중간하게 붙는다.
    devEls = [e for e in 개발["elements"]
              if not (e["box"]["x"] <= 1 and e["box"]["y"] <= 1
                      and e["box"]["w"] >= DW - 2 and e["box"]["h"] >= DH - 2)]

    후보쌍 = []
    for fi, f in enumerate(fig):
        for di, d in enumerate(devEls):
            # 종류가 다르면 원칙적으로 안 짝지음(글자↔상자 억지 방지).
            # 단, 글자가 강하게 일치 '그리고' 크기도 비슷하면 교차 허용(뱃지·색버튼).
            if f.get("isText") != d.get("isText"):
                fa = f["box"]["w"] * f["box"]["h"]
                da = d["box"]["w"] * d["box"]["h"]
                넓이비 = min(fa, da) / max(fa, da, 0.001)
                if 글자닮음(f.get("text"), d.get("text")) < 0.8 or 넓이비 < 0.25:
                    continue
            후보쌍.append((짝점수(f, d, FW, FH, DW, DH), fi, di))

    후보쌍.sort(key=lambda x: -x[0])
    쓴시안, 쓴개발, 짝 = {}, {}, []
    for s, fi, di in 후보쌍:
        if s < 문턱 or fi in 쓴시안 or di in 쓴개발:
            continue
        쓴시안[fi] = 1
        쓴개발[di] = 1
        짝.append({"fi": fi, "di": di, "s": round(s, 4)})

    return {
        "fig": fig,
        "devEls": devEls,
        "pairs": 짝,
        "unmatchedF": [i for i in range(len(fig)) if i not in 쓴시안],
        "unmatchedD": [i for i in range(len(devEls)) if i not in 쓴개발],
    }
