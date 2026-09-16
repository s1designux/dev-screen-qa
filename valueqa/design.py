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
    m = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?", c)
    if m:
        # 투명도 0 으로 칠한 것은 '칠이 없는 것'이다. 그대로 색으로 읽으면 안 보이는 칠이 값이 되어 헛지적이 된다.
        if m.group(4) is not None and float(m.group(4)) <= 0.01:
            return 기본
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


def _아이콘속(요소들):
    """아이콘 부품(이름에 'icon' 마디가 든 것)과 그 안에 든 것 전부의 id 모음.

    개발화면은 아이콘을 그림 한 장으로 그린다. 그래서 시안 아이콘의 속(벡터·원·사각형)을
    개발 쪽 값과 견줄 수가 없다 — 속까지 통째로 뺀다.
    """
    아이콘이름 = re.compile(r"(^|[/\s_-])icons?([/\s_-]|$)", re.I)
    뿌리 = {e["id"] for e in 요소들
            if e.get("kind") == "icon" or 아이콘이름.search(e.get("name") or "")}
    if not 뿌리:
        return 뿌리
    자식 = {}
    for e in 요소들:
        자식.setdefault(e.get("parentId"), []).append(e["id"])
    속 = set(뿌리)
    쌓기 = list(뿌리)
    while 쌓기:
        for c in 자식.get(쌓기.pop(), []):
            if c not in 속:
                속.add(c)
                쌓기.append(c)
    return 속


def _아이콘틀(요소들):
    """아이콘 그림을 이루는 껍데기 도형의 id 모음.

    피그마 아이콘 부품은 벡터 둘레에 같은 크기의 사각형·원('Bounding box', 'Oval')을 함께 둔다.
    개발화면은 아이콘을 그림 한 장으로 그리므로 그 껍데기에 짝지을 것이 없다 —
    값 대조에 올리면 "눈 아이콘 단추를 16px 로 줄이고 회색으로 칠하라" 같은 헛지적이 나간다.
    아이콘 크기(한 변 48px 이하)이면서 **아이콘이 그 안을 꽉 채우고 있으면** 껍데기로 본다.

    '꽉 채운다'를 따지는 까닭 (river 2026-09-16): 그냥 '품고 있으면' 으로 두었더니
    체크상자 몸통(18×18 파란 사각형) 안의 체크 표시(10×7.5)까지 껍데기로 보아 시안에서 통째로 빠졌다.
    그러면 개발 화면의 체크상자가 짝지을 것을 잃고 '디자인에 없는 요소' 로 줄줄이 올라온다.
    껍데기는 아이콘과 크기가 같은 것이지, 아이콘을 담는 그릇이 아니다.
    """
    아이콘들 = [o for o in 요소들 if o.get("kind") == "icon"]
    틀 = set()
    for e in 요소들:
        if e.get("kind") != "shape":
            continue
        b = e["box"]
        if max(b["w"], b["h"]) > 48:          # 큰 카드가 아이콘을 품은 것까지 빼지는 않는다
            continue
        for o in 아이콘들:
            ob = o["box"]
            감쌈 = (b["x"] <= ob["x"] + 1 and b["y"] <= ob["y"] + 1
                   and b["x"] + b["w"] >= ob["x"] + ob["w"] - 1
                   and b["y"] + b["h"] >= ob["y"] + ob["h"] - 1)
            꽉참 = ob["w"] >= b["w"] * 0.8 and ob["h"] >= b["h"] * 0.8
            if 감쌈 and 꽉참:
                틀.add(e["id"])
                break
    return 틀


# ── 시안 그림에서 '아무것도 안 그려지는 상자' 가려내기 ────────────────────
# 왜 (river 2026-09-16): 디자이너가 간격을 띄우려고 오토레이아웃 대신 깔아 둔 껍데기 프레임은
# 화면에서는 안 보인다(투명하거나, 흰 바탕 위의 흰 칠이거나). 레이어 값만 보면 흰 카드와 구분이 안 된다 —
# 그림자만으로 보이는 진짜 카드가 있기 때문이다. 그래서 **시안 그림을 직접 보고** 정한다:
# 상자 둘레의 안쪽·바깥쪽 픽셀이 똑같으면 그 상자는 화면에 아무 자국도 남기지 않은 것이다.
# 안에 든 것(글자·아이콘)은 따로 견주므로 껍데기만 빠진다.
문턱 = 8          # 0~255 · 이보다 작은 색 차이는 '자국이 없다'로 본다 (가장 흐린 1px 구분선도 20 넘게 나온다)


