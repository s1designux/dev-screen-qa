---
name: rule-doc-sync-tool
description: 검수 규칙 문서가 코드와 어긋났는지 재는 도구 — scripts/규칙뽑기.py, 내가 돌린다
metadata:
  type: project
---

검수 규칙의 원본은 코드(`engine/ui.html` 의 정책표들 · `valueqa/compare.py` 허용치 · `valueqa/rules.py` 규정 3갈래)이고,
`docs/검수규칙-한눈에.html` 은 사람이 읽는 **손으로 적은 사본**이다. 사본이 자동으로 따라가지 않아 2026-09-10~15 닷새 뒤처졌었다.
2026-09-15 `scripts/규칙뽑기.py` 를 만들어 둘을 맞댄다 — 빠진 규칙 · 없어진 규칙 · 달라진 허용치 숫자 · 바뀐 규칙 문구(문서 줄의 `data-판` 지문).
문서는 도구가 혼자 고쳐 쓰지 않는다(`--넣기` 는 '확인 필요' 딱지를 붙여 꽂기만 함).

**Why:** 규칙이 코드에만 있으면 river님이 볼 수 없고, 사본이 낡으면 문서를 믿을 수 없게 된다.

**How to apply:** 규칙을 고친 뒤 이 도구를 **내가** 돌려 문서까지 같이 맞춘다([[feedback-tools-i-run]]).
회귀 숫자 재기는 별개다([[qa-regression-harness]]). 규칙 제안·승인 이력은 `validation-image-qa/repro/RULE_PROPOSALS.md` 에 남긴다([[policy-layers]]).
