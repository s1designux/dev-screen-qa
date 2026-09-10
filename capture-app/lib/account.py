"""시험 계정 — 검수용 아이디·비밀번호를 한 곳에만 둔다.

이름표(apps/*.yaml)와 동작 글에는 표식만 적는다:

    입력 아이디를 입력해 주세요.=<아이디>
    입력 비밀번호를 입력해 주세요.=<비번>
    입력 비밀번호를 입력해 주세요.=<틀린비번>   일부러 틀린 비밀번호(로그인 실패 화면을 찍을 때)

진짜 값은 apps/앱사전.json 에만 있고, 그 파일은 깃에 올라가지 않는다.
찍기 직전에 runner 가 표식을 진짜 값으로 바꿔 넣는다.
"""
import json
import os

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
사전파일 = os.path.join(뿌리, "apps", "앱사전.json")

아이디표식 = "<아이디>"
비번표식 = "<비번>"
틀린비번표식 = "<틀린비번>"


def 읽기(앱이름):
    """그 앱에 적어 둔 시험 계정. 없으면 빈 값."""
    빈것 = {"아이디": "", "비밀번호": ""}
    if not 앱이름 or not os.path.exists(사전파일):
        return 빈것
    try:
        with open(사전파일, encoding="utf-8") as f:
            사전 = json.load(f)
    except Exception:
        return 빈것
    것 = 사전.get(앱이름) or {}
    return {"아이디": 것.get("시험아이디", "") or "",
            "비밀번호": 것.get("시험비밀번호", "") or ""}


def 틀리게(비밀번호):
    """일부러 틀린 비밀번호를 만든다 — 로그인 실패 화면을 찍으려면 틀려야 한다.

    글자를 덧붙이면 칸의 길이 제한에 잘려 도로 맞는 비밀번호가 될 수 있다.
    그래서 길이는 그대로 두고 **맨 끝 한 글자만** 다른 글자로 바꾼다.
    """
    비밀번호 = (비밀번호 or "").strip()
    if not 비밀번호:
        return ""
    끝 = 비밀번호[-1]
    바꾼끝 = ("9" if 끝.isdigit() and 끝 != "9" else
           "0" if 끝.isdigit() else
           "z" if 끝.isalpha() and 끝.lower() != "z" else
           "a" if 끝.isalpha() else "9")
    if 끝.isalpha() and 끝.isupper():
        바꾼끝 = 바꾼끝.upper()
    return 비밀번호[:-1] + 바꾼끝


def 표식있나(글):
    글 = 글 or ""
    return 아이디표식 in 글 or 비번표식 in 글 or 틀린비번표식 in 글


def 채우기(글, 계정):
    """표식을 진짜 값으로 바꾼다. 적어 둔 값이 없으면 표식을 그대로 둔다."""
    if not 글:
        return 글
    계정 = 계정 or {}
    틀린것 = 틀리게(계정.get("비밀번호"))
    for 표식, 값 in ((아이디표식, (계정.get("아이디") or "").strip()),
                  (틀린비번표식, 틀린것),
                  (비번표식, (계정.get("비밀번호") or "").strip())):
        if 값:
            글 = 글.replace(표식, 값)
    return 글
