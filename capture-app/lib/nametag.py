"""앱 이름표(apps/*.yaml)를 읽는다.

바깥 라이브러리를 쓰지 않는다(설치 묶음 배포 때 파이썬만 있으면 돌아가게).
그래서 일반 YAML 전부가 아니라 이름표가 쓰는 모양만 읽는다:

    키: 값
    화면:
      - 번호: "001"
        이름: 설정 홈
"""
import re

REQUIRED_TOP = ("앱이름", "플랫폼", "서비스코드")
REQUIRED_SCREEN = ("번호", "이름")


class 이름표오류(Exception):
    pass


def _값(raw):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    v = re.split(r"\s+#", v, 1)[0].strip()  # 값 뒤에 붙은 설명(#)은 떼어낸다
    return v


def _쪼개기(line, lineno):
    if ":" not in line:
        raise 이름표오류(f"{lineno}번째 줄: '이름: 값' 모양이 아닙니다 — {line.strip()}")
    k, v = line.split(":", 1)
    return k.strip(), _값(v)


def 읽기(path):
    top, screens, cur = {}, [], None
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()

            if indent == 0:
                if stripped == "화면:":
                    cur = None
                    top["화면"] = screens
                    continue
                k, v = _쪼개기(stripped, lineno)
                top[k] = v
                cur = None
            elif stripped.startswith("- "):
                cur = {}
                screens.append(cur)
                k, v = _쪼개기(stripped[2:], lineno)
                cur[k] = v
            else:
                if cur is None:
                    raise 이름표오류(f"{lineno}번째 줄: 어느 화면에 속하는지 알 수 없습니다 — {stripped}")
                k, v = _쪼개기(stripped, lineno)
                cur[k] = v

    top.setdefault("화면", screens)
    확인(top, path)
    return top


def 확인(tag, path):
    빠진것 = [k for k in REQUIRED_TOP if not tag.get(k)]
    if 빠진것:
        raise 이름표오류(f"{path}: 이름표에 {', '.join(빠진것)} 칸이 비었습니다")
    if not tag["화면"]:
        raise 이름표오류(f"{path}: 찍을 화면이 한 개도 적혀 있지 않습니다")
    for i, s in enumerate(tag["화면"], 1):
        빠진것 = [k for k in REQUIRED_SCREEN if not s.get(k)]
        if 빠진것:
            raise 이름표오류(f"{path}: {i}번째 화면에 {', '.join(빠진것)} 칸이 비었습니다")
        s.setdefault("상태", "default")
        s.setdefault("누를것", "-")
        s.setdefault("동작", "-")
        s.setdefault("이어서", "아니오")


PLATFORM_CODE = {"android": "AND", "ios": "IOS", "web": "WEB"}


def 사진이름(tag, screen):
    """포털이 알아보는 이름 — 화면ID@상태.png (예: SET-AND-002@default.png)"""
    plat = PLATFORM_CODE.get(tag["플랫폼"].strip().lower())
    if not plat:
        raise 이름표오류(f"플랫폼은 android / ios / web 중 하나여야 합니다 — {tag['플랫폼']}")
    return f"{tag['서비스코드']}-{plat}-{screen['번호']}@{screen['상태']}.png"
