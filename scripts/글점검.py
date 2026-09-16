#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""글 점검 — 화면에 적힌 글이 `docs/화면글쓰기규칙.md` 를 지키는지 본다.

왜: 한 번 다듬어도 새 화면을 만들 때마다 문서체·두 번 말하기·옛 이름이 다시 섞인다.
이 도구는 **화면에 보이는 글만** 골라 규칙에 어긋난 줄을 짚는다. 저 혼자 고치지 않는다
(CLAUDE.md 2번-2) — 어디가 어긋났는지 보여주고, 문장은 사람이 정한다.

보는 것 네 가지:
  1. 옛 이름 — 화면에 없는 말(지적 …)이 안내문에 남아 있는지
  2. 문서체 — 제공하지 않습니다 / 진행합니다 / 보존 … 관공서 말
  3. 말투 섞임 — 한 파일 안에서 '~합니다' 와 '~해요' 가 섞였는지
  4. 너무 긴 안내 — 한 문구에 문장 셋 이상, 또는 90자 넘는 줄

쓰는 법:
  python3 scripts/글점검.py           # 어긋난 곳만 (있으면 종료코드 1)
  python3 scripts/글점검.py --전부     # 파일별로 다 보여주기
"""
import os, re, sys

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
볼곳 = [("mvp0", ".py"), ("capture-app/site", ".py")]

옛이름 = {"지적": "수정필요"}
문서체 = {
    "제공하지 않습니다": "못 합니다 / 할 수 없습니다",
    "진행합니다": "합니다",
    "보존합니다": "그대로 남습니다",
    "보존됩니다": "그대로 남습니다",
    "등록 절차": "올리는 법",
    "해당 항목": "이것",
    "확인하여 주시기": "확인하세요",
    "불가합니다": "할 수 없습니다",
    "바랍니다": "하세요",
}
# 화면 글로 보는 줄 — HTML 조각이거나 사람에게 던지는 오류문
글줄 = re.compile(r"(<(p|span|div|small|label|option|button|h[1-6])\b|class=\"(hint|sub|why|lbl|help|empty|muted|warn|tip)\"|ValueError\(|alert\(|confirm\()")
한글 = re.compile(r"[가-힣]")
해요체 = re.compile(r"[가-힣](해요|어요|예요|에요|아요)[\.\!\?\"'<]")
합니다체 = re.compile(r"[가-힣](합니다|습니다|입니다|하세요|세요)[\.\!\?\"'<]")
주석 = re.compile(r"^\s*#")


def 문장수(글):
    """마침표·물음표·느낌표로만 센다(문장 안의 '요·다' 는 세지 않는다)."""
    토막 = [x for x in re.split(r"[\.\!\?]+", 글) if 한글.search(x)]
    return len(토막)


def 줄들(파일):
    for n, 줄 in enumerate(open(파일, encoding="utf-8"), 1):
        if 주석.match(줄) or not 한글.search(줄):
            continue
        if not 글줄.search(줄):
            continue
        yield n, 줄.rstrip("\n")


문자열 = re.compile(r"'([^'\\n]{4,})'|\"([^\"\\n]{4,})\"")


def 문구들(줄):
    """그 줄의 따옴표 안 글 중 **사람에게 보이는 한글 문구**만 꺼낸다(SQL·코드는 뺀다)."""
    나온 = []
    for a, b in 문자열.findall(줄):
        글 = a or b
        if not 한글.search(글):
            continue
        # 한 덩이 HTML 이면 칸(p·h·div…)마다 따로 본다 — 제목과 본문을 한 문구로 세지 않는다.
        for 조각 in re.split(r"</(?:p|div|span|h[1-6]|li|small|label)>|<br\s*/?>", 글):
            조각 = re.sub(r"<[^>]+>", " ", 조각)      # 태그
            조각 = re.sub(r"\{[^{}]*\}", "", 조각)   # f-string 자리
            조각 = re.sub(r"\\n", " ", 조각)
            조각 = re.sub(r"\s+", " ", 조각).strip()
            if 한글.search(조각):
                나온.append(조각)
    return 나온


def 점검():
    난것 = []
    for 폴더, 끝 in 볼곳:
        자리 = os.path.join(뿌리, 폴더)
        for 이름 in sorted(os.listdir(자리)):
            if not 이름.endswith(끝):
                continue
            파일 = os.path.join(자리, 이름)
            쪽 = os.path.relpath(파일, 뿌리)
            해요 = 합니다 = 0
            for n, 줄 in 줄들(파일):
                for 글 in 문구들(줄):
                    for 옛, 새 in 옛이름.items():
                        if 옛 in 글:
                            난것.append((쪽, n, "옛 이름", f"'{옛}' → '{새}'", 글[:70]))
                    for 말, 대신 in 문서체.items():
                        if 말 in 글:
                            난것.append((쪽, n, "문서체", f"'{말}' → '{대신}'", 글[:70]))
                    if 문장수(글) >= 3:
                        난것.append((쪽, n, "너무 김", "문장 셋 이상 — 두 줄까지", 글[:70]))
                    elif len(글) > 90:
                        난것.append((쪽, n, "너무 김", f"{len(글)}자 — 90자까지", 글[:70]))
                해요 += len(해요체.findall(줄))
                합니다 += len(합니다체.findall(줄))
            if 해요 and 합니다:
                난것.append((쪽, 0, "말투 섞임", f"해요 {해요} · 합니다 {합니다}", "한 파일 안에서 섞지 않는다"))
    return 난것


def 보이기(난것, 전부=False):
    if not 난것:
        print("어긋난 곳 없음 — docs/화면글쓰기규칙.md 를 지키고 있습니다.")
        return 0
    갈래 = {}
    for 쪽, n, 무엇, 어떻게, 글 in 난것:
        갈래.setdefault(무엇, []).append((쪽, n, 어떻게, 글))
    for 무엇, 목록 in 갈래.items():
        print(f"\n■ {무엇} · {len(목록)}곳")
        for 쪽, n, 어떻게, 글 in (목록 if 전부 else 목록[:12]):
            print(f"  {쪽}:{n}  {어떻게}")
            print(f"     {글}")
        if not 전부 and len(목록) > 12:
            print(f"  … {len(목록) - 12}곳 더 (--전부)")
    print(f"\n모두 {len(난것)}곳. 문장은 사람이 정한다 — 이 도구는 짚기만 한다.")
    return 1


if __name__ == "__main__":
    sys.exit(보이기(점검(), "--전부" in sys.argv))
