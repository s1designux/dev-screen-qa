---
name: capture-medium-table
description: "촬영기 매체 유형표(capture-app/lib/매체.py) — 유형별 차이를 값으로 모으고 겪은일을 쌓는다, 단발 수정 금지 (river 결정 2026-09-14)"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T05:03:26.207Z
---

2026-09-14 `capture-app/lib/매체.py` 를 만들었다(커밋 5cd4b59). PC 웹·모바일 웹·앱·PC S/W 마다
견주는법(값/그림)·주소 끝 빗금·자리(%) 허용·한 글자씩 입력·꺼진 단추 기다릴 초를 **값으로** 두고,
`webshot.py`·`site/동작규칙.py`·`site/server.py` 가 그 표를 읽는다. 사람이 읽는 장은 `capture-app/규칙.md` 1-2.

**Why:** river — "단발성으로 수정하기보다 각 매체 유형에 따른 특징·가이드를 축적해 나가자".
첫 실전(유비스사용자포털 〔따로 보관: 서비스주소-1〕)에서 네 번 데였고, 그 넷이 표의 첫 `겪은일` 줄이 됐다.

**How to apply:**
- 새로 데이면 그 유형의 `겪은일` 에 한 줄(언제·무슨 일·그래서) 적고, 값으로 표현되면 위 칸을 고친다. 지우지 않는다.
- 웹 전용 동작 말 `탭칸끝 <칸 안내글>` = 그 칸에 겹친 작은 단추 중 이름표가 보기·눈인 것을 누름. 앱의 `탭좌표`는 웹에서 거부된다.
- 동작 말 목록은 `actions.웹말` 한 곳 — 검사(`actions.확인(글, 유형)`)와 실행(`webshot`)이 같은 목록을 봐야 한다(갈라져서 데였다).
- 이름표 yaml 에 `유형:` 이 들어간다(옛 것은 `플랫폼:` 만 있어 `_갈래()` 가 물러난다).
- 관련: [[capture-site-rules]] · [[pcweb-value-track]] · [[value-qa-token-rules]]
