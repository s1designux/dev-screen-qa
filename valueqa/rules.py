"""규정 대조 — 회사 토큰·컴포넌트 규정을 지켰는지. 세 가지 판정.

  1. 토큰 밖의 값인가   — 개발 화면의 색·글자크기·굵기·모서리·테두리가 토큰 목록 안에 있나.
                         없으면 후보로 올리고 **가장 가까운 토큰을 함께 제안**한다.
  2. 컴포넌트 규격       — 그 요소가 어느 컴포넌트인지 알아본 뒤(component_id.py) 정본 규격(높이·최소 너비·모서리·
                         허용 변형)과 맞는지 본다. 폐지된 변형(danger·ghost)도 후보.
  3. 시안 자체가 규정 밖 — 시안 값이 토큰 밖이면 개발이 아니라 **디자이너에게** 간다. 따로 모은다.

시안과 같아도 토큰 밖 값이면 후보다. 여기서 나오는 것은 모두 **후보**다(CLAUDE.md 2번-2) — 확정은 사람이 한다.

**규정은 정확히 같아야 한다** (river 2026-09-14): 1~2 차이라고 넘기면 그건 규정이 아니다. 허용차를 두지 않는다.
"""
from .component_id import 정체알아보기, 축값으로변형, 축값에서
from .registry import 헥스로

투명 = ("rgba(0, 0, 0, 0)", "transparent", "")

CSS이름 = {"color": "color", "backgroundColor": "background-color", "borderColor": "border-color",
         "fontSize": "font-size", "fontWeight": "font-weight", "borderRadius": "border-radius",
         "borderWidth": "border-width", "box.h": "height", "box.w": "min-width"}
속성말 = {"color": "글자색", "backgroundColor": "배경색", "borderColor": "테두리색", "fontSize": "글자 크기",
        "fontWeight": "글자 굵기", "borderRadius": "모서리 둥글기", "borderWidth": "테두리 두께",
        "box.h": "높이", "box.w": "너비"}
크기갈래 = {"fontSize": "font-size", "borderRadius": "radius", "borderWidth": "border-width", "box.h": "sizing"}


# ---------------------------------------------------------------- 가까운 토큰

def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def 가까운색(h, 토큰):
    """색 → (토큰 이름, 토큰 값, 채널 최대 차이). 정확히 있으면 차이 0."""
    if h in 토큰["색"]:
        return 토큰["색"][h][0], h, 0
    r, g, b = _rgb(h)
    가장 = None
    for 값, 이름들 in 토큰["색"].items():
        # 제안은 밝은 테마 토큰에서 고른다 — 어두운 테마 기초색(-dark-)을 밝은 화면에 권하면 엉뚱하다.
        if all("-dark-" in n for n in 이름들):
            continue
        r2, g2, b2 = _rgb(값)
        거리 = (r - r2) ** 2 + (g - g2) ** 2 + (b - b2) ** 2
        if 가장 is None or 거리 < 가장[0]:
            가장 = (거리, 이름들[0], 값, max(abs(r - r2), abs(g - g2), abs(b - b2)))
    return (가장[1], 가장[2], 가장[3]) if 가장 else (None, None, None)


def 가까운크기(px, 갈래, 토큰):
    표 = 토큰["크기"].get(갈래) or {}
    if not 표:
        return None, None, None
    if px in 표:
        return 표[px], px, 0
    값 = min(표, key=lambda v: abs(v - px))
    return 표[값], 값, abs(값 - px)


def 가까운굵기(w, 토큰):
    표 = 토큰["굵기"]
    if not 표:
        return None, None, None
    if w in 표:
        return 표[w], w, 0
    값 = min(표, key=lambda v: abs(v - w))
    return 표[값], 값, abs(값 - w)


# ---------------------------------------------------------------- 1·3. 토큰 밖의 값

def _요소의값들(el):
    """요소에서 규정을 볼 값만 뽑는다. (여백·위치는 보지 않는다 — 퍼블리싱 소관·참고)"""
    st = el["style"]
    out = []
    if el.get("isText"):
        if st.get("color") not in 투명:
            out.append(("color", st["color"]))
        if st.get("fontSize"):
            out.append(("fontSize", st["fontSize"]))
        if isinstance(st.get("fontWeight"), (int, float)) and st["fontWeight"]:
            out.append(("fontWeight", st["fontWeight"]))
    else:
        if st.get("backgroundColor") not in 투명:
            out.append(("backgroundColor", st["backgroundColor"]))
        if (st.get("borderWidth") or 0) > 0:
            out.append(("borderWidth", st["borderWidth"]))
            if st.get("borderColor") not in 투명:
                out.append(("borderColor", st["borderColor"]))
        r = st.get("borderRadius") or 0
        if r > 0:
            완전둥금 = r >= min(el["box"]["w"], el["box"]["h"]) / 2 - 1
            out.append(("borderRadius", 9999.0 if 완전둥금 else r))
    return out


