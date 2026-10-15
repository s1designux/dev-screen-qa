---
name: portal-gnb-and-s1-parts
description: 포털 맨 위 메뉴 줄(GNB)과 S-1 정본 부품 쓰는 법 — 아이콘·GNB CSS 낱장·Select 동작
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-22T07:31:24.874Z
---

2026-09-22. river 지시: **포털 화면은 디자인가이드 컴포넌트와 토큰만** 쓴다.

**맨 위 메뉴 줄** — `mvp0/gnb.py`. 과제 · 가져온 기록 · 검수 규칙 · 촬영 준비.
size `sm`, 정렬은 정본 기본값 center-between(3분할)이라 메뉴가 **가운데**에 선다 —
오른쪽 유틸 자리를 빈 `<span data-s1-part="util">` 로 두어야 가운데가 잡힌다.
촬영 준비는 아직 다른 포트(8767)라 새 창. 반출 문서(검수결과서·수정요청서)에는 넣지 않는다.

**첫 화면에 헤더가 없다** (river 2026-09-22). 메뉴 줄 → 상태 칩 → 카드.
'과제 만들기'는 단추가 아니라 **맨 앞 점선 카드**다.

**걸려 넘어진 것 셋 — 다시 만나면 여기부터 본다:**
1. **아이콘이 안 나온다.** 부품 CSS 가 `mask:url("./assets/icons/…")` 로 부르는데
   `부품받기.sh` 가 CSS 만 받아 왔다. 이제 아이콘 24장도 함께 받는다.
   CSS 자리 기준이라 실제 요청 주소는 `/assets/css/assets/icons/…` 다(포털 라우트도 그렇게).
2. **옛 화면에 s1-ui.css 를 통째로 이으면 안 된다.** 가져온 기록·검수 규칙은
   손으로 옮겨 적은 `s1_components.CSS`(`s1_tokens.링크()`)를 쓴다 — 통째로 이으면 단추·표까지 바뀐다.
   그래서 `부품받기.sh` 가 GNB 칸만 잘라 `s1-gnb.css` 로 두고 `gnb.바()` 가 그 한 장만 잇는다.
3. **Select 는 JS 가 있어야 한다.** `mvp0/assets/js/s1-select.js` — 가이드에
   `status: verified` 로 적힌 것만 옮겼다. 고른 값은 같은 상자의 hidden 에 담겨 폼으로 간다.

**점검은 두 개를 돌린다:** `python3 ~/.claude/skills/s1-design/scripts/토큰점검.py <파일…>` ·
`python3 scripts/글점검.py`. 토큰은 있는 것만 쓴다 — `--sizing-160` 은 없다(128 다음이 없음).

**포털을 고친 뒤에는 꼭 다시 켠다.** `run_portal.py` 감시기가 멈춰 있는 때가 있어
옛 코드가 계속 뜬다. `pkill -f run_portal.py` 뒤 다시 켜고 화면으로 확인한다.

관련: [[portal-v3-project-first]] · [[s1-design-skill]] · [[ui-writing-rules]]
