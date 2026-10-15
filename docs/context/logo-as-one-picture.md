---
name: logo-as-one-picture
description: 로고·이미지 컴포넌트 안의 글자는 글자로 보지 않고 그림 한 덩어리로 크기·자리만 본다 (공통 규칙)
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-14T07:43:59.495Z
---

2026-09-14 river 확정(모든 서비스 공통). 엔진 `engine/ui.html` 의 **그림표(POLICY_IMAGE_RULES)** 에 들어 있다.
이름이 IMG·LOGO·로고·wordmark·BI·CI·symbol 을 가리키고, 안에 그림 요소가 있고, 글자는 곁들임뿐인
(2개 이하·24자 이하) 작은 덩어리(높이 160px 이하·프레임 15% 이하)를 **비교 단위 하나(icon)** 로 묶는다.

**Why:** 로고 안 글자를 글자로 비교하면 글꼴·굵기·줄높이 같은 쓸모없는 값이 카드에 오르고,
정작 "로고가 통째로 8% 크다"는 못 짚었다(실제 우비스 로그인 화면: 시안 167px → 개발 181px).

**How to apply:** 크기(잉크 가로폭)는 **로고 덩어리에서만** 잰다 — 작은 아이콘까지 재면 잉크 넓히기가
옆 요소를 물어 10화면에서 볼 것이 +35건 늘었다(실측). 문턱은 8%·3px. 양쪽 다 `growInkBox` 로 재야
한쪽만 커 보이지 않는다. 회귀 기준선(2026-09-14 HEAD): 10화면 볼 것 302 · 체류시간 정답 6/7 ·
자체검사 214. 돌리는 법은 `validation-image-qa/repro/열개.sh` + `세기.js`, 실제 화면 재현은
`elements_portal_login.json`. [[image-qa-policy-rules]] [[card-body-rules]] [[policy-layers]]
