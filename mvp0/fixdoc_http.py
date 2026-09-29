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

import s1
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
        # 스토리보드 ID는 그 화면 한 장에 붙는다(river 2026-09-15). 아직 안 적었으면 묶음키+순번으로 대신한다.
        메모 = {"화면키": (p.get("human_key") or "%s-%02d" % (human_key, n)),
                "화면이름": p["name"], "주소": 주소}
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


def 카드(human_key, 셈, 부품=True):
    """검수 페이지 목록 맨 위에 붙는 주의 칸.

    모양은 촬영 준비 사이트 ①의 '디자인 수정 필요' 칸과 같다(사람이 보는 말·모양이 두 곳에서 같아야 한다).
    """
    몇 = ("<b>%d곳</b>입니다." % 셈) if 셈 else "모아 두었습니다."
    센 = ("· %d건" % 셈) if 셈 else ""
    # DESIGN_SYSTEM_GAP: 정본 아이콘 스물다섯에 '주의(세모)'가 없다. 접고 펴는 화살표는
    # 정본 chevron 을 그대로 쓰고, 세모만 같은 규격(24 틀)으로 그려 CSS 가 가면으로 깐다.
    주의아이콘 = '<span class="ico" aria-hidden="true"></span>'
    화살표 = '<span class="arw" aria-hidden="true"></span>'
    단추 = (s1.단추링크("수정요청서 MD 다운로드", "/screen/%s/수정요청.md" % human_key,
                    "primary", download=True)
          + s1.단추링크("수정요청서 PDF 보기", "/screen/%s/수정요청.html" % human_key,
                    "primary", target="_blank", rel="noopener"))
    return f"""
    <details class="warn-card" open>
      <summary>{주의아이콘}<span class="ttl">개발화면 검수 전 적용해주세요</span>
        <span class="muted">{센}</span>{화살표}</summary>
      <div class="body">
        <p>색·크기·글꼴이 시안과 다르거나 회사 색·컴포넌트를 쓰지 않은 곳, {몇}<br>
           <b>검수를 시작하기 전에</b> 개발이 먼저 고치면 같은 수정필요를 되풀이하지 않습니다.</p>
        {단추}
      </div>
    </details>"""


CSS = """
/* 주의 칸 — 촬영 준비 사이트 ①의 '디자인 수정 필요' 칸과 같은 모양.
   값은 S-1 디자인가이드 토큰만 쓴다(색·크기를 직접 적지 않는다). */
.warn-card{background:var(--color-surface-default);
  border:var(--border-width-1) solid var(--color-red-100);
  border-radius:var(--radius-card-md);margin:0 0 var(--spacing-16)}
.warn-card>summary{list-style:none;cursor:pointer;display:flex;align-items:center;
  gap:var(--spacing-6);padding:var(--spacing-16) var(--spacing-20);
  font-size:var(--font-size-14);color:var(--color-text-state-caution);
  border-radius:var(--radius-card-md)}
.warn-card>summary::-webkit-details-marker{display:none}
.warn-card>summary:hover{background:var(--color-red-50)}
.warn-card[open]>summary{border-radius:var(--radius-card-md) var(--radius-card-md) 0 0}
.warn-card>summary .ttl{font-weight:var(--font-weight-bold)}
.warn-card>summary .muted{font-weight:var(--font-weight-medium)}
/* 아이콘은 글자색을 따라가게 가면으로 깐다(정본 부품이 아이콘을 다루는 방식과 같다).
   DESIGN_SYSTEM_GAP: '주의(세모)'가 정본 스물다섯에 없어 같은 규격으로 그려 /assets/img/ 에 두었다.
   화살표는 정본 chevron 을 그대로 쓴다. */
.warn-card>summary .ico,.warn-card>summary .arw{flex:0 0 auto;background:currentColor;
  -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;
  -webkit-mask-position:center;mask-position:center;
  -webkit-mask-size:contain;mask-size:contain}
.warn-card>summary .ico{width:var(--sizing-16);height:var(--sizing-16);
  -webkit-mask-image:url('/assets/img/icon-caution.svg');
  mask-image:url('/assets/img/icon-caution.svg')}
.warn-card>summary .arw{margin-left:auto;width:var(--sizing-20);height:var(--sizing-20);
  transform:rotate(90deg);transition:transform .15s;
  -webkit-mask-image:url('/assets/icons/chevron.svg');
  mask-image:url('/assets/icons/chevron.svg')}
.warn-card[open]>summary .arw{transform:rotate(-90deg)}
.warn-card>.body{padding:0 var(--spacing-20) var(--spacing-16)}
/* 단추 둘 사이 — 정본 부품(data-s1-component)으로 낼 때도 간격은 여기서 준다 */
.warn-card>.body [data-s1-component="button"]+[data-s1-component="button"]{margin-left:var(--spacing-8)}
.warn-card>.body p{margin:0 0 var(--spacing-10);font-size:var(--font-size-14);
  line-height:var(--line-height-140);color:var(--color-text-body-tertiary)}

"""
