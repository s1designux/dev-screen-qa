"""앱 사전 — 앱 이름 하나만 적으면 나머지 칸이 저절로 채워지게.

한 번 찍어 본 앱은 여기에 저절로 쌓인다(사람이 따로 등록하지 않는다).
apps/ 에 이미 있는 이름표도 함께 읽어, 손으로 쓴 것도 사전이 된다.
"""
import json
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parent
사전파일 = 뿌리 / "apps" / "앱사전.json"

sys.path.insert(0, str(뿌리 / "lib"))
import nametag  # noqa: E402
import 들어가는길  # noqa: E402

# 처음부터 알고 있는 앱 (이미 확인해 둔 것)
기본 = {
    "삼성통근버스": {"서비스코드": "BUS", "앱주소": "kr.co.s1.samsungbus", "로그인": "필요",
                "유형": "android", "시험아이디": "", "시험비밀번호": ""},
    "갤럭시 설정": {"서비스코드": "SET", "앱주소": "com.android.settings", "로그인": "없음",
              "유형": "android", "시험아이디": "", "시험비밀번호": ""},
}


def 유형짚기(것, 이름표=None):
    """이 이름이 앱인지 사이트인지. **사람이 플러그인에서 고른 유형**이 먼저다.

    주소를 보고 짐작하는 것은 마지막이다 — 앱인데 웹 주소를 함께 적어 둔 경우가 있어
    (웹뷰 앱·같은 서비스의 포털) 주소만 보면 앱이 사이트로 넘어간다(2026-09-17).
    """
    for 곳 in (것, 이름표 or {}):
        t = str((곳 or {}).get("유형") or "").strip()
        if t:
            return t
        p = str((곳 or {}).get("플랫폼") or "").strip()
        if p:
            return "web" if p == "web" else "android"
    return "web" if (것 or {}).get("기본주소") else "android"


def 들어가는길찾기(tag):
    """이 앱으로 들어가는 길(로그인 동작) 한 줄.

    따로 적어 둔 것이 있으면 그것, 없으면 **전에 찍은 로그인 화면의 동작**을 그대로 쓴다.
    한 번 로그인 화면을 찍어 본 앱은 다음부터 홈만 골라도 로그인하고 들어간다.
    """
    적힌것 = str(tag.get("들어가는길") or "").strip()
    if 적힌것 and 적힌것 not in ("-", "없음"):
        return 적힌것
    for s in tag.get("화면") or []:
        if 들어가는길.정말들어가나(s.get("동작", "")):
            return (s.get("동작") or "").strip()
    return ""


def 읽기():
    사전 = dict(기본)
    이름표들 = {}
    for y in sorted((뿌리 / "apps").glob("*.yaml")):
        try:
            t = nametag.읽기(str(y))
        except Exception:
            continue
        if t.get("앱이름"):
            이름표들[t["앱이름"]] = t
            사전[t["앱이름"]] = {"서비스코드": t.get("서비스코드", ""),
                             "앱주소": t.get("앱주소", ""),
                             "기본주소": t.get("기본주소", ""),   # 웹이면 사이트 주소
                             "화면폭": t.get("화면폭", ""),
                             "로그인": t.get("로그인", "없음"),
                             "유형": 유형짚기(t),
                             "들어가는길": 들어가는길찾기(t),
                             "시험아이디": "", "시험비밀번호": ""}
    if 사전파일.exists():
        try:
            for 이름, 것 in json.loads(사전파일.read_text(encoding="utf-8")).items():
                # 유형이 안 적힌 옛 줄은 이름표에 적힌 유형을 그대로 쓴다(주소로 짐작하지 않는다)
                것 = dict(것)
                것["유형"] = 유형짚기(것, 이름표들.get(이름) or 사전.get(이름))
                사전[이름] = 것
        except Exception:
            pass
    return 사전


def 적어두기(앱이름, 서비스코드, 앱주소, 로그인="없음", 시험아이디="", 시험비밀번호="",
          기본주소="", 화면폭="", 들어가는길="", 유형=""):
    """찍고 나면 다음부터는 앱 이름만 적어도 되게 기억해 둔다.

    시험 아이디·비밀번호도 여기에만 둔다. 이 파일은 깃에 올라가지 않는다.
    """
    if not 앱이름:
        return
    사전 = {}
    if 사전파일.exists():
        try:
            사전 = json.loads(사전파일.read_text(encoding="utf-8"))
        except Exception:
            사전 = {}
    사전[앱이름] = {"서비스코드": 서비스코드, "앱주소": 앱주소,
                 "기본주소": 기본주소 or "", "화면폭": str(화면폭 or ""),
                 "로그인": 로그인 or "없음",
                 "유형": 유형 or (사전.get(앱이름, {}).get("유형") or ""),
                 "들어가는길": 들어가는길 or (사전.get(앱이름, {}).get("들어가는길") or ""),
                 "시험아이디": 시험아이디 or "", "시험비밀번호": 시험비밀번호 or ""}
    사전파일.write_text(json.dumps(사전, ensure_ascii=False, indent=2), encoding="utf-8")
