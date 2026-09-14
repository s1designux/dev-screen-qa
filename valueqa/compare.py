"""값 견주기 — 짝지어진 두 요소의 속성을 하나씩 대조한다.

(plugin-value-qa/ui.html 의 compareRows() 를 그대로 옮긴 것. 허용치를 바꾸면 저쪽도 함께 바꾼다.)

한 가지만 다르다: **안쪽여백(padding)은 지적 후보로 올리지 않는다.**
검수결과서 범위에서 여백은 퍼블리싱 소관으로 빠져 있기 때문이다(CLAUDE.md 8번).
값은 그대로 재서 '참고'로 남기고, 판정(합/불)에는 넣지 않는다.
"""

# 속성별 허용치 [넘어가는 선, 주의까지의 선]
허용 = {
    "box.x": (2, 6), "box.y": (2, 6), "box.w": (2, 6), "box.h": (2, 6),
    "fontSize": (0.5, 0.5), "fontWeight": (0, 0),
    "borderRadius": (1, 3), "borderWidth": (0.5, 1),
    "paddingTop": (1, 3), "paddingRight": (1, 3), "paddingBottom": (1, 3), "paddingLeft": (1, 3),
    "opacity": (0.01, 0.05),
}

이름 = {
    "box.x": "가로 위치", "box.y": "세로 위치", "box.w": "너비", "box.h": "높이",
    "color": "글자색", "backgroundColor": "배경색", "fontSize": "글자 크기",
    "fontWeight": "글자 굵기", "fontFamily": "글꼴",
    "borderRadius": "모서리 둥글기", "borderWidth": "테두리 두께", "borderColor": "테두리색",
    "paddingTop": "안쪽여백↑", "paddingRight": "안쪽여백→",
    "paddingBottom": "안쪽여백↓", "paddingLeft": "안쪽여백←",
}

여백들 = ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft")
나쁨순 = {"pass": 0, "warn": 1, "fail": 2}


def 숫자판정(k, a, b):
    좁, 넓 = 허용.get(k, (1, 3))
    차 = abs(a - b)
    return "pass" if 차 <= 좁 else ("warn" if 차 <= 넓 else "fail")


def 꺼내기(o, 길):
    값 = o
    for k in 길.split("."):
        if 값 is None:
            return None
        값 = 값.get(k)
    return 값


def 더나쁜(a, b):
    return a if 나쁨순[a] >= 나쁨순[b] else b


def 글꼴다듬기(f):
    return (f or "").lower().replace('"', "").replace("'", "").replace(" ", "").strip()


def 못읽은값(v):
    """시안에서 값을 하나로 읽지 못한 자리.

    한 덩이 글자 안에 글꼴이 섞여 있으면 피그마는 '혼합'이라고만 알려 준다.
    그것은 '다르다'가 아니라 '모른다'다 — 모르는 것을 다르다고 적어 보내면
    개발은 고칠 수가 없다(글꼴을 '혼합'으로 맞출 수는 없으니까). 그래서 그 줄은 건너뛴다.
    """
    return v is None or str(v).strip() in ("", "혼합", "mixed", "Mixed", "MIXED")


def 모서리줄(d, v):
    """모서리: 한 변을 완전히 감쌀 만큼 크면 '완전 둥금'(원·알약).
    표현값이 20px 이든 999px 이든 50% 이든 같게 본다."""
    dR, vR = d["style"]["borderRadius"], v["style"]["borderRadius"]
    d둥 = dR >= min(d["box"]["w"], d["box"]["h"]) / 2 - 1
    v둥 = vR >= min(v["box"]["w"], v["box"]["h"]) / 2 - 1
    if d둥 and v둥:
        return {"k": "borderRadius", "label": 이름["borderRadius"], "a": "완전 둥금", "b": "완전 둥금", "j": "pass"}
    if d둥 != v둥:
        return {"k": "borderRadius", "label": 이름["borderRadius"],
                "a": "완전 둥금" if d둥 else dR, "b": "완전 둥금" if v둥 else vR, "unit": "px", "j": "fail"}
    return {"k": "borderRadius", "label": 이름["borderRadius"], "a": dR, "b": vR, "unit": "px",
            "j": 숫자판정("borderRadius", dR, vR)}


