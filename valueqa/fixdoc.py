"""수정 지시서 — 퍼블리싱·개발이 **한꺼번에 고칠 수 있게** 적어 주는 문서(Markdown).

검수 결과를 그림으로 보여 주는 것이 아니라, 고칠 것을 값으로 적어 준다.
같은 고침(같은 속성·같은 값)이 여러 곳에 있으면 **묶어서 한 줄**로 준다 — 일괄 반영하라고.

순서를 이렇게 두는 이유: 값은 기계가 정확히 짚어 줄 수 있다.
값부터 한 번에 바로잡아 놓고, **그다음에 눈으로 보는 검수(그림·배치)를 최소한만** 하면 된다.

**어느 화면의 어느 항목인지** 가 없으면 개발이 적용할 수 없다. 그래서 고칠 것마다
`{화면키}-{번호}` 를 붙이고, 화면 이름·주소·시안 레이어 이름·요소의 글자·화면 안 자리를 함께 적는다.
여러 화면을 한 문서로 낼 때는 `지시서묶음()` 을 쓴다 — 화면이 달라도 같은 고침은 맨 앞에 모아 준다.

여기 적힌 것도 여전히 **후보**다(CLAUDE.md 2번-2). 사람이 보고 걸러 낸 뒤 개발에 넘긴다.
"""
import re
from datetime import datetime

# 값 대조의 속성 이름 → 개발이 쓰는 CSS 이름
CSS이름 = {
    "color": "color", "backgroundColor": "background-color",
    "fontSize": "font-size", "fontWeight": "font-weight", "fontFamily": "font-family",
    "borderRadius": "border-radius", "borderWidth": "border-width", "borderColor": "border-color",
    "box.w": "width", "box.h": "height",
}
픽셀값 = {"fontSize", "borderRadius", "borderWidth", "box.w", "box.h"}


def _css값(k, v):
    if k in 픽셀값 and isinstance(v, (int, float)):
        return "%gpx" % v
    if k == "fontFamily":
        return '"%s"' % v
    return str(v)


def _고칠줄(c):
    """후보 하나에서 '고칠 것' 목록을 뽑는다. 참고·밀림·여백은 뺀다."""
    나온것 = []
    for r in c.get("rows", []):
        if r["j"] == "pass" or r.get("cascade") or r.get("deferred"):
            continue
        k = r["k"]
        if k not in CSS이름:
            continue
        if r["a"] == "완전 둥금" or r["b"] == "완전 둥금":   # 표현이 달라도 같은 뜻이라 값으로 못 적는다
            continue
        나온것.append({"k": k, "css": CSS이름[k],
                    "지금": _css값(k, r["b"]), "바꿀값": _css값(k, r["a"]), "이름": r["label"]})
    return 나온것


def _고르개(c):
    자리 = c.get("개발자리") or {}
    return 자리.get("고르개") or ""


def _자리말(box, W, H):
    """화면 안 어디쯤인지 말로 — 개발이 눈으로 찾을 때 쓴다."""
    if not box or not W or not H:
        return ""
    가운데x = box["x"] + box["w"] / 2
    가운데y = box["y"] + box["h"] / 2
    세로 = "위쪽" if 가운데y < H / 3 else ("가운데" if 가운데y < H * 2 / 3 else "아래쪽")
    가로 = "왼편" if 가운데x < W / 3 else ("가운데" if 가운데x < W * 2 / 3 else "오른편")
    return "%s %s" % (세로, 가로)


def _글자(c):
    """그 요소가 담고 있는 글자 — '어느 버튼인지' 를 사람이 알아보는 가장 빠른 실마리."""
    글 = (c.get("이름") or "").strip()
    if 글 and "/" not in 글 and not 글.startswith("("):
        return 글
    return ""


def _디자인이름(c):
    """디자인 레이어 이름. 디자이너끼리 쓰는 이름이라 **보조로만** 적는다."""
    이름 = (c.get("이름") or "").strip()
    return 이름 if "/" in 이름 else ""


