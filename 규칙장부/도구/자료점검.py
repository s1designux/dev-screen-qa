#!/usr/bin/env python3
"""자료 점검 — 정본 자료함이 맞는지, 백업이 실제로 되살아나는지 프로그램이 확인한다.

사람이 눈으로 고르지 않는다. 이 도구가 재고, 숫자는 `규칙장부/자료/자료점검-최근.json` 에만 적는다.
사람이 확정한 것(정본 · 치우는 조건)은 `규칙장부/자료목록.md` 에 손으로 적는다.

하는 일 다섯:
 1. 자료함 후보를 모은다 — 정본 후보 · 다른 .db · .bak-* · 백업 폴더 사본.
 2. 각각의 지문(sha256) · 크기 · 마지막 수정 · 주요 표 행수를 잰다.
 3. 정본 후보에 **없는 판정·이력**이 다른 사본에 있는지 열쇠(uuid/id)로 대조한다.
 4. 되살리기 시험 — 사본을 임시 자리에 복사해 열고, 무결성 검사와 표 읽기가 되는지 본다.
 5. (--포털시험) 하루 백업 최신 한 벌을 임시 자리에 되살려 포털을 임시 포트로 띄우고,
    화면 목록 · 화면 · 페이지 상세 · 그림이 실제로 열리는지 확인한 뒤 끈다. 정본은 건드리지 않는다.

실행이 끊기거나 표를 못 읽으면 '통과'가 아니라 **판정 불가**로 적는다.

    python3 규칙장부/도구/자료점검.py [--자료뿌리 <폴더>] [--포털시험]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import time
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(뿌리))
import 설정  # noqa: E402

# 판정·이력이 담기는 표 — 사본에만 있는 행이 하나라도 있으면 그 사본은 못 치운다.
판정표 = [
    "inspection_issue", "issue_history",
    "auto_candidate", "auto_candidate_event", "auto_range",
    "rule_verdict", "policy_rule",
    "intake_event", "page_design_event", "page_capture_event", "page_move_event",
]
세는표 = ["screen", "inspection_page", "inspection_run", "design_elements"] + 판정표


def 지문(경로: Path, 조각=1 << 20) -> str:
    h = hashlib.sha256()
    with open(경로, "rb") as f:
        while True:
            덩이 = f.read(조각)
            if not 덩이:
                break
            h.update(덩이)
    return h.hexdigest()


def 열기(경로: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{경로}?mode=ro", uri=True)


def 행수(db: sqlite3.Connection, 표: str):
    try:
        return db.execute(f"select count(*) from {표}").fetchone()[0]
    except sqlite3.Error:
        return None


def 열쇠들(db: sqlite3.Connection, 표: str):
    """그 표의 행을 가리키는 열쇠 모음. 표가 없으면 None."""
    try:
        칸 = [r[1] for r in db.execute(f"pragma table_info({표})")]
        if not 칸:
            return None
        열쇠 = "uuid" if "uuid" in 칸 else ("id" if "id" in 칸 else None)
        if 열쇠 is None:
            return None
        return {r[0] for r in db.execute(f"select {열쇠} from {표}")}
    except sqlite3.Error:
        return None


def 재기(경로: Path) -> dict:
    것 = {
        "자리": str(경로),
        "크기": 경로.stat().st_size,
        "마지막수정": datetime.fromtimestamp(경로.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        "지문": 지문(경로),
        "행수": {},
        "읽기": "됨",
    }
    if 것["크기"] == 0:
        것["읽기"] = "빈 파일"
        return 것
    try:
        db = 열기(경로)
        for 표 in 세는표:
            n = 행수(db, 표)
            if n is not None:
                것["행수"][표] = n
        db.close()
    except sqlite3.Error as e:
        것["읽기"] = f"못 읽음: {e}"
    return 것


def 되살리기시험(경로: Path) -> dict:
    """사본을 임시 자리에 옮겨 열어 본다. 원본은 건드리지 않는다."""
    결과 = {"무결성": None, "표읽기": None, "판정": "판정 불가"}
    if 경로.stat().st_size == 0:
        결과["판정"] = "빈 파일 — 되살릴 것 없음"
        return 결과
    with tempfile.TemporaryDirectory() as 임시:
        사본 = Path(임시) / 경로.name
        try:
            shutil.copy2(경로, 사본)
            db = sqlite3.connect(사본)
            결과["무결성"] = db.execute("pragma integrity_check").fetchone()[0]
            읽은표 = 0
            for 표 in 세는표:
                if 행수(db, 표) is not None:
                    읽은표 += 1
            db.close()
            결과["표읽기"] = 읽은표
            if 결과["무결성"] == "ok" and 읽은표 > 0:
                결과["판정"] = "되살아남"
            else:
                결과["판정"] = "판정 불가"
        except Exception as e:  # noqa: BLE001 — 무엇이든 실패는 '판정 불가'
            결과["오류"] = str(e)
            결과["판정"] = "판정 불가"
    return 결과


def _빈포트() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    포트 = s.getsockname()[1]
    s.close()
    return 포트


def _받기(주소: str, 시간=10):
    try:
        with urllib.request.urlopen(주소, timeout=시간) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def 포털시험(백업방: Path) -> dict:
    """하루 백업 최신 한 벌을 임시 자리에 되살려 포털이 실제로 여는지 본다."""
    사본들 = sorted(백업방.glob("*/mvp0-real.db"))
    if not 사본들:
        return {"판정": "판정 불가", "까닭": f"백업을 찾지 못함: {백업방}"}
    골라온것 = 사본들[-1]
    것 = {"되살린것": str(골라온것), "본것": {}, "판정": "판정 불가"}
    포트 = _빈포트()
    with tempfile.TemporaryDirectory() as 임시:
        방 = Path(임시) / "mvp0"
        방.mkdir(parents=True)
        shutil.copy2(골라온것, 방 / "mvp0-real.db")
        그림 = 골라온것.parent / "uploads"
        if 그림.exists():
            shutil.copytree(그림, 방 / "uploads")
        else:
            (방 / "uploads").mkdir()
        환경 = dict(os.environ,
                   QA_PORTAL_PORT=str(포트),
                   QA_PORTAL_DB=str(방 / "mvp0-real.db"),
                   QA_PORTAL_UPLOADS=str(방 / "uploads"))
        기록 = Path(임시) / "포털.log"
        with open(기록, "wb") as 적기:
            돌던것 = subprocess.Popen([sys.executable, str(뿌리 / "mvp0" / "portal.py")],
                                    stdout=적기, stderr=subprocess.STDOUT, env=환경)
            try:
                바탕 = f"http://127.0.0.1:{포트}"
                코드, 몸 = 0, b""
                for _ in range(40):          # 최대 10초 기다린다
                    코드, 몸 = _받기(바탕 + "/")
                    if 코드:
                        break
                    time.sleep(0.25)
                것["본것"]["화면 목록"] = 코드
                글 = 몸.decode("utf-8", "replace")
                화면 = re.findall(r'href="(/screen/[^"]+)"', 글)
                if 화면:
                    코드, 몸 = _받기(바탕 + 화면[0])
                    것["본것"]["화면"] = 코드
                    글 = 몸.decode("utf-8", "replace")
                    페이지 = re.findall(r"location\.href='(/screen/[^']+/page/[0-9a-f]+)'", 글)
                    if 페이지:
                        코드, 몸 = _받기(바탕 + 페이지[0])
                        것["본것"]["페이지 상세"] = 코드
                        글 = 몸.decode("utf-8", "replace")
                        그림주소 = re.findall(r"/uploads/[A-Za-z0-9_.가-힣-]+", 글)
                        if 그림주소:
                            코드, 몸 = _받기(바탕 + 그림주소[0])
                            것["본것"]["그림"] = 코드
                            것["그림크기"] = len(몸)
            finally:
                돌던것.terminate()
                try:
                    돌던것.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    돌던것.kill()
            것["포털이 남긴 말"] = 기록.read_text(encoding="utf-8", errors="replace").strip()[-500:]
    봐야할것 = ["화면 목록", "화면", "페이지 상세", "그림"]
    if all(것["본것"].get(k) == 200 for k in 봐야할것):
        것["판정"] = "되살아나고 열림"
    return 것


def 대조(정본: Path, 사본: Path) -> dict:
    """사본에만 있는 판정·이력 행을 표별로 센다."""
    나옴 = {}
    try:
        a, b = 열기(정본), 열기(사본)
    except sqlite3.Error as e:
        return {"오류": str(e)}
    for 표 in 판정표:
        가진것, 사본것 = 열쇠들(a, 표), 열쇠들(b, 표)
        if 가진것 is None or 사본것 is None:
            continue
        남은것 = 사본것 - 가진것
        if 남은것:
            나옴[표] = len(남은것)
    a.close()
    b.close()
    return 나옴


def 그림확인(정본: Path, 그림방: Path) -> dict:
    """정본이 가리키는 그림 파일이 실제로 있는지."""
    if not 그림방.exists():
        return {"그림방": str(그림방), "없음": "그림방을 찾지 못함"}
    있는것 = {p.name for p in 그림방.iterdir() if p.is_file()}
    db = 열기(정본)
    가리킨것 = set()
    for 표, 칸 in [("inspection_run", "dev_img"), ("inspection_page", "dev_img"),
                  ("inspection_page", "design_img"), ("intake_asset", "filename")]:
        try:
            for (v,) in db.execute(f"select {칸} from {표} where {칸} is not null and {칸} != ''"):
                가리킨것.add(str(v))
        except sqlite3.Error:
            pass
    # 값 대조가 읽는 자료는 칸이 아니라 페이지 이름표로 붙어 있다.
    try:
        for (u,) in db.execute("select uuid from inspection_page"):
            for 꼬리 in ("_design.json", "_dev값.json"):
                이름 = f"{u}{꼬리}"
                if 이름 in 있는것:
                    가리킨것.add(이름)
    except sqlite3.Error:
        pass
    db.close()
    빠진것 = sorted(가리킨것 - 있는것)
    남는것 = sorted(있는것 - 가리킨것)
    return {
        "그림방": str(그림방),
        "그림파일": len(있는것),
        "가리킨것": len(가리킨것),
        "빠진것수": len(빠진것),
        "빠진것": 빠진것[:20],
        "안가리킨것수": len(남는것),
        "안가리킨것": 남는것[:20],
    }


def 모으기(자료뿌리: Path, 정본: Path) -> list[Path]:
    것 = []
    for p in sorted((자료뿌리 / "mvp0").glob("*.db")):
        if p != 정본:
            것.append(p)
    for p in sorted(자료뿌리.glob("*.db")):
        if p != 정본:
            것.append(p)
    것 += sorted((자료뿌리 / "mvp0").glob("mvp0-real.db.bak-*"))
    백업방 = Path.home() / "dev-screen-qa-백업"
    if 백업방.exists():
        것 += sorted(백업방.glob("*/mvp0-real.db"))
    return 것


def main() -> int:
    받기 = argparse.ArgumentParser(description="자료 점검 — 정본과 되살리기 확인")
    받기.add_argument("--자료뿌리", default=None, help="검수 자료가 있는 폴더 (기본: 설정의 자료.뿌리)")
    받기.add_argument("--포털시험", action="store_true",
                    help="백업 최신 한 벌을 임시로 되살려 포털이 실제로 여는지 본다")
    args = 받기.parse_args()

    자료뿌리 = Path(args.자료뿌리 or 설정.자리("자료.뿌리") or 뿌리).expanduser().resolve()
    정본 = (자료뿌리 / 설정.값("포털.자료함")).resolve()
    그림방 = (자료뿌리 / 설정.값("포털.그림보관")).resolve()

    if not 정본.exists():
        print(f"정본 후보를 찾지 못했습니다: {정본}")
        print("→ 판정 불가")
        return 2

    잰것 = {
        "잰때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "자료뿌리": str(자료뿌리),
        "정본후보": 재기(정본),
        "그림": 그림확인(정본, 그림방),
        "사본": [],
    }
    잰것["정본후보"]["되살리기"] = 되살리기시험(정본)

    for p in 모으기(자료뿌리, 정본):
        한벌 = 재기(p)
        한벌["되살리기"] = 되살리기시험(p)
        한벌["정본에없는것"] = 대조(정본, p) if 한벌["읽기"] == "됨" else {}
        잰것["사본"].append(한벌)

    if args.포털시험:
        잰것["포털시험"] = 포털시험(Path.home() / "dev-screen-qa-백업")

    적을곳 = 뿌리 / "규칙장부" / "자료" / "자료점검-최근.json"
    적을곳.parent.mkdir(parents=True, exist_ok=True)
    적을곳.write_text(json.dumps(잰것, ensure_ascii=False, indent=2), encoding="utf-8")

    ㅈ = 잰것["정본후보"]
    print(f"정본 후보  {정본}")
    print(f"  지문 {ㅈ['지문'][:16]}…  크기 {ㅈ['크기']:,}  마지막 수정 {ㅈ['마지막수정']}")
    print(f"  되살리기 {ㅈ['되살리기']['판정']} (무결성 {ㅈ['되살리기']['무결성']})")
    ㄱ = 잰것["그림"]
    if "빠진것수" in ㄱ:
        print(f"  가리킨 자료 {ㄱ['가리킨것']}개 중 없는 것 {ㄱ['빠진것수']}개"
              f" / 그림방 {ㄱ['그림파일']}개 (아무도 안 가리키는 것 {ㄱ['안가리킨것수']}개)")
    print()
    print(f"{'사본':52s} {'되살리기':10s} 정본에 없는 판정·이력")
    막힌것 = 0
    for 한벌 in 잰것["사본"]:
        이름 = Path(한벌["자리"]).name
        윗방 = Path(한벌["자리"]).parent.name
        보일이름 = 이름 if 윗방 in ("mvp0", 자료뿌리.name) else f"{윗방}/{이름}"
        남은것 = 한벌.get("정본에없는것") or {}
        말 = ", ".join(f"{k} {v}" for k, v in 남은것.items()) if 남은것 else "없음"
        print(f"{보일이름:52s} {한벌['되살리기']['판정']:10s} {말}")
        if 한벌["되살리기"]["판정"] == "판정 불가":
            막힌것 += 1
    if "포털시험" in 잰것:
        ㅍ = 잰것["포털시험"]
        print()
        print(f"포털 되살리기 시험  {Path(ㅍ.get('되살린것', '')).parent.name or '—'}  →  {ㅍ['판정']}")
        for 무엇, 코드 in (ㅍ.get("본것") or {}).items():
            print(f"  {무엇:10s} {코드}")
        if ㅍ.get("까닭"):
            print(f"  까닭 {ㅍ['까닭']}")
    print()
    print(f"잰 것을 적었습니다: {적을곳.relative_to(뿌리)}")
    if 막힌것:
        print(f"되살리지 못한 사본 {막힌것}개 — 판정 불가로 적었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
