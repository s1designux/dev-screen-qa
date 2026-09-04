#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""룰 엔진이 낸 후보를 로컬 비전 모델에 물어 '진짜 차이인지' 걸러보는 실험 하네스.
확정은 하지 않는다. 사람이 볼 표·그림만 만든다."""
import base64, io, json, os, sys, time, urllib.request
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("VLM_MODEL", "qwen2.5vl:7b")
PAD = 48          # 조각 주변 여유
MIN_SIDE = 260    # 너무 작은 조각은 키워서 보여준다

PROMPT = """당신은 UI 검수 보조자입니다. 확정하지 말고 판단만 하세요.

이미지 한 장에 같은 화면의 같은 부분이 두 개 붙어 있습니다.
왼쪽(초록 테두리) = 디자인 시안, 오른쪽(주황 테두리) = 실제 개발화면.
빨간 실선 안쪽이 봐야 할 곳입니다. 바깥은 위치를 알기 위한 주변입니다.

빨간 테두리 안을 비교해서, 사람이 검수결과서에 적을 만한 '눈에 보이는 차이'가 있는지 판단하세요.

차이로 볼 것: 글자 내용이 다름, 요소가 있고 없음, 색이 다름, 크기가 다름, 위치가 눈에 띄게 다름, 모양이 다름.
차이로 보지 말 것: 글꼴이 살짝 달라 생긴 굵기·자간 차이, 안티에일리어싱(경계 흐림), 1~2px 미세 어긋남, 캡처 화질 차이, 커서/포커스 표시.

아래 JSON 형식으로만 답하세요. 다른 말은 쓰지 마세요.
{"verdict":"차이있음|차이없음|판단불가","reason":"한국어 한 문장","confidence":0~100}"""


def crop(img, box, pad):
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    L, T = max(0, x - pad), max(0, y - pad)
    R, B = min(img.width, x + w + pad), min(img.height, y + h + pad)
    piece = img.crop((L, T, R, B)).convert("RGB")
    d = ImageDraw.Draw(piece)
    d.rectangle([x - L, y - T, x - L + w - 1, y - T + h - 1], outline=(255, 0, 0), width=2)
    return piece


def pair(a, b):
    s = 1
    m = min(a.height, b.height, a.width, b.width)
    if m < MIN_SIDE:
        s = min(4, max(1, round(MIN_SIDE / max(1, m))))
    if s > 1:
        a = a.resize((a.width * s, a.height * s), Image.NEAREST)
        b = b.resize((b.width * s, b.height * s), Image.NEAREST)
    gap, bd = 24, 4
    W = a.width + b.width + gap + bd * 4
    H = max(a.height, b.height) + bd * 2
    out = Image.new("RGB", (W, H), (255, 255, 255))
    out.paste(a, (bd, bd)); out.paste(b, (a.width + gap + bd * 3, bd))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, a.width + bd * 2 - 1, H - 1], outline=(0, 160, 60), width=bd)
    d.rectangle([a.width + gap + bd * 2, 0, W - 1, H - 1], outline=(240, 130, 0), width=bd)
    return out


def ask(img):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    body = json.dumps({
        "model": MODEL, "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [{"role": "user", "content": PROMPT,
                      "images": [base64.b64encode(buf.getvalue()).decode()]}],
    }).encode()
    req = urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        txt = json.loads(r.read())["message"]["content"]
    took = time.time() - t0
    raw = txt.strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        i, j = raw.index("{"), raw.rindex("}") + 1
        got = json.loads(raw[i:j])
    except Exception:
        got = {"verdict": "판단불가", "reason": "모델 응답을 읽지 못함: " + txt[:120], "confidence": 0}
    got["_sec"] = round(took, 1)
    return got


def main():
    case = sys.argv[1] if len(sys.argv) > 1 else "findid"
    design_png = sys.argv[2] if len(sys.argv) > 2 else "design_1920x1080.png"
    dev_png = sys.argv[3] if len(sys.argv) > 3 else "dev_1920x934.png"
    data = json.load(open(os.path.join(HERE, case + ".json")))
    cands = data["candidates"]
    design = Image.open(os.path.join(HERE, design_png))
    dev = Image.open(os.path.join(HERE, dev_png))
    outdir = os.path.join(HERE, "vlm_" + case)
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for c in cands:
        db, rb = c.get("designBox"), c.get("rawBox")
        if not db or not rb:
            continue
        img = pair(crop(design, db, PAD), crop(dev, rb, PAD))
        p = os.path.join(outdir, "no%02d.png" % c["no"])
        img.save(p)
        got = ask(img)
        rows.append({"no": c["no"], "kind": c.get("kind"), "label": c.get("label"),
                     "detail": c.get("detail"), "rule_conf": c.get("confidence"),
                     "img": os.path.relpath(p, HERE), **got})
        print("#%-2d %-9s %-6s %3s%%  %4.1fs  %s" % (
            c["no"], c.get("kind"), got["verdict"], got.get("confidence"),
            got["_sec"], got["reason"][:60]), flush=True)
    json.dump(rows, open(os.path.join(HERE, "vlm_%s.json" % case), "w"),
              ensure_ascii=False, indent=1)
    print("\n저장:", os.path.join(HERE, "vlm_%s.json" % case))


if __name__ == "__main__":
    main()
