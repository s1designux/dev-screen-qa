#!/usr/bin/env python3
"""포털 자료함에서 검수 페이지 한 장을 꺼내 시험지 세트 모양으로 담는다.

시험 화면이 열다섯 장뿐이라 새 규칙의 근거가 안 나오는 문제를 풀려고 만들었다.
꺼내는 것은 셋이다 — 시안 그림 · 개발 그림 · 시안 요소(플러그인이 보낸 native 모양 그대로).

**여기서 시험지를 바로 고치지 않는다.** 꺼낸 것은 `--둘곳`(기본: 시험화면후보/)에 담고,
시험지에 넣을지는 사람이 보고 정한다. 넣고 나면 출발점 성적을 다시 재야 한다
(시험지 지문이 바뀌어 앞서 잰 성적과 못 견준다 — 시험지/기준.md).

    python3 scripts/시험화면꺼내기.py --목록                 # 꺼낼 수 있는 페이지 보기
    python3 scripts/시험화면꺼내기.py --프레임 218:12757 --이름 가입약관
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[1]
본폴더 = Path(os.path.expanduser("~/dev-screen-qa"))
자료함 = 본폴더 / "mvp0" / "mvp0-real.db"
그림방 = 본폴더 / "mvp0" / "uploads"


def 잇기() -> sqlite3.Connection:
    if not 자료함.exists():
        sys.exit(f"포털 자료함을 찾지 못했습니다: {자료함}")
    c = sqlite3.connect(f"file:{자료함}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def 페이지들(c: sqlite3.Connection) -> list[dict]:
    본 = []
    줄들 = c.execute("""
        select p.uuid, p.name, p.design_img, s.human_key hk, l.design_id,
               (select r.dev_img from inspection_run r
                 where r.page_id = p.uuid order by r.round desc limit 1) dev
          from inspection_page p
          join screen s on s.uuid = p.screen_id
          left join page_design_link l on l.page_id = p.uuid
         where p.removed_at is null
    """).fetchall()
    for r in 줄들:
        if not r["design_id"]:
            continue
        것 = c.execute("select frame, elements from design_elements where design_id=?",
                      (r["design_id"],)).fetchone()
        if not 것:
            continue
        틀 = json.loads(것[0])
        시안 = 그림방 / str(r["design_img"] or "")
        개발 = 그림방 / str(r["dev"] or "")
        if not (r["design_img"] and 시안.exists() and r["dev"] and 개발.exists()):
            continue
        후보수 = c.execute("""select count(*) from auto_candidate a
                              join auto_run ar on ar.id = a.auto_run_id
                             where ar.page_id = ?""", (r["uuid"],)).fetchone()[0]
        본.append({"page": r["uuid"], "name": r["name"], "hk": r["hk"],
                   "design_id": r["design_id"], "frame": 틀, "후보": 후보수,
                   "시안": 시안, "개발": 개발, "요소": 것[1]})
    return 본


def 담기(한장: dict, 이름: str, 둘곳: Path) -> dict:
    둘곳.mkdir(parents=True, exist_ok=True)
    틀 = 한장["frame"]
    요소파일 = f"elements_{이름}.json"
    시안파일 = f"design_{이름}_{틀['width']}x{틀['height']}.png"
    from PIL import Image
    with Image.open(한장["개발"]) as im:
        개발파일 = f"dev_{이름}_{im.width}x{im.height}.png"
    (둘곳 / 요소파일).write_text(json.dumps(
        {"frame": 틀, "native": json.loads(한장["요소"])}, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(한장["시안"], 둘곳 / 시안파일)
    shutil.copy2(한장["개발"], 둘곳 / 개발파일)
    return {"이름": 이름, "요소": 요소파일, "시안": 시안파일, "개발": 개발파일}


def main() -> int:
    받기 = argparse.ArgumentParser(description="포털에서 시험 화면 꺼내기")
    받기.add_argument("--목록", action="store_true", help="꺼낼 수 있는 페이지를 보여준다")
    받기.add_argument("--프레임", default="", help="꺼낼 페이지의 시안 프레임 id")
    받기.add_argument("--이름", default="", help="시험지에서 쓸 짧은 이름")
    받기.add_argument("--둘곳", default="시험화면후보", help="꺼낸 것을 담을 자리")
    args = 받기.parse_args()

    c = 잇기()
    모두 = 페이지들(c)
    if args.목록 or not args.프레임:
        for h in sorted(모두, key=lambda x: (x["hk"], str(x["name"]))):
            틀 = h["frame"]
            print(f"{틀.get('id'):18s} {h['hk']:22s} {str(h['name'])[:36]:38s} "
                  f"{틀.get('width')}x{틀.get('height')} 후보{h['후보']:>4}")
        return 0

    고른것 = [h for h in 모두 if h["frame"].get("id") == args.프레임]
    if not 고른것:
        print(f"그 프레임을 찾지 못했습니다: {args.프레임}")
        return 2
    if not args.이름:
        print("--이름 을 함께 주세요(시험지에서 쓸 짧은 이름)")
        return 2
    적은것 = 담기(고른것[0], args.이름, 뿌리 / args.둘곳)
    print(json.dumps(적은것, ensure_ascii=False))
    print(f"담은 자리: {args.둘곳}/  — 시험지에 넣을지는 사람이 정합니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
