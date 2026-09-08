#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""어긋난 것 모으기 — 검수기 결과와 AI 읽기 결과를 맞대어 '규칙 후보'를 센다.

AI에게 "어떤 규칙이 필요하냐"고 묻지 않는다. AI는 글자를 읽었을 뿐이고,
여기서는 **코드가 세기만** 한다. 그래야 근거가 숫자로 남고 매번 같은 답이 나온다.

세 가지 어긋남:
  A. 못 봄     — AI는 글자가 다르다는데 검수기는 후보로도 못 냄 (엔진 구멍)
  B. 잘못 접힘 — 검수기가 냈는데 정책이 '가변'으로 접었고, 실제로는 글자가 다름 (정답이 숨음)
  C. 헛지적    — 검수기가 지적했는데 글자는 똑같음 (사람 시간 낭비)

사용:
  python3 rule_gap.py --engine stay-policy.json --read vlm_read_stay.json \
                      --elements elements_stay_full.json --out gap_stay.json
"""
import argparse, json, os, re, sys

norm = lambda s: re.sub(r"\s+", "", str(s or ""))


def load_elements(path):
    el = json.load(open(path, encoding="utf-8"))
    cols = el["cols"]
    out = {}
    for r in el["rows"]:
        o = dict(zip(cols, r))
        if o.get("kind") == "text" and str(o.get("text") or "").strip():
            out[o["id"]] = {"text": re.sub(r"\s+", " ", o["text"].strip()),
                            "box": [o["x"], o["y"], o["w"], o["h"]],
                            "name": o.get("name") or "", "chain": o.get("chain") or [],
                            "propRef": o.get("propRef") or ""}
    return out, el.get("frame", {}).get("name")


def place_hint(e):
    """이 글자가 '어떤 자리'에 있는지 — 규칙은 글자가 아니라 자리에 붙기 때문에 이것으로 묶는다."""
    names = []
    if e["propRef"]:
        names.append(str(e["propRef"]))
    if e["name"] and e["name"] != e["text"]:
        names.append(str(e["name"]))
    for c in (e["chain"] or [])[:3]:
        n = c if isinstance(c, str) else (c or {}).get("n")
        if n and not re.match(r"^(Frame|Group|Rectangle|Text|Instance|Component|Vector|Ellipse|Line)\s*\d*$", str(n), re.I):
            names.append(str(n))
    return " / ".join(names[:3]) or "(이름 없음)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True, help="검수기 결과 JSON (run.js 출력)")
    ap.add_argument("--read", required=True, help="읽기 층 결과 JSON (vlm_read.py 출력)")
    ap.add_argument("--elements", required=True)
    ap.add_argument("--answers", help="정답 파일(있으면 '이 제안이 정답을 죽이는지' 함께 계산)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    els, screen = load_elements(a.elements)
    eng = json.load(open(a.engine, encoding="utf-8"))
    rd = json.load(open(a.read, encoding="utf-8"))
    if rd.get("skippedScreen") or "regions" not in rd:
        sys.exit("읽기 층이 건너뛴 화면입니다: " + rd.get("reason", ""))

    answers = set()
    if a.answers:
        k = json.load(open(a.answers, encoding="utf-8"))
        answers = {norm(x["design"]) for x in k["answers"]}

    # ── AI가 뭐라고 했나: 디자인 글자별로 '다름' / '같음'
    ai_diff, ai_same = {}, set()
    for g in rd["regions"]:
        for it in g["only_design"]:
            ai_diff[norm(it["t"])] = {"t": it["t"], "why": "개발화면에 없음", "region": g["region"]}
        for it in g["spacing"]:
            ai_diff[norm(it["design"])] = {"t": it["design"], "why": "띄어쓰기 다름 (→ %s)" % it["dev"], "region": g["region"]}
        for t in g["design"]:
            if norm(t) not in ai_diff:
                ai_same.add(norm(t))
    read_regions = {norm(t) for g in rd["regions"] for t in g["design"]}  # AI가 실제로 본 글자만 판단한다
    body_texts = {norm(t) for s in rd.get("skipped", []) for t in s.get("design", [])}  # 반복 줄(표 본문)로 판정돼 안 읽은 자리

    # ── 검수기는 뭐라고 했나: 디자인 노드별로 후보가 있었나 / 접혔나
    TEXTISH = {"text", "spacing", "missing"}  # 글자에 대한 지적만. 색·크기·위치·아이콘은 AI가 못 보므로 판단하지 않는다
    cand_by_node = {}
    for c in eng["candidates"]:
        for nid in (c.get("designNodeIds") or []):
            cand_by_node.setdefault(nid, []).append(c)

    A, B, C = [], [], []
    for nid, e in els.items():
        n = norm(e["text"])
        if n not in read_regions or n in body_texts:
            continue  # AI가 안 읽었거나, 표 본문으로 판정된 자리는 판단하지 않는다
        cands = cand_by_node.get(nid, [])
        folded = [c for c in cands if c.get("status") == "variable"]
        shown = [c for c in cands if c.get("status") != "variable"]
        row = {"text": e["text"], "nodeId": nid, "box": e["box"], "place": place_hint(e),
               "policy": (cands[0].get("policy") if cands else None),
               "isAnswer": n in answers}
        if n in ai_diff:
            row["ai"] = ai_diff[n]["why"]
            if not cands:
                A.append(row)
            elif folded and not shown:
                B.append(row)
        elif n in ai_same and [c for c in shown if c.get("kind") in TEXTISH]:
            row["ai"] = "글자는 똑같음"
            row["label"] = [c for c in shown if c.get("kind") in TEXTISH][0].get("label")
            C.append(row)

    def group(rows):
        g = {}
        for r in rows:
            key = (r["place"], r.get("policy") or "-")
            g.setdefault(key, []).append(r)
        return sorted(g.items(), key=lambda kv: -len(kv[1]))

    res = {"screen": screen, "engine": os.path.basename(a.engine), "read": os.path.basename(a.read),
           "counts": {"못 봄": len(A), "잘못 접힘": len(B), "헛지적": len(C)},
           "못 봄": A, "잘못 접힘": B, "헛지적": C,
           "묶음": {k: [{"자리": p, "판정": pol, "건수": len(v),
                         "정답 포함": sum(1 for x in v if x["isAnswer"]),
                         "예": [x["text"] for x in v[:6]]}
                        for (p, pol), v in group(rows)]
                    for k, rows in (("못 봄", A), ("잘못 접힘", B), ("헛지적", C))}}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)

    print("화면: %s" % screen)
    print("── 어긋난 것 ──")
    for k in ("못 봄", "잘못 접힘", "헛지적"):
        print("  %s %d건" % (k, res["counts"][k]))
    for k in ("못 봄", "잘못 접힘", "헛지적"):
        rows = res["묶음"][k]
        if not rows:
            continue
        print("\n[%s] 같은 자리끼리 묶음 — 규칙 후보" % k)
        for r in rows[:8]:
            mark = "  ⚠ 정답 %d건 포함" % r["정답 포함"] if r["정답 포함"] else ""
            print("  · %-38s %s  %d건%s" % (r["자리"][:38], r["판정"], r["건수"], mark))
            print("      예: %s" % " · ".join(r["예"]))
    print("\n저장: %s" % a.out)


if __name__ == "__main__":
    main()