def 화면정보(결과, 화면키=None, 화면이름=None, 주소=None):
    """문서 머리와 항목 번호에 쓸 화면 정보. 주는 값이 없으면 잰 값에서 끌어온다.

    화면 이름은 **개발 화면 기준**(브라우저 제목)을 먼저 쓴다 — 시안 프레임 이름은 디자이너가
    임의로 붙인 것이라 개발·퍼블리싱이 못 알아본다. 시안 이름은 '디자인쪽이름' 으로 따로 남긴다.
    """
    시안meta = 결과["meta"]["시안"]
    개발meta = 결과["meta"]["개발"]
    이름 = 화면이름 or 개발meta.get("title") or 시안meta.get("frameName") or 개발meta.get("label") or "화면"
    키 = 화면키 or re.sub(r"[^A-Za-z0-9가-힣]+", "-", 이름).strip("-")[:20].upper() or "화면"
    return {
        "키": 키, "이름": 이름, "주소": 주소 or 개발meta.get("url") or "",
        "디자인쪽이름": 시안meta.get("frameName") or "",
        "시안폭": 시안meta.get("artboardWidth"), "개발폭": 개발meta.get("artboardWidth"),
        "시안높이": 시안meta.get("artboardHeight"), "개발높이": 개발meta.get("artboardHeight"),
        "찍은때": 개발meta.get("capturedAt") or "",
        "폭다름": 결과.get("폭다름", False),
    }


def _항목만들기(결과, 정보):
    """후보 → 번호 붙은 '고칠 항목' 목록. 화면 정보를 항목마다 달아 둔다."""
    값후보 = [c for c in 결과["후보"] if c["갈래"] == "값다름"]
    번호 = 0
    항목 = []
    for c in 값후보:
        줄들 = _고칠줄(c)
        if not 줄들:
            continue
        번호 += 1
        항목.append({
            "번호": "%s-%02d" % (정보["키"], 번호),
            "화면": 정보,
            "후보": c,
            "줄들": 줄들,
            "항목이름": c["이름"],
            "글자": _글자(c),
            "디자인이름": _디자인이름(c),
            "자리": _자리말(c.get("devBox") or c.get("box"), 정보["개발폭"], 정보["개발높이"]),
            "고르개": _고르개(c),
        })
    구조 = []
    for c in 결과["후보"]:
        if c["갈래"] == "값다름":
            continue
        번호 += 1
        구조.append({
            "번호": "%s-%02d" % (정보["키"], 번호),
            "화면": 정보, "후보": c, "갈래": c["갈래"],
            "항목이름": c["이름"], "고르개": _고르개(c),
            "글자": _글자(c), "디자인이름": _디자인이름(c),
            "자리": _자리말(c.get("devBox") or c.get("box"),
                         정보["개발폭"] if c.get("devBox") else 정보["시안폭"],
                         정보["개발높이"] if c.get("devBox") else 정보["시안높이"]),
        })
    return 항목, 구조


def _어디(it, 디자인이름도=True):
    """'어느 화면의 어느 항목' 한 칸으로 — **개발 화면 기준**으로 적는다.

    선택자(id·class) 를 앞에 두고, 그 요소의 글자와 화면 안 자리를 덧붙인다.
    디자인 레이어 이름은 맨 뒤에 보조로만 (디자이너가 되짚을 때 쓴다).
    """
    조각 = []
    if it.get("고르개"):
        조각.append("`%s`" % it["고르개"])
    if it.get("글자"):
        조각.append("“%s”" % it["글자"])
    if it.get("자리"):
        조각.append("(%s)" % it["자리"])
    if not 조각:
        조각.append(it.get("항목이름") or "요소")
    if 디자인이름도 and it.get("디자인이름"):
        조각.append("〈시안 %s〉" % it["디자인이름"])
    return " · ".join(조각)


def _묶기(항목들):
    """'무엇을 어떤 값으로' 로 묶는다 — 지금 값이 제각각이어도 바꿀 값이 같으면 한 번에 반영된다.
    화면이 달라도 묶는다(여러 화면을 한 문서로 낼 때 이게 핵심이다)."""
    묶음 = {}
    for it in 항목들:
        for r in it["줄들"]:
            칸 = 묶음.setdefault((r["css"], r["바꿀값"]), {"곳": [], "지금들": []})
            칸["곳"].append(it)
            칸["지금들"].append(r["지금"])
    return 묶음


