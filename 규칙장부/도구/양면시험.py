#!/usr/bin/env python3
"""양면 시험 — 규칙 하나를 두 쪽에서 본다.

규칙을 넣으면 **드러나야 할 것**이 드러나는지, 그리고 비슷하게 생겼지만
**그대로 접혀 있어야 할 것**이 접혀 있는지를 함께 본다. 한 쪽만 보면
"볼 것이 줄었다"는 말이 좋은 소식인지 오류를 덮은 것인지 갈라지지 않는다.

시험지 한 장은 `시험지/양면/<제안번호>.json`. 재는 것은 사람이 아니라
공식 측정이 남긴 결과 파일(`규칙장부/측정/<측정번호>/<화면>.json`)이다.

자리를 적는 길이 둘이다 (한 건에 하나만 적는다):

- `"글자": "로그인"` — 시안에서 그 글자를 가진 요소를 찾아, 그 요소를 가리키는 후보를 본다.
- `"네모": {"x":1149,"y":234,"w":18,"h":16}` — **개발 촬영본 그림 위의 자리**로 적는다.
  시안에 아예 없는 것(개발에만 생긴 단추 같은 것)은 글자로 찾을 수 없어 이 길로 적는다.
  후보의 개발 좌표(rawBox)가 이 네모 안에 절반 넘게 들어오면 '그 자리에 있다'고 센다.
  네모는 넉넉하게 그린다 — 좁게 그리면 핀이 몇 픽셀 어긋나도 못 찾는다.
  `"이름표": "디자인에 없는"` 을 함께 적으면 그 말이 든 후보만 센다(다른 규칙이 우연히
  같은 자리를 짚어 시험이 통과하는 것을 막는다).

    python3 규칙장부/도구/양면시험.py <제안번호> <측정번호>
"""
from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
시험지방 = 뿌리 / "시험지"
측정방 = 뿌리 / "규칙장부" / "측정"

겹침문턱 = 0.5  # 후보 네모의 절반 넘게 들어와야 '그 자리'로 센다


def 화면목록() -> dict:
    목록 = json.loads((시험지방 / "목록.json").read_text(encoding="utf-8"))
    return {c["이름"]: c for c in 목록["화면"]}


def 글자의요소(요소파일: Path, 글자: str) -> list[str]:
    것 = json.loads(요소파일.read_text(encoding="utf-8"))
    줄 = 것.get("native")
    if 줄 is not None:
        return [e.get("id") for e in 줄
                if e.get("kind") == "text" and str(e.get("text") or "").strip() == 글자]
    칸 = 것["cols"]
    본 = []
    for r in 것["rows"]:
        d = dict(zip(칸, r))
        if d.get("kind") == "text" and str(d.get("text") or "").strip() == 글자:
            본.append(d.get("id"))
    return 본


def 보이는후보(결과: dict, 요소들: list[str]):
    본 = []
    for c in 결과.get("candidates") or []:
        if set(c.get("designNodeIds") or []) & set(요소들):
            본.append(c)
    return [c for c in 본 if c.get("status") not in ("variable", "excluded")], 본


