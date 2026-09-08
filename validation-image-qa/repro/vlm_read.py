#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""읽기 층 — 로컬 AI(Qwen2.5-VL)로 개발화면의 글자를 읽어 '검수할 내용'을 뽑는다.

역할 분담(로컬 AI 활용방안):
  검수기 = 겹치기·자 재기 / **AI = 눈(글자 읽기)만** / 정책 = 거르기 / 사람 = 확정.
AI에게 "같냐"고 묻지 않는다. "뭐라고 쓰여 있냐"만 묻고, 같고 다름은 이 코드가 판정한다.

vlm_region3.py와 다른 점(그게 체류시간 화면 전용이었던 이유를 없앴다):
  ① 읽을 구역을 손으로 안 적는다 — 디자인 글자 목록에서 가로 띠를 자동으로 만든다.
  ② 개발 쪽 밀림을 손으로 안 넣는다 — 검수기가 이미 낸 겹치기 값(tx/ty/s)을 그대로 쓴다.
  ③ 한 번 읽은 조각은 저장해둔다(코드를 고쳐도 다시 안 읽는다).
  ④ 결과를 화면과 무관한 같은 모양의 JSON으로 낸다.

사용:
  python3 vlm_read.py --elements elements_stay.json --dev dev_stay_1920x1081.png \
                      --align stay-policy.json --out vlm_read_stay.json
