#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v3 — 환각 안전장치.
① 디자인 쪽은 AI로 읽지 않는다. 피그마에서 뽑은 글자(elements_stay_texts.json)를 진실값으로 쓴다.
② 개발 쪽은 '글자 + 위치'를 같이 대게 하고, 디자인에 없는 글자(=오류 후보 또는 환각)는
   그 위치만 잘라 다시 읽혀 정말 있는지 확인한다. 없으면 버린다."""
import base64, io, json, re, sys, time, urllib.request
from PIL import Image

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5vl:7b"

def ask(img, prompt):
    buf = io.BytesIO(); img.save(buf, format="PNG")
    body = json.dumps({"model": MODEL, "stream": False, "options": {"temperature": 0, "num_ctx": 4096},
                       "messages": [{"role": "user", "content": prompt,
                                     "images": [base64.b64encode(buf.getvalue()).decode()]}]}).encode()
    with urllib.request.urlopen(urllib.request.Request(OLLAMA, body, {"Content-Type": "application/json"}), timeout=600) as r:
        raw = json.loads(r.read())["message"]["content"].strip()
    if "```" in raw:
        raw = raw.split("```")[1]; raw = raw[4:] if raw.lower().startswith("json") else raw
    return raw

GROUND = """이 그림에 보이는 글자를 전부 찾아, 각 글자가 있는 네모의 좌표를 함께 적으세요.
좌표는 [왼쪽x, 위y, 오른쪽x, 아래y]이고, 그림의 왼쪽 끝=0, 오른쪽 끝=1000, 위 끝=0, 아래 끝=1000인 비율값입니다. 위에서 아래, 왼쪽에서 오른쪽 순서로.
보이는 그대로 적고(띄어쓰기도 그대로), 없는 글자를 지어내지 마세요. 글자가 하나도 없으면 빈 목록을 답하세요.
JSON만: {"texts":[{"t":"글자","box":[x1,y1,x2,y2]}]}"""
VERIFY = """이 작은 조각에 글자가 있으면 보이는 그대로 적으세요. 없으면 빈 문자열.
JSON만: {"text":""}"""

def norm(s): return re.sub(r"\s+", "", str(s or ""))

def read_dev(img, box, split):
    """개발 띠를 겹쳐 나눠 읽고, 글자마다 원본 좌표를 붙여 돌려준다."""
    piece = img.crop(box); w = piece.width; seg = w / split; ov = int(seg * 0.10)
    found = []
    for i in range(split):
        L = max(0, int(seg * i) - ov); R = min(w, int(seg * (i + 1)) + ov)
        p = piece.crop((L, 0, R, piece.height))
        s = max(1, min(3, int(560 / max(1, p.height))))
        ps = p.resize((p.width * s, p.height * s), Image.LANCZOS)
        raw = ask(ps, GROUND)
        # 답 모양이 들쭉날쭉하다({"texts":[..]} / 바로 [..] / "box}[" 같은 오타) — 정규식으로 항목만 건진다
        for m in re.finditer(r'"t"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"box"[^\[]*\[\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)', raw):
            t = m.group(1).strip()
            if not t: continue
            nx1, ny1, nx2, ny2 = [float(m.group(k)) for k in (2, 3, 4, 5)]
            pw, ph = R - L, piece.height
            bx = (box[0] + L + nx1 / 1000 * pw, box[1] + ny1 / 1000 * ph,
                  box[0] + L + nx2 / 1000 * pw, box[1] + ny2 / 1000 * ph)
            found.append({"t": t, "box": bx})
        if "\"t\"" not in raw and raw.strip() not in ("[]", "{\"texts\":[]}", ""):
            found.append({"t": "(읽기 실패: %s)" % raw[:40].replace("\n", " "), "box": None})
    return found

SLICE = """이 작은 조각에 보이는 글자를 전부 적으세요. 보이는 그대로, 띄어쓰기도 그대로.
없는 글자를 지어내지 마세요. 글자가 하나도 없으면 빈 목록을 답하세요.
JSON만: {"texts":["...","..."]}"""

def slice_reads(img, box, n=6, overlap=0.5):
    """개발 띠를 좁은 조각으로(서로 절반씩 겹치게) 잘라 각각 읽는다. 환각은 넓은 틀에서 나오고 좁은 틀에서는 사라진다."""
    piece = img.crop(box); w = piece.width; sw = w / (n - (n - 1) * overlap)
    texts = []
    for i in range(n):
        L = int(i * sw * (1 - overlap)); R = min(w, int(L + sw))
        p = piece.crop((L, 0, R, piece.height))
        sc = max(1, min(3, int(560 / max(1, p.height)))); p = p.resize((p.width * sc, p.height * sc), Image.LANCZOS)
        raw = ask(p, SLICE)
        texts += re.findall(r'"((?:[^"\\]|\\.)+)"', raw)
    return [t for t in texts if t.strip() and t.strip() != "texts"]

def verify(item, slice_joined):
    a = norm(item["t"])
    if a and a in slice_joined: return "확인됨", None
    return "없음(환각)", None

REGIONS = [  # (이름, 디자인 영역, 개발 영역)
 ("상단 메뉴",      (0,101,1920,140), (0,118,1920,152)),
 ("탭 줄",          (0,138,1720,170), (0,155,1720,188)),
 ("검색 조건",      (20,190,1900,272),(20,208,1900,292)),
 ("목록 제목·건수", (40,300,1250,338),(40,322,1250,360)),
 ("표 컬럼 제목",   (40,340,1250,372),(40,362,1250,398)),
]

def main():
    dev = Image.open("dev_stay_1920x1081.png")
    E = json.load(open("elements_stay_texts.json"))["rows"]
    out = []; t0 = time.time()
    for name, db, vb in REGIONS:
        # 디자인 글자: 피그마 값 그대로(영역 안에 든 것만)
        dtexts = [r[5] for r in E if db[0] <= r[1] < db[2] and db[1] <= r[2] < db[3] and r[5].strip()]
        split = 4 if (vb[2] - vb[0]) > 1500 else 3
        wide = read_dev(dev, vb, split)
        narrow = slice_reads(dev, vb)                       # 좁은 조각 읽기 — 누락 보완 + 환각 검증에 같이 쓴다
        # 개발 글자 = 넓은 읽기 ∪ 좁은 읽기 (중복 제거)
        seen, dv = set(), []
        for t in [f["t"] for f in wide] + narrow:
            t = re.sub(r"\s+", " ", t.strip())
            if norm(t) and norm(t) not in seen: seen.add(norm(t)); dv.append(t)
        sj = "".join(norm(t) for t in narrow)
        jv = "".join(norm(t) for t in dv)
        dset = {re.sub(r"\s+", " ", t.strip()) for t in dtexts}
        # 디자인 글자 하나하나: 똑같이 있음 / 띄어쓰기만 다름 / 토막나 읽혔지만 있음 / 없음
        only_design, spacing = [], []
        for t in dtexts:
            tt = re.sub(r"\s+", " ", t.strip())
            if tt in dv: continue
            m = [u for u in dv if norm(u) == norm(tt)]
            if m: spacing.append((tt, m[0])); continue
            if norm(tt) in jv: continue
            only_design.append(tt)
        # 개발 글자 중 디자인에 없는 것: 좁은 조각에서도 나와야 인정(환각 안전장치)
        jd = "".join(norm(t) for t in dtexts)
        only_dev, hall, unver = [], [], []
        for u in dv:
            if u in dset or any(norm(u) == norm(a) for a, _ in spacing) or norm(u) in jd: continue
            if norm(u) in sj: only_dev.append((u, "확인됨", None))
            else: hall.append((u, "없음(환각)", None))
        out.append({"region": name, "design": dtexts, "dev": dv, "only_design": only_design,
                    "only_dev": [f[0] for f in only_dev], "spacing": spacing,
                    "hallucination": [h[0] for h in hall], "unverified": [(u[0], u[1]) for u in unver]})
        print("── %s" % name)
        print("   디자인에만: %s" % (" · ".join(only_design) or "(없음)"))
        print("   개발에만  : %s" % (" · ".join(f[0] for f in only_dev) or "(없음)"))
        if spacing: print("   띄어쓰기만: %s" % " · ".join("“%s”→“%s”" % p for p in spacing))
        if hall:    print("   ↳ 지어낸 글자로 판정해 버림: %s" % " · ".join(h[0] for h in hall))
        if unver:   print("   ↳ 미검증: %s" % " · ".join("%s(%s)" % (u[0], u[1]) for u in unver))
    json.dump(out, open("vlm_stay3.json", "w"), ensure_ascii=False, indent=1)
    print("\n총 %.0f초 · 저장: vlm_stay3.json" % (time.time() - t0))

if __name__ == "__main__":
    main()
