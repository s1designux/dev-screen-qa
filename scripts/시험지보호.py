#!/usr/bin/env python3
"""시험지 보호 — 채점표를 고치려는 손을 한 번 막아 선다 (PreToolUse 훅).

`시험지/` 는 정답·재현 세트·측정 도구·통과 기준이 있는 자리다. 성적이 나쁘게 나왔다고
채점표를 고치면 이 체계가 통째로 무너지므로, 고치는 도구가 그리로 향하면 막는다.
`시험지/양면/` 만 연다 — 규칙마다 시험지 한 장이 새로 늘어나는 자리다.

이 훅만으로 됐다고 보지 않는다(우회할 수 있다). 진짜 확인은 문지기의 **지문 대조**다.
"""
from __future__ import annotations

import json
import re
import sys

열린자리 = "시험지/양면/"
막는자리 = "시험지/"


def 막을것인가(입력: dict) -> str | None:
    이름 = 입력.get("tool_name") or ""
    것 = 입력.get("tool_input") or {}
    if 이름 in ("Edit", "Write", "NotebookEdit"):
        길 = str(것.get("file_path") or "")
        if 막는자리 in 길 and 열린자리 not in 길:
            return 길
    if 이름 == "Bash":
        명령 = str(것.get("command") or "")
        # 시험지 쪽으로 쓰기·지우기·옮기기가 향하는 꼴만 본다(읽기는 막지 않는다).
        # 한 낱말 안에서만 본다 — 여러 줄짜리 글 속에 '시험지/' 라는 말이 나오는 것까지 막으면
        # 문서를 쓰는 일이 통째로 막힌다.
        낱말 = r"""['"]?[^\s;|&'"]*시험지/[^\s;|&'"]*"""
        꼴들 = [r">>?\s*" + 낱말,
              r"\b(rm|mv|cp|tee|truncate|shred)\b[^\n;|&]*?" + 낱말,
              r"\bsed\b[^\n;|&]*?-i[^\n;|&]*?" + 낱말]
        for 꼴 in 꼴들:
            찾은것 = re.search(꼴, 명령)
            if 찾은것 and 열린자리 not in 찾은것.group(0):
                return 찾은것.group(0).strip()
    return None


def main() -> int:
    try:
        입력 = json.load(sys.stdin)
    except Exception:
        return 0
    걸린것 = 막을것인가(입력)
    if not 걸린것:
        return 0
    print(
        "[시험지 문지기] 시험지는 고치지 않는다 — 채점표다.\n"
        f"  막은 것: {걸린것}\n"
        "  고쳐야 할 까닭이 있으면 멈추고 river에게 올린다. "
        "고치면 앞서 잰 성적과 견줄 수 없고, 문지기가 '측정한 뒤 시험지가 바뀌었다'며 문을 닫는다.\n"
        "  규칙마다 새로 만드는 양면 시험지(시험지/양면/)는 열려 있다.",
        file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
