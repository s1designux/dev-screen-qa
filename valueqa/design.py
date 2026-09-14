"""시안 값 받아오기 — 플러그인이 보낸 '검수요소'를 값 대조가 읽는 모양으로 바꾼다.

피그마 토큰은 쓰지 않는다. 촬영 준비 플러그인(`capture-app/plugin-pick`)이 시안을 보낼 때
`검수요소`(= plugin-image-qa 의 collectDesign 과 같은 모양)를 함께 실어 보내므로 그것을 쓴다.

바뀌는 것은 '모양'뿐이다 — 값 자체는 손대지 않는다:
    검수요소: {kind, values:{fill, radius, ...}, 색은 #RRGGBB}
    →  측정모양: {isText, style:{backgroundColor, borderRadius, ...}, 색은 rgb(r, g, b)}

거르는 규칙은 plugin-value-qa/code.js 의 readDesign() 을 따른다:
아이콘 조각(작은 벡터)은 빼고, 글자도 칠도 테두리도 없는 껍데기는 빼고, 같은 자리에 겹친 레이어는 하나만.
"""
import re

굵기표 = {"thin": 100, "hairline": 100, "extralight": 200, "ultralight": 200, "light": 300,
         "regular": 400, "normal": 400, "book": 400, "medium": 500, "semibold": 600,
         "demibold": 600, "demi": 600, "bold": 700, "extrabold": 800, "ultrabold": 800,
         "heavy": 800, "black": 900}

벡터류 = {"VECTOR", "BOOLEAN_OPERATION", "LINE", "STAR", "POLYGON"}
기본글자색 = "rgb(0, 0, 0)"
기본상자색 = "rgb(31, 41, 55)"
투명 = "rgba(0, 0, 0, 0)"


def 색바꾸기(c, 기본=None):
    """#RRGGBB · rgba(...) · None → rgb(r, g, b) (개발 쪽 브라우저 값과 같은 표기)."""
    if not c:
        return 기본
    c = str(c).strip()
    m = re.match(r"^#([0-9a-fA-F]{6})$", c)
    if m:
        v = m.group(1)
        return "rgb(%d, %d, %d)" % (int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16))
    m = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", c)
    if m:
        return "rgb(%s, %s, %s)" % (m.group(1), m.group(2), m.group(3))
    return 기본


def 굵기(값, 스타일):
    if isinstance(값, (int, float)):
        return round(값)
    s = (스타일 or "").lower().replace(" ", "").replace("italic", "").replace("oblique", "")
    return 굵기표.get(s)


def _줄높이(v):
    return v if isinstance(v, (int, float)) else 0


def _모아쓴글자(요소들):
    """상자의 대표 글자 — 그 안에 든 글자 요소들을 합친다(짝맞춤 힌트용)."""
    자식 = {}
    for e in 요소들:
        자식.setdefault(e.get("parentId"), []).append(e)

    def 훑기(id_):
        모음 = []
        for c in 자식.get(id_, []):
            if c.get("kind") == "text":
                모음.append(c.get("text") or "")
            모음.extend(훑기(c.get("id")))
        return 모음

    return {e["id"]: " ".join(t for t in 훑기(e["id"]) if t).strip()[:50] for e in 요소들}


