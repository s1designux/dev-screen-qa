---
name: portal-value-candidates
description: "값 대조 결과가 포털 페이지 상세에 후보로 뜬다 — auto_run.source로 그림 검수와 갈라 둠, 제외하면 수정요청서에서도 빠짐"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T07:04:17.732Z
---

2026-09-14: 값 대조(`valueqa/`)가 수정요청서(문서)로만 나가던 것을 포털 데이터로 쌓았다.
`mvp0/value_candidates.py` 가 `uploads/{page}_design.json` + `{page}_dev값.json` 을 재서
`auto_candidate` 에 넣고, 페이지 상세 '수정필요' 칸에 그림 검수 후보와 **한 목록**으로 보인다(카드에 `값 대조` 이름표).

- 두 검수는 `auto_run.source` ('engine' / 'value') 로 가른다. 옛 DB는 `auto_inspect.repair()` 가 칸을 더한다.
- 값은 **마지막 차수**의 개발 화면을 잰 것이라 옛 차수에는 안 붙인다. 자료 지문이 바뀌면 새 회차로 다시 재되 사람 판정은 이어받는다.
- 사람이 '제외'로 내리면 수정요청서에서도 빠진다(문서는 데이터를 읽는 출력물 — [[value-qa-token-rules]], [[portal-fixdoc-download]]).
- 판정은 `rule_verdict` 에 규칙 이름 `value` 로 쌓인다. 요소 층 정책으로는 쌓지 않는다(그림 검수 규칙이 아니다 — [[policy-layers]]).
- 확인: 삼성통근버스 로그인 6쪽에서 쪽당 5~7건, 문서 숫자 13 → 제외 3건 반영 후 12.

**Why:** 검수 결과는 데이터가 원본이어야 하는데(CLAUDE.md 2번-1) 값 대조만 문서로 흘러나가 판정이 남지 않았다.
**How to apply:** 값 대조 쪽 화면·문서를 고칠 때는 `mvp0/value_candidates.py` 의 `키()` 가 판정을 잇는 축이라는 것을 먼저 본다.
