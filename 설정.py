"""이 컴퓨터에서만 쓰는 값 한 곳 — `설정.json`.

저장소는 공개라 실제 주소·계정·자리(경로)를 코드에 적어 두지 않는다.
그런 값은 이 컴퓨터의 `설정.json` 한 장에만 적고, 코드는 여기서 꺼내 쓴다.
`설정.json` 은 깃에 올라가지 않는다(`설정.예시.json` 만 올라간다).

찾는 차례: `설정.json` → 환경변수 → 기본값.
그래서 지금까지 환경변수로 돌리던 방식은 그대로 살아 있다.

    import 설정
    포트 = 설정.값("포털.포트")

값이 비면(빈 글자·null) 적지 않은 것으로 본다.
"""
import json
import os
from pathlib import Path

뿌리 = Path(__file__).resolve().parent
설정파일 = 뿌리 / "설정.json"

# 키 → (환경변수 이름, 기본값)
#   · 환경변수 이름이 빈 글자면 환경변수로는 못 바꾼다.
#   · 자리(경로) 값은 뿌리 폴더 기준 상대경로로 적어도 된다.
표 = {
    "자료.뿌리":         ("QA_DATA_ROOT",       ""),
    "포털.포트":         ("QA_PORTAL_PORT",     8765),
    "포털.자료함":       ("QA_PORTAL_DB",       "mvp0/mvp0-real.db"),
    "포털.그림보관":     ("QA_PORTAL_UPLOADS",  "mvp0/uploads"),
    "포털.동료공유":     ("QA_PORTAL_SHARE",    False),
    "촬영준비.포트":     ("QA_CAPTURE_PORT",    8767),
    "촬영준비.받는자리": ("QA_CAPTURE_BIND",    "127.0.0.1"),
    "촬영준비.adb":      ("QA_CAPTURE_ADB",     "~/Library/Android/sdk/platform-tools/adb"),
    "피그마.열쇠":       ("FIGMA_TOKEN",        ""),
    "정본.저장소":       ("QA_REGISTRY_REPO",   "s1designux/S1-UX-DESIGN-with-AI"),
    "정본.가지":         ("QA_REGISTRY_BRANCH", "main"),
    "정본.받는곳":       ("QA_REGISTRY_HOST",   "https://codeload.github.com"),
    "정본.판보는곳":     ("QA_REGISTRY_API",    "https://api.github.com"),
    "정본.이미받은자리": ("QA_REGISTRY_DIR",    ""),
}

_읽은것 = None


def 다시읽기():
    """`설정.json` 을 다시 읽는다(고치고 바로 쓰고 싶을 때)."""
    global _읽은것
    _읽은것 = None
    return 전부()


def 전부():
    """`설정.json` 에 적힌 것만. 파일이 없거나 깨졌으면 빈 것."""
    global _읽은것
    if _읽은것 is None:
        _읽은것 = {}
        if 설정파일.exists():
            try:
                것 = json.loads(설정파일.read_text(encoding="utf-8"))
                if isinstance(것, dict):
                    _읽은것 = _펴기(것)
            except Exception:
                _읽은것 = {}
    return _읽은것


def _펴기(것, 앞=""):
    """{"포털": {"포트": 8765}} → {"포털.포트": 8765}. 이미 편 모양도 그대로 받는다."""
    편것 = {}
    for k, v in 것.items():
        if k.startswith("_"):      # "_설명" 같은 메모 줄은 건너뛴다
            continue
        키 = f"{앞}{k}"
        if isinstance(v, dict):
            편것.update(_펴기(v, 키 + "."))
        else:
            편것[키] = v
    return 편것


def 값(키, 기본=None):
    """설정.json → 환경변수 → 표의 기본값 차례로 찾는다."""
    환경이름, 표기본 = 표.get(키, ("", None))
    적은것 = 전부().get(키)
    if 적은것 is not None and 적은것 != "":
        return _맞추기(키, 적은것)
    if 환경이름:
        들어온것 = os.environ.get(환경이름, "").strip()
        if 들어온것 != "":
            return _맞추기(키, 들어온것)
    return 표기본 if 기본 is None else 기본


def _맞추기(키, 것):
    """표의 기본값과 같은 종류로 맞춘다(글자로 적힌 숫자·참거짓도 받아 준다)."""
    _, 표기본 = 표.get(키, ("", None))
    if isinstance(표기본, bool):
        if isinstance(것, bool):
            return 것
        return str(것).strip().lower() in ("1", "true", "yes", "on", "켬", "예")
    if isinstance(표기본, int):
        try:
            return int(str(것).strip())
        except ValueError:
            return 표기본
    return str(것).strip() if not isinstance(것, str) else 것.strip()


def 자리(키, 기본=None):
    """자리(경로) 값 — 물결(~)을 펴고, 상대경로는 뿌리 폴더 기준으로 읽는다."""
    것 = 값(키, 기본)
    if not 것:
        return None
    길 = Path(os.path.expanduser(str(것)))
    return 길 if 길.is_absolute() else (뿌리 / 길)


def 뿌리찾기(어디):
    """다른 폴더의 파일에서 이 모듈을 부를 수 있게 뿌리를 sys.path 에 넣어 준다."""
    import sys
    if str(뿌리) not in sys.path:
        sys.path.insert(0, str(뿌리))
    return 뿌리


def 지금값():
    """지금 쓰는 값과 그게 어디서 온 것인지."""
    적은것 = 전부()
    줄 = []
    for 키, (환경이름, 표기본) in 표.items():
        if 적은것.get(키) not in (None, ""):
            어디 = "설정.json"
        elif 환경이름 and os.environ.get(환경이름, "").strip() != "":
            어디 = "환경변수 " + 환경이름
        else:
            어디 = "기본값"
        줄.append((키, 값(키), 어디))
    return 줄


if __name__ == "__main__":
    print("설정 파일: %s%s\n" % (설정파일, "" if 설정파일.exists() else "  ← 아직 없음(기본값으로 돕니다)"))
    for 키, 것, 어디 in 지금값():
        print("  %-18s %-46s %s" % (키, 것, 어디))
