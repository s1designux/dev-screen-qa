"""'찍는 손' — PC 웹. 주소를 열어 **값을 긁고** 화면도 한 장 통짜로 찍는다.

PC 웹 검수는 그림 대조가 아니라 **값 대조**다(색·글꼴·크기·자리). 그래서 한 번 열 때
값(JSON)을 먼저 긁고, 사람이 좌우로 볼 그림(PNG)도 함께 남긴다.
그림 대조는 모바일 앱·설치형 소프트웨어 쪽 이야기다.

앱(안드로이드)은 폰을 꽂아야 하지만 웹은 그럴 것이 없다. 그래서 윈도우 PC에서
그대로 돌아간다. 브라우저는 **이미 깔려 있는 크롬·엣지**를 빌려 쓴다(따로 내려받지 않는다).

쓰는 말은 앱 쪽(lib/actions.py)과 같다: 탭 · 있으면탭 · 입력 · 기다림 · 스크롤 · 뒤로 · 지우기.
웹에만 있는 말 둘: 탭칸끝(칸 안 오른쪽 끝 단추) · 칸흔들기(칸을 건드려 꺼진 단추를 도로 켠다).
"""
import os
import re
import time
from datetime import datetime

import account
import actions
import 커서
import nametag
import webvalue
import 매체

기본폭 = 1440
기본기다림 = 0.6          # 동작 하나를 하고 화면이 가라앉기를 기다리는 초
여는기다림 = 1.5          # 주소를 열고 기다릴 **최대** 초 — 조용해지면 그 전에 넘어간다
찾는짧은초 = 0.4          # 화면에서 무엇을 찾을 때 첫 바퀴에 기다릴 초
찾는긴초 = 2.0            # 첫 바퀴에 다 못 찾으면 두 바퀴째에 기다릴 초
브라우저차례 = ("chrome", "msedge", None)   # 깔려 있는 것부터 빌려 쓰고, 없으면 딸려온 것


class 웹오류(Exception):
    pass


def 연장가져오기():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise 웹오류(
            "웹을 찍는 연장(Playwright)이 아직 없습니다.\n"
            "  윈도우 명령창에서:  py -m pip install playwright\n"
            "  (자세한 것은 capture-app/설치/윈도우.md)")
    return sync_playwright


def 숨어서찍나():
    """창을 띄우지 않고 찍을지. 기본은 **보이게** 찍는다.

    사람이 '브라우저 창이 저절로 열리고 닫힙니다' 는 안내를 보고 기다리는데 창이 안 뜨면
    돌아가는 중인지 멈춘 건지 알 수 없다. 눈에 보여야 잘못 찍힌 화면도 그 자리에서 알아본다.
    창 없이 돌리고 싶을 때만 CAPTURE_HEADLESS=1 을 준다(예약 실행 등).
    """
    return (os.environ.get("CAPTURE_HEADLESS", "") or "").strip().lower() in ("1", "true", "y", "yes")


def 브라우저켜기(연장, 보이기=None):
    """깔려 있는 크롬 → 엣지 → 딸려온 것 차례로 열어 본다."""
    숨김 = 숨어서찍나() if 보이기 is None else (not 보이기)
    마지막탈 = None
    for 이름 in 브라우저차례:
        try:
            if 이름:
                return 연장.chromium.launch(channel=이름, headless=숨김), 이름
            return 연장.chromium.launch(headless=숨김), "딸려온 크로미움"
        except Exception as e:          # 안 깔려 있으면 다음 차례로
            마지막탈 = e
    raise 웹오류(f"브라우저를 열지 못했습니다 — {마지막탈}")


def _살아있나(브라우저, 쪽):
    try:
        return bool(브라우저.is_connected()) and not 쪽.is_closed()
    except Exception:
        return False


def _갈래(tag):
    """이 이름표가 어느 매체인지 — 유형표(lib/매체.py)의 열쇠. 옛 이름표는 '플랫폼' 만 있다."""
    return (tag.get("유형") or tag.get("플랫폼") or 매체.PC웹)


