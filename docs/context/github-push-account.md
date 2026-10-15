---
name: github-push-account
description: "깃허브에 올릴 때 쓰는 계정은 s1designux — riverbae 는 읽기만 되고, 내장 터미널은 타이핑이 막혀 있다"
metadata:
  node_type: memory
  type: reference
  modified: 2026-09-23T03:01:31.109Z
---

저장소 `s1designux/dev-screen-qa` 에 **올리려면 `s1designux` 계정**이어야 한다.
`riverbae` 로는 읽기만 된다(2026-09-23 확인: push false).

**내장 터미널 칸에는 글자를 칠 수 없다.** 그래서 `gh auth login` 처럼 되묻는 명령이
`(Y/n)` 에서 그대로 멈춰 선다. river 님께 "터미널에 Y 치세요" 라고 하면 안 된다.

**되는 길 — 되묻지 않게 만들고 코드만 건넨다:**

```
gh config set git_protocol https
gh auth login --hostname github.com --git-protocol https --web </dev/null
```

`</dev/null` 이 핵심이다. 되묻기를 건너뛰고 **여덟 자리 코드**와
`https://github.com/login/device` 를 바로 내놓는다.
그 주소를 크롬으로 열어 드리고 코드만 전해 드리면 된다 — river 님은 붙여넣기만 한다.

로그인 뒤에는 `gh auth setup-git --hostname github.com` 을 한 번 돌려야 git 이 그 계정을 쓴다.

안 되는 길(2026-09-23 다 해 봄): 내장 터미널에 직접 치기 · `echo Y |` 로 밀어넣기 ·
`script` 로 가짜 터미널 만들기 · 맥 터미널 앱을 열어 드리기. SSH 열쇠는 이 맥에 없다.

관련: [[feedback-tools-i-run]] · [[feedback-open-in-chrome]]