def _머리(L, 제목, 화면들, 차수, 정본커밋):
    L.append("# %s" % 제목)
    L.append("")
    머리 = []
    if 차수:
        머리.append("%s차 검수" % 차수)
    머리.append(datetime.now().strftime("%Y-%m-%d"))
    if 정본커밋:
        머리.append("디자인 정본 %s" % 정본커밋)
    L.append(" · ".join(머리))
    L.append("")
    L.append("| 화면 | 개발 화면 | 주소 | 시안 ↔ 개발 폭 | 시안 프레임 |")
    L.append("|---|---|---|---|---|")
    for 정보 in 화면들:
        L.append("| `%s` | %s | %s | %s ↔ %s px%s | %s |"
                 % (정보["키"], 정보["이름"], 정보["주소"] or "—",
                    정보["시안폭"] or "?", 정보["개발폭"] or "?",
                    " ⚠ 다름" if 정보["폭다름"] else "",
                    정보.get("디자인쪽이름") or "—"))
    L.append("")
    L.append("> 값으로 확인한 차이입니다. **이 값들을 먼저 반영해 주세요.**")
    L.append("> 값이 맞춰진 뒤에 그림·배치를 눈으로 보는 검수를 최소한으로 한 번 더 합니다.")
    L.append("> **고칠 자리는 개발 화면 기준(선택자·id·class)으로 적었습니다.** "
             "맨 뒤 〈시안 …〉 는 디자이너가 되짚을 때 쓰는 레이어 이름이라 무시하셔도 됩니다.")
    L.append("> 번호(`화면-번호`)로 이야기해 주시면 어느 화면의 어느 항목인지 서로 헷갈리지 않습니다.")
    L.append("> 안쪽여백(padding)과 요소의 위치(x·y)는 여기 넣지 않았습니다 — 퍼블리싱 단계에서 봅니다.")
    L.append("")
    _쓰는법(L)


def _쓰는법(L):
    """이 문서를 처음 받는 사람이 무엇부터 해야 하는지."""
    L.append("## 이 문서 쓰는 법")
    L.append("")
    L.append("1. **'한꺼번에 고칠 것' 부터.** 여러 곳을 같은 값으로 맞추면 되는 것들입니다. "
             "에디터에서 찾아 바꾸기로 한 번에 반영하세요.")
    L.append("2. **자리를 찾습니다.** 표의 선택자를 개발자도구 검색창에 그대로 붙여넣으면 그 요소가 잡힙니다. "
             "옆에 적힌 글자와 화면 안 자리로 눈으로도 확인하세요.")
    L.append("3. **값을 넣습니다.** 아래 CSS 덩어리는 *그대로 붙이라는 것이 아니라* "
             "무엇을 무엇으로 바꿀지 보여 주는 것입니다. 실제로는 그 요소가 쓰는 클래스·컴포넌트 쪽에 반영해 주세요. "
             "⚠ 공통 컴포넌트를 고치면 다른 화면도 함께 바뀝니다 — 그런 것 같으면 고치기 전에 알려 주세요.")
    L.append("4. **구조 항목은 기획을 확인합니다.** '디자인에 없는데 있다'는 지우라는 뜻이 아니라 "
             "기획이 바뀐 것인지 묻는 것입니다.")
    L.append("5. **끝나면 맨 아래 체크 목록을 체크해 회신해 주세요.** "
             "그 화면을 다시 찍어 값을 재고, 체크된 것만 확인합니다.")
    L.append("")


