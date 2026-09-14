"""수정요청서 — 포털에서 내려받는 '개발이 먼저 고칠 것' 한 장.

검수를 시작하기 전에 **값으로 확인되는 차이**(시안↔개발, 토큰·컴포넌트 규정)를 먼저 개발에 넘긴다.
그것부터 맞춰 놓지 않으면 사람이 눈으로 보는 검수가 헛돈다 — 같은 지적을 차수마다 다시 쓰게 된다.

읽는 자료는 촬영기가 접수 때 그림 옆에 함께 넣어 둔 두 개다(`site/intake.py`):
  uploads/{page}_design.json   시안 값 (틀 + 요소)
  uploads/{page}_dev값.json    개발 화면에서 잰 값

둘 다 있는 페이지만 대조한다(앱 촬영본·옛 자료는 값이 없어 건너뛴다).
여기서 나오는 것도 **후보**다 — 확정은 사람이 한다(CLAUDE.md 2번-2).

같은 후보가 페이지 상세에도 카드로 올라가 있다(`value_candidates.py`). 사람이 거기서 **제외**로 내린 것은
이 문서에서도 빠진다 — 문서는 데이터를 읽어 만드는 출력물이다(CLAUDE.md 2번-1).
"""
import json
import time

import value_candidates

준비됨 = True
try:
    from valueqa.__main__ import 시안읽기
    from valueqa.candidates import 후보뽑기
    from valueqa.fixdoc import 지시서묶음, 셈만
except Exception:                                   # valueqa 가 없으면 조용히 꺼져 있는다
    준비됨 = False

_정본칸 = {"때": 0.0, "것": None}
정본수명 = 600                                        # 초. 정본은 시시각각 바뀌지만 화면을 열 때마다 받아 올 수는 없다


def 정본():
    """회사 규정 정본 — 한 번 받아 두고 10분쯤 같은 것을 쓴다. 못 받으면 None(규정 대조 없이 간다)."""
    if not 준비됨:
        return None
    if _정본칸["것"] is not None and time.time() - _정본칸["때"] < 정본수명:
        return _정본칸["것"]
    try:
        from valueqa.registry import 정본가져오기
        _정본칸["것"] = 정본가져오기("auto")
    except Exception:                               # 폐쇄망·오프라인이면 규정 대조는 빼고 간다
        _정본칸["것"] = None
    _정본칸["때"] = time.time()
    return _정본칸["것"]


def _짝자료(uploads, pages):
    """페이지마다 (시안 값, 개발 값) 파일이 둘 다 있는 것만 고른다."""
    쓸것 = []
    for n, p in enumerate(pages, 1):
        시안길 = uploads / f"{p['uuid']}_design.json"
        개발길 = uploads / f"{p['uuid']}_dev값.json"
        if 시안길.exists() and 개발길.exists():
            쓸것.append((n, p, 시안길, 개발길))
    return 쓸것


def _대조(uploads, pages, human_key, 주소, store=None):
    """페이지별 값 대조 + (받아 둔 정본이 있으면) 규정 대조. 사람이 제외한 후보는 뺀다."""
    본 = 정본()
    쓸것 = _짝자료(uploads, pages)
    판정 = value_candidates.판정표(store, [p['uuid'] for _, p, _, _ in 쓸것]) if store else {}
    화면별 = []
    for n, p, 시안길, 개발길 in 쓸것:
        시안 = 시안읽기(str(시안길))
        with open(개발길, encoding="utf-8") as f:
            개발 = json.load(f)
        결과 = 후보뽑기(시안, 개발)
        메모 = {"화면키": "%s-%02d" % (human_key, n), "화면이름": p["name"], "주소": 주소}
        if 본:
            from valueqa.rules import 규정검사
            메모["규정"] = 규정검사(결과, 본, None, 0, "PC")
        화면별.append((value_candidates.거른것(결과, 판정.get(p['uuid'])), 메모))
    return 화면별


def 셈하기(uploads, pages, human_key, 주소, store=None):
    """주의 카드에 적을 숫자. **문서의 '모두' 칸과 같은 수**를 쓴다(둘이 어긋나면 안 된다)."""
    if not 준비됨:
        return None
    try:
        화면별 = _대조(uploads, pages, human_key, 주소, store)
    except Exception:
        return None
    return 셈만(화면별) if 화면별 else None


