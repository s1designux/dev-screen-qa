---
name: worktrees-unified
description: 작업 폴더는 ~/dev-screen-qa 한 곳(2026-09-14 통합). 예외 둘 — -디자인가이드, -일꾼체계(2026-09-16 river 지시)
metadata:
  type: project
---

2026-09-14, 작업 사본 5개(-capture / -color / -windows / -policy / -site)를 모두 main에 합치고 폴더를 지웠다. 이제 코드는 `~/dev-screen-qa` 한 곳뿐이다. 깃허브 main에도 올렸다.

버린 것 하나: `codex/inspection-policy`(2026-09-09, 'unify design-led inspection preparation and capture') — main이 그 뒤 없앤 '촬영 절차' 화면을 되살리는 내용이라 합치지 않고 가지를 지웠다.

**Why:** river님은 두 가지를 나란히 돌려 견주지 않고 실험도 결국 main으로 간다. 사본이 여럿이면 "고쳤는데 왜 그대로냐"(피그마가 옆 폴더 플러그인을 보고 있던 일)가 반복된다.

**How to apply:** 새 작업에 워크트리를 새로 만들지 않는다. `~/dev-screen-qa`에서 바로 한다. 관련: [[portal-single-instance]], [[pcweb-value-track]].

**예외 (2026-09-16, river 지시):** 일꾼 체계(하네스) 작업은 일이 크고 다른 세션 커밋을 막지 않도록 `~/dev-screen-qa-일꾼체계`(브랜치 `feat/worker-structure`)에서 따로 한다. 그 전에 `-디자인가이드`(feat/design-guide)도 하나 더 있다. 브랜치를 본 폴더에서 체크아웃하면 다른 세션 커밋이 그 브랜치로 흘러간다(실제로 342517c가 그렇게 됐다 → main으로 옮김). **본 폴더는 항상 main에 둔다.** 계획: [[worker-structure-plan]].
