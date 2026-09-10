"""시험 계정 — 검수용 아이디·비밀번호를 한 곳에만 둔다.

이름표(apps/*.yaml)와 동작 글에는 표식만 적는다:

    입력 아이디를 입력해 주세요.=<아이디>
    입력 비밀번호를 입력해 주세요.=<비번>

진짜 값은 apps/앱사전.json 에만 있고, 그 파일은 깃에 올라가지 않는다.
찍기 직전에 runner 가 표식을 진짜 값으로 바꿔 넣는다.
"""
import json
import os

뿌리 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
사전파일 = os.path.join(뿌리, "apps", "앱사전.json")

아이디표식 = "<아이디>"
비번표식 = "<비번>"


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


def 표식있나(글):
    return 아이디표식 in (글 or "") or 비번표식 in (글 or "")


def 채우기(글, 계정):
    """표식을 진짜 값으로 바꾼다. 적어 둔 값이 없으면 표식을 그대로 둔다."""
    if not 글:
        return 글
    계정 = 계정 or {}
    for 표식, 칸 in ((아이디표식, "아이디"), (비번표식, "비밀번호")):
        값 = (계정.get(칸) or "").strip()
        if 값:
            글 = 글.replace(표식, 값)
    return 글
