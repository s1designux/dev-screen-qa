"""메뉴 훑기 — 사이트에 어떤 메뉴가 있는지 먼저 읽고, 시안과 닮은 화면을 스스로 짚는다.

왜 있나 (river 2026-09-16): 시안은 개발 주소를 모른다. 그래서 화면마다 주소를 사람이
적어야 했다. 로그인한 다음 메뉴 링크를 훑어 **[메뉴 이름 · 주소 · 그 화면 사진]** 을 모아 두면,
올린 시안과 그림으로 견주어 어느 메뉴인지 **스스로 짚을 수 있다.**

무엇을 하나
  ① 로그인한다(들어가는 길과 같은 길 — lib/들어가는길.py)
  ② 첫 화면의 메뉴 링크를 모으고, 한 단계만 더 들어가 그 안의 메뉴도 모은다
  ③ 메뉴마다 화면을 한 장 찍어 **지문**(16×16 밝기)을 남긴다 — 사진은 검수에 쓰지 않는다
  ④ 시안 그림의 지문과 견주어 가장 닮은 메뉴를 짚는다

무엇을 하지 않나
  · **확정하지 않는다.** 애매하면 비워 두고 사람에게 묻는다(CLAUDE.md 2번-2).
  · 계정·주소가 비어 있으면 아예 돌지 않는다 — 로그인을 잘못 여러 번 해 계정이 잠기지 않게.
  · 눌러야 나오는 상세 화면은 메뉴가 아니라서 잡히지 않는다. 그 줄은 빈 칸으로 둔다.
"""
import hashlib
import json
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

여기 = Path(__file__).resolve().parent
뿌리 = 여기.parent
사전파일 = 뿌리 / "apps" / "메뉴사전.json"

sys.path.insert(0, str(뿌리 / "lib"))
import webshot  # noqa: E402
import 계정확인  # noqa: E402
import 들어가는길  # noqa: E402
import 매체  # noqa: E402

메뉴많아야 = 40          # 한 번에 훑을 메뉴 수 — 더 있으면 앞에서부터
한단계더볼것 = 12        # 그중 몇 개나 더 들어가 안쪽 메뉴를 볼까
동시에 = 8               # 한꺼번에 읽을 창 수 — 기다리는 시간이 대부분이라 나눈 만큼 빨라진다
닮음문턱 = 0.72          # 이만큼 닮아야 짚는다
갈라짐 = 0.05            # 1등이 2등보다 이만큼은 앞서야 짚는다(비슷한 목록 화면을 헷갈리지 않게)

_잠금 = threading.Lock()
_상태 = {"진행중": False, "지금": 0, "전부": 0, "말": "", "읽는것": "",
       "앱이름": "", "때": "", "까닭": "", "메뉴": [], "짝": {}}


def 상태():
    with _잠금:
        return json.loads(json.dumps(_상태, ensure_ascii=False))


def _고치기(**칸):
    with _잠금:
        _상태.update(칸)


# ── 기억 ────────────────────────────────────────────────────
def _사전읽기():
    if not 사전파일.exists():
        return {}
    try:
        것 = json.loads(사전파일.read_text(encoding="utf-8"))
        return 것 if isinstance(것, dict) else {}
    except Exception:
        return {}


def 기억읽기(앱이름):
    """전에 훑어 둔 메뉴 — 같은 사이트는 다시 훑지 않는다."""
    return _사전읽기().get((앱이름 or "").strip()) or {}


