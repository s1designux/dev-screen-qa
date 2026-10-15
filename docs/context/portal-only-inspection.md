---
name: portal-only-inspection
description: 2026-09-14 river 확정 — 피그마 검수기 플러그인 폐기, 검수는 포털에서만. 엔진은 engine/ui.html로 이사
metadata:
  type: project
---

river 확정(2026-09-14): **앞으로 검수는 포털에서만 한다.** 피그마 「개발화면 검수기」 플러그인 창은 쓰지 않는다.
룰 세팅 자동화도 실제 검수도 포털 한 곳에서.

폐기한 것은 **창**이지 **엔진**이 아니다. 비교 엔진 한 벌은 `plugin-image-qa/ui.html` → **`engine/ui.html`** 로 옮겼고
포털이 예전처럼 `/engine/ui.html`로 내보내 돌린다. 플러그인으로 띄우는 데 필요했던 것(manifest.json·code.js·README·test.js)은
`legacy/plugin-image-qa/`로 옮겼다 — 현재 작업에서 부르거나 읽지 않는다. `npm run test:image` → `test:image:legacy`로 이름 바뀜.
`mvp0/policy_api.py`(검수기↔포털 규칙 배선)는 부르는 쪽이 없어져 사용 안 함(파일은 유지).

**시안 통로는 플러그인 유지** — 촬영 준비 플러그인(프레임 골라 포털로 보내기)은 검수기가 아니라 배달부라 계속 쓴다.

`engine/ui.html` 안에는 아직 그 시절 플러그인 화면 코드(번호 패널·판정 단추)가 남아 있다. 포털은 안 쓴다.
걷어내는 건 나중 정리 조각 — 지금 건드리면 규칙까지 흔들린다.

검증: 자체검사 209 통과, 화면 10개 회귀 316·정답 7/7(이사 전과 동일), 레거시 플러그인 검사도 그대로 통과.

**Why:** 대기열 1번(플러그인 1.0 나머지)은 폐기됐다. 관련 [[rule-verdict-log]] · [[policy-layers]] · [[portal-auto-inspect]].
