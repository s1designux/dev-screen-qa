---
name: canon-parts-everywhere
description: 모든 포털 화면을 정본 s1-ui 부품으로 갈아입힘 · 뼈대는 mvp0/s1.py 한 곳 · 점검은 scripts/부품점검.py
metadata:
  type: project
---

2026-09-29 — 포털 화면 15개를 전부 **정본 부품**으로 갈아입혔다. 손으로 옮겨 적은 사본
(`s1_components.CSS` · `s1_tokens.링크()`)은 걷었고, 부르는 곳이 없어 이력으로만 남는다.

- **뼈대를 짓는 곳은 `mvp0/s1.py` 한 곳.** 화면은 `s1.단추/입력/고르개/표/칩/탭/대화창` 을 불러 쓴다.
- **동작(JS)도 정본 것.** `부품받기.sh` 가 `mvp0/assets/js/s1/` 로 28장을 받아 오고,
  화면은 `s1_tokens.동작()` 한 줄. 정본이 안 하는 둘(고른 값 폼에 싣기 · 창 여는 단추)만
  `assets/js/s1-form.js` 가 잇는다.
- **점검기 `scripts/부품점검.py`** — 정본 명세를 그때그때 읽어 일곱 가지를 본다.
  `DESIGN_SYSTEM_GAP` 을 적어 둔 자리는 위반이 아니라 '적어 둔 빈자리'로 따로 센다.
- 숫자: 정본 밖 160 → 0곳. 받아 둔 판 0.8.1 → 0.13.14.

**Why:** 토큰만 맞추면 색은 맞는데 모양은 여전히 포털 모양이다 — 점검기가 값만 보고 부품을 못 봤다.

**How to apply:** 새 화면을 만들거나 고치면 `python3 scripts/부품점검.py` 로 0을 확인한다.
정본에 없는 크기 이름(`sm` 등)을 쓰면 옷을 안 입는다 — 명세에 있는 이름만 쓴다.
[[s1-design-skill]] [[portal-gnb-and-s1-parts]] [[portal-project-workspace]]