"""
import argparse, base64, hashlib, io, json, os, re, sys, time, urllib.request
from PIL import Image

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MODEL = os.environ.get("VLM_MODEL", "qwen2.5vl:7b")
CACHE_DIR = os.environ.get("VLM_CACHE", "vlm_read_cache")
SEC_PER_CALL = 11.0  # 실측(M1 Pro 16GB) — 예상 시간 안내용

# ── AI에게 묻는 말 (두 가지뿐: 넓게 읽기 / 좁은 조각 읽기)
WIDE = """이 그림에 보이는 글자를 전부 찾아, 각 글자가 있는 네모의 좌표를 함께 적으세요.
좌표는 [왼쪽x, 위y, 오른쪽x, 아래y]이고, 그림의 왼쪽 끝=0, 오른쪽 끝=1000, 위 끝=0, 아래 끝=1000인 비율값입니다. 위에서 아래, 왼쪽에서 오른쪽 순서로.
보이는 그대로 적고(띄어쓰기도 그대로), 없는 글자를 지어내지 마세요. 글자가 하나도 없으면 빈 목록을 답하세요.
JSON만: {"texts":[{"t":"글자","box":[x1,y1,x2,y2]}]}"""
NARROW = """이 작은 조각에 보이는 글자를 전부 적으세요. 보이는 그대로, 띄어쓰기도 그대로.
없는 글자를 지어내지 마세요. 글자가 하나도 없으면 빈 목록을 답하세요.
JSON만: {"texts":["...","..."]}"""


def norm(s):
    return re.sub(r"\s+", "", str(s or ""))


def squeeze(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def edit1(a, b):
    """한 글자 차이인가(오독 의심). 길이 차 2 이상이면 아님."""
    if abs(len(a) - len(b)) > 1:
        return False
    if a == b:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    lo, hi = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(hi)):
        if hi[:i] + hi[i + 1:] == lo:
            return True
    return False


# ── 로컬 AI 호출 (조각 그림 + 물음 → 글자). 같은 조각은 저장해둔 답을 쓴다.
_stats = {"calls": 0, "cached": 0, "sec": 0.0}


def ask(img, prompt, tag):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    key = hashlib.sha1(png + prompt.encode() + MODEL.encode()).hexdigest()
    path = os.path.join(CACHE_DIR, key + ".txt")
    if os.path.exists(path):
        _stats["cached"] += 1
        return open(path, encoding="utf-8").read()
    body = json.dumps({"model": MODEL, "stream": False,
                       "options": {"temperature": 0, "num_ctx": 4096},
                       "messages": [{"role": "user", "content": prompt,
                                     "images": [base64.b64encode(png).decode()]}]}).encode()
    t0 = time.time()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        raw = json.loads(r.read())["message"]["content"].strip()
    _stats["calls"] += 1
    _stats["sec"] += time.time() - t0
    if "```" in raw:
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    os.makedirs(CACHE_DIR, exist_ok=True)
    open(path, "w", encoding="utf-8").write(raw)
    return raw


def upscale(p):
    s = max(1, min(3, int(560 / max(1, p.height))))
    return p.resize((p.width * s, p.height * s), Image.LANCZOS) if s > 1 else p


def read_wide(img, box, split, tag):
    """띠를 좌우로 나눠(10% 겹쳐) 읽고 글자마다 원본 좌표를 붙인다."""
    piece = img.crop(box)
    w, h = piece.width, piece.height
    seg = w / split
    ov = int(seg * 0.10)
    found = []
    for i in range(split):
        L = max(0, int(seg * i) - ov)
        R = min(w, int(seg * (i + 1)) + ov)
        raw = ask(upscale(piece.crop((L, 0, R, h))), WIDE, "%s/wide%d" % (tag, i))
        # 답 모양이 들쭉날쭉하다({"texts":[..]} / 바로 [..] / 오타) — 정규식으로 항목만 건진다
        for m in re.finditer(r'"t"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"box"[^\[]*\[\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)', raw):
            t = m.group(1).strip()
            if not t:
                continue
            nx1, ny1, nx2, ny2 = [float(m.group(k)) for k in (2, 3, 4, 5)]
            pw = R - L
            found.append({"t": t, "box": [round(box[0] + L + nx1 / 1000 * pw), round(box[1] + ny1 / 1000 * h),
                                          round((nx2 - nx1) / 1000 * pw), round((ny2 - ny1) / 1000 * h)]})
    return found


def read_narrow(img, box, n, tag):
    """띠를 좁은 조각으로(절반씩 겹쳐) 잘라 각각 읽는다.
    환각은 넓은 틀에서 나오고 좁은 틀에서는 사라진다 — 그래서 이 결과가 검증용이 된다."""
    piece = img.crop(box)
    w = piece.width
    sw = w / (n - (n - 1) * 0.5)
    texts = []
    for i in range(n):
        L = int(i * sw * 0.5)
        R = min(w, int(L + sw))
        if R - L < 8:
            continue
        raw = ask(upscale(piece.crop((L, 0, R, piece.height))), NARROW, "%s/narrow%d" % (tag, i))
        texts += re.findall(r'"((?:[^"\\]|\\.)+)"', raw)
    return [t for t in texts if t.strip() and t.strip() != "texts"]


# ── 읽을 구역(가로 띠)을 디자인 글자에서 자동으로 만든다
def text_rows(items, gap):
    """세로로 겹치는 글자끼리 한 줄로 묶고, 아주 가까운 줄은 합친다."""
    items = sorted(items, key=lambda e: (e["y"], e["x"]))
    rows = []
    for e in items:
        placed = False
        for r in rows:
            ov = min(r["y2"], e["y"] + e["h"]) - max(r["y"], e["y"])
            if ov > 0.5 * min(r["y2"] - r["y"], e["h"]):
                r["items"].append(e)
                r["y"] = min(r["y"], e["y"])
                r["y2"] = max(r["y2"], e["y"] + e["h"])
                placed = True
                break
        if not placed:
            rows.append({"y": e["y"], "y2": e["y"] + e["h"], "items": [e]})
    rows.sort(key=lambda r: r["y"])
    merged = []
    for r in rows:
        if merged and r["y"] - merged[-1]["y2"] <= gap and (max(merged[-1]["y2"], r["y2"]) - merged[-1]["y"]) <= 64:
            merged[-1]["y2"] = max(merged[-1]["y2"], r["y2"])
            merged[-1]["items"] += r["items"]
        else:
            merged.append(dict(r, items=list(r["items"])))
    for r in merged:
        r["items"].sort(key=lambda e: e["x"])
        r["x"] = min(e["x"] for e in r["items"])
        r["x2"] = max(e["x"] + e["w"] for e in r["items"])
    return merged


def row_signature(r):
    """줄의 '모양' — 글자 개수와 칸의 가로 위치. 같으면 같은 종류의 줄로 본다."""
    return (len(r["items"]), tuple(round(e["x"] / 8) for e in r["items"]), round((r["y2"] - r["y"]) / 4))


def mark_repeats(rows, min_repeat):
    """표 본문처럼 같은 모양이 일정 간격으로 되풀이되는 줄은 첫 줄만 읽는다.
    (같은 모양 = 글자 칸 수가 같고 줄 간격이 일정. 값은 달라도 되고, 칸 위치는 조금 달라도 된다.)
    나머지는 '왜 안 읽었는지'를 남긴다 — 숨기는 게 아니라 읽기 비용을 줄이는 것."""
    # ① 칸 위치까지 똑같은 줄이 여러 개 (값이 같은 줄)
    same = {}
    for r in rows:
        same.setdefault(row_signature(r), []).append(r)
    for g in same.values():
        if len(g) >= min_repeat:
            g.sort(key=lambda r: r["y"])
            for r in g[1:]:
                r["skip"] = "같은 모양의 줄 %d개 중 첫 줄만 읽음(표 본문으로 보임)" % len(g)
    # ② 칸 수가 같고 줄 간격이 일정하게 이어지는 묶음 (값만 다른 표 본문)
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows):
            a, b, c = rows[j - 1], rows[j], rows[i]
            step = b["y"] - a["y"]
            if len(b["items"]) != len(c["items"]):
                break
            if abs((b["y2"] - b["y"]) - (c["y2"] - c["y"])) > 6:
                break
            if j - i >= 2 and abs(step - (rows[i + 1]["y"] - rows[i]["y"])) > 4:
                break
            j += 1
        if j - i >= min_repeat:
            for r in rows[i + 1:j]:
                if not r.get("skip"):
                    r["skip"] = "같은 칸 수·같은 간격으로 이어지는 줄 %d개 중 첫 줄만 읽음(표 본문으로 보임)" % (j - i)
            i = j
        else:
            i += 1
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--elements", required=True, help="디자인 요소 목록 JSON (run.js와 같은 파일)")
    ap.add_argument("--dev", required=True, help="개발화면 PNG")
    ap.add_argument("--align", help="검수기 결과 JSON (run.js 출력) — 겹치기 값 tx/ty/s를 여기서 가져온다")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pad", type=int, default=6, help="띠 위아래 여유 픽셀")
    ap.add_argument("--gap", type=int, default=6, help="이만큼 가까운 줄은 한 띠로 합침")
    ap.add_argument("--min-repeat", type=int, default=3, help="같은 모양 줄이 이 개수 이상이면 첫 줄만 읽음")
    ap.add_argument("--skip-above", type=float, default=None,
                    help="겹치기 점수가 이보다 높으면 AI를 부르지 않고 끝낸다(검수기만으로 충분한 화면)")
    ap.add_argument("--dry-run", action="store_true", help="읽지 않고 구역과 예상 시간만 보여준다")
    a = ap.parse_args()

    el = json.load(open(a.elements, encoding="utf-8"))
    cols = el["cols"]
    rowsraw = [dict(zip(cols, r)) for r in el["rows"]]
    texts = [{"id": o.get("id"), "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"], "t": squeeze(o.get("text"))}
             for o in rowsraw if o.get("kind") == "text" and squeeze(o.get("text"))]
    if not texts:
        sys.exit("디자인 글자 요소가 없습니다: " + a.elements)

    # 겹치기 값 — 검수기가 이미 계산한 것을 그대로 쓴다(손으로 밀림을 넣지 않는다)
    L, s, tx, ty, top, score, anchors = 1.0, 1.0, 0.0, 0.0, 0, None, None
    if a.align:
        al = json.load(open(a.align, encoding="utf-8"))
        m = al["model"]
        L, s, tx, ty = m.get("logicalScale", 1), m.get("s", 1) or 1, m.get("tx", 0), m.get("ty", 0)
        top = (al.get("range") or {}).get("captureTop") or 0
        score, anchors = m.get("score"), m.get("anchors")
    if a.skip_above is not None and score is not None and score >= a.skip_above:
        json.dump({"skippedScreen": True, "reason": "겹치기 점수 %.2f — 검수기만으로 충분(설정 %.2f 이상)" % (score, a.skip_above),
                   "align": {"score": score, "anchors": anchors}}, open(a.out, "w"), ensure_ascii=False, indent=1)
        print("겹치기 점수 %.2f ≥ %.2f — AI를 부르지 않았습니다." % (score, a.skip_above))
        return

    def to_dev(x, y):
        return ((x * L - tx) / s, (y * L - ty) / s + top)

    dev = Image.open(a.dev).convert("RGB")
    rows = mark_repeats(text_rows(texts, a.gap), a.min_repeat)
    read_rows = [r for r in rows if not r.get("skip")]

    # 예상 시간
    def splits_of(r):
        x1, _ = to_dev(r["x"], r["y"])
        x2, _ = to_dev(r["x2"], r["y2"])
        wpx = x2 - x1
        return (4 if wpx > 1500 else 3 if wpx > 700 else 2), (6 if wpx > 700 else 4 if wpx > 300 else 2)
    est = sum(sum(splits_of(r)) for r in read_rows)
    print("띠 %d개 중 %d개 읽음(나머지 %d개는 반복 줄) · AI 호출 예상 %d회 · 예상 %.0f분"
          % (len(rows), len(read_rows), len(rows) - len(read_rows), est, est * SEC_PER_CALL / 60))
    if score is not None:
        print("겹치기: 점수 %.2f · 기준요소 %s · tx %s / ty %s / 배율 %s%s"
              % (score, anchors, tx, ty, s, "  ⚠ 정렬 확인 필요" if score < 0.85 else ""))
    if a.dry_run:
        for i, r in enumerate(rows, 1):
            print("  %2d. y %4d~%-4d  글자 %2d개  %s%s" % (i, r["y"], r["y2"], len(r["items"]),
                  " / ".join(e["t"] for e in r["items"])[:70], "   ← 건너뜀" if r.get("skip") else ""))
        return

    out_regions, skipped = [], []
    t0 = time.time()
    for i, r in enumerate(rows, 1):
        name = "띠%02d (y %d~%d)" % (i, r["y"], r["y2"])
        if r.get("skip"):
            skipped.append({"region": name, "reason": r["skip"], "design": [e["t"] for e in r["items"]]})
            continue
        x1, y1 = to_dev(r["x"], r["y"] - a.pad)
        x2, y2 = to_dev(r["x2"], r["y2"] + a.pad)
        box = (max(0, int(x1)), max(0, int(y1)), min(dev.width, int(x2)), min(dev.height, int(y2)))
        if box[2] - box[0] < 8 or box[3] - box[1] < 6:
            skipped.append({"region": name, "reason": "겹치기 결과 개발화면 밖", "design": [e["t"] for e in r["items"]]})
            continue
        ws, ns = splits_of(r)
        wide = read_wide(dev, box, ws, name)
        narrow = read_narrow(dev, box, ns, name)

        # 개발 글자 = 넓은 읽기 ∪ 좁은 읽기 (중복 제거, 넓은 쪽 좌표 유지)
        seen, dv = set(), []
        for item in [dict(f) for f in wide] + [{"t": t, "box": None} for t in narrow]:
            t = squeeze(item["t"])
            if not norm(t) or norm(t) in seen:
                continue
            seen.add(norm(t))
            dv.append({"t": t, "box": item["box"]})
        narrow_join = "".join(norm(t) for t in narrow)
        dev_join = "".join(norm(d["t"]) for d in dv)
        dev_texts = [d["t"] for d in dv]

        # 디자인 글자 하나하나: 그대로 있음 / 띄어쓰기만 다름 / 토막나 읽혔지만 있음 / 없음
        only_design, spacing = [], []
        for e in r["items"]:
            tt = e["t"]
            if tt in dev_texts:
                continue
            m = [d["t"] for d in dv if norm(d["t"]) == norm(tt)]
            if m:
                spacing.append({"design": tt, "dev": m[0], "designBox": [e["x"], e["y"], e["w"], e["h"]]})
                continue
            if norm(tt) in dev_join:
                continue
            only_design.append({"t": tt, "designBox": [e["x"], e["y"], e["w"], e["h"]]})

        # 개발에만 있는 글자 — 좁은 조각에서도 나와야 인정(환각 안전장치)
        design_join = "".join(norm(e["t"]) for e in r["items"])
        design_norms = [norm(e["t"]) for e in r["items"]]
        only_dev, dropped, need_check = [], [], []
        for d in dv:
            u = d["t"]
            nu = norm(u)
            if u in {e["t"] for e in r["items"]} or any(norm(u) == norm(sp["design"]) for sp in spacing) or nu in design_join:
                continue
            if nu not in narrow_join:
                dropped.append({"t": u, "why": "좁게 다시 보니 없음 — 지어낸 글자로 보고 버림"})
                continue
            if len(nu) <= 1:
                need_check.append({"t": u, "why": "한 글자 — 잘못 읽었을 수 있음", "devBox": d["box"]})
                continue
            near = [dn for dn in design_norms if edit1(nu, dn)]
            if near:
                need_check.append({"t": u, "why": "디자인의 “%s”와 한 글자 차이 — 오독일 수 있음" % near[0], "devBox": d["box"]})
                continue
            only_dev.append({"t": u, "devBox": d["box"]})

        out_regions.append({"region": name,
                            "designBox": [r["x"], r["y"], r["x2"] - r["x"], r["y2"] - r["y"]],
                            "devBox": [box[0], box[1], box[2] - box[0], box[3] - box[1]],
                            "design": [e["t"] for e in r["items"]],
                            "dev": dev_texts,
                            "only_design": only_design, "only_dev": only_dev, "spacing": spacing,
                            "need_check": need_check, "dropped": dropped})
        print("── %s" % name)
        print("   디자인에만: %s" % (" · ".join(x["t"] for x in only_design) or "(없음)"))
        print("   개발에만  : %s" % (" · ".join(x["t"] for x in only_dev) or "(없음)"))
        if spacing:
            print("   띄어쓰기만: %s" % " · ".join("“%s”→“%s”" % (p["design"], p["dev"]) for p in spacing))
        if need_check:
            print("   확인 필요 : %s" % " · ".join("%s(%s)" % (x["t"], x["why"]) for x in need_check))
        if dropped:
            print("   ↳ 버린 글자: %s" % " · ".join(x["t"] for x in dropped))

    tot = lambda k: sum(len(r[k]) for r in out_regions)
    res = {"screen": el.get("frame", {}).get("name"), "dev": os.path.basename(a.dev),
           "elements": os.path.basename(a.elements), "model": MODEL,
           "align": {"tx": tx, "ty": ty, "s": s, "logicalScale": L, "captureTop": top,
                     "score": score, "anchors": anchors,
                     "warn": "정렬 확인 필요(점수 0.85 미만)" if (score is not None and score < 0.85) else None},
           "regions": out_regions, "skipped": skipped,
           "summary": {"bands": len(rows), "read": len(out_regions), "skipped": len(skipped),
                       "only_design": tot("only_design"), "only_dev": tot("only_dev"),
                       "spacing": tot("spacing"), "need_check": tot("need_check"),
                       "dropped_hallucination": tot("dropped"),
                       "ai_calls": _stats["calls"], "ai_cached": _stats["cached"],
                       "seconds": round(time.time() - t0)}}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print("\n합계 — 디자인에만 %d · 개발에만 %d · 띄어쓰기 %d · 확인 필요 %d · 버린 환각 %d"
          % (res["summary"]["only_design"], res["summary"]["only_dev"], res["summary"]["spacing"],
             res["summary"]["need_check"], res["summary"]["dropped_hallucination"]))
    print("AI 호출 %d회(저장분 재사용 %d회) · %.0f초 · 저장: %s"
          % (_stats["calls"], _stats["cached"], time.time() - t0, a.out))


if __name__ == "__main__":
    main()
