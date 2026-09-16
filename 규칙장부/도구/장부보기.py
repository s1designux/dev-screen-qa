#!/usr/bin/env python3
"""규칙 장부 읽기 — 지금 상태는 적지 않고 이력에서 계산한다.

    python3 규칙장부/도구/장부보기.py            # 제안별 지금 상태 한 줄씩
    python3 규칙장부/도구/장부보기.py P1          # 그 제안의 사건을 있는 그대로
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 장부적기 import 읽기  # noqa: E402

# 뒤에 오는 사건이 앞의 상태를 덮는다. 같은 날이면 목록 순서대로.
상태말 = {"등록": "올라옴", "보류": "보류", "거절": "거절", "관찰": "관찰",
        "승인": "범위 승인됨", "구현": "구현함", "측정": "성적 잼",
        "양면": "양면 봄", "검토": "검토 끝", "반영": "반영됨"}


def 지금상태(사건들: list[dict]) -> str:
    본것 = "올라옴"
    for e in 사건들:
        if e["사건"] in 상태말:
            본것 = 상태말[e["사건"]]
        if e["사건"] == "검토" and e.get("결과"):
            본것 = f"검토 {e['결과']}"
    return 본것


def main() -> int:
    모두 = 읽기()
    if not 모두:
        print("규칙 장부가 비어 있습니다.")
        return 0
    if len(sys.argv) > 1:
        제안 = sys.argv[1]
        for e in 읽기(제안):
            뒷말 = " · ".join(f"{k} {v}" for k, v in e.items()
                            if k not in ("때", "사건", "제안") and v)
            print(f"{e['때'][:16]}  {e['사건']:5s} {뒷말}")
        return 0

    묶음: dict[str, list[dict]] = {}
    for e in 모두:
        묶음.setdefault(e["제안"], []).append(e)
    print(f"{'제안':8s} {'지금':10s} 한마디")
    for 제안, 사건들 in 묶음.items():
        첫 = next((e for e in 사건들 if e["사건"] == "등록"), 사건들[0])
        print(f"{제안:8s} {지금상태(사건들):10s} {str(첫.get('내용',''))[:64]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
