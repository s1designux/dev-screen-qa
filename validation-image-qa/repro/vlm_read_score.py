#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""읽기 층 결과 채점 — 사람이 확정한 정답이 다 남았는지, 사람이 볼 양이 얼마인지.
만든 사람이 스스로 '맞다'고 정하지 않는다. 정답 파일과 대조해 숫자만 낸다.
사용: python3 vlm_read_score.py vlm_read_stay.json answers_stay.json
"""
import json, re, sys

norm = lambda s: re.sub(r"\s+", "", str(s or ""))


def main():
    res = json.load(open(sys.argv[1], encoding="utf-8"))
    key = json.load(open(sys.argv[2], encoding="utf-8"))
    buckets = {"only_design": [], "only_dev": [], "spacing": [], "need_check": [], "dropped": []}
    for r in res["regions"]:
        for k in buckets:
            for it in r[k]:
                t = it.get("t") or it.get("design")
                buckets[k].append((r["region"], t, it))

    print("== 정답 %d건이 남았는지 ==" % len(key["answers"]))
    hit = 0
    for a in key["answers"]:
        found = None
        for k in a["expect"]:
            for region, t, it in buckets[k]:
                if norm(t) == norm(a["design"]):
                    found = (k, region)
                    break
            if found:
                break
        # 다른 칸에서라도 나왔는지(엉뚱한 칸으로 들어간 경우를 보이게)
        elsewhere = None
        if not found:
            for k in buckets:
                for region, t, it in buckets[k]:
                    if norm(t) == norm(a["design"]):
                        elsewhere = (k, region)
                        break
                if elsewhere:
                    break
        if found:
            hit += 1
            print("  ✅ #%d %s  “%s” → %s  [%s · %s]" % (a["no"], a["where"], a["design"], a["dev"], found[0], found[1]))
        elif elsewhere:
            print("  ⚠️  #%d %s  “%s” — 기대한 칸(%s)이 아니라 %s에 있음 [%s]"
                  % (a["no"], a["where"], a["design"], "/".join(a["expect"]), elsewhere[0], elsewhere[1]))
        else:
            print("  ❌ #%d %s  “%s” → %s  — 없음" % (a["no"], a["where"], a["design"], a["dev"]))
    print("  정답 %d/%d" % (hit, len(key["answers"])))

    print("\n== 오류가 아닌 것이 올라왔는지 ==")
    for n in key.get("not_errors", []):
        where = [k for k in ("only_design", "only_dev", "spacing")
                 for region, t, it in buckets[k] if norm(t) == norm(n["design"])]
        print("  %s “%s” (%s)%s" % ("⚠️ 올라옴" if where else "✅ 안 올라옴", n["design"], n["why"],
                                     "  ← " + where[0] if where else ""))

    s = res["summary"]
    print("\n== 사람이 볼 양 ==")
    print("  디자인에만 %d · 개발에만 %d · 띄어쓰기 %d · 확인 필요 %d  →  합계 %d건"
          % (s["only_design"], s["only_dev"], s["spacing"], s["need_check"],
             s["only_design"] + s["only_dev"] + s["spacing"] + s["need_check"]))
    print("  (버린 지어낸 글자 %d건 · 안 읽은 반복 줄 %d개 · AI %d회 · %d초)"
          % (s["dropped_hallucination"], s["skipped"], s["ai_calls"] + s["ai_cached"], s["seconds"]))


if __name__ == "__main__":
    main()
