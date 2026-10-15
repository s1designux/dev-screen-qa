---
name: portal-auto-inspect
description: "포털 자동 검수 1차(2026-09-10) — 페이지 열면 후보 표출, 엔진 한 벌 공유, 저장 표, 재기 도구, 미확인 범위"
metadata: 
  node_type: memory
  type: project
  modified: 2026-09-10T04:27:02.762Z
---

2026-09-10 river 지시: "후보찾기 버튼 말고 화면을 열면 검수 내용이 바로 표출". 1차 완료(커밋 전).

**구조:** `mvp0/auto_inspect.py`(저장·HTTP·화면 조각·엔진 손잡이) / `mvp0/figma_elements.py`(REST 트리 → code.js collectDesign 모양).
엔진은 `plugin-image-qa/ui.html`을 `/engine/ui.html`로 내보내며 마지막 시작 줄만 손잡이로 치환 → 숨은 iframe → `comparePair()` 직접 호출.
페이지 상세 GET은 읽기 전용(테스트가 DB 덤프 동일성을 검사함). 실행·저장은 페이지 JS의 POST(`/auto/<page>/materials|result|fail|retry`, `candidate/<id>/status|register`).
후보 상태 open/excluded/variable, '지적 등록'만 `inspection_issue` 생성(dedup `{page}|{노드}|{kind}|auto`).

**검증:** `validation/test_auto_inspect.py` 7개 · `validation-image-qa/repro/portal_parity.js`(플러그인 재현과 후보 동일, findid 10건·체류시간 111건, 정답 7/7) · 브라우저 실물(스크래치 DB, 후보 62·제외·등록·핀 생성 확인).
**미확인:** 실제 Figma 토큰으로 REST 프레임 읽기(합성 REST 문서로만 검사). 앱 화면·큰 캡처(>4096) 미검증.

**검수 시안 바로 받기(2026-09-10, river 결정 "한 동작, 받는 쪽이 구분"):** 촬영 준비 플러그인 `dev-screen-qa-capture/capture-app/plugin-pick`이
포털 `/api/frames`에 묻고 검수 화면이 있으면 단추가 '검수 시안 바꾸기'(주황) → `/api/design`으로 PNG+collectDesign 모양 요소+설정 전송(토큰 불필요).
포털 `mvp0/design_receive.py`: `page_design_link`(페이지→최신 판)·`page_design_event`(append-only)·`auto_run`은 (run_id, design_id)별(옛 표는 legacy_alter_table로 이주).
검증: `validation/test_design_receive.py` 5개 + 스크래치 포털에서 플러그인 UI(가짜 code.js) ↔ 포털 왕복 확인. **실제 Figma 안에서 플러그인 실행은 미확인**(river가 눌러봐야 함).
플러그인 쪽 변경은 다른 저장소(dev-screen-qa-capture)라 커밋은 river/별도.
**앱 흐름 완결(2026-09-10, river: "과속보기 말고 우비스 버스만"):** plugin-pick '원본 인식하기' 꾸러미에 검수요소/검수설정/틀 동봉 →
`site/server.py _받기`가 `디자인/NNN_elements.json`으로 저장 → `draft.py`가 초안에 자리 전달 → `site/intake.py _시안판등록`이
intake_asset/intake_design/design_elements/page_design_link(+event)를 포털 DB에 씀. 검증: scratchpad `verify_intake.py`(가짜 결과폴더로 접수 → 후보 탭·materials OK).
촬영기가 바로 넣은 페이지의 '개발 화면 변경' 팝업은 같은 화면 묶음 사진 중 고름(`page_capture_event`).
플러그인 manifest는 http로 localhost만 허용(127.0.0.1은 manifest 오류).

**스크래치 확인법:** scratchpad `seed_scratch.py`(체류시간 세트 주입) + `run_scratch.py`(8777) — 회사 화면 자료라 커밋 금지.

관련: [[image-qa-policy-rules]] [[image-qa-variable-text]] [[worktree-stash-incident]]
