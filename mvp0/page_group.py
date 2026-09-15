"""검수 페이지를 '스토리보드 ID' 로 자동으로 묶어 보이기 (river 확정 2026-09-15).

한 화면 묶음 안에도 로그인·회원가입·비밀번호 찾기처럼 여러 화면이 섞인다.
가르는 자(尺)는 **스토리보드 ID** 다 — ID 는 UI 사양서에서 오고,
포털은 그 이름을 보고 **묶기만** 한다. ID 를 지어 붙이지 않는다 (CLAUDE.md 2번-2).

묶는 법 — **ID 에서 '무엇을 하는 화면인가' 까지가 뭉치**다 (river 2026-09-15):
- `uv-web-login001` · `uv-web-login002` → 뭉치 `uv-web-login` (로그인 무리).
  글자에 바로 붙은 끝 숫자는 그 무리 안의 낱장 번호로 본다.
- 숫자가 구분자 뒤에 떨어져 있으면(`UV-WEB-012` · `UV_WEB_LOGIN_01`) 그 마디까지가 한 화면이다 → ID 전체가 뭉치 키.
  (`UV-WEB-012` 와 `UV-WEB-013` 은 서로 다른 뭉치. CLAUDE.md 7번 예시 체계.)
- 상태 접미사는 떼고 본다: `UV-WEB-012@empty` 는 `UV-WEB-012` 뭉치에 든다 (CLAUDE.md 7번).
- 대소문자·앞뒤 공백은 같은 것으로 본다. 적힌 글자는 그대로 보여 준다.
- 아직 ID 를 안 적은 장은 맨 아래 '아직 ID 없음' 뭉치로 모인다.
"""
import re

_매체말 = {"웹", "앱", "모바일웹", "모바일", "PC", "AND", "APP", "IOS", "WEB"}


_끝숫자 = re.compile(r"(\d+)\s*$")


def 나눔(human_key):
    """ID 를 (뭉치 부분, 낱장 번호) 로 가른다.

    `uv-web-login001` → ("uv-web-login", "001")   # 글자에 붙은 숫자 = 무리 안의 번호
    `UV-WEB-012`      → ("UV-WEB-012", "")        # 구분자 뒤 숫자만인 마디 = 그 자체가 한 화면
    """
    k = (human_key or "").strip().split("@", 1)[0].strip()
    if not k:
        return "", ""
    m = _끝숫자.search(k)
    if m:
        앞 = k[:m.start()]
        if 앞 and 앞[-1].isalpha():       # 글자에 딱 붙은 숫자만 낱장 번호로 본다
            return 앞, m.group(1)
    return k, ""


def 뭉치키(human_key):
    """묶을 때 쓰는 열쇠. 상태 접미사(@…)와 낱장 번호를 떼고 대문자로 맞춘다. 없으면 빈 문자열."""
    return 나눔(human_key)[0].upper()


def _자연순(k):
    """`UV-WEB-2` 가 `UV-WEB-10` 보다 앞에 오게. 숫자 마디는 숫자로 견준다."""
    return [(1, int(t)) if t.isdigit() else (0, t) for t in re.split(r"(\d+)", k) if t]


def 이름제안(이름들):
    """장 이름들의 공통 뿌리. `웹_홈_로그인 시` · `웹_홈_사업장…` → `홈`.

    (page_move.JS 의 이름제안과 같은 방식 — 사람이 보는 말이 양쪽에서 같아야 한다.)
    """
    쪼갠것 = [n.split("_") for n in 이름들 if n]
    if not 쪼갠것:
        return ""
    공통 = []
    for i in range(min(len(x) for x in 쪼갠것)):
        토막 = 쪼갠것[0][i]
        if all(x[i] == 토막 for x in 쪼갠것):
            공통.append(토막)
        else:
            break
    while 공통 and 공통[0].strip() in _매체말:
        공통.pop(0)
    if not 공통:
        return 이름들[0]
    return " ".join(t.strip() for t in 공통 if t.strip())


def 묶기(pages):
    """[(보여줄ID, 뭉치이름, [페이지…]), …]. ID 있는 뭉치가 ID 순으로 먼저, 'ID 없음'이 맨 뒤."""
    순서, 뭉치 = [], {}
    for p in pages:
        k = 뭉치키(p.get("human_key"))
        if k not in 뭉치:
            뭉치[k] = {"id": 나눔(p.get("human_key"))[0], "pages": []}
            순서.append(k)
        뭉치[k]["pages"].append(p)
    있는것 = sorted([k for k in 순서 if k], key=_자연순)
    나열 = 있는것 + ([""] if "" in 뭉치 else [])
    return [(뭉치[k]["id"], 이름제안([p.get("name") or "" for p in 뭉치[k]["pages"]]),
             뭉치[k]["pages"]) for k in 나열]


CSS = """
  /* 스토리보드 ID 로 갈라 보이는 뭉치 머리 (page_group) */
  tr.grp td { background:var(--color-bg-subtle); border-top:1px solid var(--color-border-subtle); }
  tr.grp { cursor:default; }
  tr.grp .gid { font-family:ui-monospace,monospace; font-weight:var(--font-weight-bold);
    color:var(--color-text-primary); }
  tr.grp .gname { margin-left:var(--spacing-8); color:var(--color-text-tertiary); }
  tr.grp .gcnt { margin-left:var(--spacing-8); font-size:var(--font-size-12); color:var(--color-text-helper); }
  tr.grp.none .gid { color:var(--color-text-helper); font-family:inherit; font-weight:var(--font-weight-regular); }
"""

JS = """
(function () {
  // 뭉치 머리의 네모 = 그 뭉치 장 전체 고르기 (옮기기·삭제가 읽는 그 네모들)
  Array.prototype.forEach.call(document.querySelectorAll('input.pick-grp'), function (머리) {
    머리.addEventListener('change', function () {
      var 뭉치 = 머리.dataset.grp;
      Array.prototype.forEach.call(
        document.querySelectorAll('input[name=page][data-grp="' + 뭉치 + '"]'),
        function (c) { if (c.checked !== 머리.checked) { c.checked = 머리.checked;
          c.dispatchEvent(new Event('change', { bubbles: true })); } });
    });
  });
})();
"""
