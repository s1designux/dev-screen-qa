#!/usr/bin/env python3
"""문지기 — 규칙 하나를 적용해도 되는지 프로그램이 막아 선다.

사람의 기억이나 "아까 쟀다"는 말로 넘어가지 못하게 한다. 다섯 가지를 본다:

 1. river의 **범위·기준 승인**(승인번호)이 장부에 있는가
 2. 승인 뒤에 잰 **공식 성적**이 있고 그 판정이 '잼'인가
 3. 그 측정에 **양면 시험** 결과가 붙어 있고 두 쪽 다 맞았는가
 4. **독립 검토**가 통과로 적혀 있는가
 5. 측정한 뒤에 **검수기·시험지가 바뀌지 않았는가** (바뀌었으면 다시 재야 한다)

문이 열려도 그것으로 끝이 아니다 — 마지막 **적용 승인은 river**가 한다.

    python3 규칙장부/도구/문지기.py <제안번호> [--엔진 engine/ui.html]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
시험지방 = 뿌리 / "시험지"
측정방 = 뿌리 / "규칙장부" / "측정"
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 장부적기 import 읽기  # noqa: E402


def 지문(경로: Path) -> str:
    h = hashlib.sha256()
    with open(경로, "rb") as f:
        for 덩이 in iter(lambda: f.read(1 << 20), b""):
            h.update(덩이)
    return h.hexdigest()


def 시험지지문() -> str:
    """공식측정과 같은 셈법 — `양면/` 은 빼고 잰다."""
    것 = {}
    for p in sorted(시험지방.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        길 = p.relative_to(시험지방)
        if 길.parts[0] == "양면":
            continue
        것[str(길)] = 지문(p)
    return hashlib.sha256(json.dumps(것, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def 보기(제안: str, 엔진: Path) -> dict:
    사건 = 읽기(제안)
    본것 = {"제안": 제안, "막는 것": [], "확인한 것": []}
    if not 사건:
        본것["막는 것"].append("장부에 이 제안이 없다")
        return 본것

    승인 = [e for e in 사건 if e["사건"] == "승인" and e.get("승인번호")]
    if not 승인:
        본것["막는 것"].append("범위·기준 승인(승인번호)이 없다")
    else:
        본것["확인한 것"].append(f"승인번호 {승인[-1]['승인번호']} ({승인[-1]['때']})")

    측정사건 = [e for e in 사건 if e["사건"] == "측정" and e.get("측정번호")]
    if 승인 and 측정사건:
        측정사건 = [e for e in 측정사건 if e["때"] >= 승인[-1]["때"]]
    if not 측정사건:
        본것["막는 것"].append("승인 뒤에 잰 공식 성적이 없다")
        return 본것

    측정번호 = 측정사건[-1]["측정번호"]
    잰것파일 = 측정방 / 측정번호 / "측정.json"
    if not 잰것파일.exists():
        본것["막는 것"].append(f"공식 성적 파일이 없다: 규칙장부/측정/{측정번호}/측정.json")
        return 본것
    잰것 = json.loads(잰것파일.read_text(encoding="utf-8"))
    본것["측정번호"] = 측정번호
    if 잰것.get("판정") != "잼":
        본것["막는 것"].append(f"공식 성적 판정이 '{잰것.get('판정')}' 이다")
    else:
        본것["확인한 것"].append(f"공식 성적 {측정번호} · 볼 것 {잰것.get('볼것합계')}"
                            + "".join(f" · 정답 {a['이름']} {a.get('산것')}/{a.get('전체')}"
                                      for a in 잰것.get("정답", [])))

    양면파일 = 측정방 / 측정번호 / f"양면-{제안}.json"
    if not 양면파일.exists():
        본것["막는 것"].append("양면 시험 결과가 그 측정에 붙어 있지 않다")
    else:
        양면 = json.loads(양면파일.read_text(encoding="utf-8"))
        장 = 시험지방 / "양면" / f"{제안}.json"
        if 양면.get("판정") != "두 쪽 다 맞음":
            본것["막는 것"].append(f"양면 시험 판정이 '{양면.get('판정')}' 이다")
        elif not 장.exists() or 양면.get("양면시험지지문") != 지문(장):
            본것["막는 것"].append("양면 시험지가 그 뒤에 바뀌었다 — 양면 시험을 다시 봐야 한다")
        else:
            본것["확인한 것"].append("양면 시험 두 쪽 다 맞음")

    검토 = [e for e in 사건 if e["사건"] == "검토" and e["때"] >= 측정사건[-1]["때"]]
    통과한검토 = [e for e in 검토 if e.get("결과") == "통과"]
    if not 통과한검토:
        본것["막는 것"].append("측정 뒤 독립 검토 통과가 장부에 없다")
    else:
        본것["확인한 것"].append(f"독립 검토 통과 ({통과한검토[-1]['때']})")

    지금엔진 = 지문(엔진)
    잰엔진 = (잰것.get("엔진") or {}).get("지문")
    if 지금엔진 != 잰엔진:
        본것["막는 것"].append("측정한 뒤 검수기가 바뀌었다 — 다시 재야 한다")
    else:
        본것["확인한 것"].append(f"검수기 그대로 ({지금엔진[:12]}…)")

    if 시험지지문() != 잰것.get("시험지지문"):
        본것["막는 것"].append("측정한 뒤 시험지가 바뀌었다 — 다시 재야 한다")
    else:
        본것["확인한 것"].append("시험지 그대로")

    return 본것


def main() -> int:
    받기 = argparse.ArgumentParser(description="문지기 — 적용해도 되는지 본다")
    받기.add_argument("제안", help="제안번호 (예: P1)")
    받기.add_argument("--엔진", default="engine/ui.html")
    args = 받기.parse_args()

    엔진 = Path(args.엔진)
    if not 엔진.is_absolute():
        엔진 = (뿌리 / 엔진).resolve()
    if not 엔진.exists():
        print(f"검수기를 찾지 못했습니다: {엔진}\n문 닫힘")
        return 2

    본것 = 보기(args.제안, 엔진)
    for 말 in 본것["확인한 것"]:
        print(f"  ○ {말}")
    for 말 in 본것["막는 것"]:
        print(f"  ✗ {말}")
    if 본것["막는 것"]:
        print("문 닫힘 — 위의 것을 채우기 전에는 적용하지 않는다.")
        return 1
    print("문 열림 — 남은 것은 river의 적용 승인 하나뿐이다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
