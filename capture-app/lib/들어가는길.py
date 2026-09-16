"""들어가는 길 — 로그인 화면을 찍지 않아도 로그인은 하고 들어간다.

왜 있나 (river 2026-09-16): 지금까지 로그인은 **'로그인 화면' 줄의 동작**에만 적혀 있었다.
그래서 홈·메뉴 화면만 골라 찍으면 아무도 로그인하지 않은 채 주소를 열어 로그인 창만 줄줄이 찍혔다.
로그인은 '찍을 화면 한 장'이 아니라 **들어가는 길**이므로 따로 둔다.

무엇이 공통이고 무엇이 매체별인가 (lib/계정확인.py 와 같은 방식):
  · 공통(여기) — 언제 들어가야 하나(고른 목록에 로그인 화면이 없고, 로그인이 있는 서비스일 때)
  · 웹  — **찍는 그 창에서** 한 번 로그인한다. 칸 찾는 법은 `계정확인` 것을 그대로 쓴다(적어 둘 것 없다).
  · 앱  — 묶음마다 앱을 껐다 켜므로 대본 앞에 로그인 동작을 조용히 붙인다.
          앱은 화면 속 칸을 저절로 찾을 수 없어 이름표의 `들어가는길:` 한 줄이 있어야 한다.

들어가는 길은 **찍지 않는다** — 사진으로 남지 않고, 찍은 목록에도 들어가지 않는다.
"""
import os
import re
import sys

여기 = os.path.dirname(os.path.abspath(__file__))
if 여기 not in sys.path:
    sys.path.insert(0, 여기)

import account  # noqa: E402
import actions  # noqa: E402
import 계정확인  # noqa: E402
import 매체  # noqa: E402

로그인무늬 = re.compile(r"로그인|log\s*in|sign\s*in", re.I)
로그아웃무늬 = re.compile(r"로그아웃|log\s*out|sign\s*out", re.I)


def 로그인화면인가(화면):
    """이 줄이 '로그인 화면' 인가 — 이름으로 보고, 없으면 동작에 계정 표식이 있나로 본다."""
    이름 = " ".join(str(화면.get(k, "") or "") for k in ("이름", "디자인이름", "상태"))
    if 로그아웃무늬.search(이름):
        return False
    if 로그인무늬.search(이름):
        return True
    return account.표식있나(화면.get("동작", ""))


def 정말들어가나(동작):
    """이 동작 하나로 정말 로그인이 되나 — 아이디·비밀번호를 다 넣고 들어가는 것만 인정한다.

    '비밀번호 칸을 누르기'(상태만 만드는 동작)나 **일부러 틀리는 동작**은 들어가는 길이 아니다.
    """
    글 = 동작 or ""
    return (account.아이디표식 in 글 and account.비번표식 in 글
            and account.틀린비번표식 not in 글)


def 목록에있나(화면들):
    return any(로그인화면인가(s) for s in (화면들 or []))


def 계정읽기(tag):
    것 = account.읽기(tag.get("앱이름", ""))
    return {"아이디": (tag.get("시험아이디") or 것["아이디"] or "").strip(),
            "비밀번호": (tag.get("시험비밀번호") or 것["비밀번호"] or "")}


def 로그인쓰나(tag):
    """이 서비스에 로그인이 있나 — 이름표에 적힌 것, 없으면 시험 계정이 적혀 있나로 본다."""
    적힌것 = str(tag.get("로그인") or "").strip()
    if 적힌것 in ("필요", "예", "yes", "true"):
        return True
    if 적힌것 in ("없음", "아니오", "no", "false"):
        return False
    것 = 계정읽기(tag)
    return bool(것["아이디"] and 것["비밀번호"])


def 필요한가(tag):
    """고른 목록에 로그인 화면이 없는데 로그인이 있는 서비스면, 들어가는 길이 필요하다."""
    return 로그인쓰나(tag) and not 목록에있나(tag.get("화면") or [])