def 주소만들기(tag, 화면):
    """사람이 적은 주소를 그대로 연다. **끝 빗금을 떼지 않는다** — 유형표(lib/매체.py) 겪은일 2026-09-14.
    (뗐더니 서버가 404 오류 페이지로 보냈고, 그 오류 화면을 로그인 화면인 줄 알고 찍었다.)"""
    주소 = (화면.get("주소") or "").strip()
    갈래 = _갈래(tag)
    바탕 = 매체.주소다듬기(tag.get("기본주소"), 갈래)
    if not 주소:
        if not 바탕:
            raise 웹오류(f"{화면['이름']}: 주소가 없습니다")
        return 바탕
    if re.match(r"^https?://", 주소):
        return 주소
    if not 바탕:
        raise 웹오류(f"{화면['이름']}: '기본주소' 가 없어 '{주소}' 만으로는 열 수 없습니다")
    return 바탕.rstrip("/") + "/" + 주소.lstrip("/")


def _먼저찾기(찾는길들):
    """여러 갈래로 찾아본다 — **짧게 한 바퀴 돌고**, 다 못 찾았을 때만 길게 한 바퀴 더.

    한 갈래에 2초씩 기다리면 헛걸음 하나에 2초가 그냥 날아간다. 이미 그려진 화면은
    거의 즉시 잡히므로 첫 바퀴는 짧게 돌고, 늦게 그려지는 화면만 두 바퀴째를 기다린다.
    (화면 8장 찍는 데 헛걸음으로만 20초 넘게 쓰던 것을 줄인다 — 2026-09-14)
    """
    for 초 in (찾는짧은초, 찾는긴초):
        for 찾기 in 찾는길들:
            try:
                것 = 찾기().first
                것.wait_for(state="visible", timeout=int(초 * 1000))
                return 것
            except Exception:
                continue
    return None


def _칸찾기(쪽, 글자):
    """이름·안내글·라벨 어느 것으로 적어도 그 칸을 찾아 준다."""
    것 = _먼저찾기((lambda: 쪽.get_by_placeholder(글자, exact=False),
                 lambda: 쪽.get_by_label(글자, exact=False),
                 lambda: 쪽.locator(f'[name="{글자}"], #{글자}')))
    if 것 is None:
        것 = _비슷한것찾기(쪽, 글자, "칸")
    if 것 is None:
        raise 웹오류(f"'{글자}' 칸을 화면에서 찾지 못했습니다(닮은 안내글도 없음)")
    return 것


def _누를것찾기(쪽, 글자):
    """누를 것을 찾는다 — 단추·링크·글자, 그리고 **적는 칸**까지.

    '탭 비밀번호를 입력해 주세요.' 처럼 안내글이 적힌 칸을 눌러 커서만 두는 화면이 있다.
    칸은 단추도 링크도 아니고 안내글이 글자로도 안 잡혀서, 칸 찾는 길을 **같은 바퀴에** 붙인다
    (뒤로 미뤄 두면 단추·링크·글자를 다 헛걸음한 뒤에야 칸을 보느라 8초가 든다).
    """
    return _먼저찾기((lambda: 쪽.get_by_role("button", name=글자, exact=False),
                  lambda: 쪽.get_by_role("link", name=글자, exact=False),
                  lambda: 쪽.get_by_text(글자, exact=False),
                  lambda: 쪽.get_by_placeholder(글자, exact=False),
                  lambda: 쪽.get_by_label(글자, exact=False),
                  lambda: 쪽.locator(f'[name="{글자}"], #{글자}')))


def _적기(칸, 값, 갈래=None):
    """칸에 글자를 넣는다. 웹은 **한 글자씩** 친다 — 자판을 뗄 때(keyup)만 단추를 켜는 화면이 있어서다.
    한 번에 밀어 넣으면(fill) 자판 신호가 나지 않아 로그인 단추가 꺼진 채로 남는다(유형표 겪은일 2026-09-14)."""
    커서.것으로(칸)
    칸.click()
    칸.fill("")
    if not 매체.값(갈래, "입력.한글자씩", False):
        칸.fill(값)
        return
    try:
        칸.press_sequentially(값, delay=30)      # Playwright 새 판
    except AttributeError:
        칸.type(값, delay=30)                    # 옛 판