def 값견주기(d, v, 밀림있음=False, 폭다름=False):
    """d=시안 요소, v=개발 요소. {rows, status, ...} 를 돌려준다."""
    글자냐 = bool(d.get("isText") or v.get("isText"))
    본문칸 = bool(d.get("contentZone") or v.get("contentZone"))
    줄들 = []

    자리키 = ["box.x", "box.y"] if 글자냐 else ["box.x", "box.y", "box.w", "box.h"]
    for k in 자리키:
        a, b = 꺼내기(d, k), 꺼내기(v, k)
        if a is None or b is None:
            continue
        j = 숫자판정(k, a, b)
        자리다 = k in ("box.x", "box.y")     # 위치는 디자인 목업·페이지 높이 차이로 어긋나기 쉬워 늘 '참고'
        밀림 = (k == "box.y" and 밀림있음 and j != "pass")
        참고 = (j != "pass" and not 밀림 and (자리다 or 폭다름))
        꼬리 = ("위치 참고" if (자리다 and not 폭다름) else "폭 다름") if 참고 else ""
        줄들.append({"k": k, "label": 이름[k], "a": a, "b": b, "unit": "px",
                     "j": j, "cascade": 밀림, "deferred": 참고, "dtag": 꼬리})

    if not 본문칸:
        ds, vs = d["style"], v["style"]
        if 글자냐:
            줄들.append({"k": "color", "label": 이름["color"], "a": ds["color"], "b": vs["color"],
                         "j": "pass" if ds["color"] == vs["color"] else "fail", "color": True})
            줄들.append({"k": "fontSize", "label": 이름["fontSize"], "a": ds["fontSize"], "b": vs["fontSize"],
                         "unit": "px", "j": 숫자판정("fontSize", ds["fontSize"], vs["fontSize"])})
            if ds.get("fontWeight") is not None and vs.get("fontWeight") is not None:
                줄들.append({"k": "fontWeight", "label": 이름["fontWeight"], "a": ds["fontWeight"], "b": vs["fontWeight"],
                             "j": 숫자판정("fontWeight", ds["fontWeight"], vs["fontWeight"])})
            if not 못읽은값(ds.get("fontFamily")):
                줄들.append({"k": "fontFamily", "label": 이름["fontFamily"], "a": ds["fontFamily"], "b": vs["fontFamily"],
                             "j": "pass" if 글꼴다듬기(ds["fontFamily"]) == 글꼴다듬기(vs["fontFamily"]) else "warn"})
        else:
            줄들.append({"k": "backgroundColor", "label": 이름["backgroundColor"],
                         "a": ds["backgroundColor"], "b": vs["backgroundColor"],
                         "j": "pass" if ds["backgroundColor"] == vs["backgroundColor"] else "fail", "color": True})
            줄들.append(모서리줄(d, v))
            줄들.append({"k": "borderWidth", "label": 이름["borderWidth"], "a": ds["borderWidth"], "b": vs["borderWidth"],
                         "unit": "px", "j": 숫자판정("borderWidth", ds["borderWidth"], vs["borderWidth"])})
            if ds["borderWidth"] > 0 and vs["borderWidth"] > 0:
                줄들.append({"k": "borderColor", "label": 이름["borderColor"], "a": ds["borderColor"], "b": vs["borderColor"],
                             "j": "pass" if ds["borderColor"] == vs["borderColor"] else "fail", "color": True})
            for p in 여백들:
                # 여백은 재기만 하고 판정에 넣지 않는다 — 퍼블리싱 소관(CLAUDE.md 8번).
                j = 숫자판정(p, ds[p], vs[p])
                줄들.append({"k": p, "label": 이름[p], "a": ds[p], "b": vs[p], "unit": "px",
                             "j": j, "cascade": False, "deferred": j != "pass", "dtag": "퍼블리싱 소관"})

    상태 = "pass"
    밀림표시 = 참고표시 = False
    for r in 줄들:
        if r.get("cascade"):
            밀림표시 = True
            continue
        if r.get("deferred"):
            참고표시 = True
            continue
        상태 = 더나쁜(상태, r["j"])
    return {"rows": 줄들, "status": 상태, "hasCascade": 밀림표시, "hasDeferred": 참고표시,
            "isText": 글자냐, "isContent": 본문칸}
