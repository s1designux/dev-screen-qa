#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""개선판: AI에게 '같냐'고 묻지 않는다.
디자인 조각과 개발 조각을 각각 따로 읽히고(=AI는 눈 역할만), 같고 다름은 코드가 판정한다.
확정은 하지 않는다. 사람이 볼 표만 만든다."""
import base64, io, json, os, re, sys, time, urllib.request
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("VLM_MODEL", "qwen2.5vl:7b")
PAD = 14        # v1의 48 → 주변 잡음을 줄인다
MIN_SIDE = 340  # 작은 조각은 부드럽게 확대

READ = """이 그림에서 **빨간 네모 안**에 보이는 것만 알려주세요. 네모 바깥은 무시하세요.

- 글자가 있으면 `text`에 **보이는 그대로** 적으세요. 띄어쓰기도 그대로. 없으면 빈 문자열.
- 그림/아이콘/도형이 있으면 `shape`에 아주 짧은 한국어 이름으로 적으세요.
  (예: "사람 아이콘", "아래쪽 삼각형", "지구본 아이콘", "가로선", "빈 입력칸", "회색 버튼")
  없으면 빈 문자열.
- `color`에는 글자나 도형의 색을 아주 짧게 (예: "검정", "회색", "파랑"). 모르면 빈 문자열.

읽은 것만 적으세요. 추측하거나 설명을 덧붙이지 마세요.
JSON만 답하세요: {"text":"","shape":"","color":""}"""


def crop(img, box, pad):
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    L, T = max(0, x - pad), max(0, y - pad)
    R, B = min(img.width, x + w + pad), min(img.height, y + h + pad)
    piece = img.crop((L, T, R, B)).convert("RGB")
    s = 1
    m = min(piece.width, piece.height)
    if m < MIN_SIDE:
        s = min(6, max(1, MIN_SIDE / max(1, m)))
    if s > 1:
        piece = piece.resize((int(piece.width * s), int(piece.height * s)), Image.LANCZOS)
    d = ImageDraw.Draw(piece)
    d.rectangle([(x - L) * s, (y - T) * s, (x - L + w) * s - 1, (y - T + h) * s - 1],
                outline=(255, 0, 0), width=max(2, int(2 * s)))
    return piece


def call(img, prompt):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    body = json.dumps({
        "model": MODEL, "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [{"role": "user", "content": prompt,
                      "images": [base64.b64encode(buf.getvalue()).decode()]}],
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        raw = json.loads(r.read())["message"]["content"].strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.lower().startswith("json") else raw
    try:
        i, j = raw.index("{"), raw.rindex("}") + 1
        return json.loads(raw[i:j])
    except Exception:
        return {"text": "", "shape": "", "color": "", "_err": raw[:120]}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def judge(a, b):
    """AI가 읽은 두 결과를 코드가 비교한다."""
    at, bt = norm(a.get("text")), norm(b.get("text"))
    ash, bsh = norm(a.get("shape")), norm(b.get("shape"))
    ac, bc = norm(a.get("color")), norm(b.get("color"))
    if at or bt:
        if at != bt:
            if at.replace(" ", "") == bt.replace(" ", ""):
                return "차이있음", "띄어쓰기가 다름: “%s” → “%s”" % (at, bt)
            return "차이있음", "글자가 다름: “%s” → “%s”" % (at or "(없음)", bt or "(없음)")
        if ac and bc and ac != bc:
            return "차이있음", "글자는 같은데 색이 다름: %s → %s" % (ac, bc)
        return "차이없음", "글자가 같음: “%s”" % at
    if ash or bsh:
        if ash != bsh:
            return "차이있음", "모양이 다름: %s → %s" % (ash or "(없음)", bsh or "(없음)")
        if ac and bc and ac != bc:
            return "차이있음", "모양은 같은데 색이 다름: %s → %s" % (ac, bc)
        return "차이없음", "모양이 같음: %s" % ash
    return "판단불가", "양쪽 모두 읽어낸 것이 없음"


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else "findid"
    design_png = sys.argv[2] if len(sys.argv) > 2 else "design_1920x1080.png"
    dev_png = sys.argv[3] if len(sys.argv) > 3 else "dev_1920x934.png"
    data = json.load(open(os.path.join(HERE, case + ".json")))
    design = Image.open(os.path.join(HERE, design_png))
    dev = Image.open(os.path.join(HERE, dev_png))
    outdir = os.path.join(HERE, "vlm2_" + case)
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for c in data["candidates"]:
        db, rb = c.get("designBox"), c.get("rawBox")
        if not db or not rb:
            continue
        t0 = time.time()
        di, vi = crop(design, db, PAD), crop(dev, rb, PAD)
        pd = os.path.join(outdir, "no%02d_design.png" % c["no"])
        pv = os.path.join(outdir, "no%02d_dev.png" % c["no"])
        di.save(pd); vi.save(pv)
        ra, rb2 = call(di, READ), call(vi, READ)
        verdict, reason = judge(ra, rb2)
        rows.append({"no": c["no"], "kind": c.get("kind"), "label": c.get("label"),
                     "detail": c.get("detail"), "rule_conf": c.get("confidence"),
                     "design_read": ra, "dev_read": rb2,
                     "verdict": verdict, "reason": reason,
                     "img_design": os.path.relpath(pd, HERE),
                     "img_dev": os.path.relpath(pv, HERE),
                     "_sec": round(time.time() - t0, 1)})
        print("#%-2d %-9s %-6s %4.1fs  %s" % (c["no"], c.get("kind"), verdict,
                                              rows[-1]["_sec"], reason[:70]), flush=True)
    json.dump(rows, open(os.path.join(HERE, "vlm2_%s.json" % case), "w"),
              ensure_ascii=False, indent=1)
    print("\n저장: vlm2_%s.json" % case)


if __name__ == "__main__":
    main()
