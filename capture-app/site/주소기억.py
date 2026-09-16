"""주소 기억 — 화면마다 한 번 적은 개발 주소를 기억해 두고 다음부터 저절로 채운다.

왜 있나 (river 2026-09-16): 시안은 개발 주소를 모른다. 화면 ID ↔ 개발 주소는 사람이 한 번
잇는 것인데(CLAUDE.md 7번), 시안을 새로 고를 때마다 찍을 목록을 다시 지어 주소 칸이 빈칸으로
나왔다. 같은 화면인데 또 적게 되던 것을, 한 번 적으면 그 뒤로는 기억이 채운다.

무엇으로 알아보나: **디자인 이름**(프레임 이름). 시안을 다시 골라도 이름은 그대로라서
번호·차례가 바뀌어도 따라온다. 디자인 이름이 없으면 화면 이름으로 본다.

어디에 쌓나: `apps/주소사전.json` (깃에 올리지 않는다 — 실제 주소는 이 PC에만 둔다).
전에 찍은 이름표(`apps/*.yaml`)에 적힌 주소도 함께 읽는다 — 손으로 쓴 것도 기억이 된다.
지우지 않는다: 빈 칸으로 두어도 기억은 남는다(고쳐 적으면 고쳐진다).
"""
import json
import re
import sys
from pathlib import Path

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parent
사전파일 = 뿌리 / "apps" / "주소사전.json"

sys.path.insert(0, str(뿌리 / "lib"))
import nametag  # noqa: E402


def 열쇠(줄):
    """그 화면을 알아보는 이름 — 디자인 이름이 먼저, 없으면 화면 이름."""
    이름 = (줄.get("디자인이름") or 줄.get("이름") or "").strip()
    return re.sub(r"\s+", " ", 이름)


def _사전읽기():
    if not 사전파일.exists():
        return {}
    try:
        것 = json.loads(사전파일.read_text(encoding="utf-8"))
        return 것 if isinstance(것, dict) else {}
    except Exception:
        return {}


def 읽기(앱이름):
    """이 서비스에서 기억하고 있는 '화면 이름 → 주소'."""
    앱이름 = (앱이름 or "").strip()
    기억 = {}
    if not 앱이름:
        return 기억
    # ① 전에 찍은 이름표에 적힌 주소 (손으로 쓴 것도 기억이 된다)
    for y in sorted((뿌리 / "apps").glob("*.yaml")):
        try:
            t = nametag.읽기(str(y))
        except Exception:
            continue
        if (t.get("앱이름") or "").strip() != 앱이름:
            continue
        for s in t.get("화면") or []:
            주소 = (s.get("주소") or "").strip()
            이름 = 열쇠(s)
            if 주소 and 이름:
                기억[이름] = 주소
    # ② 사람이 마지막으로 적은 것이 이긴다
    기억.update((_k, _v) for _k, _v in (_사전읽기().get(앱이름) or {}).items()
                if isinstance(_v, str) and _v.strip())
    return 기억


def 적어두기(앱이름, 초안):
    """적힌 주소만 기억에 쌓는다. 빈 칸으로는 지우지 않는다."""
    앱이름 = (앱이름 or "").strip()
    if not 앱이름:
        return 0
    사전 = _사전읽기()
    이것 = dict(사전.get(앱이름) or {})
    쌓은수 = 0
    for 줄 in 초안 or []:
        주소 = (줄.get("주소") or "").strip()
        이름 = 열쇠(줄)
        if 주소 and 이름 and 이것.get(이름) != 주소:
            이것[이름] = 주소
            쌓은수 += 1
    if not 쌓은수:
        return 0
    사전[앱이름] = 이것
    사전파일.parent.mkdir(parents=True, exist_ok=True)
    사전파일.write_text(json.dumps(사전, ensure_ascii=False, indent=2), encoding="utf-8")
    return 쌓은수


def 채우기(앱이름, 초안):
    """찍을 목록의 **빈 주소 칸만** 기억으로 채운다. 사람이 적은 것은 건드리지 않는다."""
    기억 = 읽기(앱이름)
    if not 기억:
        return 0
    채운수 = 0
    for 줄 in 초안 or []:
        if (줄.get("주소") or "").strip():
            continue
        주소 = 기억.get(열쇠(줄))
        if 주소:
            줄["주소"] = 주소
            채운수 += 1
    return 채운수
