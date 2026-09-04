#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2.1 — AI는 글자·모양만 읽고, 색은 코드가 픽셀로 잰다.
(v2에서 AI가 안내용 빨간 네모를 '글자색 빨강'으로 읽어 헛경보를 낸 것을 고침)"""
import json, os, re, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vlm_triage2 import norm

COLOR_GAP = 42          # 잉크색 차이 이 이상이면 '색 다름'
INK_MARGIN = 60         # 배경보다 이만큼 어두우면 잉크로 본다


def ink_color(img, box):
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    p = img.crop((x, y, x + w, y + h)).convert("RGB")
    px = list(p.getdata())
    if not px:
        return None
    lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
    bg = sorted(lum)[int(len(lum) * 0.9)]          # 밝은 쪽 = 배경
    ink = [c for c, l in zip(px, lum) if l < bg - INK_MARGIN]
    if len(ink) < 8:
        return None
    n = len(ink)
    return tuple(round(sum(c[i] for c in ink) / n) for i in range(3))


def dist(a, b):
    return max(abs(a[i] - b[i]) for i in range(3)) if a and b else 0


def name(c):
    if not c:
        return "(읽지 못함)"
    r, g, b = c
    if max(c) - min(c) < 28:
        return "검정" if r < 90 else ("회색" if r < 190 else "밝은 회색")
    if r > g and r > b:
        return "빨강 계열"
    if b > r and b > g:
        return "파랑 계열"
    if g > r and g > b:
        return "초록 계열"
    return "#%02X%02X%02X" % c


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else "findid"
    design = Image.open(sys.argv[2] if len(sys.argv) > 2 else "design_1920x1080.png")
    dev = Image.open(sys.argv[3] if len(sys.argv) > 3 else "dev_1920x934.png")
    rule = {c["no"]: c for c in json.load(open(case + ".json"))["candidates"]}
    rows = json.load(open("vlm2_%s.json" % case))
    for r in rows:
        c = rule[r["no"]]
        at, bt = norm(r["design_read"].get("text")), norm(r["dev_read"].get("text"))
        ash, bsh = norm(r["design_read"].get("shape")), norm(r["dev_read"].get("shape"))
        ca, cb = ink_color(design, c["designBox"]), ink_color(dev, c["rawBox"])
        # 룰 엔진이 이미 '가변(데이터에 따라 바뀌는 자리)'으로 표시한 후보는
        # 글자 내용이 달라도 오류로 세지 않는다. 색·모양만 본다.
        varying = "가변" in ((c.get("policy") or "") + " " + (c.get("detail") or ""))
        r["varying"] = varying
        gap = dist(ca, cb)
        r["design_color"], r["dev_color"], r["color_gap"] = name(ca), name(cb), gap
        if varying:
            if gap >= COLOR_GAP:
                v, why = "차이있음", "가변 자리지만 색이 다름: %s → %s (차이 %d)" % (name(ca), name(cb), gap)
            elif ash and bsh and ash != bsh:
                v, why = "차이있음", "가변 자리지만 모양이 다름: %s → %s" % (ash, bsh)
            else:
                v, why = "차이없음", "데이터가 바뀌는 자리 — 내용 차이는 오류로 세지 않음 (“%s” → “%s”)" % (at or ash, bt or bsh)
        elif at or bt:
            if at != bt:
                v, why = ("차이있음",
                          ("띄어쓰기가 다름: “%s” → “%s”" % (at, bt))
                          if at.replace(" ", "") == bt.replace(" ", "")
                          else "글자가 다름: “%s” → “%s”" % (at or "(없음)", bt or "(없음)"))
            elif gap >= COLOR_GAP:
                v, why = "차이있음", "글자는 같은데 색이 다름: %s → %s (차이 %d)" % (name(ca), name(cb), gap)
            else:
                v, why = "차이없음", "글자가 같음: “%s”" % at
        elif ash or bsh:
            if ash != bsh:
                v, why = "차이있음", "모양이 다름: %s → %s" % (ash or "(없음)", bsh or "(없음)")
            elif gap >= COLOR_GAP:
                v, why = "차이있음", "모양은 같은데 색이 다름: %s → %s (차이 %d)" % (name(ca), name(cb), gap)
            else:
                v, why = "차이없음", "모양이 같음: %s" % ash
        else:
            v, why = "판단불가", "양쪽 모두 읽어낸 것이 없음"
        r["verdict"], r["reason"] = v, why
        print("#%-2d %-9s %-4s %-6s  %s" % (r["no"], r["kind"],
              "가변" if varying else "고정", v, why[:64]))
    json.dump(rows, open("vlm21_%s.json" % case, "w"), ensure_ascii=False, indent=1)
    print("\n저장: vlm21_%s.json (AI 재호출 없음 — 읽은 값 재사용)" % case)


if __name__ == "__main__":
    main()
