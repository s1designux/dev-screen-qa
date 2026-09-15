"""시안 요소 전체 목록 — 플러그인이 검수 포털용으로 이미 보낸 깊은 목록을 동작 초안에도 쓴다.

플러그인은 화면을 보낼 때 요소를 두 벌 보낸다:
  · `속`      — 동작 초안용 얕은 목록(6단계·300개까지). 검색줄 속 셀렉박스처럼 깊이 든 것을 놓친다.
  · 검수요소  — 검수 포털 자동 검수용 전체 목록(12단계까지). `디자인/NNN_elements.json` 에 있다.
같은 화면을 두 번 읽을 까닭이 없으므로(2026-09-15 river) 전체 목록이 있으면 그것을 `속` 모양으로 바꿔 쓴다.
없으면(옛 꾸러미) `속` 그대로 쓴다 — 어느 쪽이든 [{이름, 종류, 글자, 자리(%)}] 이고,
전체 목록에서 온 것은 `상자(px)`·`사슬(조상 이름들)`·`id`·`부모` 가 더 붙는다.
"""
import json
import os


def 전체목록(줄):
    경로 = (줄 or {}).get("검수요소파일")
    if 경로 and os.path.exists(경로):
        try:
            d = json.load(open(경로, encoding="utf-8"))
        except Exception:
            d = None
        try:
            나온 = _바꾸기(d) if isinstance(d, dict) else []
        except Exception:          # 모양이 다른 파일이면 얕은 목록으로 돌아간다 — 페이지가 죽지 않게
            나온 = []
        if 나온:
            return 나온
    return list((줄 or {}).get("속") or [])


def _바꾸기(d):
    틀 = d.get("틀") or {}
    W, H = float(틀.get("폭") or 0), float(틀.get("높이") or 0)
    나온 = []
    for e in d.get("요소") or []:
        b = e.get("box") or {}
        if not all(k in b for k in ("x", "y", "w", "h")):
            continue
        자리 = ({"x": round(b["x"] / W * 100, 1), "y": round(b["y"] / H * 100, 1),
               "w": round(b["w"] / W * 100, 1), "h": round(b["h"] / H * 100, 1)}
              if W and H else dict(b))
        종류 = e.get("type") or ""
        나온.append({"이름": e.get("name") or "", "종류": 종류,
                  "글자": (e.get("text") or "").strip() if 종류 == "TEXT" else "",
                  "자리": 자리, "상자": {k: float(b[k]) for k in ("x", "y", "w", "h")},
                  "깊이": e.get("depth"), "id": e.get("id"), "부모": e.get("parentId"),
                  "사슬": [c.get("n", "") for c in (e.get("chain") or [])]})
    return 나온
