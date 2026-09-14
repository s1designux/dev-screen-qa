"""동작 사양 점검 — 시안이 '눌러 보지 않으면 알 수 없는 것'을 제대로 그려 두었는지 본다.

색·크기·토큰 같은 **눈에 보이는 기준은 보지 않는다**(디자인 쪽 GUI 검수기 몫, river 확정 2026-09-14).
여기서 보는 것은 그 시안을 촬영 기준으로 삼았을 때 **기준 자체가 틀어지는** 것들이다:

  버튼꺼짐 — 칸을 다 채워 놓고도 단추를 꺼진 색으로 그려 두었다.
             PC 웹은 칸이 차면 단추가 켜지므로, 이대로 찍으면 개발이 맞는데도 다르다고 나온다.
             짚을 때는 '무엇이 잘못됐나'가 아니라 **제대로면 어떤 모습이어야 하나**를 적는다(river 2026-09-14).
  흐름번호 — 다른 프레임엔 붙은 흐름 번호가 이 프레임에만 없다(섞여 있을 때만).

무엇을 볼지는 유형마다 다르다 — `lib/매체.py` 의 `시안점검` 값을 본다(앱은 자판이 단추를 가려 '버튼꺼짐'을 보지 않는다).
갈림길 조건(몇 회부터인지 등)은 보지 않는다 — 촬영 대본이 화면 이름에서 이미 읽어 낸다(river 확정 2026-09-14).

의견일 뿐이다. 고칠지는 디자이너가 정하고, 이 점검 때문에 촬영을 막지 않는다(CLAUDE.md 2번-2).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import 매체

누름말 = ["누르면", "누른", "클릭", "탭 시", "탭시"]          # 누름을 전제한 말
버튼활성 = re.compile(r"(버튼|btn|button).*활성", re.I)        # '로그인 버튼 활성화' 류
다음말 = ["성공", "완료", "홈", "메인", "다음", "이동", "결과"]
흐름번호 = re.compile(r"\b[A-Z]{2,}/[A-Z0-9_-]{2,}/[0-9a-z]{2,}\b")


def _속글자(화면):
    return " ".join((e.get("글자") or "") for e in (화면.get("속") or []))


def _끝마디(이름):
    조각 = [t.strip() for t in (이름 or "").split("_") if t.strip()]
    return 조각[-1] if 조각 else ""


def _무리(이름):
    """'웹_로그인 화면_비밀번호 숨김' → '로그인 화면' (server._무리 와 같은 규칙)."""
    조각 = [t.strip() for t in (이름 or "").split("_") if t.strip()]
    if not 조각:
        return ""
    앞머리 = {"웹", "앱", "web", "app", "aos", "ios", "pc", "mo", "mobile"}
    if len(조각) >= 2 and 조각[0].lower() in 앞머리:
        조각 = 조각[1:]
    return 조각[0] if 조각 else ""



def _갈곳안적힘(화면, 무리별):
    끝 = _끝마디(화면.get("이름", ""))
    if not (버튼활성.search(끝) or any(w in 끝 for w in 누름말)):
        return None
    이웃 = 무리별.get(_무리(화면.get("이름", "")), [])
    if any(any(w in (o.get("이름") or "") for w in 다음말) for o in 이웃):
        return None
    return "누르면 나올 화면이 받은 시안에 없습니다"


# ── 시안 안에서 상태가 서로 안 맞는 곳 ──────────────────────────────
# 두 칸을 다 채웠으면 버튼이 켜져 있어야 하는데 시안은 꺼진 채로 그려져 있다 — 이런 것.
# 촬영기가 이 시안을 기준으로 삼으면 '개발이 틀렸다'가 아니라 '기준이 틀렸다'가 된다.
안내문 = re.compile(r"(해\s*주세요|하세요|입력|선택|검색|을 넣|를 넣)")
입력이름 = re.compile(r"(INPUT|TEXT-?FIELD|FIELD|입력)", re.I)
버튼이름 = re.compile(r"(BTN|BUTTON|버튼)", re.I)


def _상자안(밖, 안):
    return (안["x"] >= 밖["x"] - 1 and 안["y"] >= 밖["y"] - 1
            and 안["x"] + 안["w"] <= 밖["x"] + 밖["w"] + 1
            and 안["y"] + 안["h"] <= 밖["y"] + 밖["h"] + 1)


def _칠(e):
    return ((e.get("values") or {}).get("fill") or "").upper()


def _채도(색):
    try:
        r, g, b = (int(색[i:i + 2], 16) for i in (1, 3, 5))
    except Exception:
        return 0
    return max(r, g, b) - min(r, g, b)


def _요소읽기(화면):
    길 = 화면.get("검수요소파일") or ""
    if not 길:
        return []
    try:
        with open(길, encoding="utf-8") as f:
            return (json.load(f) or {}).get("요소") or []
    except OSError:
        return []


칸이름빼기 = re.compile(r"^\s*(.+?)\s*(?:을|를)?\s*(?:입력|선택|적어|넣어)")


def _칸이름(안내글):
    """'아이디를 입력해 주세요.' → '아이디'."""
    m = 칸이름빼기.match(안내글 or "")
    return (m.group(1) if m else (안내글 or "")).strip(" .!?")


def _입력과버튼(요소):
    """(입력칸별 채워짐 여부, 주 버튼의 칠, 버튼 글자, 칸·버튼 상자들)."""
    글자 = [e for e in 요소 if e.get("kind") == "text" and (e.get("text") or "").strip()]
    입력, 버튼, 버튼글, 상자 = [], None, "", []
    for e in 요소:
        이름 = e.get("name") or ""
        if e.get("kind") == "text":
            continue
        if 입력이름.search(이름):
            속 = [t for t in 글자 if _상자안(e["box"], t["box"])]
            if not 속:
                continue
            안내 = next((t["text"] for t in 속 if 안내문.search(t["text"])), "")
            입력.append({"y": e["box"]["y"], "참": not 안내, "칸이름": _칸이름(안내)})
            상자.append(e["box"])
        elif 버튼이름.search(이름) and _칠(e) and 버튼 is None:
            버튼 = _칠(e)
            버튼글 = next((t["text"] for t in 글자 if _상자안(e["box"], t["box"])), "")
            상자.append(e["box"])
    입력.sort(key=lambda x: x["y"])
    return 입력, 버튼, 버튼글, 상자


def _잘라보기(상자들, 화면, 비 = 360 / 240):
    """칸·버튼이 들어간 자리만 확대해 보여 주려고, 그 부분을 % 로 잘라 낸다.

    시안 한 장을 통째로 줄여 놓으면 단추가 점만 해져 무엇이 문제인지 안 보인다.
    """
    if not 상자들:
        return None
    W = float(화면.get("폭") or 0) or max(b["x"] + b["w"] for b in 상자들)
    H = float(화면.get("높이") or 0) or max(b["y"] + b["h"] for b in 상자들)
    x0 = min(b["x"] for b in 상자들)
    y0 = min(b["y"] for b in 상자들)
    x1 = max(b["x"] + b["w"] for b in 상자들)
    y1 = max(b["y"] + b["h"] for b in 상자들)
    w, h = (x1 - x0) * 1.15, (y1 - y0) * 1.15          # 둘레를 조금 넉넉히
    if w / h < 비:                                     # 보여 줄 칸과 같은 가로세로비로 맞춘다
        w = h * 비
    else:
        h = w / 비
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    x, y = cx - w / 2, cy - h / 2
    x = max(0, min(x, W - w)) if W > w else 0
    y = max(0, min(y, H - h)) if H > h else 0
    w, h = min(w, W), min(h, H)
    return {"x": round(x / W * 100, 2), "y": round(y / H * 100, 2),
            "w": round(w / W * 100, 2), "h": round(h / H * 100, 2)}


def _버튼꺼짐(고른화면, 자리):
    """같은 화면 묶음 안에서 버튼 색이 두 가지면, 켜진 색을 배워 어긋난 곳을 찾는다."""
    잰것 = {}
    for f in 고른화면:
        잰것[id(f)] = _입력과버튼(_요소읽기(f))

    무리별 = {}
    for f in 고른화면:
        무리별.setdefault(_무리(f.get("이름", "")), []).append(f)

    나온것 = []
    for 무리, 식구 in 무리별.items():
        색 = {잰것[id(f)][1] for f in 식구 if 잰것[id(f)][1]}
        if len(색) < 2:
            continue                                   # 켜짐·꺼짐 두 모습이 다 있어야 배울 수 있다
        # 또렷한(채도 높은) 색을 켜진 색으로 본다. 회색끼리라 가릴 수 없으면 이름으로 가린다.
        켜짐 = max(색, key=_채도)
        if _채도(켜짐) == 0:
            켜짐 = next((잰것[id(f)][1] for f in 식구
                       if 버튼활성.search(f.get("이름") or "") and 잰것[id(f)][1]), 켜짐)
        # 칸 이름은 안내 글자가 남아 있는 화면(대개 기본 화면)에서 가져온다 — 채워진 화면엔 값만 있다.
        칸이름 = []
        for f in 식구:
            이름들 = [i["칸이름"] for i in 잰것[id(f)][0] if i["칸이름"]]
            if len(이름들) > len(칸이름):
                칸이름 = 이름들
        for f in 식구:
            입력, 버튼, 버튼글, 상자 = 잰것[id(f)]
            if not 버튼 or 버튼 == 켜짐:
                continue
            if len(입력) >= 2 and all(i["참"] for i in 입력):
                # 갈래 이름이 곧 '제대로면 어떤 모습이어야 하나' 다 — 무슨 칸, 어떤 버튼인지 이름을 밝힌다.
                칸말 = "·".join(칸이름) if 칸이름 else "모든 칸"
                단추말 = "'%s' 버튼" % 버튼글 if 버튼글 else "버튼"
                나온것.append({"갈래": "%s 모두 입력 시 %s 활성화 필요" % (칸말, 단추말),
                            "화면": f.get("이름", ""), "자리": 자리[id(f)],
                            "잘라": _잘라보기(상자, f),
                            "말": "지금 시안은 %s이 꺼진 색(%s)으로 그려져 있습니다 — 켜진 색은 %s 입니다"
                                 % (단추말, 버튼, 켜짐)})
    return 나온것


def 점검(고른화면, 유형=None):
    """[{갈래, 화면, 말}] — 받은 시안만 보고 찾은 의견. 무엇을 볼지는 유형표가 정한다."""
    고른화면 = 고른화면 or []
    볼것 = set(매체.값(유형, "시안점검", ["버튼꺼짐", "갈곳"]) or [])
    자리 = {id(f): i for i, f in enumerate(고른화면, 1)}   # 썸네일 주소(/받은그림/001.png)에 쓴다
    무리별 = {}
    for f in 고른화면:
        무리별.setdefault(_무리(f.get("이름", "")), []).append(f)

    번호있음 = [f for f in 고른화면 if 흐름번호.search(f.get("이름") or "")]
    번호섞임 = 0 < len(번호있음) < len(고른화면)   # 전부 없으면 이 프로젝트는 안 쓰는 것 — 잠자코 있는다

    나온것 = _버튼꺼짐(고른화면, 자리) if "버튼꺼짐" in 볼것 else []
    for f in 고른화면:
        이름 = f.get("이름", "")
        말 = _갈곳안적힘(f, 무리별) if "갈곳" in 볼것 else None
        if 말:
            나온것.append({"갈래": "누른 뒤 갈 곳이 안 적힘", "화면": 이름,
                        "자리": 자리[id(f)], "말": 말})
        if 번호섞임 and not 흐름번호.search(이름):
            나온것.append({"갈래": "흐름 번호가 없음", "화면": 이름, "자리": 자리[id(f)],
                        "말": "다른 프레임엔 붙은 흐름 번호가 이 프레임에만 없습니다"})
    return 나온것


def 갈래별(나온것):
    """[(갈래, [항목…])] — 나온 차례 그대로. 갈래 이름이 곧 '이래야 한다'는 말이다."""
    묶음 = {}
    for it in 나온것:
        묶음.setdefault(it["갈래"], []).append(it)
    return list(묶음.items())
