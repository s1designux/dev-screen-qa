"""찍을 창 높이 — **시안 한 판에서 내용이 차지하는 높이**를 그대로 창 높이로 쓴다.

왜 있나: 시안은 1920×1080 인데 창 높이가 900 으로 못 박혀 있어, 같은 화면을 서로 다른
자로 찍고 있었다. 내용이 세로 가운데 정렬이면 위쪽과 가운데가 서로 다른 만큼 밀려
**한 번의 세로 이동으로는 맞출 수 없다**(유비스사용자포털 로그인, 2026-09-21 · 위 87 · 가운데 127).
시안 쪽을 고치거나 검수기를 고치는 대신, 처음부터 같은 자로 찍는다(river 승인 A-20260921-P27).

재는 법: **시안 판 높이 − 맨 위 틀 띠 − 맨 아래 틀 띠.**
틀 띠는 시안에 그림으로 그려 넣은 브라우저 창 틀·주소창·작업표시줄 따위라 실제 창에는 없다.
고르는 기준은 검수기(`engine/ui.html` 의 `frameBandEdge`·`FRAME_NAME_RE`)와 같게 둔다 —
촬영 때는 검수기를 돌리지 않으므로 같은 규칙을 여기에 한 벌 더 둔다.

못 정하면(요소 목록이 없거나, 나온 값이 너무 낮거나 높으면) 예전처럼 기본 높이로 둔다.
"""
import json
import os
import re

기본높이 = 900
가장낮은 = 400          # 이보다 낮으면 무언가 잘못 잰 것이다
가장높은 = 1600         # 스크롤로 긴 시안 — 창을 이만큼 크게 열 수는 없다

# 검수기 FRAME_NAME_RE 와 같은 낱말
틀이름 = re.compile(
    r"브라우저|browser|chrome|크롬|탭 ?바|tab ?bar|\burl\b|주소 ?창|address ?bar|"
    r"status ?bar|상태 ?바|safe ?area|notch|home ?indicator|navigation ?bar|"
    r"device ?frame|bezel|mockup|목업", re.I)
틀글자 = re.compile(r"https?://|www\.|\.(com|net|kr|io|do|html?)(/|$)|^\d{1,2}:\d{2}$", re.I)


def _띠끝(상자, 폭, 높이):
    """화면 위·아래 끝에 붙어 가로로 거의 꽉 찬 얇은 영역인가 — 어느 끝인지 돌려준다."""
    try:
        x, y, w, h = (float(상자[k]) for k in ("x", "y", "w", "h"))
    except (KeyError, TypeError, ValueError):
        return None
    위 = y <= 2
    아래 = y + h >= 높이 - 2
    if not (위 or 아래) or w < 폭 * 0.8 or h > 높이 * 0.25 or h < 8:
        return None
    return "위" if 위 else "아래"


def _자식들(요소들):
    자식 = {}
    for e in 요소들:
        자식.setdefault(e.get("parentId"), []).append(e)
    return 자식


def _후손(e, 자식):
    나온, 남은 = [], list(자식.get(e.get("id"), []))
    while 남은:
        d = 남은.pop()
        나온.append(d)
        남은 += 자식.get(d.get("id"), [])
    return 나온


def _틀인가(e, 자식):
    if 틀이름.search(e.get("name") or ""):
        return True
    for d in _후손(e, 자식):
        if 틀이름.search(d.get("name") or ""):
            return True
        글 = str(d.get("text") or "").strip()
        if 글 and 틀글자.search(글):
            return True
    return False


def 재기(요소들, 폭, 높이):
    """시안 요소 목록에서 위·아래 틀 띠를 빼고 남는 내용 높이를 잰다.

    돌려주는 것: {높이, 판, 틀위, 틀아래, 까닭}
    `높이` 가 None 이면 못 정한 것이다(`까닭` 에 한 줄).
    """
    폭, 높이 = float(폭 or 0), float(높이 or 0)
    것 = {"높이": None, "판": int(높이), "틀위": 0, "틀아래": 0, "까닭": ""}
    if not 폭 or not 높이:
        것["까닭"] = "시안 판 크기를 알 수 없습니다"
        return 것
    자식 = _자식들(요소들 or [])
    위끝, 아래끝 = 0.0, 높이
    for e in 요소들 or []:
        상자 = e.get("box") or {}
        끝 = _띠끝(상자, 폭, 높이)
        if not 끝 or not _틀인가(e, 자식):
            continue
        if 끝 == "위":
            위끝 = max(위끝, float(상자["y"]) + float(상자["h"]))
        else:
            아래끝 = min(아래끝, float(상자["y"]))
    잰것 = round(아래끝 - 위끝)
    것.update({"틀위": round(위끝), "틀아래": round(높이 - 아래끝)})
    if 잰것 < 가장낮은:
        것["까닭"] = f"잰 높이가 너무 낮습니다({잰것}px)"
    elif 잰것 > 가장높은:
        것["까닭"] = f"시안이 너무 깁니다({잰것}px) — 창을 그만큼 열 수 없습니다"
    else:
        것["높이"] = 잰것
    return 것


def 파일로재기(경로):
    """플러그인이 남긴 검수 요소 파일(`디자인/NNN_elements.json`)에서 잰다."""
    if not 경로 or not os.path.exists(경로):
        return {"높이": None, "판": 0, "틀위": 0, "틀아래": 0, "까닭": "시안 요소 목록이 없습니다"}
    try:
        d = json.load(open(경로, encoding="utf-8"))
        틀 = d.get("틀") or {}
        return 재기(d.get("요소") or [], 틀.get("폭"), 틀.get("높이"))
    except Exception as e:
        return {"높이": None, "판": 0, "틀위": 0, "틀아래": 0,
                "까닭": f"시안 요소 목록을 읽지 못했습니다 — {e}"}


def 초안높이(줄):
    """찍을 목록 한 줄에서 창 높이를 정한다 — 못 정하면 None."""
    것 = 파일로재기((줄 or {}).get("검수요소파일"))
    if 것["높이"] is None and (줄 or {}).get("높이"):
        # 요소 목록이 없는 옛 꾸러미 — 프레임 높이만이라도 있으면 그대로 쓴다
        try:
            판 = int(float(줄["높이"]))
            if 가장낮은 <= 판 <= 가장높은:
                것.update({"높이": 판, "판": 판, "까닭": ""})
        except (TypeError, ValueError):
            pass
    return 것


def 고르기(줄, tag=None):
    """실제로 창을 열 때 쓸 높이 — 이름표에 적힌 값 → 이름표 위쪽 값 → 기본 900."""
    for 곳 in (줄 or {}, tag or {}):
        값 = str(곳.get("창높이") or "").strip()
        if 값:
            try:
                수 = int(float(값))
            except ValueError:
                continue
            if 가장낮은 <= 수 <= 가장높은:
                return 수
    return 기본높이
