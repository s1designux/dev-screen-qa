#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""피그마에서 조각으로 받아온 요소 목록(파이프 구분)을 run.js가 읽는 elements JSON으로 조립한다.
부모 이름 사슬(chain)은 전송량을 줄이려고 안 받고, 여기서 parentId를 타고 올라가 복원한다.
사용: python3 extract/assemble.py <접두사> <출력파일>
     예) python3 extract/assemble.py route elements_route.json
"""
import glob, json, os, sys

pre, out = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
meta = open(os.path.join(here, pre + "_meta.txt"), encoding="utf-8").read().strip()
fid, fname, fw, fh = meta.replace("frame=", "").split("|")

FIELDS = ["id", "type", "kind", "depth", "parentId", "x", "y", "w", "h",
          "fill", "stroke", "strokeWidth", "radius", "text", "fontSize", "fontWeight", "color", "name", "propRef"]
NUM = {"depth", "x", "y", "w", "h", "strokeWidth", "radius", "fontSize", "fontWeight"}

rows = {}
for path in glob.glob(os.path.join(here, pre + "_*.txt")):
    if path.endswith("_meta.txt"):
        continue
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != len(FIELDS):
            sys.exit("칸 수가 다릅니다(%d개, %d개여야 함): %s" % (len(parts), len(FIELDS), line[:80]))
        o = {}
        for k, v in zip(FIELDS, parts):
            if k in NUM:
                if v == "":
                    o[k] = None
                else:
                    f = float(v)
                    o[k] = int(f) if f == int(f) else f
            else:
                o[k] = v
        rows[int(o["id"])] = o

ids = sorted(rows)
missing = [i for i in range(max(ids) + 1) if i not in rows]
if missing:
    sys.exit("빠진 줄: %s" % missing[:20])

def chain_of(i):
    """부모 이름 사슬 — 가까운 순서로 4개까지(code.js의 chain과 같은 뜻)."""
    out, cur = [], rows[i]["parentId"]
    while cur != "" and len(out) < 4:
        p = rows[int(cur)]
        out.append({"n": p["name"], "t": p["type"]})
        cur = p["parentId"]
    return out

COLS = ["id", "type", "kind", "depth", "parentId", "x", "y", "w", "h", "fill", "stroke",
        "strokeWidth", "radius", "text", "fontSize", "fontWeight", "color", "name", "chain", "propRef"]
data = {"frame": {"id": fid, "name": fname, "width": float(fw), "height": float(fh)}, "cols": COLS, "rows": []}
for i in ids:
    o = rows[i]
    data["rows"].append([
        "n%d" % i, o["type"], o["kind"], o["depth"],
        ("n%d" % int(o["parentId"])) if o["parentId"] != "" else None,
        o["x"], o["y"], o["w"], o["h"],
        o["fill"] or None, o["stroke"] or None, o["strokeWidth"], o["radius"],
        o["text"], o["fontSize"], o["fontWeight"], o["color"] or None,
        o["name"], chain_of(i), o["propRef"] or None])

json.dump(data, open(out, "w"), ensure_ascii=False)
texts = sum(1 for r in data["rows"] if r[2] == "text")
print("%s — 요소 %d개(글자 %d개) · %s %sx%s" % (out, len(data["rows"]), texts, fname, fw, fh))
