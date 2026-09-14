# engine — 검수 비교 엔진 (원본 한 벌)

`ui.html` 한 파일이 **규칙과 비교 알고리즘의 원본**이다. 복사본을 만들지 않는다.
포털(`mvp0/auto_inspect.py`)이 이 파일을 `/engine/ui.html` 로 내보내 숨은 틀에서 돌린다.

- 규칙의 **알고리즘**은 여기, 규칙의 **값**(켜고 끄기·기준값·예외)은 포털 DB `policy_rule` (CLAUDE.md 8번).
- 자체 검사: `cd validation-image-qa/repro && ./selftest.sh`
- 화면 10개 회귀: `cd validation-image-qa/repro && ./measure_all.sh ../../engine/ui.html <접두사>`

2026-09-14 이전에는 `plugin-image-qa/ui.html` 이었다(피그마 플러그인과 한 폴더). 플러그인은 폐기했고
(`legacy/plugin-image-qa/`), 엔진만 여기로 옮겼다.