def 문서만들기(uploads, pages, human_key, 화면이름, 주소, store=None):
    """내려받을 Markdown 한 장."""
    if not 준비됨:
        return None
    화면별 = _대조(uploads, pages, human_key, 주소, store)
    if not 화면별:
        return None
    return 지시서묶음(화면별, 제목="개발화면 수정 요청 — %s" % 화면이름, 차수=1)


def 카드(human_key, 셈):
    """검수 페이지 목록 맨 위에 붙는 주의 카드."""
    몇 = ("값으로 확인된 차이가 <b>%d곳</b> 있습니다." % 셈) if 셈 else "값으로 확인된 차이를 모아 두었습니다."
    return f"""
    <section class="warn-card">
      <div class="warn-head">⚠ 개발화면 검수 전 적용해주세요</div>
      <div class="warn-body">
        <p>{몇} 색·크기·글꼴처럼 <b>값으로 딱 떨어지는 것</b>과, 회사 토큰·공통 컴포넌트 규정에
           어긋난 것입니다. 사람이 눈으로 보는 검수를 시작하기 <b>전에</b> 개발이 먼저 반영해야
           같은 지적을 차수마다 되풀이하지 않습니다.</p>
        <a class="s1-btn s1-btn-primary" href="/screen/{human_key}/수정요청.md" download>수정요청서 MD 다운로드</a>
        <a class="s1-btn s1-btn-primary" href="/screen/{human_key}/수정요청.html" target="_blank">수정요청서 PDF 보기</a>
        <span class="warn-hint">개발·퍼블리셔에게 그대로 넘기는 문서입니다. 자동으로 찾은 후보이며 확정은 디자이너가 합니다.
          <b>PDF 보기</b>는 내려받지 않고 그 자리에서 읽고, 눌러서 PDF 로 저장합니다.</span>
      </div>
    </section>"""


CSS = """
/* 주의 카드 — 값은 S-1 디자인가이드 토큰만 쓴다(색·크기를 직접 적지 않는다).
   토큰 네 장은 포털이 /assets/css/ 로 내보낸다. */
.warn-card{border:var(--border-width-1) solid var(--color-status-warning);
  border-radius:var(--radius-card-md);background:var(--color-bg-level-1);
  margin:0 0 var(--spacing-16);overflow:hidden}
.warn-head{background:var(--color-status-warning);color:var(--color-text-primary);
  font-weight:var(--font-weight-bold);padding:var(--spacing-8) var(--spacing-14);
  font-size:var(--font-size-14)}
.warn-body{padding:var(--spacing-12) var(--spacing-14) var(--spacing-14)}
.warn-body p{margin:0 0 var(--spacing-10);font-size:var(--font-size-14);
  line-height:var(--line-height-140);color:var(--color-text-tertiary)}
.warn-hint{display:block;margin-top:var(--spacing-8);
  font-size:var(--font-size-12);color:var(--color-text-caption)}

/* S-1 Button · Size XSM(PC) — h34 / 좌우 spacing-8 / radius-4 / body 14M.
   두 단추는 같은 무게다(둘 다 이 카드의 할 일이다 — river 2026-09-14). */
.s1-btn{display:inline-flex;align-items:center;justify-content:center;
  height:34px;min-width:64px;padding:0 var(--spacing-8);
  border-radius:var(--radius-button-md);border:var(--border-width-1) solid transparent;
  font-size:var(--font-size-14);font-weight:var(--font-weight-medium);
  text-decoration:none;cursor:pointer}
.s1-btn+.s1-btn{margin-left:var(--spacing-8)}
.s1-btn-primary{background:var(--color-button-bg-primary--default);
  border-color:var(--color-button-border-primary--default);
  color:var(--color-button-label-primary--default)}
.s1-btn-primary:hover{background:var(--color-button-bg-primary--hover);
  border-color:var(--color-button-border-primary--hover);
  color:var(--color-button-label-primary--hover)}
"""
