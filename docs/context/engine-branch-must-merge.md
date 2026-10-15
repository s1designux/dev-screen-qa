---
name: engine-branch-must-merge
description: 포털이 돌리는 검수기는 main 의 engine/ui.html — 작업 가지에 규칙을 넣고 합치지 않으면 실제 검수에 안 쓰인다
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-17T03:52:18.604Z
---

포털(`~/dev-screen-qa/mvp0/portal.py`, 8765)은 **그 폴더 main 의 `engine/ui.html`을 매 요청마다 읽는다.**
다른 가지·다른 워크트리(`-일꾼체계` 등)에서 규칙을 넣고 한 바퀴를 다 돌려도, main 에 합치기 전까지
**실제 검수에는 한 줄도 반영되지 않는다.**

2026-09-17 river 가 "전에 보완했던 게 반영이 안 된 채로 검수된다"고 한 원인이 이것이었다.
P21(항목 이름 고정)·P22(입력칸 지우기 단추)가 `feat/worker-structure` 에서 반영됨 상태였는데
포털은 그것이 없는 main 엔진을 돌리고 있었다.

**How to apply:** 규칙 한 바퀴를 마쳤으면 **main 에 합치는 것까지가 끝이다.**
합친 판은 양쪽 조각이 처음 만나는 새 조합이므로 **다시 재고**(공식측정) 양면·문지기를 다시 통과시킨다.
river 가 "규칙이 반영 안 된 것 같다"고 하면 먼저 `git log main..<가지> -- engine/ui.html` 로 안 합쳐진 규칙부터 본다.

관련: [[qa-regression-harness]] · [[worker-structure-plan]] · [[portal-only-inspection]]
