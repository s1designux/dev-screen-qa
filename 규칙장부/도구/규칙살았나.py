#!/usr/bin/env python3
"""규칙이 아직 살았나 — 양면 시험지 전부를 한 성적에 대고 한 번에 본다.

양면 시험은 규칙마다 한 장씩 있는데, 지금까지는 그 규칙을 만들 때 한 번 돌리고 끝이었다.
그래서 **나중에 다른 것을 고치다 그 규칙이 죽어도 아무도 모른다.** 이 도구는 있는 시험지를
모두 같은 성적에 대고 돌려, 어느 규칙이 아직 짚고 있고 어느 규칙이 조용해졌는지 한 줄씩 보인다.

재지 않는다 — 공식 측정이 이미 남긴 결과만 읽는다. 성적을 새로 만들지 않는다.

    python3 규칙장부/도구/규칙살았나.py <측정번호>
    python3 규칙장부/도구/규칙살았나.py <측정번호> --견줄것 <옛 측정번호>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
시험지방 = 뿌리 / "시험지"
측정방 = 뿌리 / "규칙장부" / "측정"

건너뛰는장 = {"보기", "틀시험"}  # 틀이 도는지 보는 가짜 시험지 — 규칙이 아니다


def 양면모듈():
    길 = Path(__file__).resolve().parent / "양면시험.py"
    틀 = importlib.util.spec_from_file_location("양면시험", 길)
    것 = importlib.util.module_from_spec(틀)
    틀.loader.exec_module(것)
    return 것


def 한장보기(양면, 제안: str, 측정번호: str) -> dict:
    try:
        r = 양면.보기(제안, 측정번호)
    except Exception as 잘못:
        return {"제안": 제안, "판정": "판정 불가", "말": f"돌리다 막혔다: {잘못}"}
    드 = r["드러나야 할 것"]
    접 = r["접혀 있어야 할 것"]
    한줄 = {"제안": 제안, "판정": r["판정"],
          "드러나야 할 것": f"{sum(1 for h in 드 if h['판정'] == '맞음')}/{len(드)}",
          "접혀 있어야 할 것": f"{sum(1 for h in 접 if h['판정'] == '맞음')}/{len(접)}"}
    틀린것 = [f"{h['화면']} {h.get('자리') or h.get('글자')}"
           for h in 드 + 접 if h["판정"] == "틀림"]
    못잰것 = [f"{h['화면']} {h.get('자리') or h.get('글자')} — {h.get('말', '')}"
           for h in 드 + 접 if h["판정"] == "판정 불가"]
    if 틀린것:
        한줄["틀린 자리"] = 틀린것
    if 못잰것:
        한줄["못 잰 자리"] = 못잰것
    if not 드:
        한줄["빈 쪽"] = "드러나야 할 것이 비어 있다 — 이 규칙이 죽어도 이 시험으로는 모른다"
    return 한줄


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-2].strip())
        return 2
    측정번호 = sys.argv[1]
    견줄것 = ""
    if "--견줄것" in sys.argv:
        견줄것 = sys.argv[sys.argv.index("--견줄것") + 1]
    if not (측정방 / 측정번호).exists():
        print(f"그 측정을 찾지 못했습니다: {측정방 / 측정번호}\n→ 판정 불가")
        return 2

    양면 = 양면모듈()
    장들 = sorted(p.stem for p in (시험지방 / "양면").glob("*.json")
               if p.stem not in 건너뛰는장)

    본것 = {"측정번호": 측정번호, "본 것": [한장보기(양면, 제안, 측정번호) for 제안 in 장들]}
    옛것 = {}
    if 견줄것 and (측정방 / 견줄것).exists():
        옛것 = {h["제안"]: h["판정"] for h in
              (한장보기(양면, 제안, 견줄것) for 제안 in 장들)}
        본것["견줄것"] = 견줄것

    표 = {"두 쪽 다 맞음": "○ 살아 있음", "틀린 것 있음": "✗ 조용해졌다",
         "판정 불가": "? 못 쟀다"}
    print(f"성적 {측정번호} 에 대고 양면 시험지 {len(장들)}장을 다시 돌렸습니다.")
    if 견줄것:
        print(f"옛 성적 {견줄것} 과 나란히 봅니다.")
    print()
    for h in 본것["본 것"]:
        뒷말 = f"드러나야 {h.get('드러나야 할 것', '-')} · 접혀있어야 {h.get('접혀 있어야 할 것', '-')}"
        옛 = f"   (옛 {옛것[h['제안']]})" if h["제안"] in 옛것 and 옛것[h["제안"]] != h["판정"] else ""
        print(f"  {표.get(h['판정'], h['판정']):10s} {h['제안']:8s} {뒷말}{옛}")
        for 줄 in h.get("틀린 자리", []):
            print(f"       ✗ {줄}")
        for 줄 in h.get("못 잰 자리", []):
            print(f"       ? {줄}")
        if h.get("빈 쪽"):
            print(f"       · {h['빈 쪽']}")

    둘곳 = 측정방 / 측정번호 / "규칙살았나.json"
    둘곳.write_text(json.dumps(본것, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n적은 자리: {둘곳.relative_to(뿌리)}")
    죽은것 = [h["제안"] for h in 본것["본 것"] if h["판정"] != "두 쪽 다 맞음"]
    return 1 if 죽은것 else 0


if __name__ == "__main__":
    raise SystemExit(main())