def _본문(L, 항목들, 구조들, 주의들, 여러화면):
    묶음 = _묶기(항목들)
    한꺼번에 = {k: v for k, v in 묶음.items() if len(v["곳"]) >= 2}
    낱개 = {k: v for k, v in 묶음.items() if len(v["곳"]) == 1}

    L.append("| 무엇 | 몇 |")
    L.append("|---|---|")
    L.append("| 한꺼번에 고칠 것(여러 곳을 같은 값으로) | %d 가지 |" % len(한꺼번에))
    L.append("| 하나씩 고칠 것 | %d 가지 |" % len(낱개))
    L.append("| 고칠 항목 | %d 개 |" % len(항목들))
    L.append("| 구조 확인 | %d 개 |" % len(구조들))
    L.append("")

    장 = [0]

    def 장번호():
        장[0] += 1
        return 장[0]

    화면칸 = "화면 | " if 여러화면 else ""
    화면선 = "---|" if 여러화면 else ""

    if 한꺼번에:
        L.append("## %d. 한꺼번에 고칠 것" % 장번호())
        L.append("")
        L.append("여러 곳을 **같은 값으로** 맞추면 되는 것들입니다. 한 번에 반영할 수 있습니다.")
        L.append("")
        L.append("| 고칠 것 | 바꿀 값 (시안) | 지금 (개발) | 해당 번호 |")
        L.append("|---|---|---|---|")
        for (css, 바꿀값), v in sorted(한꺼번에.items(), key=lambda x: -len(x[1]["곳"])):
            번호들 = ", ".join("`%s`" % it["번호"] for it in v["곳"])
            지금 = ", ".join(sorted(set(v["지금들"])))
            L.append("| `%s` | `%s` | `%s` | %s |" % (css, 바꿀값, 지금, 번호들))
        L.append("")

    L.append("## %d. 고칠 항목 — 개발 화면의 어디를 무엇으로" % 장번호())
    L.append("")
    L.append("| 번호 | %s고칠 자리 (개발 화면 기준) | 고칠 것 | 지금 (개발) | 바꿀 값 (시안) |" % 화면칸)
    L.append("|---|%s---|---|---|---|" % 화면선)
    for it in 항목들:
        for i, r in enumerate(it["줄들"]):
            번호칸 = "`%s`" % it["번호"] if i == 0 else "↳"
            어디칸 = _어디(it) if i == 0 else "↳"
            화면값 = ("`%s` | " % it["화면"]["키"]) if 여러화면 else ""
            L.append("| %s | %s%s | `%s` | `%s` | `%s` |"
                     % (번호칸, 화면값, 어디칸, r["css"], r["지금"], r["바꿀값"]))
    L.append("")

    if 항목들:
        L.append("## %d. 그대로 붙여 쓰는 값" % 장번호())
        L.append("")
        L.append("개발 화면에서 읽은 태그·class 로 적었습니다. 실제 선택자는 프로젝트에 맞게 바꿔 주세요.")
        L.append("")
        지금화면 = None
        L.append("```css")
        for it in 항목들:
            if 여러화면 and it["화면"]["키"] != 지금화면:
                지금화면 = it["화면"]["키"]
                L.append("/* ===== %s · %s ===== */" % (지금화면, it["화면"]["이름"]))
            고르개 = it["고르개"] or "/* %s */" % it["항목이름"]
            L.append("/* %s · %s */" % (it["번호"], _어디(it).replace("`", "").replace("“", "'").replace("”", "'")))
            L.append("%s {" % 고르개)
            for r in it["줄들"]:
                L.append("  %s: %s;   /* 지금 %s */" % (r["css"], r["바꿀값"], r["지금"]))
            L.append("}")
        L.append("```")
        L.append("")

    if 구조들:
        L.append("## %d. 구조 — 값이 아니라 있고 없음" % 장번호())
        L.append("")
        L.append("| 번호 | %s고칠 자리 (개발 화면 기준) | 무슨 일 |" % 화면칸)
        L.append("|---|%s---|---|" % 화면선)
        for it in 구조들:
            말 = ("디자인에 없는 요소가 개발에 있습니다" if it["갈래"] == "더있음"
                 else "디자인에 있는데 개발에서 못 찾았습니다")
            화면값 = ("`%s` | " % it["화면"]["키"]) if 여러화면 else ""
            L.append("| `%s` | %s%s | %s |" % (it["번호"], 화면값, _어디(it), 말))
        L.append("")
        L.append("'없애 주세요/넣어 주세요'가 아닐 수 있습니다. 기획이 바뀐 것인지 먼저 확인해 주세요.")
        L.append("")

    if 주의들:
        L.append("## %d. 참고 — 아주 작은 차이 (%d)" % (장번호(), len(주의들)))
        L.append("")
        L.append("고치지 않아도 되는 수준입니다. 다른 것을 손보는 김에 같이 맞추면 좋습니다.")
        L.append("")
        for 정보, c in 주의들:
            다른곳 = ", ".join("%s %s→%s" % (x["속성"], x["시안"], x["개발"]) for x in c["다른곳"]) or "미세"
            앞 = ("`%s` " % 정보["키"]) if 여러화면 else ""
            L.append("- %s%s — %s" % (앞, c["이름"], 다른곳))
        L.append("")

    if 항목들 or 구조들:
        L.append("## %d. 고친 뒤 확인" % 장번호())
        L.append("")
        L.append("반영하신 뒤 체크해 주세요. 체크된 것만 다음 차수에서 다시 재겠습니다.")
        L.append("")
        for it in 항목들:
            앞 = ("%s " % it["화면"]["키"]) if 여러화면 else ""
            L.append("- [ ] `%s` %s%s — %s"
                     % (it["번호"], 앞, _어디(it),
                        ", ".join("%s %s" % (r["css"], r["바꿀값"]) for r in it["줄들"])))
        for it in 구조들:
            앞 = ("%s " % it["화면"]["키"]) if 여러화면 else ""
            말 = "남길지 확인" if it["갈래"] == "더있음" else "빠진 것인지 확인"
            L.append("- [ ] `%s` %s%s — %s" % (it["번호"], 앞, _어디(it), 말))
        L.append("")

    return 장번호


