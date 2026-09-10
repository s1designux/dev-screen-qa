"""찍은 사진을 검수 포털에 접수한다.

촬영기와 포털은 서로 붙어 있지 않다. 접점은 사진 이름 규칙 하나뿐이고,
여기서는 그 사진을 포털이 읽는 자리(uploads)에 옮기고 포털 데이터에 한 줄씩 적는다.

넣는 것만 한다. 이미 있는 검수 데이터는 건드리지 않는다.
"""
import json
import shutil
import sqlite3
import time
import uuid as uuidmod
from datetime import datetime
from pathlib import Path

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parent


class 접수오류(Exception):
    pass


def _디자인그림(작업, 노드들):
    """고른 Figma 화면의 그림을 받아 온다. 못 받으면 조용히 건너뛴다(검수는 계속된다)."""
    if not 노드들:
        return {}
    try:
        import urllib.request
        import design_source as 디자인
        주소표 = 디자인.그림주소(작업.get("파일", {}).get("파일열쇠", ""), 노드들)
        받은것 = {}
        for 노드, 주소 in 주소표.items():
            try:
                with urllib.request.urlopen(주소, timeout=30) as r:
                    받은것[노드] = r.read()
            except Exception:
                pass
        return 받은것
    except Exception:
        return {}


def 포털자리():
    """포털의 데이터 파일과 사진 자리를 찾는다."""
    후보 = [
        뿌리.parent / "mvp0" / "mvp0-real.db",              # 같은 저장소 안
        Path.home() / "dev-screen-qa" / "mvp0" / "mvp0-real.db",   # 원래 작업 폴더
    ]
    for db in 후보:
        if db.exists():
            return db, db.parent / "uploads"
    raise 접수오류("검수 포털의 데이터 파일(mvp0-real.db)을 찾지 못했습니다.")


def _png크기(자료):
    if 자료[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(자료[16:20], "big"), int.from_bytes(자료[20:24], "big")


def _하나(conn, 물음, 값=()):
    r = conn.execute(물음, 값).fetchone()
    return r[0] if r else None


def _표있음(conn, 이름):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (이름,)).fetchone() is not None


def _시안판등록(conn, page, 노드, 작업, 초안줄, 시안이름, 시안, 지금):
    """시안을 포털의 '시안 판'(intake_design)으로도 등록하고 페이지에 잇는다.
    플러그인이 함께 보낸 요소 목록이 있으면 같이 넣어, 포털을 열면 자동 검수 후보가 바로 뜬다.
    포털이 아직 그 표를 만들지 않았으면(옛 포털) 조용히 건너뛴다 — 그림만으로도 검수는 된다."""
    if not all(_표있음(conn, t) for t in ("intake_asset", "intake_design", "design_elements", "page_design_link")):
        return
    import hashlib
    크기 = _png크기(시안)
    if not 크기:
        return
    열쇠 = (작업.get("파일", {}) or {}).get("파일열쇠") or ""
    if not 열쇠:
        이름 = (작업.get("파일", {}) or {}).get("파일이름") or ""
        열쇠 = ("name:" + 이름) if 이름 else "plugin"
    설정 = None
    요소 = None
    틀 = {}
    길 = 초안줄.get("검수요소파일", "")
    if 길 and Path(길).exists():
        try:
            꾸러미 = json.loads(Path(길).read_text(encoding="utf-8"))
            요소 = 꾸러미.get("요소")
            설정 = 꾸러미.get("설정")
            틀 = 꾸러미.get("틀") or {}
        except (ValueError, OSError):
            요소 = None
    자산 = uuidmod.uuid4().hex
    conn.execute("INSERT INTO intake_asset VALUES (?,?,?,?,?,?)",
                 (자산, 시안이름, hashlib.sha256(시안).hexdigest(), 크기[0], 크기[1], 지금))
    시안판 = uuidmod.uuid4().hex
    conn.execute("INSERT INTO intake_design VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (시안판, 열쇠, 노드 or 시안판, 초안줄.get("이름") or 초안줄.get("상태") or "디자인", "", 노드 or "",
                  자산, 지금, None, "Figma 플러그인",
                  json.dumps({"policy": 설정}, ensure_ascii=False) if isinstance(설정, dict) else ""))
    if isinstance(요소, list):
        conn.execute("INSERT OR REPLACE INTO design_elements VALUES (?,?,?,?,?)",
                     (시안판, 지금, None,
                      json.dumps({"id": 노드, "name": 초안줄.get("이름") or "", "width": 틀.get("폭") or 크기[0], "height": 틀.get("높이") or 크기[1]}, ensure_ascii=False),
                      json.dumps(요소, ensure_ascii=False)))
    conn.execute("INSERT OR REPLACE INTO page_design_link VALUES (?,?,?)", (page, 시안판, 지금))
    if _표있음(conn, "page_design_event"):
        conn.execute("INSERT INTO page_design_event VALUES (?,?,?,?,?,?,?,?)",
                     (uuidmod.uuid4().hex, page, 시안판, None, 시안이름, 지금, "촬영기 접수", "촬영 준비에서 시안과 함께 접수"))


