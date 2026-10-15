---
name: worktree-stash-incident
description: "데스크톱 앱이 작업 중 파일을 stash(\"epitaxy: pre-switch\")로 치워 버린 일과 복구법 — 다른 세션이 같은 폴더를 함께 편집함"
metadata: 
  node_type: memory
  type: feedback
  modified: 2026-09-10T04:27:16.924Z
---

2026-09-10 dev-screen-qa-site 작업 중, 내가 만든 미추적 파일 4개와 수정본이 갑자기 사라짐.
원인: 데스크톱 앱이 `git stash -u`("On feat/qa-portal: epitaxy: pre-switch from feat/qa-portal")로 치움. 브랜치는 그대로였고,
그 뒤 **다른 세션**이 같은 폴더의 `mvp0/portal.py`를 별건(붙여넣기 업로드)으로 고치고 있었다.

**Why:** 같은 체크아웃을 여러 세션이 쓰면 앱이 전환 전에 작업을 stash한다. pop 하면 남의 변경을 덮을 수 있다.
**How to apply:** ① 파일이 사라지면 먼저 `git stash list --format='%H %ci %gs'` ② 미추적 파일은 `git show <sha>^3:<path> > <path>`,
추적 변경은 `git diff <sha>^1 <sha> -- <path> | git apply`(pop 금지) ③ 남의 변경이 같은 파일에 있으면 내 hunk만 따로 커밋
④ 작업 중간에 scratchpad로 patch/tgz 백업을 남긴다. 커밋 전 `git diff`에 내 것 아닌 hunk가 섞였는지 확인.

관련: [[portal-auto-inspect]]
