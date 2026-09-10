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

# 처음부터 알고 있는 앱 (이미 확인해 둔 것)
기본 = {
    "삼성통근버스": {"서비스코드": "BUS", "앱주소": "kr.co.s1.samsungbus", "로그인": "없음"},
    "갤럭시 설정": {"서비스코드": "SET", "앱주소": "com.android.settings", "로그인": "없음"},
}


def 읽기():
    사전 = dict(기본)
    for y in sorted((뿌리 / "apps").glob("*.yaml")):
        try:
            t = nametag.읽기(str(y))
        except Exception:
            continue
        if t.get("앱이름"):
            사전[t["앱이름"]] = {"서비스코드": t.get("서비스코드", ""),
                             "앱주소": t.get("앱주소", ""),
                             "로그인": t.get("로그인", "없음")}
    if 사전파일.exists():
        try:
            사전.update(json.loads(사전파일.read_text(encoding="utf-8")))
        except Exception:
            pass
    return 사전


def 적어두기(앱이름, 서비스코드, 앱주소, 로그인="없음"):
    """찍고 나면 다음부터는 앱 이름만 적어도 되게 기억해 둔다."""
    if not 앱이름:
        return
    사전 = {}
    if 사전파일.exists():
        try:
            사전 = json.loads(사전파일.read_text(encoding="utf-8"))
        except Exception:
            사전 = {}
    사전[앱이름] = {"서비스코드": 서비스코드, "앱주소": 앱주소, "로그인": 로그인 or "없음"}
    사전파일.write_text(json.dumps(사전, ensure_ascii=False, indent=2), encoding="utf-8")
