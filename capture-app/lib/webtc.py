"""디자인 기준 TC대로 PC 웹 화면을 재고 찍는다.

포털('디자인 먼저' 흐름)이 내려준 **촬영요청.json** 이 "무엇을 찍을지"를 정한다.
디자인에 있는 화면·상태만 돌기 때문에, 시안에 없는 화면을 엉뚱하게 찍는 일이 없다.

포털은 디자인만 알고 개발 주소는 모른다. 그래서 **주소표** 한 장을 사람이 한 번 적는다
(화면 ID ↔ 개발 route 는 원래 사람이 1회 잇는 것이다 — CLAUDE.md 7번).

    py -3 lib/webtc.py 촬영요청.json 주소표.yaml [결과폴더]

주소표는 이름표와 같은 모양이고, 화면마다 `디자인이름` 칸으로 TC와 이어 준다.
"""
import json
import os
import sys
import time
from datetime import datetime

여기 = os.path.dirname(os.path.abspath(__file__))
뿌리 = os.path.dirname(여기)
sys.path.insert(0, 여기)

import nametag  # noqa: E402
import webshot  # noqa: E402


def 다듬기(글):
    return "".join((글 or "").split()).lower()


def 주소찾기(표, 사례):
    """TC 하나에 맞는 주소표 줄을 찾는다 — case_id 가 적혀 있으면 그것이 먼저."""
    for 줄 in 표["화면"]:
        if 줄.get("case_id") and 줄["case_id"] == 사례["case_id"]:
            return 줄
    이름 = 다듬기(사례.get("design_name"))
    for 줄 in 표["화면"]:
        if 다듬기(줄.get("디자인이름")) == 이름:
            return 줄
    for 줄 in 표["화면"]:              # 이름을 다 적기 번거로울 때는 일부만 적어도 된다
        적은것 = 다듬기(줄.get("디자인이름"))
        if 적은것 and (적은것 in 이름 or 이름 in 적은것):
            return 줄
    return None


def 짜기(요청, 표):
    """TC 목록 + 주소표 → webshot 이 알아듣는 화면 목록."""
    화면, 빠진것 = [], []
    for 사례 in 요청.get("cases", []):
        줄 = 주소찾기(표, 사례)
        if not 줄:
            빠진것.append({"case_id": 사례["case_id"],
                        "화면이름": 사례.get("design_name", ""),
                        "까닭": "주소표에 이 디자인 이름이 없습니다"})
            continue
        화면.append({"번호": f"{사례.get('seq', 0):03d}",
                   "이름": 사례.get("design_name", "") or 줄.get("이름", ""),
                   "상태": 줄.get("상태", "default"),
                   "주소": 줄.get("주소", ""),
                   "동작": 줄.get("동작", "-"),
                   "case_id": 사례["case_id"],
                   "디자인이름": 사례.get("design_name", ""),
                   "해야할일": 사례.get("steps", ""),
                   "기대모습": 사례.get("expected", "")})
    return 화면, 빠진것


def 이름짓기(tag, 화면):
    """포털이 알아보는 TC 사진 이름 — capture_tc.py 와 같은 규칙."""
    return "TC-" + 화면["case_id"] + "@capture.png"


def 돌리기(요청경로, 표경로, 결과폴더=None):
    with open(요청경로, encoding="utf-8") as f:
        요청 = json.load(f)
    if 요청.get("format") != "design-capture-request-v1":
        raise SystemExit("포털에서 내려받은 촬영요청 파일이 아닙니다.")
    if (요청.get("platform") or "").lower() not in ("web", "mobile-web"):
        raise SystemExit(f"이 길은 웹 전용입니다 — 받은 것은 '{요청.get('platform')}'")

    표 = nametag.읽기(표경로)
    화면, 빠진것 = 짜기(요청, 표)
    if not 화면:
        raise SystemExit("주소를 찾은 TC가 한 개도 없습니다. 주소표의 '디자인이름' 을 확인해 주세요.")

    tag = dict(표)
    tag["화면"] = 화면
    tag["플랫폼"] = "web"
    결과폴더 = 결과폴더 or os.path.join(
        뿌리, "shots", time.strftime("%Y%m%d-%H%M") + "-TC")

    print(f"■ {요청.get('screen', '')} — TC {len(화면)}개를 재고 찍습니다"
          f"{f' (주소 못 찾은 것 {len(빠진것)}개)' if 빠진것 else ''}\n")
    목록 = webshot.찍기(tag, 결과폴더, 이름짓기)

    결과 = {"format": "design-capture-results-v1",
          "plan_id": 요청.get("plan_id"),
          "screen": 요청.get("screen"),
          "platform": "web",
          "찍은때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "화면폭": 목록.get("화면폭"),
          "찍힌것": 목록["찍힌것"],
          "못찍은것": 목록["못찍은것"] + 빠진것}
    with open(os.path.join(결과폴더, "찍은목록.json"), "w", encoding="utf-8") as f:
        json.dump(결과, f, ensure_ascii=False, indent=2)

    print(f"\n■ 끝. 잰 것 {len(결과['찍힌것'])}개 / 못 한 것 {len(결과['못찍은것'])}개")
    print(f"   폴더: {결과폴더}")
    return 결과


def main():
    if len(sys.argv) < 3:
        raise SystemExit("쓰는 법: py -3 lib/webtc.py 촬영요청.json 주소표.yaml [결과폴더]")
    결과 = 돌리기(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    if 결과["못찍은것"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
