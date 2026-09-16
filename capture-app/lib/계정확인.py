"""시험 계정이 맞는지 **찍기 전에** 한 번 해 본다 — 모든 매체가 같이 쓰는 조각.

왜 있나: 작업자가 적어 준 아이디·비밀번호가 틀리면, 지금까지는 그냥 이상한 화면이
줄줄이 찍혔다. 다 찍고 나서야 "이게 아닌데" 하고 알아챈다.
그래서 찍기 **전에** 한 번 로그인해 보고, 안 되면 그 자리에서 다시 적게 한다.

무엇이 공통이고 무엇이 매체별인가 (CLAUDE.md 8번과 같은 방식):
  · 공통(여기)  — 한 번 해 보고 · 안 되면 까닭을 말하고 · 사람이 고쳐 다시 한다
  · 매체별(lib/매체.py) — '어떻게 해 보나'(로그인확인)와 '무엇을 보고 아나'(로그인실패말 등)

앱·PC 설치형은 아직 미리 해 볼 길이 없다 — '못 해 봄'(됨=None)으로 돌려주고 막지 않는다.
"""
import account
import 매체

기다릴초 = 4.0
막힘표 = "■ 로그인 막힘"          # 촬영기록에 남기는 표식 — 사이트가 이 줄을 보고 안내를 띄운다


def 됨(까닭=""):
    return {"됨": True, "까닭": 까닭, "잠김": False}


def 안됨(까닭, 잠김=False):
    return {"됨": False, "까닭": 까닭, "잠김": 잠김}


def 못해봄(까닭):
    return {"됨": None, "까닭": 까닭, "잠김": False}


def 확인(tag, 아이디=None, 비밀번호=None):
    """시험 계정으로 한 번 로그인해 본다. 찍지는 않는다."""
    유형 = (tag.get("유형") or tag.get("플랫폼") or 매체.기본유형)
    길 = 매체.값(유형, "로그인확인")
    if not 길:
        return 못해봄(f"{매체.값(유형, '이름')} 은(는) 찍기 전에 미리 해 볼 수 없습니다. "
                  f"찍다가 막히면 그때 알려 드립니다.")
    # 이름표(yaml)에는 계정을 적지 않는다 — 진짜 값은 apps/앱사전.json 에만 있다.
    것 = account.읽기(tag.get("앱이름", ""))
    아이디 = (아이디 if 아이디 is not None else (tag.get("시험아이디") or 것["아이디"])) or ""
    비밀번호 = (비밀번호 if 비밀번호 is not None else (tag.get("시험비밀번호") or 것["비밀번호"])) or ""
    로그인있나 = (str(tag.get("로그인") or "").strip() in ("필요", "예", "yes", "true")
              or bool(아이디 or 비밀번호))
    if not 로그인있나:
        return 못해봄("로그인이 없는 사이트입니다 — 해 보지 않습니다.")
    if not 아이디.strip() or not 비밀번호:
        return 안됨("시험 아이디·비밀번호가 비어 있습니다.")
    return _브라우저로(tag, 유형, 아이디.strip(), 비밀번호)


# ── 브라우저로 해 보기 (PC 웹 · 모바일 웹) ───────────────────────
def _칸(쪽, 말들, 비번칸=False):
    if 비번칸:
        것 = 쪽.locator('input[type="password"]').first
        try:
            것.wait_for(state="visible", timeout=4000)
            return 것
        except Exception:
            pass
    for 말 in 말들:
        for 찾기 in (lambda m=말: 쪽.get_by_placeholder(m, exact=False),
                   lambda m=말: 쪽.get_by_label(m, exact=False),
                   lambda m=말: 쪽.locator(f'input[name*="{m}" i], input[id*="{m}" i]')):
            try:
                것 = 찾기().first
                것.wait_for(state="visible", timeout=1200)
                return 것
            except Exception:
                continue
    return None


def _단추(쪽, 말들):
    for 말 in 말들:
        for 찾기 in (lambda m=말: 쪽.get_by_role("button", name=m, exact=False),
                   lambda m=말: 쪽.get_by_role("link", name=m, exact=False),
                   lambda m=말: 쪽.locator(f'button:has-text("{m}")')):
            try:
                것 = 찾기().first
                것.wait_for(state="visible", timeout=1200)
                return 것
            except Exception:
                continue
    return None


