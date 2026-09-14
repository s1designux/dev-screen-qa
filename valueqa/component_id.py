"""컴포넌트 알아보기 — 개발 화면의 요소가 정본의 어느 컴포넌트인지.

**클래스 이름에 기대지 않는다.** 실제 서비스 화면은 디자인 시스템 클래스(`s1-btn`)를 안 쓰는 경우가 많다.
그래서 세 길을 겹쳐 쓰고, 알아본 것만 규격을 본다. 못 알아본 것은 조용히 넘기고 **몇 개인지 숫자로만** 알린다.

  (1) 시안 쪽 정체를 짝 건너로 옮긴다 — 시안은 피그마 컴포넌트 인스턴스라 이름이 정본과 맞는다. 가장 튼튼하다.
  (2) 프로젝트마다 한 번 정해 두는 대응표 — "이 프로젝트에서 버튼은 `.btn-primary`". 화면마다 설정하는 것이 아니다.
      정본의 component-geometry-map(전시 페이지 접두사)이 기본값이고, 프로젝트 표가 있으면 그것을 더한다.
  (3) 모양으로 추측 — 위 둘로 못 알아본 것만, 낮은 신뢰도로. 이것으로 확정하지 않는다.
"""
from .registry import _이름다듬기, 헥스로

신뢰도 = {"시안": 0.9, "대응표": 0.7, "모양": 0.4}


def _정본찾기(이름, 컴포넌트표):
    """피그마 세트 이름·컴포넌트 이름 → 정본 규격. 'Button', 'button', 'Button / PC' 모두 받는다."""
    if not 이름:
        return None
    후보 = [_이름다듬기(이름)]
    if "/" in 이름:
        후보.append(_이름다듬기(이름.split("/")[0]))
    for k in 후보:
        if not k:
            continue
        for c in 컴포넌트표.values():
            if k in c["별칭"]:
                return c
    return None


def _속성정리(속성):
    """플러그인이 보낸 componentProperties → {축이름: 값}. {"Size": {"type":"VARIANT","value":"MD"}} 도 받는다."""
    out = {}
    for k, v in (속성 or {}).items():
        if isinstance(v, dict):
            v = v.get("value")
        if v is None or isinstance(v, (dict, list)):
            continue
        out[str(k).split("#")[0]] = str(v)
    return out


def 시안쪽정체(시안요소, 컴포넌트표):
    """(1) 시안 요소에 실려 온 인스턴스 정보 → {"규격", "축값", "길": "시안"}. 없으면 None."""
    c = 시안요소.get("컴포넌트") or {}
    이름 = c.get("세트") or c.get("이름")
    규격 = _정본찾기(이름, 컴포넌트표)
    if not 규격 and c.get("이름"):
        규격 = _정본찾기(c["이름"], 컴포넌트표)
    if not 규격:
        return None
    return {"규격": 규격, "축값": _속성정리(c.get("속성")), "길": "시안", "신뢰도": 신뢰도["시안"]}


def 대응표만들기(컴포넌트표, 프로젝트표=None):
    """{접두사: 규격}. 정본 기본값(전시 페이지 접두사) + 프로젝트 표(있으면 우선)."""
    표 = {}
    for c in 컴포넌트표.values():
        for p in c["접두사"]:
            표[p.lower()] = c
    for 이름, 접두사들 in (프로젝트표 or {}).items():
        규격 = _정본찾기(이름, 컴포넌트표)
        if not 규격:
            continue
        if isinstance(접두사들, str):
            접두사들 = [접두사들]
        for p in 접두사들:
            표[p.lstrip(".").lower()] = 규격
    return 표


def 대응표정체(개발요소, 대응표):
    """(2) 개발 요소의 class 가 대응표의 접두사로 시작하면 그 컴포넌트."""
    반 = (개발요소.get("cls") or "").lower().split()
    if not 반 or not 대응표:
        return None
    for 접두사, 규격 in sorted(대응표.items(), key=lambda x: -len(x[0])):   # 긴 접두사 먼저 (s1-btn-md 보다 s1-btn 이 늦게)
        for c in 반:
            if c == 접두사 or c.startswith(접두사 + "-") or c.startswith(접두사 + "_") or c.startswith(접두사 + "--"):
                return {"규격": 규격, "축값": {}, "길": "대응표", "신뢰도": 신뢰도["대응표"]}
    return None