def 접수(결과폴더, 작업, 고른파일=None, 검수자="촬영기"):
    """찍은 사진 묶음을 포털에 화면 1개 + 상태별 검수 페이지로 넣는다."""
    결과폴더 = Path(결과폴더)
    목록파일 = 결과폴더 / "찍은목록.json"
    if not 목록파일.exists():
        raise 접수오류("찍은 목록이 없습니다. 촬영이 끝난 뒤에 보내 주세요.")
    목록 = json.loads(목록파일.read_text(encoding="utf-8"))
    찍힌것 = 목록.get("찍힌것", [])
    if 고른파일:
        찍힌것 = [s for s in 찍힌것 if s["파일"] in set(고른파일)]
    if not 찍힌것:
        raise 접수오류("보낼 사진이 한 장도 없습니다.")

    db, 사진자리 = 포털자리()
    사진자리.mkdir(exist_ok=True)
    백업 = db.with_suffix(f".db.bak-{time.strftime('%Y%m%d')}")
    if not 백업.exists():
        shutil.copy2(db, 백업)                      # 하루 한 번, 되돌릴 수 있게

    초안 = {r["번호"]: r for r in 작업.get("초안", [])}
    노드표 = {s["화면번호"]: 초안.get(s["화면번호"], {}).get("노드", "") for s in 찍힌것}
    # Figma 플러그인이 그림까지 같이 보냈으면 그걸 쓴다(다시 받아 올 필요 없다).
    디자인 = {}
    남은노드 = []
    for 번호, 노드 in 노드표.items():
        길 = 초안.get(번호, {}).get("디자인그림", "")
        if 길 and Path(길).exists():
            디자인[노드] = Path(길).read_bytes()
        elif 노드:
            남은노드.append(노드)
    디자인.update(_디자인그림(작업, 남은노드))
    첫번호 = 찍힌것[0]["화면번호"]
    화면이름 = (초안.get(첫번호, {}).get("화면묶음")
             or 초안.get(첫번호, {}).get("이름") or 목록.get("앱이름", "화면"))
    사람키 = f"{작업.get('서비스코드','APP')}-AND-{첫번호}"

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    지금 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    프로젝트 = 목록.get("앱이름") or "이름없는 앱"
    pid = _하나(conn, "SELECT uuid FROM project WHERE name=?", (프로젝트,))
    if not pid:
        pid = uuidmod.uuid4().hex
        conn.execute("INSERT INTO project (uuid, name) VALUES (?,?)", (pid, 프로젝트))

    sid = _하나(conn, "SELECT uuid FROM screen WHERE human_key=?", (사람키,))
    if not sid:
        sid = uuidmod.uuid4().hex
        conn.execute(
            "INSERT INTO screen (uuid, project_id, human_key, name, platform, dev_keys, states, variants)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (sid, pid, 사람키, 화면이름, "android",
             json.dumps([작업.get("앱주소", "")], ensure_ascii=False),
             json.dumps([s.get("상태", "default") for s in 찍힌것], ensure_ascii=False),
             json.dumps([목록.get("화면크기", "")], ensure_ascii=False)))

    다음순서 = (_하나(conn, "SELECT MAX(seq) FROM inspection_page WHERE screen_id=?", (sid,)) or 0)
    넣은것 = []
    for i, s in enumerate(찍힌것, 1):
        사진 = 결과폴더 / s["파일"]
        if not 사진.exists():
            continue
        자료 = 사진.read_bytes()
        크기 = _png크기(자료)
        if not 크기:
            continue
        w, h = 크기

        page = uuidmod.uuid4().hex
        conn.execute(
            "INSERT INTO inspection_page (uuid, screen_id, seq, name, note, coord_ref_w, coord_ref_h)"
            " VALUES (?,?,?,?,?,?,?)",
            (page, sid, 다음순서 + i, s.get("상태", "default"),
             f"{목록.get('찍은때','')} 촬영 · {목록.get('기기','')}", w, h))

        # 시안의 '지금 값'(색·글꼴·크기 …)도 그림 옆에 함께 남긴다. 검수 때 원본값으로 쓴다.
        속 = 초안.get(s["화면번호"], {}).get("속") or []
        if 속:
            (사진자리 / f"{page}_design.json").write_text(
                json.dumps({"화면": s.get("상태", ""), "노드": 노드표.get(s["화면번호"], ""),
                            "요소": 속}, ensure_ascii=False, indent=1), encoding="utf-8")

        시안 = 디자인.get(노드표.get(s["화면번호"], ""))
        if 시안:
            시안이름 = f"{page}_design.png"
            (사진자리 / 시안이름).write_bytes(시안)
            conn.execute("UPDATE inspection_page SET design_img=? WHERE uuid=?",
                         (시안이름, page))
            _시안판등록(conn, page, 노드표.get(s["화면번호"], ""), 작업, 초안.get(s["화면번호"], {}),
                    시안이름, 시안, 지금)

        run = uuidmod.uuid4().hex
        이름 = f"{run}_dev.png"
        (사진자리 / 이름).write_bytes(자료)
        conn.execute(
            "INSERT INTO inspection_run (uuid, screen_id, page_id, round, inspector, created_at,"
            " pass_fail, dev_img, dev_img_w, dev_img_h, coord_ref_w, coord_ref_h)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run, sid, page, 1, 검수자, 지금, None, 이름, w, h, w, h))
        넣은것.append(s.get("상태", "default"))

    conn.commit()
    conn.close()
    return {"화면": 사람키, "화면이름": 화면이름, "페이지": 넣은것,
            "포털주소": f"http://127.0.0.1:8765/screen/{사람키}", "데이터파일": str(db)}
