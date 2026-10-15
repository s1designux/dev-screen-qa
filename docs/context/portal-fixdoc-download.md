---
name: portal-fixdoc-download
description: 수정요청서를 포털 검수 페이지 목록 맨 위 주의 카드에서 내려받는다 — 촬영기가 접수 때 개발 값도 함께 넣어야 생긴다
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T06:51:35.891Z
---

2026-09-14 완성한 길: **촬영 → 접수 → 포털에서 수정요청서 내려받기.**

- 촬영 사이트는 **'검수로 보낸 후 포털 열기'** 단추 하나다(보내기와 포털 열기를 합쳤다).
  새 창은 누른 그 순간 열어 두고 접수가 끝나면 그 창을 포털로 보낸다 — 안 그러면 팝업 막기에 걸린다.
- 접수(`capture-app/site/intake.py`)가 그림 옆에 두 개를 같이 넣는다:
  `uploads/{page}_design.json`(시안 값, **틀 포함**) · `uploads/{page}_dev값.json`(개발 화면에서 잰 값).
  **둘 다 있어야** 포털이 대조한다 — 예전에 보낸 화면·앱 촬영본은 값이 없어 카드가 안 뜬다.
- 포털 `/screen/<키>` 맨 위에 **'⚠ 개발화면 검수 전 적용해주세요'** 카드(`mvp0/fixdoc_http.py`),
  `/screen/<키>/수정요청.md` 로 내려받는다. 한글 주소라 라우팅에서 `unquote` 로 풀어 견준다.
- **카드의 숫자와 문서의 '모두' 칸은 같은 셈**(`valueqa.fixdoc.셈만`)을 쓴다. 어긋나면 문서를 못 믿는다.
- 회사 규정 정본은 10분쯤 받아 둔 것을 쓴다(화면 열 때마다 깃허브를 두드릴 수 없다).
  못 받으면 규정 대조 없이 값 대조만으로 낸다 — 폐쇄망 대비.

**Why:** 값 대조도 문서도 다 됐는데 **받을 길이 없어** 손으로 명령을 쳐야만 나오고 있었다.

**How to apply:** 코드를 고치면 포털·촬영 사이트를 껐다 켜야 보인다
(촬영 사이트는 `capture-app/다시켜기.sh`, 포털은 `mvp0/portal.py` 를 다시 띄운다).
관련: [[fixdoc-rules]] [[portal-single-instance]] [[capture-site-rules]]