def 모양정체(개발요소, 컴포넌트표, 토큰):
    """(3) 버튼처럼 생겼나 — 글자 한 줄이 든 상자, 배경 또는 테두리가 정본 색, 높이가 규격 높이 근처. 낮은 신뢰도."""
    if 개발요소.get("isText") or not (개발요소.get("text") or "").strip():
        return None
    st = 개발요소["style"]
    글 = 개발요소["text"].strip()
    if len(글) > 20 or "\n" in 글:
        return None
    배경 = 헥스로(st.get("backgroundColor"))
    선 = 헥스로(st.get("borderColor")) if (st.get("borderWidth") or 0) > 0 else None
    색맞음 = (배경 and 배경 in 토큰["색"] and 배경 not in ("#FFFFFF",)) or (선 and 선 in 토큰["색"])
    if not 색맞음:
        return None
    if (개발요소.get("role") or "").upper() not in ("BUTTON", "A", "DIV", "SPAN", "INPUT", "LABEL"):
        return None
    규격 = 컴포넌트표.get("Button")
    if not 규격 or not 규격["높이들"]:
        return None
    h = 개발요소["box"]["h"]
    if min(abs(h - x) for x in 규격["높이들"]) > 6:
        return None
    return {"규격": 규격, "축값": {}, "길": "모양", "신뢰도": 신뢰도["모양"]}


def 정체알아보기(결과, 컴포넌트표, 토큰, 프로젝트표=None):
    """값 대조 결과(후보뽑기 출력)의 짝을 따라 개발 요소마다 정체를 붙인다.

    돌려주는 것: {"정체": {개발id: {...}}, "셈": {"알아봄", "못알아봄", "길별": {...}}}
    """
    대응표 = 대응표만들기(컴포넌트표, 프로젝트표)
    정체 = {}
    시안정체 = {}
    # (1) 시안 요소의 정체 — 짝을 통해 개발 요소로
    for c in 결과.get("_짝", []):
        f, d = c["시안"], c["개발"]
        x = 시안쪽정체(f, 컴포넌트표)
        if x:
            정체[d["id"]] = x
            시안정체[f.get("id")] = x
    개발요소들 = 결과.get("_개발요소", [])
    for d in 개발요소들:
        if d["id"] in 정체:
            continue
        x = 대응표정체(d, 대응표)                                   # (2)
        if not x:
            x = 모양정체(d, 컴포넌트표, 토큰)                       # (3)
        if x:
            정체[d["id"]] = x
    후보수 = sum(1 for d in 개발요소들 if not d.get("isText") and (d.get("text") or "").strip())
    길별 = {"시안": 0, "대응표": 0, "모양": 0}
    for x in 정체.values():
        길별[x["길"]] += 1
    return {"정체": 정체, "시안정체": 시안정체,
            "셈": {"알아봄": len(정체), "못알아봄": max(0, 후보수 - len(정체)), "길별": 길별}}


def 축값으로변형(규격, 축값, 플랫폼="PC"):
    """인스턴스 속성(Size=MD, Variant=Primary …)으로 정본 변형 하나를 고른다. 못 고르면 None."""
    if not 규격["변형"]:
        return None
    원하는 = {k: v.lower() for k, v in 축값.items() if k in 규격["축"]}
    if "Break" in 규격["축"] and "Break" not in 원하는:
        원하는["Break"] = 플랫폼.lower()
    if "State" in 규격["축"] and "State" not in 원하는:
        원하는["State"] = "default"
    가장 = None
    for v in 규격["변형"]:
        ax = {k: str(x).lower() for k, x in v["축값"].items()}
        if all(ax.get(k) == x for k, x in 원하는.items()):
            return v
        점 = sum(1 for k, x in 원하는.items() if ax.get(k) == x)
        if 가장 is None or 점 > 가장[0]:
            가장 = (점, v)
    return 가장[1] if 가장 and 가장[0] >= max(1, len(원하는) - 1) else None


def 축값에서(규격, 축값, 축):
    for k, v in 축값.items():
        if k.lower() == 축.lower():
            return v
    return None