def _꼬리(L, 화면들):
    L.append("## 이번에 다루지 않은 것")
    L.append("")
    L.append("- **안쪽여백(padding)** — 재기는 했지만 요청에 넣지 않았습니다. 퍼블리싱 단계에서 봅니다.")
    L.append("- **요소의 가로·세로 위치** — 화면 높이·스크롤에 따라 쉽게 달라져 참고로만 둡니다.")
    if any(정보["폭다름"] for 정보 in 화면들):
        L.append("- **너비·높이(폭이 다른 화면)** — 시안과 개발의 화면 폭이 달라 크기 차이는 참고로 내렸습니다. "
                 "같은 폭으로 다시 찍으면 값으로 잡힙니다.")
    L.append("- **아이콘 모양** — 그림이라 값으로 견줄 수 없습니다. 눈으로 보는 검수에서 봅니다.")
    L.append("")
    L.append("---")
    L.append("")
    L.append("자동으로 찾은 **후보**입니다. 확정은 디자이너가 합니다.")


def 지시서(결과, 화면이름="", 차수=None, 정본커밋=None, 화면키=None, 주소=None):
    """화면 하나짜리 수정 요청."""
    정보 = 화면정보(결과, 화면키, 화면이름, 주소)
    항목들, 구조들 = _항목만들기(결과, 정보)
    주의들 = [(정보, c) for c in (결과.get("주의") or [])]
    L = []
    _머리(L, "개발화면 수정 요청 — %s" % 정보["이름"], [정보], 차수, 정본커밋)
    _본문(L, 항목들, 구조들, 주의들, 여러화면=False)
    _꼬리(L, [정보])
    return "\n".join(L) + "\n"


def 지시서묶음(화면별, 제목="개발화면 수정 요청", 차수=None, 정본커밋=None):
    """화면 여러 개를 한 문서로.

    화면별 = [(결과, {"화면키":…, "화면이름":…, "주소":…}), …]
    화면이 달라도 같은 고침은 맨 앞 '한꺼번에 고칠 것' 에 함께 묶인다.
    """
    화면들, 항목들, 구조들, 주의들 = [], [], [], []
    for 결과, 메모 in 화면별:
        메모 = 메모 or {}
        정보 = 화면정보(결과, 메모.get("화면키"), 메모.get("화면이름"), 메모.get("주소"))
        화면들.append(정보)
        ㅎ, ㄱ = _항목만들기(결과, 정보)
        항목들.extend(ㅎ)
        구조들.extend(ㄱ)
        주의들.extend((정보, c) for c in (결과.get("주의") or []))
    L = []
    _머리(L, "%s — 화면 %d개" % (제목, len(화면들)), 화면들, 차수, 정본커밋)
    _본문(L, 항목들, 구조들, 주의들, 여러화면=True)
    _꼬리(L, 화면들)
    return "\n".join(L) + "\n"
