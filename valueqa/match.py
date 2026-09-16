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


def 내용옮김(개발):
    """개발에서 잰 자리는 '판(아트보드)' 기준이고, 시안 자리는 '화면' 기준이다.

    촬영기는 넓은 판 한가운데에 화면을 앉히고 그 자리를 contentX/Y 에 음수로 적어 둔다
    (예: contentX=-2240 이면 판의 x=2240 이 화면의 x=0). 이 값을 안 빼면 화면 전체가
    옆으로 2240 밀린 채로 짝을 찾아, 홈처럼 판이 넓은 화면은 거의 모든 요소가 짝을 잃는다.
    (근거: 우비스 버스 홈 4장 — 판 5120 · 화면 1920)
    """
    m = 개발.get("meta") or {}
    폭 = m.get("docW") or m.get("viewportWidth") or m.get("artboardWidth") or 1
    높 = m.get("artboardHeight") or 폭
    dx, dy = m.get("contentX") or 0, m.get("contentY") or 0
    if dx or dy:
        높 = 높 + dy                                  # 판 위아래 여백만큼 화면이 짧다
    return float(폭), float(max(높, 1)), float(dx), float(dy)


def _자리표(fig, devEls, 배율, dy=0.0):
    """글자가 똑같고 화면에 딱 하나뿐인 요소들로 '개발 → 시안' 세로 밀림을 잰다."""
    본것 = {}
    for d in devEls:
        if not d.get("isText"):
            continue
        키 = 다듬기(d.get("text"))
        if 키:
            본것[키] = None if 키 in 본것 else d
    밀림, 쓴글자 = [], set()
    for f in fig:
        키 = 다듬기(f.get("text"))
        if not f.get("isText") or not 키 or 키 in 쓴글자:
            continue
        d = 본것.get(키)
        if d is None:
            continue                      # 같은 글자가 여럿이면 어느 것인지 모른다 — 안 쓴다
        쓴글자.add(키)
        밀림.append(f["box"]["y"] - (d["box"]["y"] + dy) * 배율)
    return 밀림


def 세로밀림들(fig, devEls, 배율, dy=0.0):
    """개발 화면을 시안 위에 올릴 때 세로로 얼마나 밀어야 맞는지 — 여러 개일 수 있다.

    웹 화면은 통째로 한 번 밀리지 않는다. 시안 프레임에는 가짜 브라우저 틀이 얹혀 있고,
    바닥글은 창 아래에 붙어 있어서 **머리·본문·바닥이 저마다 다르게 밀린다.**
    그래서 밀림 하나를 고르거나 높이 비율로 늘이면(둘 다 해 봤다) 위아래로 붙은 요소가
    서로 자리를 바꿔 잡힌다 — 아이디 칸이 비밀번호 칸에 붙는 식이다.

    그래서 밀림을 **덩어리로 모아 여럿 그대로 둔다.** 견줄 때는 그중 가장 잘 맞는 것을 쓴다.
    잴 것이 없으면 빈 목록을 돌려 예전 방식(각자 높이로 나누기)으로 둔다.
    """
    밀림 = sorted(_자리표(fig, devEls, 배율, dy))
    if not 밀림:
        return []
    덩어리, 지금 = [], [밀림[0]]
    for v in 밀림[1:]:
        if v - 지금[-1] <= 20:
            지금.append(v)
        else:
            덩어리.append(지금)
            지금 = [v]
    덩어리.append(지금)
    덩어리.sort(key=lambda g: -len(g))
    덩어리 = 덩어리[:4]
    return [sum(g) / len(g) for g in 덩어리]


def 짝점수(f, d, FW, FH, DW, DH, 배율=None, 밀림들=None, 옮김=(0.0, 0.0)):
    t = 글자닮음(f.get("text"), d.get("text"))
    같은종류 = 1.0 if f.get("isText") == d.get("isText") else 0.0
    둘다글자 = f.get("isText") and d.get("isText")
    # 개발 자리를 시안 자 위로 옮겨 놓고 견준다 — 가로는 폭으로, 세로는 맞춰 둔 자로.
    # 자를 못 맞췄으면 예전처럼 각자 높이로 나눈다(옛 엔진과의 셈 맞춤이 깨지지 않는다).
    배율 = (FW / DW) if 배율 is None else 배율
    dx, dy = 옮김
    ㄱ, ㄴ = d["box"]["x"] + dx, d["box"]["y"] + dy
    거리가로 = f["box"]["x"] / FW - ㄱ * 배율 / FW
    if 밀림들:
        거리세로 = min(abs(f["box"]["y"] - (ㄴ * 배율 + m)) for m in 밀림들) / FH
    else:
        거리세로 = f["box"]["y"] / FH - ㄴ / DH
    거리 = math.hypot(거리가로, 거리세로)
    자리 = max(0.0, 1 - 거리 / 0.4)
    높이비 = min(f["box"]["h"], d["box"]["h"]) / max(f["box"]["h"], d["box"]["h"], 0.001)
    너비비 = min(f["box"]["w"], d["box"]["w"]) / max(f["box"]["w"], d["box"]["w"], 0.001)
    크기 = 높이비 if 둘다글자 else 너비비 * 높이비
    return 0.30 * t + 0.10 * 같은종류 + 0.35 * 자리 + 0.25 * 크기


