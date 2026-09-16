#!/usr/bin/env python3
"""양면 시험 — 규칙 하나를 두 쪽에서 본다.

규칙을 넣으면 **드러나야 할 것**이 드러나는지, 그리고 비슷하게 생겼지만
**그대로 접혀 있어야 할 것**이 접혀 있는지를 함께 본다. 한 쪽만 보면
"볼 것이 줄었다"는 말이 좋은 소식인지 오류를 덮은 것인지 갈라지지 않는다.

시험지 한 장은 `시험지/양면/<제안번호>.json`. 재는 것은 사람이 아니라
공식 측정이 남긴 결과 파일(`규칙장부/측정/<측정번호>/<화면>.json`)이다.

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
            한줄 = {"화면": 이름, "글자": 한건["글자"], "까닭": 한건.get("까닭", "")}
            if r is None or 이름 not in 화면들:
                한줄["판정"] = "판정 불가"
                한줄["말"] = "그 화면 결과가 없다"
                막힘 = True
            else:
                요소들 = 글자의요소(시험지방 / "세트" / 화면들[이름]["요소"], 한건["글자"])
                if not 요소들:
                    한줄["판정"] = "판정 불가"
                    한줄["말"] = "시안에서 그 글자를 찾지 못했다"
                    막힘 = True
                else:
                    보임, 전부 = 보이는후보(r, 요소들)
                    한줄["보이는 후보"] = [f"#{c['no']} {c.get('label')}" for c in 보임]
                    한줄["접힌 후보"] = len(전부) - len(보임)
                    한줄["판정"] = "맞음" if bool(보임) == 바라는것 else "틀림"
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
            print(f"  {표} {h['화면']:8s} {h['글자']}  →  {뒷말}")
    print(f"판정: {본것['판정']}")
    print(f"적은 자리: {둘곳.relative_to(뿌리)}")
    return 0 if 본것["판정"] == "두 쪽 다 맞음" else 1


if __name__ == "__main__":
    raise SystemExit(main())
