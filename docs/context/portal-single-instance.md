---
name: portal-single-instance
description: 검수 포털은 ~/dev-screen-qa 8765 한 곳만 쓴다. 사본 클론(8799)은 2026-09-10 폐기
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-10T08:19:15.023Z
---

검수 포털은 **`~/dev-screen-qa` 한 곳**에서만 돈다 (http://127.0.0.1:8765).
켤 때는 `cd ~/dev-screen-qa/mvp0 && python3 run_portal.py` — run_portal.py는 mvp0 안의
.py/.js/.sql이 바뀌면 스스로 껐다 켜므로, 파이썬을 고친 뒤 따로 재시작할 필요가 없다.

2026-09-10: 같은 저장소를 한 번 더 받아 둔 `~/dev-screen-qa-site`가 8799에서 같이 돌고
있었다. 검수 DB가 0바이트(빈 파일)이고 사진도 2장뿐이라 실제 자료는 없었다.
서버를 끄고 폴더를 `dev-screen-qa-site-사용안함`으로 바꿨다(지우지 않음).
그 안에 `사용안함.md`와 손대다 만 변경을 담은 `손대던_변경_보관.patch`가 있다.

**Why:** 포털이 두 벌 떠 있으면 어느 쪽에 반영됐는지 헷갈리고, 빈 DB 쪽을 보고
"자료가 사라졌다"고 오해하기 쉽다.

**How to apply:** "사이트에 반영"은 8765를 뜻한다. 포털이 여럿 떠 있으면 DB 크기부터
확인해 실제본을 가린다. 관련: [[demo-report-portal]](8766 데모본은 별개로 유지),
[[portal-auto-inspect]].
