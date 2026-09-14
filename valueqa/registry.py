"""정본 받아오기 — 회사 디자인 시스템 정본(`S1-UX-DESIGN-with-AI`)에서 토큰 목록과 컴포넌트 규격을 읽는다.

정본은 아직 정리 중이라 시시각각 바뀐다. 그래서 **복사해 두지 않고 검수할 때마다 받아온다.**
받아온 판(커밋)은 결과에 적어, 어느 판으로 판정했는지 되짚을 수 있게 한다.

읽는 것:
  · assets/css/tokens.css                          — 모든 토큰의 실제 값 (현행 정본 CSS, 자동 생성물)
  · registry/tokens/deprecated-tokens.json         — 그만 쓰는 토큰
  · registry/components/component-guide-model.json — 피그마 컴포넌트 세트 이름·변형별 크기 (기계가 뽑은 것)
  · registry/components/*.json                     — 컴포넌트 규격 서술(변형 목록·폐지 변형·모서리 토큰)
  · registry/governance/component-page-coverage.json — 피그마 세트 이름 → 컴포넌트 id
  · registry/governance/component-geometry-map.json  — 컴포넌트 → 웹 클래스 접두사 (전시 페이지 기준, 실마리 하나)
  · registry/governance/deprecated.json            — 폐지된 변형

`registry/tokens/component.tokens.json` 은 은퇴했다(index.json 이 그렇게 적어 둠) — 읽지 않는다.
`registry/tokens/legacy/` 도 옛 스냅샷이라 읽지 않는다.
"""
import io
import json
import os
import re
import tarfile
import tempfile
import urllib.request
from datetime import datetime

import sys as _sys
_뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _뿌리 not in _sys.path:
    _sys.path.insert(0, _뿌리)
import 설정 as _설정                      # 이 컴퓨터에서만 쓰는 값 (설정.json → 환경변수 → 기본값)

저장소 = _설정.값("정본.저장소")
가지 = _설정.값("정본.가지")
받는주소 = "%s/%s/tar.gz/refs/heads/%s" % (_설정.값("정본.받는곳").rstrip("/"), 저장소, 가지)
판주소 = "%s/repos/%s/commits/%s" % (_설정.값("정본.판보는곳").rstrip("/"), 저장소, 가지)


class 정본오류(Exception):
    pass


# ---------------------------------------------------------------- 받아오기

def 캐시자리():
    return os.path.join(tempfile.gettempdir(), "valueqa-registry")