def _누르기(것, 이름, 갈래=None):
    """누른다. 꺼져 있는 단추를 오래 기다리지 않고, 꺼져 있다고 분명히 말한다.

    로그인 단추처럼 앞 칸이 차야 켜지는 것이 있다(유형표 겪은일 2026-09-14).
    기본 30초를 기다리다 'Timeout' 만 남기면 사람이 까닭을 알 수 없다.
    """
    초 = 매체.값(갈래, "단추.기다릴초", 30)
    커서.것으로(것)
    try:
        것.click(timeout=int(초 * 1000))
    except Exception as e:
        꺼짐 = False
        try:
            꺼짐 = not 것.is_enabled()
        except Exception:
            pass
        if 꺼짐:
            raise 웹오류(f"'{이름}' 단추가 꺼져 있습니다 — 앞 칸을 채워야 켜지는 화면입니다")
        raise 웹오류(f"'{이름}' 을(를) 누르지 못했습니다 — {str(e).strip().splitlines()[0]}")


def _칸흔들기(쪽, 칸이름, 값="", 계정=None, 실패=False, 갈래=None):
    """그 칸을 살짝 건드려 **꺼진 단추를 도로 켠다**.

    로그인을 한 번 틀리면 아이디·비밀번호가 칸에 그대로 있는데도 로그인 단추를 다시
    꺼 버리는 화면이 있다(유형표 겪은일 2026-09-14). 사람은 비밀번호를 한 글자 지웠다
    다시 적어 단추를 켠다 — 그것을 그대로 한다.

    한 글자 넣었다 곧바로 지우므로 **적혀 있던 값은 그대로**다.
    칸이 비어 있으면(화면이 값까지 지웠으면) 적어 둔 값을 다시 넣는다.
    """
    칸 = _칸찾기(쪽, 칸이름)
    커서.것으로(칸)
    칸.click()
    지금 = ""
    try:
        지금 = 칸.input_value()
    except Exception:
        pass
    if not 지금:
        if not 값:
            raise 웹오류(f"'{칸이름}' 칸이 비어 있습니다 — 무엇을 적을지 = 로 이어 주세요")
        _적기(칸, account.채우기(값, 계정, 실패), 갈래)
        return
    칸.press("End")
    칸.press("a")
    칸.press("Backspace")


보기무늬 = re.compile(r"eye|show|reveal|visib|보기|표시|숨김", re.I)


def _칸끝누르기(쪽, 칸이름):
    """칸 안쪽 오른쪽 끝에 붙은 작은 단추(비밀번호 눈)를 누른다.

    자리(%)로 누르지 않는 까닭: 시안 높이와 브라우저 창 높이가 달라 세로가 그대로 옮겨지지 않는다
    (유형표 겪은일 2026-09-14 — 38% 로 눌렀더니 빈 곳을 눌렀다).

    누를 것을 고르는 차례:
      1) 그 칸 위에 겹쳐 있는 작은 단추 중 **이름표가 '보기·눈'** 인 것 (aria-label·title·class)
      2) 없으면 그 중 맨 왼쪽 것 (지우기 ✕ 는 보통 맨 오른쪽에 붙는다)
      3) 단추를 하나도 못 찾으면 칸의 오른쪽 끝을 그냥 누른다
    """
    상자 = _칸찾기(쪽, 칸이름).bounding_box()
    if not 상자:
        raise 웹오류(f"'{칸이름}' 칸이 화면에 보이지 않습니다")
    가운데y = 상자["y"] + 상자["height"] / 2
    단추들 = []
    for i in range(쪽.locator("button, a[role=button], [role=button]").count()):
        것 = 쪽.locator("button, a[role=button], [role=button]").nth(i)
        try:
            b = 것.bounding_box()
        except Exception:
            continue
        if not b or b["width"] > 60 or b["height"] > 60:
            continue
        if not (상자["x"] <= b["x"] + b["width"] / 2 <= 상자["x"] + 상자["width"]):
            continue
        if abs(b["y"] + b["height"] / 2 - 가운데y) > 상자["height"] / 2 + 4:
            continue
        이름 = " ".join(str(것.get_attribute(a) or "") for a in ("aria-label", "title", "class"))
        단추들.append((b["x"], bool(보기무늬.search(이름)), 것))
    보기 = [x for x in 단추들 if x[1]]
    고른것 = (보기 or sorted(단추들))[0][2] if (보기 or 단추들) else None
    if 고른것 is not None:
        커서.것으로(고른것)
        고른것.click()
        return
    커서.자리로(쪽, 상자["x"] + 상자["width"] - 16, 가운데y)
    쪽.mouse.click(상자["x"] + 상자["width"] - 16, 가운데y)