def 시안값으로(검수요소, 프레임=None):
    """검수요소 목록 → {meta, elements} (값 대조가 읽는 모양)."""
    프레임 = 프레임 or {}
    W = float(프레임.get("width") or 프레임.get("폭") or 0)
    H = float(프레임.get("height") or 프레임.get("높이") or 0)
    if not W:
        W = max((e["box"]["x"] + e["box"]["w"] for e in 검수요소), default=1)
    if not H:
        H = max((e["box"]["y"] + e["box"]["h"] for e in 검수요소), default=1)

    속글자 = _모아쓴글자(검수요소)
    날것 = []
    for e in 검수요소:
        v = e.get("values") or {}
        글자냐 = e.get("kind") == "text"
        bb = e["box"]

        if 글자냐:
            style = {
                "color": 색바꾸기(v.get("color"), 기본글자색), "backgroundColor": 투명,
                "fontSize": v.get("fontSize") or 0,
                "fontWeight": 굵기(v.get("fontWeight"), v.get("fontStyle")),
                "fontFamily": v.get("fontFamily") or "", "lineHeight": _줄높이(v.get("lineHeight")),
                "borderRadius": 0, "borderWidth": 0, "borderColor": 기본글자색,
                "paddingTop": 0, "paddingRight": 0, "paddingBottom": 0, "paddingLeft": 0,
                "textAlign": (v.get("textAlign") or "LEFT").lower().replace("left", "start").replace("right", "end"),
                "opacity": v.get("opacity") if isinstance(v.get("opacity"), (int, float)) else 1,
            }
            글 = (e.get("text") or "")[:50]
        else:
            칠 = 색바꾸기(v.get("fill"))
            선 = 색바꾸기(v.get("stroke"))
            선굵기 = v.get("strokeWidth") or 0
            # 아이콘 조각(작은 벡터)은 뺀다 — 개발화면은 아이콘을 그림 하나로 그려서 값 비교 자체가 안 된다.
            if e.get("type") in 벡터류 and max(bb["w"], bb["h"]) < 32:
                continue
            # 글자도 칠도 보이는 테두리도 없는 껍데기는 뺀다.
            if not 칠 and not (선 and 선굵기 > 0):
                continue
            둥글기 = v.get("radius")
            if e.get("type") == "ELLIPSE" and not 둥글기:
                둥글기 = min(bb["w"], bb["h"]) / 2
            style = {
                "color": 기본상자색, "backgroundColor": 칠 or 투명,
                "fontSize": 16, "fontWeight": 400, "fontFamily": "", "lineHeight": 0,
                "borderRadius": round(둥글기 or 0, 1), "borderWidth": round(선굵기, 1),
                "borderColor": 선 or 기본상자색,
                "paddingTop": 0, "paddingRight": 0, "paddingBottom": 0, "paddingLeft": 0,
                "textAlign": "start",
                "opacity": v.get("opacity") if isinstance(v.get("opacity"), (int, float)) else 1,
            }
            글 = 속글자.get(e["id"], "")

        이름 = e.get("name") or e.get("type") or ""
        요소 = {
            "id": e.get("id"), "name": 이름, "role": e.get("type"),
            "isText": 글자냐, "text": 글, "box": dict(bb), "style": style,
            "contentZone": 이름.startswith("content/"),
        }
        # 피그마 컴포넌트 인스턴스면 정체(세트 이름·변형 속성)를 함께 싣는다 — 규정 대조가 짝 건너 개발 요소에 옮겨 붙인다.
        if e.get("component"):
            c = e["component"]
            요소["컴포넌트"] = {"이름": c.get("name") or "", "세트": c.get("set") or "", "속성": c.get("props") or {}}
        날것.append(요소)

    # 거의 같은 자리·같은 종류로 겹친 레이어는 하나만 (컴포넌트 껍데기 + 배경 중복 제거)
    걸러낸 = []
    for el in 날것:
        겹침 = False
        for o in 걸러낸:
            if (o["isText"] == el["isText"]
                    and abs(o["box"]["x"] - el["box"]["x"]) <= 1 and abs(o["box"]["y"] - el["box"]["y"]) <= 1
                    and abs(o["box"]["w"] - el["box"]["w"]) <= 1 and abs(o["box"]["h"] - el["box"]["h"]) <= 1):
                겹침 = True
                break
        if not 겹침:
            걸러낸.append(el)

    return {
        "meta": {"label": "design", "source": "figma-plugin",
                 "frameName": 프레임.get("name") or 프레임.get("이름") or "",
                 "rootId": 프레임.get("id"),
                 "artboardWidth": round(W, 1), "artboardHeight": round(H, 1),
                 "toolVersion": "valueqa-design-1.1"},
        "elements": 걸러낸,
    }
