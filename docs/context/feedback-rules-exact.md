---
name: feedback-rules-exact
description: 규정(토큰·컴포넌트) 대조는 허용차 없이 정확히 같아야 한다 — 1~2 차이도 위반 (river 확정 2026-09-14)
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-09-14T03:31:57.338Z
---

토큰·컴포넌트 규정 대조에서 "1~2 차이는 넘기자"는 선택지를 두지 않는다. 무조건 정확히 같아야 한다.

**Why:** river — "그대로 지켜야만 하는 디자인 규칙이 단순히 1~2 틀렸다고 넘어가면 그게 규정일까? 무조건 다 맞아야 해."
차이 크기로 신뢰도를 낮추는 것도 같은 이유로 하지 않는다.

**How to apply:** `valueqa/rules.py` 에 허용차 옵션 없음(CLI `--허용차` 삭제). 앞으로 규정 관련 검사를 만들 때
"거의 맞으면 통과" 식의 문턱을 제안하지 않는다. 시안↔개발 값 대조(①)의 허용치(compare.py)는 별개 — 그건 측정 오차용이다. [[value-qa-token-rules]]
