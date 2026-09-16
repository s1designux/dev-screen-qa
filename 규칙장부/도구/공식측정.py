#!/usr/bin/env python3
"""공식 측정 — 검수기 성적은 이 프로그램이 잰 것만 공식이다.

만든 손이 자기 것을 재서 늘 "통과"가 되던 구멍을 막는다. 규칙:
 · 시험지(`시험지/`)는 읽기만 한다. 재는 동안 한 글자도 고치지 않는다 — 앞뒤로 지문을 맞대 본다.
 · 재는 일은 시험지를 임시 자리에 복사해서 한다. 결과는 `규칙장부/측정/<측정번호>/` 에만 쌓인다.
 · 한 화면이라도 못 재면 '통과'가 아니라 **판정 불가**다. 빠진 채로 합계를 내지 않는다.
 · 엔진·시험지·도구의 지문을 성적과 함께 적는다. 지문이 다르면 견줄 수 없는 성적이다.

    python3 규칙장부/도구/공식측정.py [--엔진 engine/ui.html] [--이름 붙일이름] [--자체검사안함]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[2]
시험지방 = 뿌리 / "시험지"
측정방 = 뿌리 / "규칙장부" / "측정"
장부 = 뿌리 / "규칙장부" / "측정장부.jsonl"
크롬 = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def 지문(경로: Path) -> str:
    h = hashlib.sha256()
    with open(경로, "rb") as f:
        for 덩이 in iter(lambda: f.read(1 << 20), b""):
            h.update(덩이)
    return h.hexdigest()


def 시험지지문() -> dict:
    """재는 데 쓰이는 시험지 파일의 지문. 재기 전후로 맞대 본다.

    `양면/` 은 규칙마다 새 장이 늘어나는 자리라 여기 넣지 않는다 — 장이 하나 는다고
    앞서 잰 성적이 못 쓰게 되면 안 된다. 양면 시험지 한 장의 지문은 그 시험 결과에 따로 적힌다.
    """
    것 = {}
    for p in sorted(시험지방.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        길 = p.relative_to(시험지방)
        if 길.parts[0] == "양면":
            continue
        것[str(길)] = 지문(p)
    return 것


def 볼것세기(결과: dict) -> dict:
    후보 = 결과.get("candidates") or []
    접힌것 = [c for c in 후보 if c.get("status") in ("variable", "excluded")]
    return {"후보": len(후보), "접힘": len(접힌것), "볼것": len(후보) - len(접힌것)}


def 한화면재기(일터: Path, 엔진: Path, 화면: dict, 시안최대: int) -> dict:
    이름 = 화면["이름"]
    환경 = dict(os.environ,
               ELEMENTS_JSON=화면["요소"],
               DESIGN_PNG=화면["시안"],
               DEV_PNG=화면["개발"],
               DESIGN_MAX=str(시안최대))
    정렬고정 = 화면.get("정렬고정")
    환경["FORCE_TY"] = "" if 정렬고정 in (None, "") else str(정렬고정)
    잰것 = {"이름": 이름, "잰나": "판정 불가"}
    try:
        돈것 = subprocess.run([shutil.which("node") or "node", "run.js", str(엔진), 이름],
                            cwd=일터, env=환경, capture_output=True, text=True, timeout=600)
    except Exception as e:  # noqa: BLE001
        잰것["까닭"] = f"돌리지 못함: {e}"
        return 잰것
    결과파일 = 일터 / f"{이름}.json"
    if 돈것.returncode != 0 or not 결과파일.exists():
        잰것["까닭"] = (돈것.stderr or 돈것.stdout or "").strip()[-400:] or f"종료코드 {돈것.returncode}"
        return 잰것
    try:
        결과 = json.loads(결과파일.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        잰것["까닭"] = f"결과를 읽지 못함: {e}"
        return 잰것
    잰것.update(볼것세기(결과))
    잰것["잰나"] = "잼"
    정렬 = 결과.get("model") or {}
    잰것["정렬"] = {k: 정렬.get(k) for k in ("mode", "s", "tx", "ty", "score", "anchors")}
    잰것["띠"] = len(정렬.get("bands") or [])
    return 잰것


def 정답보기(일터: Path, 정답: dict) -> dict:
    결과파일 = 일터 / f"{정답['화면']}.json"
    것 = {"이름": 정답["이름"], "기대": 정답["기대"], "산것": None, "판정": "판정 불가"}
    if not 결과파일.exists():
        것["까닭"] = f"{정답['화면']} 결과가 없다"
        return 것
    돈것 = subprocess.run([shutil.which("node") or "node", 정답["검사도구"], 결과파일.name],
                        cwd=일터, capture_output=True, text=True, timeout=300)
    글 = (돈것.stdout or "") + (돈것.stderr or "")
    것["적은것"] = 글.strip()[-2000:]
    맞은것 = re.search(r"정답 생존 (\d+)/(\d+)", 글)
    if not 맞은것:
        것["까닭"] = "정답 생존 줄을 찾지 못했다"
        return 것
    것["산것"], 것["전체"] = int(맞은것.group(1)), int(맞은것.group(2))
    것["판정"] = "지킴" if 것["산것"] >= 정답["기대"] else "떨어짐"
    return 것


def 자체검사(엔진: Path) -> dict:
    것 = {"판정": "판정 불가"}
    if not Path(크롬).exists():
        것["까닭"] = "크롬을 찾지 못했다"
        return 것
    try:
        돈것 = subprocess.run([크롬, "--headless=new", "--no-sandbox", "--disable-gpu",
                             "--virtual-time-budget=60000", "--dump-dom",
                             f"file://{엔진.resolve()}?selftest=1"],
                            capture_output=True, text=True, timeout=300)
    except Exception as e:  # noqa: BLE001
        것["까닭"] = f"돌리지 못함: {e}"
        return 것
    글 = 돈것.stdout or ""
    것["통과"] = 글.count("✓")
    것["실패"] = 글.count("✗")
    한마디 = re.search(r"SELFTEST ([A-Z]+)", 글)
    것["한마디"] = 한마디.group(1) if 한마디 else None
    if 것["통과"] or 것["실패"]:
        것["판정"] = "실패 없음" if 것["실패"] == 0 else "실패 있음"
    return 것


def 다음측정번호() -> str:
    측정방.mkdir(parents=True, exist_ok=True)
    이미 = [p.name for p in 측정방.iterdir() if p.is_dir() and p.name[:1].isdigit()]
    번호 = max([int(n.split("-")[0]) for n in 이미] or [0]) + 1
    return f"{번호:03d}-{datetime.now().strftime('%Y%m%d-%H%M')}"


def main() -> int:
    받기 = argparse.ArgumentParser(description="공식 측정 — 검수기 성적 재기")
    받기.add_argument("--엔진", default="engine/ui.html", help="잴 검수기 파일")
    받기.add_argument("--이름", default="", help="이 측정에 붙일 한마디(무엇을 바꾼 판인지)")
    받기.add_argument("--자체검사안함", action="store_true", help="엔진 자체 검사를 건너뛴다")
    args = 받기.parse_args()

    엔진 = Path(args.엔진)
    if not 엔진.is_absolute():
        엔진 = (뿌리 / 엔진).resolve()
    if not 엔진.exists():
        print(f"검수기를 찾지 못했습니다: {엔진}\n→ 판정 불가")
        return 2
    if not (시험지방 / "목록.json").exists():
        print(f"시험지를 찾지 못했습니다: {시험지방}\n→ 판정 불가")
        return 2

    목록 = json.loads((시험지방 / "목록.json").read_text(encoding="utf-8"))
    앞지문 = 시험지지문()
    측정번호 = 다음측정번호()
    둘곳 = 측정방 / 측정번호
    둘곳.mkdir(parents=True, exist_ok=True)

    잰것 = {
        "측정번호": 측정번호,
        "잰때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "이름": args.이름,
        "엔진": {"자리": str(엔진), "지문": 지문(엔진)},
        "시험지판": 목록.get("판"),
        "시험지지문": hashlib.sha256(
            json.dumps(앞지문, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "화면": [], "정답": [], "판정": "판정 불가",
    }

    with tempfile.TemporaryDirectory() as 임시:
        일터 = Path(임시) / "재는자리"
        일터.mkdir()
        for 방 in ("세트", "정답", "도구"):
            for p in (시험지방 / 방).iterdir():
                if p.is_file():
                    shutil.copy2(p, 일터 / p.name)
        for 화면 in 목록["화면"]:
            잰것["화면"].append(한화면재기(일터, 엔진, 화면, int(목록.get("시안최대", 4096))))
        for 정답 in 목록.get("정답", []):
            잰것["정답"].append(정답보기(일터, 정답))
        # 화면별 원본 결과는 한 덩이로 묶어 둔다(한 번 재면 1.2MB — 낱장으로 쌓으면 저장소가 금세 무거워진다).
        이름들 = {c["이름"] for c in 목록["화면"]}
        묶을것 = sorted(p for p in 일터.glob("*.json") if p.stem in 이름들)
        if 묶을것:
            with tarfile.open(둘곳 / "원본결과.tar.gz", "w:gz") as 묶음:
                for p in 묶을것:
                    묶음.add(p, arcname=p.name)
        풀곳 = 둘곳 / "화면별"
        풀곳.mkdir(exist_ok=True)
        for p in 묶을것:
            shutil.copy2(p, 풀곳 / p.name)

    잰것["자체검사"] = {"판정": "건너뜀"} if args.자체검사안함 else 자체검사(엔진)
    뒷지문 = 시험지지문()
    잰것["시험지 그대로인가"] = (앞지문 == 뒷지문)
    바뀐것 = sorted(set(앞지문) ^ set(뒷지문)) + sorted(
        k for k in set(앞지문) & set(뒷지문) if 앞지문[k] != 뒷지문[k])
    if 바뀐것:
        잰것["재는 동안 바뀐 시험지"] = 바뀐것

    못잰것 = [c for c in 잰것["화면"] if c["잰나"] != "잼"]
    떨어진정답 = [a for a in 잰것["정답"] if a["판정"] != "지킴"]
    if 못잰것 or not 잰것["시험지 그대로인가"]:
        잰것["판정"] = "판정 불가"
    elif 떨어진정답:
        잰것["판정"] = "정답 떨어짐"
    elif 잰것["자체검사"].get("판정") == "실패 있음":
        잰것["판정"] = "자체검사 실패"
    else:
        잰것["판정"] = "잼"
        잰것["볼것합계"] = sum(c["볼것"] for c in 잰것["화면"])

    (둘곳 / "측정.json").write_text(json.dumps(잰것, ensure_ascii=False, indent=2), encoding="utf-8")
    장부.parent.mkdir(parents=True, exist_ok=True)
    with open(장부, "a", encoding="utf-8") as f:
        f.write(json.dumps({k: 잰것[k] for k in
                            ("측정번호", "잰때", "이름", "엔진", "시험지판", "시험지지문",
                             "판정") if k in 잰것}
                           | {"볼것합계": 잰것.get("볼것합계"),
                              "정답": [(a["이름"], a.get("산것"), a["기대"]) for a in 잰것["정답"]],
                              "자체검사": 잰것["자체검사"].get("판정")},
                           ensure_ascii=False) + "\n")

    print(f"측정번호 {측정번호}   검수기 {엔진.name} ({잰것['엔진']['지문'][:12]}…)")
    print(f"{'화면':10s} {'후보':>6s} {'접힘':>6s} {'볼것':>6s}  정렬")
    for c in 잰것["화면"]:
        if c["잰나"] != "잼":
            print(f"{c['이름']:10s} {'판정 불가':>18s}  {c.get('까닭','')[:60]}")
            continue
        정 = c.get("정렬") or {}
        print(f"{c['이름']:10s} {c['후보']:6d} {c['접힘']:6d} {c['볼것']:6d}"
              f"  ty={정.get('ty')} 띠={c.get('띠')}")
    if "볼것합계" in 잰것:
        print(f"{'합계':10s} {'':6s} {'':6s} {잰것['볼것합계']:6d}")
    for a in 잰것["정답"]:
        print(f"정답 {a['이름']}: {a.get('산것')}/{a.get('전체', a['기대'])} → {a['판정']}")
    ㅈ = 잰것["자체검사"]
    print(f"자체검사: {ㅈ.get('판정')} (통과 {ㅈ.get('통과')} 실패 {ㅈ.get('실패')})")
    print(f"판정: {잰것['판정']}")
    print(f"적은 자리: 규칙장부/측정/{측정번호}/  ·  규칙장부/측정장부.jsonl")
    return 0 if 잰것["판정"] == "잼" else 1


if __name__ == "__main__":
    raise SystemExit(main())