def 안그려진것(그림길, 요소들, 틀폭):
    """시안 그림에 아무 자국도 남기지 않는 상자들의 id 모음. 그림이 없거나 못 읽으면 빈 모음."""
    try:
        from PIL import Image
    except Exception:
        return set()                                # 그림 도구가 없으면 이 규칙은 조용히 쉰다
    try:
        im = Image.open(그림길).convert("RGB")
    except Exception:
        return set()
    W, H = im.size
    if not 틀폭 or not W:
        return set()
    배 = W / float(틀폭)
    px = im.load()
    두께 = max(3, int(round(3 * 배)))                # 경계를 가로지르며 훑을 폭(양쪽)

    def 점(x, y):
        return px[min(max(int(round(x)), 0), W - 1), min(max(int(round(y)), 0), H - 1)]

    def 한변(고정, 시작값, 끝값, 세로냐):
        """그 변을 따라 11군데에서 경계를 가로질러 훑고, 색이 튄 폭의 **가운뎃값**을 돌려준다.

        가운뎃값을 쓰는 까닭: 글자 한 줄이 변을 스쳐 지나가는 것만으로 '그려졌다'가 되면 안 된다.
        테두리선·칠 경계는 변 **전체**에 고르게 나타나므로 가운뎃값이 높다.
        """
        벌 = []
        for i in range(1, 12):
            t = i / 12.0
            가운데 = 시작값 + (끝값 - 시작값) * t
            lo = [255, 255, 255]
            hi = [0, 0, 0]
            for k in range(-두께, 두께 + 1):
                c = 점(가운데, 고정 + k) if 세로냐 else 점(고정 + k, 가운데)
                for j in range(3):
                    lo[j] = min(lo[j], c[j])
                    hi[j] = max(hi[j], c[j])
            벌.append(max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]))
        벌.sort()
        return 벌[len(벌) // 2]

    out = set()
    for e in 요소들:
        if e.get("kind") != "shape":
            continue                                # 글자·아이콘·그림은 이 규칙이 보지 않는다
        b = e["box"]
        if b["w"] < 4 or b["h"] < 4:
            continue
        x0, y0 = b["x"] * 배, b["y"] * 배
        x1, y1 = (b["x"] + b["w"]) * 배, (b["y"] + b["h"]) * 배
        변들 = ((y0, x0, x1, True), (y1, x0, x1, True), (x0, y0, y1, False), (x1, y0, y1, False))
        잴수있는 = 자국있는 = 0
        for 고정, 가, 나, 세로냐 in 변들:
            바깥 = 고정 < 1 or (고정 > H - 2 if 세로냐 else 고정 > W - 2)
            if 바깥:
                continue                            # 화면 밖으로 걸친 변은 잴 수가 없다 — 세지 않는다
            잴수있는 += 1
            if 한변(고정, 가, 나, 세로냐) >= 문턱:
                자국있는 += 1
        if not 잴수있는:
            continue
        if 자국있는 >= max(2, 잴수있는 - 1):
            continue                                # 변 대부분에 자국이 남았다 = 실제로 그려진 상자
        out.add(e["id"])
    return out


def 시안값으로(검수요소, 프레임=None, 그림=None):
    """검수요소 목록 → {meta, elements} (값 대조가 읽는 모양)."""
    프레임 = 프레임 or {}
    W = float(프레임.get("width") or 프레임.get("폭") or 0)
    H = float(프레임.get("height") or 프레임.get("높이") or 0)
    if not W:
        W = max((e["box"]["x"] + e["box"]["w"] for e in 검수요소), default=1)
    if not H:
        H = max((e["box"]["y"] + e["box"]["h"] for e in 검수요소), default=1)

    속글자 = _모아쓴글자(검수요소)
    아이콘틀 = _아이콘틀(검수요소) | _아이콘속(검수요소)
    안보임 = 안그려진것(그림, 검수요소, W) if 그림 else set()
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
            # 피그마는 테두리를 아예 안 준 노드에도 strokeWidth 1 을 적어 둔다.
            # 그대로 믿으면 '없는 테두리'가 생겨 헛지적이 된다 — 선 색이 있을 때만 두께를 인정한다.
            선굵기 = (v.get("strokeWidth") or 0) if 선 else 0
            # 아이콘은 뺀다 — 개발화면은 아이콘을 그림 한 장(img·svg·배경그림)으로 그린다.
            # 그래서 시안의 벡터 칠(#757575 같은 것)을 개발의 '배경색'과 견주면 늘 다르게 나온다(헛지적).
            # 작은 벡터뿐 아니라 collectDesign 이 아이콘으로 표시한 것 전부(로고 포함)를 뺀다.
            if e.get("kind") == "icon" or (e.get("type") in 벡터류 and max(bb["w"], bb["h"]) < 32):
                continue
            # 아이콘을 감싸려고 깔아 둔 껍데기 사각형(피그마 아이콘 부품의 'Bounding box')도 뺀다.
            if e["id"] in 아이콘틀:
                continue
            # 글자도 칠도 보이는 테두리도 없는 껍데기는 뺀다.
            if not 칠 and not (선 and 선굵기 > 0):
                continue
            # 레이어 투명도를 0 으로 내려 둔 것도 화면에 없는 것이다.
            if v.get("opacity") == 0:
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
        # 시안 그림에 아무 자국도 남기지 않는 껍데기(간격용 프레임 등)는 이름표만 붙여 둔다.
        # 목록에서 빼지는 않는다 — 짝맞춤과 '큰 상자 안은 덮어 준다'는 셈이 함께 흔들리기 때문(실측).
        if e["id"] in 안보임:
            요소["안보임"] = True
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