def 짝표만들기(결과):
    """개발 요소 id → 짝지어진 시안 요소. 토큰을 고를 때 '시안이 뭐라고 했는지' 를 보려고 쓴다."""
    표 = {}
    for p in 결과.get("_짝") or []:
        개발 = p.get("개발") or {}
        if 개발.get("id"):
            표[개발["id"]] = p.get("시안") or {}
    return 표


def _시안이고른토큰(el, k, 짝표, 토큰):
    """그 자리에 시안이 쓴 색이 **이미 토큰**이면 그것을 답으로 삼는다.

    개발값에서 가장 가까운 토큰을 기계적으로 고르면, 시안이 쓴 토큰과 다른 토큰을 권할 수 있다
    (#DCDCDC 는 #D9D9D9 와 #DFDEDE 에서 똑같이 3만큼 떨어져 있다).
    그러면 한 문서 안에서 시안 대조와 규정 대조가 서로 다른 값을 가리켜 개발이 헷갈린다.
    """
    if not 짝표 or k not in ("color", "backgroundColor", "borderColor"):
        return None
    f = 짝표.get(el.get("id"))
    if not f:
        return None
    시안h = 헥스로((f.get("style") or {}).get(k))
    if not 시안h or 시안h not in 토큰["색"]:
        return None
    return 토큰["색"][시안h][0], 시안h


def 토큰밖(요소들, 토큰, 허용차=0, 짝표=None):
    """요소 목록에서 토큰 밖 값을 찾는다. 같은 (속성, 값)은 여러 요소라도 후보 하나에 모은다."""
    모음 = {}
    for el in 요소들:
        for k, v in _요소의값들(el):
            if k in ("color", "backgroundColor", "borderColor"):
                h = 헥스로(v)
                if not h:                      # 반투명(덧씌우기)은 예외 EX03 — 넘긴다
                    continue
                이름, 값, 차이 = 가까운색(h, 토큰)
                시안것 = _시안이고른토큰(el, k, 짝표, 토큰)
                if 시안것 and 차이:
                    이름, 값 = 시안것
                    r1, g1, b1 = _rgb(h)
                    r2, g2, b2 = _rgb(값)
                    차이 = max(abs(r1 - r2), abs(g1 - g2), abs(b1 - b2))
                지금 = h
            elif k == "fontWeight":
                이름, 값, 차이 = 가까운굵기(int(v), 토큰)
                지금 = int(v)
            else:
                이름, 값, 차이 = 가까운크기(float(v), 크기갈래[k], 토큰)
                지금 = float(v)
            if 이름 is None or 차이 is None or 차이 <= 허용차:
                continue
            열쇠 = (k, 지금)
            칸 = 모음.setdefault(열쇠, {
                "갈래": "토큰밖", "속성": k, "css": CSS이름[k], "속성말": 속성말[k],
                "지금": 지금, "가까운토큰": {"이름": 이름, "값": 값, "차이": 차이},
                "곳": [], "신뢰도": 0.0,
            })
            칸["곳"].append(el)
    후보 = []
    for c in 모음.values():
        # 토큰 밖이면 차이가 1이든 100이든 똑같이 규정 위반이다 — 차이 크기로 신뢰도를 낮추지 않는다(river 2026-09-14).
        # 신뢰도는 '값을 잰 것' 자체의 확실함이라 높게 둔다.
        c["신뢰도"] = 0.9
        후보.append(c)
    후보.sort(key=lambda c: (-len(c["곳"]), c["css"], str(c["지금"])))
    return 후보


# ---------------------------------------------------------------- 2. 컴포넌트 규격

def _색토큰값(이름, 토큰):
    return 헥스로(토큰["이름값"].get(이름, "")) if 이름 else None


