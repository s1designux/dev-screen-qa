"""디자인 원본 읽기 — Figma 파일 주소 한 줄에서 화면(프레임) 목록을 뽑는다.

바깥 라이브러리를 쓰지 않는다(파이썬만 있으면 돌아가게). 읽기만 하고 쓰지 않는다.

열쇠(토큰)는 코드에 넣지 않는다. 다음 두 곳에서만 찾는다:
  1) 환경변수 FIGMA_TOKEN
  2) ~/.figma-token 파일 한 줄
"""
import json
import os
import re
import urllib.error
import urllib.request

열쇠파일 = os.path.expanduser("~/.figma-token")


class 읽기오류(Exception):
    pass


def 열쇠():
    import sys
    from pathlib import Path as _P
    뿌리 = _P(__file__).resolve().parent.parent.parent
    if str(뿌리) not in sys.path:
        sys.path.insert(0, str(뿌리))
    import 설정 as 설정
    t = (설정.값("피그마.열쇠") or "").strip()          # 설정.json → 환경변수 FIGMA_TOKEN
    if t:
        return t
    if os.path.exists(열쇠파일):
        t = open(열쇠파일, encoding="utf-8").read().strip()
        if t:
            return t
    return ""


def 주소풀기(url):
    """붙여넣은 Figma 주소에서 파일 열쇠와(있으면) 노드 번호를 꺼낸다."""
    u = (url or "").strip()
    m = re.search(r"/(?:file|design)/([A-Za-z0-9]+)", u)
    if not m:
        if re.fullmatch(r"[A-Za-z0-9]{10,}", u):
            return u, None
        raise 읽기오류("Figma 파일 주소가 아닙니다. figma.com/design/... 주소를 붙여넣어 주세요.")
    node = None
    n = re.search(r"node-id=([0-9]+)[-:]([0-9]+)", u)
    if n:
        node = f"{n.group(1)}:{n.group(2)}"
    return m.group(1), node


def _부르기(길, 토큰):
    req = urllib.request.Request("https://api.figma.com" + 길,
                                 headers={"X-Figma-Token": 토큰})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise 읽기오류("Figma 열쇠가 없거나 이 파일을 볼 권한이 없습니다.")
        if e.code == 404:
            raise 읽기오류("그런 Figma 파일이 없습니다. 주소를 다시 확인해 주세요.")
        raise 읽기오류(f"Figma에서 읽지 못했습니다 (오류 {e.code}).")
    except urllib.error.URLError:
        raise 읽기오류("인터넷(또는 Figma)에 닿지 못했습니다.")


def _화면들(부모, 페이지이름, 묶음=""):
    """프레임을 모은다. 섹션(묶음)이면 그 안쪽 프레임까지 펼쳐 본다."""
    나온것 = []
    for c in 부모.get("children", []) or []:
        종류 = c.get("type")
        if 종류 == "SECTION":
            안쪽 = _화면들(c, 페이지이름, c.get("name", ""))
            나온것 += 안쪽 or [_한개(c, 페이지이름, 묶음)]
        elif 종류 in ("FRAME", "COMPONENT", "COMPONENT_SET", "INSTANCE"):
            나온것.append(_한개(c, 페이지이름, 묶음))
    return 나온것


def _한개(c, 페이지이름, 묶음):
    box = c.get("absoluteBoundingBox") or {}
    return {"id": c.get("id"), "이름": c.get("name", ""), "묶음": 묶음,
            "페이지이름": 페이지이름,
            "x": round(box.get("x") or 0), "y": round(box.get("y") or 0),
            "폭": round(box.get("width") or 0), "높이": round(box.get("height") or 0)}


def 파일읽기(url):
    """페이지 목록과, 페이지마다의 화면(프레임) 목록을 돌려준다.

    섹션으로 묶여 있으면 그 안쪽 화면까지 펼쳐서 가져온다."""
    토큰 = 열쇠()
    if not 토큰:
        raise 읽기오류("Figma 열쇠가 아직 없습니다. '열쇠 넣기'에 한 번만 넣어 주세요.")
    키, _ = 주소풀기(url)
    데이터 = _부르기(f"/v1/files/{키}?depth=3", 토큰)

    페이지들 = []
    for p in 데이터.get("document", {}).get("children", []):
        if p.get("type") != "CANVAS":
            continue
        이름 = p.get("name", "")
        페이지들.append({"id": p.get("id"), "이름": 이름, "화면": _화면들(p, 이름)})

    return {"파일열쇠": 키, "파일이름": 데이터.get("name", ""), "페이지": 페이지들}


def 그림주소(파일열쇠, 노드들, 배율=1):
    """고른 화면의 미리보기 그림 주소(없으면 빈 표)."""
    토큰 = 열쇠()
    if not 토큰 or not 노드들:
        return {}
    try:
        d = _부르기(f"/v1/images/{파일열쇠}?ids={','.join(노드들[:60])}"
                  f"&format=png&scale={배율}", 토큰)
        return {k: v for k, v in (d.get("images") or {}).items() if v}
    except 읽기오류:
        return {}