def 최신판():
    """정본의 지금 커밋(짧은 SHA). 막혀 있으면 None."""
    try:
        req = urllib.request.Request(판주소, headers={"User-Agent": "valueqa", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return (json.load(r).get("sha") or "")[:7] or None
    except Exception:
        return None


def 받아오기(자리=None, 시간=60):
    """정본을 통째로 받아 임시 폴더에 풀고 그 경로를 돌려준다. 저장소 안에는 두지 않는다.

    인터넷이 막힌 곳(내부망)에서는 설정.json 의 `정본.이미받은자리` 에 미리 내려받아 둔
    폴더를 적어 두면 인터넷을 쓰지 않고 그 폴더를 그대로 쓴다.

    돌려주는 것: {"경로", "커밋", "받은때"}
    """
    미리받은것 = _설정.자리("정본.이미받은자리")
    if 미리받은것:
        if not os.path.isdir(str(미리받은것)):
            raise 정본오류("설정.json 의 정본.이미받은자리 에 적은 폴더가 없습니다 — %s" % 미리받은것)
        표시 = os.path.join(str(미리받은것), ".받은때")
        적힌때 = ""
        if os.path.exists(표시):
            with open(표시, encoding="utf-8") as f:
                적힌때 = f.read().strip()
        return {"경로": str(미리받은것), "커밋": "내려받아둔판", "받은때": 적힌때 or "(적혀 있지 않음)"}
    커밋 = 최신판()
    자리 = 자리 or 캐시자리()
    목적지 = os.path.join(자리, 커밋 or "main")
    표시 = os.path.join(목적지, ".받은때")
    if 커밋 and os.path.exists(표시):
        with open(표시, encoding="utf-8") as f:
            return {"경로": 목적지, "커밋": 커밋, "받은때": f.read().strip()}
    try:
        req = urllib.request.Request(받는주소, headers={"User-Agent": "valueqa"})
        with urllib.request.urlopen(req, timeout=시간) as r:
            덩어리 = r.read()
    except Exception as e:
        raise 정본오류("정본을 받아오지 못했습니다 — %s (%s)" % (받는주소, e))
    os.makedirs(목적지, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(덩어리), mode="r:gz") as t:
        for m in t.getmembers():
            조각 = m.name.split("/", 1)
            if len(조각) < 2 or not m.isfile():
                continue
            if not (조각[1].startswith("registry/") or 조각[1].startswith("assets/css/")):
                continue
            대상 = os.path.join(목적지, 조각[1])
            os.makedirs(os.path.dirname(대상), exist_ok=True)
            with open(대상, "wb") as f:
                f.write(t.extractfile(m).read())
    받은때 = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(표시, "w", encoding="utf-8") as f:
        f.write(받은때)
    return {"경로": 목적지, "커밋": 커밋, "받은때": 받은때}


# ---------------------------------------------------------------- 토큰

def _json(경로):
    try:
        with open(경로, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def 헥스로(값):
    """'#FFF' '#FFFFFF' 'rgb(255, 255, 255)' → '#FFFFFF'. 알파가 1 미만이면 None(덧씌우기 색은 예외 EX03)."""
    if not 값:
        return None
    s = str(값).strip()
    m = re.match(r"^#([0-9a-fA-F]{3})$", s)
    if m:
        v = m.group(1)
        return ("#" + v[0] * 2 + v[1] * 2 + v[2] * 2).upper()
    m = re.match(r"^#([0-9a-fA-F]{6})$", s)
    if m:
        return ("#" + m.group(1)).upper()
    m = re.match(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([0-9.]+))?\s*\)$", s)
    if m:
        if m.group(4) is not None and float(m.group(4)) < 1:
            return None
        return "#%02X%02X%02X" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _px(값):
    m = re.match(r"^\s*(-?[0-9.]+)px\s*$", str(값))
    return float(m.group(1)) if m else None


def 토큰읽기(경로):
    """tokens.css → 이름별 값(참조를 끝까지 풀어서) + 갈래별 목록.

    돌려주는 것:
      이름값: {"--color-gray-100": "#E9E9E9", "--spacing-8": "8px", ...}   (밝은 테마 기준)
      색:     {"#E9E9E9": ["--color-gray-100", ...]}    값 → 그 값을 가진 토큰 이름들(기초 토큰 먼저)
      크기:   {"spacing": {8: "--spacing-8"}, "sizing": {...}, "radius": {...}, "font-size": {...}, "border-width": {...}}
      굵기:   {400: "--font-weight-regular", ...}
      폐지:   {"--input-hover-bg": {...}}
    """
    css경로 = os.path.join(경로, "assets", "css", "tokens.css")
    try:
        with open(css경로, encoding="utf-8") as f:
            css = f.read()
    except OSError as e:
        raise 정본오류("정본 CSS 를 못 읽었습니다 — %s (%s)" % (css경로, e))

    # 어두운 테마 블록은 뺀다 — 검수는 밝은 화면 기준. (어두운 기초색 자체는 :root 에 있어 목록에 남는다)
    밝은css = re.sub(r"\[data-theme=\"dark\"\]\s*\{[^}]*\}", "", css)
    날것 = {}
    for m in re.finditer(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);", 밝은css):
        이름, 값 = m.group(1), re.sub(r"/\*.*?\*/", "", m.group(2)).strip()
        날것.setdefault(이름, 값)   # 먼저 나온 정의를 쓴다

    def 풀기(값, 깊이=0):
        m = re.match(r"^var\((--[a-zA-Z0-9_-]+)\)$", 값.strip())
        if m and 깊이 < 8:
            return 풀기(날것.get(m.group(1), 값), 깊이 + 1)
        return 값.strip()

    이름값 = {k: 풀기(v) for k, v in 날것.items()}

    색, 크기, 굵기 = {}, {"spacing": {}, "sizing": {}, "radius": {}, "font-size": {}, "border-width": {}}, {}
    for 이름, 값 in 이름값.items():
        h = 헥스로(값)
        if h:
            색.setdefault(h, []).append(이름)
            continue
        px = _px(값)
        if px is not None:
            for 갈래 in 크기:
                if 이름.startswith("--" + 갈래 + "-") and 이름.count("-") == 갈래.count("-") + 3:
                    크기[갈래].setdefault(px, 이름)
            continue
        if 이름.startswith("--font-weight-") and re.match(r"^\d+$", 값):
            굵기.setdefault(int(값), 이름)
    # 같은 값의 토큰이 여럿이면 기초 토큰(짧은 이름·--color-<색>-<숫자>)을 앞에
    for h in 색:
        색[h].sort(key=lambda n: (0 if re.match(r"^--color-(base|brand|[a-z-]+-\d+)$", n) else 1, len(n), n))

    폐지 = {}
    d = _json(os.path.join(경로, "registry", "tokens", "deprecated-tokens.json")) or {}
    for t in d.get("deprecatedTokens", []):
        if t.get("cssVariable"):
            폐지[t["cssVariable"]] = t
    return {"이름값": 이름값, "색": 색, "크기": 크기, "굵기": 굵기, "폐지": 폐지}


# ---------------------------------------------------------------- 컴포넌트 규격

def _이름다듬기(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def 컴포넌트읽기(경로, 토큰=None):
    """피그마 세트 이름을 열쇠로 한 컴포넌트 규격 표.

    {"Button": {"id": "button", "이름": "Button", "별칭": {...다듬은 이름들},
                "축": {"Size": [...], "Variant": [...], ...},
                "변형": [{"축값": {...}, "높이": 44, "너비": 80, "최소너비": 80, "칠": "--color-...", "선": "--color-..."}],
                "높이들": {44, 34, 28, 48},
                "모서리": 4.0 또는 None, "모서리토큰": "--radius-button-md",
                "폐지변형": {"danger", "ghost"},
                "접두사": ["s1-btn"]}}
    """
    안내 = _json(os.path.join(경로, "registry", "components", "component-guide-model.json")) or {}
    덮개 = (_json(os.path.join(경로, "registry", "governance", "component-page-coverage.json")) or {}).get("sectionFor", {})
    기하 = (_json(os.path.join(경로, "registry", "governance", "component-geometry-map.json")) or {}).get("sets", {})
    폐지목록 = (_json(os.path.join(경로, "registry", "governance", "deprecated.json")) or {}).get("deprecated", [])
    이름값 = (토큰 or {}).get("이름값", {})

    표 = {}
    for 세트 in 안내.get("componentSets", []):
        세트이름 = 세트.get("name") or ""
        아이디 = 덮개.get(세트이름) or _이름다듬기(세트이름)
        서술 = _json(os.path.join(경로, "registry", "components", "%s.json" % 아이디)) or {}
        변형들 = []
        for v in 세트.get("variants", []):
            n = v.get("node") or {}
            dim = n.get("dimensions") or {}
            lay = n.get("layout") or {}
            ap = n.get("appearance") or {}
            변형들.append({
                "축값": v.get("axes") or {},
                "높이": dim.get("height"), "너비": dim.get("width"),
                "너비고정": (lay.get("primaryAxisSizingMode") == "FIXED" and lay.get("layoutMode") == "HORIZONTAL"),
                "최소너비": lay.get("minWidth"),
                "칠": ("--" + ap["fill"].replace("/", "-")) if ap.get("fill") and ap["fill"] != "(없음)" else None,
                "선": ("--" + ap["stroke"].replace("/", "-")) if ap.get("stroke") and ap["stroke"] != "(없음)" else None,
            })
        모서리토큰 = None
        sz = 서술.get("sizing")
        if isinstance(sz, dict) and isinstance(sz.get("radius"), str) and sz["radius"].startswith("--"):
            모서리토큰 = sz["radius"]
        모서리 = _px(이름값.get(모서리토큰, "")) if 모서리토큰 else None

        폐지변형 = set()
        for p in 서술.get("pendingVariants", []) or []:
            if p.get("status") in ("deprecated", "legacy") and p.get("name"):
                폐지변형.add(p["name"].lower())
        for p in 폐지목록:
            if p.get("type") == "component-variant" and (p.get("name") or "").lower().startswith(세트이름.lower() + " /"):
                폐지변형.add(p["name"].split("/", 1)[1].strip().lower())

        별칭 = {_이름다듬기(세트이름), _이름다듬기(아이디)}
        meta = 서술.get("_meta") or {}
        fig = 서술.get("figma") or {}
        for s in (meta.get("name"), meta.get("id"), fig.get("componentName")):
            if s:
                별칭.add(_이름다듬기(s))
        표[세트이름] = {
            "id": 아이디, "이름": 세트이름, "별칭": 별칭,
            "축": 세트.get("axes") or {},
            "변형": 변형들,
            "높이들": sorted({v["높이"] for v in 변형들 if isinstance(v["높이"], (int, float))}),
            "모서리": 모서리, "모서리토큰": 모서리토큰,
            "폐지변형": 폐지변형,
            "접두사": list((기하.get(세트이름) or {}).get("prefixes") or []),
            "값맵": ((서술.get("figma") or {}).get("valueMap") or {}),
        }
    return 표


def 정본읽기(경로, 판=None):
    """받아 둔(또는 로컬) 정본 폴더 → 토큰 + 컴포넌트 규격 한 덩어리."""
    토큰 = 토큰읽기(경로)
    컴포넌트 = 컴포넌트읽기(경로, 토큰)
    return {"경로": 경로, "커밋": (판 or {}).get("커밋"), "받은때": (판 or {}).get("받은때"),
            "토큰": 토큰, "컴포넌트": 컴포넌트}


def 정본가져오기(어디="auto"):
    """'auto' 면 깃허브에서 받아오고, 경로면 그 폴더를 읽는다."""
    if 어디 in (None, "", "auto"):
        판 = 받아오기()
        return 정본읽기(판["경로"], 판)
    return 정본읽기(어디, {"커밋": "로컬", "받은때": None})


def 토큰셈(정본):
    """정본에 토큰이 몇 개인지 — 받아온 판이 온전한지 한눈에 보는 숫자."""
    t = 정본["토큰"]
    return {"색": len(t["색"]), "간격": len(t["크기"]["spacing"]), "크기": len(t["크기"]["sizing"]),
            "모서리": len(t["크기"]["radius"]), "글자크기": len(t["크기"]["font-size"]),
            "테두리": len(t["크기"]["border-width"]), "굵기": len(t["굵기"]),
            "컴포넌트": len(정본["컴포넌트"]), "규격있는컴포넌트": sum(1 for c in 정본["컴포넌트"].values() if c["높이들"])}
