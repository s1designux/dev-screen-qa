---
name: image-qa-policy-rules
description: "검수 정책 규칙화 조각 — 2026-09-09 마무리(볼 것 647→329·정답 7/7). 남은 것은 #1·#2 보류와 다음 대기열"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-09T01:29:59.160Z
---

2026-09-09 기준 (`validation-image-qa/repro/RULE_PROPOSALS.md` 가 원본).

**이 조각은 끝났다.** CLAUDE.md 21번 0번 항목의 세 가지가 모두 채워졌다:
① 규칙이 `plugin-image-qa/ui.html`의 «검수 정책표» 한 곳에 모임(제외표·가변표·목록규칙)
② 기본 규칙 4줄이 표 안에 있음 — 표 컬럼 제목 고정 / 메뉴·탭 이름 고정 / 표 본문 값 가변 / 가짜 브라우저 틀·작업표시줄 제외
③ 체류시간 정답 생존으로 매 단계 검증

**줄어든 자취(화면 10개 '볼 것'):** 647 → 529(#9·#10) → 440(#5·#8) → 428(#12) → 423(#13) → 331(#14·#15) → **329(#16)**.
정답은 **7건**(`answers_stay.json`), 자체 검사 **188개**.

**마지막 조각 #16 (커밋 a970cf2):** 선택된 탭을 탭 줄 안에서 가로로 넓게 찾아 글자만 대조.
그 전에는 탭을 못 찾아 '없어짐'으로 올렸고, 노선관리의 진짜 오류(「노선관리」↔「노선 관리」)가 묻혀 있었다.

**아직 열려 있는 것:** #1(표 항목 이름 고정) 보류 — 근거 화면 부족. #2(띄어쓰기) 관찰만, AI 읽기는 못 믿는다. #6·#7·#11은 거절/실패로 닫힘.

**재기 도구:** `./selftest.sh` · `./measure_all.sh <ui.html> <접두사>` · `node count.js <새> <기준>` ·
`node answers_check.js <접두사>_stay.json` · `node tab_report.js <출력.html>`.
재기는 한 번에 한 세션만(`MEASURING.lock`). 회사 화면 자료·산출물은 커밋하지 않는다.

관련: [[image-qa-variable-text]] [[image-qa-range-chrome]] [[local-ai-decision]] [[dev-screen-qa-validation]]
