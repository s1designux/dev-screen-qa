---
name: portal-prewarm-and-engine-speed
description: "촬영→포털 기다림의 원인은 접수가 아니라 페이지 열 때 도는 검수기, 속도 조각 3곳 + 미리 검수"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-17T03:51:35.726Z
---

2026-09-17. "촬영 후 포털로 보내는 시간이 느리다"의 실제 원인: 접수(intake.py)는 0.04초이고,
기다림은 **포털에서 페이지를 처음 열 때 도는 검수기**였다. PC 웹 넓은 화면 13~17초, 앱 1~3초.

고친 것 둘:
1. `engine/ui.html` 속도 조각 세 군데 — `edgeMask3`(윤곽 3×3 확인을 한 장으로) · `pointIndex`(점 자리표) ·
   `blurLumMap`(흐린 밝기 한 번만). 판정 무변화: 화면 15개 후보·정렬 동일, 자체검사 통과.
   홈 17.0→3.3초 · 게시판 13.0→1.6초 · 체류시간 4.4→1.0초.
2. 포털 '미리 검수'(`mvp0/auto_inspect.py` PREWARM_JS·pending_pages, `mvp0/portal.py`) —
   페이지 목록을 열어 두면 결과 없는 장을 한 장씩 미리 돌리고, 페이지 상세에서는 **다음 한 장만** 미리 돌린다.
   GET `/auto/screen/<화면uuid>/pending` 은 읽기만 한다(회차는 materials POST 가 만든다).

배운 것: **엔진 파일(engine/ui.html)이 바뀌면 engine_rev 가 달라져 기존 결과가 전부 다시 돈다.**
속도만 고쳐도 그렇다 — 미리 검수가 그 재계산을 대신 받아 준다.

같은 날 `dev-screen-qa-cf` 세션이 같은 파일을 동시에 고치고 있었다 — [[worktree-stash-incident]] 와 같은 종류의 일.
공용 파일에는 `git checkout` 을 쓰지 않고, 현재 내용 위에 조각만 다시 얹는다. 관련: [[qa-regression-harness]] · [[portal-auto-inspect]]
