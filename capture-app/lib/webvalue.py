"""화면의 '값'을 긁는다 — PC 웹 검수의 본체.

그림을 견주는 것이 아니라 색·글꼴·글자크기·굵기·모서리·테두리·크기·자리를 **값으로** 견준다.
재는 자(尺)는 새로 만들지 않고 이미 검증된 것을 **그대로 빌려 쓴다**:

    capture-extension/collect-core.js  →  globalThis.__qaMeasure()

사람이 북마크를 눌러 한 화면씩 재던 것을, 브라우저가 화면을 여는 김에 대신 재는 것뿐이다.
(복사본을 두지 않는다 — 자가 바뀌면 양쪽이 함께 바뀌어야 한다.)
"""
import json
import os

여기 = os.path.dirname(os.path.abspath(__file__))
자 = os.path.normpath(os.path.join(여기, "..", "..", "capture-extension", "collect-core.js"))


class 값오류(Exception):
    pass


def 자읽기():
    try:
        with open(자, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise 값오류(f"값을 재는 자를 찾지 못했습니다 — {자} ({e})")


def 긁기(쪽, 화면이름=""):
    """열려 있는 쪽에서 값을 재어 돌려준다."""
    쪽.evaluate(자읽기())
    잰것 = 쪽.evaluate("() => globalThis.__qaMeasure()")
    if not isinstance(잰것, dict) or "elements" not in 잰것:
        raise 값오류("값을 재지 못했습니다")
    잰것.setdefault("meta", {})["label"] = 화면이름 or 잰것["meta"].get("label", "")
    return 잰것


def 쓰기(경로, 값):
    with open(경로, "w", encoding="utf-8") as f:
        json.dump(값, f, ensure_ascii=False, indent=2)
