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


def 시험지읽기(제안: str) -> dict:
    장 = 시험지방 / "양면" / f"{제안}.json"
    if not 장.exists():
        return {}
    try:
        return json.loads(장.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def 죽으면걸리나(제안: str) -> str:
    """이 시험지가 **규칙이 없는 판에서 실제로 걸렸는지** 확인한 기록.

    시험지가 '두 쪽 다 맞음'이라고 해서 그 규칙이 살아 있다는 뜻은 아니다 — 규칙을 아예
    빼고 재도 맞을 수 있다(P24 가 그렇다: 그 시험지는 '과하게 번지지 않았나'만 가린다).
    그래서 시험지에 `"규칙 없는 판 확인"` 칸을 두고, 규칙을 뺀 판으로 재서 이 시험지가
    실제로 걸린 성적 번호를 적는다. 없으면 '확인 안 됨'으로 보인다.
    """
    return str(시험지읽기(제안).get("규칙 없는 판 확인") or "")


def 비운까닭(제안: str) -> str:
    """드러나는 쪽을 일부러 비운 시험지는 그 까닭을 적어 둔다.

    헛지적을 **없애는** 규칙은 새로 드러날 후보가 원래 없다(P23). 그런 시험지는
    접히는 쪽에 자리를 박아 두고 여기에 까닭을 적는다 — 적어 두지 않으면 '이 규칙이
    죽어도 모른다'고 짚는다.
    """
    return str(시험지읽기(제안).get("드러나는 쪽 비운 까닭") or "")


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
    한줄["규칙 없는 판 확인"] = 죽으면걸리나(제안) or "확인 안 됨"
    if not 드:
        까닭 = 비운까닭(제안)
        한줄["빈 쪽"] = (f"드러나는 쪽을 일부러 비웠다 — {까닭}" if 까닭
                     else "드러나야 할 것이 비어 있다 — 이 규칙이 죽어도 이 시험으로는 모른다")
        한줄["일부러 비웠나"] = bool(까닭)
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

    표 = {"두 쪽 다 맞음": "○ 맞음", "틀린 것 있음": "✗ 걸림",
         "판정 불가": "? 못 쟀다"}
    print(f"성적 {측정번호} 에 대고 양면 시험지 {len(장들)}장을 다시 돌렸습니다.")
    if 견줄것:
        print(f"옛 성적 {견줄것} 과 나란히 봅니다.")
    print()
    for h in 본것["본 것"]:
        뒷말 = f"드러나야 {h.get('드러나야 할 것', '-')} · 접혀있어야 {h.get('접혀 있어야 할 것', '-')}"
        옛 = f"   (옛 {옛것[h['제안']]})" if h["제안"] in 옛것 and 옛것[h["제안"]] != h["판정"] else ""
        확인 = h.get("규칙 없는 판 확인", "확인 안 됨")
        꼬리 = ("[규칙 빼고 재니 걸렸다 · " + 확인 + "]" if 확인[:1].isdigit()
              else "[규칙을 빼도 안 걸린다 — " + 확인.split(":", 1)[-1].strip() + "]" if 확인.startswith("안 됨")
              else "[가릴 규칙이 없다 — " + 확인.split(":", 1)[-1].strip() + "]" if 확인.startswith("해당 없음")
              else "[규칙을 빼도 걸리는지 확인 안 됨]")
        print(f"  {표.get(h['판정'], h['판정']):7s} {h['제안']:8s} {뒷말}{옛}")
        print(f"       {꼬리}")
        for 줄 in h.get("틀린 자리", []):
            print(f"       ✗ {줄}")
        for 줄 in h.get("못 잰 자리", []):
            print(f"       ? {줄}")
        if h.get("빈 쪽"):
            print(f"       · {h['빈 쪽']}")

    둘곳 = 측정방 / 측정번호 / "규칙살았나.json"
    둘곳.write_text(json.dumps(본것, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n적은 자리: {둘곳.relative_to(뿌리)}")
    확인들 = [str(h.get("규칙 없는 판 확인", "")) for h in 본것["본 것"]]
    센것 = sum(1 for v in 확인들 if v[:1].isdigit())
    안된것 = [h["제안"] for h, v in zip(본것["본 것"], 확인들) if v.startswith("안 됨")]
    없는것 = [h["제안"] for h, v in zip(본것["본 것"], 확인들) if v.startswith("해당 없음")]
    모름 = [h["제안"] for h, v in zip(본것["본 것"], 확인들)
          if not (v[:1].isdigit() or v.startswith("안 됨") or v.startswith("해당 없음"))]
    print(f"규칙을 빼면 실제로 걸리는 것이 확인된 시험지: {센것}장 / {len(확인들)}장")
    if 안된것:
        print(f"  · 규칙을 빼도 안 걸리는 시험지: {', '.join(안된것)} — 맞았다고 해서 그 규칙이 살았다는 뜻이 아니다")
    if 없는것:
        print(f"  · 가릴 규칙이 아예 없는 시험지: {', '.join(없는것)}")
    if 모름:
        print(f"  · 아직 확인 안 한 시험지: {', '.join(모름)}")
    죽은것 = [h["제안"] for h in 본것["본 것"] if h["판정"] != "두 쪽 다 맞음"]
    return 1 if 죽은것 else 0


if __name__ == "__main__":
    raise SystemExit(main())