def _기억쓰기(앱이름, 메뉴들):
    사전 = _사전읽기()
    사전[(앱이름 or "").strip()] = {"때": time.strftime("%Y-%m-%d %H:%M"), "메뉴": 메뉴들}
    사전파일.parent.mkdir(parents=True, exist_ok=True)
    사전파일.write_text(json.dumps(사전, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 그림 지문 ────────────────────────────────────────────────
_지문크기 = 32
_줄수 = 64              # 세로는 더 잘게 — 무엇이 위·아래 어디에 놓였나가 화면을 가른다
_지문뽑기 = """
(자료) => new Promise((끝) => {
  const 그림 = new Image();
  그림.onload = () => {
    const N = %d, M = %d;
    const 판 = document.createElement('canvas');
    판.width = N; 판.height = M;
    const 붓 = 판.getContext('2d');
    붓.drawImage(그림, 0, 0, N, M);
    const 점 = 붓.getImageData(0, 0, N, M).data;
    const 밝기 = [];
    for (let i = 0; i < 점.length; i += 4)
      밝기.push((점[i] * 0.299 + 점[i + 1] * 0.587 + 점[i + 2] * 0.114) / 255);
    // 줄마다 / 칸마다 '얼마나 찼나' — 글자 한 자 차이에는 잘 흔들리지 않고, 배치가 다르면 크게 다르다.
    const 줄 = [], 칸 = new Array(N).fill(0);
    for (let y = 0; y < M; y++) {
      let 합 = 0;
      for (let x = 0; x < N; x++) {
        const v = 1 - 밝기[y * N + x];
        합 += v; 칸[x] += v;
      }
      줄.push(합 / N);
    }
    끝({밝기: 밝기, 줄: 줄, 칸: 칸.map((v) => v / M),
        가로: 그림.naturalWidth, 세로: 그림.naturalHeight});
  };
  그림.onerror = () => 끝(null);
  그림.src = 자료;
})
""" % (_지문크기, _줄수)


def _자료주소(그림바이트):
    import base64
    return "data:image/png;base64," + base64.b64encode(그림바이트).decode("ascii")


def 지문(쪽, 그림바이트):
    """그림 한 장 → 지문(밝기 · 줄마다 · 칸마다 · 가로세로). 브라우저 안에서 잰다."""
    try:
        return 쪽.evaluate(_지문뽑기, _자료주소(그림바이트))
    except Exception:
        return None


def _상관(가, 나):
    if not 가 or not 나 or len(가) != len(나):
        return 0.0
    n = len(가)
    평균가, 평균나 = sum(가) / n, sum(나) / n
    위 = sum((a - 평균가) * (b - 평균나) for a, b in zip(가, 나))
    아래 = (sum((a - 평균가) ** 2 for a in 가) ** 0.5) * (sum((b - 평균나) ** 2 for b in 나) ** 0.5)
    return max(0.0, 위 / 아래) if 아래 else 0.0


def 닮음(가, 나):
    """두 그림이 같은 화면으로 보이나 (0~1).

    시안과 개발 화면은 **원래 조금 다르다**(그걸 검수하는 것이니까). 그래서 점 하나하나가 아니라
    **무엇이 위·아래 어디에 놓였나**(줄마다·칸마다 채워진 정도)를 주로 본다.
    세로 길이가 많이 다르면 깎는다 — 긴 목록 화면과 짧은 안내 화면은 다른 화면이다.
    """
    if not isinstance(가, dict) or not isinstance(나, dict):
        return 0.0
    점수 = (0.45 * _상관(가.get("줄"), 나.get("줄"))
          + 0.30 * _상관(가.get("칸"), 나.get("칸"))
          + 0.25 * _상관(가.get("밝기"), 나.get("밝기")))
    비 = []
    for 것 in (가, 나):
        가로, 세로 = 것.get("가로") or 0, 것.get("세로") or 0
        비.append((세로 / 가로) if 가로 else 0)
    if 비[0] and 비[1]:
        점수 *= 0.6 + 0.4 * (min(비) / max(비))
    return max(0.0, min(1.0, 점수))


# ── 이름으로도 견준다 ────────────────────────────────────────
_군더더기 = re.compile(r"(웹|앱|모바일|pc)[_\s-]*|[_\s-]*(기본|default|화면|페이지|view|screen)$", re.I)


def 이름닮음(디자인이름, 메뉴이름):
    """시안 이름과 메뉴 이름이 얼마나 같은가 — '웹_공지사항_기본' 과 '공지사항' 은 같은 것으로 본다."""
    from difflib import SequenceMatcher

    def 다듬기(글):
        글 = re.sub(r"\s+", "", (글 or "").strip().lower())
        for _ in range(3):
            글 = _군더더기.sub("", 글)
        return 글

    가, 나 = 다듬기(디자인이름), 다듬기(메뉴이름)
    if not 가 or not 나:
        return 0.0
    if 가 == 나 or 가 in 나 or 나 in 가:
        return 1.0
    return SequenceMatcher(None, 가, 나).ratio()


# ── 링크 모으기 ──────────────────────────────────────────────
_링크뽑기 = """
() => Array.from(document.querySelectorAll('a[href]')).map((a) => ({
  이름: (a.innerText || a.getAttribute('aria-label') || a.title || '').trim().replace(/\\s+/g, ' ').slice(0, 40),
  주소: a.href,
}))
"""
안볼말 = re.compile(r"로그아웃|logout|sign\s*out|다운로드|download|\.(pdf|zip|xlsx?|hwp|docx?)$", re.I)


def _같은집인가(주소, 바탕):
    try:
        가 = urlparse(주소)
        나 = urlparse(바탕)
        return 가.scheme in ("http", "https") and 가.netloc == 나.netloc
    except Exception:
        return False


def _다듬기(주소):
    """같은 화면을 두 번 세지 않게 — 조각(#…)은 떼고 끝 빗금만 맞춘다."""
    가 = urlparse(주소)
    길 = 가.path or "/"
    return f"{가.scheme}://{가.netloc}{길}" + (f"?{가.query}" if 가.query else "")


def 링크모으기(쪽, 바탕, 이미본것):
    모은것 = []
    try:
        것들 = 쪽.evaluate(_링크뽑기)
    except Exception:
        return 모은것
    for 하나 in 것들:
        주소 = _다듬기(하나.get("주소") or "")
        이름 = (하나.get("이름") or "").strip()
        if not 이름 or not _같은집인가(주소, 바탕) or 안볼말.search(이름) or 안볼말.search(주소):
            continue
        if 주소 in 이미본것:
            continue
        이미본것.add(주소)
        모은것.append({"이름": 이름, "주소": 주소})
    return 모은것


# ── 한 바퀴 ─────────────────────────────────────────────────
def _조용해질때까지(쪽, 최대초):
    """훑을 때만 쓰는 기다림 — 지문 한 장만 뜨면 되니 꼬리 시간을 달지 않는다.

    (찍을 때 쓰는 webshot._가라앉기 는 사람이 볼 사진이라 뒤에 300ms 를 더 준다. 여기는 아니다.)
    """
    try:
        쪽.wait_for_load_state("networkidle", timeout=int(최대초 * 1000))
    except Exception:
        pass


def _tag(작업):
    return {"앱이름": 작업.get("앱이름", ""),
            "유형": 작업.get("유형") or 매체.PC웹,
            "플랫폼": "web",
            "기본주소": 작업.get("기본주소", ""),
            "화면폭": 작업.get("찍을폭") or 1440,
            "로그인": 작업.get("로그인", ""),
            "들어가는길": 작업.get("들어가는길", ""),
            "시험아이디": 작업.get("시험아이디", ""),
            "시험비밀번호": 작업.get("시험비밀번호", ""),
            "화면": []}


def 돌만한가(작업):
    """훑어도 되는 자리인가 — 웹이고, 주소가 있고, 로그인이 있으면 계정도 있을 때만."""
    if (작업.get("유형") or "") not in (매체.PC웹, 매체.모바일웹):
        return False, "웹이 아닙니다."
    if not (작업.get("기본주소") or "").strip():
        return False, "기본 주소가 아직 없습니다."
    tag = _tag(작업)
    if 들어가는길.로그인쓰나(tag):
        것 = 들어가는길.계정읽기(tag)
        if not (것["아이디"] and 것["비밀번호"]):
            return False, "시험 아이디·비밀번호가 아직 없습니다."
    return True, ""


def 시안들(초안):
    """찍을 목록에서 그림이 있는 줄만 — (줄차례, 디자인이름, 그림파일)."""
    것들 = []
    for i, r in enumerate(초안 or []):
        길 = (r.get("디자인그림") or "").strip()
        if 길 and Path(길).exists():
            것들.append((i, (r.get("디자인이름") or r.get("이름") or "").strip(), Path(길)))
    return 것들


def 총점(그림점수, 이름점수):
    """그림이 주(主)고 이름이 거든다 — 이름이 없거나 다르면 그림만으로도 짚을 수 있게."""
    return round(0.65 * 그림점수 + 0.35 * 이름점수, 4) if 이름점수 else round(그림점수, 4)


def _짝맞추기(시안지문들, 메뉴들):
    """시안마다 가장 닮은 메뉴를 짚는다. 애매하면 짚지 않는다(비워 둔다 — CLAUDE.md 2번-2)."""
    짝 = {}
    for 줄차례, 이름, 지문값 in 시안지문들:
        점수 = []
        for m in 메뉴들:
            if not m.get("지문"):
                continue
            그림 = 닮음(지문값, m["지문"])
            글자 = max(이름닮음(이름, m.get("이름", "")), 이름닮음(이름, m.get("제목", "")))
            점수.append((총점(그림, 글자), 그림, 글자, m))
        점수.sort(key=lambda t: -t[0])
        if not 점수:
            continue
        일등, 그림, 글자, 메뉴 = 점수[0]
        이등 = 점수[1][0] if len(점수) > 1 else 0.0
        확정 = 일등 >= 닮음문턱 and (일등 - 이등) >= 갈라짐
        # 다음으로 닮은 것도 함께 내민다 — 짚은 것이 틀렸을 때 사람이 바로 바꿔 고를 수 있게
        후보 = [{"주소": m["주소길"], "메뉴이름": m["이름"], "닮음": round(점 * 100)}
              for 점, _그림, _글자, m in 점수[:3]]
        짝[str(줄차례)] = {"주소": 메뉴["주소길"], "메뉴이름": 메뉴["이름"],
                        "닮음": round(일등 * 100), "그림": round(그림 * 100),
                        "이름": round(글자 * 100), "확정": 확정, "디자인이름": 이름,
                        "후보": 후보}
    return 짝


def _메뉴더하기(메뉴들, 새것):
    """같은 화면을 두 번 두지 않는다 — 주소만 다른 같은 화면이면 **짧은 주소**를 남긴다.

    (로그인 뒤 돌아온 첫 화면은 주소 뒤에 물음표가 붙어 있는 일이 많다.)
    """
    for i, 있던것 in enumerate(메뉴들):
        if 닮음(있던것.get("지문"), 새것.get("지문")) >= 0.995:
            if len(새것["주소길"]) < len(있던것["주소길"]):
                메뉴들[i] = 새것
            return
    메뉴들.append(새것)


def _주소길(주소, 바탕):
    """기본 주소 뒤에 붙는 부분만 남긴다 — 찍을 목록의 '개발 주소' 칸 모양."""
    가, 나 = urlparse(주소), urlparse(바탕)
    if 가.netloc != 나.netloc:
        return 주소
    길 = 가.path or "/"
    if 가.query:
        길 += "?" + 가.query
    바탕길 = (나.path or "").rstrip("/")
    if 바탕길 and 길.startswith(바탕길 + "/"):
        길 = 길[len(바탕길):]
    return 길


def 한바퀴(작업):
    """로그인 → 메뉴 훑기 → 그림으로 짝짓기. 다른 실에서 돈다."""
    tag = _tag(작업)
    바탕 = 매체.주소다듬기(tag["기본주소"], tag["유형"])
    초안시안 = 시안들(작업.get("초안"))
    sync_playwright = webshot.연장가져오기()
    메뉴들, 이미본것 = [], set()

    with sync_playwright() as 연장:
        # 훑는 동안은 창을 띄우지 않는다 — 사람이 보던 화면을 가리지 않게.
        브라우저, _ = webshot.브라우저켜기(연장, 보이기=False)
        칸 = 브라우저.new_context(viewport={"width": int(tag["화면폭"] or 1440), "height": 900})
        쪽 = 칸.new_page()
        try:
            _고치기(말="로그인하는 중", 읽는것="")
            if 들어가는길.로그인쓰나(tag):
                것 = 들어가는길.웹으로(쪽, tag)
                if 것["됨"] is False:
                    raise RuntimeError(것["까닭"])
            # 창을 실 사이로 넘길 수는 없어(playwright 동기 판) 실마다 제 브라우저를 켜고,
            # **로그인한 자리만 이어받는다** — 계정을 다시 두드리지 않는다.
            # 링크를 모으고 시안 지문을 재는 동안 곁창들이 같이 준비되게 여기서 먼저 띄운다.
            로그인자리 = None
            if 들어가는길.로그인쓰나(tag):
                try:
                    로그인자리 = 칸.storage_state()
                except Exception:
                    로그인자리 = None
            일감준비 = threading.Event()
            곁실들 = [threading.Thread(target=lambda: _곁창(), daemon=True)
                   for _ in range(max(1, 동시에) - 1)]

            if not (쪽.url or "").startswith("http"):
                쪽.goto(바탕, wait_until="load", timeout=30000)
            elif 쪽.url.rstrip("/") == 바탕.rstrip("/"):
                pass          # 로그인한 자리가 곧 첫 화면이다
            _조용해질때까지(쪽, 1.2)

            _고치기(말="메뉴를 찾는 중")
            이미본것.add(_다듬기(쪽.url))
            차례 = [{"이름": "첫 화면", "주소": _다듬기(쪽.url)}] + 링크모으기(쪽, 바탕, 이미본것)
            차례 = 차례[:메뉴많아야]
            _고치기(전부=len(차례))

            # 시안 지문은 한 번만 잰다
            시안지문들 = []
            for 줄차례, 이름, 길 in 초안시안:
                시안지문들.append((줄차례, 이름, 지문(쪽, 길.read_bytes())))

            # 창 여럿으로 나눠 읽는다. 한 메뉴에 드는 1.4초 가운데 1.36초가 '화면이 뜨기를
            # 기다리는 시간'이라(2026-09-16 실측), 창을 늘린 만큼 그대로 줄어든다.
            # 로그인은 한 번만 하고 그 자리(칸)를 창들이 같이 쓴다 — 계정을 여러 번 두드리지 않는다.
            일감잠금 = threading.Lock()
            다음 = [0]                 # 다음에 읽을 차례
            더볼것 = [한단계더볼것]
            읽은수 = [0]

            def 다음일감():
                with 일감잠금:
                    if 다음[0] >= len(차례) or 다음[0] >= 메뉴많아야:
                        return None
                    i = 다음[0]
                    다음[0] += 1
                    return i, 차례[i]

            def 일꾼(내쪽):
                while True:
                    일 = 다음일감()
                    if 일 is None:
                        return
                    i, 하나 = 일
                    try:
                        if _다듬기(내쪽.url) != 하나["주소"]:
                            내쪽.goto(하나["주소"], wait_until="load", timeout=20000)
                        _조용해질때까지(내쪽, 1.2)
                        사진 = 내쪽.screenshot(full_page=True)
                        제목 = 내쪽.evaluate("() => (document.querySelector('h1,h2')?.innerText "
                                          "|| document.title || '').trim().slice(0, 40)")
                        지문값 = 지문(내쪽, 사진)
                    except Exception:
                        continue
                    with 일감잠금:
                        읽은수[0] += 1
                        _메뉴더하기(메뉴들, {"차례": i, "이름": 하나["이름"], "제목": 제목,
                                         "주소": 하나["주소"],
                                         "주소길": _주소길(하나["주소"], 바탕),
                                         "지문": 지문값})
                        # 한 단계 더 들어가 안쪽 메뉴도 본다(창이 아직 그 화면에 있을 때).
                        if 더볼것[0] > 0 and len(차례) < 메뉴많아야:
                            더볼것[0] -= 1
                            try:
                                차례.extend(링크모으기(내쪽, 바탕, 이미본것))
                                del 차례[메뉴많아야:]
                            except Exception:
                                pass
                        # 읽는 대로 바로 짚어 준다 — 다 끝날 때까지 기다리지 않게
                        차례대로 = sorted(메뉴들, key=lambda m: m.get("차례", 0))
                        _고치기(지금=읽은수[0], 전부=len(차례), 말="메뉴를 읽는 중",
                              읽는것=하나["이름"],
                              짝=_짝맞추기(시안지문들, 차례대로),
                              메뉴=[{"이름": m["이름"], "주소길": m["주소길"]} for m in 차례대로])

            def _곁창():
                """제 브라우저를 켜서 같이 읽는다. 로그인이 안 이어지면 조용히 물러난다."""
                sp = webshot.연장가져오기()
                try:
                    with sp() as 딴연장:
                        딴브라우저, _ = webshot.브라우저켜기(딴연장, 보이기=False)
                        try:
                            딴칸 = 딴브라우저.new_context(
                                viewport={"width": int(tag["화면폭"] or 1440), "height": 900},
                                storage_state=로그인자리)
                            딴쪽 = 딴칸.new_page()
                            딴쪽.goto(바탕, wait_until="load", timeout=30000)
                            _조용해질때까지(딴쪽, 1.0)
                            if 로그인자리 and 계정확인.판정(딴쪽).get("됨") is False:
                                return          # 로그인이 안 이어졌다 — 다시 로그인하지 않는다
                            일감준비.wait(60)
                            일꾼(딴쪽)
                        finally:
                            webshot.브라우저끄기(딴브라우저)
                except Exception:
                    return

            for 실 in 곁실들:
                실.start()
            일감준비.set()          # 곁창들이 이제 읽어도 된다
            일꾼(쪽)                 # 로그인한 창도 한 몫 읽는다
            for 실 in 곁실들:
                실.join()
            메뉴들.sort(key=lambda m: m.get("차례", 0))
        finally:
            webshot.브라우저끄기(브라우저)

    _기억쓰기(tag["앱이름"], [{"이름": m["이름"], "제목": m.get("제목", ""),
                          "주소길": m["주소길"], "주소": m["주소"],
                          "지문": m["지문"]} for m in 메뉴들])
    return 메뉴들


def 자동시작(작업, 다시=False):
    """② 찍을 목록에 들어오면 저절로 시작한다. 이미 훑은 사이트는 다시 훑지 않는다."""
    앱이름 = (작업.get("앱이름") or "").strip()
    with _잠금:
        if _상태["진행중"]:
            return False
    된다, 까닭 = 돌만한가(작업)
    if not 된다:
        _고치기(까닭=까닭, 말="", 진행중=False)
        return False
    기억 = 기억읽기(앱이름)
    if 기억 and not 다시:
        메뉴들 = 기억.get("메뉴") or []
        _고치기(앱이름=앱이름, 때=기억.get("때", ""), 까닭="", 진행중=True,
              말="전에 훑어 둔 메뉴와 견주는 중", 지금=0, 전부=len(메뉴들), 읽는것="",
              메뉴=[{"이름": m["이름"], "주소길": m.get("주소길", "")} for m in 메뉴들])
        초안시안 = 시안들(작업.get("초안"))
        if not (초안시안 and any(m.get("지문") for m in 메뉴들)):
            _고치기(진행중=False, 말="전에 훑어 둔 메뉴", 지금=len(메뉴들))
            return False

        def 견주기():
            # 사이트를 다시 돌지 않는다 — 기억해 둔 지문과 시안 그림만 견준다.
            try:
                _고치기(짝=_기억으로짝(초안시안, 메뉴들), 말="전에 훑어 둔 메뉴",
                      지금=len(메뉴들))
            except Exception as e:
                _고치기(까닭=str(e).strip().splitlines()[0][:150], 말="")
            finally:
                _고치기(진행중=False)

        threading.Thread(target=견주기, daemon=True).start()
        return True

    _고치기(진행중=True, 지금=0, 전부=0, 말="브라우저를 켜는 중", 읽는것="",
          앱이름=앱이름, 까닭="", 짝={}, 메뉴=[])

    def 돌리기():
        try:
            한바퀴(작업)
            _고치기(말="다 읽었습니다", 읽는것="", 때=time.strftime("%Y-%m-%d %H:%M"))
        except Exception as e:
            _고치기(까닭=str(e).strip().splitlines()[0][:150], 말="")
        finally:
            _고치기(진행중=False)

    threading.Thread(target=돌리기, daemon=True).start()
    return True


def _기억으로짝(초안시안, 메뉴들):
    """전에 훑어 둔 지문으로 짚는다 — 브라우저를 켜지 않고 그림만 견준다."""
    sync_playwright = webshot.연장가져오기()
    with sync_playwright() as 연장:
        브라우저, _ = webshot.브라우저켜기(연장, 보이기=False)
        쪽 = 브라우저.new_context().new_page()
        try:
            시안지문들 = [(i, 이름, 지문(쪽, 길.read_bytes())) for i, 이름, 길 in 초안시안]
        finally:
            webshot.브라우저끄기(브라우저)
    return _짝맞추기(시안지문들, 메뉴들)