# ── 시안 글자와 개발 글자가 조금 다를 때 ──────────────────────────────
# 시안은 '삼성전자 기흥·화성', 개발은 '삼성전자(기흥/화성)' — 같은 단추인데 글자가 살짝 다르다(2026-09-15 실측).
# 못 찾았다고 멈추면 그 뒤 화면까지 다 못 찍으므로, 화면에 보이는 것 가운데 **가장 닮은 것**을 누르고
# 그 사실을 기록에 남긴다(글자 차이 자체는 검수에서 다룰 일이다). 닮음이 문턱 아래면 누르지 않는다.
닮음문턱 = 0.72

_후보긁기 = """
(종류) => {
  const 보임 = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const 누를것 = 'button, a, [role=button], [role=link], [role=option], [role=tab], [role=menuitem], label, summary, li, span, p, h1, h2, h3, h4, td, th, div';
  const 칸 = 'input, textarea, select, [contenteditable]';
  const 목록 = [];
  document.querySelectorAll(종류 === '칸' ? 칸 : 칸 + ', ' + 누를것).forEach(e => {
    if (!보임(e)) { 목록.push({ 글: '', 칸단추: false }); return; }   // 자리를 비워 두어 번호가 어긋나지 않게
    let 글 = '';
    if (e.matches(칸)) 글 = e.getAttribute('placeholder') || e.getAttribute('aria-label') || e.value || '';
    else {
      // 자기 안에 글자를 품은 가장 작은 덩어리만 — 큰 상자가 안쪽 글자를 통째로 가로채지 않게
      const 직접 = Array.from(e.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join(' ').trim();
      글 = 직접 || ((e.children.length <= 2 && (e.innerText || '').length <= 40) ? (e.innerText || '').trim() : '');
      if (!글) 글 = e.getAttribute('aria-label') || e.getAttribute('title') || '';
    }
    글 = (글 || '').replace(/\s+/g, ' ').trim();
    const 칸단추 = e.matches(칸) || e.matches('button, a, [role=button], [role=link], [role=option], [role=tab], [role=menuitem]');
    목록.push({ 글: (글 && 글.length <= 60) ? 글 : '', 칸단추: 칸단추 });
  });
  return 목록;
}
"""
_표시하기 = """
([종류, 번호]) => {
  const 칸 = 'input, textarea, select, [contenteditable]';
  const 누를것 = 'button, a, [role=button], [role=link], [role=option], [role=tab], [role=menuitem], label, summary, li, span, p, h1, h2, h3, h4, td, th, div';
  const 것 = document.querySelectorAll(종류 === '칸' ? 칸 : 칸 + ', ' + 누를것)[번호];
  document.querySelectorAll('[data-capture-pick]').forEach(e => e.removeAttribute('data-capture-pick'));
  if (것) 것.setAttribute('data-capture-pick', '1');
  return !!것;
}
"""


def _닮음(a, b):
    import difflib
    def 다듬기(t):
        return re.sub(r"[\s\(\)\[\]·/,.\-_:;'\"‘’“”!?]", "", t or "").lower()
    x, y = 다듬기(a), 다듬기(b)
    if not x or not y:
        return 0.0
    if x == y:
        return 1.0
    if x in y or y in x:
        return max(len(x), len(y)) and min(len(x), len(y)) / max(len(x), len(y)) * 0.5 + 0.5
    return difflib.SequenceMatcher(None, x, y).ratio()