def 겹친비율(후보네모: dict, 적은네모: dict) -> float:
    """후보의 개발 좌표가 적어 둔 네모 안에 얼마나 들어왔나 (후보 넓이를 1로 본다)."""
    try:
        ax, ay = float(후보네모["x"]), float(후보네모["y"])
        aw, ah = float(후보네모["w"]), float(후보네모["h"])
        bx, by = float(적은네모["x"]), float(적은네모["y"])
        bw, bh = float(적은네모["w"]), float(적은네모["h"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    가로 = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    세로 = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    return (가로 * 세로) / (aw * ah)


def 그자리후보(결과: dict, 네모: dict, 이름표: str = ""):
    """적어 둔 네모 자리에 놓인 후보. (센 것, 근처에 있던 것 전부)"""
    닿은것 = []
    for c in 결과.get("candidates") or []:
        raw = c.get("rawBox")
        if not isinstance(raw, dict):
            continue
        비율 = 겹친비율(raw, 네모)
        if 비율 <= 0:
            continue
        닿은것.append((c, 비율))
    센것 = [(c, 비) for c, 비 in 닿은것
           if 비 >= 겹침문턱
           and c.get("status") not in ("variable", "excluded")
           and (not 이름표 or 이름표 in str(c.get("label") or ""))]
    return 센것, 닿은것


def 화면결과(잰방: Path, 이름: str):
    """공식 측정이 남긴 화면별 결과. 낱장이 없으면 묶음(원본결과.tar.gz)에서 꺼내 읽는다."""
    낱장 = 잰방 / "화면별" / f"{이름}.json"
    if not 낱장.exists():
        낱장 = 잰방 / f"{이름}.json"
    if 낱장.exists():
        return json.loads(낱장.read_text(encoding="utf-8"))
    묶음 = 잰방 / "원본결과.tar.gz"
    if 묶음.exists():
        with tarfile.open(묶음, "r:gz") as t:
            안 = t.extractfile(f"{이름}.json")
            if 안 is not None:
                return json.loads(안.read().decode("utf-8"))
    return None


def 자리적기(한건: dict) -> str:
    if 한건.get("글자"):
        return str(한건["글자"])
    네모 = 한건.get("네모") or {}
    꼬리 = f" · 이름표 '{한건['이름표']}'" if 한건.get("이름표") else ""
    return (f"네모({네모.get('x')},{네모.get('y')} "
            f"{네모.get('w')}×{네모.get('h')}){꼬리}")


def 한건보기(한건: dict, 결과: dict, 화면정보: dict, 바라는것: bool) -> dict:
    """한 줄을 잰다. 글자로 적은 것과 네모로 적은 것을 갈라 본다."""
    한줄 = {"화면": 한건["화면"], "자리": 자리적기(한건), "까닭": 한건.get("까닭", "")}
    if 한건.get("글자"):
        한줄["글자"] = 한건["글자"]

    if 한건.get("글자") and 한건.get("네모"):
        한줄["판정"] = "판정 불가"
        한줄["말"] = "글자와 네모를 함께 적었다 — 한 건에 하나만 적는다"
        return 한줄

    if 한건.get("네모"):
        네모 = 한건["네모"]
        if not all(k in 네모 for k in ("x", "y", "w", "h")):
            한줄["판정"] = "판정 불가"
            한줄["말"] = "네모에 x·y·w·h 가 다 있어야 한다"
            return 한줄
        센것, 닿은것 = 그자리후보(결과, 네모, str(한건.get("이름표") or ""))
        한줄["보이는 후보"] = [f"#{c['no']} {c.get('label')} ({비:.0%} 들어옴)" for c, 비 in 센것]
        한줄["그 자리에 닿은 후보 전부"] = [
            f"#{c['no']} {c.get('label')} [{c.get('status')}] ({비:.0%} 들어옴)"
            for c, 비 in sorted(닿은것, key=lambda t: -t[1])]
        한줄["판정"] = "맞음" if bool(센것) == 바라는것 else "틀림"
        if not 센것 and not 닿은것:
            한줄["말"] = "그 네모 자리에 닿은 후보가 하나도 없다"
        return 한줄

    if not 한건.get("글자"):
        한줄["판정"] = "판정 불가"
        한줄["말"] = "글자도 네모도 적혀 있지 않다"
        return 한줄

    요소들 = 글자의요소(시험지방 / "세트" / 화면정보["요소"], 한건["글자"])
    if not 요소들:
        한줄["판정"] = "판정 불가"
        한줄["말"] = "시안에서 그 글자를 찾지 못했다"
        return 한줄
    보임, 전부 = 보이는후보(결과, 요소들)
    한줄["보이는 후보"] = [f"#{c['no']} {c.get('label')}" for c in 보임]
    한줄["접힌 후보"] = len(전부) - len(보임)
    한줄["판정"] = "맞음" if bool(보임) == 바라는것 else "틀림"
    return 한줄


def 보기(제안번호: str, 측정번호: str) -> dict:
    시험 = json.loads((시험지방 / "양면" / f"{제안번호}.json").read_text(encoding="utf-8"))
    화면들 = 화면목록()
    잰방 = 측정방 / 측정번호
    결과모음: dict[str, dict] = {}

    def 결과(이름: str):
        if 이름 not in 결과모음:
            결과모음[이름] = 화면결과(잰방, 이름)
        return 결과모음[이름]

    장 = 시험지방 / "양면" / f"{제안번호}.json"
    본것 = {"제안": 제안번호, "측정번호": 측정번호,
           "양면시험지지문": hashlib.sha256(장.read_bytes()).hexdigest(),
           "드러나야 할 것": [], "접혀 있어야 할 것": [], "판정": "판정 불가"}
    막힘 = False
    for 쪽, 바라는것 in (("드러나야 할 것", True), ("그대로 접혀 있어야 할 것", False)):
        적을곳 = "드러나야 할 것" if 바라는것 else "접혀 있어야 할 것"
        for 한건 in 시험.get(쪽, []):
            이름 = 한건["화면"]
            r = 결과(이름)
            if r is None or 이름 not in 화면들:
                한줄 = {"화면": 이름, "자리": 자리적기(한건), "까닭": 한건.get("까닭", ""),
                      "판정": "판정 불가", "말": "그 화면 결과가 없다"}
                막힘 = True
            else:
                한줄 = 한건보기(한건, r, 화면들[이름], 바라는것)
                if 한줄["판정"] == "판정 불가":
                    막힘 = True
            본것[적을곳].append(한줄)

    모두 = 본것["드러나야 할 것"] + 본것["접혀 있어야 할 것"]
    if 막힘 or not 모두:
        본것["판정"] = "판정 불가"
    else:
        본것["판정"] = "두 쪽 다 맞음" if all(h["판정"] == "맞음" for h in 모두) else "틀린 것 있음"
    return 본것


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    제안번호, 측정번호 = sys.argv[1], sys.argv[2]
    장 = 시험지방 / "양면" / f"{제안번호}.json"
    if not 장.exists():
        print(f"양면 시험지를 찾지 못했습니다: {장}\n→ 판정 불가")
        return 2
    if not (측정방 / 측정번호).exists():
        print(f"그 측정을 찾지 못했습니다: {측정방 / 측정번호}\n→ 판정 불가")
        return 2

    본것 = 보기(제안번호, 측정번호)
    둘곳 = 측정방 / 측정번호 / f"양면-{제안번호}.json"
    둘곳.write_text(json.dumps(본것, ensure_ascii=False, indent=2), encoding="utf-8")

    for 쪽 in ("드러나야 할 것", "접혀 있어야 할 것"):
        print(f"[{쪽}]")
        for h in 본것[쪽]:
            표 = {"맞음": "○", "틀림": "✗", "판정 불가": "?"}[h["판정"]]
            뒷말 = ", ".join(h.get("보이는 후보") or []) or h.get("말") or "보이는 후보 없음"
            print(f"  {표} {h['화면']:8s} {h['자리']}  →  {뒷말}")
    print(f"판정: {본것['판정']}")
    print(f"적은 자리: {둘곳.relative_to(뿌리)}")
    return 0 if 본것["판정"] == "두 쪽 다 맞음" else 1


if __name__ == "__main__":
    raise SystemExit(main())