def _뽑기(글, 말):
    """화면에 뜬 안내 문장 그대로를 한 줄 가져온다 — 우리가 지어내지 않는다."""
    for 줄 in (글 or "").splitlines():
        줄 = 줄.strip()
        if 말.lower() in 줄.lower() and 3 < len(줄) <= 120:
            return 줄
    return ""


def 판정(쪽):
    """로그인 화면을 벗어났으면 됐다. 남아 있으면 화면에 뜬 말로 까닭을 가른다."""
    try:
        남았나 = 쪽.locator('input[type="password"]').first.is_visible(timeout=1500)
    except Exception:
        남았나 = False
    if not 남았나:
        return 됨("로그인 화면을 벗어났습니다.")
    try:
        글 = 쪽.inner_text("body")[:4000]
    except Exception:
        글 = ""
    낮춘글 = 글.lower()
    for 말 in 매체.로그인잠김말:
        if 말.lower() in 낮춘글:
            return 안됨(_뽑기(글, 말) or "계정이 잠긴 것 같습니다.", 잠김=True)
    for 말 in 매체.로그인실패말:
        if 말.lower() in 낮춘글:
            return 안됨(_뽑기(글, 말) or "아이디나 비밀번호가 맞지 않습니다.")
    return 안됨("로그인 화면에 그대로 머물렀습니다. 아이디·비밀번호를 확인해 주세요.")


def 쪽에서(쪽, 유형, 아이디, 비밀번호, 주소=None):
    """**이미 열려 있는 창**에서 한 번 로그인한다. 찍지 않는다.

    미리 해 보는 것(아래 `_브라우저로`)과 찍기 전에 지나는 들어가는 길(`lib/들어가는길.py`)이
    같은 길을 쓰게 하려고 한 곳에 두었다 — 한쪽만 고쳐져 어긋나지 않게.
    """
    import webshot            # 글자 넣고 누르는 법은 '찍는 손' 것을 그대로 빌려 쓴다
    try:
        if 주소:
            쪽.goto(주소, wait_until="load", timeout=30000)
            쪽.wait_for_timeout(1200)
        아이디칸 = _칸(쪽, 매체.로그인칸말["아이디"])
        비번칸 = _칸(쪽, 매체.로그인칸말["비밀번호"], 비번칸=True)
        if 아이디칸 is None or 비번칸 is None:
            return 못해봄("이 화면에서 아이디·비밀번호 칸을 찾지 못했습니다. "
                      "로그인 화면이 아닐 수 있어 그냥 넘어갑니다.")
        webshot._적기(아이디칸, 아이디, 유형)
        webshot._적기(비번칸, 비밀번호, 유형)
        단추 = _단추(쪽, 매체.로그인칸말["단추"])
        if 단추 is None:
            비번칸.press("Enter")
        else:
            try:
                webshot._누르기(단추, "로그인", 유형)
            except Exception as e:
                return 안됨(str(e).strip().splitlines()[0][:120])
        쪽.wait_for_timeout(int(기다릴초 * 1000))
        return 판정(쪽)
    except Exception as e:
        return 못해봄(f"로그인해 보다 막혔습니다 — {str(e).strip().splitlines()[0][:120]}")


def _브라우저로(tag, 유형, 아이디, 비밀번호):
    import webshot            # 브라우저 켜는 법은 '찍는 손' 것을 그대로 빌려 쓴다

    주소 = 매체.주소다듬기(tag.get("기본주소"), 유형)
    if not 주소:
        return 못해봄("기본 주소가 없어 미리 해 볼 수 없습니다.")
    try:
        sync_playwright = webshot.연장가져오기()
    except webshot.웹오류 as e:
        return 못해봄(str(e).splitlines()[0])

    폭 = int(tag.get("화면폭") or webshot.기본폭)
    with sync_playwright() as 연장:
        브라우저, _ = webshot.브라우저켜기(연장)
        칸 = 브라우저.new_context(viewport={"width": 폭, "height": 900})
        쪽 = 칸.new_page()
        try:
            return 쪽에서(쪽, 유형, 아이디, 비밀번호, 주소=주소)
        finally:
            try:
                브라우저.close()
            except Exception:
                pass