def _비슷한것찾기(쪽, 글자, 종류="누를것"):
    """정확히 그 글자가 없을 때, 화면에 보이는 것 중 가장 닮은 것을 찾아 준다. 문턱 아래면 None.

    닮은 정도가 같으면 **칸·단추**를 글자 덩어리보다 먼저 쓴다(숨은 라벨·목록 줄을 집지 않게).
    고른 것이 실제로 보이지 않으면 다음으로 닮은 것을 이어서 본다.
    """
    try:
        후보 = 쪽.evaluate(_후보긁기, 종류) or []
    except Exception:
        return None
    순위 = []
    for i, 것 in enumerate(후보):
        글 = 것.get("글") if isinstance(것, dict) else 것
        if not 글:
            continue
        r = _닮음(글자, 글)
        if r >= 닮음문턱:
            앞자리 = 1 if (isinstance(것, dict) and 것.get("칸단추")) else 0
            순위.append((-round(r, 2), -앞자리, i, 글, r))
    순위.sort()
    for _, _, i, 글, r in 순위[:5]:
        try:
            if not 쪽.evaluate(_표시하기, [종류, i]):
                continue
            것 = 쪽.locator("[data-capture-pick]").first
            것.wait_for(state="visible", timeout=int(찾는짧은초 * 1000))
        except Exception:
            continue
        print(f"    · 시안 글자 '{글자}' 가 화면에 없어 가장 닮은 '{글}' 을(를) 썼습니다 (닮음 {r:.0%}) "
              f"— 글자가 다른 것은 검수에서 다룹니다", flush=True)
        return 것
    return None


def 한마디하기(쪽, 마디, 계정, 실패, 기다림, 갈래=None):
    """동작 한 마디를 해 본다(앱 쪽 lib/actions.py 와 같은 말). 유형표(lib/매체.py)가 세부를 정한다."""
    낱말 = 마디.split(None, 1)
    앞 = 낱말[0]
    뒤 = 낱말[1].strip() if len(낱말) > 1 else ""

    if 앞 in ("탭", "누르기", "클릭"):
        것 = _누를것찾기(쪽, 뒤)
        if 것 is None:
            것 = _비슷한것찾기(쪽, 뒤)
        if 것 is None:
            raise 웹오류(f"'{뒤}' 를 화면에서 찾지 못했습니다(닮은 글자도 없음)")
        _누르기(것, 뒤, 갈래)
    elif 앞 in ("있으면탭", "있으면누르기"):
        것 = _누를것찾기(쪽, 뒤)
        if 것 is not None:
            커서.것으로(것)
            것.click()
    elif 앞 in ("입력", "적기"):
        if "=" not in 뒤:
            raise 웹오류("어느 칸에 무엇을 적을지 = 로 이어 주세요 — 예: 입력 아이디=test01")
        칸, 값 = 뒤.split("=", 1)
        _적기(_칸찾기(쪽, 칸.strip()), account.채우기(값.strip(), 계정, 실패), 갈래)
    elif 앞 in ("기다림", "대기"):
        try:
            time.sleep(float(뒤))
        except ValueError:
            raise 웹오류(f"몇 초 기다릴지 숫자로 적어 주세요 — {마디}")
        return
    elif 앞 in ("탭칸끝",):
        _칸끝누르기(쪽, 뒤)
    elif 앞 in ("칸흔들기",):
        칸, 값 = (뒤.split("=", 1) + [""])[:2]
        _칸흔들기(쪽, 칸.strip(), 값.strip(), 계정, 실패, 갈래)
    elif 앞 in ("탭좌표", "자리탭"):
        # 글자가 없는 것(비밀번호 눈 아이콘 등)은 자리(가로%,세로%)로 누른다.
        if not 매체.값(갈래, "좌표.세로퍼센트", True):
            raise 웹오류(f"웹에서는 자리(%)로 누르지 않습니다 — 창 높이가 시안과 달라 빗나갑니다. "
                     f"'탭칸끝 <칸 안내글>' 로 적어 주세요 ({마디})")
        수 = re.findall(r"[0-9.]+", 뒤)
        if len(수) != 2:
            raise 웹오류(f"자리를 가로%,세로% 로 적어 주세요 — 예: 탭좌표 86,41 ({마디})")
        칸크기 = 쪽.viewport_size or {"width": 기본폭, "height": 900}
        x = 칸크기["width"] * float(수[0]) / 100
        y = 칸크기["height"] * float(수[1]) / 100
        커서.자리로(쪽, x, y)
        쪽.mouse.click(x, y)
    elif 앞 == "스크롤":
        쪽.mouse.wheel(0, 800)
    elif 앞 == "뒤로":
        쪽.go_back()
    elif 앞 == "지우기":
        쪽.keyboard.press("Control+A")
        쪽.keyboard.press("Delete")
    else:
        raise 웹오류(f"모르는 말입니다 — {마디}. 쓸 수 있는 말: 탭 · 있으면탭 · 입력 · "
                 f"기다림 · 스크롤 · 뒤로 · 지우기 · 탭칸끝 · 칸흔들기 · 되풀이")
    쪽.wait_for_timeout(int(기다림 * 1000))


