#!/usr/bin/env python3
"""규칙 장부에 사건 한 줄을 쌓는다 (append-only).

규칙 하나의 '지금 상태'는 따로 적지 않는다 — 사건을 쌓고 상태는 이력에서 계산한다.
고치거나 지우지 않는다. 잘못 적었으면 바로잡는 사건을 새로 쌓는다.

사건: 등록 · 승인 · 구현 · 측정 · 양면 · 검토 · 반영 · 보류 · 거절 · 관찰 · 바로잡음

    python3 규칙장부/도구/장부적기.py 승인 P1 --내용 "…" --승인번호 A-2026-0916-1 --적은이 river
    python3 규칙장부/도구/장부적기.py 측정 P1 --측정번호 003-20260916-1330 --적은이 프로그램
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
장부 = 뿌리 / "규칙장부" / "규칙장부.jsonl"
사건들 = ["등록", "승인", "구현", "측정", "양면", "검토", "반영", "보류", "거절", "관찰", "바로잡음"]


def 적기(사건: str, 제안: str, 때: str = "", **나머지) -> dict:
    한줄 = {"때": 때 or datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "사건": 사건, "제안": 제안}
    한줄.update({k: v for k, v in 나머지.items() if v})
    장부.parent.mkdir(parents=True, exist_ok=True)
    with open(장부, "a", encoding="utf-8") as f:
        f.write(json.dumps(한줄, ensure_ascii=False) + "\n")
    return 한줄


def 읽기(제안: str | None = None) -> list[dict]:
    if not 장부.exists():
        return []
    줄 = []
    for 글 in 장부.read_text(encoding="utf-8").splitlines():
        if not 글.strip():
            continue
        try:
            것 = json.loads(글)
        except json.JSONDecodeError:
            continue
        if 제안 is None or 것.get("제안") == 제안:
            줄.append(것)
    return 줄


def main() -> int:
    받기 = argparse.ArgumentParser(description="규칙 장부에 사건 한 줄 쌓기")
    받기.add_argument("사건", choices=사건들)
    받기.add_argument("제안", help="제안번호 (예: P1). 규칙번호와 다르다")
    받기.add_argument("--내용", default="")
    받기.add_argument("--규칙", default="", help="규칙번호(코드 자리·계층과 이어지는 번호)")
    받기.add_argument("--승인번호", default="")
    받기.add_argument("--측정번호", default="")
    받기.add_argument("--결과", default="", help="검토 사건의 결과 (통과 / 되돌림)")
    받기.add_argument("--적은이", default="", help="river · 운영 AI · 구현 AI · 독립 검토 AI · 프로그램")
    받기.add_argument("--때", default="", help="지난 일을 옮겨 적을 때만. 비우면 지금 시각")
    args = 받기.parse_args()

    한줄 = 적기(args.사건, args.제안, 때=args.때, 내용=args.내용, 규칙=args.규칙,
              승인번호=args.승인번호, 측정번호=args.측정번호,
              결과=args.결과, 적은이=args.적은이)
    print(json.dumps(한줄, ensure_ascii=False))
    print(f"적은 자리: {장부.relative_to(뿌리)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
