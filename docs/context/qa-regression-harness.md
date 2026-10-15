---
name: qa-regression-harness
description: 검수기 회귀 재는 법 — 잰다.sh 화면 15개, 실패한 화면은 그때마다 목록에 더한다
metadata:
  type: project
---

검수기(`engine/ui.html`) 규칙을 고치면 `validation-image-qa/repro/잰다.sh <이름>` 으로 **화면 15개**를 다시 재고
`node 열넷세기.js <새> <옛>` 으로 견준다. 체류시간 정답은 `node answers_check.js <이름>_stay.json` (7/7 유지),
자체검사는 `./selftest.sh` (222 통과).

**실패한 화면은 그때마다 목록에 더한다.** 이것이 같은 문제가 되돌아오는 걸 막는 가장 확실한 방법이다.
2026-09-16 에 앱 로그인(키보드 열린 화면)을 `appkbd` 로 더해 14 → 15개가 됐다.

포털 자료로 바로 재려면 `elements_*.json` 에 `native` 배열(포털 `design_elements.elements` 그대로)을 넣으면 된다 —
`run.js` 가 cols/rows 대신 그걸 쓴다. 시안·개발 PNG 는 `mvp0/uploads` 에서 가져온다.

**예전 숫자는 믿지 말 것:** 2026-09-15 이전 10화면 숫자는 정렬을 끈 채 잰 값이다(302→316 · 6/7→7/7).
기준선은 그때그때 지금 엔진으로 다시 재서 잡는다.

[[band-alignment]] [[align-vertical-rescue]]
