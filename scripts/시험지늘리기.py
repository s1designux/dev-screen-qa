#!/usr/bin/env python3
"""시험화면후보/ 에 담아 둔 화면을 시험지에 넣는다 (사람이 정한 뒤에만 돈다).

시험지는 채점표라 함부로 고치지 않는다(`시험지/README.md`). 그래서 이 도구는
**river가 늘리기로 정했을 때만** 돌린다. 두 가지를 한다:

 1. `시험화면후보/` 의 시안·개발 그림과 시안 요소를 `시험지/세트/` 로 옮긴다
 2. `시험지/목록.json` 의 화면 목록 맨 뒤에 한 줄씩 더한다 (정답 목록은 건드리지 않는다)

넣고 나면 **시험지 지문이 바뀌어 앞서 잰 성적과 못 견준다.** 넣은 뒤에는 반드시
`규칙장부/도구/공식측정.py` 로 출발점을 다시 재고 그 번호를 장부에 남긴다.

    python3 scripts/시험지늘리기.py --볼것만        # 무엇이 들어갈지 보기만
    python3 scripts/시험지늘리기.py --넣는다
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[1]
후보방 = 뿌리 / "시험화면후보"
시험지방 = 뿌리 / "시험지"
세트방 = 시험지방 / "세트"
목록길 = 시험지방 / "목록.json"


def 후보들() -> list[dict]:
    본 = []
    for 요소 in sorted(후보방.glob("elements_*.json")):
        이름 = 요소.stem[len("elements_"):]
        시안 = sorted(후보방.glob(f"design_{이름}_*.png"))
        개발 = sorted(후보방.glob(f"dev_{이름}_*.png"))
        if not (시안 and 개발):
            print(f"  ! {이름}: 시안 또는 개발 그림이 없다 — 건너뛴다")
            continue
        본.append({"이름": 이름, "요소": 요소.name,
                   "시안": 시안[0].name, "개발": 개발[0].name})
    return 본


def main() -> int:
    받기 = argparse.ArgumentParser(description="시험지에 화면 더 넣기")
    받기.add_argument("--넣는다", action="store_true", help="실제로 넣는다")
    받기.add_argument("--볼것만", action="store_true", help="무엇이 들어갈지 보기만 한다")
    args = 받기.parse_args()

    if not 후보방.exists():
        sys.exit(f"넣을 것이 없습니다: {후보방}")
    목록 = json.loads(목록길.read_text(encoding="utf-8"))
    이미 = {c["이름"] for c in 목록["화면"]}
    넣을것 = [h for h in 후보들() if h["이름"] not in 이미]

    print(f"지금 시험 화면 {len(목록['화면'])}장 → 넣으면 {len(목록['화면']) + len(넣을것)}장")
    for h in 넣을것:
        print(f"  + {h['이름']:12s} {h['요소']}  {h['시안']}  {h['개발']}")
    if not 넣을것:
        print("새로 넣을 것이 없습니다.")
        return 0
    if not args.넣는다 or args.볼것만:
        print("\n보기만 했습니다. 실제로 넣으려면 --넣는다")
        return 0

    for h in 넣을것:
        for 칸 in ("요소", "시안", "개발"):
            shutil.copy2(후보방 / h[칸], 세트방 / h[칸])
        목록["화면"].append(h)
    글 = json.dumps(목록, ensure_ascii=False, indent=2) + "\n"
    # 화면 한 줄은 한 줄로 — 사람이 읽는 파일이라 줄이 흩어지지 않게 모은다
    글 = re.sub(r"\{\n\s+(\"이름\".*?)\n\s+\}", lambda m: "{" + re.sub(r"\s*\n\s*", " ", m.group(1)) + "}",
              글, flags=re.S)
    목록길.write_text(글, encoding="utf-8")
    print(f"\n넣었습니다. 이제 시험 화면 {len(목록['화면'])}장입니다.")
    print("→ 시험지 지문이 바뀌었습니다. 공식측정.py 로 출발점을 다시 재세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