def 동작하기(쪽, 동작, 계정, 실패, 기다림, 갈래=None):
    """사람이 적은 동작 한 줄을 그대로 해 본다.

    '되풀이 5' 가 나오면 그 뒤에 오는 것들을 5번 되풀이한다(앱 쪽과 같다) —
    비밀번호를 다섯 번 틀리는 화면처럼 같은 짓을 여러 번 해야 할 때 쓴다.
    """
    마디들 = actions.쪼개기(동작)
    for i, 마디 in enumerate(마디들):
        낱말 = 마디.split(None, 1)
        if 낱말[0] in ("되풀이", "반복"):
            수 = re.sub(r"[^0-9]", "", 낱말[1] if len(낱말) > 1 else "")
            if not 수 or not (1 <= int(수) <= 20):
                raise 웹오류("몇 번 되풀이할지 1~20 사이로 적어 주세요 — 예: 되풀이 5")
            뒤 = 마디들[i + 1:]
            if not 뒤:
                raise 웹오류("되풀이할 것을 뒤에 적어 주세요 — 예: 되풀이 5 → 탭 로그인")
            for _ in range(int(수)):
                for m in 뒤:
                    한마디하기(쪽, m, 계정, 실패, 기다림, 갈래)
            return
        한마디하기(쪽, 마디, 계정, 실패, 기다림, 갈래)


def 브라우저끄기(브라우저):
    """다 찍었으면 브라우저를 **바로 끈다**.

    설치된 크롬은 로그인 칸에 글자를 넣고 여러 번 보낸 화면을 찍고 나면, 곱게 닫는 데
    25초쯤 걸린다(제 비밀번호 관리 기능을 정리하느라 그런다 — 딸려온 크로미움은 0초다).
    사진·값은 이미 다 저장한 뒤라 기다릴 까닭이 없다. 찍는 데 21초 쓰고 닫는 데 24초를
    더 쓰던 것을 없앤다(2026-09-14).

    곱게 끄는 길이 막히면 그때만 원래대로 기다린다.
    """
    try:
        브라우저._impl_obj._connection._transport._proc.kill()
        return
    except Exception:
        pass
    try:
        브라우저.close()
    except Exception:
        pass


def _가라앉기(쪽, 최대초):
    """페이지가 조용해질 때까지만 기다린다 — 정해진 시간을 늘 통째로 버리지 않는다."""
    try:
        쪽.wait_for_load_state("networkidle", timeout=int(최대초 * 1000))
    except Exception:
        pass
    쪽.wait_for_timeout(300)


def 값이름(사진이름):
    """같은 화면의 값 파일 이름 — TS-WEB-001@default.png → TS-WEB-001@default.값.json"""
    return 사진이름[:-4] + ".값.json"


def 숫자(tag, 이름, 기본):
    try:
        return float(str(tag.get(이름, "")).strip())
    except (TypeError, ValueError):
        return 기본


