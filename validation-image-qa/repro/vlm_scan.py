#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""후보가 아니라 '모든 글자 요소'를 AI에게 읽혀 본다.
룰 엔진이 후보를 못 내면 AI도 볼 기회가 없다 — 그 한계를 확인하기 위한 실험."""
import json, os, sys
from PIL import Image
from vlm_triage2 import crop, call, READ, norm

case = sys.argv[1]; design = Image.open(sys.argv[2]); dev = Image.open(sys.argv[3])
E = json.load(open("elements_%s.json" % case))
col = {n: i for i, n in enumerate(E["cols"])}
rows = [r for r in E["rows"] if r[col["kind"]] == "text" and r[col["text"]].strip()]
model = json.load(open("%s.json" % case))["model"]
tx, ty = model.get("tx", 0), model.get("ty", 0)
print("글자 요소 %d개 · 정렬 보정 (%+d, %+d)\n" % (len(rows), tx, ty))
out = []
for r in rows:
    box = {"x": round(r[col["x"]]), "y": round(r[col["y"]]),
           "w": max(1, round(r[col["w"]])), "h": max(1, round(r[col["h"]]))}
    dbox = dict(box); vbox = {**box, "x": box["x"] + tx, "y": box["y"] + ty}
    a = norm(call(crop(design, dbox, 10), READ).get("text"))
    b = norm(call(crop(dev, vbox, 10), READ).get("text"))
    same = a == b
    out.append({"id": r[col["id"]], "design_text": r[col["text"]],
                "read_design": a, "read_dev": b, "same": same})
    if not same:
        print("  %-8s “%s”  →  “%s”" % (r[col["id"]], a, b))
json.dump(out, open("vlmscan_%s.json" % case, "w"), ensure_ascii=False, indent=1)
print("\n다르게 읽힌 것 %d / %d개" % (sum(1 for o in out if not o["same"]), len(out)))
