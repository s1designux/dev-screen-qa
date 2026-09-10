"""동작 한 줄을 촬영 도구 명령으로 옮긴다.

사람이 쓰는 말은 다섯 가지뿐이다. 화살표(→)나 세미콜론으로 잇는다.

    탭 로그인                 그 글자를 누른다
    입력 아이디=test01        그 칸을 눌러 글자를 적는다
    기다림 2                  2초 기다린다
    스크롤                    아래로 한 번 굴린다
    뒤로                      뒤로 간다
    지우기                    적은 글자를 지운다
    탭좌표 86,41              글자가 없는 아이콘은 자리(가로%,세로%)로 누른다
    되풀이 5                   그 뒤에 오는 것들을 5번 되풀이한다
    있으면탭 취소              그 글자가 있으면 누르고, 없으면 그냥 지나간다
                              (삼성패스 저장 팝업처럼 가끔 끼어드는 것에 쓴다)
"""
import re


class 동작오류(Exception):
    pass


def _따옴표(v):
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def 쪼개기(글):
    if not 글 or 글.strip() in ("-", "없음"):
        return []
    return [t.strip() for t in re.split(r"→|->|;|\n", 글) if t.strip()]


def 한마디(마디):
    낱말 = 마디.split(None, 1)
    앞 = 낱말[0]
    뒤 = 낱말[1].strip() if len(낱말) > 1 else ""

    if 앞 in ("탭", "누르기", "클릭"):
        if not 뒤:
            raise 동작오류("무엇을 누를지 적어 주세요 — 예: 탭 로그인")
        return [f"- tapOn: {_따옴표(뒤)}"]

    if 앞 in ("있으면탭", "있으면누르기"):
        if not 뒤:
            raise 동작오류("무엇이 있으면 누를지 적어 주세요 — 예: 있으면탭 취소")
        return ["- tapOn:", f"    text: {_따옴표(뒤)}", "    optional: true"]

    if 앞 in ("입력", "적기"):
        if "=" not in 뒤:
            raise 동작오류("어느 칸에 무엇을 적을지 = 로 이어 주세요 — 예: 입력 아이디=test01")
        칸, 값 = 뒤.split("=", 1)
        return [f"- tapOn: {_따옴표(칸.strip())}", f"- inputText: {_따옴표(값.strip())}"]

    if 앞 in ("기다림", "대기"):
        초 = re.sub(r"[^0-9.]", "", 뒤) or "1"
        return ["- waitForAnimationToEnd:", f"    timeout: {int(float(초) * 1000)}"]

    if 앞 in ("스크롤", "굴리기"):
        return ["- scroll"]

    if 앞 in ("뒤로", "back"):
        return ["- back"]

    if 앞 in ("탭좌표", "자리탭"):
        수 = re.findall(r"[0-9.]+", 뒤)
        if len(수) != 2:
            raise 동작오류("자리를 가로%,세로% 로 적어 주세요 — 예: 탭좌표 86,41")
        return ["- tapOn:", f"    point: {수[0]}%,{수[1]}%"]

    if 앞 in ("지우기",):
        return ["- eraseText"]

    raise 동작오류(f"모르는 말입니다 — '{마디}'. 쓸 수 있는 말: 탭 · 있으면탭 · 입력 · 기다림 · 스크롤 · 뒤로 · 지우기 · 탭좌표 · 되풀이")


def 옮기기(글):
    """동작 한 줄 → 촬영 도구 명령 여러 줄.

    '되풀이 5' 가 나오면 그 뒤에 오는 것들을 5번 되풀이한다
    (예: 비밀번호 5회 틀리기 → 되풀이 5 → 탭 로그인 → 기다림 2 → 탭 확인).
    """
    마디들 = 쪼개기(글)
    줄 = []
    i = 0
    while i < len(마디들):
        마디 = 마디들[i]
        낱말 = 마디.split(None, 1)
        if 낱말[0] in ("되풀이", "반복"):
            수 = re.sub(r"[^0-9]", "", 낱말[1] if len(낱말) > 1 else "")
            if not 수 or int(수) < 1 or int(수) > 20:
                raise 동작오류("몇 번 되풀이할지 1~20 사이로 적어 주세요 — 예: 되풀이 5")
            뒤 = 마디들[i + 1:]
            if not 뒤:
                raise 동작오류("되풀이할 것을 뒤에 적어 주세요 — 예: 되풀이 5 → 탭 로그인")
            한벌 = []
            for m in 뒤:
                한벌 += 한마디(m)
            return 줄 + 한벌 * int(수)
        줄 += 한마디(마디)
        i += 1
    return 줄


def 확인(글):
    """쓴 대로 되는지만 미리 본다. 되면 빈 글자, 안 되면 까닭."""
    try:
        옮기기(글)
        return ""
    except 동작오류 as e:
        return str(e)