def 값닮음(f, d):
    """상자끼리 자리·크기가 똑같이 겹칠 때 어느 쪽이 '그' 요소인지 가르는 실마리.

    개발 화면은 같은 자리에 두 겹을 둔다 — 눈에 보이지 않는 입력칸(<input>) 위에
    실제로 그려지는 상자(<span>)를 얹는 식이다. 자리·크기만 보면 둘의 점수가 똑같아서
    먼저 적힌 쪽(대개 안 보이는 입력칸)이 잡히고, 진짜로 그려지는 쪽은 '디자인에 없는 요소'로
    올라온다 — 같은 것이 두 번 지적된다. 그래서 **값이 닮은 쪽**을 먼저 잇는다.
    (점수를 바꾸지 않는다. 점수가 같을 때만 순서를 가른다.)
    """
    fs, ds = f.get("style") or {}, d.get("style") or {}
    투명 = "rgba(0, 0, 0, 0)"
    점 = 0.0
    f칠, d칠 = fs.get("backgroundColor") or 투명, ds.get("backgroundColor") or 투명
    if f칠 == d칠:
        점 += 1.0
    elif (f칠 != 투명) == (d칠 != 투명):
        점 += 0.3                                  # 둘 다 칠이 있다(색만 다름) — 그래도 닮은 쪽
    if (fs.get("borderWidth") or 0) > 0 and (ds.get("borderWidth") or 0) > 0:
        점 += 0.5
    if abs((fs.get("borderRadius") or 0) - (ds.get("borderRadius") or 0)) <= 1:
        점 += 0.5
    return 점


def 짝맞추기(시안, 개발, 문턱=0.5):
    """{pairs, unmatchedF, unmatchedD, fig, devEls} 를 돌려준다."""
    FW = 시안["meta"]["artboardWidth"]
    FH = 시안["meta"].get("artboardHeight") or FW
    DW, DH, dx, dy = 내용옮김(개발)
    fig = 시안["elements"]
    # 화면 전체를 덮는 바깥 상자(body 래퍼)는 짝 대상에서 뺀다 — 무엇과도 어중간하게 붙는다.
    devEls = [e for e in 개발["elements"]
              if not (e["box"]["x"] + dx <= 1 and e["box"]["y"] + dy <= 1
                      and e["box"]["w"] >= DW - 2 and e["box"]["h"] >= DH - 2)]

    배율 = FW / DW
    옮김 = (dx, dy)
    # 시안과 개발의 세로 길이가 다를 때만 자를 맞춘다 — 같으면 예전 셈 그대로다.
    밀림들 = 세로밀림들(fig, devEls, 배율, dy) if abs(FH - DH * 배율) > 1 else []

    후보쌍 = []
    for fi, f in enumerate(fig):
        for di, d in enumerate(devEls):
            # 종류가 다르면 원칙적으로 안 짝지음(글자↔상자 억지 방지).
            # 단, 글자가 강하게 일치 '그리고' 크기도 비슷하면 교차 허용(뱃지·색버튼).
            fa = f["box"]["w"] * f["box"]["h"]
            da = d["box"]["w"] * d["box"]["h"]
            넓이비 = min(fa, da) / max(fa, da, 0.001)
            if f.get("isText") != d.get("isText"):
                if 글자닮음(f.get("text"), d.get("text")) < 0.8 or 넓이비 < 0.25:
                    continue
            elif not f.get("isText") and 넓이비 < 0.15:
                # 글자 없는 상자끼리는 덩치가 너무 다르면 잇지 않는다. 자리가 가깝다는 것만으로
                # 로고(135×30)가 시안의 커서 막대(1×16)에 붙는 일이 있었다 — 그러면 "로고를
                # 1px 로 줄여 주세요" 같은 헛지적이 나간다. 못 이으면 빠짐·더있음으로 남는다.
                continue
            점 = 짝점수(f, d, FW, FH, DW, DH, 배율, 밀림들, 옮김)
            후보쌍.append((점, 값닮음(f, d), fi, di))

    # 점수가 같으면(같은 자리에 겹쳐 둔 두 겹) 값이 닮은 쪽을 먼저 잇는다.
    후보쌍.sort(key=lambda x: (-round(x[0], 4), -x[1]))
    쓴시안, 쓴개발, 짝 = {}, {}, []
    for s, _닮음, fi, di in 후보쌍:
        if s < 문턱 or fi in 쓴시안 or di in 쓴개발:
            continue
        쓴시안[fi] = 1
        쓴개발[di] = 1
        짝.append({"fi": fi, "di": di, "s": round(s, 4)})

    return {
        "fig": fig,
        "devEls": devEls,
        "옮김": 옮김,
        "pairs": 짝,
        "unmatchedF": [i for i in range(len(fig)) if i not in 쓴시안],
        "unmatchedD": [i for i in range(len(devEls)) if i not in 쓴개발],
    }
