# C 조각 — 플러그인 1.0 나머지(번호 중심 패널 · 캔버스 포인팅 · 디자인 원본값 표시)

**여기서 일한다:** `/Users/designgroup_02/dev-screen-qa-plugin` · 브랜치 `feat/image-qa-plugin-panel`
(같은 저장소의 별도 작업 폴더. B 조각과 **파일이 겹치므로** 반드시 이 폴더에서 한다.)

## 할 일 (CLAUDE.md 21번 대기열 1번)
- 번호 중심 패널 / 캔버스에서 번호 짚기 / 디자인 원본값(살아 있는 Figma 값) 표시.
- 금지: 자동으로 오류를 **확정**하기, 정확한 개발값을 **추측**하기.

## 지켜야 할 것
- 검수 자료(PNG·elements JSON)는 이 폴더에 **없다**. 화면 10개 재기가 필요하면 B 세션과 순서를 맞춰
  `/Users/designgroup_02/dev-screen-qa`에서 한 번에 한 세션만 돌린다(`MEASURING.lock` 규칙).
- `git add .` 금지. 커밋 전 멈추고 보고.

## 합칠 때
B와 C는 `plugin-image-qa/ui.html`을 함께 고친다. B는 검수 엔진 쪽, C는 화면(패널·캔버스) 쪽이라
자리가 다르지만, 합칠 때 한 번은 손으로 맞춰야 할 수 있다.
