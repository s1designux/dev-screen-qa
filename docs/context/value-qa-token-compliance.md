---
name: value-qa-token-compliance
description: 값 대조 검수에서 river가 가장 중요하게 보는 것 — 회사 토큰·컴포넌트 규정 준수와 화면 패턴(간격·폰트) 일관성
metadata:
  type: project
---

값 대조(웹) 검수의 1순위는 "시안 그림과 같나"가 아니라 **회사가 정한 디자인 토큰값과 컴포넌트 규정을 그대로 지켰는지**, 그리고 컴포넌트로 짜인 **화면 패턴의 간격·폰트가 동일하게 적용됐는지**다 (river 2026-09-14).

**Why:** 시안과 픽셀이 같아도 토큰 밖의 색·간격이면 규정 위반이고, 반대로 시안 자체가 규정을 벗어났을 수도 있다. 즉 1:1 화면 대조만으로는 부족하고 '규정'이라는 제3의 기준이 필요하다.

**How to apply:** 값 대조 조각([[pcweb-value-track]])을 3층으로 본다 — ①시안↔개발 1:1 대조 ②토큰·컴포넌트 규정 준수 ③화면 간 패턴 일관성. 이를 위해 토큰표·컴포넌트 규정을 데이터 한 벌로 받아 둬야 한다(출처 미정). 규칙 값은 포털 DB에 두는 [[policy-layers]] 원칙을 따른다.

**정본 출처 (river 2026-09-14):** `https://github.com/s1designux/S1-UX-DESIGN-with-AI` — public. 기계가 읽을 수 있는 `registry/`(tokens/*.json · components/*.json · governance/*.json · patterns/{id}/flow.md) + `assets/css/tokens.css`가 정본. **아직 정리 중이라 시시각각 바뀐다 → 복사해 두지 말고 매번 받아오되 본 판(커밋)을 기록한다.**

**화면 간 일관성(③)은 뺀다** — 시안 대조가 되면 저절로 정리되므로 river가 제외했다.

**흐름 검수도 하고 싶다(river 2026-09-14):** 어떤 버튼을 누르면 어느 화면이 나오는지. 시안 프레임 이름에 흐름 번호가 이미 박혀 있다(`PC/LOGIN/4c2`, `registry/governance/screen-naming-policy.json`), 개발 쪽은 촬영기가 이미 Playwright로 눌러가며 찍는다. 도착 화면 판정은 값 대조를 그대로 쓴다 → 값 대조 뒤에 얹는 조각.

**내부망 조건 (river 2026-09-14):** 검수 PC에서 깃허브 **내려받기는 되고 올리기만 막혀 있다.** 따라서 정본을 매번 당겨오는 방식이 그대로 성립한다(파일로 들여오는 통로 불필요).

**① 걸음 완료 (2026-09-14, `feat/windows-capture` 가지):** `valueqa/` 파이썬 꾸러미 — 시안↔개발 값 대조로 후보 뽑기. `plugin-value-qa/ui.html`의 runMatcher·compareRows·doCompare를 옮긴 것(검수는 포털에서만 하므로 피그마 창 밖에서 돌아야 함). 자가검사가 **옛 엔진과 셈 동일**(값다름 6·더있음 1·밀림 7·주의 2·일치 2, 짝 17/17)까지 잠근다 — `npm test` vs `python3 -m valueqa.selftest`. padding은 후보에서 뺀다(퍼블리싱 소관). **커밋·푸시 완료 2026-09-14 (`60fbeaf`, origin/feat/windows-capture).**

**값 검수의 결과물은 '고치는 문서'다 (river 2026-09-14):** 이미지 검수처럼 보여 주는 화면이 아니라, 퍼블리싱·개발이 **일괄 반영**할 수 있는 md/가이드로 낸다(`valueqa/fixdoc.py`, `--지시서`). 같은 값으로 맞추면 되는 여러 곳은 한 줄로 묶고, 요소별 CSS 덩어리는 개발 화면에서 읽은 태그·class 로 적는다. **값부터 일괄로 고치게 한 뒤, 그림·CSS 눈검수는 최소한만** 한다 — 이것이 검수 흐름의 순서다.

**지시서에는 '어느 화면의 어느 항목'이 있어야 한다 (river 2026-09-14):** 고칠 것마다 `{화면키}-{번호}`(예: `CV-WEB-012-03`)를 붙이고 화면 이름·주소·시안 레이어 이름·요소 글자·개발 태그.class·화면 안 자리(위쪽 오른편)를 함께 적는다. 화면 여러 개는 `지시서묶음()`으로 한 문서에, **화면이 달라도 같은 고침은 맨 앞 '한꺼번에 고칠 것'에 모아** 일괄 반영하게 한다. 화면키는 포털 사람키를 그대로 쓴다.

**자리는 개발 화면 기준으로 (river 2026-09-14):** 디자인 레이어 이름·시안 프레임 이름은 디자이너가 임의로 붙인 것이라 개발·퍼블리싱이 못 알아본다. 지시서는 `#id` / `section.stats > div.card` 같은 **CSS 선택자**와 개발 화면 제목·주소를 앞세우고, 시안 이름은 맨 뒤 〈시안 …〉로만 둔다. 이를 위해 `plugin-value-qa/collect-core.js`를 **core-1.2**로 올려 요소의 `id`와 선택자(`sel`)를 함께 재게 했다(파생물은 `node plugin-value-qa/build-tools.js`; 하드코딩된 경로를 저장소 기준으로 고쳤고, 치환 시 `$&` 때문에 ui.html이 깨지던 것도 함수 치환으로 고침).

**② 조각 인수인계 (2026-09-14):** `capture-app/다음조각-토큰규정대조.md` 한 장이면 새 세션이 바로 이어서 할 수 있다. 정본 `registry/` 실제 구조 확인 완료 — 토큰은 `tokens/foundation.*.json`(`{value, cssVar}`)·`assets/css/tokens.css`, 컴포넌트 규격은 `components/*.json`, **개발 화면에서 컴포넌트를 알아보는 열쇠는 `governance/component-geometry-map.json`의 클래스 접두사(`s1-btn` 등)**. `tokens/component.tokens.json`은 은퇴(2026-07-02), `tokens/legacy/`는 옛 스냅샷. **가장 큰 미지수: 실제 서비스 화면이 `s1-*` 클래스를 쓰는지** — 착수 때 river에게 확인.

**실제 화면은 디자인시스템 클래스 이름을 안 쓴다 (river 2026-09-14):** `component-geometry-map.json`의 `s1-btn` 접두사는 전시 페이지 기준이라 그것만으로는 대부분 못 알아본다. 대응은 세 길 — ①**시안 쪽 정체를 짝 건너로 옮기기**(시안은 Figma 인스턴스라 이름이 정본과 맞고 ①의 짝 맞추기가 이미 이어 놓았다; `plugin-pick/code.js`가 `검수요소`에 mainComponent 이름·variant를 싣게 하면 됨 — 이것을 먼저) ②프로젝트마다 한 번만 잇는 대응표 ③모양으로 추측(낮은 신뢰도). 못 알아본 것은 조용히 넘기고 개수만 알린다.

**메인 통합 완료 (2026-09-14, `fab44e3`):** `feat/windows-capture` → `main`. 부딪힌 것은 `.claude/launch.json` 하나(메인의 `run_portal.py` + 가지의 촬영준비사이트 항목). 합친 자리에서 포털 84개·값 대조 자가검사·옛 엔진 재현 모두 통과. 이제 `~/dev-screen-qa`(main) 한 곳에서 이어간다.