def 찍기(tag, 결과폴더, 이름짓기=None):
    """이름표에 적힌 웹 화면을 차례로 재고 찍어, 앱 쪽과 같은 모양의 목록을 남긴다.

    이름짓기: 사진 이름을 다르게 붙이고 싶을 때(디자인 TC 기준 촬영 등) 넘긴다.
    """
    이름짓기 = 이름짓기 or (lambda t, s: nametag.사진이름(t, s))
    sync_playwright = 연장가져오기()
    os.makedirs(결과폴더, exist_ok=True)
    폭 = int(숫자(tag, "화면폭", 기본폭))
    기다림 = 숫자(tag, "기다림", 기본기다림)
    계정 = account.읽기(tag.get("앱이름", ""))   # 시험 아이디·비번은 apps/앱사전.json 에만 있다
    찍힌것, 실패 = [], []
    앞장성공 = False        # 앞 화면이 제대로 찍혔나 — 이어 찍을 수 있는지 가른다

    with sync_playwright() as 연장:
        브라우저, 어느것 = 브라우저켜기(연장)
        print(f"  브라우저: {어느것} · 폭 {폭}px"
              + ("" if 숨어서찍나() else " · 창이 보이게"), flush=True)
        칸 = 브라우저.new_context(viewport={"width": 폭, "height": 900})
        쪽 = 칸.new_page()
        try:
            for i, 화면 in enumerate(tag["화면"], 1):
                이름 = 이름짓기(tag, 화면)
                print(f"[{i}/{len(tag['화면'])}] {화면['이름']} → {이름}", flush=True)
                # 창을 보이게 찍으므로 사람이 실수로 닫을 수 있다. 닫혔으면 다시 열고 이어 간다
                # (한 장 때문에 남은 장을 다 놓치지 않게).
                if not _살아있나(브라우저, 쪽):
                    try:
                        브라우저.close()
                    except Exception:
                        pass
                    브라우저, _ = 브라우저켜기(연장)
                    칸 = 브라우저.new_context(viewport={"width": 폭, "height": 900})
                    쪽 = 칸.new_page()
                    앞장성공 = False
                    print("    · 브라우저 창이 닫혀 있어 다시 열었습니다", flush=True)
                try:
                    # '이어서: 예' 인 화면은 앞 화면에서 눌러 둔 상태 위에 이어 찍는다.
                    # 주소를 다시 열면 적어 둔 글자·로그인 실패 횟수가 도로 지워진다.
                    # 앞 화면이 실패했으면 이을 상태가 없으니 처음부터 다시 연다.
                    if 화면.get("이어서") == "예" and 앞장성공:
                        pass
                    else:
                        쪽.goto(주소만들기(tag, 화면), wait_until="load", timeout=30000)
                        _가라앉기(쪽, 숫자(tag, "여는기다림", 여는기다림))
                    동작 = 화면.get("동작", "-")
                    if 동작 not in ("-", "", "없음"):
                        동작하기(쪽, 동작, 계정, account.실패화면(화면.get("이름", "")), 기다림,
                              _갈래(tag))
                    커서.치우기(쪽)      # 화살표는 사람 눈에만 — 값·사진에는 들어가지 않는다
                    값 = webvalue.긁기(쪽, 화면.get("이름", ""))
                    webvalue.쓰기(os.path.join(결과폴더, 값이름(이름)), 값)
                    쪽.screenshot(path=os.path.join(결과폴더, 이름), full_page=True)
                except Exception as e:
                    까닭 = str(e).strip().splitlines()[0]
                    print(f"    ✗ 못 찍음: {까닭}", flush=True)
                    실패.append({"화면이름": 화면["이름"], "까닭": 까닭})
                    앞장성공 = False
                    continue
                앞장성공 = True
                한줄 = {"파일": 이름, "값파일": 값이름(이름), "화면번호": 화면["번호"],
                      "화면이름": 화면["이름"], "상태": 화면.get("상태", "default"),
                      "잰것": len(값.get("elements", []))}
                if 화면.get("case_id"):
                    한줄["case_id"] = 화면["case_id"]
                if 화면.get("디자인이름"):
                    한줄["디자인이름"] = 화면["디자인이름"]
                찍힌것.append(한줄)
        finally:
            브라우저끄기(브라우저)

    찍힌것.sort(key=lambda x: x["화면번호"])
    return {"앱이름": tag["앱이름"], "플랫폼": tag["플랫폼"],
            "찍은때": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "화면폭": 폭, "찍힌것": 찍힌것, "못찍은것": 실패}
