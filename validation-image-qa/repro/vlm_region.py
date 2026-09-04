#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 화면 검증 — 구역 단위로 AI에게 '보이는 글자를 전부 읽어라'만 시키고,
같고 다름은 코드가 목록을 맞춰 판정한다. 요소 하나씩이 아니라 구역이라 밀림에 강하다."""
import json, sys
from PIL import Image
from vlm_triage2 import call

READ_ALL = """이 그림에 보이는 글자를 **전부** 찾아 적어 주세요.
위에서 아래로, 왼쪽에서 오른쪽 순서로 읽습니다.
보이는 그대로 적으세요 — 띄어쓰기도 그대로, 고치거나 다듬지 마세요.
글자가 아닌 아이콘·그림은 적지 마세요.
JSON만 답하세요: {"texts":["...","..."]}"""

REGIONS = [
 ("상단 메뉴",      (0,101,1920,140), (0,118,1920,152)),
 ("탭 줄",          (0,138,1720,170), (0,155,1720,188)),
 ("검색 조건",      (20,190,1900,272),(20,208,1900,292)),
 ("목록 제목·건수", (40,300,1250,338),(40,322,1250,360)),
 ("표 컬럼 제목",   (40,340,1250,372),(40,362,1250,398)),
]

SEP = set("|·ㅣl￨")

def dedup(items):
    """구분자·중복을 걷어낸다."""
    seen, out = set(), []
    for t in items:
        if not t or t in SEP or all(c in SEP or c.isspace() for c in t):
            continue
        if t not in seen:
            seen.add(t); out.append(t)
    return out


def heal(only, other):
    """조각 경계에서 두 토막으로 읽힌 글자를 붙여, 반대쪽에 있으면 차이에서 뺀다."""
    joined = "".join(other).replace(" ", "")
    return [t for t in only if t.replace(" ", "") not in joined]


def read(img, box, split):
    """넓은 띠는 좌우로 나눠 읽어야 작은 글자를 놓치지 않는다."""
    piece = img.crop(box)
    parts, w = [], piece.width
    ov = int(w / split * 0.10)   # 조각을 겹쳐 잘라 경계에서 글자가 반토막 나지 않게 한다
    for i in range(split):
        p = piece.crop((max(0, w * i // split - ov), 0, min(w, w * (i + 1) // split + ov), piece.height))
        s = max(1, min(3, int(560 / max(1, p.height))))
        p = p.resize((p.width * s, p.height * s), Image.LANCZOS)
        got = call(p, READ_ALL)
        parts += [str(t).strip() for t in (got.get("texts") or []) if str(t).strip()]
    return parts

design = Image.open("design_stay_1920x1080.png")
dev = Image.open("dev_stay_1920x1081.png")
out = []
for name, db, vb in REGIONS:
    split = 3 if (db[2] - db[0]) > 1500 else 2
    a, b = read(design, db, split), read(dev, vb, split)
    a, b = dedup(a), dedup(b)
    sa, sb = set(a), set(b)
    only_d = [t for t in a if t not in sb]
    only_v = [t for t in b if t not in sa]
    # 붙여읽기 보정: 조각 경계에서 쪼개진 글자는 이어 붙이면 반대쪽에 있다
    only_d, only_v = heal(only_d, b), heal(only_v, a)
    # 띄어쓰기만 다른 것은 따로 표시한다(진짜 오류일 수도, 오독일 수도 있어 사람이 본다)
    spacing = []
    for t in list(only_d):
        for u in list(only_v):
            if t.replace(" ", "") == u.replace(" ", ""):
                spacing.append((t, u)); only_d.remove(t); only_v.remove(u); break
    out.append({"region": name, "design": a, "dev": b, "spacing": spacing,
                "only_design": only_d, "only_dev": only_v})
    print("── %s" % name)
    print("   디자인에만: %s" % (" · ".join(only_d) or "(없음)"))
    print("   개발에만  : %s" % (" · ".join(only_v) or "(없음)"))
    if spacing: print("   띄어쓰기만 다름: %s" % " · ".join("“%s”→“%s”" % p for p in spacing))
json.dump(out, open("vlm_stay.json", "w"), ensure_ascii=False, indent=1)
print("\n저장: vlm_stay.json")