def 동작글(tag):
    """사람이 적어 둔 들어가는 길(동작 한 줄). 없으면 빈 글."""
    글 = str(tag.get("들어가는길") or "").strip()
    return "" if 글 in ("-", "없음") else 글


def 갈래(tag):
    return tag.get("유형") or tag.get("플랫폼") or 매체.PC웹


def 주소(tag):
    """로그인하러 들어갈 주소. 따로 적었으면 그것, 아니면 기본 주소."""
    적힌것 = str(tag.get("로그인주소") or "").strip()
    바탕 = 매체.주소다듬기(tag.get("기본주소"), 갈래(tag))
    if not 적힌것:
        return 바탕
    if re.match(r"^https?://", 적힌것):
        return 적힌것
    if not 바탕:
        return ""
    return 바탕.rstrip("/") + "/" + 적힌것.lstrip("/")


# ── 앱: 대본 앞에 붙일 줄 ───────────────────────────────────────
def 앱줄(tag, 계정=None):
    """묶음 대본 앞에 조용히 붙일 로그인 줄. (줄들, 알림) 을 돌려준다.

    앱은 켤 때마다 로그아웃되므로 묶음마다 한 번씩 지나가야 한다.
    적어 둔 길이 없으면 막지 않고 한 줄로 알린다 — 찍히는 것을 보고 사람이 정한다.
    """
    if not 필요한가(tag):
        return [], ""
    글 = 동작글(tag)
    if not 글:
        return [], ("로그인이 있는 앱인데 '들어가는 길'이 적혀 있지 않습니다 — "
                    "이름표에 `들어가는길: 입력 아이디=<아이디> → 입력 비밀번호=<비번> → 탭 로그인` "
                    "처럼 한 줄 적어 주세요. 그 전까지는 로그인 전 화면이 찍힙니다.")
    것 = 계정 or 계정읽기(tag)
    if not (것["아이디"] and 것["비밀번호"]):
        return [], ("로그인이 있는 앱인데 시험 아이디·비밀번호가 비어 있습니다 — "
                    "촬영 준비 사이트 ②의 '앱 정보'에 적어 주세요.")
    try:
        줄 = actions.옮기기(글, 것, False, None)
    except Exception as e:
        return [], f"'들어가는 길'을 읽지 못했습니다 — {e}"
    return 줄 + ["- waitForAnimationToEnd:", "    timeout: 5000"], ""


# ── 웹: 찍는 그 창에서 한 번 ────────────────────────────────────
def 웹으로(쪽, tag, 기다림=0.6):
    """이미 열려 있는 창에서 한 번 로그인한다(찍지 않는다). 계정확인과 같은 판정을 쓴다."""
    import webshot          # 서로 부르는 것을 막으려고 여기서 불러온다

    것 = 계정읽기(tag)
    if not (것["아이디"] and 것["비밀번호"]):
        return 계정확인.안됨("시험 아이디·비밀번호가 비어 있습니다.")
    들어갈주소 = 주소(tag)
    if not 들어갈주소:
        return 계정확인.못해봄("기본 주소가 없어 들어가는 길을 지날 수 없습니다.")

    유형 = 갈래(tag)
    글 = 동작글(tag)
    if not 글:
        # 적어 둔 길이 없으면 칸을 찾아 들어간다 — 사이트마다 따로 설정하게 만들지 않는다.
        return 계정확인.쪽에서(쪽, 유형, 것["아이디"], 것["비밀번호"], 주소=들어갈주소)
    try:
        쪽.goto(들어갈주소, wait_until="load", timeout=30000)
        쪽.wait_for_timeout(1200)
        webshot.동작하기(쪽, 글, 것, False, 기다림, 유형)
        쪽.wait_for_timeout(int(계정확인.기다릴초 * 1000))
    except Exception as e:
        return 계정확인.안됨(str(e).strip().splitlines()[0][:120])
    return 계정확인.판정(쪽)
