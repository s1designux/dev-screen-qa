# [새 세션용] 검수 정책 규칙화 — 다음 조각

## 0. 먼저 할 일
- 저장소 루트 `/Users/designgroup_02/dev-screen-qa` 의 `CLAUDE.md` 를 읽고 전제로 삼는다.
- 브랜치 `feat/image-qa-bottom-range` · 작업 폴더 `validation-image-qa/repro/`
- `RULE_PROPOSALS.md` 를 읽는다. **#9(3안 정렬)·#10(탭 줄) 승인·적용됨**, #5·#6·#8 보류, #7 거절, #1 보류.

## 1. 여기까지 끝난 것 (2026-09-08)

**볼 것 647건의 정체를 갈랐고, 가장 큰 원인(밀림)을 고쳐 원본에 반영했다.**

| 단계 | 볼 것 | 정답 |
|---|---|---|
| 처음 | 647 | 8/8 |
| #9 3안 정렬(구역 밀림을 이웃 ±8px 안에서, 푸터 예외) | 572 | 8/8 |
| #10 탭 줄(탭 구성 차이는 오류 아님) | **529** | **7/7** (#7 탭 10→4는 오류 아님으로 재확정) |

- river 원칙(확정): **밀림은 화면 공통으로 한 번, 밀림 뺀 뒤 다른 컴포넌트만 따로.** 판정 버튼으로 수백 건을 river에게 넘기지 않는다 — 걸러내는 건 검수기 제작자 일.
- 탭 줄: GNB 아래 탭은 열린 만큼만 보인다 → 구성 차이 오류 아님. **선택된 탭(흰 바탕·파란 글씨)은 글자만 같으면 됨, 자리 무관.**
- 정답은 이제 **7건** (`answers_stay.json`).
- 원본 `plugin-image-qa/ui.html` 변경됨(42줄 추가·2줄 수정), **커밋 전 보고 대기.**

## 2. 이 조각에서 할 일

1. **보류한 #5·#6·#8을 새 기준선(529) 위에서 다시 잰다.** 근거가 검수기 자신의 점수라 river가 못 믿었던 것 — 이제 정렬이 고쳐졌으니 다시 볼 만하다. 재면서 **새로 생긴 후보는 내가 먼저 걸러** river에겐 못 가른 것만 보인다.
2. **같은 밀림이 컴포넌트마다 되풀이되는 「위치」 106건을 구역당 한 줄로 묶는다.** (river 원칙 그대로. 화면당 3~6줄이 된다.)
3. 선택된 탭을 개발 탭 줄 안에서 찾아 **글자만 대조**하기 — 노선관리 「노선관리」↔「노선 관리」 띄어쓰기가 지금은 '없어짐'으로 올라온다.
4. 검수기가 게시판의 가짜 크롬탭(browser_tab, 글자 0개)을 못 거르는 구멍 — #3 규칙 보강.

## 3. 쓸 수 있는 자료 (이미 폴더에 있음 · 커밋 안 됨)
화면 10개가 바로 돌아간다. 요소 목록·PNG 이름은 `README.md` 참조.
`board`(게시판) · `vehicle`(차량위치) · `dash`(대시보드) · `door`(출입문) ·
`stay`(체류시간) · `findid` · `login` · `table` · `codes` · `route`(노선관리, `FORCE_TY=99` 필요)

**주의:** `elements_route.json` 은 286줄이 빠진 옛 파일이다. **`elements_route_plugin.json`(완전본)을 쓴다.**
체류시간은 `elements_stay_full.json`(752줄)을 쓴다.

10개를 한 번에 돌리는 방법(각 화면 env는 이 파일 4절 표와 같다):
```bash
ELEMENTS_JSON=elements_stay_full.json DESIGN_PNG=design_stay_1920x1080.png \
DEV_PNG=dev_stay_1920x1081.png DESIGN_MAX=4096 node run.js ../../plugin-image-qa/ui.html m_stay_base
```

## 4. 화면별 실행값 (2026-09-08 기준선 — #9·#10 반영 뒤. 결과 파일 `m2_<화면>.json`)

| 화면 | elements | 디자인 PNG | 개발 PNG | FORCE_TY | 후보/숨김/볼것 |
|---|---|---|---|---|---|
| board | elements_board.json | design_board_1920x1898.png | dev_board_1920x1816.png | – | 138 / 73 / 65 |
| vehicle | elements_vehicle.json | design_vehicle_720x1560.png | dev_vehicle_360x780.png | – | 72 / 10 / 62 |
| dash | elements_dash.json | design_dash_360x1071.png | dev_dash_360x1031.png | – | 38 / 19 / 19 |
| door | elements_door.json | design_door_186x400.png | dev_door_196x436.png | – | 21 / 8 / 13 |
| stay | elements_stay_full.json | design_stay_1920x1080.png | dev_stay_1920x1081.png | – | 227 / 109 / 118 |
| findid | elements.json | design_1920x1080.png | dev_1920x934.png | – | 13 / 0 / 13 |
| login | elements_login.json | design_login_1920x1080.png | dev_login_1920x934.png | – | 6 / 0 / 6 |
| table | elements_table.json | design_table_1200x700.png | dev_table_1200x700.png | – | 12 / 9 / 3 |
| codes | elements_codes.json | design_codes_1200x760.png | dev_codes_1200x760.png | – | 3 / 0 / 3 |
| route | elements_route_plugin.json | design_route_1920x1080.png | dev_route_1920x1080.png | 99 | 451 / 224 / 227 |

## 5. 세는 기준 (이번에 통일함)
- **볼 것** = 후보의 `status`가 `variable`·`excluded`가 **아닌** 것.
- `policy` 문자열에 '가변'이 들어갔다고 다 숨겨지는 게 아니다(글자 내용류 후보만 접힌다).
  예전 기록의 '가변접힘' 숫자와 이 숫자는 다르다 — **`status`로 센다.**
- 규칙 하나의 효과는 **끄고 재는 것**이 제일 정확하다(`ui.html` 사본에서 해당 `test` 첫 줄에 `return null;`).

## 6. 알아둘 것
- 겹치기가 틀어진 화면의 결과는 헛것이다. `*.align.png` 를 **눈으로** 먼저 본다.
- 대시보드는 아래로 갈수록 20~25px 밀린다 → 아래쪽 결과 신뢰도 낮음.
- 출입문은 겹치기 0.77·디자인 3줄↔개발 6줄이라 **근거로 쓰지 않는다.**
- 로컬 AI 읽기는 화면당 7~20분, 한 번에 하나만 돌린다(Ollama가 하나뿐).
  AI의 **띄어쓰기 판독은 못 믿는다**(3건 중 1건). 반드시 캡처를 잘라 눈으로 확인한다.
- 로고 워드마크 누락·탭 10→4는 정책이 아니라 **엔진이 후보를 못 내는 별건**이다.
- 보고는 **① 결과(표·이미지) ② 결정할 것** 두 칸뿐. 비교·검수는 말로 설명하지 말고 이미지나 HTML로 만든다.
- `git add .` 금지. 회사 화면 자료·산출물은 커밋하지 않는다. 커밋 전 멈추고 보고.

## 7. 이 조각이 끝나면 (CLAUDE.md 21번 대기열)
1. `plugin-image-qa/` 1.0 나머지 — 번호 중심 패널 / 캔버스 포인팅 / 디자인 원본값 표시
2. 차수 연동 2차 — 새 차수 추가 + 이전 지적 끌고와 사람이 판단
3. 실제 검수 데이터 더 넣기 → 4. A4 반출 본구현
