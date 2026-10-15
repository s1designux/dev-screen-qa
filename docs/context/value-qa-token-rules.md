---
name: value-qa-token-rules
description: "조각 ② 토큰·컴포넌트 규정 대조 완료(2026-09-14, main 커밋 a40a77e·cc3b084) — 정본은 그때그때 받아옴, 컴포넌트는 클래스 아닌 시안 인스턴스 정체로, 허용차 없음"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T02:22:55.819Z
---

2026-09-14 `valueqa/registry.py`·`rules.py`·`component_id.py` 를 만들어 `python3 -m valueqa … --정본 auto` 로 회사 규정을 대조한다.
2026-09-14 다른 세션이 트리를 통합하며 main 에 커밋했다(a40a77e, cc3b084). windows 워크트리는 사라졌고 이제 `~/dev-screen-qa` main 한 곳이다.

**Why:** river 가 가장 중요하게 보는 것은 시안 1:1 이 아니라 "회사 토큰·컴포넌트 규정 준수"([[value-qa-token-compliance]]).
정본(`s1designux/S1-UX-DESIGN-with-AI`)은 시시각각 바뀌어 복사 금지 → 검수 때 받아오고 커밋을 지시서 머리에 적는다.
실제 서비스 화면은 `s1-btn` 같은 클래스를 안 쓰므로 컴포넌트 정체는 **시안 피그마 인스턴스**(플러그인 `component` 칸)를 짝 건너 옮겨 알아본다.

**How to apply:**
- 규격의 정본은 `registry/components/component-guide-model.json`(세트 49·변형별 높이/최소너비/칠/선), 세트→id 는 `governance/component-page-coverage.json`.
  `component.tokens.json`·`tokens/legacy/` 는 은퇴 — 읽지 않는다. 어두운 테마 블록은 뺀다.
- 오프라인 자가검사는 `validation-registry/정본-시험용/`(모양만 흉내) 으로 돈다. 진짜 정본 숫자: 색 209·컴포넌트 49.
- 허용차는 없음([[feedback-rules-exact]]). 첫 실전 화면은 **실제 개발된 웹 화면**(river 확정 2026-09-14) — 주소·시안 프레임은 아직 못 받음. 플러그인 인스턴스 정체는 실기 미확인.
- 다음 조각은 ③ 흐름 검수, 포털 붙이기([[pcweb-value-track]]).
