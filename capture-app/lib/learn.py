"""자리 익히기 — 처음 한 번만 글자로 찾아서 그 자리를 기억해 둔다.

왜 따로 도는가
    자리는 '그 화면이 떠 있는 순간'에만 알아낼 수 있다. 그래서 대본을 끊어 가며
    거기까지 폰을 몰고 간 뒤, 그 자리에서 화면 목록을 한 번 읽어 좌표를 적어 둔다.

    이 일은 이름표를 새로 만들거나 고쳤을 때 한 번만 돈다. 그 뒤의 촬영은
    기억해 둔 자리를 바로 누르므로 빨라진다(lib/places.py).

사진은 찍지 않는다 — 자리만 익힌다.
"""
import os
import shutil
import subprocess
import sys

여기 = os.path.dirname(os.path.abspath(__file__))
뿌리 = os.path.dirname(여기)
sys.path.insert(0, 여기)

import actions  # noqa: E402
import places  # noqa: E402


def 익힐것(tag, 묶음들, 자리사전):
    """아직 자리를 모르는 글자가 있는 묶음만 골라 낸다."""
    남은것 = []
    for 한묶음 in 묶음들:
        모름 = []
        for s in 한묶음:
            for 글자 in actions.누를글자들(s.get("동작", "")):
                키 = places.열쇠(s["번호"], 글자)
                if 키 not in 자리사전:
                    모름.append((s, 글자, 키))
        if 모름:
            남은것.append((한묶음, 모름))
    return 남은것


def _머리(tag, 한묶음, 스플래시인가):
    줄 = ["- stopApp", "- launchApp"]
    if not 스플래시인가(한묶음[0]):
        줄 += ["- waitForAnimationToEnd:", "    timeout: 5000"]
    누를것 = 한묶음[0].get("누를것", "-")
    if 누를것 not in ("-", "", "없음"):
        줄 += ["- scrollUntilVisible:", "    element:",
              f"      text: {actions._따옴표(누를것)}", "    direction: DOWN",
              "    timeout: 10000", f"- tapOn: {actions._따옴표(누를것)}",
              "- waitForAnimationToEnd:", "    timeout: 5000"]
    return 줄


def _돌리기(손파일, 앱주소, 줄, 임시, 순번):
    """대본 한 토막을 실제 폰에서 돌린다. 앱은 켜 둔 채로 다음 토막이 이어받는다."""
    if not 줄:
        return
    경로 = os.path.join(임시, f"익힘{순번:03d}.yaml")
    with open(경로, "w", encoding="utf-8") as f:
        f.write(f"appId: {앱주소}\n---\n" + "\n".join(줄) + "\n")
    subprocess.run([손파일, 경로, 앱주소, "-", "-", os.path.join(임시, f"out{순번:03d}")],
                   capture_output=True, text=True)


def 익히기(tag, 묶음들, 계정, 손파일, 결과폴더, 스플래시인가, 실패화면):
    """자리를 모르는 글자마다 그 화면까지 폰을 몰고 가서 자리를 적어 둔다.

    돌려준 값: 이번에 새로 익힌 자리 개수.
    """
    앱주소 = tag.get("앱주소", "")
    자리사전 = places.읽기(앱주소)
    할것 = 익힐것(tag, 묶음들, 자리사전)
    if not 할것:
        return 0

    임시 = os.path.join(결과폴더, ".자리익히는중")
    shutil.rmtree(임시, ignore_errors=True)
    os.makedirs(임시, exist_ok=True)

    모르는수 = sum(len(m) for _, m in 할것)
    print(f"처음 보는 자리 {모르는수}곳을 익힙니다 — 이 이름표에서 한 번만 하는 일입니다.",
          flush=True)

    익힌수 = 0
    순번 = 0
    for 한묶음, _모름 in 할것:
        줄 = _머리(tag, 한묶음, 스플래시인가)
        for s in 한묶음:
            글 = s.get("동작", "")
            마디들 = actions.쪼개기(글)
            되풀이있음 = any(m.split(None, 1)[0] in ("되풀이", "반복") for m in 마디들)
            if 되풀이있음:
                줄 += actions.옮기기(글, 계정, 실패화면(s.get("이름", "")), 자리사전)
                continue
            for 마디 in 마디들:
                낱말 = 마디.split(None, 1)
                앞 = 낱말[0]
                뒤 = 낱말[1].strip() if len(낱말) > 1 else ""
                글자 = ""
                if 앞 in ("탭", "누르기", "클릭"):
                    글자 = 뒤
                elif 앞 in ("입력", "적기") and "=" in 뒤:
                    글자 = 뒤.split("=", 1)[0].strip()
                키 = places.열쇠(s["번호"], 글자) if 글자 else ""
                if 글자 and 키 not in 자리사전:
                    # 여기까지 폰을 몰고 간 뒤, 그 화면에서 글자의 자리를 읽는다.
                    순번 += 1
                    _돌리기(손파일, 앱주소, 줄, 임시, 순번)
                    줄 = []
                    좌표 = places.지금화면에서찾기(글자)
                    places.촬영도구깨우기()
                    if 좌표:
                        places.적어두기(앱주소, 키, 좌표[0], 좌표[1])
                        자리사전[키] = [int(round(좌표[0])), int(round(좌표[1]))]
                        익힌수 += 1
                    # 못 찾았으면 사전에 적지 않는다 — 예전처럼 글자로 누르게 둔다.
                줄 += actions.한마디(마디, 계정, 실패화면(s.get("이름", "")), 자리사전)
                if 앞 not in ("기다림", "대기"):
                    줄 += ["- waitForAnimationToEnd:", "    timeout: 2000"]
        순번 += 1
        _돌리기(손파일, 앱주소, 줄, 임시, 순번)

    shutil.rmtree(임시, ignore_errors=True)
    print(f"자리 {익힌수}곳을 기억했습니다.\n", flush=True)
    return 익힌수
