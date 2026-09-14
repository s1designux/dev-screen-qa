"""후보 뽑기 — 짝 맞추기 + 값 견주기를 한 번에 돌려 '다른 곳'을 후보로 만든다.

**후보는 지적이 아니다** (CLAUDE.md 2번-2). 사람이 포털에서 '지적 등록'을 눌러야 지적이 된다.
그래서 여기서 나오는 것에는 신뢰도가 함께 붙고, 자동으로 확정되는 길은 없다.

후보 세 갈래:
  값다름   — 짝은 지었는데 속성 값이 다르다 (색·글자크기·굵기·모서리·테두리·크기)
  더있음   — 시안에 없는 것이 개발에만 있다
  빠짐     — 시안에 있는데 개발에서 못 찾았다
"""
from .match import 짝맞추기
from .compare import 값견주기


def 짧은시안이름(f):
    이름 = f.get("name") or ""
    return 이름 if "/" in 이름 else (f.get("text") or ("글자" if f.get("isText") else "상자"))


def 짧은개발이름(d):
    if d.get("text"):
        return d["text"]
    return "(%s %s×%s)" % ("글자" if d.get("isText") else "상자", d["box"]["w"], d["box"]["h"])


def _안에들어있나(box, 상자들):
    for b in 상자들:
        if b is box:
            continue
        if (box["x"] >= b["x"] - 2 and box["y"] >= b["y"] - 2
                and box["x"] + box["w"] <= b["x"] + b["w"] + 2
                and box["y"] + box["h"] <= b["y"] + b["h"] + 2
                and b["w"] * b["h"] > box["w"] * box["h"]):
            return True
    return False


def _개발자리(d):
    """개발자가 어디를 고치면 되는지 짚어 주는 실마리 — **개발 화면 기준**의 선택자다.

    디자인 레이어 이름은 디자이너가 임의로 붙인 것이라 개발·퍼블리싱이 못 알아본다.
    그래서 id → 측정할 때 만들어 둔 CSS 선택자 → 태그.class 차례로 고른다.
    (선택자는 측정기 core-1.2 부터 함께 들어온다. 옛 측정값에는 없어 태그.class 로 물러난다.)
    """
    태그 = (d.get("role") or "").lower()
    반 = (d.get("cls") or "").strip()
    첫반 = 반.split()[0] if 반 else ""
    돔아이디 = (d.get("domId") or "").strip()
    선택자 = (d.get("sel") or "").strip()
    고르개 = 선택자 or (("#%s" % 돔아이디) if 돔아이디 else
                     (("%s.%s" % (태그, 첫반)) if (태그 and 첫반) else (태그 or "")))
    return {"태그": 태그, "class": 반, "id": 돔아이디, "선택자": 선택자, "고르개": 고르개}


def _신뢰도(짝점수, 어긋난줄수):
    """짝을 얼마나 믿을 수 있나 × 차이가 얼마나 뚜렷한가. 0~1."""
    뚜렷 = min(1.0, 0.55 + 0.15 * 어긋난줄수)
    return round(max(0.0, min(1.0, 짝점수)) * 뚜렷, 3)


def 후보뽑기(시안, 개발, 문턱=0.5):
    M = 짝맞추기(시안, 개발, 문턱)
    fig, devEls, 짝 = M["fig"], M["devEls"], M["pairs"]

    쓴시안 = {p["fi"] for p in 짝}
    쓴개발 = {p["di"] for p in 짝}
    짝지은시안상자 = [fig[p["fi"]]["box"] for p in 짝]
    짝지은개발상자 = [devEls[p["di"]]["box"] for p in 짝]
    남은개발 = [d for di, d in enumerate(devEls) if di not in 쓴개발]

    # 개발에만 있는 것: 배경이나 테두리가 있어 '눈에 보이는' 것만. 이미 짝지은 상자 안에 든 것은 뺀다.
    더있음 = [d for d in 남은개발
              if ((d["style"].get("backgroundColor") and d["style"]["backgroundColor"] != "rgba(0, 0, 0, 0)")
                  or d["style"].get("borderWidth", 0) > 0)
              and not _안에들어있나(d["box"], 짝지은개발상자)]
    빠짐 = [f for fi, f in enumerate(fig)
            if fi not in 쓴시안 and not _안에들어있나(f["box"], 짝지은시안상자)]

    폭다름 = bool(시안["meta"].get("artboardWidth") and 개발["meta"].get("artboardWidth")
                and abs(시안["meta"]["artboardWidth"] - 개발["meta"]["artboardWidth"]) > 4)

    후보, 주의, 밀림, 일치수 = [], [], [], 0
    for p in 짝:
        f, d = fig[p["fi"]], devEls[p["di"]]
        내려감 = d["box"]["y"] - f["box"]["y"]
        밀림있음 = 내려감 > 6 and any(x["box"]["y"] < d["box"]["y"] for x in 남은개발)
        결과 = 값견주기(f, d, 밀림있음, 폭다름)
        어긋난줄 = [r for r in 결과["rows"]
                  if r["j"] != "pass" and not r.get("cascade") and not r.get("deferred")]
        한건 = {
            "갈래": "값다름",
            "시안id": f.get("id"), "개발id": d.get("id"),
            "이름": 짧은시안이름(f),
            "개발자리": _개발자리(d),
            "box": f["box"], "devBox": d["box"],
            "짝점수": p["s"],
            "신뢰도": _신뢰도(p["s"], len(어긋난줄)),
            "상태": 결과["status"],
            "다른곳": [{"속성": r["label"], "시안": r["a"], "개발": r["b"]} for r in 어긋난줄],
            "rows": 결과["rows"],
        }
        if 결과["status"] == "fail":
            후보.append(한건)
        elif 결과["status"] == "warn":
            주의.append(한건)
        elif 결과["hasCascade"]:
            밀림.append(한건)
        else:
            일치수 += 1

    for d in 더있음:
        후보.append({"갈래": "더있음", "시안id": None, "개발id": d.get("id"),
                     "이름": 짧은개발이름(d), "개발자리": _개발자리(d), "box": None, "devBox": d["box"],
                     "짝점수": None, "신뢰도": 0.5, "상태": "fail",
                     "다른곳": [{"속성": "구조", "시안": "없음", "개발": "있음"}], "rows": []})
    for f in 빠짐:
        후보.append({"갈래": "빠짐", "시안id": f.get("id"), "개발id": None,
                     "이름": 짧은시안이름(f), "개발자리": None, "box": f["box"], "devBox": None,
                     "짝점수": None, "신뢰도": 0.5, "상태": "fail",
                     "다른곳": [{"속성": "구조", "시안": "있음", "개발": "없음"}], "rows": []})

    return {
        "후보": 후보,
        "주의": 주의,
        "밀림": 밀림,
        "셈": {"후보": len(후보), "값다름": len(후보) - len(더있음) - len(빠짐),
              "더있음": len(더있음), "빠짐": len(빠짐),
              "주의": len(주의), "밀림": len(밀림), "일치": 일치수,
              "짝": len(짝), "시안요소": len(fig), "개발요소": len(devEls)},
        "폭다름": 폭다름,
        "meta": {"시안": 시안.get("meta", {}), "개발": 개발.get("meta", {})},
    }
