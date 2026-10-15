---
name: app-capture-rules
description: 앱 촬영본 기본 규칙(상태바·키보드·하단바 제외) + 포털 검수 범위 조정 조각(2026-09-10) — 원인·구조·검증·남은 것
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-10T07:15:51.797Z
---

2026-09-10 river 지시: "앱 화면 기본 규칙으로 만들고 포털에 검수 범위 조정도 넣어줘". 커밋 전(스테이징만).

**증상(우비스 버스 로그인, 시안 360×812 ↔ 촬영본 1080×2340):** 촬영본 상태바가 '디자인에 없는 요소', 키보드 자판이 전부 지적,
빈 곳에 '누락'. 규칙이 빠진 게 아니라 **앱 화면에서 정렬이 틀어진 것**(포털은 `plugin-image-qa/ui.html` 한 벌을 그대로 씀).

**엔진(ui.html) 바뀐 것:**
- 검수 정책표에 **촬영본 제외표 `CAPTURE_EXCLUDE_RULES`**(세로가 긴 캡처만): statusBar(맨 위 첫 잉크 덩어리, 8% 안) /
  keyboard(바닥부터 같은 회색 바탕 줄이 7% 안쪽 간격으로 이어져 25~60%) / navBar(맨 아래 잉크 덩어리, 위가 20줄 이상 비어야).
  `captureRowProfile`(줄마다 최빈색·잉크). 사람이 정한 범위가 있으면 규칙보다 우선. 정렬이 믿을 만하면(m0 score≥.85) 주소창까지 더 자름.
- 잘라낸 아래쪽에 해당하는 시안 요소는 비교하지 않음(면적 비교 칸도 건너뜀) + 개수 안내.
- 정렬: 표가 엇비슷한 무리가 여럿이면(`clear`가 아니면) `scoreModel`로 그림 전체 윤곽을 재서 고름. 한 표짜리는 '그대로 겹치기'보다 못하면 버림.
  기준 요소는 칸의 대표(가장 큰 것)가 짝을 못 찾을 때만 같은 칸의 글자로 재시도(`alts`) — 글자 우선으로 바꾸면 체류시간 정답 6/7로 깨짐.
- 1차 비교를 건너뛸 때 이름으로 분명한 틀 띠(`namedFrameBoxes`)를 기준 요소에서 뺌(상태바 '12:30'이 기준이 되던 것).

**포털(auto_inspect.py):** `auto_range`(append-only) / `auto_run` 유일 제약 제거(같은 차수·시안에 여러 회차, `run_for`는 최신) /
`set_range` → 새 회차 pending / `materials`가 topTrim·bottomTrim 전달 / '검수 범위' 카드 + 조정 편집기(선 끌기, 숫자, 담당자) /
`POST /auto/<page>/range`. **`repair(db)`** — 외래키 끈 별도 연결에서 옛 표 모양(auto_run_v0/v1 잔재, auto_candidate 참조 틀어짐)을 고침.
실제 DB는 자동 재시작된 포털이 이미 고쳤음(백업 `mvp0-real.db.bak-범위조정전-20260910-1610`).

**검증:** 자체검사 193 / 웹 10개 회귀(`regb`→`regn3`, 체류시간 7/7, login 헛지적 -1, vehicle -2, dash ±1, door 정답 없음·요동) /
스크래치 재현 `scratchpad/app_repro.py`(실제 DB 읽기만, 헤드리스 크롬) 4쪽 / 스크래치 포털 8778에서 조정→재검수→카드 '직접 정함' 확인.
**미확인:** 브라우저 콘솔에 `ERR_EMPTY_RESPONSE`(결과 저장은 됨, 새로고침과 겹친 요청으로 보임) / 다른 기기·iOS 촬영본 / 회색 바닥 시트가 키보드로 잡힐 가능성.

**주의:** 같은 시각 다른 세션("검수 화면 불필요한 내용")이 auto_inspect.py에서 주황 안내 목록(auto-notice)을 뺐다 — 되살리지 말 것.
관련: [[portal-auto-inspect]] [[image-qa-policy-rules]] [[worktree-stash-incident]]