def 규격대조(개발요소, 정체, 토큰, 허용차=0, 플랫폼="PC"):
    """알아본 요소 하나를 정본 규격에 대 본다. 어긋난 줄 목록을 돌려준다."""
    규격 = 정체["규격"]
    축값 = 정체.get("축값") or {}
    변형 = 축값으로변형(규격, 축값, 플랫폼) if 축값 else None
    줄 = []
    h, w = 개발요소["box"]["h"], 개발요소["box"]["w"]

    # 폐지된 변형
    v = 축값에서(규격, 축값, "Variant")
    if v and v.lower() in 규격["폐지변형"]:
        줄.append({"무엇": "변형", "css": None, "지금": v, "규격": "·".join(sorted(x for x in 규격["축"].get("Variant", []))),
                   "말": "폐지된 변형 '%s' 입니다. 허용: %s" % (v, ", ".join(규격["축"].get("Variant", [])))})

    # 높이
    if 변형 and isinstance(변형["높이"], (int, float)):
        기대 = 변형["높이"]
        크기말 = 축값에서(규격, 축값, "Size") or ""
        if abs(h - 기대) > max(허용차, 0.5):
            줄.append({"무엇": "높이", "css": "height", "지금": h, "규격": 기대,
                       "말": "이 %s은(는) %s %s(%gpx) 규격입니다. 지금 %gpx 입니다."
                             % (규격["이름"], 플랫폼, 크기말, 기대, h)})
    elif 규격["높이들"]:
        가까운 = min(규격["높이들"], key=lambda x: abs(x - h))
        if abs(h - 가까운) > max(허용차, 0.5):
            줄.append({"무엇": "높이", "css": "height", "지금": h, "규격": 가까운,
                       "말": "%s 규격 높이는 %s 중 하나입니다. 지금 %gpx 입니다."
                             % (규격["이름"], "/".join("%g" % x for x in 규격["높이들"]), h)})

    # 최소 너비
    최소 = (변형 or {}).get("최소너비")
    if isinstance(최소, (int, float)) and w + 허용차 < 최소:
        줄.append({"무엇": "최소 너비", "css": "min-width", "지금": w, "규격": 최소,
                   "말": "%s 최소 너비는 %gpx 입니다. 지금 %gpx 입니다." % (규격["이름"], 최소, w)})

    # 모서리
    if isinstance(규격.get("모서리"), (int, float)) and not 개발요소.get("isText"):
        r = 개발요소["style"].get("borderRadius") or 0
        if abs(r - 규격["모서리"]) > max(허용차, 0.5):
            줄.append({"무엇": "모서리", "css": "border-radius", "지금": r, "규격": 규격["모서리"],
                       "토큰": 규격.get("모서리토큰"),
                       "말": "%s 모서리는 %s(%gpx) 입니다. 지금 %gpx 입니다."
                             % (규격["이름"], 규격.get("모서리토큰") or "규격", 규격["모서리"], r)})

    # 변형이 정해졌으면 배경·테두리 색도 그 변형의 토큰과 맞아야 한다
    if 변형 and not 개발요소.get("isText"):
        st = 개발요소["style"]
        for 자리, 토큰이름, 속성 in (("배경색", 변형.get("칠"), "backgroundColor"), ("테두리색", 변형.get("선"), "borderColor")):
            기대색 = _색토큰값(토큰이름, 토큰)
            if not 기대색:
                continue
            if 속성 == "borderColor" and (st.get("borderWidth") or 0) <= 0:
                continue
            지금색 = 헥스로(st.get(속성))
            if 지금색 and 지금색 != 기대색:
                줄.append({"무엇": 자리, "css": CSS이름[속성], "지금": 지금색, "규격": 기대색, "토큰": 토큰이름,
                           "말": "%s %s은(는) %s(%s) 입니다. 지금 %s 입니다." % (규격["이름"], 자리, 토큰이름, 기대색, 지금색)})
    return 줄


def 컴포넌트규격(결과, 정본, 프로젝트표=None, 허용차=0, 플랫폼="PC"):
    정체들 = 정체알아보기(결과, 정본["컴포넌트"], 정본["토큰"], 프로젝트표)
    후보 = []
    by_id = {d["id"]: d for d in 결과.get("_개발요소", [])}
    for 개발id, 정체 in 정체들["정체"].items():
        d = by_id.get(개발id)
        if not d:
            continue
        줄 = 규격대조(d, 정체, 정본["토큰"], 허용차, 플랫폼)
        if 줄:
            후보.append({"갈래": "규격", "개발요소": d, "규격": 정체["규격"]["이름"], "컴포넌트id": 정체["규격"]["id"],
                         "길": 정체["길"], "신뢰도": 정체["신뢰도"], "축값": 정체.get("축값") or {}, "줄": 줄})
    return 후보, 정체들["셈"]


# ---------------------------------------------------------------- 한 번에

def 규정검사(결과, 정본, 프로젝트표=None, 허용차=0, 플랫폼="PC"):
    """값 대조 결과(후보뽑기 출력) + 정본 → 규정 후보 세 갈래.

    돌려주는 것:
      토큰밖:   개발 화면의 토큰 밖 값 (개발·퍼블리싱에게)
      규격:     컴포넌트 규격 어긋남 (개발·퍼블리싱에게, ⚠ 공통 컴포넌트)
      시안규정: 시안 자체가 토큰 밖 (디자이너에게 — 개발 지시서에 섞지 않는다)
      알아봄:   컴포넌트를 몇 개 알아봤고 몇 개 못 알아봤는지
      정본:     어느 판으로 봤는지
    """
    개발요소 = 결과.get("_개발요소", [])
    시안요소 = 결과.get("_시안요소", [])
    토큰 = 정본["토큰"]
    토큰밖목록 = 토큰밖(개발요소, 토큰, 허용차, 짝표만들기(결과))
    시안규정 = 토큰밖(시안요소, 토큰, 허용차)
    규격후보, 알아봄 = 컴포넌트규격(결과, 정본, 프로젝트표, 허용차, 플랫폼)
    return {
        "토큰밖": 토큰밖목록, "규격": 규격후보, "시안규정": 시안규정,
        "알아봄": 알아봄,
        "정본": {"커밋": 정본.get("커밋"), "받은때": 정본.get("받은때")},
        "허용차": 허용차,
        "셈": {"토큰밖": len(토큰밖목록), "토큰밖자리": sum(len(c["곳"]) for c in 토큰밖목록),
              "규격": len(규격후보), "시안규정": len(시안규정),
              "알아봄": 알아봄["알아봄"], "못알아봄": 알아봄["못알아봄"]},
    }
