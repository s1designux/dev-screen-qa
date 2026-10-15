---
name: s1-design-skill
description: 디자인가이드로 화면 만들고 고치는 한 벌(s1-design) — 모든 폴더 공용, 값은 안 베끼고 쓸 때마다 받아 읽음
metadata:
  type: project
---

2026-09-14: 화면을 만들거나 고칠 때 S-1 디자인가이드를 자동으로 적용하는 한 벌을 `~/.claude/skills/s1-design/` 에 뒀다(모든 작업 폴더 공용).
가이드 정본은 `s1designux/S-1-UX-DESIGN-AI-GUIDELINE`(PC 범위, 원본에서 매일 자동 동기화).

**Why:** river 확정 — 디자인가이드는 **고정 정보가 아니다.** 그래서 토큰 값을 문서·코드·기억에 베껴 두지 않고,
`scripts/가이드받기.sh` 로 쓸 때마다 받아 `~/.claude/s1-design-guide` 에서 그 자리에서 읽는다(막히면 받아 둔 판으로 가고 그렇다고 알림).

**How to apply:** 화면 작업 전 가이드받기 → 쓸 컴포넌트의 `design/DESIGN.core.md` §4 절 통째로 읽기 → 토큰만 쓰기 →
끝나면 `scripts/토큰점검.py <파일·폴더>` 로 0 만들기. 토큰 이름은 tokens·component-tokens·typography·**site-base** 네 파일에 흩어져 있다(site-base 를 빼면 없는 토큰으로 잘못 잡힌다).
남의 화면을 그린 삽화·붙여 온 원본은 `s1-제외 시작 … s1-제외 끝` 으로 빼 둔다 — 사진을 가이드 색으로 칠하지 않는 것과 같다.
첫 적용: 촬영 준비 사이트(`capture-app/site/server.py`), 워크트리 `dev-screen-qa-디자인가이드`(feat/design-guide). [[capture-site-rules]] [[value-qa-token-rules]]
